"""Admin/internal rollout control-plane endpoints."""
from __future__ import annotations

import os
import secrets
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.auth import UserClaims, optional_user
from api.core.database import get_db
from api.services.rollout_control_service import RolloutControlService, RolloutPolicyError


DEFAULT_ROLLOUT_ALLOWED_ROLES = "admin,ops"

router = APIRouter(prefix="/admin/rollout", tags=["rollout-control"])


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


def _load_allowed_roles() -> set[str]:
    configured = os.getenv("BOOKMAKER_ROLLOUT_ALLOWED_ROLES", DEFAULT_ROLLOUT_ALLOWED_ROLES)
    return {role.strip().lower() for role in configured.split(",") if role and role.strip()}


def require_rollout_admin_access(
    request: Request,
    claims: Optional[UserClaims] = Depends(optional_user),
) -> Dict[str, Any]:
    internal_token = os.getenv("BOOKMAKER_ROLLOUT_INTERNAL_TOKEN")
    provided_token = request.headers.get("x-internal-rollout-token")
    if internal_token and provided_token and secrets.compare_digest(provided_token, internal_token):
        return {
            "source": "internal_token",
            "actor_sub": "internal-token",
            "actor_email": None,
        }

    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: rollout control requires admin auth or internal token",
        )

    allowed_roles = _load_allowed_roles()
    user_roles = _extract_roles(claims)
    if user_roles.isdisjoint(allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: insufficient role for rollout control",
        )

    return {
        "source": "authenticated",
        "actor_sub": claims.sub,
        "actor_email": claims.email,
        "roles": sorted(user_roles),
    }


class RolloutPolicyUpdateRequest(BaseModel):
    rollout_mode: Optional[str] = Field(default=None, pattern="^(full|canary|disabled)$")
    sport_cohort: Optional[List[str]] = None
    competition_cohort: Optional[List[str]] = None
    bookmaker_cohort: Optional[List[str]] = None
    policy_metadata: Optional[Dict[str, Any]] = None


class KillSwitchRequest(BaseModel):
    enabled: bool


class RolloutPolicyResponse(BaseModel):
    scope: str
    rollout_mode: str
    kill_switch_enabled: bool
    sport_cohort: List[str]
    competition_cohort: List[str]
    bookmaker_cohort: List[str]
    policy_metadata: Dict[str, Any]
    policy_source: str
    updated_by: Optional[str] = None
    updated_by_email: Optional[str] = None
    updated_at: Optional[str] = None
    bookmaker_code: Optional[str] = None
    platform_code: Optional[str] = None


class RolloutStatusResponse(BaseModel):
    requested_sport: Optional[str] = None
    requested_competition: Optional[str] = None
    requested_bookmakers: List[str]
    eligible_lifecycle_states: List[str]
    runnable_count: int
    excluded_count: int
    bookmakers: List[Dict[str, Any]]


def _raise_rollout_policy_error(exc: RolloutPolicyError) -> None:
    status_code = status.HTTP_400_BAD_REQUEST
    if exc.reason_code == "bookmaker_not_found":
        status_code = status.HTTP_404_NOT_FOUND
    raise HTTPException(
        status_code=status_code,
        detail={
            "reason_code": exc.reason_code,
            "message": str(exc),
        },
    ) from exc


@router.get("/bookmakers/{bookmaker_code}/policy", response_model=RolloutPolicyResponse)
def get_bookmaker_rollout_policy(
    bookmaker_code: str,
    _access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    policy = RolloutControlService.get_bookmaker_policy(db, bookmaker_code=bookmaker_code)
    return RolloutPolicyResponse(**policy)


@router.put("/bookmakers/{bookmaker_code}/policy", response_model=RolloutPolicyResponse)
def set_bookmaker_rollout_policy(
    bookmaker_code: str,
    request: RolloutPolicyUpdateRequest,
    access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    try:
        policy = RolloutControlService.upsert_bookmaker_policy(
            db,
            bookmaker_code=bookmaker_code,
            rollout_mode=request.rollout_mode,
            sport_cohort=request.sport_cohort,
            competition_cohort=request.competition_cohort,
            bookmaker_cohort=request.bookmaker_cohort,
            policy_metadata=request.policy_metadata,
            updated_by=access.get("actor_sub"),
            updated_by_email=access.get("actor_email"),
        )
    except RolloutPolicyError as exc:
        _raise_rollout_policy_error(exc)
    return RolloutPolicyResponse(**policy)


@router.get("/bookmakers/{bookmaker_code}/kill-switch")
def get_bookmaker_kill_switch(
    bookmaker_code: str,
    _access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    policy = RolloutControlService.get_bookmaker_policy(db, bookmaker_code=bookmaker_code)
    return {
        "bookmaker_code": policy.get("bookmaker_code"),
        "kill_switch_enabled": bool(policy.get("kill_switch_enabled")),
    }


@router.put("/bookmakers/{bookmaker_code}/kill-switch")
def set_bookmaker_kill_switch(
    bookmaker_code: str,
    request: KillSwitchRequest,
    access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    try:
        policy = RolloutControlService.upsert_bookmaker_policy(
            db,
            bookmaker_code=bookmaker_code,
            kill_switch_enabled=request.enabled,
            updated_by=access.get("actor_sub"),
            updated_by_email=access.get("actor_email"),
        )
    except RolloutPolicyError as exc:
        _raise_rollout_policy_error(exc)
    return {
        "bookmaker_code": policy.get("bookmaker_code"),
        "kill_switch_enabled": bool(policy.get("kill_switch_enabled")),
    }


@router.get("/platforms/{platform_code}/policy", response_model=RolloutPolicyResponse)
def get_platform_rollout_policy(
    platform_code: str,
    _access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    policy = RolloutControlService.get_platform_policy(db, platform_code=platform_code)
    return RolloutPolicyResponse(**policy)


@router.put("/platforms/{platform_code}/policy", response_model=RolloutPolicyResponse)
def set_platform_rollout_policy(
    platform_code: str,
    request: RolloutPolicyUpdateRequest,
    access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    try:
        policy = RolloutControlService.upsert_platform_policy(
            db,
            platform_code=platform_code,
            rollout_mode=request.rollout_mode,
            sport_cohort=request.sport_cohort,
            competition_cohort=request.competition_cohort,
            bookmaker_cohort=request.bookmaker_cohort,
            policy_metadata=request.policy_metadata,
            updated_by=access.get("actor_sub"),
            updated_by_email=access.get("actor_email"),
        )
    except RolloutPolicyError as exc:
        _raise_rollout_policy_error(exc)
    return RolloutPolicyResponse(**policy)


@router.get("/platforms/{platform_code}/kill-switch")
def get_platform_kill_switch(
    platform_code: str,
    _access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    policy = RolloutControlService.get_platform_policy(db, platform_code=platform_code)
    return {
        "platform_code": policy.get("platform_code"),
        "kill_switch_enabled": bool(policy.get("kill_switch_enabled")),
    }


@router.put("/platforms/{platform_code}/kill-switch")
def set_platform_kill_switch(
    platform_code: str,
    request: KillSwitchRequest,
    access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    try:
        policy = RolloutControlService.upsert_platform_policy(
            db,
            platform_code=platform_code,
            kill_switch_enabled=request.enabled,
            updated_by=access.get("actor_sub"),
            updated_by_email=access.get("actor_email"),
        )
    except RolloutPolicyError as exc:
        _raise_rollout_policy_error(exc)
    return {
        "platform_code": policy.get("platform_code"),
        "kill_switch_enabled": bool(policy.get("kill_switch_enabled")),
    }


@router.get("/status", response_model=RolloutStatusResponse)
def get_rollout_status(
    sport: Optional[str] = Query(default=None),
    competition: Optional[str] = Query(default=None),
    bookmakers: Optional[str] = Query(default=None, description="Comma-separated bookmaker codes"),
    _access: Dict[str, Any] = Depends(require_rollout_admin_access),
    db: Session = Depends(get_db),
):
    requested_bookmakers = (
        [part.strip() for part in bookmakers.split(",") if part and part.strip()]
        if bookmakers
        else None
    )
    summary = RolloutControlService.rollout_status_summary(
        db,
        requested_sport=sport,
        requested_competition=competition,
        requested_bookmakers=requested_bookmakers,
    )
    return RolloutStatusResponse(**summary)
