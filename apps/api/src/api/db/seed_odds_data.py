# apps/api/src/api/db/seed_odds_data.py
"""Seed the database with initial Australian sports and bookmaker data"""
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import async_sessionmaker
from api.core.database import async_engine
from api.models import (
    Sport, SportType, Bookmaker, SourceType, Competition, Team
)


async def seed_sports():
    """Create initial Australian sports data"""
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)

    sports_data = [
        {
            "code": SportType.AFL,
            "name": "Australian Football League",
            "display_name": "AFL",
            "season_format": {"start_month": 3, "end_month": 9, "rounds": 23},
            "common_markets": ["match_winner", "handicap", "total_points", "first_goalscorer"],
            "sort_order": 1
        },
        {
            "code": SportType.NRL,
            "name": "National Rugby League",
            "display_name": "NRL",
            "season_format": {"start_month": 3, "end_month": 10, "rounds": 27},
            "common_markets": ["match_winner", "handicap", "total_points", "first_tryscorer"],
            "sort_order": 2
        },
        {
            "code": SportType.CRICKET,
            "name": "Cricket",
            "display_name": "Cricket",
            "season_format": {"start_month": 10, "end_month": 4},
            "common_markets": ["match_winner", "total_runs", "top_batsman", "top_bowler"],
            "sort_order": 3
        },
        {
            "code": SportType.TENNIS,
            "name": "Tennis",
            "display_name": "Tennis",
            "season_format": {"year_round": True},
            "common_markets": ["match_winner", "set_betting", "total_games"],
            "sort_order": 4
        },
        {
            "code": SportType.HORSE_RACING,
            "name": "Horse Racing",
            "display_name": "Horse Racing",
            "season_format": {"year_round": True},
            "common_markets": ["win", "place", "each_way", "quinella", "trifecta"],
            "sort_order": 5
        },
        {
            "code": SportType.SOCCER,
            "name": "Football (Soccer)",
            "display_name": "Soccer",
            "season_format": {"start_month": 9, "end_month": 5},
            "common_markets": ["match_winner", "total_goals", "both_teams_score"],
            "sort_order": 6
        }
    ]

    async with async_session() as session:
        # Check if sports already exist
        from sqlalchemy import text
        existing_sports = await session.execute(text("SELECT COUNT(*) FROM sports"))
        count = existing_sports.scalar()

        if count == 0:
            print("Creating initial sports data...")
            for sport_data in sports_data:
                sport = Sport(**sport_data)
                session.add(sport)

            await session.commit()
            print(f"Successfully created {len(sports_data)} sports")
        else:
            print(f"Sports already exist ({count} found), skipping seed")


async def seed_bookmakers():
    """Create initial Australian bookmaker data"""
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)

    bookmakers_data = [
        {
            "code": "sportsbet",
            "name": "Sportsbet",
            "display_name": "Sportsbet",
            "website_url": "https://www.sportsbet.com.au",
            "default_source_type": SourceType.SCRAPE,
            "base_url": "https://www.sportsbet.com.au",
            "rate_limit_seconds": 3,
            "supports_each_way": True,
            "scraping_config": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "headers": {"Accept": "application/json, text/plain, */*"},
                "selectors": {
                    "odds": ".market-odds",
                    "event_name": ".event-name",
                    "market_name": ".market-header"
                }
            }
        },
        {
            "code": "tab",
            "name": "TAB",
            "display_name": "TAB",
            "website_url": "https://www.tab.com.au",
            "default_source_type": SourceType.SCRAPE,
            "base_url": "https://www.tab.com.au",
            "rate_limit_seconds": 5,
            "supports_each_way": True,
            "scraping_config": {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "headers": {"Accept": "application/json"},
                "requires_js": True
            }
        },
        {
            "code": "ladbrokes",
            "name": "Ladbrokes",
            "display_name": "Ladbrokes",
            "website_url": "https://www.ladbrokes.com.au",
            "default_source_type": SourceType.SCRAPE,
            "base_url": "https://www.ladbrokes.com.au",
            "rate_limit_seconds": 4,
            "supports_each_way": True,
            "scraping_config": {
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "headers": {"Accept": "application/json, text/html"},
                "anti_bot_detection": True
            }
        },
        {
            "code": "bet365",
            "name": "bet365",
            "display_name": "bet365",
            "website_url": "https://www.bet365.com.au",
            "default_source_type": SourceType.SCRAPE,
            "base_url": "https://www.bet365.com.au",
            "api_endpoint": "https://api.bet365.com/v1",  # Hypothetical - they don't offer public API
            "rate_limit_seconds": 10,  # More conservative due to strict anti-bot
            "supports_each_way": True,
            "scraping_config": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "requires_proxy": True,
                "requires_js": True,
                "anti_bot_detection": True,
                "captcha_detection": True
            }
        },
        {
            "code": "neds",
            "name": "Neds",
            "display_name": "Neds",
            "website_url": "https://www.neds.com.au",
            "default_source_type": SourceType.SCRAPE,
            "base_url": "https://www.neds.com.au",
            "rate_limit_seconds": 3,
            "supports_each_way": False,
            "scraping_config": {
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15",
                "headers": {"Accept": "application/json"},
                "mobile_optimized": True
            }
        },
        {
            "code": "pointsbet",
            "name": "PointsBet",
            "display_name": "PointsBet",
            "website_url": "https://www.pointsbet.com.au",
            "default_source_type": SourceType.SCRAPE,
            "base_url": "https://www.pointsbet.com.au",
            "rate_limit_seconds": 4,
            "supports_each_way": False,
            "scraping_config": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "headers": {"Accept": "application/json"},
                "requires_js": True
            }
        },
        {
            "code": "unibet",
            "name": "Unibet",
            "display_name": "Unibet",
            "website_url": "https://www.unibet.com.au",
            "is_active": False,  # Phase A freeze: keep disabled until hardening GO
            "default_source_type": SourceType.SCRAPE,
            "base_url": "https://www.unibet.com.au",
            "rate_limit_seconds": 5,
            "supports_each_way": True,
            "scraping_config": {
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
                "headers": {"Accept": "application/json, text/html"},
                "requires_js": True,
                "onboarding_frozen": True,
            }
        }
    ]

    async with async_session() as session:
        # Check if bookmakers already exist
        from sqlalchemy import text
        existing_bookmakers = await session.execute(text("SELECT COUNT(*) FROM bookmakers"))
        count = existing_bookmakers.scalar()

        if count == 0:
            print("Creating initial bookmaker data...")
            for bookmaker_data in bookmakers_data:
                bookmaker = Bookmaker(**bookmaker_data)
                session.add(bookmaker)

            await session.commit()
            print(f"Successfully created {len(bookmakers_data)} bookmakers")
        else:
            print(f"Bookmakers already exist ({count} found), skipping seed")


async def seed_sample_afl_data():
    """Create sample AFL competition and teams for demonstration"""
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)

    async with async_session() as session:
        from sqlalchemy import select

        # Get AFL sport
        afl_sport = await session.execute(
            select(Sport).where(Sport.code == SportType.AFL)
        )
        afl_sport = afl_sport.scalar_one_or_none()

        if not afl_sport:
            print("AFL sport not found, skipping sample data")
            return

        # Check if AFL competition already exists
        existing_comp = await session.execute(
            select(Competition).where(Competition.sport_id == afl_sport.id)
        )
        if existing_comp.scalar_one_or_none():
            print("AFL competition already exists, skipping sample data")
            return

        # Create AFL 2025 season
        afl_competition = Competition(
            sport_id=afl_sport.id,
            name="AFL Premiership Season 2025",
            short_name="AFL 2025",
            country="AU",
            start_date=datetime(2025, 3, 20, tzinfo=timezone.utc),
            end_date=datetime(2025, 9, 28, tzinfo=timezone.utc),
            is_active=True,
            external_ids={
                "sportsbet": "afl_2025_prem",
                "tab": "afl2025",
                "bet365": "afl_premiership_2025"
            }
        )
        session.add(afl_competition)
        await session.flush()  # Get the ID

        # Create sample AFL teams
        afl_teams = [
            {
                "canonical_name": "Richmond Tigers",
                "short_name": "RICH",
                "display_name": "Richmond",
                "location": "Melbourne, VIC",
                "name_variations": {
                    "sportsbet": "Richmond",
                    "tab": "Tigers",
                    "bet365": "Richmond Tigers",
                    "ladbrokes": "Richmond",
                    "neds": "RICH"
                }
            },
            {
                "canonical_name": "Collingwood Magpies",
                "short_name": "COLL",
                "display_name": "Collingwood",
                "location": "Melbourne, VIC",
                "name_variations": {
                    "sportsbet": "Collingwood",
                    "tab": "Magpies",
                    "bet365": "Collingwood Magpies",
                    "ladbrokes": "Collingwood",
                    "neds": "COLL"
                }
            },
            {
                "canonical_name": "Melbourne Demons",
                "short_name": "MELB",
                "display_name": "Melbourne",
                "location": "Melbourne, VIC",
                "name_variations": {
                    "sportsbet": "Melbourne",
                    "tab": "Demons",
                    "bet365": "Melbourne Demons",
                    "ladbrokes": "Melbourne",
                    "neds": "MELB"
                }
            },
            {
                "canonical_name": "Brisbane Lions",
                "short_name": "BRIS",
                "display_name": "Brisbane",
                "location": "Brisbane, QLD",
                "name_variations": {
                    "sportsbet": "Brisbane Lions",
                    "tab": "Lions",
                    "bet365": "Brisbane",
                    "ladbrokes": "Brisbane Lions",
                    "neds": "BRIS"
                }
            }
        ]

        print("Creating sample AFL teams...")
        for team_data in afl_teams:
            team = Team(
                sport_id=afl_sport.id,
                **team_data
            )
            session.add(team)

        await session.commit()
        print(f"Successfully created AFL competition and {len(afl_teams)} teams")


async def main():
    """Run all seed functions"""
    print("🚀 Seeding Australian matched betting data...")

    await seed_sports()
    await seed_bookmakers()
    await seed_sample_afl_data()

    print("✅ All seed data created successfully!")
    print("\nNext steps:")
    print("- Sports: 6 Australian sports configured")
    print("- Bookmakers: 7 major AU bookmakers added")
    print("- Sample Data: AFL 2025 season with 4 teams")
    print("- Ready for Step 4: Scraping Framework")


if __name__ == "__main__":
    asyncio.run(main())
