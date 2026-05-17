"""Subscription schemas for request/response models"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


class SubscriptionTier(str, Enum):
    """Subscription tier levels"""
    FREE = "free"
    PREMIUM = "premium"
    PRO = "pro"


class SubscriptionStatus(str, Enum):
    """Subscription status states"""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class SubscriptionResponse(BaseModel):
    """
    Subscription information response (backend → frontend).

    Uses camelCase for frontend compatibility (NO CodingKeys needed).
    """
    householdId: str
    tier: SubscriptionTier
    status: SubscriptionStatus
    currentPeriodStart: Optional[datetime] = None
    currentPeriodEnd: Optional[datetime] = None
    cancelAtPeriodEnd: bool
    canceledAt: Optional[datetime] = None

    class Config:
        from_attributes = True


class CreateCheckoutSessionRequest(BaseModel):
    """
    Request to create Stripe checkout session (frontend → backend).

    Uses snake_case in API (CodingKeys on frontend).
    """
    price_id: str = Field(..., description="Stripe price ID for the subscription tier")
    success_url: str = Field(..., description="URL to redirect after successful payment")
    cancel_url: str = Field(..., description="URL to redirect if payment is canceled")


class CheckoutSessionResponse(BaseModel):
    """
    Checkout session creation response (backend → frontend).

    Uses camelCase for frontend compatibility.
    """
    sessionId: str = Field(..., description="Stripe checkout session ID")
    sessionUrl: str = Field(..., description="URL to redirect user to Stripe checkout")


class CustomerPortalRequest(BaseModel):
    """
    Request to create Stripe customer portal session (frontend → backend).

    Uses snake_case in API (CodingKeys on frontend).
    """
    return_url: str = Field(..., description="URL to redirect after portal session")


class CustomerPortalResponse(BaseModel):
    """
    Customer portal session response (backend → frontend).

    Uses camelCase for frontend compatibility.
    """
    portalUrl: str = Field(..., description="URL to redirect user to Stripe customer portal")


class PricingInfo(BaseModel):
    """
    Pricing tier information (backend → frontend).

    Uses camelCase for frontend compatibility.
    """
    tier: SubscriptionTier
    priceId: str
    displayName: str
    monthlyPrice: str
    yearlyPrice: str
    features: list[str]


class PricingResponse(BaseModel):
    """
    Available pricing tiers response (backend → frontend).

    Uses camelCase for frontend compatibility.
    """
    tiers: list[PricingInfo]
    currentTier: SubscriptionTier
