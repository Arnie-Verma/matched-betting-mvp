"""Rollout control plane policy service for worker runnable-set selection."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from sqlalchemy.orm import Session

from api.core.bookmaker_freeze import is_bookmaker_frozen
from api.models import Bookmaker, BookmakerRolloutPolicy, PlatformRolloutPolicy


ROLLOUT_MODE_FULL = "full"
ROLLOUT_MODE_CANARY = "canary"
ROLLOUT_MODE_DISABLED = "disabled"
ALLOWED_ROLLOUT_MODES = {ROLLOUT_MODE_FULL, ROLLOUT_MODE_CANARY, ROLLOUT_MODE_DISABLED}
DEFAULT_ELIGIBLE_LIFECYCLE_STATES = {"canary_active", "active", "degraded"}


class RolloutPolicyError(ValueError):
    """Raised when rollout policy requests are invalid."""

    def __init__(self, reason_code: str, message: str):
        super().__init__(message)
        self.reason_code = reason_code


@dataclass
class RolloutSelectionResult:
    runnable_configs: List[Dict[str, Any]]
    decisions: List[Dict[str, Any]]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_code(value: Any) -> str:
    return str(value or "").strip().lower()


def _normalize_rollout_mode(value: Any) -> str:
    mode = _normalize_code(value)
    if mode not in ALLOWED_ROLLOUT_MODES:
        raise RolloutPolicyError(
            reason_code="invalid_rollout_mode",
            message=(
                f"Invalid rollout_mode='{value}'. "
                f"Expected one of: {sorted(ALLOWED_ROLLOUT_MODES)}"
            ),
        )
    return mode


def _normalize_cohort(values: Optional[Sequence[Any]]) -> List[str]:
    if values is None:
        return []
    normalized = {_normalize_code(v) for v in values if _normalize_code(v)}
    return sorted(normalized)


def _cohort_to_storage(values: List[str]) -> Optional[List[str]]:
    return values or None


def _load_eligible_states() -> Set[str]:
    configured = os.getenv(
        "ROLLOUT_ELIGIBLE_LIFECYCLE_STATES",
        ",".join(sorted(DEFAULT_ELIGIBLE_LIFECYCLE_STATES)),
    )
    states = {_normalize_code(item) for item in configured.split(",") if _normalize_code(item)}
    return states or set(DEFAULT_ELIGIBLE_LIFECYCLE_STATES)


def _extract_platform_code(bookmaker: Bookmaker) -> str:
    config = bookmaker.scraping_config if isinstance(bookmaker.scraping_config, dict) else {}
    return _normalize_code(config.get("scraper_class")) or "unknown"


def _bookmaker_config(bookmaker: Bookmaker) -> Dict[str, Any]:
    config = dict(bookmaker.scraping_config or {})
    return {
        "code": bookmaker.code,
        "name": bookmaker.name,
        "base_url": bookmaker.base_url or bookmaker.website_url,
        "website_url": bookmaker.website_url,
        "scraping_config": config,
    }


class RolloutControlService:
    """Persistence and selection logic for rollout control policies."""

    @classmethod
    def _default_platform_policy(cls, platform_code: str) -> Dict[str, Any]:
        return {
            "scope": "platform",
            "platform_code": platform_code,
            "rollout_mode": ROLLOUT_MODE_FULL,
            "kill_switch_enabled": False,
            "sport_cohort": [],
            "competition_cohort": [],
            "bookmaker_cohort": [],
            "policy_metadata": {},
            "policy_source": "default",
            "updated_by": None,
            "updated_by_email": None,
            "updated_at": None,
        }

    @classmethod
    def _default_bookmaker_policy(cls, bookmaker_code: str) -> Dict[str, Any]:
        return {
            "scope": "bookmaker",
            "bookmaker_code": bookmaker_code,
            "rollout_mode": ROLLOUT_MODE_FULL,
            "kill_switch_enabled": False,
            "sport_cohort": [],
            "competition_cohort": [],
            "bookmaker_cohort": [],
            "policy_metadata": {},
            "policy_source": "default",
            "updated_by": None,
            "updated_by_email": None,
            "updated_at": None,
        }

    @classmethod
    def _serialize_platform_policy(cls, policy: PlatformRolloutPolicy) -> Dict[str, Any]:
        return {
            "scope": "platform",
            "platform_code": _normalize_code(policy.platform_code),
            "rollout_mode": _normalize_code(policy.rollout_mode) or ROLLOUT_MODE_FULL,
            "kill_switch_enabled": bool(policy.kill_switch_enabled),
            "sport_cohort": _normalize_cohort(policy.sport_cohort),
            "competition_cohort": _normalize_cohort(policy.competition_cohort),
            "bookmaker_cohort": _normalize_cohort(policy.bookmaker_cohort),
            "policy_metadata": dict(policy.policy_metadata or {}),
            "policy_source": "persisted",
            "updated_by": policy.updated_by,
            "updated_by_email": policy.updated_by_email,
            "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
        }

    @classmethod
    def _serialize_bookmaker_policy(cls, policy: BookmakerRolloutPolicy) -> Dict[str, Any]:
        return {
            "scope": "bookmaker",
            "bookmaker_code": _normalize_code(policy.bookmaker_code),
            "rollout_mode": _normalize_code(policy.rollout_mode) or ROLLOUT_MODE_FULL,
            "kill_switch_enabled": bool(policy.kill_switch_enabled),
            "sport_cohort": _normalize_cohort(policy.sport_cohort),
            "competition_cohort": _normalize_cohort(policy.competition_cohort),
            "bookmaker_cohort": _normalize_cohort(policy.bookmaker_cohort),
            "policy_metadata": dict(policy.policy_metadata or {}),
            "policy_source": "persisted",
            "updated_by": policy.updated_by,
            "updated_by_email": policy.updated_by_email,
            "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
        }

    @classmethod
    def get_platform_policy(cls, db: Session, platform_code: str) -> Dict[str, Any]:
        normalized_platform = _normalize_code(platform_code)
        policy = (
            db.query(PlatformRolloutPolicy)
            .filter(PlatformRolloutPolicy.platform_code == normalized_platform)
            .one_or_none()
        )
        if policy is None:
            return cls._default_platform_policy(normalized_platform)
        return cls._serialize_platform_policy(policy)

    @classmethod
    def get_bookmaker_policy(cls, db: Session, bookmaker_code: str) -> Dict[str, Any]:
        normalized_code = _normalize_code(bookmaker_code)
        policy = (
            db.query(BookmakerRolloutPolicy)
            .filter(BookmakerRolloutPolicy.bookmaker_code == normalized_code)
            .one_or_none()
        )
        if policy is None:
            return cls._default_bookmaker_policy(normalized_code)
        return cls._serialize_bookmaker_policy(policy)

    @classmethod
    def upsert_platform_policy(
        cls,
        db: Session,
        *,
        platform_code: str,
        rollout_mode: Optional[str] = None,
        kill_switch_enabled: Optional[bool] = None,
        sport_cohort: Optional[Sequence[str]] = None,
        competition_cohort: Optional[Sequence[str]] = None,
        bookmaker_cohort: Optional[Sequence[str]] = None,
        policy_metadata: Optional[Dict[str, Any]] = None,
        updated_by: Optional[str] = None,
        updated_by_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_platform = _normalize_code(platform_code)
        if not normalized_platform:
            raise RolloutPolicyError("platform_code_invalid", "platform_code is required")

        record = (
            db.query(PlatformRolloutPolicy)
            .filter(PlatformRolloutPolicy.platform_code == normalized_platform)
            .one_or_none()
        )
        if record is None:
            record = PlatformRolloutPolicy(
                platform_code=normalized_platform,
                rollout_mode=ROLLOUT_MODE_FULL,
                kill_switch_enabled=False,
            )
            db.add(record)

        if rollout_mode is not None:
            record.rollout_mode = _normalize_rollout_mode(rollout_mode)
        if kill_switch_enabled is not None:
            record.kill_switch_enabled = bool(kill_switch_enabled)
        if sport_cohort is not None:
            record.sport_cohort = _cohort_to_storage(_normalize_cohort(sport_cohort))
        if competition_cohort is not None:
            record.competition_cohort = _cohort_to_storage(_normalize_cohort(competition_cohort))
        if bookmaker_cohort is not None:
            record.bookmaker_cohort = _cohort_to_storage(_normalize_cohort(bookmaker_cohort))
        if policy_metadata is not None:
            record.policy_metadata = dict(policy_metadata)

        record.updated_by = updated_by
        record.updated_by_email = updated_by_email
        record.updated_at = _now_utc()

        db.commit()
        db.refresh(record)
        return cls._serialize_platform_policy(record)

    @classmethod
    def upsert_bookmaker_policy(
        cls,
        db: Session,
        *,
        bookmaker_code: str,
        rollout_mode: Optional[str] = None,
        kill_switch_enabled: Optional[bool] = None,
        sport_cohort: Optional[Sequence[str]] = None,
        competition_cohort: Optional[Sequence[str]] = None,
        bookmaker_cohort: Optional[Sequence[str]] = None,
        policy_metadata: Optional[Dict[str, Any]] = None,
        updated_by: Optional[str] = None,
        updated_by_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_code = _normalize_code(bookmaker_code)
        if not normalized_code:
            raise RolloutPolicyError("bookmaker_code_invalid", "bookmaker_code is required")

        bookmaker = db.query(Bookmaker).filter(Bookmaker.code == normalized_code).one_or_none()
        if bookmaker is None:
            raise RolloutPolicyError("bookmaker_not_found", f"Bookmaker '{normalized_code}' not found")

        record = (
            db.query(BookmakerRolloutPolicy)
            .filter(BookmakerRolloutPolicy.bookmaker_code == normalized_code)
            .one_or_none()
        )
        if record is None:
            record = BookmakerRolloutPolicy(
                bookmaker_id=bookmaker.id,
                bookmaker_code=normalized_code,
                rollout_mode=ROLLOUT_MODE_FULL,
                kill_switch_enabled=False,
            )
            db.add(record)

        if rollout_mode is not None:
            record.rollout_mode = _normalize_rollout_mode(rollout_mode)
        if kill_switch_enabled is not None:
            record.kill_switch_enabled = bool(kill_switch_enabled)
        if sport_cohort is not None:
            record.sport_cohort = _cohort_to_storage(_normalize_cohort(sport_cohort))
        if competition_cohort is not None:
            record.competition_cohort = _cohort_to_storage(_normalize_cohort(competition_cohort))
        if bookmaker_cohort is not None:
            record.bookmaker_cohort = _cohort_to_storage(_normalize_cohort(bookmaker_cohort))
        if policy_metadata is not None:
            record.policy_metadata = dict(policy_metadata)

        record.updated_by = updated_by
        record.updated_by_email = updated_by_email
        record.updated_at = _now_utc()

        db.commit()
        db.refresh(record)
        return cls._serialize_bookmaker_policy(record)

    @classmethod
    def _evaluate_policy_gate(
        cls,
        *,
        policy: Dict[str, Any],
        scope_prefix: str,
        bookmaker_code: str,
        requested_sport: Optional[str],
        requested_competition: Optional[str],
    ) -> List[str]:
        reasons: List[str] = []
        rollout_mode = _normalize_code(policy.get("rollout_mode")) or ROLLOUT_MODE_FULL
        kill_switch_enabled = bool(policy.get("kill_switch_enabled"))
        sport_cohort = _normalize_cohort(policy.get("sport_cohort"))
        competition_cohort = _normalize_cohort(policy.get("competition_cohort"))
        bookmaker_cohort = _normalize_cohort(policy.get("bookmaker_cohort"))

        if kill_switch_enabled:
            reasons.append(f"{scope_prefix}_kill_switch_enabled")
            return reasons

        if rollout_mode == ROLLOUT_MODE_DISABLED:
            reasons.append(f"{scope_prefix}_rollout_disabled")
            return reasons

        if rollout_mode != ROLLOUT_MODE_CANARY:
            return reasons

        if bookmaker_cohort and _normalize_code(bookmaker_code) not in set(bookmaker_cohort):
            reasons.append(f"{scope_prefix}_bookmaker_cohort_excluded")

        if sport_cohort:
            requested = _normalize_code(requested_sport)
            if not requested or requested == "all":
                reasons.append(f"{scope_prefix}_sport_cohort_requires_specific_sport")
            elif requested not in set(sport_cohort):
                reasons.append(f"{scope_prefix}_sport_cohort_excluded")

        if competition_cohort:
            requested_comp = _normalize_code(requested_competition)
            if not requested_comp:
                reasons.append(f"{scope_prefix}_competition_cohort_requires_specific_competition")
            elif requested_comp not in set(competition_cohort):
                reasons.append(f"{scope_prefix}_competition_cohort_excluded")

        return reasons

    @classmethod
    def resolve_runnable_bookmakers(
        cls,
        db: Session,
        *,
        bookmaker_rows: Sequence[Bookmaker],
        requested_sport: Optional[str] = None,
        requested_competition: Optional[str] = None,
        requested_bookmakers: Optional[Sequence[str]] = None,
    ) -> RolloutSelectionResult:
        normalized_requested = {_normalize_code(code) for code in (requested_bookmakers or []) if _normalize_code(code)}
        eligible_states = _load_eligible_states()

        bookmaker_codes = [_normalize_code(row.code) for row in bookmaker_rows if _normalize_code(row.code)]
        bookmaker_policy_rows = (
            db.query(BookmakerRolloutPolicy)
            .filter(BookmakerRolloutPolicy.bookmaker_code.in_(bookmaker_codes))
            .all()
            if bookmaker_codes
            else []
        )
        bookmaker_policies = {
            _normalize_code(row.bookmaker_code): cls._serialize_bookmaker_policy(row)
            for row in bookmaker_policy_rows
        }

        platform_codes = {_extract_platform_code(row) for row in bookmaker_rows}
        platform_policy_rows = (
            db.query(PlatformRolloutPolicy)
            .filter(PlatformRolloutPolicy.platform_code.in_(platform_codes))
            .all()
            if platform_codes
            else []
        )
        platform_policies = {
            _normalize_code(row.platform_code): cls._serialize_platform_policy(row)
            for row in platform_policy_rows
        }

        runnable_configs: List[Dict[str, Any]] = []
        decisions: List[Dict[str, Any]] = []

        for bookmaker in sorted(bookmaker_rows, key=lambda item: _normalize_code(item.code)):
            code = _normalize_code(bookmaker.code)
            platform_code = _extract_platform_code(bookmaker)
            lifecycle_state = _normalize_code(getattr(bookmaker, "lifecycle_state", "") or "")

            platform_policy = platform_policies.get(platform_code, cls._default_platform_policy(platform_code))
            bookmaker_policy = bookmaker_policies.get(code, cls._default_bookmaker_policy(code))
            reasons: List[str] = []

            if normalized_requested and code not in normalized_requested:
                reasons.append("bookmaker_not_in_requested_subset")

            if lifecycle_state not in eligible_states:
                reasons.append("lifecycle_state_not_eligible")

            if is_bookmaker_frozen(code):
                reasons.append("bookmaker_frozen")

            reasons.extend(
                cls._evaluate_policy_gate(
                    policy=platform_policy,
                    scope_prefix="platform",
                    bookmaker_code=code,
                    requested_sport=requested_sport,
                    requested_competition=requested_competition,
                )
            )
            reasons.extend(
                cls._evaluate_policy_gate(
                    policy=bookmaker_policy,
                    scope_prefix="bookmaker",
                    bookmaker_code=code,
                    requested_sport=requested_sport,
                    requested_competition=requested_competition,
                )
            )

            scraper_platform = _normalize_code((bookmaker.scraping_config or {}).get("scraper_class"))
            if not scraper_platform:
                reasons.append("scraper_platform_missing")

            runnable = len(reasons) == 0
            if runnable:
                runnable_configs.append(_bookmaker_config(bookmaker))

            decisions.append(
                {
                    "bookmaker_code": code,
                    "platform_code": platform_code,
                    "lifecycle_state": lifecycle_state,
                    "is_active": bool(getattr(bookmaker, "is_active", False)),
                    "runnable": runnable,
                    "reasons": reasons,
                    "platform_policy": platform_policy,
                    "bookmaker_policy": bookmaker_policy,
                }
            )

        return RolloutSelectionResult(
            runnable_configs=runnable_configs,
            decisions=decisions,
        )

    @classmethod
    def rollout_status_summary(
        cls,
        db: Session,
        *,
        requested_sport: Optional[str] = None,
        requested_competition: Optional[str] = None,
        requested_bookmakers: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        bookmakers = db.query(Bookmaker).all()
        selection = cls.resolve_runnable_bookmakers(
            db,
            bookmaker_rows=bookmakers,
            requested_sport=requested_sport,
            requested_competition=requested_competition,
            requested_bookmakers=requested_bookmakers,
        )
        decisions = selection.decisions
        runnable_count = sum(1 for row in decisions if row.get("runnable"))
        return {
            "requested_sport": _normalize_code(requested_sport) or None,
            "requested_competition": _normalize_code(requested_competition) or None,
            "requested_bookmakers": sorted({_normalize_code(code) for code in (requested_bookmakers or []) if _normalize_code(code)}),
            "eligible_lifecycle_states": sorted(_load_eligible_states()),
            "runnable_count": runnable_count,
            "excluded_count": max(0, len(decisions) - runnable_count),
            "bookmakers": decisions,
        }
