"""
Generate PR-O1 observability evidence artifacts.

Outputs:
  - docs/evidence/phase-a-hardening/2026-02-11/pr13_observability_metrics.json
  - docs/evidence/phase-a-hardening/2026-02-11/pr13_observability_threshold_eval.json
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from api.services.observability_service import (
    OBSERVABILITY_SCHEMA_VERSION,
    ObservabilityThresholds,
    evaluate_observability_thresholds,
    summarize_observability_events,
)


METRICS_OUTPUT = Path(
    "docs/evidence/phase-a-hardening/2026-02-11/pr13_observability_metrics.json"
)
THRESHOLD_OUTPUT = Path(
    "docs/evidence/phase-a-hardening/2026-02-11/pr13_observability_threshold_eval.json"
)


def _event(
    *,
    recorded_at: datetime,
    category: str,
    metric_name: str,
    source: str,
    endpoint: str = "",
    action_type: str = "",
    bookmaker_code: str = "",
    platform_code: str = "",
    payload: Dict[str, Any],
    seq: int,
) -> Dict[str, Any]:
    return {
        "stream_id": f"{int(recorded_at.timestamp() * 1000)}-{seq}",
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "recorded_at": recorded_at.isoformat(),
        "category": category,
        "metric_name": metric_name,
        "source": source,
        "endpoint": endpoint or None,
        "action_type": action_type or None,
        "bookmaker_code": bookmaker_code or None,
        "platform_code": platform_code or None,
        "payload": payload,
    }


def build_synthetic_24h_events() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    events: List[Dict[str, Any]] = []
    seq = 0

    for hour in range(24):
        ts = now - timedelta(hours=23 - hour)
        entain_success = 1 if hour % 8 else 0
        punter_success = 1
        success_count = entain_success + punter_success
        failure_count = 2 - success_count
        success_rate = success_count / 2
        open_breakers = 0
        scrape_p95 = 280.0 + (hour % 4) * 12.0
        matcher_latency = 180.0 + (hour % 5) * 25.0

        seq += 1
        events.append(
            _event(
                recorded_at=ts,
                category="scheduler",
                metric_name="scrape_scheduler_cycle",
                source="worker",
                action_type="bounded_scheduler_cycle",
                payload={
                    "configured_global_cap": 3,
                    "configured_platform_default_cap": 2,
                    "configured_platform_caps": {"entain": 1, "punterstech": 2},
                    "observed_max_in_flight_global": 3,
                    "observed_max_in_flight_by_platform": {"entain": 1, "punterstech": 2},
                    "cycle_duration_seconds": 22.0 + (hour % 3) * 1.5,
                },
                seq=seq,
            )
        )

        seq += 1
        events.append(
            _event(
                recorded_at=ts,
                category="scrape_reliability",
                metric_name="scrape_reliability_cycle",
                source="worker",
                action_type="scrape_cycle_summary",
                payload={
                    "total_bookmakers": 2,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "scrape_success_rate": success_rate,
                    "open_breaker_count": open_breakers,
                    "scrape_duration_p95_seconds": scrape_p95,
                    "platform_outcomes": {
                        "entain": {"success": entain_success, "failure": int(not entain_success)},
                        "punterstech": {"success": punter_success, "failure": 0},
                    },
                },
                seq=seq,
            )
        )

        for bookmaker_code, platform_code, success, duration in (
            ("ladbrokes", "entain", bool(entain_success), scrape_p95 - 40),
            ("mintbet", "punterstech", True, scrape_p95 - 20),
        ):
            seq += 1
            events.append(
                _event(
                    recorded_at=ts,
                    category="scrape_reliability",
                    metric_name="scrape_bookmaker_result",
                    source="worker",
                    bookmaker_code=bookmaker_code,
                    platform_code=platform_code,
                    action_type="bookmaker_scrape_result",
                    payload={
                        "success": success,
                        "events_scraped": 12,
                        "odds_scraped": 96,
                        "scrape_duration_seconds": duration,
                    },
                    seq=seq,
                )
            )

        seq += 1
        events.append(
            _event(
                recorded_at=ts,
                category="matcher_performance",
                metric_name="matcher_request",
                source="api",
                endpoint="/odds/matcher",
                action_type="matcher_request",
                payload={
                    "status_code": 200,
                    "latency_ms": matcher_latency,
                    "query_round_trip_signal": 4,
                    "opportunities_total": 140 + (hour % 6),
                },
                seq=seq,
            )
        )

        seq += 1
        events.append(
            _event(
                recorded_at=ts,
                category="security",
                metric_name="access_decision",
                source="api",
                endpoint="/odds/refresh/status",
                action_type="refresh_status_acl_allowed",
                payload={"mode": "owner"},
                seq=seq,
            )
        )
        seq += 1
        events.append(
            _event(
                recorded_at=ts,
                category="security",
                metric_name="access_decision",
                source="api",
                endpoint="/health/scrapers",
                action_type="scraper_health_access_allowed",
                payload={"mode": "authenticated"},
                seq=seq,
            )
        )

        # Sparse denied attempts to keep denied-rate low.
        if hour in {3, 9, 17}:
            seq += 1
            events.append(
                _event(
                    recorded_at=ts,
                    category="security",
                    metric_name="access_decision",
                    source="api",
                    endpoint="/health/scrapers",
                    action_type="scraper_health_access_denied",
                    payload={"reason": "unauthenticated"},
                    seq=seq,
                )
            )

    return events


def main() -> None:
    events = build_synthetic_24h_events()
    summary = summarize_observability_events(events)
    thresholds = ObservabilityThresholds.from_env()

    baseline_eval = evaluate_observability_thresholds(summary, thresholds)

    stressed_summary = json.loads(json.dumps(summary))
    stressed_summary["scrape_reliability"]["scrape_success_rate"] = 0.60
    stressed_summary["scrape_reliability"]["scrape_duration_p95_seconds"] = 420.0
    stressed_summary["scrape_reliability"]["open_breaker_cycle_count"] = 2
    stressed_summary["matcher_performance"]["latency_ms_p95"] = 520.0
    stressed_summary["security"]["acl_denied_rate"] = 0.40
    stressed_eval = evaluate_observability_thresholds(
        stressed_summary,
        ObservabilityThresholds.from_env(),
    )

    metrics_payload = {
        "slice": "PR-O1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "window": "synthetic_24h_equivalent",
        "telemetry_schema": {
            "schema_version": "observability.v1",
            "fields": {
                "recorded_at": "ISO-8601 timestamp",
                "category": "scheduler|scrape_reliability|matcher_performance|security",
                "metric_name": "stable metric id",
                "source": "worker|api",
                "endpoint": "request path when applicable",
                "action_type": "event action semantic",
                "bookmaker_code": "bookmaker attribution when applicable",
                "platform_code": "platform attribution when applicable",
                "payload": "versioned metric body JSON object",
            },
        },
        "summary": summary,
        "sample_metric_records": events[:12],
        "runtime_overhead_note": (
            "Emission is one Redis XADD per event with bounded stream length; "
            "query-signal values reuse existing query stages and do not add DB round-trips."
        ),
    }
    threshold_payload = {
        "slice": "PR-O1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold_settings": thresholds.to_dict(),
        "baseline_evaluation": baseline_eval,
        "stressed_evaluation": stressed_eval,
    }

    METRICS_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    METRICS_OUTPUT.write_text(json.dumps(metrics_payload, indent=2), encoding="utf-8")
    THRESHOLD_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    THRESHOLD_OUTPUT.write_text(json.dumps(threshold_payload, indent=2), encoding="utf-8")

    print(f"Wrote {METRICS_OUTPUT}")
    print(f"Wrote {THRESHOLD_OUTPUT}")


if __name__ == "__main__":
    main()
