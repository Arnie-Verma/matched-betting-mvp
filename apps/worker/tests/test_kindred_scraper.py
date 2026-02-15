"""
Unit tests for KindredScraper (Unibet AU) - Production readiness validation

Tests cover:
1. Initialization and configuration
2. Feed parsing (soccer/afl/nrl/basketball/ice_hockey/boxing)
3. Filtering (competition allowlist, esports, horizon)
4. Error handling (timeouts, bad structure)
5. Parallel scrape aggregation
"""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import os
import sys
from unittest.mock import patch, AsyncMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scrapers.kindred_scraper import KindredScraper
from scrapers.base import ScraperStatus, ScrapeResult


def _iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _make_outcome(
    outcome_type: str,
    odds_decimal: float | None = None,
    odds_scaled: int | None = None,
    status: str = "OPEN",
    participant: str | None = None,
) -> dict:
    outcome: dict = {"type": outcome_type, "status": status}
    if odds_decimal is not None:
        outcome["oddsDecimal"] = odds_decimal
    if odds_scaled is not None:
        outcome["odds"] = odds_scaled
    if participant is not None:
        outcome["participant"] = participant
    return outcome


def _make_offer(offer_id: int, criterion_label: str, outcomes: list[dict]) -> dict:
    return {
        "id": offer_id,
        "suspended": False,
        "criterion": {"englishLabel": criterion_label},
        "outcomes": outcomes,
    }


def _make_event_item(
    event_id: int,
    group: str,
    home: str,
    away: str,
    start_iso: str,
    *,
    state: str = "NOT_STARTED",
    path: list[dict] | None = None,
    main_offer: dict | None = None,
    offers: list[dict] | None = None,
) -> dict:
    return {
        "event": {
            "id": event_id,
            "group": group,
            "homeName": home,
            "awayName": away,
            "start": start_iso,
            "state": state,
            "path": path or [],
        },
        "mainBetOffer": main_offer,
        "betOffers": offers or [],
    }


def _make_feed(event_items: list[dict]) -> dict:
    return {
        "layout": {
            "sections": [
                {
                    "widgets": [
                        {
                            "matches": {
                                "groups": [
                                    {
                                        "name": "Root",
                                        "subGroups": [
                                            {
                                                "name": "Main",
                                                "events": event_items,
                                            }
                                        ],
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
    }


def _make_feed_events_list(event_items: list[dict]) -> dict:
    """Feed shape where matches.events is a list (common for tournament filters)."""
    return {
        "layout": {
            "sections": [
                {
                    "widgets": [
                        {
                            "matches": {
                                "events": event_items,
                            }
                        }
                    ]
                }
            ]
        }
    }


def _make_feed_highlighted_events(event_items: list[dict]) -> dict:
    """Feed shape where matches.highlightedEvents is a dict with events list."""
    return {
        "layout": {
            "sections": [
                {
                    "widgets": [
                        {
                            "matches": {
                                "highlightedEvents": {"events": event_items},
                            }
                        }
                    ]
                }
            ]
        }
    }


@pytest.fixture
def scraper() -> KindredScraper:
    return KindredScraper("unibet", "https://www.unibet.com.au/")


class TestKindredScraperInit:
    def test_init_normalizes_base_url(self):
        scraper = KindredScraper("unibet", "www.unibet.com.au/")
        assert scraper.base_url == "https://www.unibet.com.au"

    def test_all_sports_defined(self, scraper):
        assert scraper.ALL_SPORTS == ["soccer", "afl", "nrl", "basketball", "ice_hockey", "boxing"]

    def test_unsupported_sport_raises(self, scraper):
        with pytest.raises(ValueError):
            scraper._sport_feed_url("cricket")


class TestFeedParsing:
    def test_parse_soccer_match_result_1x2(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=24))

        partial = _make_offer(
            1,
            "1st Half Match Result",
            [
                _make_outcome("OT_ONE", odds_decimal=2.5, participant="Arsenal"),
                _make_outcome("OT_CROSS", odds_decimal=3.0),
                _make_outcome("OT_TWO", odds_decimal=2.8, participant="Chelsea"),
            ],
        )
        full_time = _make_offer(
            2,
            "Regular Time",
            [
                _make_outcome("OT_ONE", odds_decimal=2.10, participant="Arsenal"),
                _make_outcome("OT_CROSS", odds_decimal=3.50),
                _make_outcome("OT_TWO", odds_decimal=3.20, participant="Chelsea"),
            ],
        )

        data = _make_feed(
            [
                _make_event_item(
                    100,
                    "Premier League",
                    "Arsenal",
                    "Chelsea",
                    start,
                    path=[{"name": "Soccer"}, {"name": "England"}, {"name": "Premier League"}],
                    main_offer=partial,
                    offers=[full_time],
                )
            ]
        )

        events = scraper._parse_feed(data, "soccer")
        assert len(events) == 1

        event = events[0]
        assert event.sport == "soccer"
        assert event.competition == "English Premier League"
        assert {o.selection_key for o in event.odds} == {"home", "away", "draw"}
        assert all(o.market_name == "Match Result" for o in event.odds)

        by_key = {o.selection_key: o for o in event.odds}
        assert by_key["home"].decimal_odds == Decimal("2.10")
        assert by_key["draw"].decimal_odds == Decimal("3.50")
        assert by_key["away"].decimal_odds == Decimal("3.20")

    def test_parse_events_list_shape(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=24))
        offer = _make_offer(
            99,
            "Regular Time",
            [
                _make_outcome("OT_ONE", odds_decimal=2.10, participant="Arsenal"),
                _make_outcome("OT_CROSS", odds_decimal=3.50),
                _make_outcome("OT_TWO", odds_decimal=3.20, participant="Chelsea"),
            ],
        )

        data = _make_feed_events_list(
            [
                _make_event_item(
                    101,
                    "Premier League",
                    "Arsenal",
                    "Chelsea",
                    start,
                    path=[{"name": "Soccer"}, {"name": "England"}, {"name": "Premier League"}],
                    main_offer=offer,
                )
            ]
        )
        events = scraper._parse_feed(data, "soccer")
        assert len(events) == 1

    def test_parse_highlighted_events_shape(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=24))
        offer = _make_offer(
            199,
            "Regular Time",
            [
                _make_outcome("OT_ONE", odds_decimal=2.10, participant="Arsenal"),
                _make_outcome("OT_CROSS", odds_decimal=3.50),
                _make_outcome("OT_TWO", odds_decimal=3.20, participant="Chelsea"),
            ],
        )
        data = _make_feed_highlighted_events(
            [
                _make_event_item(
                    102,
                    "Premier League",
                    "Arsenal",
                    "Chelsea",
                    start,
                    path=[{"name": "Soccer"}, {"name": "England"}, {"name": "Premier League"}],
                    main_offer=offer,
                )
            ]
        )
        events = scraper._parse_feed(data, "soccer")
        assert len(events) == 1

    def test_parse_basketball_moneyline_excludes_partial(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=6))

        partial = _make_offer(
            10,
            "1st Half Moneyline",
            [
                _make_outcome("OT_ONE", odds_decimal=1.50, participant="Lakers"),
                _make_outcome("OT_TWO", odds_decimal=2.60, participant="Celtics"),
            ],
        )
        full_game = _make_offer(
            11,
            "Moneyline - Including Overtime",
            [
                _make_outcome("OT_ONE", odds_decimal=1.80, participant="Lakers"),
                _make_outcome("OT_TWO", odds_decimal=2.00, participant="Celtics"),
            ],
        )

        data = _make_feed(
            [
                _make_event_item(
                    200,
                    "NBA",
                    "LA Lakers",
                    "Boston Celtics",
                    start,
                    main_offer=partial,
                    offers=[full_game],
                )
            ]
        )

        events = scraper._parse_feed(data, "basketball")
        assert len(events) == 1
        event = events[0]
        assert all(o.market_name == "Money Line" for o in event.odds)
        assert {o.selection_key for o in event.odds} == {"home", "away"}

        by_key = {o.selection_key: o for o in event.odds}
        assert by_key["home"].decimal_odds == Decimal("1.80")
        assert by_key["away"].decimal_odds == Decimal("2.00")

    @pytest.mark.asyncio
    async def test_parse_ice_hockey_moneyline_via_kambi(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=12))

        match_odds = _make_offer(
            21,
            "Match Odds - Regular Time",
            [
                _make_outcome("OT_ONE", odds_decimal=2.40, participant="New York Rangers"),
                _make_outcome("OT_CROSS", odds_decimal=4.00),
                _make_outcome("OT_TWO", odds_decimal=2.60, participant="Boston Bruins"),
            ],
        )

        data = _make_feed(
            [
                _make_event_item(
                    300,
                    "NHL",
                    "New York Rangers",
                    "Boston Bruins",
                    start,
                    main_offer=match_odds,
                    offers=[],
                )
            ]
        )

        kambi_payload = {
            "betOffers": [
                _make_offer(
                    22,
                    "Moneyline - Including Overtime",
                    [
                        _make_outcome("OT_ONE", odds_decimal=1.90, participant="New York Rangers"),
                        _make_outcome("OT_TWO", odds_decimal=1.95, participant="Boston Bruins"),
                    ],
                )
            ]
        }

        mock_request = AsyncMock(return_value=kambi_payload)
        with patch.object(scraper, "_request_json", new=mock_request):
            events = await scraper._parse_feed_async(data, "ice_hockey")

        assert len(events) == 1
        event = events[0]
        assert all(o.market_name == "Moneyline" for o in event.odds)
        assert {o.selection_key for o in event.odds} == {"home", "away"}

        by_key = {o.selection_key: o for o in event.odds}
        assert by_key["home"].decimal_odds == Decimal("1.90")
        assert by_key["away"].decimal_odds == Decimal("1.95")

        assert mock_request.await_count == 1
        called_url = mock_request.await_args.args[0]
        assert "/betoffer/event/300.json" in called_url

    def test_parse_afl_match_winner(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=8))
        offer = _make_offer(
            30,
            "Including Overtime",
            [
                _make_outcome("OT_ONE", odds_decimal=1.70, participant="Geelong"),
                _make_outcome("OT_TWO", odds_decimal=2.20, participant="Carlton"),
            ],
        )

        data = _make_feed([_make_event_item(400, "AFL", "Geelong", "Carlton", start, main_offer=offer)])
        events = scraper._parse_feed(data, "afl")
        assert len(events) == 1
        event = events[0]
        assert all(o.market_name == "Match Winner" for o in event.odds)
        assert {o.selection_key for o in event.odds} == {"home", "away"}

    def test_parse_nrl_match_winner(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=10))
        offer = _make_offer(
            40,
            "Including Overtime",
            [
                _make_outcome("OT_ONE", odds_decimal=1.55, participant="Storm"),
                _make_outcome("OT_TWO", odds_decimal=2.55, participant="Eels"),
            ],
        )
        data = _make_feed([_make_event_item(500, "NRL", "Melbourne Storm", "Parramatta Eels", start, main_offer=offer)])
        events = scraper._parse_feed(data, "nrl")
        assert len(events) == 1
        event = events[0]
        assert all(o.market_name == "Match Winner" for o in event.odds)
        assert {o.selection_key for o in event.odds} == {"home", "away"}

    def test_parse_boxing_supports_draw_and_scaled_odds(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=4))
        offer = _make_offer(
            50,
            "Bout Odds",
            [
                _make_outcome("OT_ONE", odds_decimal=1.60, participant="Fighter A"),
                _make_outcome("OT_CROSS", odds_scaled=21000),
                _make_outcome("OT_TWO", odds_decimal=2.50, participant="Fighter B"),
            ],
        )
        data = _make_feed([_make_event_item(600, "Upcoming Fights", "Fighter A", "Fighter B", start, main_offer=offer)])
        events = scraper._parse_feed(data, "boxing")
        assert len(events) == 1
        event = events[0]
        assert all(o.market_name == "Fight Betting" for o in event.odds)
        assert {o.selection_key for o in event.odds} == {"home", "away", "draw"}

        by_key = {o.selection_key: o for o in event.odds}
        assert by_key["draw"].decimal_odds == Decimal("21.00")


class TestFiltering:
    def test_competition_allowlist_filters_unknown_league(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=24))
        offer = _make_offer(
            1,
            "Regular Time",
            [
                _make_outcome("OT_ONE", odds_decimal=2.10, participant="Team A"),
                _make_outcome("OT_CROSS", odds_decimal=3.50),
                _make_outcome("OT_TWO", odds_decimal=3.20, participant="Team B"),
            ],
        )
        data = _make_feed([_make_event_item(700, "Scottish Premiership", "Team A", "Team B", start, main_offer=offer)])
        assert scraper._parse_feed(data, "soccer") == []

    def test_esports_filtered(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=24))
        offer = _make_offer(
            1,
            "Regular Time",
            [
                _make_outcome("OT_ONE", odds_decimal=2.10),
                _make_outcome("OT_CROSS", odds_decimal=3.50),
                _make_outcome("OT_TWO", odds_decimal=3.20),
            ],
        )
        data = _make_feed(
            [
                _make_event_item(
                    800,
                    "Premier League",
                    "Team A",
                    "Team B",
                    start,
                    path=[{"name": "Esports"}],
                    main_offer=offer,
                )
            ]
        )
        assert scraper._parse_feed(data, "soccer") == []

    def test_horizon_filters_far_future(self, scraper):
        start = _iso_z(datetime.now(timezone.utc) + timedelta(days=30))
        offer = _make_offer(
            1,
            "Regular Time",
            [
                _make_outcome("OT_ONE", odds_decimal=2.10, participant="Team A"),
                _make_outcome("OT_CROSS", odds_decimal=3.50),
                _make_outcome("OT_TWO", odds_decimal=3.20, participant="Team B"),
            ],
        )
        data = _make_feed([_make_event_item(900, "Premier League", "Team A", "Team B", start, main_offer=offer)])
        assert scraper._parse_feed(data, "soccer") == []


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_timeout_returns_failed_or_partial(self, scraper):
        with patch.object(scraper, "_request_json", new=AsyncMock(side_effect=asyncio.TimeoutError("timeout"))):
            result = await scraper.scrape_sport("soccer", limit=10)
            assert result.status in {ScraperStatus.FAILED, ScraperStatus.PARTIAL}
            assert result.errors


class TestFeedUrlRegression:
    @pytest.mark.asyncio
    async def test_basketball_scrape_uses_nested_nbl_filter_path(self, scraper):
        called_urls: list[str] = []
        start = _iso_z(datetime.now(timezone.utc) + timedelta(hours=12))

        feed = _make_feed(
            [
                _make_event_item(
                    9901,
                    "NBL",
                    "Melbourne United",
                    "Sydney Kings",
                    start,
                    main_offer=_make_offer(
                        9902,
                        "Moneyline - Including Overtime",
                        [
                            _make_outcome("OT_ONE", odds_decimal=1.85, participant="Melbourne United"),
                            _make_outcome("OT_TWO", odds_decimal=1.95, participant="Sydney Kings"),
                        ],
                    ),
                )
            ]
        )

        async def fake_request(url: str):
            called_urls.append(url)
            return feed

        with patch.object(scraper, "_request_json", new=AsyncMock(side_effect=fake_request)):
            result = await scraper.scrape_sport("basketball")

        assert result.events_scraped >= 1
        assert any(
            "views/filter/basketball/australia/nbl/matches" in url
            for url in called_urls
        )


class TestParallelScrapeAggregation:
    @pytest.mark.asyncio
    async def test_scrape_all_sports_parallel_aggregates_results(self, scraper):
        now = datetime.now(timezone.utc)
        soccer_result = ScrapeResult(
            bookmaker_code="unibet",
            status=ScraperStatus.SUCCESS,
            events_scraped=1,
            odds_scraped=3,
            events=[],
            errors=[],
            started_at=now,
            completed_at=now,
        )
        basketball_result = ScrapeResult(
            bookmaker_code="unibet",
            status=ScraperStatus.SUCCESS,
            events_scraped=2,
            odds_scraped=4,
            events=[],
            errors=[],
            started_at=now,
            completed_at=now,
        )

        with patch.object(
            scraper,
            "scrape_sport",
            new=AsyncMock(side_effect=[soccer_result, basketball_result]),
        ):
            combined = await scraper.scrape_all_sports_parallel(
                sports=["soccer", "basketball"],
                batch_size=2,
            )
            assert combined.status == ScraperStatus.SUCCESS
            assert combined.events_scraped == 3
            assert combined.odds_scraped == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
