import asyncio
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jobs import refresh_worker
from jobs import scrape_service as scrape_service_module


class _DummyScraper:
    def __init__(self, *args, **kwargs):
        pass


class _DummyRedis:
    def get(self, *args, **kwargs):
        return None

    def set(self, *args, **kwargs):
        return None

    def setex(self, *args, **kwargs):
        return None

    def incr(self, *args, **kwargs):
        return 1

    def decr(self, *args, **kwargs):
        return 0

    def expire(self, *args, **kwargs):
        return True


@pytest.fixture
def service(monkeypatch):
    monkeypatch.setattr(scrape_service_module, "BetfairScraper", _DummyScraper)
    monkeypatch.setattr(scrape_service_module, "EntainScraper", _DummyScraper)
    monkeypatch.setattr(scrape_service_module.redis, "from_url", lambda *_args, **_kwargs: _DummyRedis())
    svc = scrape_service_module.ScrapeService()
    monkeypatch.setattr(svc, "get_scraper_for_bookmaker", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(svc, "_run_post_scrape_cleanup", lambda: {"skipped": True})
    return svc


def test_platform_default_concurrency_fallback_and_default_overrides(monkeypatch):
    monkeypatch.setattr(scrape_service_module, "BetfairScraper", _DummyScraper)
    monkeypatch.setattr(scrape_service_module, "EntainScraper", _DummyScraper)
    monkeypatch.setattr(scrape_service_module.redis, "from_url", lambda *_args, **_kwargs: _DummyRedis())
    monkeypatch.delenv("SCRAPE_PLATFORM_CONCURRENCY_DEFAULT_CAP", raising=False)
    monkeypatch.delenv("SCRAPE_GLOBAL_CONCURRENCY_CAP", raising=False)
    monkeypatch.delenv("BOOKMAKER_CONCURRENCY_CAP", raising=False)

    svc = scrape_service_module.ScrapeService()

    assert svc.platform_default_concurrency_cap == 1
    assert svc.platform_concurrency_caps.get("punterstech") == 2


@pytest.mark.asyncio
async def test_global_scheduler_cap_is_respected(monkeypatch, service):
    monkeypatch.setenv("SCRAPE_GLOBAL_CONCURRENCY_CAP", "2")
    monkeypatch.setenv("SCRAPE_PLATFORM_CONCURRENCY_DEFAULT_CAP", "10")
    monkeypatch.delenv("SCRAPE_PLATFORM_CONCURRENCY_CAPS_JSON", raising=False)

    service.global_scrape_concurrency_cap = 2
    service.platform_default_concurrency_cap = 10
    service.platform_concurrency_caps = {}

    active = [
        {"code": f"book{i}", "scraping_config": {"scraper_class": "entain"}}
        for i in range(6)
    ]
    monkeypatch.setattr(service, "get_active_bookmakers_from_db", lambda: active)

    in_flight = 0
    observed_max = 0

    async def fake_scrape(bookmaker_code, sports=None, limit=None):
        nonlocal in_flight, observed_max
        in_flight += 1
        observed_max = max(observed_max, in_flight)
        await asyncio.sleep(0.02)
        in_flight -= 1
        return {
            "bookmaker": bookmaker_code,
            "success": True,
            "events_scraped": 1,
            "odds_scraped": 2,
            "odds_saved": 2,
            "errors": [],
        }

    monkeypatch.setattr(service, "scrape_bookmaker_all_sports", fake_scrape)
    result = await service.scrape_all_active_bookmakers(sport="all", limit=None)

    assert result["scheduler"]["global_cap"] == 2
    assert result["scheduler"]["observed_max_in_flight_global"] <= 2
    assert observed_max <= 2
    assert observed_max == 2


@pytest.mark.asyncio
async def test_per_platform_caps_are_respected(monkeypatch, service):
    monkeypatch.setenv("SCRAPE_GLOBAL_CONCURRENCY_CAP", "8")
    monkeypatch.setenv("SCRAPE_PLATFORM_CONCURRENCY_DEFAULT_CAP", "5")
    monkeypatch.setenv(
        "SCRAPE_PLATFORM_CONCURRENCY_CAPS_JSON",
        json.dumps({"entain": 1, "punterstech": 2}),
    )

    service.global_scrape_concurrency_cap = 8
    service.platform_default_concurrency_cap = 5
    service.platform_concurrency_caps = {"entain": 1, "punterstech": 2}

    active = [
        {"code": "ladbrokes", "scraping_config": {"scraper_class": "entain"}},
        {"code": "neds", "scraping_config": {"scraper_class": "entain"}},
        {"code": "sportsbet", "scraping_config": {"scraper_class": "entain"}},
        {"code": "mintbet", "scraping_config": {"scraper_class": "punterstech"}},
        {"code": "tradiebet", "scraping_config": {"scraper_class": "punterstech"}},
        {"code": "betblitz", "scraping_config": {"scraper_class": "punterstech"}},
    ]
    code_to_platform = {cfg["code"]: cfg["scraping_config"]["scraper_class"] for cfg in active}
    monkeypatch.setattr(service, "get_active_bookmakers_from_db", lambda: active)

    current_by_platform = {"entain": 0, "punterstech": 0}
    observed_by_platform = {"entain": 0, "punterstech": 0}

    async def fake_scrape(bookmaker_code, sports=None, limit=None):
        platform = code_to_platform[bookmaker_code]
        current_by_platform[platform] += 1
        observed_by_platform[platform] = max(
            observed_by_platform[platform],
            current_by_platform[platform],
        )
        await asyncio.sleep(0.03)
        current_by_platform[platform] -= 1
        return {
            "bookmaker": bookmaker_code,
            "success": True,
            "events_scraped": 1,
            "odds_scraped": 1,
            "odds_saved": 1,
            "errors": [],
        }

    monkeypatch.setattr(service, "scrape_bookmaker_all_sports", fake_scrape)
    result = await service.scrape_all_active_bookmakers(sport="all", limit=None)

    observed = result["scheduler"]["observed_max_in_flight_by_platform"]
    assert observed["entain"] <= 1
    assert observed["punterstech"] <= 2
    assert observed_by_platform["entain"] == 1
    assert observed_by_platform["punterstech"] == 2
    assert result["scheduler"]["platform_caps"]["entain"] == 1
    assert result["scheduler"]["platform_caps"]["punterstech"] == 2


@pytest.mark.asyncio
async def test_scheduler_failure_isolation(monkeypatch, service):
    service.global_scrape_concurrency_cap = 3
    service.platform_default_concurrency_cap = 3
    service.platform_concurrency_caps = {}

    active = [
        {"code": "ladbrokes", "scraping_config": {"scraper_class": "entain"}},
        {"code": "neds", "scraping_config": {"scraper_class": "entain"}},
        {"code": "mintbet", "scraping_config": {"scraper_class": "punterstech"}},
    ]
    monkeypatch.setattr(service, "get_active_bookmakers_from_db", lambda: active)

    async def fake_scrape(bookmaker_code, sports=None, limit=None):
        await asyncio.sleep(0.01)
        if bookmaker_code == "neds":
            raise RuntimeError("synthetic scrape failure")
        return {
            "bookmaker": bookmaker_code,
            "success": True,
            "events_scraped": 3,
            "odds_scraped": 9,
            "odds_saved": 9,
            "errors": [],
        }

    monkeypatch.setattr(service, "scrape_bookmaker_all_sports", fake_scrape)
    result = await service.scrape_all_active_bookmakers(sport="all", limit=None)

    by_code = {entry["bookmaker"]: entry for entry in result["results"]}
    assert by_code["ladbrokes"]["success"] is True
    assert by_code["mintbet"]["success"] is True
    assert by_code["neds"]["success"] is False
    assert "synthetic scrape failure" in by_code["neds"]["error"]
    assert result["bookmakers_scraped"] == 2
    assert result["total_bookmakers"] == 3


@pytest.mark.asyncio
async def test_scheduler_emits_observability_metrics(monkeypatch, service):
    service.global_scrape_concurrency_cap = 2
    service.platform_default_concurrency_cap = 2
    service.platform_concurrency_caps = {"entain": 1}
    service._bookmaker_platform_codes = {
        "ladbrokes": "entain",
        "neds": "entain",
    }

    active = [
        {"code": "ladbrokes", "scraping_config": {"scraper_class": "entain"}},
        {"code": "neds", "scraping_config": {"scraper_class": "entain"}},
    ]
    monkeypatch.setattr(service, "get_active_bookmakers_from_db", lambda: active)
    monkeypatch.setattr(
        service,
        "_get_breaker_state",
        lambda _code: {"state": "closed", "failures": 0, "opened_at": None},
    )

    async def fake_scrape(bookmaker_code, sports=None, limit=None):
        await asyncio.sleep(0.01)
        return {
            "bookmaker": bookmaker_code,
            "success": bookmaker_code == "ladbrokes",
            "events_scraped": 2,
            "odds_scraped": 4,
            "odds_saved": 4,
            "scrape_duration_seconds": 0.5 if bookmaker_code == "ladbrokes" else 0.8,
            "errors": [],
        }

    emitted = []

    def fake_emit(**kwargs):
        emitted.append(kwargs)
        return "1-1"

    monkeypatch.setattr(service, "scrape_bookmaker_all_sports", fake_scrape)
    monkeypatch.setattr(scrape_service_module, "emit_observability_event", fake_emit)

    await service.scrape_all_active_bookmakers(sport="all", limit=None)

    by_metric = {}
    for event in emitted:
        by_metric.setdefault(event["metric_name"], []).append(event)

    assert "scrape_scheduler_cycle" in by_metric
    assert "scrape_reliability_cycle" in by_metric
    assert "scrape_bookmaker_result" in by_metric

    scheduler_payload = by_metric["scrape_scheduler_cycle"][0]["payload"]
    assert "observed_max_in_flight_global" in scheduler_payload
    assert "observed_max_in_flight_by_platform" in scheduler_payload
    assert "configured_global_cap" in scheduler_payload
    assert "configured_platform_caps" in scheduler_payload

    reliability_payload = by_metric["scrape_reliability_cycle"][0]["payload"]
    assert reliability_payload["total_bookmakers"] == 2
    assert reliability_payload["success_count"] == 1
    assert reliability_payload["failure_count"] == 1
    assert reliability_payload["scrape_success_rate"] == 0.5


def test_resolve_active_bookmakers_filters_frozen_codes(monkeypatch):
    class _FakeService:
        @staticmethod
        def get_active_bookmakers_from_db():
            return [
                {"code": "ladbrokes"},
                {"code": "unibet"},
                {"code": "betfair"},
                {"code": "betfair"},
            ]

    monkeypatch.setattr(refresh_worker, "get_scrape_service", lambda: _FakeService())
    monkeypatch.setattr(refresh_worker, "is_bookmaker_frozen", lambda code: code == "unibet")

    resolved = refresh_worker._resolve_active_bookmakers()
    assert resolved == ["ladbrokes", "betfair"]
