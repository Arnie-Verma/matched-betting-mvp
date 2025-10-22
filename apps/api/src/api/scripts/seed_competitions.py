#!/usr/bin/env python3
"""
Seed all sports and competitions to match Outmatched.com
"""
import logging
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.core.database import SessionLocal
from api.models import Sport, Competition

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Competition data: (sport_code, sport_name, competition_short_name, competition_full_name, country)
COMPETITIONS = [
    # Soccer/Football
    ("soccer", "Soccer", "EPL", "English Premier League", "GB"),
    ("soccer", "Soccer", "La Liga", "Spanish La Liga", "ES"),
    ("soccer", "Soccer", "Bundesliga", "German Bundesliga", "DE"),
    ("soccer", "Soccer", "Serie A", "Italian Serie A", "IT"),
    ("soccer", "Soccer", "Ligue 1", "French Ligue 1", "FR"),
    ("soccer", "Soccer", "UCL", "UEFA Champions League", "EU"),
    ("soccer", "Soccer", "A-League", "A-League Men", "AU"),
    ("soccer", "Soccer", "MLS", "Major League Soccer", "US"),

    # Australian Rules Football
    ("afl", "AFL", "AFL", "Australian Football League", "AU"),

    # Rugby League
    ("nrl", "NRL", "NRL", "National Rugby League", "AU"),

    # Basketball
    ("basketball", "Basketball", "NBA", "National Basketball Association", "US"),
    ("basketball", "Basketball", "NBL", "National Basketball League", "AU"),

    # Ice Hockey
    ("hockey", "Ice Hockey", "NHL", "National Hockey League", "US"),

    # Boxing
    ("boxing", "Boxing", "Boxing", "Boxing", "INT"),
]


def seed_competitions():
    """Seed all sports and competitions"""
    logger.info("Seeding sports and competitions...")

    db = SessionLocal()

    try:
        sports_created = 0
        competitions_created = 0

        for sport_code, sport_name, comp_short, comp_full, country in COMPETITIONS:
            # Get or create sport
            sport = db.query(Sport).filter(Sport.code == sport_code).first()
            if not sport:
                sport = Sport(
                    code=sport_code,
                    name=sport_name,  # Required field
                    display_name=sport_name,
                    is_active=True
                )
                db.add(sport)
                db.flush()
                sports_created += 1
                logger.info(f"Created sport: {sport_name}")

            # Get or create competition
            competition = db.query(Competition).filter(
                Competition.sport_id == sport.id,
                Competition.short_name == comp_short
            ).first()

            if not competition:
                competition = Competition(
                    sport_id=sport.id,
                    name=comp_full,
                    short_name=comp_short,
                    country=country,
                    is_active=True
                )
                db.add(competition)
                competitions_created += 1
                logger.info(f"Created competition: {comp_short} ({comp_full})")

        db.commit()

        logger.info(f"✅ Seeded {sports_created} sports and {competitions_created} competitions")

    except Exception as e:
        logger.error(f"❌ Error seeding competitions: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_competitions()
    logger.info("✅ Competition seeding completed!")
