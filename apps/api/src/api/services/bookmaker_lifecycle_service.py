"""Lifecycle state transition guard service for bookmaker promotion control."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import Session

from api.core.bookmaker_freeze import is_bookmaker_frozen
from api.models import Bookmaker, BookmakerLifecycleTransition


LIFECYCLE_STATES: Set[str] = {
    "backlog",
    "discovery_complete",
    "adapter_ready",
    "config_ready",
    "validation_passed",
    "canary_active",
    "active",
    "degraded",
    "disabled",
}

LIVE_RUNTIME_STATES: Set[str] = {"canary_active", "active", "degraded"}

ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    "backlog": {"discovery_complete", "disabled"},
    "discovery_complete": {"adapter_ready", "disabled"},
    "adapter_ready": {"config_ready", "disabled"},
    "config_ready": {"validation_passed", "disabled"},
    "validation_passed": {"canary_active", "disabled"},
    "canary_active": {"active", "degraded", "disabled"},
    "active": {"degraded", "disabled"},
    "degraded": {"canary_active", "active", "disabled"},
    "disabled": {"backlog"},
}


@dataclass
class LifecycleTransitionResult:
    bookmaker_code: str
    from_state: str
    to_state: str
    is_active: bool
    transitioned_at: datetime
    transition_id: int


class LifecycleTransitionError(ValueError):
    """Raised when a lifecycle transition request violates policy."""

    def __init__(
        self,
        *,
        reason_code: str,
        message: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
    ):
        super().__init__(message)
        self.reason_code = reason_code
        self.from_state = from_state
        self.to_state = to_state


def _normalize_state(value: str) -> str:
    return (value or "").strip().lower()


class BookmakerLifecycleService:
    """Transition guard and audit persistence for bookmaker lifecycle changes."""

    @staticmethod
    def _resolve_effective_state(bookmaker: Bookmaker) -> str:
        state = _normalize_state(getattr(bookmaker, "lifecycle_state", "") or "")
        if state in LIFECYCLE_STATES:
            return state
        return "active" if bool(bookmaker.is_active) else "backlog"

    @staticmethod
    def _desired_is_active(state: str) -> bool:
        return state in LIVE_RUNTIME_STATES

    @staticmethod
    def _validate_transition(from_state: str, to_state: str) -> None:
        if to_state not in LIFECYCLE_STATES:
            raise LifecycleTransitionError(
                reason_code="invalid_target_state",
                message=f"Unknown lifecycle state '{to_state}'",
                from_state=from_state,
                to_state=to_state,
            )

        if from_state == to_state:
            raise LifecycleTransitionError(
                reason_code="no_op_transition",
                message=f"Transition is a no-op for state '{to_state}'",
                from_state=from_state,
                to_state=to_state,
            )

        allowed_targets = ALLOWED_TRANSITIONS.get(from_state, set())
        if to_state not in allowed_targets:
            raise LifecycleTransitionError(
                reason_code="invalid_transition",
                message=(
                    f"Invalid lifecycle transition from '{from_state}' to '{to_state}'. "
                    f"Allowed targets: {sorted(allowed_targets)}"
                ),
                from_state=from_state,
                to_state=to_state,
            )

    @classmethod
    def transition_bookmaker_state(
        cls,
        db: Session,
        *,
        bookmaker_code: str,
        to_state: str,
        reason: str,
        transitioned_by: Optional[str],
        transitioned_by_email: Optional[str] = None,
        transition_source: str = "api",
        transition_metadata: Optional[Dict[str, Any]] = None,
    ) -> LifecycleTransitionResult:
        normalized_code = (bookmaker_code or "").strip().lower()
        normalized_to_state = _normalize_state(to_state)
        normalized_reason = (reason or "").strip()

        if not normalized_code:
            raise LifecycleTransitionError(
                reason_code="invalid_bookmaker_code",
                message="bookmaker_code is required",
                to_state=normalized_to_state,
            )
        if not normalized_reason:
            raise LifecycleTransitionError(
                reason_code="missing_reason",
                message="Transition reason is required",
                to_state=normalized_to_state,
            )

        bookmaker = (
            db.query(Bookmaker)
            .filter(Bookmaker.code == normalized_code)
            .first()
        )
        if not bookmaker:
            raise LifecycleTransitionError(
                reason_code="bookmaker_not_found",
                message=f"Bookmaker '{normalized_code}' was not found",
                to_state=normalized_to_state,
            )

        from_state = cls._resolve_effective_state(bookmaker)
        cls._validate_transition(from_state, normalized_to_state)

        if is_bookmaker_frozen(bookmaker.code) and normalized_to_state in LIVE_RUNTIME_STATES:
            raise LifecycleTransitionError(
                reason_code="freeze_guard_blocked",
                message=(
                    f"Bookmaker '{bookmaker.code}' is frozen and cannot transition to "
                    f"live runtime state '{normalized_to_state}'"
                ),
                from_state=from_state,
                to_state=normalized_to_state,
            )

        now = datetime.now(timezone.utc)
        desired_is_active = cls._desired_is_active(normalized_to_state)

        bookmaker.lifecycle_state = normalized_to_state
        bookmaker.lifecycle_state_updated_at = now
        bookmaker.lifecycle_last_transition_at = now
        bookmaker.lifecycle_last_transition_by = transitioned_by
        bookmaker.lifecycle_last_transition_reason = normalized_reason
        bookmaker.is_active = desired_is_active

        transition = BookmakerLifecycleTransition(
            bookmaker_id=bookmaker.id,
            from_state=from_state,
            to_state=normalized_to_state,
            transition_reason=normalized_reason,
            transition_metadata=transition_metadata or {},
            transitioned_by=transitioned_by,
            transitioned_by_email=transitioned_by_email,
            transition_source=(transition_source or "api").strip().lower(),
            created_at=now,
        )
        db.add(transition)
        db.add(bookmaker)
        db.commit()
        db.refresh(bookmaker)
        db.refresh(transition)

        return LifecycleTransitionResult(
            bookmaker_code=bookmaker.code,
            from_state=from_state,
            to_state=normalized_to_state,
            is_active=bool(bookmaker.is_active),
            transitioned_at=transition.created_at,
            transition_id=int(transition.id),
        )
