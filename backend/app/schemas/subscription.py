"""Subscription request/response schemas - Apple StoreKit 2"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.subscription import SubscriptionTier, SubscriptionStatus


class SubscriptionResponse(BaseModel):
    """Current subscription state for the caller's household."""
    model_config = ConfigDict(from_attributes=True)

    householdId: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    productId: Optional[str] = None
    environment: Optional[str] = None
    currentPeriodStart: Optional[datetime] = None
    currentPeriodEnd: Optional[datetime] = None
    autoRenewStatus: Optional[bool] = None
    isActive: bool = False


class VerifyTransactionRequest(BaseModel):
    """
    Frontend posts the signed JWS string from StoreKit's
    `Transaction.jwsRepresentation` after a successful purchase or restore.
    """
    signedTransaction: str = Field(..., description="JWS-encoded transaction from StoreKit")


class PricingTier(BaseModel):
    """One pricing tier.

    Display prices are owned by App Store / StoreKit, NOT the backend —
    the iOS app looks them up from `Product.products(for:)` using the product
    IDs returned here.
    """
    tier: SubscriptionTier
    displayName: str
    monthlyProductId: str
    yearlyProductId: str
    features: List[str]


class PricingResponse(BaseModel):
    """Available tiers and the caller's current tier."""
    tiers: List[PricingTier]
    currentTier: SubscriptionTier
