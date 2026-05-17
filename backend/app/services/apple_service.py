"""Apple StoreKit 2 / App Store Server API integration.

This module is the single boundary between the rest of the app and Apple's
subscription system. Two things flow in:

1. **Signed transactions** posted by iOS after a `Product.purchase()` succeeds.
   We verify the JWS signature against Apple's root certificates, then
   upsert the household's `Subscription` row with the new state.

2. **Server Notifications V2** posted directly by Apple to our webhook when
   the subscription state changes server-side (renewal, refund, plan change,
   billing failure). Verified the same way and processed idempotently.

We can also actively poll Apple's App Store Server API to refresh state
(`refresh_subscription_status`) — useful for sync after the app has been
offline for a while.

Configuration lives entirely in env vars (see `app/config.py` and
`backend/APPLE_SETUP.md`). If those env vars aren't set yet, the verifier
and API client are never constructed and callers receive
`AppleNotConfiguredError` — keeps the rest of the app bootable while the
App Store Connect setup is in progress.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from appstoreserverlibrary.api_client import AppStoreServerAPIClient
from appstoreserverlibrary.models.Environment import Environment
from appstoreserverlibrary.models.JWSTransactionDecodedPayload import JWSTransactionDecodedPayload
from appstoreserverlibrary.models.ResponseBodyV2DecodedPayload import ResponseBodyV2DecodedPayload
from appstoreserverlibrary.models.NotificationTypeV2 import NotificationTypeV2
from appstoreserverlibrary.models.Subtype import Subtype
from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier

from app.config import settings
from app.models.subscription import (
    AppleNotification,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)

logger = logging.getLogger(__name__)

CERTS_DIR = Path(__file__).resolve().parent.parent / "certs" / "apple"


class AppleNotConfiguredError(RuntimeError):
    """Raised when an Apple operation is attempted with missing env vars."""


# ---------------------------------------------------------------------------
# Lazy singletons — built only when needed so missing env vars don't crash
# import time. Construction is cheap; we cache to avoid re-reading the certs.
# ---------------------------------------------------------------------------

_verifier: Optional[SignedDataVerifier] = None
_api_client: Optional[AppStoreServerAPIClient] = None


def _environment() -> Environment:
    return (
        Environment.SANDBOX
        if settings.APPLE_ENVIRONMENT.lower() == "sandbox"
        else Environment.PRODUCTION
    )


def _load_root_certs() -> List[bytes]:
    if not CERTS_DIR.exists():
        return []
    return [p.read_bytes() for p in sorted(CERTS_DIR.glob("*.cer"))]


def _is_verifier_configured() -> bool:
    return bool(settings.APPLE_BUNDLE_ID) and bool(_load_root_certs())


def _is_api_configured() -> bool:
    return all([
        settings.APPLE_BUNDLE_ID,
        settings.APPLE_ISSUER_ID,
        settings.APPLE_KEY_ID,
        settings.APPLE_PRIVATE_KEY,
    ])


def get_verifier() -> SignedDataVerifier:
    global _verifier
    if _verifier is None:
        if not _is_verifier_configured():
            raise AppleNotConfiguredError(
                "APPLE_BUNDLE_ID is unset or Apple root certificates are missing"
            )
        _verifier = SignedDataVerifier(
            root_certificates=_load_root_certs(),
            enable_online_checks=False,
            environment=_environment(),
            bundle_id=settings.APPLE_BUNDLE_ID,
            app_apple_id=settings.APPLE_APP_APPLE_ID or None,
        )
    return _verifier


def get_api_client() -> AppStoreServerAPIClient:
    global _api_client
    if _api_client is None:
        if not _is_api_configured():
            raise AppleNotConfiguredError(
                "APPLE_ISSUER_ID / APPLE_KEY_ID / APPLE_PRIVATE_KEY are not set"
            )
        _api_client = AppStoreServerAPIClient(
            signing_key=settings.APPLE_PRIVATE_KEY.encode(),
            key_id=settings.APPLE_KEY_ID,
            issuer_id=settings.APPLE_ISSUER_ID,
            bundle_id=settings.APPLE_BUNDLE_ID,
            environment=_environment(),
        )
    return _api_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def tier_for_product_id(product_id: Optional[str]) -> SubscriptionTier:
    """Map an Apple productId to its tier. Unknown products → FREE."""
    if not product_id:
        return SubscriptionTier.FREE
    if product_id in (
        settings.APPLE_PRODUCT_ID_PREMIUM_MONTHLY,
        settings.APPLE_PRODUCT_ID_PREMIUM_YEARLY,
    ):
        return SubscriptionTier.PREMIUM
    if product_id in (
        settings.APPLE_PRODUCT_ID_PRO_MONTHLY,
        settings.APPLE_PRODUCT_ID_PRO_YEARLY,
    ):
        return SubscriptionTier.PRO
    return SubscriptionTier.FREE


def _ms_to_datetime(ts_ms: Optional[int]) -> Optional[datetime]:
    """Apple ships timestamps as ms-since-epoch; we store tz-aware datetimes."""
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)


def _get_or_create_subscription(db: Session, household_id: UUID) -> Subscription:
    sub = db.query(Subscription).filter_by(household_id=household_id).first()
    if sub is None:
        sub = Subscription(
            household_id=household_id,
            tier=SubscriptionTier.FREE,
            status=SubscriptionStatus.INACTIVE,
        )
        db.add(sub)
        db.flush()
    return sub


def _apply_transaction_to_subscription(
    sub: Subscription,
    tx: JWSTransactionDecodedPayload,
) -> None:
    """Apply a verified transaction's fields to the subscription row.

    Caller is responsible for committing.
    """
    sub.apple_original_transaction_id = tx.originalTransactionId
    sub.apple_product_id = tx.productId
    sub.apple_environment = tx.rawEnvironment or sub.apple_environment

    sub.current_period_start = _ms_to_datetime(tx.purchaseDate)
    sub.current_period_end = _ms_to_datetime(tx.expiresDate)

    if tx.revocationDate:
        sub.revocation_date = _ms_to_datetime(tx.revocationDate)
        sub.revocation_reason = tx.rawRevocationReason
        sub.tier = SubscriptionTier.FREE
        sub.status = SubscriptionStatus.REFUNDED
    else:
        sub.tier = tier_for_product_id(tx.productId)
        sub.status = SubscriptionStatus.ACTIVE


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def verify_purchase_transaction(
    db: Session,
    household_id: UUID,
    signed_transaction: str,
) -> Subscription:
    """Verify a JWS transaction from the iOS app and upsert the subscription.

    Called from `POST /subscriptions/verify` after a successful StoreKit
    purchase or `Transaction.currentEntitlement` restore.

    Raises:
        AppleNotConfiguredError: env vars missing.
        VerificationException: signature/audience invalid.
    """
    verifier = get_verifier()
    tx: JWSTransactionDecodedPayload = verifier.verify_and_decode_signed_transaction(
        signed_transaction
    )

    sub = _get_or_create_subscription(db, household_id)
    _apply_transaction_to_subscription(sub, tx)
    db.commit()
    db.refresh(sub)
    return sub


def handle_server_notification(
    db: Session,
    signed_payload: str,
) -> AppleNotification:
    """Verify and idempotently process an App Store Server Notification V2.

    Apple may retry on non-2xx for up to 3 days, so duplicate notifications
    (same `notificationUUID`) are no-ops.
    """
    verifier = get_verifier()
    payload: ResponseBodyV2DecodedPayload = verifier.verify_and_decode_notification(
        signed_payload
    )

    # Idempotency: have we seen this notificationUUID before?
    existing = db.query(AppleNotification).filter_by(
        notification_uuid=payload.notificationUUID,
    ).first()
    if existing and existing.processed:
        return existing

    data = payload.data
    signed_tx_info = data.signedTransactionInfo if data else None
    tx: Optional[JWSTransactionDecodedPayload] = (
        verifier.verify_and_decode_signed_transaction(signed_tx_info)
        if signed_tx_info
        else None
    )

    record = existing or AppleNotification(
        notification_uuid=payload.notificationUUID,
        notification_type=payload.rawNotificationType or "",
        subtype=payload.rawSubtype,
        apple_original_transaction_id=(tx.originalTransactionId if tx else None),
        bundle_id=(data.bundleId if data else None),
        environment=(data.rawEnvironment if data else None),
        raw_payload=signed_payload,
        processed=False,
    )
    if existing is None:
        db.add(record)
        db.flush()

    try:
        if tx is not None:
            _route_notification(db, payload, tx)
        record.processed = True
        record.processed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        logger.exception("Failed to process Apple notification %s", payload.notificationUUID)
        record.error_message = str(exc)
        db.commit()
        raise

    return record


def _route_notification(
    db: Session,
    payload: ResponseBodyV2DecodedPayload,
    tx: JWSTransactionDecodedPayload,
) -> None:
    """Apply notification effects to the subscription identified by the JWS tx.

    The household is found via the matching `apple_original_transaction_id`.
    If no subscription claims this transaction (e.g. the user signed up on a
    device that never hit `/subscriptions/verify`), we ignore — the next
    `/verify` or `/refresh` call will reconcile.
    """
    sub = db.query(Subscription).filter_by(
        apple_original_transaction_id=tx.originalTransactionId,
    ).first()
    if sub is None:
        logger.warning(
            "Notification %s references unknown originalTransactionId=%s",
            payload.notificationUUID,
            tx.originalTransactionId,
        )
        return

    ntype = payload.notificationType
    subtype = payload.subtype

    if ntype in (NotificationTypeV2.SUBSCRIBED, NotificationTypeV2.DID_RENEW):
        _apply_transaction_to_subscription(sub, tx)

    elif ntype == NotificationTypeV2.DID_CHANGE_RENEWAL_PREF:
        # Plan switch (e.g. monthly -> yearly). New product takes effect at
        # the next renewal; for now we just record the auto-renew product.
        sub.auto_renew_product_id = tx.productId

    elif ntype == NotificationTypeV2.DID_CHANGE_RENEWAL_STATUS:
        sub.auto_renew_status = (subtype == Subtype.AUTO_RENEW_ENABLED)

    elif ntype == NotificationTypeV2.DID_FAIL_TO_RENEW:
        if subtype == Subtype.GRACE_PERIOD:
            sub.status = SubscriptionStatus.IN_GRACE_PERIOD
        else:
            sub.status = SubscriptionStatus.IN_BILLING_RETRY

    elif ntype in (NotificationTypeV2.EXPIRED, NotificationTypeV2.GRACE_PERIOD_EXPIRED):
        sub.status = SubscriptionStatus.EXPIRED
        sub.tier = SubscriptionTier.FREE

    elif ntype in (NotificationTypeV2.REFUND, NotificationTypeV2.REVOKE):
        sub.status = (
            SubscriptionStatus.REFUNDED if ntype == NotificationTypeV2.REFUND
            else SubscriptionStatus.REVOKED
        )
        sub.tier = SubscriptionTier.FREE
        sub.revocation_date = _ms_to_datetime(tx.revocationDate) or datetime.now(timezone.utc)
        sub.revocation_reason = tx.rawRevocationReason

    elif ntype == NotificationTypeV2.REFUND_REVERSED:
        # Apple reversed a prior refund — the user gets entitlement back.
        sub.revocation_date = None
        sub.revocation_reason = None
        _apply_transaction_to_subscription(sub, tx)

    # NotificationTypeV2.TEST and other non-subscription types: no-op.
