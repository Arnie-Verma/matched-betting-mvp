# apps/api/src/api/models/subscription.py
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey, Text, JSON, Numeric
from sqlalchemy.orm import relationship

from api.core.database import Base


class Plan(Base):
    """Plan definitions for the matched betting platform"""
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # free, starter, pro
    display_name = Column(String, nullable=False)  # "Free", "Starter", "Pro"

    # Pricing (in cents)
    price_monthly_cents = Column(Integer, nullable=True)  # None for free plan
    price_yearly_cents = Column(Integer, nullable=True)   # None for free plan

    # Stripe product/price IDs
    stripe_product_id = Column(String, nullable=True)
    stripe_price_monthly_id = Column(String, nullable=True)
    stripe_price_yearly_id = Column(String, nullable=True)

    # Feature limits and entitlements
    features = Column(JSON, nullable=False, default={})  # {"max_bookmakers": 5, "max_refreshes_per_hour": 10}

    # Metadata
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Plan(name={self.name}, price_monthly=${self.price_monthly_cents/100 if self.price_monthly_cents else 0})>"


class Subscription(Base):
    """User subscription tracking with Stripe integration"""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Stripe subscription info
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=True)
    stripe_customer_id = Column(String, index=True, nullable=False)
    stripe_price_id = Column(String, nullable=True)  # Current price being charged

    # Subscription details
    plan_name = Column(String, nullable=False)  # free, starter, pro
    status = Column(String, nullable=False)  # active, inactive, canceled, past_due, trialing
    billing_cycle = Column(String, nullable=True)  # monthly, yearly (None for free)

    # Dates (all in UTC)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    trial_start = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Pricing
    amount_cents = Column(Integer, nullable=True)  # Amount being charged in cents
    currency = Column(String, default="aud", nullable=False)

    # Metadata from Stripe
    stripe_metadata = Column(JSON, nullable=True, default={})

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, plan={self.plan_name}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        return self.status in ["active", "trialing"]

    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial period"""
        return self.status == "trialing"


class WebhookEvent(Base):
    """Track Stripe webhook events for idempotency and auditing"""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    stripe_event_id = Column(String, unique=True, index=True, nullable=False)
    event_type = Column(String, nullable=False)  # customer.subscription.created, etc.

    # Processing status
    processed = Column(Boolean, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Event data
    stripe_api_version = Column(String, nullable=True)
    event_data = Column(JSON, nullable=False)  # Full Stripe event object

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<WebhookEvent(id={self.stripe_event_id}, type={self.event_type}, processed={self.processed})>"