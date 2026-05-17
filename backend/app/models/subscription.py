"""Subscription model - Stripe subscription management"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone
import enum

from app.database import Base


class SubscriptionTier(str, enum.Enum):
    """Subscription tier levels"""
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status states (aligned with Stripe)"""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class Subscription(Base):
    """
    Subscription table - tracks user/household subscription state.

    Schema:
        - id: Primary key (UUID)
        - household_id: Foreign key to households (subscription is per-household)
        - tier: Subscription tier (free/premium/pro)
        - status: Subscription status (active/canceled/past_due/etc)
        - stripe_customer_id: Stripe customer ID (nullable for free tier)
        - stripe_subscription_id: Stripe subscription ID (nullable for free tier)
        - stripe_price_id: Stripe price ID for current subscription
        - current_period_start: Current billing period start
        - current_period_end: Current billing period end
        - cancel_at_period_end: Whether subscription will cancel at period end
        - canceled_at: When subscription was canceled (if applicable)
        - created_at: Subscription creation timestamp
        - updated_at: Last update timestamp

    Notes:
        - Free tier has no Stripe IDs (all Stripe fields are NULL)
        - Subscription is household-level (all members share benefits)
        - Status is synced via Stripe webhooks
        - When subscription expires, tier reverts to FREE automatically
    """

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    household_id = Column(
        UUID(as_uuid=True),
        ForeignKey('households.id', ondelete='CASCADE'),
        nullable=False,
        unique=True,  # One subscription per household
        index=True
    )
    tier = Column(SQLEnum(SubscriptionTier), nullable=False, default=SubscriptionTier.FREE)
    status = Column(SQLEnum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)

    # Stripe integration fields (NULL for free tier)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True)
    stripe_price_id = Column(String(255), nullable=True)

    # Billing period tracking
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    # Cancellation tracking
    cancel_at_period_end = Column(String(50), nullable=False, default="false")
    canceled_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Subscription(household_id={self.household_id}, tier={self.tier}, status={self.status})>"

    @property
    def is_active(self) -> bool:
        """Check if subscription provides premium features"""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]

    @property
    def is_premium_or_higher(self) -> bool:
        """Check if household has premium or pro tier"""
        return self.tier in [SubscriptionTier.PREMIUM, SubscriptionTier.PRO] and self.is_active


class WebhookEvent(Base):
    """
    Webhook event log - tracks processed Stripe webhooks for idempotency.

    Schema:
        - id: Primary key (UUID)
        - stripe_event_id: Stripe event ID (unique)
        - event_type: Stripe event type (e.g., 'customer.subscription.created')
        - processed: Whether event has been processed
        - payload: Full webhook payload (JSON)
        - error_message: Error message if processing failed
        - created_at: Event received timestamp
        - processed_at: Event processing completion timestamp

    Notes:
        - Prevents duplicate processing of webhook events
        - Stripe may resend events, so we track by stripe_event_id
        - Failed events can be retried manually
    """

    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    stripe_event_id = Column(String(255), nullable=False, unique=True, index=True)
    event_type = Column(String(255), nullable=False, index=True)
    processed = Column(String(50), nullable=False, default="false")
    payload = Column(String, nullable=False)  # JSON text
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<WebhookEvent(id={self.stripe_event_id}, type={self.event_type}, processed={self.processed})>"
