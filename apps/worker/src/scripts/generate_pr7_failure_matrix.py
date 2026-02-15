#!/usr/bin/env python
"""
Generate PR7 EPL/boxing failure decomposition matrix.

Classifies FAIL rows into one of:
- coverage denominator mismatch
- event mapping miss
- market-shape/key mismatch
- probability anomaly
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_EVIDENCE_DIR = Path("docs/evidence/phase-a-hardening/2026-02-11")
DEFAULT_SOURCE = "pr6_1_reason_breakdown_after.json"


def _classify(row: Dict[str, Any]) -> str:
    reasons = row.get("failure_reasons", []) or []
    text = " | ".join(str(r) for r in reasons)
    competition = str(row.get("competition", "")).lower()

    if "critical anomalies" in text:
        return "probability anomaly"

    if competition == "epl" and "Event coverage" in text:
        # In PR6.1, EPL FAILs were caused by denominator drift:
        # reference had a larger eligible window than several Punterstech brands.
        return "coverage denominator mismatch"

    if competition == "boxing" and "Coverage " in text:
        # Boxing FAILs in PR6.1 were zero-coverage rows with non-zero events,
        # indicating fixture/key overlap misses vs reference coverage.
        return "event mapping miss"

    if "Structural validation failed" in text and row.get("event_count", 0):
        return "market-shape/key mismatch"

    return "event mapping miss"


def generate(evidence_dir: Path, source_json: str, output_prefix: str) -> Dict[str, Any]:
    source_path = evidence_dir / source_json
    payload = json.loads(source_path.read_text(encoding="utf-8"))

    rows = payload.get("rows", [])
    target_rows: List[Dict[str, Any]] = []
    for row in rows:
        competition = str(row.get("competition", "")).lower()
        if competition not in {"epl", "boxing"}:
            continue
        if row.get("status") != "FAIL":
            continue

        target_rows.append(
            {
                "bookmaker": row.get("bookmaker"),
                "competition": competition,
                "status": row.get("status"),
                "total_reference_events": row.get("total_reference_events"),
                "eligible_reference_events": row.get("eligible_reference_events"),
                "event_count": row.get("event_count"),
                "event_coverage_percent": row.get("event_coverage_percent"),
                "coverage_percent": row.get("coverage_percent"),
                "exact_fail_reason": "; ".join(row.get("failure_reasons", []) or []),
                "decomposition_reason": _classify(row),
            }
        )

    reason_counts = Counter(r["decomposition_reason"] for r in target_rows)
    for reason in (
        "coverage denominator mismatch",
        "event mapping miss",
        "market-shape/key mismatch",
        "probability anomaly",
    ):
        reason_counts.setdefault(reason, 0)

    out_payload = {
        "source": source_json,
        "rows": target_rows,
        "reason_counts": dict(reason_counts),
    }

    json_name = f"{output_prefix}.json"
    md_name = f"{output_prefix}.md"
    (evidence_dir / json_name).write_text(json.dumps(out_payload, indent=2), encoding="utf-8")

    lines = [
        "# PR7 Failure Decomposition Matrix (EPL + Boxing)",
        "",
        f"- Source: `{source_json}`",
        "",
        "## Reason Counts",
        "",
    ]
    for reason in (
        "coverage denominator mismatch",
        "event mapping miss",
        "market-shape/key mismatch",
        "probability anomaly",
    ):
        lines.append(f"- {reason}: {reason_counts[reason]}")

    lines.extend(
        [
            "",
            "## Bookmaker x Competition Matrix",
            "",
            "| Bookmaker | Competition | Exact FAIL Reason | Decomposition | Ref Events | Eligible Ref | Book Events | Event Coverage % | Prob Coverage % |",
            "|---|---|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(target_rows, key=lambda r: (r["competition"], r["bookmaker"])):
        lines.append(
            "| {bookmaker} | {competition} | {exact_fail_reason} | {decomposition_reason} | "
            "{total_reference_events} | {eligible_reference_events} | {event_count} | "
            "{event_coverage_percent} | {coverage_percent} |".format(**row)
        )

    (evidence_dir / md_name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_name, "md": md_name}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PR7 failure decomposition matrix.")
    parser.add_argument("--evidence-dir", default=str(DEFAULT_EVIDENCE_DIR))
    parser.add_argument("--source-json", default=DEFAULT_SOURCE)
    parser.add_argument("--output-prefix", default="pr7_failure_decomposition_matrix")
    args = parser.parse_args()

    outputs = generate(
        evidence_dir=Path(args.evidence_dir),
        source_json=args.source_json,
        output_prefix=args.output_prefix,
    )
    print("WROTE_ARTIFACTS")
    print(outputs["json"])
    print(outputs["md"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

