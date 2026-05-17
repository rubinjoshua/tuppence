"""Stripe service - handles Stripe API operations"""

import stripe
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timezone
import uuid

from app.config import settings
from app.models.subscription import Subscription, SubscriptionTier, SubscriptionStatus, WebhookEvent
from app.models.household import Household

# Initialize Stripe with API key
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for Stripe operations (checkout, webhooks, customer portal)"""

    @staticmethod
    def get_price_tier(price_id: str) -> SubscriptionTier:
        """Map Stripe price ID to subscription tier"""
        if price_id in [settings.STRIPE_PREMIUM_MONTHLY_PRICE_ID, settings.STRIPE_PREMIUM_YEARLY_PRICE_ID]:
            return SubscriptionTier.PREMIUM
        elif price_id in [settings.STRIPE_PRO_MONTHLY_PRICE_ID, settings.STRIPE_PRO_YEARLY_PRICE_ID]:
            return SubscriptionTier.PRO
        else:
            return SubscriptionTier.FREE

    @staticmethod
    def create_checkout_session(
        db: Session,
        household_id: uuid.UUID,
        price_id: str,
        success_url: str,
        cancel_url: str
    ) -> dict:
        """
        Create Stripe checkout session for subscription.

        Args:
            db: Database session
            household_id: Household to subscribe
            price_id: Stripe price ID for the subscription tier
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect if payment is canceled

        Returns:
            dict with 'session_id' and 'session_url'

        Raises:
            ValueError: If household not found or subscription already exists
        """
        # Verify household exists
        household = db.query(Household).filter_by(id=household_id).first()
        if not household:
            raise ValueError(f"Household {household_id} not found")

        # Get or create subscription record
        subscription = db.query(Subscription).filter_by(household_id=household_id).first()
        if not subscription:
            subscription = Subscription(household_id=household_id)
            db.add(subscription)
            db.flush()

        # Create or get Stripe customer
        if subscription.stripe_customer_id:
            customer_id = subscription.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                metadata={
                    "household_id": str(household_id),
                    "household_name": household.name
                }
            )
            customer_id = customer.id
            subscription.stripe_customer_id = customer_id
            db.commit()

        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'household_id': str(household_id),
            },
        )

        return {
            'session_id': session.id,
            'session_url': session.url
        }

    @staticmethod
    def create_customer_portal_session(
        db: Session,
        household_id: uuid.UUID,
        return_url: str
    ) -> str:
        """
        Create Stripe customer portal session for subscription management.

        Args:
            db: Database session
            household_id: Household to manage
            return_url: URL to redirect after portal session

        Returns:
            Portal session URL

        Raises:
            ValueError: If household has no active Stripe subscription
        """
        subscription = db.query(Subscription).filter_by(household_id=household_id).first()
        if not subscription or not subscription.stripe_customer_id:
            raise ValueError("No active subscription found for this household")

        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )

        return session.url

    @staticmethod
    def handle_webhook_event(
        db: Session,
        event_id: str,
        event_type: str,
        event_data: dict,
        payload: str
    ) -> None:
        """
        Process Stripe webhook event idempotently.

        Args:
            db: Database session
            event_id: Stripe event ID (for idempotency)
            event_type: Stripe event type
            event_data: Event data payload
            payload: Full JSON payload (for logging)

        Raises:
            Exception: If event processing fails (will be logged)
        """
        # Check if already processed (idempotency)
        existing = db.query(WebhookEvent).filter_by(stripe_event_id=event_id).first()
        if existing and existing.processed == "true":
            return  # Already processed, skip

        # Create webhook event record
        if not existing:
            webhook_event = WebhookEvent(
                stripe_event_id=event_id,
                event_type=event_type,
                payload=payload,
                processed="false"
            )
            db.add(webhook_event)
            db.commit()
        else:
            webhook_event = existing

        try:
            # Route to appropriate handler
            if event_type == 'checkout.session.completed':
                StripeService._handle_checkout_completed(db, event_data)
            elif event_type == 'customer.subscription.created':
                StripeService._handle_subscription_created(db, event_data)
            elif event_type == 'customer.subscription.updated':
                StripeService._handle_subscription_updated(db, event_data)
            elif event_type == 'customer.subscription.deleted':
                StripeService._handle_subscription_deleted(db, event_data)
            elif event_type == 'invoice.payment_succeeded':
                StripeService._handle_payment_succeeded(db, event_data)
            elif event_type == 'invoice.payment_failed':
                StripeService._handle_payment_failed(db, event_data)

            # Mark as processed
            webhook_event.processed = "true"
            webhook_event.processed_at = datetime.now(timezone.utc)
            db.commit()

        except Exception as e:
            # Log error and re-raise
            webhook_event.error_message = str(e)
            db.commit()
            raise

    @staticmethod
    def _handle_checkout_completed(db: Session, event_data: dict) -> None:
        """Handle checkout.session.completed event"""
        session = event_data['object']
        household_id = uuid.UUID(session['metadata']['household_id'])

        subscription = db.query(Subscription).filter_by(household_id=household_id).first()
        if subscription:
            subscription.stripe_customer_id = session['customer']
            db.commit()

    @staticmethod
    def _handle_subscription_created(db: Session, event_data: dict) -> None:
        """Handle customer.subscription.created event"""
        stripe_subscription = event_data['object']
        customer_id = stripe_subscription['customer']

        subscription = db.query(Subscription).filter_by(stripe_customer_id=customer_id).first()
        if subscription:
            price_id = stripe_subscription['items']['data'][0]['price']['id']
            subscription.stripe_subscription_id = stripe_subscription['id']
            subscription.stripe_price_id = price_id
            subscription.tier = StripeService.get_price_tier(price_id)
            subscription.status = SubscriptionStatus(stripe_subscription['status'])
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription['current_period_start'], tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription['current_period_end'], tz=timezone.utc
            )
            subscription.cancel_at_period_end = "true" if stripe_subscription.get('cancel_at_period_end') else "false"
            db.commit()

    @staticmethod
    def _handle_subscription_updated(db: Session, event_data: dict) -> None:
        """Handle customer.subscription.updated event"""
        stripe_subscription = event_data['object']

        subscription = db.query(Subscription).filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()

        if subscription:
            price_id = stripe_subscription['items']['data'][0]['price']['id']
            subscription.stripe_price_id = price_id
            subscription.tier = StripeService.get_price_tier(price_id)
            subscription.status = SubscriptionStatus(stripe_subscription['status'])
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription['current_period_start'], tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription['current_period_end'], tz=timezone.utc
            )
            subscription.cancel_at_period_end = "true" if stripe_subscription.get('cancel_at_period_end') else "false"

            if stripe_subscription.get('canceled_at'):
                subscription.canceled_at = datetime.fromtimestamp(
                    stripe_subscription['canceled_at'], tz=timezone.utc
                )

            db.commit()

    @staticmethod
    def _handle_subscription_deleted(db: Session, event_data: dict) -> None:
        """Handle customer.subscription.deleted event"""
        stripe_subscription = event_data['object']

        subscription = db.query(Subscription).filter_by(
            stripe_subscription_id=stripe_subscription['id']
        ).first()

        if subscription:
            subscription.status = SubscriptionStatus.CANCELED
            subscription.tier = SubscriptionTier.FREE
            subscription.canceled_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def _handle_payment_succeeded(db: Session, event_data: dict) -> None:
        """Handle invoice.payment_succeeded event"""
        invoice = event_data['object']
        subscription_id = invoice.get('subscription')

        if subscription_id:
            subscription = db.query(Subscription).filter_by(
                stripe_subscription_id=subscription_id
            ).first()

            if subscription and subscription.status != SubscriptionStatus.ACTIVE:
                subscription.status = SubscriptionStatus.ACTIVE
                db.commit()

    @staticmethod
    def _handle_payment_failed(db: Session, event_data: dict) -> None:
        """Handle invoice.payment_failed event"""
        invoice = event_data['object']
        subscription_id = invoice.get('subscription')

        if subscription_id:
            subscription = db.query(Subscription).filter_by(
                stripe_subscription_id=subscription_id
            ).first()

            if subscription:
                subscription.status = SubscriptionStatus.PAST_DUE
                db.commit()
