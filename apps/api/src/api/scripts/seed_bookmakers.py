"""
Seed script for bookmakers and sports taxonomy.

Populates the database with:
- Australian bookmakers (TAB, Ladbrokes, Betfair, etc.)
- Sports taxonomy (AFL, NRL, Cricket, etc.)
- Common competitions

Run with:
    python -m api.scripts.seed_bookmakers
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.orm import Session
from api.core.database import SessionLocal
from api.models import Sport, Bookmaker, Competition
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_sports(db: Session):
    """Seed sports taxonomy"""
    logger.info("Seeding sports...")

    sports_data = [
        {
            "code": "afl",
            "name": "Australian Football League",
            "display_name": "AFL",
            "sort_order": 1,
            "season_format": {"start_month": 3, "end_month": 9},
            "common_markets": ["match_winner", "handicap", "total_points"]
        },
        {
            "code": "nrl",
            "name": "National Rugby League",
            "display_name": "NRL",
            "sort_order": 2,
            "season_format": {"start_month": 3, "end_month": 10},
            "common_markets": ["match_winner", "handicap", "total_points"]
        },
        {
            "code": "cricket",
            "name": "Cricket",
            "display_name": "Cricket",
            "sort_order": 3,
            "common_markets": ["match_winner", "total_runs", "first_innings_lead"]
        },
        {
            "code": "tennis",
            "name": "Tennis",
            "display_name": "Tennis",
            "sort_order": 4,
            "common_markets": ["match_winner", "set_winner", "game_handicap"]
        },
        {
            "code": "soccer",
            "name": "Soccer",
            "display_name": "Soccer",
            "sort_order": 5,
            "common_markets": ["match_winner", "total_goals", "both_teams_to_score"]
        },
        {
            "code": "basketball",
            "name": "Basketball",
            "display_name": "Basketball",
            "sort_order": 6,
            "common_markets": ["match_winner", "handicap", "total_points"]
        },
        {
            "code": "horse_racing",
            "name": "Horse Racing",
            "display_name": "Horse Racing",
            "sort_order": 7,
            "common_markets": ["win", "place", "each_way"]
        },
    ]

    for sport_data in sports_data:
        # Check if exists
        existing = db.query(Sport).filter(Sport.code == sport_data["code"]).first()
        if existing:
            logger.info(f"Sport {sport_data['code']} already exists, skipping")
            continue

        sport = Sport(**sport_data)
        db.add(sport)
        logger.info(f"Created sport: {sport_data['display_name']}")

    db.commit()
    logger.info("Sports seeded successfully")


def seed_bookmakers(db: Session):
    """Seed Australian bookmakers"""
    logger.info("Seeding bookmakers...")

    bookmakers_data = [
        {
            "code": "tab",
            "name": "TAB",
            "display_name": "TAB",
            "website_url": "https://www.tab.com.au",
            "country": "AU",
            "is_active": True,
            "supports_each_way": True,
            "default_source_type": "api",
            "base_url": "https://api.beta.tab.com.au",
            "api_endpoint": "https://api.beta.tab.com.au/v1/tab-info-service",
            "rate_limit_seconds": 2,
            "scraping_config": {
                "type": "api",
                "auth_required": False,
                "notes": "TAB has a public API used by their website"
            }
        },
        {
            "code": "ladbrokes",
            "name": "Ladbrokes",
            "display_name": "Ladbrokes",
            "website_url": "https://www.ladbrokes.com.au",
            "country": "AU",
            "is_active": True,
            "supports_each_way": True,
            "default_source_type": "api",
            "base_url": "https://www.ladbrokes.com.au",
            "rate_limit_seconds": 2,
            "scraping_config": {
                "type": "api",
                "auth_required": False,
                "notes": "Ladbrokes may use GraphQL or REST API"
            }
        },
        {
            "code": "betfair",
            "name": "Betfair Exchange",
            "display_name": "Betfair",
            "website_url": "https://www.betfair.com.au",
            "country": "AU",
            "is_active": True,
            "supports_each_way": True,
            "default_source_type": "api",
            "base_url": "https://api.betfair.com",
            "api_endpoint": "https://api.betfair.com/exchange/betting/rest/v1.0",
            "rate_limit_seconds": 1,
            "scraping_config": {
                "type": "api",
                "auth_required": True,
                "api_key_required": True,
                "notes": "Betfair has official API requiring app key and session token"
            }
        },
        # Additional bookmakers for premium/diamond tiers
        {
            "code": "sportsbet",
            "name": "Sportsbet",
            "display_name": "Sportsbet",
            "website_url": "https://www.sportsbet.com.au",
            "country": "AU",
            "is_active": True,
            "default_source_type": "scrape",
            "base_url": "https://www.sportsbet.com.au",
            "rate_limit_seconds": 3
        },
        {
            "code": "neds",
            "name": "Neds",
            "display_name": "Neds",
            "website_url": "https://www.neds.com.au",
            "country": "AU",
            "is_active": True,
            "default_source_type": "scrape",
            "base_url": "https://www.neds.com.au",
            "rate_limit_seconds": 3
        },
        {
            "code": "pointsbet",
            "name": "PointsBet",
            "display_name": "PointsBet",
            "website_url": "https://www.pointsbet.com.au",
            "country": "AU",
            "is_active": True,
            "default_source_type": "api",
            "base_url": "https://www.pointsbet.com.au",
            "rate_limit_seconds": 2
        },
        {
            "code": "unibet",
            "name": "Unibet",
            "display_name": "Unibet",
            "website_url": "https://www.unibet.com.au",
            "country": "AU",
            "is_active": False,  # Phase A freeze: keep disabled until hardening GO
            "default_source_type": "api",
            "base_url": "https://www.unibet.com.au",
            "rate_limit_seconds": 2
        },
    ]

    for bm_data in bookmakers_data:
        # Check if exists
        existing = db.query(Bookmaker).filter(Bookmaker.code == bm_data["code"]).first()
        if existing:
            logger.info(f"Bookmaker {bm_data['code']} already exists, skipping")
            continue

        bookmaker = Bookmaker(**bm_data)
        db.add(bookmaker)
        logger.info(f"Created bookmaker: {bm_data['display_name']}")

    db.commit()
    logger.info("Bookmakers seeded successfully")


def seed_competitions(db: Session):
    """Seed common Australian competitions"""
    logger.info("Seeding competitions...")

    # Get sports
    afl_sport = db.query(Sport).filter(Sport.code == "afl").first()
    nrl_sport = db.query(Sport).filter(Sport.code == "nrl").first()
    cricket_sport = db.query(Sport).filter(Sport.code == "cricket").first()

    if not afl_sport or not nrl_sport:
        logger.warning("Sports not found, skipping competitions")
        return

    competitions_data = [
        {
            "sport_id": afl_sport.id,
            "name": "AFL Premiership Season 2025",
            "short_name": "AFL 2025",
            "country": "AU",
            "is_active": True
        },
        {
            "sport_id": nrl_sport.id,
            "name": "NRL Premiership 2025",
            "short_name": "NRL 2025",
            "country": "AU",
            "is_active": True
        },
    ]

    if cricket_sport:
        competitions_data.append({
            "sport_id": cricket_sport.id,
            "name": "Big Bash League 2024/25",
            "short_name": "BBL 2024/25",
            "country": "AU",
            "is_active": True
        })

    for comp_data in competitions_data:
        # Check if exists
        existing = db.query(Competition).filter(
            Competition.sport_id == comp_data["sport_id"],
            Competition.short_name == comp_data["short_name"]
        ).first()

        if existing:
            logger.info(f"Competition {comp_data['short_name']} already exists, skipping")
            continue

        competition = Competition(**comp_data)
        db.add(competition)
        logger.info(f"Created competition: {comp_data['short_name']}")

    db.commit()
    logger.info("Competitions seeded successfully")


def main():
    """Run all seed functions"""
    logger.info("Starting database seeding...")

    db = SessionLocal()
    try:
        seed_sports(db)
        seed_bookmakers(db)
        seed_competitions(db)

        logger.info("Database seeding completed successfully!")

    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
