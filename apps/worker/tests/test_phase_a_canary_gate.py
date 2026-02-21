"""Tests for Phase A canary gate contract and reliability thresholds."""
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, "apps/worker/src")
sys.path.insert(0, "apps/api/src")

from scripts.run_phase_a_canary import (  # noqa: E402
    build_canary_summary,
    build_gate_thresholds,
    evaluate_gate,
)


def _base_summary() -> dict:
    return {
        "cycles_completed": 10,
        "duration_seconds": 1800.0,
        "latency_metrics": {"scrape_duration_p95_seconds": 300.0},
        "breaker_metrics": {"open_breaker_cycle_count": 0},
        "validation_gate_metrics": {"in_scope_fail_cycle_count": 0},
        "reliability_metrics": {"scrape_success_rate": 0.80},
        "cycles": [],
    }


def _default_thresholds() -> dict:
    return build_gate_thresholds(
        min_cycles=10,
        min_duration_seconds=1800,
        requires_in_scope_fail_zero=True,
        min_scrape_success_rate=0.75,
        max_open_breaker_cycle_count=0,
        max_scrape_p95_seconds=360.0,
    )


def _criterion(gate: dict, name: str) -> dict:
    for row in gate["criteria"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"missing criterion {name}")


def test_gate_fails_on_low_success_rate():
    summary = _base_summary()
    summary["reliability_metrics"]["scrape_success_rate"] = 0.74
    gate = evaluate_gate(summary, _default_thresholds())
    assert gate["pass"] is False
    assert _criterion(gate, "min_scrape_success_rate")["pass"] is False


def test_gate_fails_on_open_breaker_cycle_breach():
    summary = _base_summary()
    summary["breaker_metrics"]["open_breaker_cycle_count"] = 1
    gate = evaluate_gate(summary, _default_thresholds())
    assert gate["pass"] is False
    assert _criterion(gate, "max_open_breaker_cycle_count")["pass"] is False


def test_gate_fails_on_scrape_p95_breach():
    summary = _base_summary()
    summary["latency_metrics"]["scrape_duration_p95_seconds"] = 361.0
    gate = evaluate_gate(summary, _default_thresholds())
    assert gate["pass"] is False
    assert _criterion(gate, "max_scrape_p95_seconds")["pass"] is False


def test_gate_fails_on_min_cycles():
    summary = _base_summary()
    summary["cycles_completed"] = 9
    gate = evaluate_gate(summary, _default_thresholds())
    assert gate["pass"] is False
    assert _criterion(gate, "min_cycles")["pass"] is False


def test_gate_fails_on_min_duration():
    summary = _base_summary()
    summary["duration_seconds"] = 1799.0
    gate = evaluate_gate(summary, _default_thresholds())
    assert gate["pass"] is False
    assert _criterion(gate, "min_duration_seconds")["pass"] is False


def test_gate_fails_on_in_scope_fail_rows():
    summary = _base_summary()
    summary["validation_gate_metrics"]["in_scope_fail_cycle_count"] = 1
    gate = evaluate_gate(summary, _default_thresholds())
    assert gate["pass"] is False
    assert _criterion(gate, "in_scope_fail_cycle_count")["pass"] is False


def test_gate_passes_when_all_criteria_satisfied():
    gate = evaluate_gate(_base_summary(), _default_thresholds())
    assert gate["pass"] is True
    assert all(row["pass"] for row in gate["criteria"])


def test_canary_summary_builder_includes_gate_schema():
    now = datetime.now(timezone.utc)
    cycles = [
        {
            "cycle": 1,
            "scrape": {
                "duration_seconds": 300.0,
                "bookmakers_scraped": 8,
                "total_bookmakers": 10,
            },
            "breaker": {"open_count": 0, "half_open_count": 0},
            "validation": {"in_scope_fail_rows": []},
            "validation_duration_seconds": 1.0,
            "cycle_duration_seconds": 301.0,
        },
        {
            "cycle": 2,
            "scrape": {
                "duration_seconds": 250.0,
                "bookmakers_scraped": 8,
                "total_bookmakers": 10,
            },
            "breaker": {"open_count": 0, "half_open_count": 0},
            "validation": {"in_scope_fail_rows": []},
            "validation_duration_seconds": 1.0,
            "cycle_duration_seconds": 251.0,
        },
    ]
    thresholds = _default_thresholds()
    summary = build_canary_summary(
        cycles=cycles,
        started_at=now,
        ended_at=now,
        total_duration=2000.0,
        min_duration_seconds=1800,
        min_cycles=10,
        max_cycles=20,
        sleep_seconds=0,
        sports_cycle=["soccer"],
        competitions=["epl"],
        thresholds=thresholds,
    )

    assert "gate" in summary
    assert "criteria" in summary["gate"]
    assert "failure_reasons" in summary["gate"]
    assert "thresholds" in summary["gate"]
    assert "reliability_metrics" in summary
    assert "scrape_success_rate" in summary["reliability_metrics"]


def test_gate_derives_metrics_from_cycles_when_metric_blocks_absent():
    cycles = [
        {
            "cycle": 1,
            "scrape": {"duration_seconds": 100.0, "bookmakers_scraped": 8, "total_bookmakers": 10},
            "breaker": {"open_count": 0},
            "validation": {"in_scope_fail_rows": []},
        },
        {
            "cycle": 2,
            "scrape": {"duration_seconds": 200.0, "bookmakers_scraped": 0, "total_bookmakers": 0},
            "breaker": {"open_count": 0},
            "validation": {"in_scope_fail_rows": []},
        },
        {
            "cycle": 3,
            "scrape": {"duration_seconds": 400.0, "bookmakers_scraped": 6, "total_bookmakers": 10},
            "breaker": {"open_count": 1},
            "validation": {"in_scope_fail_rows": []},
        },
    ]
    summary = {
        "cycles_completed": 3,
        "duration_seconds": 500.0,
        "validation_gate_metrics": {"in_scope_fail_cycle_count": 0},
        "cycles": cycles,
    }
    thresholds = build_gate_thresholds(
        min_cycles=3,
        min_duration_seconds=100,
        requires_in_scope_fail_zero=True,
        min_scrape_success_rate=0.70,
        max_open_breaker_cycle_count=1,
        max_scrape_p95_seconds=500.0,
    )

    gate = evaluate_gate(summary, thresholds)
    assert gate["pass"] is True

    success_row = _criterion(gate, "min_scrape_success_rate")
    assert success_row["observed"] == 0.7
    assert success_row["pass"] is True

    breaker_row = _criterion(gate, "max_open_breaker_cycle_count")
    assert breaker_row["observed"] == 1
    assert breaker_row["pass"] is True

    p95_row = _criterion(gate, "max_scrape_p95_seconds")
    assert p95_row["observed"] == pytest.approx(380.0)
    assert p95_row["pass"] is True
