#!/usr/bin/env python
"""
Generate Phase A validation evidence artifacts from live DB data.

Usage:
  python -m scripts.generate_phase_a_validation_evidence --suffix pr6_1
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, "apps/worker/src")
sys.path.insert(0, "apps/api/src")

from validation.pipeline import ValidationPipeline
from validation.config import ValidationConfig


DEFAULT_COMPETITIONS = ["epl", "nba", "nhl", "boxing", "nbl"]
DEFAULT_EVIDENCE_DIR = "docs/evidence/phase-a-hardening/2026-02-11"
DEFAULT_BASELINE = "pr6_reason_breakdown_after.json"


def _categorize_reason(row: Dict[str, Any]) -> str:
    reasons = row.get("failure_reasons", []) + row.get("warning_reasons", [])
    text = " | ".join(reasons)
    if "Out-of-scope competition coverage policy" in text:
        return "coverage_out_of_scope_skip"
    if "No eligible reference fixtures in window" in text:
        return "eligible_window_empty"
    if "Event count" in text and "outside expected range" in text:
        return "structural_event_count"
    if "Event coverage" in text:
        return "eligible_coverage"
    if "Coverage " in text:
        return "probability_coverage"
    if "critical anomalies" in text:
        return "probability_anomalies"
    if row.get("status") == "FAIL":
        return "other_fail"
    return "none"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_md(path: Path, lines: List[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate(
    competitions: List[str],
    evidence_dir: Path,
    suffix: str,
    baseline_file: str,
) -> Dict[str, Any]:
    evidence_dir.mkdir(parents=True, exist_ok=True)

    config = ValidationConfig()
    pipeline = ValidationPipeline(config)

    summary_rows: List[Dict[str, Any]] = []
    reason_rows: List[Dict[str, Any]] = []

    for competition in competitions:
        result = pipeline.validate_from_database(competition=competition)
        report_dict = (
            result.report.to_dict()
            if result.report is not None
            else {"competition": competition, "scores": {}, "summary": {}}
        )

        _write_json(
            evidence_dir / f"validation_live_{competition}_{suffix}.json",
            report_dict,
        )

        for bookmaker, score in sorted(report_dict.get("scores", {}).items()):
            scope = config.get_bookmaker_competition_scope(bookmaker, competition)
            row = {
                "competition": competition,
                "bookmaker": bookmaker,
                "coverage_scope": scope,
                "total_reference_events": report_dict.get("reference_total_events", 0),
                "eligible_reference_events": report_dict.get("reference_events", 0),
                "status": score.get("status"),
                "event_count": score.get("event_count"),
                "event_coverage_percent": score.get("event_coverage_percent"),
                "coverage_percent": score.get("coverage_percent"),
                "anomaly_count": score.get("anomaly_count"),
                "critical_anomalies": score.get("critical_anomaly_count", 0),
                "failure_reasons": score.get("failure_reasons", []),
                "warning_reasons": score.get("warning_reasons", []),
            }
            summary_rows.append(
                {
                    "competition": competition,
                    "bookmaker": bookmaker,
                    "coverage_scope": scope,
                    "total_reference_events": row["total_reference_events"],
                    "eligible_reference_events": row["eligible_reference_events"],
                    "status": row["status"],
                    "critical_anomalies": row["critical_anomalies"],
                    "failure_reasons": row["failure_reasons"],
                    "warning_reasons": row["warning_reasons"],
                }
            )
            reason_rows.append({**row, "category": _categorize_reason(row)})

    summary_json_name = f"priority_competition_summary_table_live_{suffix}.json"
    summary_md_name = f"priority_competition_summary_table_live_{suffix}.md"
    _write_json(evidence_dir / summary_json_name, summary_rows)

    summary_lines = [
        f"# {suffix.upper()} Priority Competition Summary (Live DB)",
        "",
        "| Competition | Bookmaker | Scope | Total Ref Events | Eligible Ref Events | Status | Critical Anomalies |",
        "|---|---|---|---:|---:|---|---:|",
    ]
    for row in summary_rows:
        summary_lines.append(
            "| {competition} | {bookmaker} | {coverage_scope} | {total_reference_events} | "
            "{eligible_reference_events} | {status} | {critical_anomalies} |".format(**row)
        )
    _write_md(evidence_dir / summary_md_name, summary_lines)

    status_counts = Counter(r["status"] for r in reason_rows)
    category_counts = Counter(r["category"] for r in reason_rows)
    competition_status_counts: Dict[str, Counter] = defaultdict(Counter)
    competition_category_counts: Dict[str, Counter] = defaultdict(Counter)
    for row in reason_rows:
        competition_status_counts[row["competition"]][row["status"]] += 1
        competition_category_counts[row["competition"]][row["category"]] += 1

    reason_payload = {
        "status_counts": dict(status_counts),
        "category_counts": dict(category_counts),
        "competition_status_counts": {k: dict(v) for k, v in competition_status_counts.items()},
        "competition_category_counts": {k: dict(v) for k, v in competition_category_counts.items()},
        "rows": reason_rows,
    }
    reason_json_name = f"{suffix}_reason_breakdown_after.json"
    reason_md_name = f"{suffix}_reason_breakdown_after.md"
    _write_json(evidence_dir / reason_json_name, reason_payload)

    reason_lines = [
        f"# {suffix.upper()} Reason Breakdown (After)",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(status_counts.items()):
        reason_lines.append(f"- {status}: {count}")
    reason_lines.extend(["", "## Category Counts", ""])
    for category, count in sorted(category_counts.items()):
        reason_lines.append(f"- {category}: {count}")
    reason_lines.extend(["", "## Competition Status Counts", ""])
    for competition in competitions:
        reason_lines.append(
            f"- {competition}: {dict(competition_status_counts.get(competition, {}))}"
        )
    _write_md(evidence_dir / reason_md_name, reason_lines)

    baseline_path = evidence_dir / baseline_file
    baseline = {"status_counts": {}, "category_counts": {}}
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))

    all_statuses = sorted(
        set(baseline.get("status_counts", {}).keys()) | set(status_counts.keys())
    )
    status_delta = {
        status: int(status_counts.get(status, 0))
        - int(baseline.get("status_counts", {}).get(status, 0))
        for status in all_statuses
    }

    in_scope_fail_rows = [
        {
            "competition": row["competition"],
            "bookmaker": row["bookmaker"],
            "status": row["status"],
            "coverage_scope": row["coverage_scope"],
            "failure_reasons": row["failure_reasons"],
        }
        for row in reason_rows
        if row["status"] == "FAIL" and row["coverage_scope"] == "in_scope"
    ]

    reduction_payload = {
        "baseline_source": baseline_file,
        "after_source": reason_json_name,
        "baseline_status_counts": baseline.get("status_counts", {}),
        "after_status_counts": dict(status_counts),
        "status_delta": status_delta,
        "gate_target_in_scope_fail_zero": True,
        "gate_result_in_scope_fail_zero": len(in_scope_fail_rows) == 0,
        "in_scope_fail_rows": in_scope_fail_rows,
    }
    reduction_json_name = f"{suffix}_fail_warn_reduction_summary.json"
    reduction_md_name = f"{suffix}_fail_warn_reduction_summary.md"
    _write_json(evidence_dir / reduction_json_name, reduction_payload)

    reduction_lines = [
        f"# {suffix.upper()} FAIL/WARN Reduction Summary",
        "",
        f"- Baseline status counts: {baseline.get('status_counts', {})}",
        f"- After status counts: {dict(status_counts)}",
        f"- Status delta: {status_delta}",
        f"- In-scope FAIL rows: {len(in_scope_fail_rows)}",
        "- Gate (in-scope FAIL=0): {status}".format(
            status="PASS" if reduction_payload["gate_result_in_scope_fail_zero"] else "FAIL"
        ),
    ]
    if in_scope_fail_rows:
        reduction_lines.extend(["", "## In-scope FAIL rows"])
        for row in in_scope_fail_rows:
            reduction_lines.append(
                "- {competition} / {bookmaker}: {failure_reasons}".format(**row)
            )
    _write_md(evidence_dir / reduction_md_name, reduction_lines)

    return {
        "competition_files": [
            f"validation_live_{competition}_{suffix}.json" for competition in competitions
        ],
        "summary_json": summary_json_name,
        "summary_md": summary_md_name,
        "reason_json": reason_json_name,
        "reason_md": reason_md_name,
        "reduction_json": reduction_json_name,
        "reduction_md": reduction_md_name,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Phase A validation evidence.")
    parser.add_argument(
        "--competitions",
        nargs="+",
        default=DEFAULT_COMPETITIONS,
        help="Competition codes to validate.",
    )
    parser.add_argument(
        "--suffix",
        default="pr6_1",
        help="Artifact suffix (example: pr6_1).",
    )
    parser.add_argument(
        "--evidence-dir",
        default=DEFAULT_EVIDENCE_DIR,
        help="Output directory for evidence artifacts.",
    )
    parser.add_argument(
        "--baseline-file",
        default=DEFAULT_BASELINE,
        help="Baseline reason breakdown JSON in evidence dir.",
    )
    args = parser.parse_args()

    files = generate(
        competitions=args.competitions,
        evidence_dir=Path(args.evidence_dir),
        suffix=args.suffix,
        baseline_file=args.baseline_file,
    )

    print("WROTE_ARTIFACTS")
    for name in files["competition_files"]:
        print(name)
    print(files["summary_json"])
    print(files["summary_md"])
    print(files["reason_json"])
    print(files["reason_md"])
    print(files["reduction_json"])
    print(files["reduction_md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
