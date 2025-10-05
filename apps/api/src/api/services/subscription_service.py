# apps/api/src/api/services/subscription_service.py
"""Service for managing user subscriptions and plan enforcement"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
import stripe

from api.models import User, Subscription, Plan, WebhookEvent, Bookmaker
from api.services.stripe_service import StripeService


class SubscriptionService:
    """Service for managing user subscriptions"""

    def __init__(self):
        self.stripe_service = StripeService()

    def get_user_subscription(self, db: Session, user_id: int) -> Optional[Subscription]:
        """Get the current active subscription for a user"""
        return (
            db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .filter(Subscription.status.in_(["active", "trialing"]))
            .order_by(desc(Subscription.created_at))
            .first()
        )

    def get_plan_features(self, db: Session, plan_name: str) -> Dict[str, Any]:
        """Get feature limits for a given plan"""
        plan = db.query(Plan).filter(Plan.name == plan_name).first()
        if not plan:
            # Return free plan features as fallback
            return {
                "max_bookmakers": 3,
                "max_bets_per_month": 50,
                "email_notifications": True,
                "mobile_app": False,
                "priority_support": False,
                "custom_alerts": False,
                "api_access": False
            }
        return plan.features

    def create_subscription_from_stripe(
        self,
        db: Session,
        stripe_subscription: stripe.Subscription,
        user_id: int
    ) -> Subscription:
        """Create a subscription record from Stripe subscription data"""
        # Get plan name from metadata or price metadata
        plan_name = "free"  # fallback
        if stripe_subscription.metadata.get("plan_name"):
            plan_name = stripe_subscription.metadata["plan_name"]
        elif stripe_subscription.items.data:
            price = stripe_subscription.items.data[0].price
            if price.metadata.get("plan_name"):
                plan_name = price.metadata["plan_name"]

        # Determine billing cycle
        billing_cycle = None
        if stripe_subscription.items.data:
            interval = stripe_subscription.items.data[0].price.recurring.interval
            billing_cycle = "monthly" if interval == "month" else "yearly"

        # Get amount
        amount_cents = None
        if stripe_subscription.items.data:
            amount_cents = stripe_subscription.items.data[0].price.unit_amount

        subscription = Subscription(
            user_id=user_id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_subscription.customer,
            stripe_price_id=stripe_subscription.items.data[0].price.id if stripe_subscription.items.data else None,
            plan_name=plan_name,
            status=stripe_subscription.status,
            billing_cycle=billing_cycle,
            current_period_start=datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            ) if stripe_subscription.current_period_start else None,
            current_period_end=datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            ) if stripe_subscription.current_period_end else None,
            trial_start=datetime.fromtimestamp(
                stripe_subscription.trial_start, tz=timezone.utc
            ) if stripe_subscription.trial_start else None,
            trial_end=datetime.fromtimestamp(
                stripe_subscription.trial_end, tz=timezone.utc
            ) if stripe_subscription.trial_end else None,
            amount_cents=amount_cents,
            currency="aud",
            stripe_metadata=dict(stripe_subscription.metadata) if stripe_subscription.metadata else {}
        )

        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        # Update user's current plan
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.current_plan = plan_name
            user.plan_status = "active" if subscription.is_active else "inactive"
            db.commit()

        return subscription

    def update_subscription_from_stripe(
        self,
        db: Session,
        stripe_subscription: stripe.Subscription
    ) -> Optional[Subscription]:
        """Update existing subscription from Stripe data"""
        subscription = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription.id)
            .first()
        )

        if not subscription:
            return None

        # Update subscription fields
        subscription.status = stripe_subscription.status
        subscription.current_period_start = datetime.fromtimestamp(
            stripe_subscription.current_period_start, tz=timezone.utc
        ) if stripe_subscription.current_period_start else None
        subscription.current_period_end = datetime.fromtimestamp(
            stripe_subscription.current_period_end, tz=timezone.utc
        ) if stripe_subscription.current_period_end else None

        if stripe_subscription.canceled_at:
            subscription.canceled_at = datetime.fromtimestamp(
                stripe_subscription.canceled_at, tz=timezone.utc
            )

        if stripe_subscription.ended_at:
            subscription.ended_at = datetime.fromtimestamp(
                stripe_subscription.ended_at, tz=timezone.utc
            )

        subscription.stripe_metadata = dict(stripe_subscription.metadata) if stripe_subscription.metadata else {}

        db.commit()

        # Update user's plan status
        user = subscription.user
        if user:
            user.plan_status = "active" if subscription.is_active else "inactive"
            # Only update plan if subscription is canceled/ended
            if subscription.status in ["canceled", "unpaid", "past_due"]:
                user.current_plan = "free"
            db.commit()

        return subscription

    def handle_subscription_deleted(
        self,
        db: Session,
        stripe_subscription_id: str
    ) -> Optional[Subscription]:
        """Handle subscription deletion/cancellation"""
        subscription = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
            .first()
        )

        if not subscription:
            return None

        subscription.status = "canceled"
        subscription.ended_at = datetime.now(timezone.utc)
        db.commit()

        # Downgrade user to free plan
        user = subscription.user
        if user:
            user.current_plan = "free"
            user.plan_status = "active"
            db.commit()

        return subscription

    def can_user_access_feature(
        self,
        db: Session,
        user_id: int,
        feature: str,
        current_usage: Optional[int] = None
    ) -> tuple[bool, str]:
        """Check if user can access a feature based on their plan"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "User not found"

        features = self.get_plan_features(db, user.current_plan)

        # Check boolean features
        if feature in features and isinstance(features[feature], bool):
            if not features[feature]:
                return False, f"Feature '{feature}' not available in {user.current_plan} plan"
            return True, ""

        # Check numeric limits
        if feature in features and isinstance(features[feature], int):
            limit = features[feature]
            if limit == -1:  # Unlimited
                return True, ""
            if current_usage is not None and current_usage >= limit:
                return False, f"Usage limit reached for '{feature}' ({current_usage}/{limit})"
            return True, ""

        return False, f"Feature '{feature}' not defined"

    def get_subscription_status(self, db: Session, user_id: int) -> Dict[str, Any]:
        """Get comprehensive subscription status for a user"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}

        subscription = self.get_user_subscription(db, user_id)
        features = self.get_plan_features(db, user.current_plan)

        result = {
            "user_id": user_id,
            "current_plan": user.current_plan,
            "plan_status": user.plan_status,
            "features": features,
            "subscription": None
        }

        if subscription:
            result["subscription"] = {
                "id": subscription.id,
                "stripe_subscription_id": subscription.stripe_subscription_id,
                "status": subscription.status,
                "billing_cycle": subscription.billing_cycle,
                "current_period_start": subscription.current_period_start.isoformat() if subscription.current_period_start else None,
                "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
                "trial_end": subscription.trial_end.isoformat() if subscription.trial_end else None,
                "amount_cents": subscription.amount_cents,
                "currency": subscription.currency,
                "is_active": subscription.is_active,
                "is_trial": subscription.is_trial
            }

        return result

    def get_allowed_bookmakers(self, db: Session, user: User) -> list[str]:
        """
        Get list of bookmaker codes allowed for user's plan.

        Tier structure is CUMULATIVE:
        - Free tier: TAB, Ladbrokes (2 bookmakers)
        - Premium tier: Free + 13 more = 15 total
        - Platinum tier: Premium + all others = 100+ total
        """
        plan = user.current_plan.lower()

        # Free tier: Only TAB and Ladbrokes
        if plan == "free":
            return ["tab", "ladbrokes"]

        # Premium tier: Free (2) + Premium (13) = 15 total
        if plan == "premium":
            return [
                # Free tier bookmakers
                "tab", "ladbrokes",
                # Premium tier bookmakers (13)
                "sportsbet", "neds", "betfair", "pointsbet", "unibet",
                "betr", "betdeluxe", "betright", "crossbet", "dabble",
                "elitebet", "tabtouch", "realbookie", "picklebet"
            ]

        # Platinum tier: All bookmakers (active + inactive)
        # Platinum users get everything
        if plan == "platinum" or plan == "diamond":
            # Return ALL bookmakers in the database
            bookmakers = db.query(Bookmaker).all()
            return [bm.code for bm in bookmakers]

        # Default: free tier
        return ["tab", "ladbrokes"]