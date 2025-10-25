"""
Save scraped odds data to database.

This module handles the persistence of ScrapedEvent and ScrapedOdds objects
from bookmaker scrapers into the normalized database schema.
"""
import sys
sys.path.insert(0, "apps/api/src")

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Set
from decimal import Decimal
from difflib import SequenceMatcher
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from api.core.database import SessionLocal
from api.models.odds import (
    Sport, Competition, Event, Market, Selection, OddsSnapshot,
    Bookmaker, Team, SourceType, MarketType
)
from scrapers.base import ScrapedEvent, ScrapedOdds, ScrapeResult

logger = logging.getLogger(__name__)


def normalize_team_name(name: str) -> str:
    """
    Normalize team names for better fuzzy matching.

    Handles common abbreviations and variations:
    - Nottm -> Nottingham
    - Man Utd/Man United -> Manchester United
    - Man City -> Manchester City
    - Spurs -> Tottenham
    etc.
    """
    replacements = {
        "nottm": "nottingham",
        "man utd": "manchester united",
        "man united": "manchester united",
        "man city": "manchester city",
        "wolves": "wolverhampton",
        "spurs": "tottenham",
        "tottenham hotspur": "tottenham",
        "west ham": "west ham united",
        "brighton": "brighton & hove albion",
        "brighton & hove albion": "brighton",
        "newcastle": "newcastle united",
        "leicester": "leicester city",
        "norwich": "norwich city",
        "crystal palace": "palace",
    }

    normalized = name.lower().strip()

    # Apply replacements
    for abbr, full in replacements.items():
        if abbr in normalized:
            normalized = normalized.replace(abbr, full)

    return normalized


def fuzzy_match_score(str1: str, str2: str) -> float:
    """
    Calculate fuzzy match score between two strings (0.0 to 1.0).

    Uses SequenceMatcher to calculate similarity between normalized strings.
    """
    s1 = " ".join(normalize_team_name(str1).split())
    s2 = " ".join(normalize_team_name(str2).split())

    return SequenceMatcher(None, s1, s2).ratio()


class OddsPersistence:
    """Handles saving scraped odds data to database"""

    def __init__(self, db: Session):
        self.db = db
        self._sport_cache: Dict[str, Sport] = {}
        self._competition_cache: Dict[tuple, Competition] = {}
        self._bookmaker_cache: Dict[str, Bookmaker] = {}
        self._event_cache: Dict[str, Event] = {}
        self._market_cache: Dict[tuple, Market] = {}
        self._selection_cache: Dict[tuple, Selection] = {}

    def save_scrape_result(self, result: ScrapeResult, scrape_session_id: str) -> Dict[str, int]:
        """
        Save complete scrape result to database.

        Args:
            result: ScrapeResult from scraper
            scrape_session_id: Unique ID for this scrape session

        Returns:
            Dict with counts: {events_saved, odds_saved, errors}
        """
        import time
        stats = {"events_saved": 0, "odds_saved": 0, "errors": 0}

        try:
            # Get or create bookmaker
            bookmaker_start = time.time()
            bookmaker = self._get_or_create_bookmaker(result.bookmaker_code)
            bookmaker_time = time.time() - bookmaker_start
            logger.info(f"⏱️  [DB] Get bookmaker took {bookmaker_time:.4f}s")

            events_start = time.time()

            # OPTIMIZATION: Batch process all events together instead of one-by-one
            all_selection_ids = []
            all_odds_to_insert = []

            for scraped_event in result.events:
                try:
                    # Save event and get database ID
                    event_save_start = time.time()
                    event = self._save_event(scraped_event)
                    stats["events_saved"] += 1

                    # Prepare odds for batch insert (don't insert yet)
                    for scraped_odds in scraped_event.odds:
                        try:
                            market = self._get_or_create_market(event, scraped_odds)
                            selection = self._get_or_create_selection(market, scraped_odds)

                            all_selection_ids.append(selection.id)
                            all_odds_to_insert.append({
                                "selection_id": selection.id,
                                "bookmaker_id": bookmaker.id,
                                "decimal_odds": scraped_odds.decimal_odds,
                                "available_amount": scraped_odds.liquidity,
                                "source_type": SourceType.SCRAPE,
                                "source_url": scraped_odds.source_url,
                                "timestamp": scraped_odds.scraped_at,
                                "is_current": True,
                                "scrape_session_id": scrape_session_id,
                                "market_status": "open"
                            })
                            stats["odds_saved"] += 1
                        except Exception as e:
                            logger.error(f"Failed to prepare odds for {scraped_odds.selection_name}: {e}")
                            continue

                except Exception as e:
                    logger.error(f"Failed to save event {scraped_event.name}: {e}")
                    stats["errors"] += 1
                    continue

            # BATCH DELETE all old odds at once (single query)
            if all_selection_ids:
                delete_start = time.time()
                self.db.execute(
                    delete(OddsSnapshot).where(
                        OddsSnapshot.selection_id.in_(all_selection_ids),
                        OddsSnapshot.bookmaker_id == bookmaker.id,
                        OddsSnapshot.is_current == True
                    )
                )
                delete_time = time.time() - delete_start
                logger.debug(f"⏱️  [DB] Batch delete {len(set(all_selection_ids))} selections took {delete_time:.4f}s")

            # BATCH INSERT all new odds at once (single operation)
            if all_odds_to_insert:
                insert_start = time.time()
                self.db.bulk_insert_mappings(OddsSnapshot, all_odds_to_insert)
                insert_time = time.time() - insert_start
                logger.debug(f"⏱️  [DB] Batch insert {len(all_odds_to_insert)} odds took {insert_time:.4f}s")

            events_time = time.time() - events_start
            logger.info(f"⏱️  [DB] Processing {len(result.events)} events took {events_time:.2f}s")

            # Commit transaction
            commit_start = time.time()
            self.db.commit()
            commit_time = time.time() - commit_start
            logger.info(f"⏱️  [DB] Commit took {commit_time:.2f}s")
            logger.info(f"Saved scrape result: {stats}")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save scrape result: {e}")
            stats["errors"] += 1
            raise

        return stats

    def _get_or_create_bookmaker(self, bookmaker_code: str) -> Bookmaker:
        """Get bookmaker from cache or database"""
        if bookmaker_code in self._bookmaker_cache:
            return self._bookmaker_cache[bookmaker_code]

        bookmaker = self.db.scalar(
            select(Bookmaker).where(Bookmaker.code == bookmaker_code)
        )

        if not bookmaker:
            raise ValueError(f"Bookmaker '{bookmaker_code}' not found in database")

        self._bookmaker_cache[bookmaker_code] = bookmaker
        return bookmaker

    def _get_or_create_sport(self, sport_code: str) -> Sport:
        """Get or create sport"""
        if sport_code in self._sport_cache:
            return self._sport_cache[sport_code]

        sport = self.db.scalar(
            select(Sport).where(Sport.code == sport_code)
        )

        if not sport:
            # Create sport if doesn't exist
            sport_names = {
                "soccer": ("Soccer", "Soccer"),
                "afl": ("Australian Football League", "AFL"),
                "nrl": ("National Rugby League", "NRL"),
                "cricket": ("Cricket", "Cricket"),
                "tennis": ("Tennis", "Tennis"),
                "basketball": ("Basketball", "Basketball"),
            }
            name, display_name = sport_names.get(sport_code, (sport_code.title(), sport_code.upper()))

            sport = Sport(
                code=sport_code,
                name=name,
                display_name=display_name,
                is_active=True
            )
            self.db.add(sport)
            self.db.flush()

        self._sport_cache[sport_code] = sport
        return sport

    def _get_or_create_competition(self, sport: Sport, competition_name: str) -> Competition:
        """Get or create competition"""
        cache_key = (sport.id, competition_name)
        if cache_key in self._competition_cache:
            return self._competition_cache[cache_key]

        competition = self.db.scalar(
            select(Competition).where(
                Competition.sport_id == sport.id,
                Competition.name == competition_name
            )
        )

        if not competition:
            # Create competition
            short_name = competition_name[:50]  # Truncate for short_name
            competition = Competition(
                sport_id=sport.id,
                name=competition_name,
                short_name=short_name,
                is_active=True
            )
            self.db.add(competition)
            self.db.flush()

        self._competition_cache[cache_key] = competition
        return competition

    def _save_event(self, scraped_event: ScrapedEvent) -> Event:
        """
        Save or update event with fuzzy name matching.

        Matches events from different bookmakers (e.g., "Nottm Forest" vs "Nottingham Forest")
        using fuzzy string matching on event names and time proximity.
        """
        # Get sport and competition
        sport = self._get_or_create_sport(scraped_event.sport)
        competition = self._get_or_create_competition(sport, scraped_event.competition)

        # First, try exact match by name and start time
        event = self.db.scalar(
            select(Event).where(
                Event.competition_id == competition.id,
                Event.name == scraped_event.name,
                Event.start_time == scraped_event.start_time
            )
        )

        if event:
            # Exact match found - update external IDs if needed
            if scraped_event.external_id not in event.external_ids:
                event.external_ids[scraped_event.external_id] = True
                self.db.add(event)
                self.db.flush()
            return event

        # No exact match - try fuzzy matching
        # Look for events in the same competition within ±3 hours of start time
        time_window_start = scraped_event.start_time - timedelta(hours=3)
        time_window_end = scraped_event.start_time + timedelta(hours=3)

        candidate_events = self.db.scalars(
            select(Event).where(
                Event.competition_id == competition.id,
                Event.start_time >= time_window_start,
                Event.start_time <= time_window_end,
                Event.status == "scheduled"
            )
        ).all()

        # Find best fuzzy match
        best_match = None
        best_score = 0.0
        MATCH_THRESHOLD = 0.75  # 75% similarity required

        for candidate in candidate_events:
            score = fuzzy_match_score(scraped_event.name, candidate.name)
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= MATCH_THRESHOLD:
            # Fuzzy match found!
            logger.info(
                f"Fuzzy matched event: '{scraped_event.name}' -> '{best_match.name}' "
                f"(score: {best_score:.2f})"
            )

            # Update external IDs
            if scraped_event.external_id not in best_match.external_ids:
                best_match.external_ids[scraped_event.external_id] = True
                self.db.add(best_match)
                self.db.flush()

            return best_match

        # No match found - create new event
        logger.info(f"Creating new event: {scraped_event.name}")
        event = Event(
            competition_id=competition.id,
            name=scraped_event.name,
            start_time=scraped_event.start_time,
            external_ids={scraped_event.external_id: True},
            status="scheduled"
        )

        # Add venue if available
        if scraped_event.venue:
            event.venue = scraped_event.venue

        self.db.add(event)
        self.db.flush()

        return event

    def _save_event_odds(
        self,
        event: Event,
        scraped_odds_list: List[ScrapedOdds],
        bookmaker: Bookmaker,
        scrape_session_id: str
    ) -> int:
        """Save all odds for an event (with batching for performance)"""
        import time
        odds_saved = 0

        # Prepare batch data
        selection_ids_to_delete = []
        odds_to_insert = []

        for scraped_odds in scraped_odds_list:
            try:
                # Get or create market
                market = self._get_or_create_market(event, scraped_odds)

                # Get or create selection
                selection = self._get_or_create_selection(market, scraped_odds)

                # Collect selection IDs for batch delete
                selection_ids_to_delete.append(selection.id)

                # Prepare odds data for batch insert
                odds_to_insert.append({
                    "selection_id": selection.id,
                    "bookmaker_id": bookmaker.id,
                    "decimal_odds": scraped_odds.decimal_odds,
                    "available_amount": scraped_odds.liquidity,
                    "source_type": SourceType.SCRAPE,
                    "source_url": scraped_odds.source_url,
                    "timestamp": scraped_odds.scraped_at,
                    "is_current": True,
                    "scrape_session_id": scrape_session_id,
                    "market_status": "open"
                })
                odds_saved += 1

            except Exception as e:
                logger.error(f"Failed to prepare odds for {scraped_odds.selection_name}: {e}")
                continue

        # Batch delete old odds (single query instead of N queries)
        if selection_ids_to_delete:
            delete_start = time.time()
            self.db.execute(
                delete(OddsSnapshot).where(
                    OddsSnapshot.selection_id.in_(selection_ids_to_delete),
                    OddsSnapshot.bookmaker_id == bookmaker.id,
                    OddsSnapshot.is_current == True
                )
            )
            delete_time = time.time() - delete_start
            logger.debug(f"⏱️  [DB] Batch delete {len(selection_ids_to_delete)} old odds took {delete_time:.4f}s")

        # Batch insert new odds (single operation instead of N operations)
        if odds_to_insert:
            insert_start = time.time()
            self.db.bulk_insert_mappings(OddsSnapshot, odds_to_insert)
            insert_time = time.time() - insert_start
            logger.debug(f"⏱️  [DB] Batch insert {len(odds_to_insert)} odds took {insert_time:.4f}s")

        self.db.flush()
        return odds_saved

    def _get_or_create_market(self, event: Event, scraped_odds: ScrapedOdds) -> Market:
        """Get or create market for odds"""
        # Normalize market type
        market_type = self._normalize_market_type(scraped_odds.market_type)

        cache_key = (event.id, market_type, scraped_odds.market_name)
        if cache_key in self._market_cache:
            return self._market_cache[cache_key]

        # Try to find existing market
        market = self.db.scalar(
            select(Market).where(
                Market.event_id == event.id,
                Market.market_type == market_type,
                Market.name == scraped_odds.market_name
            )
        )

        if not market:
            market = Market(
                event_id=event.id,
                market_type=market_type,
                name=scraped_odds.market_name,
                is_active=True
            )
            self.db.add(market)
            self.db.flush()

        self._market_cache[cache_key] = market
        return market

    def _get_or_create_selection(self, market: Market, scraped_odds: ScrapedOdds) -> Selection:
        """Get or create selection within market"""
        cache_key = (market.id, scraped_odds.selection_key)
        if cache_key in self._selection_cache:
            return self._selection_cache[cache_key]

        selection = self.db.scalar(
            select(Selection).where(
                Selection.market_id == market.id,
                Selection.selection_key == scraped_odds.selection_key
            )
        )

        if not selection:
            selection = Selection(
                market_id=market.id,
                name=scraped_odds.selection_name,
                selection_key=scraped_odds.selection_key
            )
            self.db.add(selection)
            self.db.flush()

        self._selection_cache[cache_key] = selection
        return selection

    def _normalize_market_type(self, market_type_str: str) -> str:
        """Normalize market type string to MarketType enum"""
        # Simple mapping for now
        market_type_mapping = {
            "match_winner": MarketType.MATCH_WINNER,
            "result": MarketType.MATCH_WINNER,
            "head_to_head": MarketType.MATCH_WINNER,
            "handicap": MarketType.HANDICAP,
            "line": MarketType.HANDICAP,
            "total": MarketType.TOTAL_POINTS,
            "over_under": MarketType.TOTAL_POINTS,
        }

        normalized = market_type_str.lower().replace(" ", "_")
        return market_type_mapping.get(normalized, market_type_str)


def save_scrape_result_to_db(result: ScrapeResult, scrape_session_id: Optional[str] = None) -> Dict[str, int]:
    """
    Convenience function to save scrape result.

    Args:
        result: ScrapeResult from scraper
        scrape_session_id: Optional session ID (generated if not provided)

    Returns:
        Dict with save statistics
    """
    if not scrape_session_id:
        scrape_session_id = f"{result.bookmaker_code}_{datetime.now(timezone.utc).isoformat()}"

    db = SessionLocal()
    try:
        persistence = OddsPersistence(db)
        stats = persistence.save_scrape_result(result, scrape_session_id)
        return stats
    finally:
        db.close()
