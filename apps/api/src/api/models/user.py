# apps/api/src/api/models/user.py
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import relationship

from api.core.database import Base


class User(Base):
    """User model linked to Clerk authentication"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    clerk_user_id = Column(String, unique=True, index=True, nullable=False)  # Clerk's user ID
    email = Column(String, index=True, nullable=False)
    email_verified = Column(Boolean, default=False)

    # Stripe customer info
    stripe_customer_id = Column(String, unique=True, index=True, nullable=True)

    # Plan information (denormalized for quick access)
    current_plan = Column(String, default="free", nullable=False)  # free, starter, pro
    plan_status = Column(String, default="active", nullable=False)  # active, inactive, canceled

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, plan={self.current_plan})>"