"""
Kindred/FDJ (Unibet AU) scraper.

Unibet exposes a public JSON feed for upcoming matches by sport:

  GET /sportsbook-feeds/views/filter/{sport}/all/matches?includeParticipants=true&useCombined=true

This payload contains:
- events (with start time + participants)
- betOffers (markets) with outcomes that include decimal odds

Design goals (production):
- Direct HTTP (no Playwright) for speed and reliability
- Config-driven (BaseScraper signature) for dynamic registry support
- Strict market selection to avoid cross-market mismatches in odds matcher
"""

import asyncio
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Iterable, Tuple
from urllib.parse import urlparse

import httpx

from .base import BaseScraper, ScrapeResult, ScrapedEvent, ScrapedOdds, ScraperStatus

logger = logging.getLogger(__name__)


KINDRED_SPORT_SLUGS: Dict[str, str] = {
    # Internal -> Unibet filter slug
    "soccer": "football",
    "basketball": "basketball",
    # NOTE: Unibet uses underscore slugs for these:
    "ice_hockey": "ice_hockey",
    "afl": "australian_rules",
    "nrl": "rugby_league",
    "boxing": "boxing",
}

KINDRED_COMPETITION_FILTERS: Dict[str, List[Tuple[str, str]]] = {
    # sport -> list of (competition_code, filter_path) used in /views/filter/{filter_path}/matches
    #
    # We intentionally scrape competition filters (not sport/all) because Unibet's
    # sport "all matches" view is a small subset and misses most fixtures.
    "soccer": [
        ("epl", "football/england/premier_league"),
        ("aleague", "football/australia/a-league"),
        ("ligue1", "football/france/ligue_1"),
        ("bundesliga", "football/germany/bundesliga"),
        ("seriea", "football/italy/serie_a"),
        ("mls", "football/usa/mls"),
        ("laliga", "football/spain/la_liga"),
        # Note: Unibet AU uses a direct filter slug (not nested under UEFA).
        ("ucl", "football/champions_league"),
    ],
    "basketball": [
        ("nba", "basketball/nba"),
        ("nbl", "basketball/australia/nbl"),
    ],
    "ice_hockey": [
        ("nhl", "ice_hockey/nhl"),
    ],
    "afl": [
        ("afl", "australian_rules/afl"),
    ],
    "nrl": [
        ("nrl", "rugby_league/nrl"),
    ],
    "boxing": [
        ("boxing", "boxing/all"),
    ],
}

KINDRED_WEB_SPORT_SLUGS: Dict[str, str] = {
    # Best-effort for source_url (not used for scraping).
    "soccer": "football",
    "basketball": "basketball",
    "ice_hockey": "ice-hockey",
    "afl": "australian-rules",
    "nrl": "rugby-league",
    "boxing": "boxing",
}

KAMBI_OFFERING_BASE_URL = "https://oc-offering-api.kambicdn.com/offering/v2018/ubau"
KAMBI_OFFERING_QUERY = "lang=en_AU&market=AU&channel_id=1"


COMPETITION_CODE_MAP: Dict[str, str] = {
    # Soccer
    "premier league": "epl",
    "english premier league": "epl",
    "england premier league": "epl",
    "epl": "epl",
    "a-league": "aleague",
    "a league": "aleague",
    "a-league men": "aleague",
    "australia a-league": "aleague",
    "la liga": "laliga",
    "spanish la liga": "laliga",
    "spain la liga": "laliga",
    "bundesliga": "bundesliga",
    "german bundesliga": "bundesliga",
    "germany bundesliga": "bundesliga",
    "serie a": "seriea",
    "italian serie a": "seriea",
    "italy serie a": "seriea",
    "ligue 1": "ligue1",
    "french ligue 1": "ligue1",
    "france ligue 1": "ligue1",
    "uefa champions league": "ucl",
    "champions league": "ucl",
    "major league soccer": "mls",
    "mls": "mls",
    # AFL / NRL
    "afl": "afl",
    "nrl": "nrl",
    # Basketball
    "nba": "nba",
    "nbl": "nbl",
    "australia nbl": "nbl",
    # Ice hockey
    "nhl": "nhl",
    # Boxing
    "boxing": "boxing",
    "upcoming fights": "boxing",
}

COMPETITION_CANONICAL_NAME: Dict[str, str] = {
    "epl": "English Premier League",
    "aleague": "A-League",
    "laliga": "Spanish La Liga",
    "bundesliga": "German Bundesliga",
    "seriea": "Italian Serie A",
    "ligue1": "French Ligue 1",
    "ucl": "UEFA Champions League",
    "mls": "Major League Soccer",
    "afl": "AFL",
    "nrl": "NRL",
    "nba": "NBA",
    "nbl": "NBL",
    "nhl": "NHL",
    "boxing": "Boxing",
}

ALLOWED_COMPETITIONS_BY_SPORT: Dict[str, set[str]] = {
    "soccer": {"epl", "aleague", "ligue1", "bundesliga", "seriea", "mls", "laliga", "ucl"},
    "afl": {"afl"},
    "nrl": {"nrl"},
    "basketball": {"nba", "nbl"},
    "ice_hockey": {"nhl"},
    "boxing": {"boxing"},
}

MARKET_NAME_BY_SPORT: Dict[str, str] = {
    "soccer": "Match Result",
    "afl": "Match Winner",
    "nrl": "Match Winner",
    "basketball": "Money Line",
    # NHL requires the 2-way moneyline market (incl. OT/SO) to match other books.
    "ice_hockey": "Moneyline",
    "boxing": "Fight Betting",
}

DISALLOWED_CRITERION_TOKENS = (
    "1st half",
    "first half",
    "2nd half",
    "second half",
    "1st quarter",
    "first quarter",
    "2nd quarter",
    "second quarter",
    "3rd quarter",
    "third quarter",
    "4th quarter",
    "fourth quarter",
    "period",
    "set",
    "map",
    "innings",
)


@dataclass(frozen=True)
class _ParsedEventItem:
    event_id: str
    name: str
    start_time: datetime
    competition_code: str
    competition_name: str
    home_team: str
    away_team: str
    bet_offers: List[Dict[str, Any]]


class KindredScraper(BaseScraper):
    """
    Kindred platform scraper (Unibet AU).

    Intended usage (dynamic registry):
        KindredScraper("unibet", "https://www.unibet.com.au", config)
    """

    ALL_SPORTS = ["soccer", "afl", "nrl", "basketball", "ice_hockey", "boxing"]

    def __init__(
        self,
        bookmaker_code: str,
        base_url: str,
        config: Optional[Dict[str, Any]] = None,
    ):
        parsed = urlparse(base_url)
        scheme = parsed.scheme or "https"
        netloc = (parsed.netloc or parsed.path).strip("/")
        normalized_base = f"{scheme}://{netloc}".rstrip("/")

        super().__init__(
            bookmaker_code=bookmaker_code,
            base_url=normalized_base,
            config=config or {},
        )

        self.api_headers = {
            "Accept": "application/json",
            "User-Agent": self.headers.get("User-Agent", "Mozilla/5.0"),
        }

        self._http_client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()
        self._request_semaphore = asyncio.Semaphore(int(self.config.get("max_concurrent_requests", 4)))

        # Scrape horizon: keep aligned with odds matcher (next 14 days) to avoid DB bloat.
        self.horizon_days = int(self.config.get("horizon_days", 14))

        self.logger.info(f"[{self.bookmaker_code}] Initialized KindredScraper with base_url: {self.base_url}")

    async def _get_http_client(self) -> httpx.AsyncClient:
        async with self._client_lock:
            if self._http_client is None or self._http_client.is_closed:
                self._http_client = httpx.AsyncClient(
                    headers=self.api_headers.copy(),
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                )
        return self._http_client

    async def _request_json(self, url: str) -> Dict[str, Any]:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                client = await self._get_http_client()
                async with self._request_semaphore:
                    resp = await client.get(url)
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))
                else:
                    raise
        raise last_exc if last_exc else RuntimeError("Request failed without exception")

    def _participant_sort_key(self, name: str) -> str:
        """
        Stable, cross-bookmaker sort key for participant names.

        Boxing has no true home/away; different bookmakers can flip fighter order.
        We enforce deterministic ordering so selection_key (home/away) remains
        consistent for validation and matching.
        """
        if not name:
            return ""
        norm = name.strip().lower()
        norm = unicodedata.normalize("NFKD", norm).encode("ascii", "ignore").decode("ascii")
        norm = re.sub(r"[^a-z0-9]+", "", norm)
        return norm

    def _kambi_betoffer_url(self, event_id: str) -> str:
        return f"{KAMBI_OFFERING_BASE_URL}/betoffer/event/{event_id}.json?{KAMBI_OFFERING_QUERY}"

    def _select_kambi_moneyline_offer(self, offers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Select the NHL 2-way moneyline offer (incl. overtime/shootout) from Kambi.

        Kambi offers include many markets; we need a strict selector to avoid
        cross-market mismatches in validation / odds matcher.
        """
        candidates: List[Dict[str, Any]] = []

        for bo in offers:
            if not isinstance(bo, dict):
                continue
            if bo.get("suspended") is True:
                continue

            criterion = bo.get("criterion") or {}
            label = (criterion.get("englishLabel") or criterion.get("label") or "").lower().strip()
            if "moneyline" not in label:
                continue
            if "including overtime" not in label:
                continue

            outcomes = bo.get("outcomes") or []
            if not isinstance(outcomes, list) or not outcomes:
                continue

            types = {(o.get("type") or "").strip().upper() for o in outcomes if isinstance(o, dict)}
            if "OT_ONE" not in types or "OT_TWO" not in types:
                continue
            if "OT_CROSS" in types:
                continue

            candidates.append(bo)

        if candidates:
            return candidates[0]
        return None

    def _sport_feed_url(self, sport: str) -> str:
        slug = KINDRED_SPORT_SLUGS.get(sport)
        if not slug:
            raise ValueError(f"Unsupported sport: {sport}")
        return (
            f"{self.base_url}/sportsbook-feeds/views/filter/{slug}/all/matches"
            f"?includeParticipants=true&useCombined=true"
        )

    def _competition_feed_url(self, filter_path: str) -> str:
        return (
            f"{self.base_url}/sportsbook-feeds/views/filter/{filter_path}/matches"
            f"?includeParticipants=true&useCombined=true"
        )

    def _sport_source_url(self, sport: str) -> str:
        slug = KINDRED_WEB_SPORT_SLUGS.get(sport, "")
        if not slug:
            return self.base_url
        return f"{self.base_url}/betting/sports/filter/{slug}"

    def _is_esports_event(self, event: Dict[str, Any]) -> bool:
        group = (event.get("group") or "").lower()
        if "esports" in group:
            return True
        path = event.get("path") or []
        for node in path:
            name = (node.get("name") or node.get("englishName") or "").lower()
            term_key = (node.get("termKey") or "").lower()
            if "esports" in name or "esports" in term_key:
                return True
        return False

    def _normalize_competition_code(self, name: str, *, sport: str = "", path: Optional[List[Dict[str, Any]]] = None) -> str:
        if not name:
            return ""

        norm = name.lower().strip()

        # Strip season prefixes like "2025/2026 "
        # (Unibet usually doesn't, but keep consistent with other scrapers)
        if len(norm) >= 5 and norm[:4].isdigit():
            # remove leading year or year/year and following whitespace
            while norm and (norm[0].isdigit() or norm[0] in {"/", " "}):
                norm = norm[1:]
            norm = norm.strip()

        # Boxing/UFC are treated as "boxing" in the rest of the system.
        if any(token in norm for token in ("boxing", "ufc", "mma", "martial")):
            return "boxing"

        # Normalize common separators
        norm = norm.replace("-", " ")
        norm = " ".join(norm.split())

        mapped = COMPETITION_CODE_MAP.get(norm)
        if not mapped:
            return norm

        # Soccer has ambiguous league names (many countries have a "Premier League",
        # "Serie A", etc). Only accept these mappings if the event path includes the
        # expected country/region.
        if sport == "soccer" and path:
            path_names = [
                str(n.get("name") or n.get("englishName") or "").lower()
                for n in path
                if isinstance(n, dict)
            ]
            path_joined = " ".join(path_names)

            if mapped == "epl" and "england" not in path_joined and "english" not in path_joined:
                return norm
            if mapped == "seriea" and "italy" not in path_joined and "italian" not in path_joined:
                return norm
            if mapped == "ligue1" and "france" not in path_joined and "french" not in path_joined:
                return norm
            if mapped == "bundesliga" and "germany" not in path_joined and "german" not in path_joined:
                return norm
            if mapped == "laliga" and "spain" not in path_joined and "spanish" not in path_joined:
                return norm

        return mapped

    def _competition_from_event(self, event: Dict[str, Any]) -> str:
        # Prefer event.group (usually league name like "NBA", "Premier League")
        group = event.get("group") or ""
        if group:
            return str(group)

        # Fallback: last path node name
        path = event.get("path") or []
        if path:
            last = path[-1] if isinstance(path[-1], dict) else {}
            return str(last.get("name") or last.get("englishName") or "")
        return ""

    def _parse_start_time(self, iso: Any) -> Optional[datetime]:
        if not iso or not isinstance(iso, str):
            return None
        try:
            # Example: "2026-02-01T23:00:00Z"
            return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            return None

    def _iter_event_items(self, groups: Iterable[Dict[str, Any]]) -> Iterable[Dict[str, Any]]:
        for group in groups:
            if not isinstance(group, dict):
                continue
            # Sub-groups
            for sg in group.get("subGroups") or []:
                yield from self._iter_event_items([sg])
            # Events
            for item in group.get("events") or []:
                if isinstance(item, dict):
                    yield item

    def _extract_match_items(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        layout = data.get("layout") or {}
        sections = layout.get("sections") or []

        items: List[Dict[str, Any]] = []
        for section in sections:
            for widget in (section.get("widgets") or []):
                matches = widget.get("matches")
                if not isinstance(matches, dict):
                    continue

                # Common view: matches.events is a list of event items.
                if isinstance(matches.get("events"), list):
                    items.extend([it for it in (matches.get("events") or []) if isinstance(it, dict)])

                # Some tournament views: matches.highlightedEvents is either a list or
                # a dict with {events: [...]}.
                highlighted = matches.get("highlightedEvents")
                if isinstance(highlighted, list):
                    items.extend([it for it in highlighted if isinstance(it, dict)])
                elif isinstance(highlighted, dict) and isinstance(highlighted.get("events"), list):
                    items.extend([it for it in (highlighted.get("events") or []) if isinstance(it, dict)])

                # Grouped view: matches.groups contains nested groups/subGroups/events.
                groups = matches.get("groups")
                if isinstance(groups, list) and groups:
                    items.extend(list(self._iter_event_items(groups)))

        # De-dupe by event id (same event can appear in multiple widgets).
        seen: set[str] = set()
        unique: List[Dict[str, Any]] = []
        for it in items:
            ev = it.get("event") if isinstance(it, dict) else None
            eid = str(ev.get("id")) if isinstance(ev, dict) and ev.get("id") is not None else None
            if eid and eid in seen:
                continue
            if eid:
                seen.add(eid)
            unique.append(it)

        return unique

    def _merge_bet_offers(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        offers: List[Dict[str, Any]] = []
        main = item.get("mainBetOffer")
        if isinstance(main, dict):
            offers.append(main)
        for bo in item.get("betOffers") or []:
            if isinstance(bo, dict):
                offers.append(bo)
        # De-dupe by betOffer id where possible
        seen: set[Any] = set()
        unique: List[Dict[str, Any]] = []
        for bo in offers:
            bo_id = bo.get("id") if isinstance(bo, dict) else None
            if bo_id is not None:
                if bo_id in seen:
                    continue
                seen.add(bo_id)
            unique.append(bo)
        return unique

    def _bet_offer_rank(self, sport: str, criterion_label: str) -> int:
        crit = (criterion_label or "").lower().strip()

        if any(tok in crit for tok in DISALLOWED_CRITERION_TOKENS):
            return 10_000

        if sport == "basketball":
            if "moneyline" in crit or "money line" in crit:
                return 0
            return 100

        if sport == "ice_hockey":
            # Prefer 2-way moneyline (incl OT/SO) when available; otherwise fall back.
            if "moneyline" in crit or "money line" in crit:
                return 0
            if "including overtime" in crit:
                return 1
            if "head to head" in crit or "head-to-head" in crit or "h2h" in crit:
                return 2
            if "match odds" in crit:
                return 3
            return 100

        if sport == "soccer":
            # Prefer regular-time / full-time match result.
            if "regular time" in crit:
                return 0
            if "full time" in crit:
                return 1
            return 10

        if sport in ("afl", "nrl"):
            if "including overtime" in crit:
                return 0
            if "regular time" in crit:
                return 1
            return 10

        if sport == "boxing":
            if "bout odds" in crit:
                return 0
            if "fight" in crit:
                return 1
            return 10

        return 10

    def _select_match_winner_offer(self, sport: str, offers: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        candidates: List[Tuple[int, Dict[str, Any]]] = []
        for bo in offers:
            if bo.get("suspended") is True:
                continue
            outcomes = bo.get("outcomes") or []
            if not isinstance(outcomes, list) or not outcomes:
                continue

            # Must be a H2H-style market: outcomes with OT_ONE/OT_TWO (and optional OT_CROSS)
            types = {(o.get("type") or "").strip().upper() for o in outcomes if isinstance(o, dict)}
            if "OT_ONE" not in types or "OT_TWO" not in types:
                continue

            # Soccer: require draw selection present for proper 1X2 market.
            if sport == "soccer" and "OT_CROSS" not in types:
                continue

            # Boxing: allow 2-way or 3-way (draw can exist).
            if sport == "boxing":
                pass

            # Basket/afl/nrl: require 2-way (no OT_CROSS)
            if sport in ("basketball", "afl", "nrl") and "OT_CROSS" in types:
                continue

            criterion = bo.get("criterion") or {}
            criterion_label = criterion.get("englishLabel") or criterion.get("label") or ""
            rank = self._bet_offer_rank(sport, str(criterion_label))
            if rank >= 10_000:
                continue

            candidates.append((rank, bo))

        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    def _parse_decimal_odds(self, outcome: Dict[str, Any]) -> Optional[Decimal]:
        raw = outcome.get("oddsDecimal")
        if raw is not None:
            try:
                d = Decimal(str(raw))
                if d > 1:
                    return d
            except Exception:
                pass

        # Fallback: odds as scaled int (e.g., 3550 -> 3.55)
        raw_int = outcome.get("odds")
        if raw_int is not None:
            try:
                d = (Decimal(str(raw_int)) / Decimal("1000"))
                if d > 1:
                    return d
            except Exception:
                pass

        return None

    def _parse_item(
        self,
        item: Dict[str, Any],
        sport: str,
        *,
        competition_code_override: Optional[str] = None,
    ) -> Optional[_ParsedEventItem]:
        event = item.get("event") or {}
        if not isinstance(event, dict):
            return None

        if self._is_esports_event(event):
            return None

        # Only scheduled (avoid live)
        state = (event.get("state") or "").upper().strip()
        if state and state not in {"NOT_STARTED"}:
            return None

        start_time = self._parse_start_time(event.get("start"))
        if not start_time:
            return None

        now = datetime.now(timezone.utc)
        if start_time < now:
            return None
        if start_time > (now + timedelta(days=self.horizon_days)):
            return None

        allowed = ALLOWED_COMPETITIONS_BY_SPORT.get(sport, set())

        if competition_code_override:
            comp_code = competition_code_override
            if allowed and comp_code not in allowed:
                return None
            comp_name = COMPETITION_CANONICAL_NAME.get(comp_code, comp_code)
        else:
            comp_raw = self._competition_from_event(event)
            comp_code = self._normalize_competition_code(comp_raw, sport=sport, path=event.get("path") or [])
            if not comp_code:
                return None
            if allowed and comp_code not in allowed:
                return None
            comp_name = COMPETITION_CANONICAL_NAME.get(comp_code, comp_raw)

        home = (event.get("homeName") or "").strip()
        away = (event.get("awayName") or "").strip()
        if not home or not away:
            return None

        if sport == "boxing":
            home_key = self._participant_sort_key(home)
            away_key = self._participant_sort_key(away)
            if away_key and home_key and away_key < home_key:
                home, away = away, home

        event_id = str(event.get("id") or "").strip()
        if not event_id:
            return None

        # Prefer consistent name format ("Home v Away") for downstream normalization.
        name = f"{home} v {away}"

        offers = self._merge_bet_offers(item)

        return _ParsedEventItem(
            event_id=event_id,
            name=name,
            start_time=start_time,
            competition_code=comp_code,
            competition_name=comp_name,
            home_team=home,
            away_team=away,
            bet_offers=offers,
        )

    def _parse_feed(
        self,
        data: Dict[str, Any],
        sport: str,
        *,
        competition_code_override: Optional[str] = None,
    ) -> List[ScrapedEvent]:
        items = self._extract_match_items(data)
        if not items:
            return []

        parsed_events: List[ScrapedEvent] = []

        for item in items:
            try:
                parsed_item = self._parse_item(
                    item,
                    sport,
                    competition_code_override=competition_code_override,
                )
                if not parsed_item:
                    continue

                offer = self._select_match_winner_offer(sport, parsed_item.bet_offers)
                if not offer:
                    continue

                market_name = MARKET_NAME_BY_SPORT.get(sport, "Match Winner")
                source_url = self._sport_source_url(sport)

                event = ScrapedEvent(
                    external_id=parsed_item.event_id,
                    name=parsed_item.name,
                    sport=sport,
                    competition=parsed_item.competition_name,
                    start_time=parsed_item.start_time,
                    home_team=parsed_item.home_team,
                    away_team=parsed_item.away_team,
                    odds=[],
                )

                for outcome in offer.get("outcomes") or []:
                    if not isinstance(outcome, dict):
                        continue
                    if (outcome.get("status") or "").upper() != "OPEN":
                        continue

                    outcome_type = (outcome.get("type") or "").upper().strip()
                    participant = str(outcome.get("participant") or "").strip()

                    if outcome_type == "OT_CROSS":
                        selection_key = "draw"
                        selection_name = "Draw"
                    else:
                        # Default mapping relies on OT_ONE/OT_TWO meaning home/away
                        # from the API. For boxing we enforce deterministic fighter
                        # ordering, so we must map outcomes by participant name.
                        selection_key = None
                        selection_name = participant

                        if participant:
                            part_key = self._participant_sort_key(participant)
                            home_key = self._participant_sort_key(event.home_team or "")
                            away_key = self._participant_sort_key(event.away_team or "")
                            if part_key and home_key and part_key == home_key:
                                selection_key = "home"
                                selection_name = event.home_team or participant
                            elif part_key and away_key and part_key == away_key:
                                selection_key = "away"
                                selection_name = event.away_team or participant

                        if selection_key is None:
                            if outcome_type == "OT_ONE":
                                selection_key = "home"
                                selection_name = event.home_team or participant
                            elif outcome_type == "OT_TWO":
                                selection_key = "away"
                                selection_name = event.away_team or participant
                            else:
                                continue

                    dec = self._parse_decimal_odds(outcome)
                    if not dec:
                        continue

                    odds = ScrapedOdds(
                        event_external_id=event.external_id,
                        event_name=event.name,
                        sport=event.sport,
                        competition=event.competition,
                        start_time=event.start_time,
                        market_type="match_winner",
                        market_name=market_name,
                        selection_name=str(selection_name).strip() or selection_name,
                        selection_key=selection_key,
                        decimal_odds=dec.quantize(Decimal("0.01")),
                        bookmaker_code=self.bookmaker_code,
                        source_url=source_url,
                        scraped_at=datetime.now(timezone.utc),
                    )
                    event.odds.append(odds)

                if event.odds:
                    parsed_events.append(event)
            except Exception as exc:
                self.logger.debug(f"[{self.bookmaker_code}/{sport}] Failed to parse event item: {exc}")
                continue

        return parsed_events

    async def _parse_feed_async(
        self,
        data: Dict[str, Any],
        sport: str,
        *,
        competition_code_override: Optional[str] = None,
    ) -> List[ScrapedEvent]:
        if sport == "ice_hockey":
            return await self._parse_ice_hockey_feed(
                data,
                competition_code_override=competition_code_override,
            )
        return self._parse_feed(
            data,
            sport,
            competition_code_override=competition_code_override,
        )

    async def _parse_ice_hockey_feed(
        self,
        data: Dict[str, Any],
        *,
        competition_code_override: Optional[str] = None,
    ) -> List[ScrapedEvent]:
        """
        NHL requires a true 2-way moneyline market (incl. overtime/shootout).

        The Unibet sportsbook-feeds list view exposes a 3-way "Match Odds - Regular Time"
        market, which doesn't match other bookmakers' moneyline markets.

        We use sportsbook-feeds to discover event IDs + start times, then fetch the
        full Kambi event bet offers to extract the correct moneyline market.
        """
        items = self._extract_match_items(data)
        if not items:
            return []

        parsed_items: List[_ParsedEventItem] = []
        for item in items:
            parsed_item = self._parse_item(
                item,
                "ice_hockey",
                competition_code_override=competition_code_override,
            )
            if parsed_item:
                parsed_items.append(parsed_item)

        if not parsed_items:
            return []

        async def fetch_one(pi: _ParsedEventItem) -> Tuple[str, Optional[Dict[str, Any]]]:
            try:
                url = self._kambi_betoffer_url(pi.event_id)
                return pi.event_id, await self._request_json(url)
            except Exception:
                return pi.event_id, None

        results = await asyncio.gather(*(fetch_one(pi) for pi in parsed_items))
        betoffer_by_event_id = {event_id: payload for event_id, payload in results if payload}

        market_name = MARKET_NAME_BY_SPORT.get("ice_hockey", "Moneyline")
        events: List[ScrapedEvent] = []

        for pi in parsed_items:
            payload = betoffer_by_event_id.get(pi.event_id)
            if not payload:
                continue

            offer = self._select_kambi_moneyline_offer(payload.get("betOffers") or [])
            if not offer:
                continue

            source_url = f"{self.base_url}/betting/sports/event/{pi.event_id}"

            event = ScrapedEvent(
                external_id=pi.event_id,
                name=pi.name,
                sport="ice_hockey",
                competition=pi.competition_name,
                start_time=pi.start_time,
                home_team=pi.home_team,
                away_team=pi.away_team,
                odds=[],
            )

            for outcome in offer.get("outcomes") or []:
                if not isinstance(outcome, dict):
                    continue
                if (outcome.get("status") or "").upper() != "OPEN":
                    continue

                outcome_type = (outcome.get("type") or "").upper().strip()
                if outcome_type not in {"OT_ONE", "OT_TWO"}:
                    continue

                participant = str(outcome.get("participant") or "").strip()
                selection_key: Optional[str] = None
                selection_name: str = participant

                if participant:
                    part_key = self._participant_sort_key(participant)
                    home_key = self._participant_sort_key(event.home_team or "")
                    away_key = self._participant_sort_key(event.away_team or "")
                    if part_key and home_key and part_key == home_key:
                        selection_key = "home"
                        selection_name = event.home_team or participant
                    elif part_key and away_key and part_key == away_key:
                        selection_key = "away"
                        selection_name = event.away_team or participant

                if selection_key is None:
                    if outcome_type == "OT_ONE":
                        selection_key = "home"
                        selection_name = event.home_team or participant
                    elif outcome_type == "OT_TWO":
                        selection_key = "away"
                        selection_name = event.away_team or participant
                    else:
                        continue

                dec = self._parse_decimal_odds(outcome)
                if not dec:
                    continue

                event.odds.append(
                    ScrapedOdds(
                        event_external_id=event.external_id,
                        event_name=event.name,
                        sport=event.sport,
                        competition=event.competition,
                        start_time=event.start_time,
                        market_type="match_winner",
                        market_name=market_name,
                        selection_name=str(selection_name).strip() or selection_name,
                        selection_key=selection_key,
                        decimal_odds=dec.quantize(Decimal("0.01")),
                        bookmaker_code=self.bookmaker_code,
                        source_url=source_url,
                        scraped_at=datetime.now(timezone.utc),
                    )
                )

            if len(event.odds) >= 2:
                events.append(event)

        return events

    async def scrape_sport(self, sport: str, limit: Optional[int] = None) -> ScrapeResult:
        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()
        errors: List[str] = []
        all_events: List[ScrapedEvent] = []

        try:
            feed_defs = KINDRED_COMPETITION_FILTERS.get(sport)
            if not feed_defs:
                url = self._sport_feed_url(sport)
                self.logger.info(f"[{self.bookmaker_code}] Starting scrape: {sport} ({url})")
                data = await self._request_json(url)
                events = await self._parse_feed_async(data, sport)
                if limit:
                    events = events[:limit]
                all_events.extend(events)
            else:
                urls = [(comp_code, self._competition_feed_url(path)) for comp_code, path in feed_defs]
                self.logger.info(
                    f"[{self.bookmaker_code}] Starting scrape: {sport} ({len(urls)} competition feeds)"
                )

                async def fetch_one(comp_code: str, url: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
                    try:
                        data = await self._request_json(url)
                        return comp_code, data, None
                    except Exception as exc:
                        return comp_code, None, str(exc)

                results = await asyncio.gather(
                    *(fetch_one(comp_code, url) for comp_code, url in urls)
                )

                # Aggregate events; de-dupe by external_id
                by_id: Dict[str, ScrapedEvent] = {}
                for comp_code, data, err in results:
                    if err:
                        errors.append(f"{sport}/{comp_code}: {err}")
                        continue
                    if not data:
                        continue
                    events = await self._parse_feed_async(data, sport, competition_code_override=comp_code)
                    for ev in events:
                        if ev.external_id not in by_id:
                            by_id[ev.external_id] = ev

                all_events = list(by_id.values())
                if limit:
                    all_events = all_events[:limit]

        except Exception as exc:
            errors.append(str(exc))
            self.logger.exception(f"[{self.bookmaker_code}/{sport}] Fatal scrape error")

        total_odds = sum(len(e.odds) for e in all_events)
        status = ScraperStatus.SUCCESS if not errors else (
            ScraperStatus.PARTIAL if all_events else ScraperStatus.FAILED
        )

        scrape_duration = time.time() - scrape_start
        result = ScrapeResult(
            bookmaker_code=self.bookmaker_code,
            status=status,
            events_scraped=len(all_events),
            odds_scraped=total_odds,
            events=all_events,
            errors=errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

        self.logger.info(
            f"[{self.bookmaker_code}/{sport}] Completed in {scrape_duration:.2f}s: "
            f"{len(all_events)} events, {total_odds} odds"
        )
        self.log_scrape_stats(result)
        return result

    async def scrape_all_sports_parallel(
        self,
        sports: Optional[List[str]] = None,
        limit: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> ScrapeResult:
        import os
        if batch_size is None:
            batch_size = int(os.getenv("SCRAPER_BATCH_SIZE", "1"))

        started_at = datetime.now(timezone.utc)
        scrape_start = time.time()

        sports_to_scrape = sports or self.ALL_SPORTS
        self.logger.info(
            f"[{self.bookmaker_code}] Starting PARALLEL scrape of {len(sports_to_scrape)} sports "
            f"(batch_size={batch_size})"
        )

        all_results: List[Tuple[str, Any]] = []
        for i in range(0, len(sports_to_scrape), batch_size):
            batch = sports_to_scrape[i:i + batch_size]
            self.logger.info(f"[{self.bookmaker_code}] Processing batch {i//batch_size + 1}: {', '.join(batch)}")
            tasks = [self.scrape_sport(s, limit=limit) for s in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(zip(batch, batch_results))

        all_events: List[ScrapedEvent] = []
        all_errors: List[str] = []
        total_events_scraped = 0
        total_odds_scraped = 0
        successful_sports: List[str] = []
        failed_sports: List[str] = []

        for sport, result in all_results:
            if isinstance(result, Exception):
                all_errors.append(f"{sport}: {str(result)}")
                failed_sports.append(sport)
                self.logger.error(f"[{self.bookmaker_code}] {sport} failed: {result}")
                continue

            if not isinstance(result, ScrapeResult):
                all_errors.append(f"{sport}: Unexpected result type")
                failed_sports.append(sport)
                continue

            all_events.extend(result.events)
            all_errors.extend(result.errors)
            total_events_scraped += result.events_scraped
            total_odds_scraped += result.odds_scraped

            if result.status == ScraperStatus.SUCCESS:
                successful_sports.append(sport)
            elif result.status == ScraperStatus.PARTIAL:
                successful_sports.append(f"{sport}(partial)")
            else:
                failed_sports.append(sport)

        if not all_errors:
            status = ScraperStatus.SUCCESS
        elif all_events:
            status = ScraperStatus.PARTIAL
        else:
            status = ScraperStatus.FAILED

        scrape_duration = time.time() - scrape_start
        combined = ScrapeResult(
            bookmaker_code=self.bookmaker_code,
            status=status,
            events_scraped=total_events_scraped,
            odds_scraped=total_odds_scraped,
            events=all_events,
            errors=all_errors,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

        self.logger.info(
            f"[{self.bookmaker_code}] PARALLEL scrape completed in {scrape_duration:.2f}s: "
            f"{total_events_scraped} events, {total_odds_scraped} odds | "
            f"Success: {', '.join(successful_sports) or 'none'} | "
            f"Failed: {', '.join(failed_sports) or 'none'}"
        )

        return combined

    def parse_event(self, event_data: Any) -> ScrapedEvent:
        raise NotImplementedError("KindredScraper parses from the matches view feed")

    def parse_odds(self, odds_data: Any, event: ScrapedEvent) -> List[ScrapedOdds]:
        raise NotImplementedError("KindredScraper parses from the matches view feed")
