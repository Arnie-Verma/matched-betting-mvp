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


async def run_canary(
    evidence_dir: Path,
    competitions: List[str],
    sports_cycle: List[str],
    min_duration_seconds: int,
    min_cycles: int,
    max_cycles: int,
    sleep_seconds: int,
    output_prefix: str,
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

    scrape_latencies = [float(c["scrape"]["duration_seconds"]) for c in cycles]
    validation_latencies = [float(c["validation_duration_seconds"]) for c in cycles]
    cycle_latencies = [float(c["cycle_duration_seconds"]) for c in cycles]
    breaker_open_counts = [int(c["breaker"]["open_count"]) for c in cycles]
    breaker_half_open_counts = [int(c["breaker"]["half_open_count"]) for c in cycles]

    in_scope_fail_rows = [
        row
        for cycle_record in cycles
        for row in cycle_record["validation"]["in_scope_fail_rows"]
    ]
    cycles_with_in_scope_fails = sorted({
        cycle_record["cycle"]
        for cycle_record in cycles
        if cycle_record["validation"]["in_scope_fail_rows"]
    })
    cycles_with_open_breakers = sorted({
        cycle_record["cycle"]
        for cycle_record in cycles
        if cycle_record["breaker"]["open_count"] > 0
    })

    pass_gate = (
        len(cycles) >= min_cycles
        and total_duration >= min_duration_seconds
        and len(in_scope_fail_rows) == 0
    )

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
        "gate": {
            "requires_min_cycles": True,
            "requires_min_duration": True,
            "requires_in_scope_fail_zero": True,
            "pass": pass_gate,
        },
        "cycles": cycles,
    }
    return summary


def build_markdown_report(payload: Dict[str, Any]) -> List[str]:
    latency = payload["latency_metrics"]
    breaker = payload["breaker_metrics"]
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
        "## Validation Gate Metrics",
        "",
        f"- In-scope FAIL cycles: {validation['in_scope_fail_cycle_count']}",
        f"- In-scope FAIL cycle IDs: {validation['cycles_with_in_scope_fails']}",
        f"- In-scope FAIL rows: {len(validation['in_scope_fail_rows'])}",
        "",
        "## Gate Result",
        "",
        f"- Requires min cycles: {gate['requires_min_cycles']}",
        f"- Requires min duration: {gate['requires_min_duration']}",
        f"- Requires in-scope FAIL=0: {gate['requires_in_scope_fail_zero']}",
        f"- PASS: {gate['pass']}",
    ]
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
