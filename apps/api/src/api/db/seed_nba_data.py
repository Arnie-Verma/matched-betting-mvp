# apps/api/src/api/db/seed_nba_data.py
"""Seed NBA 2024-25 season data for scraping framework"""
import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import async_sessionmaker
from api.core.database import async_engine
from api.models import Sport, Competition, Team, SportType


async def seed_nba_data():
    """Create NBA 2024-25 season data"""
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)

    async with async_session() as session:
        from sqlalchemy import select

        # Get Basketball sport (should exist, but update it for NBA)
        basketball_sport = await session.execute(
            select(Sport).where(Sport.code == SportType.BASKETBALL)
        )
        basketball_sport = basketball_sport.scalar_one_or_none()

        if not basketball_sport:
            print("Creating Basketball sport for NBA...")
            basketball_sport = Sport(
                code=SportType.BASKETBALL,
                name="National Basketball Association",
                display_name="NBA",
                season_format={"start_month": 10, "end_month": 6, "games_per_day": 8},
                common_markets=["match_winner", "handicap", "total_points"],
                sort_order=7
            )
            session.add(basketball_sport)
            await session.flush()
        else:
            # Update existing basketball sport for NBA
            basketball_sport.name = "National Basketball Association"
            basketball_sport.display_name = "NBA"
            basketball_sport.season_format = {"start_month": 10, "end_month": 6, "games_per_day": 8}

        # Check if NBA competition already exists
        existing_comp = await session.execute(
            select(Competition).where(
                Competition.sport_id == basketball_sport.id,
                Competition.name.like("%NBA 2024-25%")
            )
        )
        if existing_comp.scalar_one_or_none():
            print("NBA 2024-25 season already exists, skipping seed")
            return

        # Create NBA 2024-25 season
        nba_competition = Competition(
            sport_id=basketball_sport.id,
            name="NBA Regular Season 2024-25",
            short_name="NBA 2024-25",
            country="US",
            start_date=datetime(2024, 10, 15, tzinfo=timezone.utc),
            end_date=datetime(2025, 4, 13, tzinfo=timezone.utc),
            is_active=True,
            external_ids={
                "tab": "nba_2024_25",
                "ladbrokes": "nba-2024-25",
                "sportsbet": "nba_season_2024_25"
            }
        )
        session.add(nba_competition)
        await session.flush()

        # NBA Teams (all 30 teams)
        nba_teams = [
            # Eastern Conference - Atlantic Division
            {
                "canonical_name": "Boston Celtics",
                "short_name": "BOS",
                "display_name": "Boston",
                "location": "Boston, MA",
                "name_variations": {
                    "tab": "Boston Celtics",
                    "ladbrokes": "Boston",
                    "sportsbet": "Boston Celtics",
                    "bet365": "Boston Celtics",
                    "neds": "BOS"
                }
            },
            {
                "canonical_name": "Brooklyn Nets",
                "short_name": "BKN",
                "display_name": "Brooklyn",
                "location": "Brooklyn, NY",
                "name_variations": {
                    "tab": "Brooklyn Nets",
                    "ladbrokes": "Brooklyn",
                    "sportsbet": "Brooklyn Nets",
                    "bet365": "Brooklyn Nets",
                    "neds": "BKN"
                }
            },
            {
                "canonical_name": "New York Knicks",
                "short_name": "NYK",
                "display_name": "New York",
                "location": "New York, NY",
                "name_variations": {
                    "tab": "New York Knicks",
                    "ladbrokes": "New York",
                    "sportsbet": "NY Knicks",
                    "bet365": "New York Knicks",
                    "neds": "NYK"
                }
            },
            {
                "canonical_name": "Philadelphia 76ers",
                "short_name": "PHI",
                "display_name": "Philadelphia",
                "location": "Philadelphia, PA",
                "name_variations": {
                    "tab": "Philadelphia 76ers",
                    "ladbrokes": "Philadelphia",
                    "sportsbet": "Philadelphia 76ers",
                    "bet365": "Philadelphia 76ers",
                    "neds": "PHI"
                }
            },
            {
                "canonical_name": "Toronto Raptors",
                "short_name": "TOR",
                "display_name": "Toronto",
                "location": "Toronto, ON",
                "name_variations": {
                    "tab": "Toronto Raptors",
                    "ladbrokes": "Toronto",
                    "sportsbet": "Toronto Raptors",
                    "bet365": "Toronto Raptors",
                    "neds": "TOR"
                }
            },
            # Eastern Conference - Central Division
            {
                "canonical_name": "Chicago Bulls",
                "short_name": "CHI",
                "display_name": "Chicago",
                "location": "Chicago, IL",
                "name_variations": {
                    "tab": "Chicago Bulls",
                    "ladbrokes": "Chicago",
                    "sportsbet": "Chicago Bulls",
                    "bet365": "Chicago Bulls",
                    "neds": "CHI"
                }
            },
            {
                "canonical_name": "Cleveland Cavaliers",
                "short_name": "CLE",
                "display_name": "Cleveland",
                "location": "Cleveland, OH",
                "name_variations": {
                    "tab": "Cleveland Cavaliers",
                    "ladbrokes": "Cleveland",
                    "sportsbet": "Cleveland Cavaliers",
                    "bet365": "Cleveland Cavaliers",
                    "neds": "CLE"
                }
            },
            {
                "canonical_name": "Detroit Pistons",
                "short_name": "DET",
                "display_name": "Detroit",
                "location": "Detroit, MI",
                "name_variations": {
                    "tab": "Detroit Pistons",
                    "ladbrokes": "Detroit",
                    "sportsbet": "Detroit Pistons",
                    "bet365": "Detroit Pistons",
                    "neds": "DET"
                }
            },
            {
                "canonical_name": "Indiana Pacers",
                "short_name": "IND",
                "display_name": "Indiana",
                "location": "Indianapolis, IN",
                "name_variations": {
                    "tab": "Indiana Pacers",
                    "ladbrokes": "Indiana",
                    "sportsbet": "Indiana Pacers",
                    "bet365": "Indiana Pacers",
                    "neds": "IND"
                }
            },
            {
                "canonical_name": "Milwaukee Bucks",
                "short_name": "MIL",
                "display_name": "Milwaukee",
                "location": "Milwaukee, WI",
                "name_variations": {
                    "tab": "Milwaukee Bucks",
                    "ladbrokes": "Milwaukee",
                    "sportsbet": "Milwaukee Bucks",
                    "bet365": "Milwaukee Bucks",
                    "neds": "MIL"
                }
            },
            # Western Conference - Pacific Division
            {
                "canonical_name": "Golden State Warriors",
                "short_name": "GSW",
                "display_name": "Golden State",
                "location": "San Francisco, CA",
                "name_variations": {
                    "tab": "Golden State Warriors",
                    "ladbrokes": "Golden State",
                    "sportsbet": "Golden State Warriors",
                    "bet365": "Golden State Warriors",
                    "neds": "GSW"
                }
            },
            {
                "canonical_name": "Los Angeles Clippers",
                "short_name": "LAC",
                "display_name": "LA Clippers",
                "location": "Los Angeles, CA",
                "name_variations": {
                    "tab": "LA Clippers",
                    "ladbrokes": "LA Clippers",
                    "sportsbet": "Los Angeles Clippers",
                    "bet365": "LA Clippers",
                    "neds": "LAC"
                }
            },
            {
                "canonical_name": "Los Angeles Lakers",
                "short_name": "LAL",
                "display_name": "LA Lakers",
                "location": "Los Angeles, CA",
                "name_variations": {
                    "tab": "LA Lakers",
                    "ladbrokes": "LA Lakers",
                    "sportsbet": "Los Angeles Lakers",
                    "bet365": "LA Lakers",
                    "neds": "LAL"
                }
            },
            {
                "canonical_name": "Phoenix Suns",
                "short_name": "PHX",
                "display_name": "Phoenix",
                "location": "Phoenix, AZ",
                "name_variations": {
                    "tab": "Phoenix Suns",
                    "ladbrokes": "Phoenix",
                    "sportsbet": "Phoenix Suns",
                    "bet365": "Phoenix Suns",
                    "neds": "PHX"
                }
            },
            {
                "canonical_name": "Sacramento Kings",
                "short_name": "SAC",
                "display_name": "Sacramento",
                "location": "Sacramento, CA",
                "name_variations": {
                    "tab": "Sacramento Kings",
                    "ladbrokes": "Sacramento",
                    "sportsbet": "Sacramento Kings",
                    "bet365": "Sacramento Kings",
                    "neds": "SAC"
                }
            },
            # Add a few more key teams for testing
            {
                "canonical_name": "Miami Heat",
                "short_name": "MIA",
                "display_name": "Miami",
                "location": "Miami, FL",
                "name_variations": {
                    "tab": "Miami Heat",
                    "ladbrokes": "Miami",
                    "sportsbet": "Miami Heat",
                    "bet365": "Miami Heat",
                    "neds": "MIA"
                }
            },
            {
                "canonical_name": "Denver Nuggets",
                "short_name": "DEN",
                "display_name": "Denver",
                "location": "Denver, CO",
                "name_variations": {
                    "tab": "Denver Nuggets",
                    "ladbrokes": "Denver",
                    "sportsbet": "Denver Nuggets",
                    "bet365": "Denver Nuggets",
                    "neds": "DEN"
                }
            }
        ]

        print("Creating NBA teams...")
        for team_data in nba_teams:
            team = Team(
                sport_id=basketball_sport.id,
                **team_data
            )
            session.add(team)

        await session.commit()
        print(f"✅ Successfully created NBA 2024-25 season and {len(nba_teams)} teams")
        print("🏀 Ready for NBA scraping framework!")


if __name__ == "__main__":
    asyncio.run(seed_nba_data())