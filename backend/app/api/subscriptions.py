"""Subscription endpoints - Stripe integration"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from sqlalchemy.orm import Session as DBSession
import stripe
import json

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.household import HouseholdMember
from app.models.subscription import Subscription
from app.schemas.subscription import (
    SubscriptionResponse,
    CreateCheckoutSessionRequest,
    CheckoutSessionResponse,
    CustomerPortalRequest,
    CustomerPortalResponse,
    PricingInfo,
    PricingResponse,
    SubscriptionTier,
)
from app.services.stripe_service import StripeService
from app.config import settings

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/status", response_model=SubscriptionResponse)
async def get_subscription_status(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current subscription status for user's household.

    Returns subscription tier, status, and billing period info.
    """
    # Get user's household
    membership = db.query(HouseholdMember).filter_by(user_id=current_user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not in any household"
        )

    # Get subscription
    subscription = db.query(Subscription).filter_by(household_id=membership.household_id).first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No subscription found for household"
        )

    return SubscriptionResponse(
        householdId=str(subscription.household_id),
        tier=subscription.tier,
        status=subscription.status,
        currentPeriodStart=subscription.current_period_start,
        currentPeriodEnd=subscription.current_period_end,
        cancelAtPeriodEnd=subscription.cancel_at_period_end == "true",
        canceledAt=subscription.canceled_at
    )


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get available subscription pricing tiers and current user's tier.

    Returns all available pricing options with features and current tier.
    """
    # Get user's current tier
    membership = db.query(HouseholdMember).filter_by(user_id=current_user.id).first()
    current_tier = SubscriptionTier.FREE

    if membership:
        subscription = db.query(Subscription).filter_by(household_id=membership.household_id).first()
        if subscription:
            current_tier = subscription.tier

    # Build pricing tiers
    tiers = [
        PricingInfo(
            tier=SubscriptionTier.FREE,
            priceId="free",
            displayName="Free",
            monthlyPrice="$0",
            yearlyPrice="$0",
            features=[
                "Basic expense tracking",
                "Up to 3 budgets",
                "Single user only",
                "7 days of history"
            ]
        ),
        PricingInfo(
            tier=SubscriptionTier.PREMIUM,
            priceId=settings.STRIPE_PREMIUM_MONTHLY_PRICE_ID,
            displayName="Premium",
            monthlyPrice="$4.99",
            yearlyPrice="$49/year (save 18%)",
            features=[
                "Unlimited budgets",
                "Advanced analytics",
                "Unlimited history",
                "CSV export",
                "Priority support"
            ]
        ),
        PricingInfo(
            tier=SubscriptionTier.PRO,
            priceId=settings.STRIPE_PRO_MONTHLY_PRICE_ID,
            displayName="Pro",
            monthlyPrice="$9.99",
            yearlyPrice="$99/year (save 17%)",
            features=[
                "All Premium features",
                "Household sharing (unlimited members)",
                "API access",
                "Custom categories",
                "White-label reports"
            ]
        )
    ]

    return PricingResponse(tiers=tiers, currentTier=current_tier)


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    data: CreateCheckoutSessionRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create Stripe checkout session for subscription purchase.

    Requires user to be in a household. Only household owners can upgrade.
    """
    # Get user's household
    membership = db.query(HouseholdMember).filter_by(user_id=current_user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not in any household"
        )

    # Only owners can manage subscriptions
    if membership.role != 'owner':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household owners can manage subscriptions"
        )

    try:
        result = StripeService.create_checkout_session(
            db=db,
            household_id=membership.household_id,
            price_id=data.price_id,
            success_url=data.success_url,
            cancel_url=data.cancel_url
        )

        return CheckoutSessionResponse(
            sessionId=result['session_id'],
            sessionUrl=result['session_url']
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}"
        )


@router.post("/portal", response_model=CustomerPortalResponse)
async def create_customer_portal_session(
    data: CustomerPortalRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create Stripe customer portal session for subscription management.

    Allows users to update payment method, cancel subscription, view invoices.
    Only household owners can access portal.
    """
    # Get user's household
    membership = db.query(HouseholdMember).filter_by(user_id=current_user.id).first()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not in any household"
        )

    # Only owners can manage subscriptions
    if membership.role != 'owner':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household owners can manage subscriptions"
        )

    try:
        portal_url = StripeService.create_customer_portal_session(
            db=db,
            household_id=membership.household_id,
            return_url=data.return_url
        )

        return CustomerPortalResponse(portalUrl=portal_url)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe error: {str(e)}"
        )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: DBSession = Depends(get_db)
):
    """
    Stripe webhook endpoint for receiving subscription events.

    Events:
        - checkout.session.completed: Payment successful
        - customer.subscription.created: New subscription
        - customer.subscription.updated: Subscription modified
        - customer.subscription.deleted: Subscription canceled
        - invoice.payment_succeeded: Recurring payment successful
        - invoice.payment_failed: Recurring payment failed

    Note: This endpoint must be configured in Stripe dashboard.
    """
    # Get raw body for signature verification
    payload = await request.body()

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    # Process event
    try:
        StripeService.handle_webhook_event(
            db=db,
            event_id=event['id'],
            event_type=event['type'],
            event_data=event['data'],
            payload=payload.decode('utf-8')
        )
    except Exception as e:
        # Log error but return 200 to Stripe (prevents infinite retries)
        print(f"Webhook processing error: {str(e)}")
        # In production, log to proper logging system
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Webhook processing failed: {str(e)}"
        )

    return {"status": "success"}


@router.get("/publishable-key")
async def get_publishable_key():
    """
    Get Stripe publishable key for frontend.

    Required for frontend to initialize Stripe.js.
    """
    return {"publishableKey": settings.STRIPE_PUBLISHABLE_KEY}
