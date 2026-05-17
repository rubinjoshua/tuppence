"""Add subscriptions and webhook_events tables

Revision ID: 008
Revises: 007
Create Date: 2026-04-07

Adds subscription management tables for Stripe integration:
- subscriptions: Tracks household subscription status and Stripe metadata
- webhook_events: Logs Stripe webhook events for idempotent processing
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create subscriptions and webhook_events tables"""

    # Create subscription_tier enum
    op.execute("""
        CREATE TYPE subscriptiontier AS ENUM ('free', 'premium', 'pro');
    """)

    # Create subscription_status enum
    op.execute("""
        CREATE TYPE subscriptionstatus AS ENUM (
            'active', 'past_due', 'canceled', 'incomplete',
            'incomplete_expired', 'trialing', 'unpaid'
        );
    """)

    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('household_id', UUID(as_uuid=True), nullable=False),
        sa.Column('tier', sa.Enum('free', 'premium', 'pro', name='subscriptiontier'), nullable=False, server_default='free'),
        sa.Column('status', sa.Enum(
            'active', 'past_due', 'canceled', 'incomplete',
            'incomplete_expired', 'trialing', 'unpaid',
            name='subscriptionstatus'
        ), nullable=False, server_default='active'),
        sa.Column('stripe_customer_id', sa.String(255), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(255), nullable=True),
        sa.Column('stripe_price_id', sa.String(255), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.String(50), nullable=False, server_default='false'),
        sa.Column('canceled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('household_id', name='uq_subscription_household'),
        sa.UniqueConstraint('stripe_subscription_id', name='uq_subscription_stripe_id')
    )

    # Create indexes for subscriptions
    op.create_index('idx_subscriptions_household_id', 'subscriptions', ['household_id'])
    op.create_index('idx_subscriptions_stripe_customer_id', 'subscriptions', ['stripe_customer_id'])
    op.create_index('idx_subscriptions_stripe_subscription_id', 'subscriptions', ['stripe_subscription_id'])

    # Create webhook_events table
    op.create_table(
        'webhook_events',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('stripe_event_id', sa.String(255), nullable=False),
        sa.Column('event_type', sa.String(255), nullable=False),
        sa.Column('processed', sa.String(50), nullable=False, server_default='false'),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stripe_event_id', name='uq_webhook_stripe_event_id')
    )

    # Create indexes for webhook_events
    op.create_index('idx_webhook_events_stripe_event_id', 'webhook_events', ['stripe_event_id'])
    op.create_index('idx_webhook_events_event_type', 'webhook_events', ['event_type'])

    # Create trigger to update updated_at timestamp
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    op.execute("""
        CREATE TRIGGER update_subscriptions_updated_at
        BEFORE UPDATE ON subscriptions
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Initialize free tier subscription for all existing households
    op.execute("""
        INSERT INTO subscriptions (household_id, tier, status)
        SELECT id, 'free', 'active' FROM households
        ON CONFLICT (household_id) DO NOTHING;
    """)


def downgrade() -> None:
    """Drop subscriptions and webhook_events tables"""

    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_subscriptions_updated_at ON subscriptions;")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")

    # Drop tables
    op.drop_table('webhook_events')
    op.drop_table('subscriptions')

    # Drop enums
    op.execute("DROP TYPE IF EXISTS subscriptionstatus;")
    op.execute("DROP TYPE IF EXISTS subscriptiontier;")
