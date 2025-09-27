# apps/api/src/api/middleware/plan_enforcement.py
"""Middleware for enforcing plan-based access control"""
from typing import Dict, Any, Optional, Callable
from functools import wraps
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session

from api.core.database import get_db
from api.core.auth import get_current_user, UserClaims
from api.models import User
from api.services.subscription_service import SubscriptionService


def require_plan_feature(
    feature: str,
    current_usage_fn: Optional[Callable[[int, Session], int]] = None,
    error_message: Optional[str] = None
):
    """
    Decorator to enforce plan-based feature access

    Args:
        feature: The feature name to check (e.g., "max_bookmakers", "api_access")
        current_usage_fn: Optional function to calculate current usage for numeric limits
        error_message: Custom error message for access denied
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies from function signature
            user_claims = None
            db = None

            # Look for dependencies in kwargs
            for key, value in kwargs.items():
                if isinstance(value, UserClaims):
                    user_claims = value
                elif isinstance(value, Session):
                    db = value

            if not user_claims or not db:
                raise HTTPException(
                    status_code=500,
                    detail="Plan enforcement middleware requires user_claims and db dependencies"
                )

            # Find user
            user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Check feature access
            subscription_service = SubscriptionService()

            current_usage = None
            if current_usage_fn:
                current_usage = current_usage_fn(user.id, db)

            can_access, message = subscription_service.can_user_access_feature(
                db, user.id, feature, current_usage
            )

            if not can_access:
                raise HTTPException(
                    status_code=403,
                    detail=error_message or message or f"Feature '{feature}' not available in your plan"
                )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def require_plan(required_plan: str, allow_higher: bool = True):
    """
    Decorator to require a specific plan level

    Args:
        required_plan: The minimum required plan (free, premium, platinum)
        allow_higher: Whether higher plans are also allowed
    """
    plan_hierarchy = {"free": 0, "premium": 1, "platinum": 2}

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract dependencies
            user_claims = None
            db = None

            for key, value in kwargs.items():
                if isinstance(value, UserClaims):
                    user_claims = value
                elif isinstance(value, Session):
                    db = value

            if not user_claims or not db:
                raise HTTPException(
                    status_code=500,
                    detail="Plan enforcement middleware requires user_claims and db dependencies"
                )

            # Find user
            user = db.query(User).filter(User.clerk_user_id == user_claims.sub).first()
            if not user:
                raise HTTPException(status_code=404, detail="User not found")

            # Check plan level
            user_plan_level = plan_hierarchy.get(user.current_plan, -1)
            required_plan_level = plan_hierarchy.get(required_plan, 999)

            if allow_higher:
                if user_plan_level < required_plan_level:
                    raise HTTPException(
                        status_code=403,
                        detail=f"This feature requires at least the {required_plan} plan"
                    )
            else:
                if user_plan_level != required_plan_level:
                    raise HTTPException(
                        status_code=403,
                        detail=f"This feature requires exactly the {required_plan} plan"
                    )

            return await func(*args, **kwargs)

        return wrapper
    return decorator


class PlanEnforcementService:
    """Service for plan enforcement checks outside of decorators"""

    def __init__(self):
        self.subscription_service = SubscriptionService()

    def check_api_rate_limit(self, user_id: int, db: Session) -> tuple[bool, str]:
        """Check if user can make API calls based on their plan"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "User not found"

        # Check if user has API access
        can_access, message = self.subscription_service.can_user_access_feature(
            db, user_id, "api_access"
        )

        if not can_access:
            return False, "API access not available in your plan"

        # TODO: Implement actual rate limiting logic here
        # For now, just check the feature
        return True, ""

    def check_bookmaker_limit(self, user_id: int, current_count: int, db: Session) -> tuple[bool, str]:
        """Check if user can add more bookmakers"""
        return self.subscription_service.can_user_access_feature(
            db, user_id, "max_bookmakers", current_count
        )

    def check_bet_limit(self, user_id: int, current_count: int, db: Session) -> tuple[bool, str]:
        """Check if user can place more bets this month"""
        return self.subscription_service.can_user_access_feature(
            db, user_id, "max_bets_per_month", current_count
        )

    def get_plan_limits(self, user_id: int, db: Session) -> Dict[str, Any]:
        """Get all plan limits for a user"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {}

        return self.subscription_service.get_plan_features(db, user.current_plan)