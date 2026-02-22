"""Shared gate-contract constants for lifecycle promotion enforcement."""
from __future__ import annotations


DEFAULT_VALIDATION_EVIDENCE_MAX_AGE_SECONDS = 6 * 60 * 60
DEFAULT_CANARY_EVIDENCE_MAX_AGE_SECONDS = 6 * 60 * 60

REQUIRED_CANARY_GATE_THRESHOLDS = {
    "min_cycles": 10,
    "min_duration_seconds": 1800,
    "requires_in_scope_fail_zero": True,
    "min_scrape_success_rate": 0.75,
    "max_open_breaker_cycle_count": 0,
    "max_scrape_p95_seconds": 360.0,
}
