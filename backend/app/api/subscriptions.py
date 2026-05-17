"""Subscription endpoints - Apple StoreKit 2 / App Store Server API"""

from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from appstoreserverlibrary.signed_data_verifier import VerificationException

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user_and_household
from app.models.household import Household, HouseholdMember
from app.models.subscription import Subscription, SubscriptionStatus, SubscriptionTier
from app.models.user import User
from app.schemas.subscription import (
    PricingResponse,
    PricingTier,
    SubscriptionResponse,
    VerifyTransactionRequest,
)
from app.services.apple_service import (
    AppleNotConfiguredError,
    handle_server_notification,
    verify_purchase_transaction,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _to_response(sub: Subscription) -> SubscriptionResponse:
    return SubscriptionResponse(
        householdId=str(sub.household_id),
        tier=sub.tier,
        status=sub.status,
        productId=sub.apple_product_id,
        environment=sub.apple_environment,
        currentPeriodStart=sub.current_period_start,
        currentPeriodEnd=sub.current_period_end,
        autoRenewStatus=sub.auto_renew_status,
        isActive=sub.is_active,
    )


def _free_response(household_id) -> SubscriptionResponse:
    return SubscriptionResponse(
        householdId=str(household_id),
        tier=SubscriptionTier.FREE,
        status=SubscriptionStatus.INACTIVE,
        isActive=False,
    )


@router.get("/status", response_model=SubscriptionResponse)
async def get_subscription_status(
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Return the caller's household subscription state."""
    _, household = user_household
    sub = db.query(Subscription).filter_by(household_id=household.id).first()
    return _to_response(sub) if sub else _free_response(household.id)


@router.get("/pricing", response_model=PricingResponse)
async def get_pricing(
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Return tier metadata + the product IDs the iOS app should fetch from StoreKit.

    Display prices live in App Store Connect, not here. The iOS client looks
    them up via `Product.products(for:)` using the IDs returned here, then
    renders whichever localized price StoreKit hands back.
    """
    _, household = user_household
    sub = db.query(Subscription).filter_by(household_id=household.id).first()
    current_tier = sub.tier if sub else SubscriptionTier.FREE

    tiers = [
        PricingTier(
            tier=SubscriptionTier.FREE,
            displayName="Free",
            monthlyProductId="",
            yearlyProductId="",
            features=[
                "Basic expense tracking",
                "Up to 3 budgets",
                "Single user only",
                "7 days of history",
            ],
        ),
        PricingTier(
            tier=SubscriptionTier.PREMIUM,
            displayName="Premium",
            monthlyProductId=settings.APPLE_PRODUCT_ID_PREMIUM_MONTHLY,
            yearlyProductId=settings.APPLE_PRODUCT_ID_PREMIUM_YEARLY,
            features=[
                "Unlimited budgets",
                "Advanced analytics",
                "Unlimited history",
                "CSV export",
                "Priority support",
            ],
        ),
        PricingTier(
            tier=SubscriptionTier.PRO,
            displayName="Pro",
            monthlyProductId=settings.APPLE_PRODUCT_ID_PRO_MONTHLY,
            yearlyProductId=settings.APPLE_PRODUCT_ID_PRO_YEARLY,
            features=[
                "All Premium features",
                "Household sharing (unlimited members)",
                "Custom categories",
                "White-label reports",
            ],
        ),
    ]
    return PricingResponse(tiers=tiers, currentTier=current_tier)


@router.post("/verify", response_model=SubscriptionResponse)
async def verify_transaction(
    data: VerifyTransactionRequest,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Verify a JWS signed transaction from StoreKit and update the household's subscription.

    Only household *owners* can upgrade — a member purchasing a subscription
    on a household they don't own is a misconfiguration on the client side.
    """
    user, household = user_household

    membership = db.query(HouseholdMember).filter_by(
        user_id=user.id,
        household_id=household.id,
    ).first()
    if not membership or membership.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household owners can manage subscriptions",
        )

    try:
        sub = verify_purchase_transaction(db, household.id, data.signedTransaction)
    except AppleNotConfiguredError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except VerificationException as e:
        raise HTTPException(status_code=400, detail=f"Invalid transaction: {e}")

    return _to_response(sub)


@router.post("/apple-notification", status_code=status.HTTP_200_OK)
async def apple_server_notification(request: Request, db: Session = Depends(get_db)):
    """Receive an App Store Server Notification V2.

    Configured in App Store Connect → App → App Store Server Notifications.
    No bearer token — Apple authenticates by signing the payload JWS, and
    the signature is verified inside `handle_server_notification`.

    Apple posts JSON `{"signedPayload": "<jws>"}` to this endpoint.
    """
    body = await request.json()
    signed_payload = body.get("signedPayload")
    if not signed_payload:
        raise HTTPException(status_code=400, detail="Missing signedPayload")

    try:
        handle_server_notification(db, signed_payload)
    except AppleNotConfiguredError as e:
        # Don't 200 Apple while we're misconfigured — fail loud so we can fix.
        raise HTTPException(status_code=503, detail=str(e))
    except VerificationException as e:
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    return {"status": "ok"}
