"""Canonical activation evidence registry service."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.models import Bookmaker, BookmakerActivationEvidence


DEFAULT_EVIDENCE_REPO_ROOT = "."
ALLOWED_EVIDENCE_TYPES = {"validation", "canary"}


def _parse_iso8601(value: str) -> Optional[datetime]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
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


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass
class ActivationEvidenceRecordResult:
    evidence_id: int
    evidence_type: str
    bookmaker_code: str
    artifact_path: str
    artifact_sha256: str
    generated_at: Optional[datetime]
    ended_at: Optional[datetime]
    validation_in_scope_fail_count: Optional[int]
    canary_gate_pass: Optional[bool]


class ActivationEvidenceRegistrationError(ValueError):
    """Raised when evidence artifact registration fails policy checks."""

    def __init__(self, *, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


class ActivationEvidenceRegistryService:
    """Persists canonical activation evidence records from artifact files."""

    @staticmethod
    def _repo_root() -> Path:
        configured = (os.getenv("BOOKMAKER_EVIDENCE_REPO_ROOT") or DEFAULT_EVIDENCE_REPO_ROOT).strip()
        return Path(configured).resolve()

    @classmethod
    def _resolve_artifact_path(cls, raw_path: str) -> Path:
        candidate = Path((raw_path or "").strip())
        if not candidate:
            raise ActivationEvidenceRegistrationError(
                reason_code="artifact_path_missing",
                message="artifact_path is required",
            )
        if candidate.is_absolute():
            resolved = candidate
        else:
            resolved = cls._repo_root() / candidate
        resolved = resolved.resolve()
        if not resolved.exists() or not resolved.is_file():
            raise ActivationEvidenceRegistrationError(
                reason_code="artifact_path_not_found",
                message=f"Artifact file not found: {resolved}",
            )
        return resolved

    @classmethod
    def _canonical_artifact_reference(cls, resolved_path: Path) -> str:
        try:
            relative = resolved_path.relative_to(cls._repo_root())
            return relative.as_posix()
        except ValueError:
            return str(resolved_path)

    @staticmethod
    def _read_artifact_json(path: Path) -> tuple[dict[str, Any], str]:
        raw_bytes = path.read_bytes()
        sha256 = hashlib.sha256(raw_bytes).hexdigest()
        try:
            payload = json.loads(raw_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ActivationEvidenceRegistrationError(
                reason_code="artifact_json_invalid",
                message=f"Artifact JSON parse failed for '{path}': {exc}",
            ) from exc
        if not isinstance(payload, dict):
            raise ActivationEvidenceRegistrationError(
                reason_code="artifact_json_invalid_shape",
                message=f"Artifact JSON root must be an object: '{path}'",
            )
        return payload, sha256

    @staticmethod
    def _extract_validation_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
        generated_raw = _first_nested_value(
            payload,
            ("generated_at", "completed_at", "ended_at", "timestamp"),
        )
        generated_at = _parse_iso8601(generated_raw) if isinstance(generated_raw, str) else None
        if generated_at is None:
            raise ActivationEvidenceRegistrationError(
                reason_code="validation_timestamp_missing_or_invalid",
                message="Validation artifact must include a valid generated timestamp",
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
        fail_count_value = _as_int(in_scope_fail_count)
        if fail_count_value is None:
            raise ActivationEvidenceRegistrationError(
                reason_code="validation_in_scope_fail_count_missing_or_invalid",
                message="Validation artifact must include integer in_scope_fail_count",
            )

        return {
            "generated_at": generated_at,
            "ended_at": None,
            "validation_in_scope_fail_count": fail_count_value,
            "canary_gate_pass": None,
            "canary_gate_thresholds": None,
            "canary_gate_failed_criteria": None,
        }

    @staticmethod
    def _extract_canary_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
        ended_raw = _first_nested_value(
            payload,
            ("ended_at", "generated_at", "completed_at", "timestamp"),
        )
        ended_at = _parse_iso8601(ended_raw) if isinstance(ended_raw, str) else None
        if ended_at is None:
            raise ActivationEvidenceRegistrationError(
                reason_code="canary_timestamp_missing_or_invalid",
                message="Canary artifact must include a valid ended timestamp",
            )

        gate = payload.get("gate")
        if not isinstance(gate, dict):
            raise ActivationEvidenceRegistrationError(
                reason_code="canary_gate_missing",
                message="Canary artifact must include gate object",
            )
        gate_pass = gate.get("pass")
        if not isinstance(gate_pass, bool):
            raise ActivationEvidenceRegistrationError(
                reason_code="canary_gate_pass_invalid",
                message="Canary artifact must include boolean gate.pass",
            )
        thresholds = gate.get("thresholds")
        if not isinstance(thresholds, dict):
            raise ActivationEvidenceRegistrationError(
                reason_code="canary_gate_thresholds_missing",
                message="Canary artifact must include gate.thresholds object",
            )

        failed_criteria: list[dict[str, Any]] = []
        for criterion in (gate.get("criteria") or []):
            if isinstance(criterion, dict) and not bool(criterion.get("pass", False)):
                failed_criteria.append(
                    {
                        "name": criterion.get("name"),
                        "expected": criterion.get("threshold"),
                        "observed": criterion.get("observed"),
                        "pass": False,
                    }
                )

        return {
            "generated_at": None,
            "ended_at": ended_at,
            "validation_in_scope_fail_count": None,
            "canary_gate_pass": gate_pass,
            "canary_gate_thresholds": thresholds,
            "canary_gate_failed_criteria": failed_criteria,
        }

    @classmethod
    def register_from_artifact_path(
        cls,
        db: Session,
        *,
        evidence_type: str,
        bookmaker_code: str,
        artifact_path: str,
        created_by: Optional[str],
        created_by_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ActivationEvidenceRecordResult:
        normalized_type = (evidence_type or "").strip().lower()
        if normalized_type not in ALLOWED_EVIDENCE_TYPES:
            raise ActivationEvidenceRegistrationError(
                reason_code="invalid_evidence_type",
                message=f"Unsupported evidence_type '{evidence_type}'",
            )

        normalized_code = (bookmaker_code or "").strip().lower()
        bookmaker = db.query(Bookmaker).filter(Bookmaker.code == normalized_code).first()
        if not bookmaker:
            raise ActivationEvidenceRegistrationError(
                reason_code="bookmaker_not_found",
                message=f"Bookmaker '{normalized_code}' not found",
            )

        resolved_path = cls._resolve_artifact_path(artifact_path)
        payload, artifact_sha256 = cls._read_artifact_json(resolved_path)
        if normalized_type == "validation":
            extracted = cls._extract_validation_fields(payload)
        else:
            extracted = cls._extract_canary_fields(payload)

        artifact_reference = cls._canonical_artifact_reference(resolved_path)
        merged_metadata = {
            "source": "artifact_path",
            "resolved_artifact_path": str(resolved_path),
            "artifact_size_bytes": resolved_path.stat().st_size,
            "evidence_type": normalized_type,
            **(metadata or {}),
        }

        record = BookmakerActivationEvidence(
            evidence_type=normalized_type,
            bookmaker_id=bookmaker.id,
            bookmaker_code=bookmaker.code,
            generated_at=extracted["generated_at"],
            ended_at=extracted["ended_at"],
            validation_in_scope_fail_count=extracted["validation_in_scope_fail_count"],
            canary_gate_pass=extracted["canary_gate_pass"],
            canary_gate_thresholds=extracted["canary_gate_thresholds"],
            canary_gate_failed_criteria=extracted["canary_gate_failed_criteria"],
            artifact_path=artifact_reference,
            artifact_sha256=artifact_sha256,
            artifact_metadata=merged_metadata,
            created_by=created_by,
            created_by_email=created_by_email,
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(BookmakerActivationEvidence)
                .filter(
                    BookmakerActivationEvidence.bookmaker_code == bookmaker.code,
                    BookmakerActivationEvidence.evidence_type == normalized_type,
                    BookmakerActivationEvidence.artifact_sha256 == artifact_sha256,
                )
                .first()
            )
            if existing:
                return ActivationEvidenceRecordResult(
                    evidence_id=int(existing.id),
                    evidence_type=existing.evidence_type,
                    bookmaker_code=existing.bookmaker_code,
                    artifact_path=existing.artifact_path,
                    artifact_sha256=existing.artifact_sha256,
                    generated_at=existing.generated_at,
                    ended_at=existing.ended_at,
                    validation_in_scope_fail_count=existing.validation_in_scope_fail_count,
                    canary_gate_pass=existing.canary_gate_pass,
                )
            raise
        db.refresh(record)

        return ActivationEvidenceRecordResult(
            evidence_id=int(record.id),
            evidence_type=record.evidence_type,
            bookmaker_code=record.bookmaker_code,
            artifact_path=record.artifact_path,
            artifact_sha256=record.artifact_sha256,
            generated_at=record.generated_at,
            ended_at=record.ended_at,
            validation_in_scope_fail_count=record.validation_in_scope_fail_count,
            canary_gate_pass=record.canary_gate_pass,
        )
