from api.services.observability_service import (
    ObservabilityThresholds,
    evaluate_observability_thresholds,
)


def _summary(
    *,
    scrape_success_rate=0.80,
    scrape_p95_seconds=300.0,
    open_breaker_cycle_count=0,
    matcher_p95_ms=250.0,
    acl_denied_rate=0.01,
):
    return {
        "scrape_reliability": {
            "scrape_success_rate": scrape_success_rate,
            "scrape_duration_p95_seconds": scrape_p95_seconds,
            "open_breaker_cycle_count": open_breaker_cycle_count,
        },
        "matcher_performance": {
            "latency_ms_p95": matcher_p95_ms,
        },
        "security": {
            "acl_denied_rate": acl_denied_rate,
        },
    }


def _criterion(result, name: str):
    for row in result["criteria"]:
        if row["name"] == name:
            return row
    raise AssertionError(f"Missing criterion: {name}")


def test_observability_thresholds_pass_case():
    thresholds = ObservabilityThresholds(enforce_acl_denied_rate=True)
    result = evaluate_observability_thresholds(_summary(), thresholds)
    assert result["overall_pass"] is True
    assert result["failure_reasons"] == []


def test_observability_thresholds_fail_on_low_scrape_success_rate():
    thresholds = ObservabilityThresholds()
    result = evaluate_observability_thresholds(
        _summary(scrape_success_rate=0.74),
        thresholds,
    )
    assert _criterion(result, "scrape_success_rate_min")["pass"] is False
    assert result["overall_pass"] is False


def test_observability_thresholds_fail_on_scrape_p95():
    thresholds = ObservabilityThresholds()
    result = evaluate_observability_thresholds(
        _summary(scrape_p95_seconds=361.0),
        thresholds,
    )
    assert _criterion(result, "scrape_p95_seconds_max")["pass"] is False
    assert result["overall_pass"] is False


def test_observability_thresholds_fail_on_open_breaker_cycles():
    thresholds = ObservabilityThresholds()
    result = evaluate_observability_thresholds(
        _summary(open_breaker_cycle_count=1),
        thresholds,
    )
    assert _criterion(result, "open_breaker_cycle_count_max")["pass"] is False
    assert result["overall_pass"] is False


def test_observability_thresholds_fail_on_matcher_p95():
    thresholds = ObservabilityThresholds()
    result = evaluate_observability_thresholds(
        _summary(matcher_p95_ms=401.0),
        thresholds,
    )
    assert _criterion(result, "matcher_p95_ms_max")["pass"] is False
    assert result["overall_pass"] is False


def test_observability_thresholds_fail_on_acl_denied_rate_when_enforced():
    thresholds = ObservabilityThresholds(
        acl_denied_rate_max=0.10,
        enforce_acl_denied_rate=True,
    )
    result = evaluate_observability_thresholds(
        _summary(acl_denied_rate=0.25),
        thresholds,
    )
    acl_row = _criterion(result, "acl_denied_rate_max")
    assert acl_row["pass"] is False
    assert acl_row["enforced"] is True
    assert result["overall_pass"] is False

