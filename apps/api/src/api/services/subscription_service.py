# apps/api/src/api/services/subscription_service.py
"""Service for managing user subscriptions and plan enforcement"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
import stripe

from api.models import User, Subscription, Plan, WebhookEvent, Bookmaker
from api.services.stripe_service import StripeService

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing user subscriptions"""

    def __init__(self):
        self.stripe_service = StripeService()

    def _extract_plan_name(
        self,
        db: Session,
        stripe_subscription: stripe.Subscription
    ) -> str:
        """Resolve plan name from Stripe subscription or price metadata."""
        plan_name = None
        price = None
        metadata = stripe_subscription.metadata or {}
        if metadata.get("plan_name"):
            plan_name = metadata["plan_name"]
        else:
            items_data = self._get_subscription_items(stripe_subscription)
            if items_data:
                price = items_data[0].price

        if price:
            price_metadata = getattr(price, "metadata", None)
            if price_metadata and price_metadata.get("plan_name"):
                plan_name = price_metadata["plan_name"]
            else:
                price_id = getattr(price, "id", None)
                if not price_id and isinstance(price, dict):
                    price_id = price.get("id")
                plan = (
                    db.query(Plan)
                    .filter(
                        or_(
                            Plan.stripe_price_monthly_id == price_id,
                            Plan.stripe_price_yearly_id == price_id
                        )
                    )
                    .first()
                )
                if not plan:
                    product_id = getattr(price, "product", None)
                    if not product_id and isinstance(price, dict):
                        product_id = price.get("product")
                    if hasattr(product_id, "id"):
                        product_id = product_id.id
                    if product_id:
                        plan = (
                            db.query(Plan)
                            .filter(Plan.stripe_product_id == product_id)
                            .first()
                        )
                if plan:
                    plan_name = plan.name

        if plan_name:
            return str(plan_name).lower()
        return "free"

    def _get_subscription_items(
        self,
        stripe_subscription: stripe.Subscription
    ) -> list:
        """Safely access subscription items list from Stripe object."""
        items = getattr(stripe_subscription, "items", None)
        if items and hasattr(items, "data"):
            return items.data
        return []

    def sync_subscription_from_stripe(
        self,
        db: Session,
        user: User
    ) -> Optional[Subscription]:
        """Sync latest active Stripe subscription for a user into the local DB."""
        if not user.stripe_customer_id:
            return None

        try:
            subscriptions = stripe.Subscription.list(
                customer=user.stripe_customer_id,
                status="all",
                expand=["data.items.data.price"],
                limit=10
            )
        except stripe.error.StripeError as exc:
            logger.warning("Stripe sync failed for user %s: %s", user.id, exc)
            return None

        active_subs = [
            sub for sub in subscriptions.data
            if sub.status in ["active", "trialing"]
        ]
        if not active_subs:
            return None

        active_subs.sort(
            key=lambda sub: (
                getattr(sub, "current_period_end", None)
                or getattr(sub, "created", None)
                or 0
            ),
            reverse=True
        )
        stripe_sub = active_subs[0]

        existing = (
            db.query(Subscription)
            .filter(Subscription.stripe_subscription_id == stripe_sub.id)
            .first()
        )
        if existing:
            return self.update_subscription_from_stripe(db, stripe_sub)

        return self.create_subscription_from_stripe(db, stripe_sub, user.id)

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
                "bookmakers": 2,
                "max_bookmakers": 3,
                "odds_matcher": True,
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
        # Get plan name from subscription or price metadata
        plan_name = self._extract_plan_name(db, stripe_subscription)

        items_data = self._get_subscription_items(stripe_subscription)
        price = items_data[0].price if items_data else None

        # Determine billing cycle
        billing_cycle = None
        if price:
            recurring = getattr(price, "recurring", None)
            if not recurring and isinstance(price, dict):
                recurring = price.get("recurring")
            interval = getattr(recurring, "interval", None) if recurring else None
            if not interval and isinstance(recurring, dict):
                interval = recurring.get("interval")
            if interval:
                billing_cycle = "monthly" if interval == "month" else "yearly"

        # Get amount
        amount_cents = getattr(price, "unit_amount", None) if price else None
        if amount_cents is None and isinstance(price, dict):
            amount_cents = price.get("unit_amount")

        current_period_start = getattr(stripe_subscription, "current_period_start", None)
        current_period_end = getattr(stripe_subscription, "current_period_end", None)
        trial_start = getattr(stripe_subscription, "trial_start", None)
        trial_end = getattr(stripe_subscription, "trial_end", None)

        stripe_price_id = getattr(price, "id", None) if price else None
        if not stripe_price_id and isinstance(price, dict):
            stripe_price_id = price.get("id")

        subscription = Subscription(
            user_id=user_id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_subscription.customer,
            stripe_price_id=stripe_price_id,
            plan_name=plan_name,
            status=stripe_subscription.status,
            billing_cycle=billing_cycle,
            current_period_start=datetime.fromtimestamp(
                current_period_start, tz=timezone.utc
            ) if current_period_start else None,
            current_period_end=datetime.fromtimestamp(
                current_period_end, tz=timezone.utc
            ) if current_period_end else None,
            trial_start=datetime.fromtimestamp(
                trial_start, tz=timezone.utc
            ) if trial_start else None,
            trial_end=datetime.fromtimestamp(
                trial_end, tz=timezone.utc
            ) if trial_end else None,
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

        plan_name = self._extract_plan_name(db, stripe_subscription)
        if plan_name == "free" and subscription.plan_name:
            plan_name = subscription.plan_name

        # Update subscription fields
        subscription.status = stripe_subscription.status
        subscription.plan_name = plan_name
        current_period_start = getattr(stripe_subscription, "current_period_start", None)
        current_period_end = getattr(stripe_subscription, "current_period_end", None)
        subscription.current_period_start = datetime.fromtimestamp(
            current_period_start, tz=timezone.utc
        ) if current_period_start else None
        subscription.current_period_end = datetime.fromtimestamp(
            current_period_end, tz=timezone.utc
        ) if current_period_end else None

        canceled_at = getattr(stripe_subscription, "canceled_at", None)
        if canceled_at:
            subscription.canceled_at = datetime.fromtimestamp(
                canceled_at, tz=timezone.utc
            )

        ended_at = getattr(stripe_subscription, "ended_at", None)
        if ended_at:
            subscription.ended_at = datetime.fromtimestamp(
                ended_at, tz=timezone.utc
            )

        subscription.stripe_metadata = dict(stripe_subscription.metadata) if stripe_subscription.metadata else {}

        db.commit()

        # Update user's plan status
        user = subscription.user
        if user:
            if subscription.is_active:
                user.current_plan = plan_name
                user.plan_status = "active"
            else:
                user.plan_status = "inactive"
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
        if user.stripe_customer_id and (not subscription or subscription.plan_name == "free"):
            synced = self.sync_subscription_from_stripe(db, user)
            if synced:
                subscription = synced
                db.refresh(user)

        if subscription and subscription.is_active and user.current_plan != subscription.plan_name:
            user.current_plan = subscription.plan_name
            user.plan_status = "active"
            db.commit()

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

        Tier structure (Betfair always included as exchange for lay odds):
        - Free tier: 2 bookmakers (Ladbrokes + Neds) + Betfair
        - Premium tier: 16 bookmakers + Betfair
        - Platinum tier: All 103 bookmakers + Betfair

        Note: Betfair is ALWAYS included as it's the exchange (provides lay odds).
        """
        plan = user.current_plan.lower()

        # Free tier: 2 bookmakers + Betfair (exchange)
        if plan == "free":
            return ["ladbrokes", "neds", "betfair"]

        # Premium tier: 16 bookmakers + Betfair
        if plan == "premium":
            return [
                "sportsbet", "ladbrokes", "neds", "tab", "pointsbet", "unibet",
                "betr", "betdeluxe", "betright", "crossbet", "dabble",
                "elitebet", "tabtouch", "realbookie", "picklebet",
                # Exchange (always included)
                "betfair"
            ]

        # Platinum tier: All 103 bookmakers
        if plan in ["platinum", "diamond"]:
            return [
                # All bookmakers
                "alphabet", "baggybet", "bet575", "bet66", "bet777", "betbetbet",
                "betblitz", "betchamps", "betdeluxe", "betestate", "betfocus",
                "betgalaxy", "betgold", "betlocal", "betm", "betnation",
                "betprofessor", "betr", "betright", "betroyale", "betyoucan",
                "bigbet", "blondebet", "boombet", "boostbet", "bossbet",
                "buffalobet", "cashcage", "chasebet", "chromabet", "crossbet",
                "dabble", "diamondbet", "dowbet", "elitebet", "fiestaet",
                "gigabet", "goldbet", "goldenbet888", "goldenrush", "havabet",
                "hotbet", "jimmybet", "juicybet", "junglebet", "justbet",
                "ladbrokes", "letsbet", "lightningbet", "marantellibet", "midasbet",
                "mintbet", "mybet", "neds", "noisy", "okebet",
                "oldgill", "palmerbet", "picklebet", "picnicbet", "playup",
                "playwest", "pointsbet", "ponybet", "premiumbet", "pulsebet",
                "punt123", "puntcity", "puntgenie", "puntnow", "puntzone",
                "questbet", "readybet", "realbookie", "robwaterhouse", "slambet",
                "sportsbet", "starsports", "sterlingparker", "sugarcastle", "surge",
                "swiftbet", "tab", "tabtouch", "templebet", "terrybet",
                "titanbet", "topbet", "tradiebet", "truebet", "ultrabet",
                "unibet", "upcoz", "vikingbet", "vinbet", "volcanobet",
                "wellbet", "winnersbet", "wishbet", "wizbet", "zbet",
                # Exchange (always included)
                "betfair"
            ]

        # Default: free tier
        return ["ladbrokes", "neds", "betfair"]
