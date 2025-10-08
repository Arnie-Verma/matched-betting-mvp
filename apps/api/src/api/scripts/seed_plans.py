"""
Seed pricing plans for the matched betting platform.

Free, Premium, and Platinum tiers with correct bookmaker counts.

Run with:
    python -m api.scripts.seed_plans
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.orm import Session
from api.core.database import SessionLocal
from api.models import Plan
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_plans(db: Session):
    """Seed the 3 pricing plans"""
    logger.info("Seeding pricing plans...")

    plans_data = [
        {
            "name": "free",
            "display_name": "Free",
            "description": "No credit card required",
            "price_monthly_cents": 0,
            "price_yearly_cents": 0,
            "stripe_price_monthly_id": None,
            "stripe_price_yearly_id": None,
            "is_active": True,
            "sort_order": 1,
            "features": {
                "bookmakers": 2,
                "odds_matcher": True,
                "feature_list": [
                    "Realtime odds comparison from 2 bookmakers",
                    "Make over $70",
                    "Learn the basics"
                ]
            }
        },
        {
            "name": "premium",
            "display_name": "Premium",
            "description": "Most popular plan",
            "price_monthly_cents": 2500,  # $25 AUD
            "price_yearly_cents": 25000,  # $250 AUD (2 months free)
            "stripe_price_monthly_id": None,  # Will be set when Stripe prices are created
            "stripe_price_yearly_id": None,
            "is_active": True,
            "sort_order": 2,
            "features": {
                "bookmakers": 16,
                "odds_matcher": True,
                "feature_list": [
                    "Realtime odds comparison from 16 bookmakers",
                    "Advanced matched betting calculators",
                    "Premium academy courses"
                ]
            }
        },
        {
            "name": "platinum",
            "display_name": "Diamond",
            "description": "Everything you need",
            "price_monthly_cents": 3500,  # $35 AUD
            "price_yearly_cents": 35000,  # $350 AUD (2 months free)
            "stripe_price_monthly_id": None,
            "stripe_price_yearly_id": None,
            "is_active": True,
            "sort_order": 3,
            "features": {
                "bookmakers": 103,
                "odds_matcher": True,
                "feature_list": [
                    "Realtime odds comparison from over 100 bookmakers",
                    "$1000s of dollars in sign up bonuses",
                    "Plus everything in premium"
                ]
            }
        }
    ]

    for plan_data in plans_data:
        # Check if exists
        existing = db.query(Plan).filter(Plan.name == plan_data["name"]).first()
        if existing:
            logger.info(f"Plan {plan_data['name']} exists, updating...")
            # Update existing plan
            for key, value in plan_data.items():
                setattr(existing, key, value)
        else:
            # Create new plan
            plan = Plan(**plan_data)
            db.add(plan)
            logger.info(f"Created plan: {plan_data['display_name']} (${plan_data['price_monthly_cents']/100}/mo)")

    db.commit()
    logger.info(f"✅ Seeded {len(plans_data)} pricing plans")


def main():
    """Run seed"""
    logger.info("Seeding pricing plans...")

    db = SessionLocal()
    try:
        seed_plans(db)
        logger.info("✅ Plans seeding completed!")

    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
