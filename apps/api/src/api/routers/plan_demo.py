# apps/api/src/api/routers/plan_demo.py
"""Demo endpoints to show plan enforcement in action"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.auth import get_current_user, UserClaims
from api.middleware import require_plan_feature, require_plan, PlanEnforcementService


router = APIRouter(prefix="/demo", tags=["plan-demo"])


@router.get("/api-feature")
@require_plan_feature("api_access")
async def api_feature_demo(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Demo endpoint that requires API access feature"""
    return {
        "message": "You have API access!",
        "user_id": user_claims.sub,
        "feature": "api_access"
    }


@router.get("/platinum-only")
@require_plan("platinum", allow_higher=False)
async def platinum_only_demo(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Demo endpoint that requires exactly the Platinum plan"""
    return {
        "message": "You're a Platinum user!",
        "user_id": user_claims.sub,
        "plan": "platinum"
    }


@router.get("/premium-plus")
@require_plan("premium", allow_higher=True)
async def premium_plus_demo(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Demo endpoint that requires Premium plan or higher"""
    return {
        "message": "You have Premium or Platinum plan!",
        "user_id": user_claims.sub,
        "minimum_plan": "premium"
    }


def get_user_bookmaker_count(user_id: int, db: Session) -> int:
    """Mock function to get current bookmaker count"""
    # In real implementation, this would query your bookmakers table
    return 2  # Mock: user has 2 bookmakers


@router.post("/add-bookmaker")
@require_plan_feature("max_bookmakers", current_usage_fn=get_user_bookmaker_count)
async def add_bookmaker_demo(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Demo endpoint that checks bookmaker limits"""
    current_count = get_user_bookmaker_count(int(user_claims.sub.split('_')[-1]), db)

    return {
        "message": "Bookmaker added successfully!",
        "current_bookmakers": current_count + 1,
        "user_id": user_claims.sub
    }


@router.get("/plan-limits")
async def get_plan_limits_demo(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's plan limits"""
    from api.models import User

    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        return {"error": "User not found"}

    enforcement_service = PlanEnforcementService()
    limits = enforcement_service.get_plan_limits(user.id, db)

    return {
        "user_id": user_claims.sub,
        "current_plan": user.current_plan,
        "limits": limits
    }