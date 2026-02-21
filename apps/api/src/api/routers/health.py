# apps/api/src/api/routers/health.py
"""
Health check and monitoring endpoints.

Provides:
- /health - Basic health check
- /health/scrapers - Scraper status including circuit breaker states
- /health/database - Database connection status
- /health/detailed - Combined detailed health status
"""
import os
import json
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from api.core.auth import UserClaims, optional_user
from api.core.database import get_db
from api.models import OddsSnapshot, Bookmaker, Event
from api.services.observability_service import (
    ObservabilityThresholds,
    build_observability_report,
    emit_observability_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _extract_roles(claims: UserClaims) -> set[str]:
    raw = claims.raw_claims or {}
    roles: set[str] = set()

    for key in ("roles", "role"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            roles.add(value.strip().lower())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    roles.add(item.strip().lower())
    return roles


def require_scraper_health_access(
    request: Request,
    claims: Optional[UserClaims] = Depends(optional_user),
) -> dict:
    """
    Access policy for /health/scrapers:
    - allow authenticated users
    - OR allow explicit internal token access (`X-Internal-Health-Token`)
    - optional role restriction via `HEALTH_SCRAPERS_ALLOWED_ROLES`
    """
    internal_token = os.getenv("HEALTH_SCRAPERS_INTERNAL_TOKEN")
    provided_token = request.headers.get("x-internal-health-token")
    if internal_token and provided_token and secrets.compare_digest(provided_token, internal_token):
        emit_observability_event(
            category="security",
            metric_name="access_decision",
            source="api",
            endpoint=request.url.path,
            action_type="scraper_health_access_allowed",
            payload={"mode": "internal_token"},
        )
        return {"mode": "internal_token"}

    if not claims:
        emit_observability_event(
            category="security",
            metric_name="access_decision",
            source="api",
            endpoint=request.url.path,
            action_type="scraper_health_access_denied",
            payload={"reason": "unauthenticated"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: /health/scrapers requires auth or internal token",
        )

    allowed_roles_raw = os.getenv("HEALTH_SCRAPERS_ALLOWED_ROLES", "").strip()
    if allowed_roles_raw:
        allowed_roles = {
            item.strip().lower()
            for item in allowed_roles_raw.split(",")
            if item.strip()
        }
        if allowed_roles:
            user_roles = _extract_roles(claims)
            if user_roles.isdisjoint(allowed_roles):
                emit_observability_event(
                    category="security",
                    metric_name="access_decision",
                    source="api",
                    endpoint=request.url.path,
                    action_type="scraper_health_access_denied",
                    payload={"reason": "role_denied", "allowed_roles": sorted(allowed_roles)},
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: insufficient role for /health/scrapers",
                )

    emit_observability_event(
        category="security",
        metric_name="access_decision",
        source="api",
        endpoint=request.url.path,
        action_type="scraper_health_access_allowed",
        payload={"mode": "authenticated", "sub": claims.sub},
    )
    return {"mode": "authenticated", "sub": claims.sub}


class BookmakerHealth(BaseModel):
    """Health status for a single bookmaker"""
    code: str
    name: str
    status: str  # healthy, degraded, unhealthy
    last_scrape: Optional[datetime] = None
    minutes_since_scrape: Optional[float] = None
    current_odds_count: int = 0
    circuit_breaker_state: str = "unknown"
    is_active: bool = True


class ScraperHealthResponse(BaseModel):
    """Response for scraper health check"""
    status: str  # healthy, degraded, unhealthy
    active_bookmakers: int
    healthy_bookmakers: int
    total_current_odds: int
    bookmakers: List[BookmakerHealth]
    last_check: datetime


class DatabaseHealthResponse(BaseModel):
    """Response for database health check"""
    status: str
    connection_ok: bool
    events_upcoming: int
    current_odds_count: int
    bookmakers_active: int
    response_time_ms: float


class DetailedHealthResponse(BaseModel):
    """Combined detailed health response"""
    status: str
    timestamp: datetime
    scrapers: ScraperHealthResponse
    database: DatabaseHealthResponse
    environment: str


def get_circuit_breaker_state(bookmaker_code: str) -> str:
    """Get circuit breaker state from Redis."""
    try:
        import redis
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        breaker_key = f"breaker:{bookmaker_code}"
        data = redis_client.get(breaker_key)
        if data:
            return json.loads(data).get("state", "closed")
        return "closed"
    except Exception as e:
        logger.warning(f"Could not get circuit breaker state for {bookmaker_code}: {e}")
        return "unknown"


@router.get("/health")
def health() -> dict[str, str]:
    """Basic health check."""
    return {"status": "ok"}


@router.get("/health/scrapers", response_model=ScraperHealthResponse)
async def scraper_health(
    _access: dict = Depends(require_scraper_health_access),
    db: Session = Depends(get_db),
):
    """
    Get health status of all active scrapers.

    Returns:
    - Per-bookmaker status (healthy/degraded/unhealthy)
    - Time since last scrape
    - Current odds count
    - Circuit breaker state
    """
    # Get all active bookmakers
    bookmakers = db.query(Bookmaker).filter(Bookmaker.is_active == True).all()

    # Get current odds counts per bookmaker
    odds_counts = dict(
        db.query(
            OddsSnapshot.bookmaker_id,
            func.count(OddsSnapshot.id)
        )
        .filter(OddsSnapshot.is_current == True)
        .group_by(OddsSnapshot.bookmaker_id)
        .all()
    )

    # Get latest odds timestamp per bookmaker
    latest_timestamps = dict(
        db.query(
            OddsSnapshot.bookmaker_id,
            func.max(OddsSnapshot.timestamp)
        )
        .filter(OddsSnapshot.is_current == True)
        .group_by(OddsSnapshot.bookmaker_id)
        .all()
    )

    now = datetime.now(timezone.utc)
    bookmaker_health_list = []
    healthy_count = 0
    total_odds = 0

    for bm in bookmakers:
        odds_count = odds_counts.get(bm.id, 0)
        total_odds += odds_count

        last_scrape = latest_timestamps.get(bm.id)
        minutes_since = None
        if last_scrape:
            # Handle timezone-naive timestamps
            if last_scrape.tzinfo is None:
                last_scrape = last_scrape.replace(tzinfo=timezone.utc)
            minutes_since = (now - last_scrape).total_seconds() / 60

        # Get circuit breaker state
        breaker_state = get_circuit_breaker_state(bm.code)

        # Determine health status
        if breaker_state == "open":
            status = "unhealthy"
        elif minutes_since is None:
            status = "unhealthy"  # Never scraped
        elif minutes_since > 30:
            status = "unhealthy"  # Stale data
        elif minutes_since > 15:
            status = "degraded"  # Getting stale
        elif odds_count < 10:
            status = "degraded"  # Low odds count
        else:
            status = "healthy"
            healthy_count += 1

        bookmaker_health_list.append(BookmakerHealth(
            code=bm.code,
            name=bm.name,
            status=status,
            last_scrape=last_scrape,
            minutes_since_scrape=round(minutes_since, 1) if minutes_since else None,
            current_odds_count=odds_count,
            circuit_breaker_state=breaker_state,
            is_active=bm.is_active
        ))

    # Determine overall status
    active_count = len(bookmakers)
    if healthy_count == active_count and active_count > 0:
        overall_status = "healthy"
    elif healthy_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return ScraperHealthResponse(
        status=overall_status,
        active_bookmakers=active_count,
        healthy_bookmakers=healthy_count,
        total_current_odds=total_odds,
        bookmakers=bookmaker_health_list,
        last_check=now
    )


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health(db: Session = Depends(get_db)):
    """Check database connection and basic stats."""
    import time
    start = time.time()

    try:
        # Simple query to test connection
        db.execute(text("SELECT 1"))

        # Get counts
        events_upcoming = db.query(func.count(Event.id)).filter(
            Event.start_time > datetime.now(timezone.utc)
        ).scalar() or 0

        current_odds = db.query(func.count(OddsSnapshot.id)).filter(
            OddsSnapshot.is_current == True
        ).scalar() or 0

        active_bookmakers = db.query(func.count(Bookmaker.id)).filter(
            Bookmaker.is_active == True
        ).scalar() or 0

        response_time = (time.time() - start) * 1000

        return DatabaseHealthResponse(
            status="healthy",
            connection_ok=True,
            events_upcoming=events_upcoming,
            current_odds_count=current_odds,
            bookmakers_active=active_bookmakers,
            response_time_ms=round(response_time, 2)
        )

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        response_time = (time.time() - start) * 1000
        return DatabaseHealthResponse(
            status="unhealthy",
            connection_ok=False,
            events_upcoming=0,
            current_odds_count=0,
            bookmakers_active=0,
            response_time_ms=round(response_time, 2)
        )


@router.get("/health/detailed", response_model=DetailedHealthResponse)
async def detailed_health(
    _access: dict = Depends(require_scraper_health_access),
    db: Session = Depends(get_db),
):
    """Comprehensive health check combining all subsystems."""
    scrapers = await scraper_health(_access=_access, db=db)
    database = await database_health(db)

    # Determine overall status
    if scrapers.status == "healthy" and database.status == "healthy":
        overall_status = "healthy"
    elif scrapers.status == "unhealthy" or database.status == "unhealthy":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return DetailedHealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        scrapers=scrapers,
        database=database,
        environment=os.getenv("ENVIRONMENT", "development")
    )


@router.get("/health/telemetry")
async def telemetry_health(
    hours: int = 24,
    limit: int = 5000,
    _access: dict = Depends(require_scraper_health_access),
):
    """
    Return observability summary + threshold evaluation for a trailing window.
    """
    report = build_observability_report(
        hours=max(1, int(hours)),
        limit=max(100, int(limit)),
        thresholds=ObservabilityThresholds.from_env(),
    )
    return report
