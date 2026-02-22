"""Lifecycle state transition guard service for bookmaker promotion control."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

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

DEFAULT_VALIDATION_EVIDENCE_MAX_AGE_SECONDS = 6 * 60 * 60
DEFAULT_CANARY_EVIDENCE_MAX_AGE_SECONDS = 6 * 60 * 60
DEFAULT_REPO_ROOT = "/workspace"
REQUIRED_CANARY_GATE_THRESHOLDS = {
    "min_cycles": 10,
    "min_duration_seconds": 1800,
    "requires_in_scope_fail_zero": True,
    "min_scrape_success_rate": 0.75,
    "max_open_breaker_cycle_count": 0,
    "max_scrape_p95_seconds": 360.0,
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


def _parse_iso8601(timestamp_str: str) -> Optional[datetime]:
    value = (timestamp_str or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _first_nested_value(data: Dict[str, Any], paths: Tuple[str, ...]) -> Any:
    for path in paths:
        cursor: Any = data
        found = True
        for key in path.split("."):
            if isinstance(cursor, dict) and key in cursor:
                cursor = cursor[key]
            else:
                found = False
                break
        if found:
            return cursor
    return None


def _as_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
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
    def _repo_root() -> Path:
        configured = (os.getenv("BOOKMAKER_EVIDENCE_REPO_ROOT") or DEFAULT_REPO_ROOT).strip()
        return Path(configured)

    @classmethod
    def _load_evidence_payload(
        cls,
        metadata: Dict[str, Any],
        *,
        inline_key: str,
        path_key: str,
        missing_reason_code: str,
        missing_message: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        inline_payload = metadata.get(inline_key)
        if isinstance(inline_payload, dict):
            return inline_payload, {"source": "inline"}

        evidence_path = metadata.get(path_key)
        if not isinstance(evidence_path, str) or not evidence_path.strip():
            raise LifecycleTransitionError(
                reason_code=missing_reason_code,
                message=missing_message,
                failed_criteria=[
                    {
                        "name": inline_key,
                        "expected": f"{inline_key} object or {path_key} path",
                        "observed": None,
                        "pass": False,
                    }
                ],
            )

        raw_path = evidence_path.strip()
        candidate_paths = [Path(raw_path)]
        if not Path(raw_path).is_absolute():
            candidate_paths.append(cls._repo_root() / raw_path)
        for candidate in candidate_paths:
            if candidate.exists():
                try:
                    parsed = json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise LifecycleTransitionError(
                        reason_code=f"{missing_reason_code}_unreadable",
                        message=f"Failed to parse evidence file '{candidate}': {exc}",
                        failed_criteria=[
                            {
                                "name": path_key,
                                "expected": "readable JSON file",
                                "observed": str(candidate),
                                "pass": False,
                            }
                        ],
                    ) from exc
                if not isinstance(parsed, dict):
                    raise LifecycleTransitionError(
                        reason_code=f"{missing_reason_code}_invalid_shape",
                        message=f"Evidence file '{candidate}' must contain a JSON object",
                        failed_criteria=[
                            {
                                "name": path_key,
                                "expected": "JSON object",
                                "observed": type(parsed).__name__,
                                "pass": False,
                            }
                        ],
                    )
                return parsed, {"source": "path", "path": str(candidate)}

        raise LifecycleTransitionError(
            reason_code=missing_reason_code,
            message=f"Evidence file not found for key '{path_key}'",
            failed_criteria=[
                {
                    "name": path_key,
                    "expected": "existing file path",
                    "observed": raw_path,
                    "pass": False,
                }
            ],
        )

    @staticmethod
    def _evaluate_recency(
        payload: Dict[str, Any],
        *,
        timestamp_fields: Tuple[str, ...],
        max_age_seconds: int,
        reason_code_prefix: str,
        evidence_label: str,
    ) -> Tuple[datetime, Dict[str, Any]]:
        observed_value = None
        for field in timestamp_fields:
            value = _first_nested_value(payload, (field,))
            if isinstance(value, str) and value.strip():
                observed_value = value
                break
        if observed_value is None:
            raise LifecycleTransitionError(
                reason_code=f"{reason_code_prefix}_timestamp_missing",
                message=f"{evidence_label} evidence timestamp is missing",
                failed_criteria=[
                    {
                        "name": f"{evidence_label}_timestamp",
                        "expected": f"one of {list(timestamp_fields)}",
                        "observed": None,
                        "pass": False,
                    }
                ],
            )

        timestamp = _parse_iso8601(observed_value)
        if timestamp is None:
            raise LifecycleTransitionError(
                reason_code=f"{reason_code_prefix}_timestamp_invalid",
                message=f"{evidence_label} evidence timestamp is invalid: '{observed_value}'",
                failed_criteria=[
                    {
                        "name": f"{evidence_label}_timestamp",
                        "expected": "ISO-8601 timestamp",
                        "observed": observed_value,
                        "pass": False,
                    }
                ],
            )

        now = datetime.now(timezone.utc)
        age_seconds = (now - timestamp).total_seconds()
        criterion = {
            "name": f"{evidence_label}_recency_seconds",
            "expected": f"<= {max_age_seconds}",
            "observed": age_seconds,
            "pass": age_seconds <= max_age_seconds,
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
        return timestamp, criterion

    @classmethod
    def _evaluate_validation_evidence(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        payload, source = cls._load_evidence_payload(
            metadata,
            inline_key="validation_evidence",
            path_key="validation_evidence_path",
            missing_reason_code="validation_evidence_missing",
            missing_message="Validation evidence is required for transition to canary_active",
        )

        max_age_seconds = _as_int(
            os.getenv(
                "BOOKMAKER_VALIDATION_EVIDENCE_MAX_AGE_SECONDS",
                str(DEFAULT_VALIDATION_EVIDENCE_MAX_AGE_SECONDS),
            )
        ) or DEFAULT_VALIDATION_EVIDENCE_MAX_AGE_SECONDS
        evidence_ts, recency_criterion = cls._evaluate_recency(
            payload,
            timestamp_fields=(
                "generated_at",
                "completed_at",
                "ended_at",
                "timestamp",
            ),
            max_age_seconds=max_age_seconds,
            reason_code_prefix="validation_evidence",
            evidence_label="validation",
        )

        in_scope_fail_count = _first_nested_value(
            payload,
            (
                "in_scope_fail_count",
                "in_scope_fail_cycle_count",
                "validation_gate_metrics.in_scope_fail_cycle_count",
                "summary.in_scope_fail_count",
            ),
        )
        if in_scope_fail_count is None:
            raise LifecycleTransitionError(
                reason_code="validation_in_scope_fail_count_missing",
                message="Validation evidence must include in_scope_fail_count",
                failed_criteria=[
                    {
                        "name": "in_scope_fail_count",
                        "expected": "integer value",
                        "observed": None,
                        "pass": False,
                    }
                ],
            )

        fail_count_value = _as_int(in_scope_fail_count)
        if fail_count_value is None:
            raise LifecycleTransitionError(
                reason_code="validation_in_scope_fail_count_invalid",
                message="Validation in_scope_fail_count must be an integer",
                failed_criteria=[
                    {
                        "name": "in_scope_fail_count",
                        "expected": "integer value",
                        "observed": in_scope_fail_count,
                        "pass": False,
                    }
                ],
            )

        fail_criterion = {
            "name": "in_scope_fail_count",
            "expected": 0,
            "observed": fail_count_value,
            "pass": fail_count_value == 0,
        }
        if not fail_criterion["pass"]:
            raise LifecycleTransitionError(
                reason_code="validation_in_scope_fail_detected",
                message=f"Validation evidence has in_scope_fail_count={fail_count_value}",
                failed_criteria=[fail_criterion],
            )

        return {
            "evidence_type": "validation",
            "source": source,
            "max_age_seconds": max_age_seconds,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evidence_timestamp": evidence_ts.isoformat(),
            "criteria": [recency_criterion, fail_criterion],
        }

    @classmethod
    def _evaluate_canary_evidence(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        payload, source = cls._load_evidence_payload(
            metadata,
            inline_key="canary_evidence",
            path_key="canary_evidence_path",
            missing_reason_code="canary_evidence_missing",
            missing_message="Canary evidence is required for transition to active",
        )

        max_age_seconds = _as_int(
            os.getenv(
                "BOOKMAKER_CANARY_EVIDENCE_MAX_AGE_SECONDS",
                str(DEFAULT_CANARY_EVIDENCE_MAX_AGE_SECONDS),
            )
        ) or DEFAULT_CANARY_EVIDENCE_MAX_AGE_SECONDS
        evidence_ts, recency_criterion = cls._evaluate_recency(
            payload,
            timestamp_fields=("ended_at", "generated_at", "completed_at", "timestamp"),
            max_age_seconds=max_age_seconds,
            reason_code_prefix="canary_evidence",
            evidence_label="canary",
        )

        gate = payload.get("gate")
        if not isinstance(gate, dict):
            raise LifecycleTransitionError(
                reason_code="canary_gate_missing",
                message="Canary evidence must include gate result payload",
                failed_criteria=[
                    {
                        "name": "gate",
                        "expected": "object with pass/criteria/thresholds",
                        "observed": type(gate).__name__,
                        "pass": False,
                    }
                ],
            )

        gate_pass = gate.get("pass")
        if not isinstance(gate_pass, bool):
            raise LifecycleTransitionError(
                reason_code="canary_gate_result_missing",
                message="Canary gate result must include boolean gate.pass",
                failed_criteria=[
                    {
                        "name": "gate.pass",
                        "expected": "boolean",
                        "observed": gate_pass,
                        "pass": False,
                    }
                ],
            )

        thresholds = gate.get("thresholds")
        if not isinstance(thresholds, dict):
            raise LifecycleTransitionError(
                reason_code="canary_thresholds_missing",
                message="Canary evidence must include gate.thresholds",
                failed_criteria=[
                    {
                        "name": "gate.thresholds",
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
                }
            )
        failed_threshold_criteria = [c for c in threshold_criteria if not c["pass"]]
        if failed_threshold_criteria:
            raise LifecycleTransitionError(
                reason_code="canary_threshold_contract_mismatch",
                message="Canary evidence thresholds do not match required gate contract",
                failed_criteria=failed_threshold_criteria,
            )

        criteria = [recency_criterion] + threshold_criteria
        if not gate_pass:
            failed_gate_criteria = []
            for criterion in (gate.get("criteria") or []):
                if isinstance(criterion, dict) and not bool(criterion.get("pass", False)):
                    failed_gate_criteria.append(
                        {
                            "name": criterion.get("name"),
                            "expected": criterion.get("threshold"),
                            "observed": criterion.get("observed"),
                            "pass": False,
                        }
                    )
            if not failed_gate_criteria:
                failed_gate_criteria = [
                    {
                        "name": "gate.pass",
                        "expected": True,
                        "observed": False,
                        "pass": False,
                    }
                ]
            raise LifecycleTransitionError(
                reason_code="canary_gate_failed",
                message="Canary gate did not pass for transition to active",
                failed_criteria=failed_gate_criteria,
            )

        return {
            "evidence_type": "canary",
            "source": source,
            "max_age_seconds": max_age_seconds,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "evidence_timestamp": evidence_ts.isoformat(),
            "gate_pass": gate_pass,
            "criteria": criteria,
        }

    @classmethod
    def _evaluate_activation_gate_checks(
        cls,
        *,
        from_state: str,
        to_state: str,
        transition_metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        metadata = transition_metadata or {}
        checks: list[dict[str, Any]] = []
        if from_state == "validation_passed" and to_state == "canary_active":
            checks.append(cls._evaluate_validation_evidence(metadata))
        if from_state == "canary_active" and to_state == "active":
            checks.append(cls._evaluate_canary_evidence(metadata))
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
