"""Tests for Apple StoreKit subscription endpoints + service."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.household import Household, HouseholdMember
from app.models.session import Session
from app.models.subscription import (
    AppleNotification,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)
from app.models.user import User
from app.services import apple_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _build_account(db, email: str, role: str = "owner"):
    user = User(email=email, password_hash="x", full_name=email.split("@")[0], is_active=True)
    db.add(user)
    db.flush()
    household = Household(name=f"{email}'s House")
    db.add(household)
    db.flush()
    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role=role))
    session = Session(
        user_id=user.id,
        household_id=household.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(session)
    db.commit()
    return {
        "user_id": user.id,
        "household_id": household.id,
        "headers": {"Authorization": f"Bearer {session.id}"},
    }


@pytest.fixture
def owner(client, db):
    return _build_account(db, "owner@test.com", role="owner")


@pytest.fixture
def member(client, db):
    return _build_account(db, "member@test.com", role="member")


def _fake_transaction(
    *,
    original_tx_id="100000000000001",
    product_id="com.joshuarubin.tuppence.premium.monthly",
    expires_in_days=30,
    revocation_date=None,
    revocation_reason=None,
):
    """Construct an object shaped like JWSTransactionDecodedPayload for tests."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    expires_ms = (
        int((datetime.now(timezone.utc) + timedelta(days=expires_in_days)).timestamp() * 1000)
        if expires_in_days else None
    )
    return SimpleNamespace(
        originalTransactionId=original_tx_id,
        transactionId=original_tx_id,
        productId=product_id,
        purchaseDate=now_ms,
        expiresDate=expires_ms,
        revocationDate=revocation_date,
        rawRevocationReason=revocation_reason,
        rawEnvironment="Sandbox",
        environment=None,
        bundleId="com.joshuarubin.tuppence",
    )


# ---------------------------------------------------------------------------
# Service-level tests (no HTTP)
# ---------------------------------------------------------------------------

class TestTierMapping:
    def test_premium_monthly_maps_to_premium(self):
        assert apple_service.tier_for_product_id(
            "com.joshuarubin.tuppence.premium.monthly"
        ) == SubscriptionTier.PREMIUM

    def test_pro_yearly_maps_to_pro(self):
        assert apple_service.tier_for_product_id(
            "com.joshuarubin.tuppence.pro.yearly"
        ) == SubscriptionTier.PRO

    def test_unknown_product_maps_to_free(self):
        assert apple_service.tier_for_product_id("com.something.unknown") == SubscriptionTier.FREE

    def test_none_maps_to_free(self):
        assert apple_service.tier_for_product_id(None) == SubscriptionTier.FREE


class TestVerifyPurchaseTransaction:
    def test_creates_subscription_on_first_purchase(self, db, owner):
        fake_tx = _fake_transaction()
        with patch.object(apple_service, "get_verifier") as gv:
            gv.return_value.verify_and_decode_signed_transaction.return_value = fake_tx
            sub = apple_service.verify_purchase_transaction(
                db, owner["household_id"], "fake-jws"
            )

        assert sub.tier == SubscriptionTier.PREMIUM
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.apple_original_transaction_id == "100000000000001"
        assert sub.is_active is True

    def test_refund_downgrades_to_free(self, db, owner):
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        fake_tx = _fake_transaction(revocation_date=now_ms, revocation_reason=1)
        with patch.object(apple_service, "get_verifier") as gv:
            gv.return_value.verify_and_decode_signed_transaction.return_value = fake_tx
            sub = apple_service.verify_purchase_transaction(
                db, owner["household_id"], "fake-jws"
            )

        assert sub.tier == SubscriptionTier.FREE
        assert sub.status == SubscriptionStatus.REFUNDED
        assert sub.revocation_date is not None


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------

class TestStatusEndpoint:
    def test_unauthenticated_401(self, client):
        response = client.get("/subscriptions/status")
        assert response.status_code == 401

    def test_returns_free_when_no_subscription_row(self, client, owner):
        response = client.get("/subscriptions/status", headers=owner["headers"])
        assert response.status_code == 200
        body = response.json()
        assert body["tier"] == "free"
        assert body["isActive"] is False

    def test_returns_premium_when_subscribed(self, client, db, owner):
        db.add(Subscription(
            household_id=owner["household_id"],
            tier=SubscriptionTier.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            apple_original_transaction_id="abc",
            apple_product_id="com.joshuarubin.tuppence.premium.monthly",
            apple_environment="Sandbox",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        ))
        db.commit()

        body = client.get("/subscriptions/status", headers=owner["headers"]).json()
        assert body["tier"] == "premium"
        assert body["isActive"] is True
        assert body["productId"] == "com.joshuarubin.tuppence.premium.monthly"


class TestPricingEndpoint:
    def test_returns_three_tiers(self, client, owner):
        body = client.get("/subscriptions/pricing", headers=owner["headers"]).json()
        assert [t["tier"] for t in body["tiers"]] == ["free", "premium", "pro"]
        assert body["currentTier"] == "free"

    def test_premium_tier_includes_product_ids(self, client, owner):
        body = client.get("/subscriptions/pricing", headers=owner["headers"]).json()
        premium = next(t for t in body["tiers"] if t["tier"] == "premium")
        assert premium["monthlyProductId"]
        assert premium["yearlyProductId"]


class TestVerifyEndpoint:
    def test_member_cannot_verify(self, client, member):
        response = client.post(
            "/subscriptions/verify",
            json={"signedTransaction": "fake-jws"},
            headers=member["headers"],
        )
        assert response.status_code == 403
        assert "owner" in response.json()["detail"].lower()

    def test_owner_can_verify(self, client, db, owner):
        fake_tx = _fake_transaction()
        with patch.object(apple_service, "get_verifier") as gv:
            gv.return_value.verify_and_decode_signed_transaction.return_value = fake_tx
            response = client.post(
                "/subscriptions/verify",
                json={"signedTransaction": "fake-jws"},
                headers=owner["headers"],
            )
        assert response.status_code == 200
        body = response.json()
        assert body["tier"] == "premium"
        assert body["isActive"] is True

    def test_returns_503_when_apple_not_configured(self, client, owner):
        with patch.object(apple_service, "get_verifier") as gv:
            gv.side_effect = apple_service.AppleNotConfiguredError("nope")
            response = client.post(
                "/subscriptions/verify",
                json={"signedTransaction": "fake-jws"},
                headers=owner["headers"],
            )
        assert response.status_code == 503


class TestAppleNotificationEndpoint:
    def test_missing_payload_400(self, client):
        response = client.post("/subscriptions/apple-notification", json={})
        assert response.status_code == 400

    def test_idempotent_processing(self, client, db, owner):
        """Same notificationUUID twice → only one AppleNotification row, no double-apply."""
        db.add(Subscription(
            household_id=owner["household_id"],
            tier=SubscriptionTier.PREMIUM,
            status=SubscriptionStatus.ACTIVE,
            apple_original_transaction_id="tx-renew-1",
            apple_product_id="com.joshuarubin.tuppence.premium.monthly",
            apple_environment="Sandbox",
        ))
        db.commit()

        fake_tx = _fake_transaction(original_tx_id="tx-renew-1", expires_in_days=60)
        fake_payload = SimpleNamespace(
            notificationUUID="notif-001",
            rawNotificationType="DID_RENEW",
            notificationType=apple_service.NotificationTypeV2.DID_RENEW,
            rawSubtype=None,
            subtype=None,
            data=SimpleNamespace(
                signedTransactionInfo="inner-jws",
                bundleId="com.joshuarubin.tuppence",
                rawEnvironment="Sandbox",
            ),
        )

        with patch.object(apple_service, "get_verifier") as gv:
            verifier = gv.return_value
            verifier.verify_and_decode_notification.return_value = fake_payload
            verifier.verify_and_decode_signed_transaction.return_value = fake_tx

            r1 = client.post("/subscriptions/apple-notification", json={"signedPayload": "outer"})
            r2 = client.post("/subscriptions/apple-notification", json={"signedPayload": "outer"})

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert db.query(AppleNotification).count() == 1
        notif = db.query(AppleNotification).one()
        assert notif.processed is True
