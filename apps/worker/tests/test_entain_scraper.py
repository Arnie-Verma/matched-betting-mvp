"""
Unit tests for EntainScraper parity contract.

Covers:
1. Parsing behavior
2. Market allow/deny policy
3. 2-way / 3-way market-shape enforcement
4. selection_key stability
5. Error handling
"""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from scrapers.base import ScrapedEvent, ScraperStatus
from scrapers.entain_scraper import EntainScraper


class TestEntainScraperInit:
    """Test scraper initialization and static config."""

    def test_init_ladbrokes(self):
        scraper = EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")
        assert scraper.bookmaker_code == "ladbrokes"
        assert scraper.base_url == "https://www.ladbrokes.com.au"

    def test_init_neds(self):
        scraper = EntainScraper("neds", "https://www.neds.com.au")
        assert scraper.bookmaker_code == "neds"
        assert scraper.base_url == "https://www.neds.com.au"

    def test_supported_sports_defined(self):
        scraper = EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")
        for sport in ["soccer", "basketball", "ice_hockey", "boxing"]:
            assert sport in scraper.ALL_SPORTS


class TestMarketAllowDeny:
    """Regression tests for market hygiene policy."""

    @pytest.fixture
    def scraper(self):
        return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

    @pytest.mark.parametrize(
        "sport,market_name,expected",
        [
            ("soccer", "Match Result", True),
            ("soccer", "1st Half Match Result", False),
            ("soccer", "Double Chance", False),
            ("basketball", "Money Line", True),
            ("basketball", "2nd Quarter Money Line", False),
            ("basketball", "NBA Championship Winner", False),
            ("ice_hockey", "Head To Head", True),
            ("ice_hockey", "Team To Make Playoffs", False),
            ("boxing", "Fight Result", True),
            ("boxing", "Fight Winner By Decision", False),
        ],
    )
    def test_market_allow_deny_by_sport(self, scraper, sport, market_name, expected):
        assert scraper._is_matcher_market(market_name, sport) is expected


class TestParsingContract:
    """Parsing contract tests for Entain APIs."""

    @pytest.fixture
    def scraper(self):
        return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

    def test_parse_rest_soccer_requires_three_way_market_shape(self, scraper):
        data = {
            "events": {
                "evt-1": {
                    "name": "Arsenal v Chelsea",
                    "competition": {"name": "Premier League"},
                    "advertised_start": "2026-02-15T10:00:00Z",
                }
            },
            "markets": {
                "m1": {"name": "Match Result", "event_id": "evt-1", "entrant_ids": ["e1", "e2"]},
            },
            "entrants": {
                "e1": {"name": "Arsenal"},
                "e2": {"name": "Chelsea"},
            },
            "prices": {
                "e1:m1": {"odds": {"numerator": 11, "denominator": 10}},
                "e2:m1": {"odds": {"numerator": 12, "denominator": 5}},
            },
        }

        events = scraper._parse_entain_response(data, "soccer")
        assert events == []

    def test_parse_rest_soccer_accepts_three_way_market_shape(self, scraper):
        data = {
            "events": {
                "evt-2": {
                    "name": "Arsenal v Chelsea",
                    "competition": {"name": "Premier League"},
                    "advertised_start": "2026-02-15T10:00:00Z",
                }
            },
            "markets": {
                "m1": {"name": "Match Result", "event_id": "evt-2", "entrant_ids": ["e1", "e2", "e3"]},
            },
            "entrants": {
                "e1": {"name": "Arsenal"},
                "e2": {"name": "Draw"},
                "e3": {"name": "Chelsea"},
            },
            "prices": {
                "e1:m1": {"odds": {"numerator": 11, "denominator": 10}},
                "e2:m1": {"odds": {"numerator": 5, "denominator": 2}},
                "e3:m1": {"odds": {"numerator": 12, "denominator": 5}},
            },
        }

        events = scraper._parse_entain_response(data, "soccer")
        assert len(events) == 1
        keys = {o.selection_key for o in events[0].odds}
        assert keys == {"home", "away", "draw"}
        assert all(o.market_type == "match_winner" for o in events[0].odds)

    def test_parse_rest_basketball_enforces_two_way_shape_and_drops_disallowed_markets(self, scraper):
        data = {
            "events": {
                "evt-3": {
                    "name": "Los Angeles Lakers v Boston Celtics",
                    "competition": {"name": "NBA"},
                    "advertised_start": "2026-02-15T10:00:00Z",
                }
            },
            "markets": {
                "good": {"name": "Money Line", "event_id": "evt-3", "entrant_ids": ["e1", "e2"]},
                "partial": {"name": "1st Half Money Line", "event_id": "evt-3", "entrant_ids": ["e1", "e2"]},
                "future": {"name": "NBA Championship Winner", "event_id": "evt-3", "entrant_ids": ["e1", "e2"]},
            },
            "entrants": {
                "e1": {"name": "Los Angeles Lakers"},
                "e2": {"name": "Boston Celtics"},
            },
            "prices": {
                "e1:good": {"odds": {"numerator": 5, "denominator": 4}},
                "e2:good": {"odds": {"numerator": 4, "denominator": 5}},
                "e1:partial": {"odds": {"numerator": 5, "denominator": 4}},
                "e2:partial": {"odds": {"numerator": 4, "denominator": 5}},
                "e1:future": {"odds": {"numerator": 5, "denominator": 4}},
                "e2:future": {"odds": {"numerator": 4, "denominator": 5}},
            },
        }

        events = scraper._parse_entain_response(data, "basketball")
        assert len(events) == 1
        assert {o.market_name for o in events[0].odds} == {"Money Line"}
        assert {o.selection_key for o in events[0].odds} == {"home", "away"}

    def test_parse_graphql_nhl_enforces_two_way_shape(self, scraper):
        gql_data = {
            "data": {
                "events": {
                    "edges": [
                        {
                            "node": {
                                "id": "evt-gql-1",
                                "name": "New York Rangers v Toronto Maple Leafs",
                                "competition": {"name": "NHL"},
                                "startTime": "2026-02-20T10:00:00Z",
                                "markets": [
                                    {
                                        "name": "Money Line",
                                        "selections": [
                                            {"name": "New York Rangers", "decimalOdds": 2.25},
                                            {"name": "Toronto Maple Leafs", "decimalOdds": 1.72},
                                        ],
                                    }
                                ],
                            }
                        }
                    ]
                }
            }
        }

        events = scraper._parse_graphql_response(gql_data, "ice_hockey")
        assert len(events) == 1
        keys = {o.selection_key for o in events[0].odds}
        assert keys == {"home", "away"}
        assert all(o.market_type == "match_winner" for o in events[0].odds)

    def test_parse_rest_boxing_enforces_deterministic_participant_order(self, scraper):
        data = {
            "events": {
                "evt-box-1": {
                    "name": "Zander Zane v Aaron Abel",
                    "competition": {"name": "Upcoming Fights"},
                    "advertised_start": "2026-02-20T10:00:00Z",
                }
            },
            "markets": {
                "m1": {"name": "Fight Result", "event_id": "evt-box-1", "entrant_ids": ["e1", "e2"]},
            },
            "entrants": {
                "e1": {"name": "Zander Zane"},
                "e2": {"name": "Aaron Abel"},
            },
            "prices": {
                "e1:m1": {"odds": {"numerator": 11, "denominator": 10}},
                "e2:m1": {"odds": {"numerator": 13, "denominator": 10}},
            },
        }

        events = scraper._parse_entain_response(data, "boxing")
        assert len(events) == 1
        assert events[0].home_team == "Aaron Abel"
        assert events[0].away_team == "Zander Zane"
        assert events[0].name == "Aaron Abel v Zander Zane"

        by_key = {o.selection_key: o.selection_name for o in events[0].odds}
        assert by_key["home"] == "Aaron Abel"
        assert by_key["away"] == "Zander Zane"


class TestSelectionKeyStability:
    """Selection key mapping should be deterministic."""

    @pytest.fixture
    def scraper(self):
        return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

    @pytest.mark.parametrize(
        "selection_name,event_name,expected_key",
        [
            ("Tottenham", "Tottenham Hotspur v Manchester Utd", "home"),
            ("Man United", "Tottenham Hotspur v Manchester Utd", "away"),
            ("The Draw", "Arsenal v Chelsea", "draw"),
            ("Unknown Selection", "Arsenal v Chelsea", "other"),
        ],
    )
    def test_selection_key_stability(self, scraper, selection_name, event_name, expected_key):
        home_team, away_team = scraper._extract_teams_from_name(event_name)
        event = ScrapedEvent(
            external_id="evt",
            name=event_name,
            sport="soccer",
            competition="test",
            start_time=datetime.now(timezone.utc) + timedelta(hours=24),
            home_team=home_team,
            away_team=away_team,
            odds=[],
        )
        assert scraper._get_selection_key(selection_name, event) == expected_key


class TestErrorHandling:
    """Error handling contract for scrape entrypoints/helpers."""

    @pytest.fixture
    def scraper(self):
        return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

    @pytest.mark.asyncio
    async def test_scrape_sport_unsupported_sport_returns_failed(self, scraper):
        result = await scraper.scrape_sport("volleyball")
        assert result.status == ScraperStatus.FAILED
        assert result.events_scraped == 0
        assert result.odds_scraped == 0
        assert result.errors
        assert "Unsupported sport" in result.errors[0]

    @pytest.mark.asyncio
    async def test_scrape_sport_browser_failure_returns_failed(self, scraper):
        with patch.object(scraper, "_get_or_create_browser", new=AsyncMock(side_effect=RuntimeError("browser down"))):
            result = await scraper.scrape_sport("soccer")

        assert result.status == ScraperStatus.FAILED
        assert result.events_scraped == 0
        assert result.odds_scraped == 0
        assert any("browser down" in e for e in result.errors)

    def test_create_failed_result_helper(self, scraper):
        started_at = datetime.now(timezone.utc)
        errors = ["boom"]
        result = scraper._create_failed_result(started_at, errors)
        assert result.status == ScraperStatus.FAILED
        assert result.events_scraped == 0
        assert result.odds_scraped == 0
        assert result.errors == errors


class TestResponseListenerLifecycle:
    """Ensure per-competition response handlers are detached."""

    @pytest.fixture
    def scraper(self):
        return EntainScraper("ladbrokes", "https://www.ladbrokes.com.au")

    def test_detach_response_listener_prefers_remove_listener(self, scraper):
        calls = []

        class _Page:
            def remove_listener(self, event, listener):
                calls.append((event, listener))

        listener = object()
        scraper._detach_response_listener(_Page(), listener)

        assert calls == [("response", listener)]

    def test_detach_response_listener_falls_back_to_off(self, scraper):
        calls = []

        class _Page:
            def off(self, event, listener):
                calls.append((event, listener))

        listener = object()
        scraper._detach_response_listener(_Page(), listener)

        assert calls == [("response", listener)]
