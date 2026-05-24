"""Subscription models - Apple StoreKit 2 / App Store Server API integration"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Enum as SQLEnum,
)
from app.models._types import GUID

from app.database import Base


class SubscriptionTier(str, enum.Enum):
    """Subscription tier — derived from the Apple productId on each transaction."""
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"


class SubscriptionStatus(str, enum.Enum):
    """
    Subscription status — mirrors Apple's subscription state machine.

    See Apple's "Get All Subscription Statuses" docs. We collapse Apple's
    integer status codes into descriptive strings so they're queryable in SQL.
    """
    ACTIVE = "active"               # Paid and current
    EXPIRED = "expired"             # Last period ended without renewal
    IN_BILLING_RETRY = "in_billing_retry"  # Renewal failed, Apple retrying
    IN_GRACE_PERIOD = "in_grace_period"    # Renewal failed, still entitled
    REVOKED = "revoked"             # Family-shared sub revoked
    REFUNDED = "refunded"           # Apple refunded the user; entitlement gone
    INACTIVE = "inactive"           # No paid subscription ever (free tier default)


class Subscription(Base):
    """
    Per-household subscription state, synced from Apple StoreKit 2.

    One row per household (household_id is the PK). Free tier is represented
    as a row with tier=FREE, status=INACTIVE, and the apple_* columns null.

    Apple's `originalTransactionId` is the canonical identifier for the
    subscription lifecycle — it persists across renewals, plan changes, and
    cross-device restores. `transactionId` changes per renewal and is NOT
    used as a key.
    """

    __tablename__ = "subscriptions"

    household_id = Column(
        GUID(),
        ForeignKey('households.id', ondelete='CASCADE'),
        primary_key=True,
    )

    tier = Column(
        SQLEnum(SubscriptionTier, name='subscription_tier'),
        nullable=False,
        default=SubscriptionTier.FREE,
    )
    status = Column(
        SQLEnum(SubscriptionStatus, name='subscription_status'),
        nullable=False,
        default=SubscriptionStatus.INACTIVE,
    )

    apple_original_transaction_id = Column(String(255), nullable=True, unique=True, index=True)
    apple_product_id = Column(String(255), nullable=True)
    apple_environment = Column(String(20), nullable=True)  # "Sandbox" | "Production"

    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    auto_renew_status = Column(Boolean, nullable=True)
    auto_renew_product_id = Column(String(255), nullable=True)

    revocation_date = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @property
    def is_active(self) -> bool:
        """True if the household currently has a paid entitlement."""
        return self.status in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.IN_GRACE_PERIOD,
            SubscriptionStatus.IN_BILLING_RETRY,
        ) and self.tier != SubscriptionTier.FREE

    def __repr__(self):
        return f"<Subscription(household={self.household_id}, tier={self.tier}, status={self.status})>"


class AppleNotification(Base):
    """
    Log of Apple Server Notifications V2 for idempotent processing and audit.

    Apple retries non-2xx responses for up to 3 days, so dedupe on Apple's
    per-notification `notificationUUID`.
    """

    __tablename__ = "apple_notifications"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    notification_uuid = Column(String(255), nullable=False, unique=True, index=True)
    notification_type = Column(String(100), nullable=False, index=True)
    subtype = Column(String(100), nullable=True)
    apple_original_transaction_id = Column(String(255), nullable=True, index=True)
    bundle_id = Column(String(255), nullable=True)
    environment = Column(String(20), nullable=True)
    processed = Column(Boolean, nullable=False, default=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    raw_payload = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<AppleNotification(type={self.notification_type}, uuid={self.notification_uuid}, processed={self.processed})>"
