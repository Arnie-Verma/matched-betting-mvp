# apps/api/src/api/db/seed_plans.py
"""Seed the database with initial plan data"""
import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker
from api.core.database import async_engine
from api.models import Plan


async def seed_plans():
    """Create initial plan data in the database"""
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)

    plans_data = [
        {
            "name": "free",
            "display_name": "Free",
            "price_monthly_cents": None,
            "price_yearly_cents": None,
            "stripe_product_id": None,
            "stripe_price_monthly_id": None,
            "stripe_price_yearly_id": None,
            "features": {
                "max_bookmakers": 2,
                "max_bets_per_month": -1,
                "email_notifications": True,
                "mobile_app": False,
                "priority_support": False,
                "custom_alerts": False,
                "api_access": False
            },
            "description": "Perfect for getting started with matched betting",
            "is_active": True,
            "sort_order": 1
        },
        {
            "name": "premium",
            "display_name": "Premium",
            "price_monthly_cents": 2499,  # $24.99 AUD
            "price_yearly_cents": None,  # Monthly only
            "stripe_product_id": None,  # Will be set after Stripe product creation
            "stripe_price_monthly_id": None,
            "stripe_price_yearly_id": None,
            "features": {
                "max_bookmakers": 10,
                "max_bets_per_month": -1,
                "email_notifications": True,
                "mobile_app": True,
                "priority_support": False,
                "custom_alerts": True,
                "api_access": False
            },
            "description": "Great for regular matched bettors looking to scale up",
            "is_active": True,
            "sort_order": 2
        },
        {
            "name": "platinum",
            "display_name": "Platinum",
            "price_monthly_cents": 3499,  # $34.99 AUD
            "price_yearly_cents": None,  # Monthly only
            "stripe_product_id": None,  # Will be set after Stripe product creation
            "stripe_price_monthly_id": None,
            "stripe_price_yearly_id": None,
            "features": {
                "max_bookmakers": 100,  # 100+ bookmakers
                "max_bets_per_month": -1,  # Unlimited
                "email_notifications": True,
                "mobile_app": True,
                "priority_support": True,
                "custom_alerts": True,
                "api_access": True
            },
            "description": "For serious matched bettors and those running betting businesses",
            "is_active": True,
            "sort_order": 3
        }
    ]

    async with async_session() as session:
        # Check if plans already exist
        from sqlalchemy import text
        existing_plans = await session.execute(
            text("SELECT COUNT(*) FROM plans")
        )
        count = existing_plans.scalar()

        if count == 0:
            print("Creating initial plan data...")
            for plan_data in plans_data:
                plan = Plan(**plan_data)
                session.add(plan)

            await session.commit()
            print(f"Successfully created {len(plans_data)} plans")
        else:
            print(f"Plans already exist ({count} found), skipping seed")


if __name__ == "__main__":
    asyncio.run(seed_plans())