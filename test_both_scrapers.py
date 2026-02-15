"""
Test script to run both TAB and Betfair scrapers together and see how events match.

Run from inside the mb_api container:
    docker exec -it mb_api python test_both_scrapers.py
"""
import sys

# This file is a manual smoke-test script (see __main__). Skip under pytest so
# it doesn't run as part of the automated test suite.
if "pytest" in sys.modules:
    import pytest

    pytest.skip("Manual TAB+Betfair smoke-test script (run directly).", allow_module_level=True)

sys.path.insert(0, "apps/worker/src")

import asyncio
import logging
from difflib import SequenceMatcher
from scrapers.tab_scraper import TABScraper
from scrapers.betfair_scraper import BetfairScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def fuzzy_match_score(str1: str, str2: str) -> float:
    """
    Calculate fuzzy match score between two strings (0.0 to 1.0).
    Uses SequenceMatcher for similarity comparison.
    """
    # Normalize strings: lowercase, remove extra spaces
    s1 = " ".join(str1.lower().split())
    s2 = " ".join(str2.lower().split())

    return SequenceMatcher(None, s1, s2).ratio()


def normalize_team_name(name: str) -> str:
    """Normalize team names for better matching"""
    # Common abbreviations
    replacements = {
        "nottm": "nottingham",
        "man utd": "manchester united",
        "man city": "manchester city",
        "wolves": "wolverhampton",
        "spurs": "tottenham",
        "west ham": "west ham united",
        "brighton": "brighton & hove albion",
        "newcastle": "newcastle united",
    }

    normalized = name.lower()
    for abbr, full in replacements.items():
        if abbr in normalized:
            normalized = normalized.replace(abbr, full)

    return normalized


def find_matching_events(tab_events, betfair_events, threshold=0.7):
    """
    Find matching events between TAB and Betfair using fuzzy name matching.

    Returns:
        List of tuples (tab_event, betfair_event, match_score)
    """
    matches = []

    for tab_event in tab_events:
        best_match = None
        best_score = 0.0

        for betfair_event in betfair_events:
            # Compare event names
            score = fuzzy_match_score(
                normalize_team_name(tab_event.name),
                normalize_team_name(betfair_event.name)
            )

            if score > best_score:
                best_score = score
                best_match = betfair_event

        if best_score >= threshold:
            matches.append((tab_event, best_match, best_score))
            logger.info(f"Match found ({best_score:.2f}): TAB '{tab_event.name}' <-> Betfair '{best_match.name}'")
        else:
            logger.warning(f"No match for TAB event: {tab_event.name} (best score: {best_score:.2f})")

    return matches


async def test_both_scrapers():
    """Test both scrapers and match events"""

    logger.info("="*80)
    logger.info("TESTING TAB + BETFAIR SCRAPERS TOGETHER")
    logger.info("="*80)

    # Run TAB scraper
    logger.info("\n🔍 Scraping TAB for EPL odds...")
    tab_scraper = TABScraper()
    tab_result = await tab_scraper.scrape_sport(sport="soccer", limit=10)

    logger.info(f"\nTAB Results:")
    logger.info(f"  Status: {tab_result.status}")
    logger.info(f"  Events: {tab_result.events_scraped}")
    logger.info(f"  Odds: {tab_result.odds_scraped}")

    if tab_result.errors:
        logger.warning(f"  Errors: {tab_result.errors}")

    # Run Betfair scraper
    logger.info("\n🔍 Scraping Betfair for EPL odds...")
    betfair_scraper = BetfairScraper()
    betfair_result = await betfair_scraper.scrape_sport(sport="soccer", limit=10)

    logger.info(f"\nBetfair Results:")
    logger.info(f"  Status: {betfair_result.status}")
    logger.info(f"  Events: {betfair_result.events_scraped}")
    logger.info(f"  Odds: {betfair_result.odds_scraped}")

    if betfair_result.errors:
        logger.warning(f"  Errors: {betfair_result.errors}")

    # Display TAB events
    logger.info("\n" + "="*80)
    logger.info("TAB EVENTS")
    logger.info("="*80)
    for i, event in enumerate(tab_result.events, 1):
        logger.info(f"\n[{i}] {event.name}")
        logger.info(f"    Competition: {event.competition}")
        logger.info(f"    Start: {event.start_time}")
        logger.info(f"    Odds: {len(event.odds)} (back odds)")
        for odds in event.odds[:3]:
            logger.info(f"      {odds.selection_name}: {odds.decimal_odds}")

    # Display Betfair events
    logger.info("\n" + "="*80)
    logger.info("BETFAIR EVENTS")
    logger.info("="*80)
    for i, event in enumerate(betfair_result.events, 1):
        logger.info(f"\n[{i}] {event.name}")
        logger.info(f"    Competition: {event.competition}")
        logger.info(f"    Start: {event.start_time}")
        logger.info(f"    Odds: {len(event.odds)} (lay odds)")
        for odds in event.odds[:3]:
            logger.info(f"      {odds.selection_name}: {odds.decimal_odds}")

    # Match events
    logger.info("\n" + "="*80)
    logger.info("MATCHING EVENTS BETWEEN TAB AND BETFAIR")
    logger.info("="*80)

    matches = find_matching_events(tab_result.events, betfair_result.events, threshold=0.7)

    logger.info(f"\nFound {len(matches)} matches out of {len(tab_result.events)} TAB events")

    # Display matched opportunities
    logger.info("\n" + "="*80)
    logger.info("MATCHED BETTING OPPORTUNITIES")
    logger.info("="*80)

    opportunity_count = 0
    for tab_event, betfair_event, match_score in matches:
        logger.info(f"\n{'='*60}")
        logger.info(f"Event: {tab_event.name}")
        logger.info(f"Match Score: {match_score:.2%}")
        logger.info(f"TAB: {tab_event.name}")
        logger.info(f"Betfair: {betfair_event.name}")
        logger.info(f"{'='*60}")

        # Match odds by selection (home/away/draw)
        tab_odds_by_selection = {odds.selection_key: odds for odds in tab_event.odds}
        betfair_odds_by_selection = {odds.selection_key: odds for odds in betfair_event.odds}

        for selection_key in ['home', 'away', 'draw']:
            if selection_key in tab_odds_by_selection and selection_key in betfair_odds_by_selection:
                tab_odds = tab_odds_by_selection[selection_key]
                betfair_odds = betfair_odds_by_selection[selection_key]

                opportunity_count += 1

                logger.info(f"\n  {tab_odds.selection_name}:")
                logger.info(f"    TAB Back:     {tab_odds.decimal_odds}")
                logger.info(f"    Betfair Lay:  {betfair_odds.decimal_odds}")

                # Quick profitability check
                back_odds = float(tab_odds.decimal_odds)
                lay_odds = float(betfair_odds.decimal_odds)
                commission = 0.02

                # Calculate if profitable (arbitrage)
                back_win_prob = 1 / back_odds
                lay_win_prob = 1 / lay_odds
                total_prob = back_win_prob + (lay_win_prob * (1 - commission))

                is_profitable = total_prob < 1.0
                profit_margin = (1.0 - total_prob) * 100 if is_profitable else (total_prob - 1.0) * -100

                if is_profitable:
                    logger.info(f"    ✅ PROFITABLE ARBIT RAGE: {profit_margin:.2f}% margin")
                else:
                    logger.info(f"    ℹ️  Qualifying loss: {profit_margin:.2f}%")

    logger.info("\n" + "="*80)
    logger.info("SUMMARY")
    logger.info("="*80)
    logger.info(f"TAB Events: {len(tab_result.events)}")
    logger.info(f"Betfair Events: {len(betfair_result.events)}")
    logger.info(f"Matched Events: {len(matches)}")
    logger.info(f"Total Opportunities: {opportunity_count}")
    logger.info("="*80)

    return tab_result, betfair_result, matches


if __name__ == "__main__":
    try:
        asyncio.run(test_both_scrapers())
        logger.info("\n✅ Test completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"\n💥 Test failed: {e}")
        sys.exit(1)
