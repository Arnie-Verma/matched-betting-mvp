"""Lifecycle state transition guard service for bookmaker promotion control."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import Session

from api.core.bookmaker_freeze import is_bookmaker_frozen
from api.models import Bookmaker, BookmakerActivationEvidence, BookmakerLifecycleTransition
from api.services.lifecycle_gate_contract import (
    DEFAULT_CANARY_EVIDENCE_MAX_AGE_SECONDS,
    DEFAULT_VALIDATION_EVIDENCE_MAX_AGE_SECONDS,
    REQUIRED_CANARY_GATE_THRESHOLDS,
)


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
        failed_criteria: Optional[list[dict[str, Any]]] = None,
    ):
        super().__init__(message)
        self.reason_code = reason_code
        self.from_state = from_state
        self.to_state = to_state
        self.failed_criteria = failed_criteria or []


def _normalize_state(value: str) -> str:
    return (value or "").strip().lower()


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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

    @staticmethod
    def _evaluate_record_recency(
        *,
        record: BookmakerActivationEvidence,
        timestamp_value: Optional[datetime],
        max_age_seconds: int,
        reason_code_prefix: str,
        evidence_label: str,
    ) -> Dict[str, Any]:
        if timestamp_value is None:
            raise LifecycleTransitionError(
                reason_code=f"{reason_code_prefix}_timestamp_missing",
                message=f"{evidence_label} evidence timestamp is missing",
                failed_criteria=[
                    {
                        "name": f"{evidence_label}_timestamp",
                        "expected": "non-null timestamp",
                        "observed": None,
                        "pass": False,
                    }
                ],
            )

        ts = timestamp_value
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
        criterion = {
            "name": f"{evidence_label}_recency_seconds",
            "expected": f"<= {max_age_seconds}",
            "observed": age_seconds,
            "pass": age_seconds <= max_age_seconds,
            "evidence_id": int(record.id),
        }
        if not criterion["pass"]:
            raise LifecycleTransitionError(
                reason_code=f"{reason_code_prefix}_stale",
                message=(
                    f"{evidence_label} evidence is stale: age_seconds={age_seconds:.2f}, "
                    f"max_age_seconds={max_age_seconds}"
                ),
                failed_criteria=[criterion],
            )
        return criterion

    @staticmethod
    def _load_canonical_evidence_record(
        db: Session,
        *,
        metadata: Dict[str, Any],
        id_key: str,
        expected_type: str,
        bookmaker_code: str,
        missing_reason_code: str,
    ) -> BookmakerActivationEvidence:
        raw_id = metadata.get(id_key)
        if raw_id is None:
            raise LifecycleTransitionError(
                reason_code=missing_reason_code,
                message=f"Canonical evidence id '{id_key}' is required",
                failed_criteria=[
                    {
                        "name": id_key,
                        "expected": "integer evidence record id",
                        "observed": None,
                        "pass": False,
                    }
                ],
            )

        evidence_id = _as_int(raw_id)
        if evidence_id is None:
            raise LifecycleTransitionError(
                reason_code=f"{expected_type}_evidence_record_id_invalid",
                message=f"Evidence id '{id_key}' must be an integer",
                failed_criteria=[
                    {
                        "name": id_key,
                        "expected": "integer",
                        "observed": raw_id,
                        "pass": False,
                    }
                ],
            )

        record = (
            db.query(BookmakerActivationEvidence)
            .filter(BookmakerActivationEvidence.id == int(evidence_id))
            .first()
        )
        if not record:
            raise LifecycleTransitionError(
                reason_code=f"{expected_type}_evidence_record_not_found",
                message=f"Evidence record id '{evidence_id}' not found",
                failed_criteria=[
                    {
                        "name": id_key,
                        "expected": "existing evidence record",
                        "observed": evidence_id,
                        "pass": False,
                    }
                ],
            )

        if (record.evidence_type or "").strip().lower() != expected_type:
            raise LifecycleTransitionError(
                reason_code=f"{expected_type}_evidence_record_type_mismatch",
                message=(
                    f"Evidence id '{evidence_id}' type mismatch: expected '{expected_type}', "
                    f"observed '{record.evidence_type}'"
                ),
                failed_criteria=[
                    {
                        "name": "evidence_type",
                        "expected": expected_type,
                        "observed": record.evidence_type,
                        "pass": False,
                    }
                ],
            )

        if (record.bookmaker_code or "").strip().lower() != (bookmaker_code or "").strip().lower():
            raise LifecycleTransitionError(
                reason_code=f"{expected_type}_evidence_bookmaker_mismatch",
                message=(
                    f"Evidence id '{evidence_id}' belongs to bookmaker '{record.bookmaker_code}', "
                    f"not '{bookmaker_code}'"
                ),
                failed_criteria=[
                    {
                        "name": "evidence.bookmaker_code",
                        "expected": bookmaker_code,
                        "observed": record.bookmaker_code,
                        "pass": False,
                    }
                ],
            )
        return record

    @classmethod
    def _evaluate_validation_evidence(
        cls,
        db: Session,
        *,
        bookmaker_code: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = cls._load_canonical_evidence_record(
            db,
            metadata=metadata,
            id_key="validation_evidence_id",
            expected_type="validation",
            bookmaker_code=bookmaker_code,
            missing_reason_code="validation_evidence_record_missing",
        )

        max_age_seconds = _as_int(
            os.getenv(
                "BOOKMAKER_VALIDATION_EVIDENCE_MAX_AGE_SECONDS",
                str(DEFAULT_VALIDATION_EVIDENCE_MAX_AGE_SECONDS),
            )
        ) or DEFAULT_VALIDATION_EVIDENCE_MAX_AGE_SECONDS
        recency_criterion = cls._evaluate_record_recency(
            record=record,
            timestamp_value=record.generated_at or record.ended_at,
            max_age_seconds=max_age_seconds,
            reason_code_prefix="validation_evidence",
            evidence_label="validation",
        )

        fail_count = record.validation_in_scope_fail_count
        if fail_count is None:
            raise LifecycleTransitionError(
                reason_code="validation_in_scope_fail_count_missing",
                message="Validation evidence record missing in_scope_fail_count",
                failed_criteria=[
                    {
                        "name": "validation_in_scope_fail_count",
                        "expected": "integer",
                        "observed": None,
                        "pass": False,
                    }
                ],
            )
        fail_criterion = {
            "name": "in_scope_fail_count",
            "expected": 0,
            "observed": int(fail_count),
            "pass": int(fail_count) == 0,
            "evidence_id": int(record.id),
        }
        if not fail_criterion["pass"]:
            raise LifecycleTransitionError(
                reason_code="validation_in_scope_fail_detected",
                message=f"Validation evidence has in_scope_fail_count={fail_count}",
                failed_criteria=[fail_criterion],
            )

        return {
            "evidence_type": "validation",
            "evidence_id": int(record.id),
            "artifact_path": record.artifact_path,
            "artifact_sha256": record.artifact_sha256,
            "criteria": [recency_criterion, fail_criterion],
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def _evaluate_canary_evidence(
        cls,
        db: Session,
        *,
        bookmaker_code: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        record = cls._load_canonical_evidence_record(
            db,
            metadata=metadata,
            id_key="canary_evidence_id",
            expected_type="canary",
            bookmaker_code=bookmaker_code,
            missing_reason_code="canary_evidence_record_missing",
        )

        max_age_seconds = _as_int(
            os.getenv(
                "BOOKMAKER_CANARY_EVIDENCE_MAX_AGE_SECONDS",
                str(DEFAULT_CANARY_EVIDENCE_MAX_AGE_SECONDS),
            )
        ) or DEFAULT_CANARY_EVIDENCE_MAX_AGE_SECONDS
        recency_criterion = cls._evaluate_record_recency(
            record=record,
            timestamp_value=record.ended_at or record.generated_at,
            max_age_seconds=max_age_seconds,
            reason_code_prefix="canary_evidence",
            evidence_label="canary",
        )

        thresholds = record.canary_gate_thresholds
        if not isinstance(thresholds, dict):
            raise LifecycleTransitionError(
                reason_code="canary_thresholds_missing",
                message="Canary evidence record missing threshold contract payload",
                failed_criteria=[
                    {
                        "name": "canary_gate_thresholds",
                        "expected": "object",
                        "observed": type(thresholds).__name__,
                        "pass": False,
                    }
                ],
            )

        threshold_criteria = []
        for key, expected in REQUIRED_CANARY_GATE_THRESHOLDS.items():
            observed = thresholds.get(key)
            passed = observed == expected
            if isinstance(expected, float):
                observed_float = _as_float(observed)
                passed = observed_float is not None and abs(observed_float - expected) < 1e-9
            threshold_criteria.append(
                {
                    "name": f"gate.thresholds.{key}",
                    "expected": expected,
                    "observed": observed,
                    "pass": passed,
                    "evidence_id": int(record.id),
                }
            )
        failed_threshold_criteria = [c for c in threshold_criteria if not c["pass"]]
        if failed_threshold_criteria:
            raise LifecycleTransitionError(
                reason_code="canary_threshold_contract_mismatch",
                message="Canary evidence thresholds do not match required gate contract",
                failed_criteria=failed_threshold_criteria,
            )

        if record.canary_gate_pass is not True:
            failed_gate_criteria = list(record.canary_gate_failed_criteria or [])
            if not failed_gate_criteria:
                failed_gate_criteria = [
                    {
                        "name": "gate.pass",
                        "expected": True,
                        "observed": record.canary_gate_pass,
                        "pass": False,
                        "evidence_id": int(record.id),
                    }
                ]
            raise LifecycleTransitionError(
                reason_code="canary_gate_failed",
                message="Canary gate did not pass for transition to active",
                failed_criteria=failed_gate_criteria,
            )

        return {
            "evidence_type": "canary",
            "evidence_id": int(record.id),
            "artifact_path": record.artifact_path,
            "artifact_sha256": record.artifact_sha256,
            "criteria": [recency_criterion] + threshold_criteria,
            "gate_pass": True,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def _evaluate_activation_gate_checks(
        cls,
        db: Session,
        *,
        bookmaker_code: str,
        from_state: str,
        to_state: str,
        transition_metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        metadata = transition_metadata or {}
        checks: list[dict[str, Any]] = []
        if from_state == "validation_passed" and to_state == "canary_active":
            checks.append(
                cls._evaluate_validation_evidence(
                    db,
                    bookmaker_code=bookmaker_code,
                    metadata=metadata,
                )
            )
        if from_state == "canary_active" and to_state == "active":
            checks.append(
                cls._evaluate_canary_evidence(
                    db,
                    bookmaker_code=bookmaker_code,
                    metadata=metadata,
                )
            )
        return {
            "from_state": from_state,
            "to_state": to_state,
            "checks": checks,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
        }

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

        gate_evaluation = cls._evaluate_activation_gate_checks(
            db,
            bookmaker_code=bookmaker.code,
            from_state=from_state,
            to_state=normalized_to_state,
            transition_metadata=transition_metadata,
        )

        now = datetime.now(timezone.utc)
        desired_is_active = cls._desired_is_active(normalized_to_state)
        persisted_transition_metadata = dict(transition_metadata or {})
        if gate_evaluation.get("checks"):
            persisted_transition_metadata["activation_gate_evaluation"] = gate_evaluation

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
            transition_metadata=persisted_transition_metadata,
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
