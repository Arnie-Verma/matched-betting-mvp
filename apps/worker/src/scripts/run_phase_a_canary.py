#!/usr/bin/env python
"""
Run a local Phase A canary loop and emit gate evidence artifacts.

The canary captures, per cycle:
- scrape latency and success/failure counts
- breaker state snapshots
- validation status summaries for priority competitions

Usage:
  python -m scripts.run_phase_a_canary
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, "apps/worker/src")
sys.path.insert(0, "apps/api/src")

from jobs.scrape_service import get_scrape_service, trigger_scrape
from validation.config import ValidationConfig
from validation.pipeline import ValidationPipeline


DEFAULT_COMPETITIONS = ["epl", "nba", "nhl", "boxing", "nbl"]
DEFAULT_EVIDENCE_DIR = "docs/evidence/phase-a-hardening/2026-02-11"
DEFAULT_MIN_SCRAPE_SUCCESS_RATE = 0.75
DEFAULT_MAX_OPEN_BREAKER_CYCLES = 0
DEFAULT_MAX_SCRAPE_P95_SECONDS = 360.0


def build_gate_thresholds(
    *,
    min_cycles: int,
    min_duration_seconds: int,
    requires_in_scope_fail_zero: bool,
    min_scrape_success_rate: float,
    max_open_breaker_cycle_count: int,
    max_scrape_p95_seconds: float,
) -> Dict[str, Any]:
    """Build a canonical thresholds payload for deterministic gate evaluation."""
    return {
        "min_cycles": int(min_cycles),
        "min_duration_seconds": int(min_duration_seconds),
        "requires_in_scope_fail_zero": bool(requires_in_scope_fail_zero),
        "min_scrape_success_rate": float(min_scrape_success_rate),
        "max_open_breaker_cycle_count": int(max_open_breaker_cycle_count),
        "max_scrape_p95_seconds": float(max_scrape_p95_seconds),
    }


def _percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * percentile
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return float(ordered[low] * (1 - weight) + ordered[high] * weight)


def _compute_scrape_success_rate_from_cycles(cycles: List[Dict[str, Any]]) -> Dict[str, Any]:
    considered = [
        cycle
        for cycle in cycles
        if int((cycle.get("scrape", {}).get("total_bookmakers") or 0)) > 0
    ]
    total_bookmakers_considered = sum(
        int((cycle.get("scrape", {}).get("total_bookmakers") or 0))
        for cycle in considered
    )
    successful_bookmakers = sum(
        int((cycle.get("scrape", {}).get("bookmakers_scraped") or 0))
        for cycle in considered
    )
    scrape_success_rate = (
        float(successful_bookmakers / total_bookmakers_considered)
        if total_bookmakers_considered > 0
        else 0.0
    )
    return {
        "total_bookmakers_considered": total_bookmakers_considered,
        "successful_bookmakers": successful_bookmakers,
        "scrape_success_rate": scrape_success_rate,
        "cycles_considered": len(considered),
    }


def _compute_open_breaker_cycle_count_from_cycles(cycles: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for cycle in cycles
        if int((cycle.get("breaker", {}).get("open_count") or 0)) > 0
    )


def _compute_scrape_p95_from_cycles(cycles: List[Dict[str, Any]]) -> float:
    scrape_latencies = [
        float(cycle.get("scrape", {}).get("duration_seconds", 0.0))
        for cycle in cycles
    ]
    return _percentile(scrape_latencies, 0.95)


def evaluate_gate(summary: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, Any]:
    """
    Pure canary gate evaluator.

    Takes a summary payload and threshold config, returns a deterministic gate
    decision with explainable criterion-level pass/fail and failure reasons.
    """
    cycles = summary.get("cycles", []) or []
    cycles_completed = int(summary.get("cycles_completed", len(cycles)))
    duration_seconds = float(summary.get("duration_seconds", 0.0))
    validation_metrics = summary.get("validation_gate_metrics", {}) or {}
    in_scope_fail_cycle_count = int(validation_metrics.get("in_scope_fail_cycle_count", 0))

    reliability = summary.get("reliability_metrics", {}) or {}
    if "scrape_success_rate" in reliability:
        scrape_success_rate = float(reliability.get("scrape_success_rate", 0.0))
    else:
        scrape_success_rate = _compute_scrape_success_rate_from_cycles(cycles)["scrape_success_rate"]

    breaker_metrics = summary.get("breaker_metrics", {}) or {}
    if "open_breaker_cycle_count" in breaker_metrics:
        open_breaker_cycle_count = int(breaker_metrics.get("open_breaker_cycle_count", 0))
    else:
        open_breaker_cycle_count = _compute_open_breaker_cycle_count_from_cycles(cycles)

    latency_metrics = summary.get("latency_metrics", {}) or {}
    if "scrape_duration_p95_seconds" in latency_metrics:
        scrape_p95_seconds = float(latency_metrics.get("scrape_duration_p95_seconds", 0.0))
    else:
        scrape_p95_seconds = _compute_scrape_p95_from_cycles(cycles)

    checks: List[Dict[str, Any]] = []
    failure_reasons: List[str] = []

    def add_check(
        *,
        name: str,
        description: str,
        operator: str,
        threshold: Any,
        observed: Any,
        passed: bool,
    ) -> None:
        checks.append(
            {
                "name": name,
                "description": description,
                "operator": operator,
                "threshold": threshold,
                "observed": observed,
                "pass": passed,
            }
        )
        if not passed:
            failure_reasons.append(
                f"{name} failed: expected {operator} {threshold}, observed {observed}"
            )

    min_cycles = int(thresholds["min_cycles"])
    add_check(
        name="min_cycles",
        description="Minimum completed cycles",
        operator=">=",
        threshold=min_cycles,
        observed=cycles_completed,
        passed=cycles_completed >= min_cycles,
    )

    min_duration_seconds = float(thresholds["min_duration_seconds"])
    add_check(
        name="min_duration_seconds",
        description="Minimum canary runtime (seconds)",
        operator=">=",
        threshold=min_duration_seconds,
        observed=duration_seconds,
        passed=duration_seconds >= min_duration_seconds,
    )

    requires_in_scope_fail_zero = bool(thresholds["requires_in_scope_fail_zero"])
    in_scope_pass = (in_scope_fail_cycle_count == 0) if requires_in_scope_fail_zero else True
    add_check(
        name="in_scope_fail_cycle_count",
        description="In-scope FAIL cycles must be zero",
        operator="==" if requires_in_scope_fail_zero else "disabled",
        threshold=0 if requires_in_scope_fail_zero else "n/a",
        observed=in_scope_fail_cycle_count,
        passed=in_scope_pass,
    )

    min_scrape_success_rate = float(thresholds["min_scrape_success_rate"])
    add_check(
        name="min_scrape_success_rate",
        description="Minimum scrape success rate",
        operator=">=",
        threshold=min_scrape_success_rate,
        observed=scrape_success_rate,
        passed=scrape_success_rate >= min_scrape_success_rate,
    )

    max_open_breaker_cycle_count = int(thresholds["max_open_breaker_cycle_count"])
    add_check(
        name="max_open_breaker_cycle_count",
        description="Maximum cycles with open breakers",
        operator="<=",
        threshold=max_open_breaker_cycle_count,
        observed=open_breaker_cycle_count,
        passed=open_breaker_cycle_count <= max_open_breaker_cycle_count,
    )

    max_scrape_p95_seconds = float(thresholds["max_scrape_p95_seconds"])
    add_check(
        name="max_scrape_p95_seconds",
        description="Maximum scrape latency p95 (seconds)",
        operator="<=",
        threshold=max_scrape_p95_seconds,
        observed=scrape_p95_seconds,
        passed=scrape_p95_seconds <= max_scrape_p95_seconds,
    )

    gate_pass = all(check["pass"] for check in checks)
    return {
        "requires_min_cycles": True,
        "requires_min_duration": True,
        "requires_in_scope_fail_zero": requires_in_scope_fail_zero,
        "requires_min_scrape_success_rate": True,
        "requires_max_open_breaker_cycle_count": True,
        "requires_max_scrape_p95_seconds": True,
        "thresholds": thresholds,
        "criteria": checks,
        "failure_reasons": failure_reasons,
        "pass": gate_pass,
    }


def _json_default(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, indent=2, default=_json_default),
        encoding="utf-8",
    )


def _write_md(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _extract_breaker_state_snapshot(scrape_service) -> Dict[str, Any]:
    active_configs = scrape_service.get_active_bookmakers_from_db()
    active_codes = sorted({cfg.get("code") for cfg in active_configs if cfg.get("code")})
    states: Dict[str, str] = {}
    failures: Dict[str, int] = {}
    for code in active_codes:
        state_data = scrape_service._get_breaker_state(code)  # noqa: SLF001
        states[code] = state_data.get("state", "closed")
        failures[code] = int(state_data.get("failures", 0))

    open_codes = [code for code, state in states.items() if state == "open"]
    half_open_codes = [code for code, state in states.items() if state == "half-open"]
    return {
        "states": states,
        "failures": failures,
        "open_codes": open_codes,
        "half_open_codes": half_open_codes,
        "open_count": len(open_codes),
        "half_open_count": len(half_open_codes),
    }


def _validate_priority_competitions(
    pipeline: ValidationPipeline,
    config: ValidationConfig,
    competitions: List[str],
) -> Dict[str, Any]:
    summaries: Dict[str, Any] = {}
    in_scope_fail_rows: List[Dict[str, Any]] = []

    for competition in competitions:
        result = pipeline.validate_from_database(competition=competition)
        report = result.report.to_dict() if result.report is not None else {"scores": {}, "summary": {}}

        status_summary = report.get("summary", {})
        fail_bookmakers = []
        in_scope_fail_bookmakers = []
        out_of_scope_fail_bookmakers = []

        for bookmaker, score in report.get("scores", {}).items():
            if score.get("status") != "FAIL":
                continue
            fail_bookmakers.append(bookmaker)
            scope = config.get_bookmaker_competition_scope(bookmaker, competition)
            row = {
                "competition": competition,
                "bookmaker": bookmaker,
                "coverage_scope": scope,
                "failure_reasons": score.get("failure_reasons", []),
            }
            if scope == "in_scope":
                in_scope_fail_bookmakers.append(bookmaker)
                in_scope_fail_rows.append(row)
            else:
                out_of_scope_fail_bookmakers.append(bookmaker)

        summaries[competition] = {
            "reference_total_events": report.get("reference_total_events", 0),
            "eligible_reference_events": report.get("reference_events", 0),
            "status_summary": {
                "pass_count": status_summary.get("pass_count", 0),
                "warn_count": status_summary.get("warn_count", 0),
                "fail_count": status_summary.get("fail_count", 0),
                "skip_count": status_summary.get("skip_count", 0),
                "na_count": status_summary.get("na_count", 0),
            },
            "fail_bookmakers": fail_bookmakers,
            "in_scope_fail_bookmakers": in_scope_fail_bookmakers,
            "out_of_scope_fail_bookmakers": out_of_scope_fail_bookmakers,
        }

    return {
        "competition_summaries": summaries,
        "in_scope_fail_rows": in_scope_fail_rows,
    }


def build_canary_summary(
    *,
    cycles: List[Dict[str, Any]],
    started_at: datetime,
    ended_at: datetime,
    total_duration: float,
    min_duration_seconds: int,
    min_cycles: int,
    max_cycles: int,
    sleep_seconds: int,
    sports_cycle: List[str],
    competitions: List[str],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """Build final canary summary payload from collected cycle records."""
    scrape_latencies = [float(c.get("scrape", {}).get("duration_seconds", 0.0)) for c in cycles]
    validation_latencies = [float(c.get("validation_duration_seconds", 0.0)) for c in cycles]
    cycle_latencies = [float(c.get("cycle_duration_seconds", 0.0)) for c in cycles]
    breaker_open_counts = [int(c.get("breaker", {}).get("open_count", 0)) for c in cycles]
    breaker_half_open_counts = [int(c.get("breaker", {}).get("half_open_count", 0)) for c in cycles]

    in_scope_fail_rows = [
        row
        for cycle_record in cycles
        for row in cycle_record.get("validation", {}).get("in_scope_fail_rows", [])
    ]
    cycles_with_in_scope_fails = sorted({
        cycle_record.get("cycle")
        for cycle_record in cycles
        if cycle_record.get("validation", {}).get("in_scope_fail_rows")
    })
    cycles_with_open_breakers = sorted({
        cycle_record.get("cycle")
        for cycle_record in cycles
        if int(cycle_record.get("breaker", {}).get("open_count", 0)) > 0
    })

    reliability = _compute_scrape_success_rate_from_cycles(cycles)

    summary = {
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": total_duration,
        "cycles_completed": len(cycles),
        "min_duration_seconds": min_duration_seconds,
        "min_cycles": min_cycles,
        "max_cycles": max_cycles,
        "sleep_seconds": sleep_seconds,
        "sports_cycle": sports_cycle,
        "latency_metrics": {
            "scrape_duration_p50_seconds": _percentile(scrape_latencies, 0.50),
            "scrape_duration_p95_seconds": _percentile(scrape_latencies, 0.95),
            "scrape_duration_avg_seconds": float(statistics.mean(scrape_latencies)) if scrape_latencies else 0.0,
            "validation_duration_p50_seconds": _percentile(validation_latencies, 0.50),
            "validation_duration_p95_seconds": _percentile(validation_latencies, 0.95),
            "cycle_duration_p50_seconds": _percentile(cycle_latencies, 0.50),
            "cycle_duration_p95_seconds": _percentile(cycle_latencies, 0.95),
        },
        "reliability_metrics": {
            **reliability,
            "open_breaker_cycle_count": len(cycles_with_open_breakers),
        },
        "breaker_metrics": {
            "cycles_with_open_breakers": cycles_with_open_breakers,
            "open_breaker_cycle_count": len(cycles_with_open_breakers),
            "max_open_breakers_in_cycle": max(breaker_open_counts) if breaker_open_counts else 0,
            "max_half_open_breakers_in_cycle": max(breaker_half_open_counts) if breaker_half_open_counts else 0,
        },
        "validation_gate_metrics": {
            "cycles_with_in_scope_fails": cycles_with_in_scope_fails,
            "in_scope_fail_cycle_count": len(cycles_with_in_scope_fails),
            "in_scope_fail_rows": in_scope_fail_rows,
            "priority_competitions": competitions,
        },
        "cycles": cycles,
    }
    summary["gate"] = evaluate_gate(summary, thresholds)
    return summary


async def run_canary(
    evidence_dir: Path,
    competitions: List[str],
    sports_cycle: List[str],
    min_duration_seconds: int,
    min_cycles: int,
    max_cycles: int,
    sleep_seconds: int,
    output_prefix: str,
    min_scrape_success_rate: float,
    max_open_breaker_cycles: int,
    max_scrape_p95_seconds: float,
) -> Dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)

    scrape_service = get_scrape_service()
    config = ValidationConfig()
    validation_pipeline = ValidationPipeline(config)

    started_at = datetime.now(timezone.utc)
    start_monotonic = time.time()
    cycles: List[Dict[str, Any]] = []

    cycle = 0
    while cycle < max_cycles:
        cycle += 1
        cycle_started_at = datetime.now(timezone.utc)
        cycle_start = time.time()
        sport = sports_cycle[(cycle - 1) % len(sports_cycle)]

        scrape_result = await trigger_scrape(sport=sport, limit=None)
        scrape_duration = float(scrape_result.get("duration_seconds", 0.0))
        scrape_bookmaker_results = scrape_result.get("results", []) or []
        scrape_failures = [
            r.get("bookmaker")
            for r in scrape_bookmaker_results
            if not r.get("success", False)
        ]

        breaker_snapshot = _extract_breaker_state_snapshot(scrape_service)

        validation_start = time.time()
        validation_data = _validate_priority_competitions(
            pipeline=validation_pipeline,
            config=config,
            competitions=competitions,
        )
        validation_duration = time.time() - validation_start

        cycle_duration = time.time() - cycle_start
        cycle_record = {
            "cycle": cycle,
            "started_at": cycle_started_at.isoformat(),
            "scrape": {
                "sport": sport,
                "duration_seconds": scrape_duration,
                "bookmakers_scraped": scrape_result.get("bookmakers_scraped"),
                "total_bookmakers": scrape_result.get("total_bookmakers"),
                "events_scraped": scrape_result.get("events_scraped"),
                "odds_scraped": scrape_result.get("odds_scraped"),
                "odds_saved": scrape_result.get("odds_saved"),
                "scrape_failures": scrape_failures,
            },
            "breaker": breaker_snapshot,
            "validation": validation_data,
            "validation_duration_seconds": validation_duration,
            "cycle_duration_seconds": cycle_duration,
        }
        cycles.append(cycle_record)

        interim = {
            "started_at": started_at.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "min_duration_seconds": min_duration_seconds,
            "min_cycles": min_cycles,
            "max_cycles": max_cycles,
            "sleep_seconds": sleep_seconds,
            "cycles_completed": cycle,
            "elapsed_seconds": time.time() - start_monotonic,
            "cycles": cycles,
        }
        _write_json(evidence_dir / f"{output_prefix}_interim.json", interim)

        elapsed = time.time() - start_monotonic
        if cycle >= min_cycles and elapsed >= min_duration_seconds:
            break
        if cycle < max_cycles:
            await asyncio.sleep(sleep_seconds)

    ended_at = datetime.now(timezone.utc)
    total_duration = time.time() - start_monotonic
    thresholds = build_gate_thresholds(
        min_cycles=min_cycles,
        min_duration_seconds=min_duration_seconds,
        requires_in_scope_fail_zero=True,
        min_scrape_success_rate=min_scrape_success_rate,
        max_open_breaker_cycle_count=max_open_breaker_cycles,
        max_scrape_p95_seconds=max_scrape_p95_seconds,
    )
    summary = build_canary_summary(
        cycles=cycles,
        started_at=started_at,
        ended_at=ended_at,
        total_duration=total_duration,
        min_duration_seconds=min_duration_seconds,
        min_cycles=min_cycles,
        max_cycles=max_cycles,
        sleep_seconds=sleep_seconds,
        sports_cycle=sports_cycle,
        competitions=competitions,
        thresholds=thresholds,
    )
    return summary


def build_markdown_report(payload: Dict[str, Any]) -> List[str]:
    latency = payload["latency_metrics"]
    breaker = payload["breaker_metrics"]
    reliability = payload.get("reliability_metrics", {})
    gate = payload["gate"]
    validation = payload["validation_gate_metrics"]

    lines = [
        "# Phase A Canary Report",
        "",
        f"- Started: {payload['started_at']}",
        f"- Ended: {payload['ended_at']}",
        f"- Duration (seconds): {payload['duration_seconds']:.2f}",
        f"- Cycles completed: {payload['cycles_completed']}",
        "",
        "## Latency Metrics",
        "",
        f"- Scrape p50: {latency['scrape_duration_p50_seconds']:.2f}s",
        f"- Scrape p95: {latency['scrape_duration_p95_seconds']:.2f}s",
        f"- Scrape avg: {latency['scrape_duration_avg_seconds']:.2f}s",
        f"- Validation p50: {latency['validation_duration_p50_seconds']:.2f}s",
        f"- Validation p95: {latency['validation_duration_p95_seconds']:.2f}s",
        f"- Cycle p50: {latency['cycle_duration_p50_seconds']:.2f}s",
        f"- Cycle p95: {latency['cycle_duration_p95_seconds']:.2f}s",
        "",
        "## Breaker Metrics",
        "",
        f"- Cycles with open breakers: {breaker['open_breaker_cycle_count']}",
        f"- Open breaker cycles: {breaker['cycles_with_open_breakers']}",
        f"- Max open breakers in a cycle: {breaker['max_open_breakers_in_cycle']}",
        f"- Max half-open breakers in a cycle: {breaker['max_half_open_breakers_in_cycle']}",
        "",
        "## Reliability Metrics",
        "",
        f"- Scrape success rate: {float(reliability.get('scrape_success_rate', 0.0)):.4f}",
        f"- Successful bookmakers: {int(reliability.get('successful_bookmakers', 0))}",
        f"- Total bookmakers considered: {int(reliability.get('total_bookmakers_considered', 0))}",
        f"- Cycles considered for success rate: {int(reliability.get('cycles_considered', 0))}",
        "",
        "## Validation Gate Metrics",
        "",
        f"- In-scope FAIL cycles: {validation['in_scope_fail_cycle_count']}",
        f"- In-scope FAIL cycle IDs: {validation['cycles_with_in_scope_fails']}",
        f"- In-scope FAIL rows: {len(validation['in_scope_fail_rows'])}",
        "",
        "## Gate Result",
        "",
        f"- PASS: {gate['pass']}",
        "",
        "| Criterion | Threshold | Observed | Pass |",
        "|---|---:|---:|:---:|",
    ]
    for criterion in gate.get("criteria", []):
        threshold = criterion.get("threshold")
        observed = criterion.get("observed")
        if isinstance(threshold, float):
            threshold = f"{threshold:.4f}"
        if isinstance(observed, float):
            observed = f"{observed:.4f}"
        lines.append(
            f"| {criterion.get('name')} | {threshold} | {observed} | "
            f"{'PASS' if criterion.get('pass') else 'FAIL'} |"
        )
    if gate.get("failure_reasons"):
        lines.extend(
            [
                "",
                "### Failure Reasons",
            ]
        )
        lines.extend([f"- {reason}" for reason in gate["failure_reasons"]])
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase A local canary.")
    parser.add_argument(
        "--competitions",
        nargs="+",
        default=DEFAULT_COMPETITIONS,
        help="Priority competitions for validation checks.",
    )
    parser.add_argument(
        "--evidence-dir",
        default=DEFAULT_EVIDENCE_DIR,
        help="Directory for evidence outputs.",
    )
    parser.add_argument(
        "--output-prefix",
        default="phase_a_canary_pr6_1",
        help="Prefix for canary artifact file names.",
    )
    parser.add_argument(
        "--sports-cycle",
        nargs="+",
        default=["soccer", "basketball", "ice_hockey", "boxing"],
        help="Sports sequence rotated across canary cycles.",
    )
    parser.add_argument(
        "--min-duration-seconds",
        type=int,
        default=1800,
        help="Minimum total canary runtime in seconds.",
    )
    parser.add_argument(
        "--min-cycles",
        type=int,
        default=10,
        help="Minimum number of cycles to run.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=20,
        help="Maximum number of cycles to run.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=int,
        default=60,
        help="Delay between cycles in seconds.",
    )
    parser.add_argument(
        "--min-scrape-success-rate",
        type=float,
        default=DEFAULT_MIN_SCRAPE_SUCCESS_RATE,
        help="Minimum scrape success rate required for gate PASS.",
    )
    parser.add_argument(
        "--max-open-breaker-cycles",
        type=int,
        default=DEFAULT_MAX_OPEN_BREAKER_CYCLES,
        help="Maximum allowed cycles with open breakers.",
    )
    parser.add_argument(
        "--max-scrape-p95-seconds",
        type=float,
        default=DEFAULT_MAX_SCRAPE_P95_SECONDS,
        help="Maximum allowed scrape p95 latency in seconds.",
    )
    args = parser.parse_args()

    # Reduce noisy scraper/validation logs in long-running canary output.
    logging.basicConfig(level=logging.ERROR)

    evidence_dir = Path(args.evidence_dir)
    summary = asyncio.run(
        run_canary(
            evidence_dir=evidence_dir,
            competitions=args.competitions,
            sports_cycle=args.sports_cycle,
            min_duration_seconds=args.min_duration_seconds,
            min_cycles=args.min_cycles,
            max_cycles=args.max_cycles,
            sleep_seconds=args.sleep_seconds,
            output_prefix=args.output_prefix,
            min_scrape_success_rate=args.min_scrape_success_rate,
            max_open_breaker_cycles=args.max_open_breaker_cycles,
            max_scrape_p95_seconds=args.max_scrape_p95_seconds,
        )
    )

    json_path = evidence_dir / f"{args.output_prefix}.json"
    md_path = evidence_dir / f"{args.output_prefix}.md"
    _write_json(json_path, summary)
    _write_md(md_path, build_markdown_report(summary))

    print("CANARY_COMPLETE")
    print(json_path.name)
    print(md_path.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
