# apps/api/src/api/routers/metadata.py
"""
Metadata endpoints for fetching bookmakers, sports, competitions.
Used by frontend filters to populate dropdowns.
"""
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.auth import get_current_user, UserClaims
from api.models import Bookmaker, Sport, Competition, User
from api.services.subscription_service import SubscriptionService


router = APIRouter(prefix="/metadata", tags=["metadata"])


def _normalize_competition_name(name: str) -> str:
    return (name or "").strip().lower()


# Only expose the leagues we actively support in the odds matcher UI
ALLOWED_COMPETITIONS = [
    {
        "key": "a-league",
        "display": "A-League",
        "aliases": ["a-league", "a league", "a-league men", "a-league women"],
    },
    {"key": "afl", "display": "AFL", "aliases": ["afl"]},
    {"key": "boxing", "display": "Boxing", "aliases": ["boxing", "upcoming fights"]},
    {
        "key": "epl",
        "display": "EPL",
        "aliases": ["epl", "premier league", "english premier league"],
    },
    {
        "key": "ligue 1",
        "display": "French Ligue 1",
        "aliases": ["ligue 1", "french ligue 1"],
    },
    {
        "key": "bundesliga",
        "display": "German Bundesliga",
        "aliases": ["bundesliga", "german bundesliga", "german bundesliga women"],
    },
    {
        "key": "serie a",
        "display": "Italian Serie A",
        "aliases": ["serie a", "italian serie a"],
    },
    {
        "key": "mls",
        "display": "Major League Soccer",
        "aliases": ["mls", "major league soccer"],
    },
    {"key": "nba", "display": "NBA", "aliases": ["nba"]},
    {"key": "nbl", "display": "NBL", "aliases": ["nbl"]},
    {"key": "nhl", "display": "NHL", "aliases": ["nhl"]},
    {"key": "nrl", "display": "NRL", "aliases": ["nrl"]},
    {
        "key": "la liga",
        "display": "Spanish La Liga",
        "aliases": ["la liga", "spanish la liga", "spanish la-liga"],
    },
    {
        "key": "ucl",
        "display": "UEFA Champions League",
        "aliases": ["ucl", "champions league", "uefa champions league"],
    },
]

ALLOWED_ORDER = [item["key"] for item in ALLOWED_COMPETITIONS]
ALIAS_LOOKUP = {
    alias: item["key"]
    for item in ALLOWED_COMPETITIONS
    for alias in item["aliases"]
}
DISPLAY_LOOKUP = {item["key"]: item["display"] for item in ALLOWED_COMPETITIONS}


class BookmakerResponse(BaseModel):
    id: int
    code: str
    display_name: str
    tier: str


class SportResponse(BaseModel):
    id: int
    code: str
    display_name: str


class CompetitionResponse(BaseModel):
    id: int
    sport_id: int
    short_name: str
    full_name: str


@router.get("/bookmakers")
async def get_bookmakers(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[BookmakerResponse]:
    """
    Get all bookmakers for filter dropdowns.
    Returns bookmakers allowed for the user's plan, sorted alphabetically by display_name.
    """
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        user = User(
            clerk_user_id=user_claims.sub,
            email=user_claims.email or f"{user_claims.sub}@temp.com",
            email_verified=user_claims.email_verified or False,
            current_plan="free",
            plan_status="active"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    subscription_service = SubscriptionService()
    allowed_bookmakers = subscription_service.get_allowed_bookmakers(db, user)

    bookmakers = (
        db.query(Bookmaker)
        .filter(Bookmaker.code.in_(allowed_bookmakers))
        .order_by(Bookmaker.display_name)
        .all()
    )

    return [
        BookmakerResponse(
            id=bm.id,
            code=bm.code,
            display_name=bm.display_name,
            tier=bm.scraping_config.get('tier', 'unknown') if bm.scraping_config else 'unknown'
        )
        for bm in bookmakers
    ]


@router.get("/sports")
async def get_sports(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[SportResponse]:
    """
    Get all sports for filter dropdowns.
    Returns all sports sorted alphabetically by display_name.
    """
    sports = db.query(Sport).order_by(Sport.display_name).all()

    return [
        SportResponse(
            id=sport.id,
            code=sport.code,
            display_name=sport.display_name
        )
        for sport in sports
    ]


@router.get("/competitions")
async def get_competitions(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[CompetitionResponse]:
    """
    Get all competitions/leagues for filter dropdowns.
    Returns only supported competitions, deduped and sorted in preferred order.
    """
    competitions = db.query(Competition).filter(Competition.is_active == True).all()

    filtered: dict[str, CompetitionResponse] = {}
    for comp in competitions:
        norm_short = _normalize_competition_name(comp.short_name)
        norm_full = _normalize_competition_name(comp.name)
        key = ALIAS_LOOKUP.get(norm_short) or ALIAS_LOOKUP.get(norm_full)
        if not key:
            continue

        if key in filtered:
            continue  # Dedupe by canonical key

        filtered[key] = CompetitionResponse(
            id=comp.id,
            sport_id=comp.sport_id,
            short_name=DISPLAY_LOOKUP.get(key, comp.short_name),
            full_name=comp.name
        )

    # Preserve preferred order; ignore missing leagues quietly
    ordered = [filtered[key] for key in ALLOWED_ORDER if key in filtered]
    return ordered
