# apps/api/src/api/routers/metadata.py
"""
Metadata endpoints for fetching bookmakers, sports, competitions.
Used by frontend filters to populate dropdowns.
"""
from typing import List
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.auth import get_current_user, UserClaims
from api.models import Bookmaker, Sport, Competition


router = APIRouter(prefix="/metadata", tags=["metadata"])


class BookmakerResponse(BaseModel):
    id: int
    code: str
    display_name: str
    tier: str


class SportResponse(BaseModel):
    id: int
    code: str
    display_name: str


class CompetitionResponse(BaseModel):
    id: int
    sport_id: int
    short_name: str
    full_name: str


@router.get("/bookmakers")
async def get_bookmakers(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[BookmakerResponse]:
    """
    Get all bookmakers for filter dropdowns.
    Returns all bookmakers sorted alphabetically by display_name.
    """
    bookmakers = db.query(Bookmaker).order_by(Bookmaker.display_name).all()

    return [
        BookmakerResponse(
            id=bm.id,
            code=bm.code,
            display_name=bm.display_name,
            tier=bm.scraping_config.get('tier', 'unknown') if bm.scraping_config else 'unknown'
        )
        for bm in bookmakers
    ]


@router.get("/sports")
async def get_sports(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[SportResponse]:
    """
    Get all sports for filter dropdowns.
    Returns all sports sorted alphabetically by display_name.
    """
    sports = db.query(Sport).order_by(Sport.display_name).all()

    return [
        SportResponse(
            id=sport.id,
            code=sport.code,
            display_name=sport.display_name
        )
        for sport in sports
    ]


@router.get("/competitions")
async def get_competitions(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[CompetitionResponse]:
    """
    Get all competitions/leagues for filter dropdowns.
    Returns all competitions sorted alphabetically by short_name.
    """
    competitions = db.query(Competition).filter(
        Competition.is_active == True
    ).order_by(Competition.short_name).all()

    return [
        CompetitionResponse(
            id=comp.id,
            sport_id=comp.sport_id,
            short_name=comp.short_name,
            full_name=comp.name  # Use 'name' field, not 'full_name'
        )
        for comp in competitions
    ]
