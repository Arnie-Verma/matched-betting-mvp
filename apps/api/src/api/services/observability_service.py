import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import redis


logger = logging.getLogger(__name__)

OBSERVABILITY_SCHEMA_VERSION = "observability.v1"
OBSERVABILITY_THRESHOLD_SCHEMA_VERSION = "observability.thresholds.v1"


def _parse_bool(raw_value: str, default: bool) -> bool:
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_float(raw_value: Optional[str], fallback: float) -> float:
    if raw_value is None or raw_value == "":
        return float(fallback)
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return float(fallback)


def _parse_int(raw_value: Optional[str], fallback: int) -> int:
    if raw_value is None or raw_value == "":
        return int(fallback)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return int(fallback)


def _percentile(values: List[float], percentile: float) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    percentile = min(max(percentile, 0.0), 1.0)
    position = (len(ordered) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    weight = position - lower_index
    return ordered[lower_index] * (1.0 - weight) + ordered[upper_index] * weight


def _decode_scalar(raw: Any) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="ignore")
    if raw is None:
        return ""
    return str(raw)


def _safe_json_loads(raw_value: str) -> Dict[str, Any]:
    if not raw_value:
        return {}
    try:
        loaded = json.loads(raw_value)
        if isinstance(loaded, dict):
            return loaded
        return {"_raw": loaded}
    except (TypeError, ValueError):
        return {"_unparsed": raw_value}


@dataclass(frozen=True)
class ObservabilityThresholds:
    scrape_success_rate_min: float = 0.75
    scrape_p95_seconds_max: float = 360.0
    open_breaker_cycle_count_max: int = 0
    matcher_p95_ms_max: float = 400.0
    acl_denied_rate_max: float = 0.10
    enforce_acl_denied_rate: bool = False

    @classmethod
    def from_env(cls) -> "ObservabilityThresholds":
        return cls(
            scrape_success_rate_min=_parse_float(os.getenv("OBS_SCRAPE_SUCCESS_RATE_MIN"), 0.75),
            scrape_p95_seconds_max=_parse_float(os.getenv("OBS_SCRAPE_P95_SECONDS_MAX"), 360.0),
            open_breaker_cycle_count_max=_parse_int(os.getenv("OBS_OPEN_BREAKER_CYCLE_COUNT_MAX"), 0),
            matcher_p95_ms_max=_parse_float(os.getenv("OBS_MATCHER_P95_MS_MAX"), 400.0),
            acl_denied_rate_max=_parse_float(os.getenv("OBS_ACL_DENIED_RATE_MAX"), 0.10),
            enforce_acl_denied_rate=_parse_bool(
                os.getenv("OBS_ENFORCE_ACL_DENIED_RATE", "false"),
                default=False,
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _telemetry_enabled() -> bool:
    return _parse_bool(os.getenv("OBSERVABILITY_ENABLED", "true"), default=True)


def _stream_key() -> str:
    return os.getenv("OBSERVABILITY_STREAM_KEY", "observability:events:v1")


def _stream_maxlen() -> int:
    return max(1000, _parse_int(os.getenv("OBSERVABILITY_STREAM_MAXLEN"), 200000))


def _get_redis_client(redis_client=None):
    if redis_client is not None:
        return redis_client
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        socket_connect_timeout=0.2,
        socket_timeout=0.2,
    )


def emit_observability_event(
    *,
    category: str,
    metric_name: str,
    source: str,
    endpoint: Optional[str] = None,
    action_type: Optional[str] = None,
    bookmaker_code: Optional[str] = None,
    platform_code: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    recorded_at: Optional[datetime] = None,
    redis_client=None,
) -> Optional[str]:
    """
    Persist one observability event to Redis stream.
    """
    if not _telemetry_enabled():
        return None

    event_time = recorded_at or datetime.now(timezone.utc)
    serialized_payload = json.dumps(payload or {}, sort_keys=True, default=str)
    fields = {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "recorded_at": event_time.isoformat(),
        "category": category,
        "metric_name": metric_name,
        "source": source,
        "endpoint": endpoint or "",
        "action_type": action_type or "",
        "bookmaker_code": bookmaker_code or "",
        "platform_code": platform_code or "",
        "payload_json": serialized_payload,
    }

    try:
        client = _get_redis_client(redis_client=redis_client)
        stream_id = client.xadd(
            _stream_key(),
            fields,
            maxlen=_stream_maxlen(),
            approximate=True,
        )
        if isinstance(stream_id, bytes):
            return stream_id.decode("utf-8", errors="ignore")
        return str(stream_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Observability emit failed: %s", exc)
        return None


def read_observability_events(
    *,
    hours: int = 24,
    limit: int = 5000,
    redis_client=None,
) -> List[Dict[str, Any]]:
    """
    Read observability events from Redis stream for a trailing time window.
    """
    if hours <= 0:
        return []

    try:
        client = _get_redis_client(redis_client=redis_client)
        now = datetime.now(timezone.utc)
        start_time = now - timedelta(hours=int(hours))
        start_id = f"{int(start_time.timestamp() * 1000)}-0"
        raw_entries = client.xrevrange(_stream_key(), "+", start_id, count=int(limit))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Observability read failed: %s", exc)
        return []

    events: List[Dict[str, Any]] = []
    for stream_id, raw_fields in reversed(raw_entries):
        parsed_fields = { _decode_scalar(k): _decode_scalar(v) for k, v in raw_fields.items() }
        payload = _safe_json_loads(parsed_fields.get("payload_json", ""))
        events.append(
            {
                "stream_id": _decode_scalar(stream_id),
                "schema_version": parsed_fields.get("schema_version", OBSERVABILITY_SCHEMA_VERSION),
                "recorded_at": parsed_fields.get("recorded_at"),
                "category": parsed_fields.get("category", ""),
                "metric_name": parsed_fields.get("metric_name", ""),
                "source": parsed_fields.get("source", ""),
                "endpoint": parsed_fields.get("endpoint") or None,
                "action_type": parsed_fields.get("action_type") or None,
                "bookmaker_code": parsed_fields.get("bookmaker_code") or None,
                "platform_code": parsed_fields.get("platform_code") or None,
                "payload": payload,
            }
        )
    return events


def summarize_observability_events(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    event_list = list(events)
    scheduler_events = [e for e in event_list if e.get("metric_name") == "scrape_scheduler_cycle"]
    reliability_cycle_events = [e for e in event_list if e.get("metric_name") == "scrape_reliability_cycle"]
    bookmaker_result_events = [e for e in event_list if e.get("metric_name") == "scrape_bookmaker_result"]
    breaker_transition_events = [e for e in event_list if e.get("metric_name") == "breaker_transition"]
    matcher_events = [e for e in event_list if e.get("metric_name") == "matcher_request"]
    security_events = [e for e in event_list if e.get("category") == "security"]

    latest_scheduler = scheduler_events[-1].get("payload", {}) if scheduler_events else {}
    max_global_in_flight = 0
    max_platform_in_flight: Dict[str, int] = {}
    for event in scheduler_events:
        payload = event.get("payload", {})
        max_global_in_flight = max(
            max_global_in_flight,
            int(payload.get("observed_max_in_flight_global", 0) or 0),
        )
        platform_values = payload.get("observed_max_in_flight_by_platform") or {}
        if isinstance(platform_values, dict):
            for platform_code, value in platform_values.items():
                platform = str(platform_code)
                max_platform_in_flight[platform] = max(
                    max_platform_in_flight.get(platform, 0),
                    int(value or 0),
                )

    success_count = 0
    failure_count = 0
    by_bookmaker: Dict[str, Dict[str, int]] = {}
    by_platform: Dict[str, Dict[str, int]] = {}
    scrape_durations_seconds: List[float] = []

    for event in bookmaker_result_events:
        payload = event.get("payload", {})
        success = bool(payload.get("success"))
        if success:
            success_count += 1
        else:
            failure_count += 1
        bookmaker_code = event.get("bookmaker_code") or "unknown"
        platform_code = event.get("platform_code") or "unknown"
        bookmaker_bucket = by_bookmaker.setdefault(bookmaker_code, {"success": 0, "failure": 0})
        platform_bucket = by_platform.setdefault(platform_code, {"success": 0, "failure": 0})
        if success:
            bookmaker_bucket["success"] += 1
            platform_bucket["success"] += 1
        else:
            bookmaker_bucket["failure"] += 1
            platform_bucket["failure"] += 1

        duration_seconds = payload.get("scrape_duration_seconds")
        if duration_seconds is None:
            duration_seconds = payload.get("duration_seconds")
        if duration_seconds is not None:
            try:
                scrape_durations_seconds.append(float(duration_seconds))
            except (TypeError, ValueError):
                pass

    total_results = success_count + failure_count
    scrape_success_rate = (success_count / total_results) if total_results else None

    open_breaker_cycle_count = 0
    for event in reliability_cycle_events:
        payload = event.get("payload", {})
        if int(payload.get("open_breaker_count", 0) or 0) > 0:
            open_breaker_cycle_count += 1

    breaker_open_transition_count = 0
    for event in breaker_transition_events:
        payload = event.get("payload", {})
        if str(payload.get("to_state", "")).lower() == "open":
            breaker_open_transition_count += 1

    matcher_latencies = []
    matcher_query_signals = []
    for event in matcher_events:
        payload = event.get("payload", {})
        latency = payload.get("latency_ms")
        query_signal = payload.get("query_round_trip_signal")
        try:
            if latency is not None:
                matcher_latencies.append(float(latency))
        except (TypeError, ValueError):
            pass
        try:
            if query_signal is not None:
                matcher_query_signals.append(float(query_signal))
        except (TypeError, ValueError):
            pass

    denied_security_events = [
        event for event in security_events if str(event.get("action_type", "")).endswith("_denied")
    ]
    allowed_security_events = [
        event for event in security_events if str(event.get("action_type", "")).endswith("_allowed")
    ]

    denied_counts_by_action: Dict[str, int] = {}
    for event in denied_security_events:
        action = str(event.get("action_type") or "unknown_denied")
        denied_counts_by_action[action] = denied_counts_by_action.get(action, 0) + 1

    security_total = len(denied_security_events) + len(allowed_security_events)
    acl_denied_rate = (len(denied_security_events) / security_total) if security_total else None

    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "total_events": len(event_list),
        "scheduler": {
            "event_count": len(scheduler_events),
            "configured_global_cap_latest": latest_scheduler.get("configured_global_cap"),
            "configured_platform_caps_latest": latest_scheduler.get("configured_platform_caps"),
            "observed_max_in_flight_global_max": max_global_in_flight,
            "observed_max_in_flight_by_platform_max": max_platform_in_flight,
        },
        "scrape_reliability": {
            "result_event_count": total_results,
            "success_count": success_count,
            "failure_count": failure_count,
            "scrape_success_rate": scrape_success_rate,
            "counts_by_bookmaker": by_bookmaker,
            "counts_by_platform": by_platform,
            "open_breaker_cycle_count": open_breaker_cycle_count,
            "breaker_open_transition_count": breaker_open_transition_count,
            "scrape_duration_p95_seconds": _percentile(scrape_durations_seconds, 0.95),
        },
        "matcher_performance": {
            "request_count": len(matcher_events),
            "latency_ms_p50": _percentile(matcher_latencies, 0.50),
            "latency_ms_p95": _percentile(matcher_latencies, 0.95),
            "query_round_trip_signal_p50": _percentile(matcher_query_signals, 0.50),
            "query_round_trip_signal_p95": _percentile(matcher_query_signals, 0.95),
        },
        "security": {
            "allowed_count": len(allowed_security_events),
            "denied_count": len(denied_security_events),
            "denied_counts_by_action": denied_counts_by_action,
            "acl_denied_rate": acl_denied_rate,
        },
        "sample_events": event_list[:10],
    }


def evaluate_observability_thresholds(
    summary: Dict[str, Any],
    thresholds: ObservabilityThresholds,
) -> Dict[str, Any]:
    scrape = summary.get("scrape_reliability", {}) or {}
    matcher = summary.get("matcher_performance", {}) or {}
    security = summary.get("security", {}) or {}

    criteria: List[Dict[str, Any]] = []

    def _append_criterion(
        *,
        name: str,
        threshold: Any,
        observed: Any,
        passed: bool,
        description: str,
        enforced: bool = True,
    ) -> None:
        criteria.append(
            {
                "name": name,
                "description": description,
                "threshold": threshold,
                "observed": observed,
                "pass": bool(passed),
                "enforced": bool(enforced),
            }
        )

    success_rate = scrape.get("scrape_success_rate")
    has_success_rate = success_rate is not None
    _append_criterion(
        name="scrape_success_rate_min",
        threshold=thresholds.scrape_success_rate_min,
        observed=success_rate,
        passed=has_success_rate and float(success_rate) >= float(thresholds.scrape_success_rate_min),
        description="Minimum scrape success rate across bookmaker result events.",
    )

    scrape_p95_seconds = scrape.get("scrape_duration_p95_seconds")
    has_scrape_p95 = scrape_p95_seconds is not None
    _append_criterion(
        name="scrape_p95_seconds_max",
        threshold=thresholds.scrape_p95_seconds_max,
        observed=scrape_p95_seconds,
        passed=has_scrape_p95 and float(scrape_p95_seconds) <= float(thresholds.scrape_p95_seconds_max),
        description="Maximum p95 scrape duration from emitted scrape result durations.",
    )

    open_breaker_cycle_count = int(scrape.get("open_breaker_cycle_count") or 0)
    _append_criterion(
        name="open_breaker_cycle_count_max",
        threshold=thresholds.open_breaker_cycle_count_max,
        observed=open_breaker_cycle_count,
        passed=open_breaker_cycle_count <= int(thresholds.open_breaker_cycle_count_max),
        description="Maximum number of reliability cycles with open breakers.",
    )

    matcher_p95_ms = matcher.get("latency_ms_p95")
    has_matcher_p95 = matcher_p95_ms is not None
    _append_criterion(
        name="matcher_p95_ms_max",
        threshold=thresholds.matcher_p95_ms_max,
        observed=matcher_p95_ms,
        passed=has_matcher_p95 and float(matcher_p95_ms) <= float(thresholds.matcher_p95_ms_max),
        description="Maximum p95 matcher latency in milliseconds.",
    )

    acl_denied_rate = security.get("acl_denied_rate")
    has_acl_denied_rate = acl_denied_rate is not None
    acl_passed = has_acl_denied_rate and float(acl_denied_rate) <= float(thresholds.acl_denied_rate_max)
    _append_criterion(
        name="acl_denied_rate_max",
        threshold=thresholds.acl_denied_rate_max,
        observed=acl_denied_rate,
        passed=acl_passed,
        description="Maximum denied access rate for protected security endpoints.",
        enforced=thresholds.enforce_acl_denied_rate,
    )

    failure_reasons = [
        (
            f"{row['name']} failed (observed={row['observed']} "
            f"threshold={row['threshold']})"
        )
        for row in criteria
        if row["enforced"] and not row["pass"]
    ]

    overall_pass = len(failure_reasons) == 0

    return {
        "schema_version": OBSERVABILITY_THRESHOLD_SCHEMA_VERSION,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "thresholds": thresholds.to_dict(),
        "criteria": criteria,
        "overall_pass": overall_pass,
        "failure_reasons": failure_reasons,
    }


def build_observability_report(
    *,
    hours: int = 24,
    limit: int = 5000,
    redis_client=None,
    thresholds: Optional[ObservabilityThresholds] = None,
) -> Dict[str, Any]:
    events = read_observability_events(hours=hours, limit=limit, redis_client=redis_client)
    summary = summarize_observability_events(events)
    threshold_config = thresholds or ObservabilityThresholds.from_env()
    threshold_evaluation = evaluate_observability_thresholds(summary, threshold_config)
    return {
        "schema_version": OBSERVABILITY_SCHEMA_VERSION,
        "window_hours": int(hours),
        "events_analyzed": len(events),
        "summary": summary,
        "threshold_evaluation": threshold_evaluation,
    }
