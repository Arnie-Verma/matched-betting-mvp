# apps/api/src/api/routers/billing.py
"""Billing and subscription management endpoints"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from api.core.database import get_db
from api.core.auth import get_current_user, UserClaims
from api.models import User, Plan
from api.services.stripe_service import StripeService
from api.services.subscription_service import SubscriptionService


router = APIRouter(prefix="/billing", tags=["billing"])


class CreateCheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


class PortalSessionRequest(BaseModel):
    return_url: str


@router.get("/plans")
async def get_plans(db: Session = Depends(get_db)):
    """Get all available plans"""
    plans = db.query(Plan).filter(Plan.is_active == True).order_by(Plan.sort_order).all()

    return {
        "plans": [
            {
                "id": plan.id,
                "name": plan.name,
                "display_name": plan.display_name,
                "description": plan.description,
                "price_monthly_cents": plan.price_monthly_cents,
                "price_yearly_cents": plan.price_yearly_cents,
                "stripe_price_monthly_id": plan.stripe_price_monthly_id,
                "stripe_price_yearly_id": plan.stripe_price_yearly_id,
                "features": plan.features,
                "sort_order": plan.sort_order
            }
            for plan in plans
        ]
    }


@router.get("/subscription")
async def get_subscription_status(
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current user's subscription status"""
    # Find user by clerk_user_id
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subscription_service = SubscriptionService()
    status = subscription_service.get_subscription_status(db, user.id)

    return status


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutRequest,
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe checkout session for subscription"""
    # Find or create user
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        # Create user if doesn't exist
        user = User(
            clerk_user_id=user_claims.sub,
            email=user_claims.email,
            email_verified=user_claims.email_verified
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    stripe_service = StripeService()

    try:
        session = stripe_service.create_checkout_session(
            user=user,
            price_id=request.price_id,
            success_url=request.success_url,
            cancel_url=request.cancel_url
        )

        # Update user's stripe_customer_id if not set
        if not user.stripe_customer_id and session.customer:
            user.stripe_customer_id = session.customer
            db.commit()

        return {
            "checkout_url": session.url,
            "session_id": session.id
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/create-portal-session")
async def create_customer_portal_session(
    request: PortalSessionRequest,
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a Stripe customer portal session"""
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="User has no Stripe customer ID")

    stripe_service = StripeService()

    try:
        session = stripe_service.create_customer_portal_session(
            customer_id=user.stripe_customer_id,
            return_url=request.return_url
        )

        return {
            "portal_url": session.url
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/features/{feature}")
async def check_feature_access(
    feature: str,
    current_usage: Optional[int] = None,
    user_claims: UserClaims = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if user can access a specific feature"""
    user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    subscription_service = SubscriptionService()
    can_access, message = subscription_service.can_user_access_feature(
        db, user.id, feature, current_usage
    )

    return {
        "can_access": can_access,
        "message": message,
        "current_plan": user.current_plan,
        "feature": feature,
        "current_usage": current_usage
    }