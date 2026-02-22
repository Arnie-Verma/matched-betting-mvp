"""Admin/internal lifecycle transition endpoints for bookmakers."""
from __future__ import annotations

import os
import secrets
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.core.auth import UserClaims, optional_user
from api.core.database import get_db
from api.services.activation_evidence_registry_service import (
    ActivationEvidenceRegistrationError,
    ActivationEvidenceRegistryService,
)
from api.services.bookmaker_lifecycle_service import (
    BookmakerLifecycleService,
    LifecycleTransitionError,
)


DEFAULT_LIFECYCLE_ALLOWED_ROLES = "admin,ops"

router = APIRouter(prefix="/admin/bookmakers", tags=["bookmaker-lifecycle"])


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
    configured = os.getenv("BOOKMAKER_LIFECYCLE_ALLOWED_ROLES", DEFAULT_LIFECYCLE_ALLOWED_ROLES)
    return {
        role.strip().lower()
        for role in configured.split(",")
        if role and role.strip()
    }


def require_lifecycle_admin_access(
    request: Request,
    claims: Optional[UserClaims] = Depends(optional_user),
) -> Dict[str, Any]:
    internal_token = os.getenv("BOOKMAKER_LIFECYCLE_INTERNAL_TOKEN")
    provided_token = request.headers.get("x-internal-admin-token")
    if internal_token and provided_token and secrets.compare_digest(provided_token, internal_token):
        return {
            "source": "internal_token",
            "actor_sub": "internal-token",
            "actor_email": None,
        }

    if not claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: lifecycle transition requires admin auth or internal token",
        )

    allowed_roles = _load_allowed_roles()
    user_roles = _extract_roles(claims)
    if user_roles.isdisjoint(allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: insufficient role for lifecycle transition",
        )

    return {
        "source": "authenticated",
        "actor_sub": claims.sub,
        "actor_email": claims.email,
        "roles": sorted(user_roles),
    }


class LifecycleTransitionRequest(BaseModel):
    to_state: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=3, max_length=2000)
    metadata: Optional[Dict[str, Any]] = None


class LifecycleTransitionResponse(BaseModel):
    bookmaker_code: str
    from_state: str
    to_state: str
    is_active: bool
    transition_id: int
    transitioned_at: str


class ActivationEvidenceRegisterRequest(BaseModel):
    evidence_type: str = Field(..., pattern="^(validation|canary)$")
    bookmaker_code: str = Field(..., min_length=1, max_length=30)
    artifact_path: str = Field(..., min_length=1, max_length=500)
    metadata: Optional[Dict[str, Any]] = None


class ActivationEvidenceRegisterResponse(BaseModel):
    evidence_id: int
    evidence_type: str
    bookmaker_code: str
    artifact_path: str
    artifact_sha256: str
    generated_at: Optional[str] = None
    ended_at: Optional[str] = None
    validation_in_scope_fail_count: Optional[int] = None
    canary_gate_pass: Optional[bool] = None


@router.post("/lifecycle-evidence/register", response_model=ActivationEvidenceRegisterResponse)
def register_activation_evidence(
    request: ActivationEvidenceRegisterRequest,
    access: Dict[str, Any] = Depends(require_lifecycle_admin_access),
    db: Session = Depends(get_db),
):
    try:
        record = ActivationEvidenceRegistryService.register_from_artifact_path(
            db,
            evidence_type=request.evidence_type,
            bookmaker_code=request.bookmaker_code,
            artifact_path=request.artifact_path,
            created_by=access.get("actor_sub"),
            created_by_email=access.get("actor_email"),
            metadata=request.metadata or {},
        )
    except ActivationEvidenceRegistrationError as exc:
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

    return ActivationEvidenceRegisterResponse(
        evidence_id=record.evidence_id,
        evidence_type=record.evidence_type,
        bookmaker_code=record.bookmaker_code,
        artifact_path=record.artifact_path,
        artifact_sha256=record.artifact_sha256,
        generated_at=record.generated_at.isoformat() if record.generated_at else None,
        ended_at=record.ended_at.isoformat() if record.ended_at else None,
        validation_in_scope_fail_count=record.validation_in_scope_fail_count,
        canary_gate_pass=record.canary_gate_pass,
    )


@router.post("/{bookmaker_code}/lifecycle", response_model=LifecycleTransitionResponse)
def transition_bookmaker_lifecycle(
    bookmaker_code: str,
    request: LifecycleTransitionRequest,
    access: Dict[str, Any] = Depends(require_lifecycle_admin_access),
    db: Session = Depends(get_db),
):
    try:
        result = BookmakerLifecycleService.transition_bookmaker_state(
            db,
            bookmaker_code=bookmaker_code,
            to_state=request.to_state,
            reason=request.reason,
            transitioned_by=access.get("actor_sub"),
            transitioned_by_email=access.get("actor_email"),
            transition_source=access.get("source", "api"),
            transition_metadata=request.metadata or {},
        )
    except LifecycleTransitionError as exc:
        status_code = status.HTTP_400_BAD_REQUEST
        if exc.reason_code == "bookmaker_not_found":
            status_code = status.HTTP_404_NOT_FOUND
        raise HTTPException(
            status_code=status_code,
            detail={
                "reason_code": exc.reason_code,
                "message": str(exc),
                "from_state": exc.from_state,
                "to_state": exc.to_state,
                "failed_criteria": exc.failed_criteria,
            },
        ) from exc

    return LifecycleTransitionResponse(
        bookmaker_code=result.bookmaker_code,
        from_state=result.from_state,
        to_state=result.to_state,
        is_active=result.is_active,
        transition_id=result.transition_id,
        transitioned_at=result.transitioned_at.isoformat(),
    )
