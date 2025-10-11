"""
Seed mock Betfair odds for testing matched betting.

This script creates realistic Betfair lay odds based on existing TAB back odds.
Lay odds are typically 1-3% higher than back odds to create a small qualifying loss.

Run with:
    python -m api.scripts.seed_mock_betfair_odds
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.orm import Session
from api.core.database import SessionLocal
from api.models import Bookmaker, OddsSnapshot, Selection
from decimal import Decimal
from datetime import datetime, timezone
import logging
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_mock_betfair_odds(db: Session):
    """Create mock Betfair odds for all selections that have TAB odds"""

    logger.info("Seeding mock Betfair odds...")

    # Get Betfair bookmaker
    betfair = db.query(Bookmaker).filter(Bookmaker.code == "betfair").first()
    if not betfair:
        logger.error("Betfair bookmaker not found!")
        return

    # Get all current TAB odds
    tab = db.query(Bookmaker).filter(Bookmaker.code == "tab").first()
    if not tab:
        logger.error("TAB bookmaker not found!")
        return

    tab_odds = db.query(OddsSnapshot).filter(
        OddsSnapshot.bookmaker_id == tab.id,
        OddsSnapshot.is_current == True
    ).all()

    logger.info(f"Found {len(tab_odds)} TAB odds to match")

    created_count = 0
    for tab_odd in tab_odds:
        # Check if Betfair odds already exist for this selection
        existing = db.query(OddsSnapshot).filter(
            OddsSnapshot.selection_id == tab_odd.selection_id,
            OddsSnapshot.bookmaker_id == betfair.id,
            OddsSnapshot.is_current == True
        ).first()

        if existing:
            continue  # Skip if already exists

        # Create Betfair odds slightly higher than TAB (1-3% spread)
        # This creates realistic qualifying losses for normal bets
        spread_pct = Decimal(str(random.uniform(0.01, 0.03)))  # 1-3% spread
        betfair_odds = tab_odd.decimal_odds * (Decimal("1") + spread_pct)
        betfair_odds = betfair_odds.quantize(Decimal("0.01"))

        # Random liquidity between $500 and $50,000
        liquidity = Decimal(str(random.randint(500, 50000)))

        # Create Betfair odds snapshot
        betfair_snapshot = OddsSnapshot(
            selection_id=tab_odd.selection_id,
            bookmaker_id=betfair.id,
            decimal_odds=betfair_odds,
            available_amount=liquidity,
            is_current=True,
            timestamp=datetime.now(timezone.utc),
            source_type="mock",  # Mark as mock data
            confidence_score=Decimal("1.0")
        )

        db.add(betfair_snapshot)
        created_count += 1

    db.commit()
    logger.info(f"✅ Created {created_count} mock Betfair odds")


def main():
    """Run seed"""
    logger.info("Seeding mock Betfair odds...")

    db = SessionLocal()
    try:
        seed_mock_betfair_odds(db)
        logger.info("✅ Mock Betfair odds seeding completed!")

    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
