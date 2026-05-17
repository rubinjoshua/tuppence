"""Subscription system tests - API endpoints and Stripe integration"""

import pytest
from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import patch, MagicMock
import json

from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus, WebhookEvent
from app.models.session import Session
from app.utils.auth import hash_password


@pytest.fixture
def auth_headers(client, db):
    """Create authenticated user and return auth headers"""
    # Create user
    user = User(
        email="test@example.com",
        password_hash=hash_password("TestPass123"),
        full_name="Test User"
    )
    db.add(user)
    db.flush()

    # Create household
    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    # Create membership (owner role)
    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)
    db.flush()

    # Create free subscription
    subscription = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.FREE,
        status=SubscriptionStatus.ACTIVE
    )
    db.add(subscription)
    db.flush()

    # Create session
    session = Session(
        user_id=user.id,
        household_id=household.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(session)
    db.commit()

    return {
        "Authorization": f"Bearer {session.id}",
        "user": user,
        "household": household,
        "subscription": subscription
    }


@pytest.fixture
def member_headers(client, db, auth_headers):
    """Create authenticated member (non-owner) and return auth headers"""
    household = auth_headers["household"]

    # Create member user
    member = User(
        email="member@example.com",
        password_hash=hash_password("MemberPass123"),
        full_name="Member User"
    )
    db.add(member)
    db.flush()

    # Create membership (member role, not owner)
    membership = HouseholdMember(
        household_id=household.id,
        user_id=member.id,
        role="member"
    )
    db.add(membership)
    db.flush()

    # Create session
    session = Session(
        user_id=member.id,
        household_id=household.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(session)
    db.commit()

    return {
        "Authorization": f"Bearer {session.id}",
        "user": member
    }


# ============================================================================
# GET /subscriptions/status Tests
# ============================================================================

def test_get_subscription_status_success(client, db, auth_headers):
    """Test GET /subscriptions/status returns subscription info"""
    response = client.get(
        "/subscriptions/status",
        headers={"Authorization": auth_headers["Authorization"]}
    )

    assert response.status_code == 200
    data = response.json()

    assert "householdId" in data
    assert "tier" in data
    assert "status" in data
    assert data["tier"] == "free"
    assert data["status"] == "active"
    assert data["cancelAtPeriodEnd"] == False


def test_get_subscription_status_with_premium_tier(client, db, auth_headers):
    """Test GET /subscriptions/status with premium subscription"""
    subscription = auth_headers["subscription"]
    subscription.tier = SubscriptionTier.PREMIUM
    subscription.stripe_customer_id = "cus_test123"
    subscription.stripe_subscription_id = "sub_test123"
    subscription.current_period_start = datetime.now(timezone.utc)
    subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
    db.commit()

    response = client.get(
        "/subscriptions/status",
        headers={"Authorization": auth_headers["Authorization"]}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["tier"] == "premium"
    assert data["status"] == "active"
    assert "currentPeriodStart" in data
    assert "currentPeriodEnd" in data


def test_get_subscription_status_unauthenticated(client, db):
    """Test GET /subscriptions/status without authentication fails"""
    response = client.get("/subscriptions/status")
    assert response.status_code == 401


# ============================================================================
# GET /subscriptions/pricing Tests
# ============================================================================

def test_get_pricing_success(client, db, auth_headers):
    """Test GET /subscriptions/pricing returns pricing tiers"""
    response = client.get(
        "/subscriptions/pricing",
        headers={"Authorization": auth_headers["Authorization"]}
    )

    assert response.status_code == 200
    data = response.json()

    assert "tiers" in data
    assert "currentTier" in data
    assert len(data["tiers"]) == 3  # FREE, PREMIUM, PRO
    assert data["currentTier"] == "free"

    # Check tier structure
    free_tier = [t for t in data["tiers"] if t["tier"] == "free"][0]
    assert free_tier["displayName"] == "Free"
    assert free_tier["monthlyPrice"] == "$0"
    assert "features" in free_tier
    assert len(free_tier["features"]) > 0


def test_get_pricing_shows_current_premium_tier(client, db, auth_headers):
    """Test GET /subscriptions/pricing shows current premium tier"""
    subscription = auth_headers["subscription"]
    subscription.tier = SubscriptionTier.PREMIUM
    db.commit()

    response = client.get(
        "/subscriptions/pricing",
        headers={"Authorization": auth_headers["Authorization"]}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["currentTier"] == "premium"


# ============================================================================
# POST /subscriptions/checkout Tests
# ============================================================================

@patch('app.services.stripe_service.stripe.Customer.create')
@patch('app.services.stripe_service.stripe.checkout.Session.create')
def test_create_checkout_session_success(mock_session_create, mock_customer_create, client, db, auth_headers):
    """Test POST /subscriptions/checkout creates checkout session"""
    # Mock Stripe API responses
    mock_customer_create.return_value = MagicMock(id="cus_test123")
    mock_session_create.return_value = MagicMock(
        id="cs_test123",
        url="https://checkout.stripe.com/session/cs_test123"
    )

    response = client.post(
        "/subscriptions/checkout",
        headers={"Authorization": auth_headers["Authorization"]},
        json={
            "price_id": "price_premium_monthly",
            "success_url": "https://app.example.com/success",
            "cancel_url": "https://app.example.com/cancel"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "sessionId" in data
    assert "sessionUrl" in data
    assert data["sessionId"] == "cs_test123"
    assert "checkout.stripe.com" in data["sessionUrl"]

    # Verify customer was created
    mock_customer_create.assert_called_once()

    # Verify checkout session was created
    mock_session_create.assert_called_once()


@patch('app.services.stripe_service.stripe.checkout.Session.create')
def test_create_checkout_session_reuses_customer(mock_session_create, client, db, auth_headers):
    """Test POST /subscriptions/checkout reuses existing Stripe customer"""
    # Set existing customer ID
    subscription = auth_headers["subscription"]
    subscription.stripe_customer_id = "cus_existing123"
    db.commit()

    mock_session_create.return_value = MagicMock(
        id="cs_test123",
        url="https://checkout.stripe.com/session/cs_test123"
    )

    response = client.post(
        "/subscriptions/checkout",
        headers={"Authorization": auth_headers["Authorization"]},
        json={
            "price_id": "price_premium_monthly",
            "success_url": "https://app.example.com/success",
            "cancel_url": "https://app.example.com/cancel"
        }
    )

    assert response.status_code == 200

    # Verify checkout session used existing customer
    call_args = mock_session_create.call_args
    assert call_args[1]["customer"] == "cus_existing123"


def test_create_checkout_session_member_forbidden(client, db, member_headers):
    """Test POST /subscriptions/checkout fails for non-owner"""
    response = client.post(
        "/subscriptions/checkout",
        headers={"Authorization": member_headers["Authorization"]},
        json={
            "price_id": "price_premium_monthly",
            "success_url": "https://app.example.com/success",
            "cancel_url": "https://app.example.com/cancel"
        }
    )

    assert response.status_code == 403
    assert "Only household owners" in response.json()["detail"]


def test_create_checkout_session_unauthenticated(client, db):
    """Test POST /subscriptions/checkout without authentication fails"""
    response = client.post(
        "/subscriptions/checkout",
        json={
            "price_id": "price_premium_monthly",
            "success_url": "https://app.example.com/success",
            "cancel_url": "https://app.example.com/cancel"
        }
    )

    assert response.status_code == 401


# ============================================================================
# POST /subscriptions/portal Tests
# ============================================================================

@patch('app.services.stripe_service.stripe.billing_portal.Session.create')
def test_create_portal_session_success(mock_portal_create, client, db, auth_headers):
    """Test POST /subscriptions/portal creates portal session"""
    # Set existing customer ID
    subscription = auth_headers["subscription"]
    subscription.stripe_customer_id = "cus_test123"
    db.commit()

    mock_portal_create.return_value = MagicMock(
        url="https://billing.stripe.com/portal/session/ps_test123"
    )

    response = client.post(
        "/subscriptions/portal",
        headers={"Authorization": auth_headers["Authorization"]},
        json={
            "return_url": "https://app.example.com/settings"
        }
    )

    assert response.status_code == 200
    data = response.json()

    assert "portalUrl" in data
    assert "billing.stripe.com" in data["portalUrl"]

    # Verify portal session was created with correct customer
    call_args = mock_portal_create.call_args
    assert call_args[1]["customer"] == "cus_test123"


def test_create_portal_session_no_customer(client, db, auth_headers):
    """Test POST /subscriptions/portal fails without Stripe customer"""
    # Subscription has no stripe_customer_id
    response = client.post(
        "/subscriptions/portal",
        headers={"Authorization": auth_headers["Authorization"]},
        json={
            "return_url": "https://app.example.com/settings"
        }
    )

    assert response.status_code == 400
    assert "No active subscription" in response.json()["detail"]


def test_create_portal_session_member_forbidden(client, db, member_headers):
    """Test POST /subscriptions/portal fails for non-owner"""
    response = client.post(
        "/subscriptions/portal",
        headers={"Authorization": member_headers["Authorization"]},
        json={
            "return_url": "https://app.example.com/settings"
        }
    )

    assert response.status_code == 403


# ============================================================================
# GET /subscriptions/publishable-key Tests
# ============================================================================

def test_get_publishable_key(client, db):
    """Test GET /subscriptions/publishable-key returns key"""
    response = client.get("/subscriptions/publishable-key")

    assert response.status_code == 200
    data = response.json()

    assert "publishableKey" in data
    assert data["publishableKey"].startswith("pk_")


# ============================================================================
# POST /subscriptions/webhook Tests
# ============================================================================

@patch('app.services.stripe_service.stripe.Webhook.construct_event')
def test_webhook_checkout_completed(mock_construct_event, client, db, auth_headers):
    """Test webhook processes checkout.session.completed event"""
    household_id = str(auth_headers["household"].id)

    # Mock webhook event
    mock_construct_event.return_value = {
        'id': 'evt_test123',
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'customer': 'cus_test123',
                'metadata': {
                    'household_id': household_id
                }
            }
        }
    }

    response = client.post(
        "/subscriptions/webhook",
        headers={"stripe-signature": "test_signature"},
        content=b'{"type": "checkout.session.completed"}'
    )

    assert response.status_code == 200

    # Verify subscription updated
    subscription = db.query(Subscription).filter_by(household_id=uuid.UUID(household_id)).first()
    assert subscription.stripe_customer_id == "cus_test123"

    # Verify webhook event logged
    webhook_event = db.query(WebhookEvent).filter_by(stripe_event_id="evt_test123").first()
    assert webhook_event is not None
    assert webhook_event.processed == "true"


@patch('app.services.stripe_service.stripe.Webhook.construct_event')
def test_webhook_subscription_created(mock_construct_event, client, db, auth_headers):
    """Test webhook processes customer.subscription.created event"""
    subscription = auth_headers["subscription"]
    subscription.stripe_customer_id = "cus_test123"
    db.commit()

    # Mock webhook event
    mock_construct_event.return_value = {
        'id': 'evt_test456',
        'type': 'customer.subscription.created',
        'data': {
            'object': {
                'id': 'sub_test123',
                'customer': 'cus_test123',
                'status': 'active',
                'items': {
                    'data': [
                        {
                            'price': {
                                'id': 'price_premium_monthly'
                            }
                        }
                    ]
                },
                'current_period_start': 1735689600,  # 2025-01-01
                'current_period_end': 1738368000,    # 2025-02-01
                'cancel_at_period_end': False
            }
        }
    }

    # Set price ID in config for tier mapping
    with patch('app.services.stripe_service.settings.STRIPE_PREMIUM_MONTHLY_PRICE_ID', 'price_premium_monthly'):
        response = client.post(
            "/subscriptions/webhook",
            headers={"stripe-signature": "test_signature"},
            content=b'{"type": "customer.subscription.created"}'
        )

    assert response.status_code == 200

    # Verify subscription updated
    db.refresh(subscription)
    assert subscription.stripe_subscription_id == "sub_test123"
    assert subscription.tier == SubscriptionTier.PREMIUM
    assert subscription.status == SubscriptionStatus.ACTIVE


@patch('app.services.stripe_service.stripe.Webhook.construct_event')
def test_webhook_subscription_deleted(mock_construct_event, client, db, auth_headers):
    """Test webhook processes customer.subscription.deleted event"""
    subscription = auth_headers["subscription"]
    subscription.stripe_customer_id = "cus_test123"
    subscription.stripe_subscription_id = "sub_test123"
    subscription.tier = SubscriptionTier.PREMIUM
    db.commit()

    # Mock webhook event
    mock_construct_event.return_value = {
        'id': 'evt_test789',
        'type': 'customer.subscription.deleted',
        'data': {
            'object': {
                'id': 'sub_test123',
                'customer': 'cus_test123'
            }
        }
    }

    response = client.post(
        "/subscriptions/webhook",
        headers={"stripe-signature": "test_signature"},
        content=b'{"type": "customer.subscription.deleted"}'
    )

    assert response.status_code == 200

    # Verify subscription reverted to free tier
    db.refresh(subscription)
    assert subscription.tier == SubscriptionTier.FREE
    assert subscription.status == SubscriptionStatus.CANCELED
    assert subscription.canceled_at is not None


@patch('app.services.stripe_service.stripe.Webhook.construct_event')
def test_webhook_idempotency(mock_construct_event, client, db, auth_headers):
    """Test webhook processes events idempotently (no duplicate processing)"""
    household_id = str(auth_headers["household"].id)

    # Mock webhook event
    mock_construct_event.return_value = {
        'id': 'evt_duplicate123',
        'type': 'checkout.session.completed',
        'data': {
            'object': {
                'customer': 'cus_test123',
                'metadata': {
                    'household_id': household_id
                }
            }
        }
    }

    # Send webhook twice
    response1 = client.post(
        "/subscriptions/webhook",
        headers={"stripe-signature": "test_signature"},
        content=b'{"type": "checkout.session.completed"}'
    )

    response2 = client.post(
        "/subscriptions/webhook",
        headers={"stripe-signature": "test_signature"},
        content=b'{"type": "checkout.session.completed"}'
    )

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Verify only one webhook event logged
    webhook_events = db.query(WebhookEvent).filter_by(stripe_event_id="evt_duplicate123").all()
    assert len(webhook_events) == 1
    assert webhook_events[0].processed == "true"


def test_webhook_invalid_signature(client, db):
    """Test webhook rejects invalid signature"""
    with patch('app.services.stripe_service.stripe.Webhook.construct_event') as mock_construct:
        # Mock signature verification failure
        import stripe as stripe_module
        mock_construct.side_effect = stripe_module.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )

        response = client.post(
            "/subscriptions/webhook",
            headers={"stripe-signature": "invalid_signature"},
            content=b'{"type": "test.event"}'
        )

        assert response.status_code == 400
        assert "Invalid signature" in response.json()["detail"]


# ============================================================================
# Subscription Model Tests
# ============================================================================

def test_subscription_is_active_property(db):
    """Test Subscription.is_active property"""
    household = Household(name="Test")
    db.add(household)
    db.flush()

    # Active subscription
    sub_active = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.PREMIUM,
        status=SubscriptionStatus.ACTIVE
    )
    assert sub_active.is_active is True

    # Trialing subscription (also active)
    sub_trialing = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.PREMIUM,
        status=SubscriptionStatus.TRIALING
    )
    assert sub_trialing.is_active is True

    # Canceled subscription (not active)
    sub_canceled = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.PREMIUM,
        status=SubscriptionStatus.CANCELED
    )
    assert sub_canceled.is_active is False

    # Past due subscription (not active)
    sub_past_due = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.PREMIUM,
        status=SubscriptionStatus.PAST_DUE
    )
    assert sub_past_due.is_active is False


def test_subscription_is_premium_or_higher_property(db):
    """Test Subscription.is_premium_or_higher property"""
    household = Household(name="Test")
    db.add(household)
    db.flush()

    # Free tier (not premium)
    sub_free = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.FREE,
        status=SubscriptionStatus.ACTIVE
    )
    assert sub_free.is_premium_or_higher is False

    # Premium tier (active)
    sub_premium = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.PREMIUM,
        status=SubscriptionStatus.ACTIVE
    )
    assert sub_premium.is_premium_or_higher is True

    # Pro tier (active)
    sub_pro = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.PRO,
        status=SubscriptionStatus.ACTIVE
    )
    assert sub_pro.is_premium_or_higher is True

    # Premium tier (canceled - not active)
    sub_premium_canceled = Subscription(
        household_id=household.id,
        tier=SubscriptionTier.PREMIUM,
        status=SubscriptionStatus.CANCELED
    )
    assert sub_premium_canceled.is_premium_or_higher is False
