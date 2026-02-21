"""
Generate reproducible PR-R2 bounded concurrency synthetic metrics.

Writes:
  docs/evidence/phase-a-hardening/2026-02-11/pr10_bounded_concurrency_metrics.json
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from typing import Dict, Any


DEFAULT_OUTPUT = "docs/evidence/phase-a-hardening/2026-02-11/pr10_bounded_concurrency_metrics.json"


def _bootstrap_paths() -> None:
    root = os.getcwd()
    sys.path.insert(0, os.path.join(root, "apps/api/src"))
    sys.path.insert(0, os.path.join(root, "apps/worker/src"))


class DummyScraper:
    def __init__(self, *args, **kwargs):
        pass


class DummyRedis:
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


ACTIVE_CONFIGS = [
    {"code": "ladbrokes", "scraping_config": {"scraper_class": "entain"}},
    {"code": "neds", "scraping_config": {"scraper_class": "entain"}},
    {"code": "sportsbet", "scraping_config": {"scraper_class": "entain"}},
    {"code": "mintbet", "scraping_config": {"scraper_class": "punterstech"}},
    {"code": "tradiebet", "scraping_config": {"scraper_class": "punterstech"}},
    {"code": "betblitz", "scraping_config": {"scraper_class": "punterstech"}},
]
PLATFORM_BY_CODE = {
    cfg["code"]: cfg["scraping_config"]["scraper_class"]
    for cfg in ACTIVE_CONFIGS
}


async def run_unbounded_before() -> Dict[str, Any]:
    current_global = 0
    max_global = 0
    current_by_platform = {"entain": 0, "punterstech": 0}
    max_by_platform = {"entain": 0, "punterstech": 0}

    async def task(code: str) -> Dict[str, Any]:
        nonlocal current_global, max_global
        platform = PLATFORM_BY_CODE[code]
        current_global += 1
        current_by_platform[platform] += 1
        max_global = max(max_global, current_global)
        max_by_platform[platform] = max(max_by_platform[platform], current_by_platform[platform])
        try:
            await asyncio.sleep(0.02)
            if code == "mintbet":
                raise RuntimeError("synthetic scrape failure")
            return {"bookmaker": code, "success": True}
        finally:
            current_global -= 1
            current_by_platform[platform] -= 1

    started = time.perf_counter()
    results = await asyncio.gather(*(task(cfg["code"]) for cfg in ACTIVE_CONFIGS), return_exceptions=True)
    duration = time.perf_counter() - started

    success = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    failed = sum(1 for r in results if isinstance(r, Exception) or (isinstance(r, dict) and not r.get("success")))
    return {
        "execution_model": "unbounded_gather_all_bookmakers",
        "duration_seconds": round(duration, 4),
        "observed_max_in_flight_global": max_global,
        "observed_max_in_flight_by_platform": max_by_platform,
        "success_count": success,
        "failed_count": failed,
    }


async def run_bounded_after() -> Dict[str, Any]:
    from jobs import scrape_service as scrape_service_module

    logging.getLogger("jobs.scrape_service").setLevel(logging.CRITICAL)

    scrape_service_module.BetfairScraper = DummyScraper
    scrape_service_module.EntainScraper = DummyScraper
    scrape_service_module.redis.from_url = lambda *args, **kwargs: DummyRedis()

    service = scrape_service_module.ScrapeService()
    service.global_scrape_concurrency_cap = 3
    service.platform_default_concurrency_cap = 2
    service.platform_concurrency_caps = {"entain": 1, "punterstech": 2}
    service.validation_enabled = False

    service.get_active_bookmakers_from_db = lambda: ACTIVE_CONFIGS
    service.get_scraper_for_bookmaker = lambda *args, **kwargs: object()
    service._run_post_scrape_cleanup = lambda: {"skipped": True}

    async def fake_scrape(bookmaker_code, sports=None, limit=None):
        await asyncio.sleep(0.02)
        if bookmaker_code == "mintbet":
            raise RuntimeError("synthetic scrape failure")
        return {
            "bookmaker": bookmaker_code,
            "success": True,
            "events_scraped": 1,
            "odds_scraped": 2,
            "odds_saved": 2,
            "errors": [],
        }

    service.scrape_bookmaker_all_sports = fake_scrape

    started = time.perf_counter()
    result = await service.scrape_all_active_bookmakers(sport="all", limit=None)
    duration = time.perf_counter() - started

    failed = sum(1 for row in result.get("results", []) if not row.get("success"))
    return {
        "execution_model": "bounded_worker_pool_with_platform_caps",
        "duration_seconds": round(duration, 4),
        "cap_settings": {
            "global_cap": service.global_scrape_concurrency_cap,
            "platform_default_cap": service.platform_default_concurrency_cap,
            "platform_caps": service.platform_concurrency_caps,
        },
        "observed_max_in_flight_global": result.get("scheduler", {}).get("observed_max_in_flight_global"),
        "observed_max_in_flight_by_platform": result.get("scheduler", {}).get("observed_max_in_flight_by_platform"),
        "success_count": result.get("bookmakers_scraped"),
        "failed_count": failed,
        "isolation_non_fatal": result.get("bookmakers_scraped") == 5 and failed == 1,
    }


async def build_payload() -> Dict[str, Any]:
    before = await run_unbounded_before()
    after = await run_bounded_after()
    return {
        "slice": "PR-R2",
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenario": "6 bookmakers synthetic fan-out with one bookmaker failure",
        "before": before,
        "after": after,
        "comparison": {
            "global_in_flight_reduction": before["observed_max_in_flight_global"] - after["observed_max_in_flight_global"],
            "entain_in_flight_reduction": before["observed_max_in_flight_by_platform"]["entain"] - after["observed_max_in_flight_by_platform"].get("entain", 0),
            "punterstech_in_flight_reduction": before["observed_max_in_flight_by_platform"]["punterstech"] - after["observed_max_in_flight_by_platform"].get("punterstech", 0),
            "failure_isolation_maintained": after["isolation_non_fatal"],
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate PR-R2 bounded concurrency synthetic metrics.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _bootstrap_paths()
    payload = asyncio.run(build_payload())
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


if __name__ == "__main__":
    main()
