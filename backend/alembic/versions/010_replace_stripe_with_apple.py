"""Replace Stripe subscription schema with Apple StoreKit schema

Revision ID: 010
Revises: 009
Create Date: 2026-05-18

Drops the Stripe-shaped `subscriptions` and `webhook_events` tables and the
associated enums, then creates the Apple StoreKit 2 equivalents:

- `subscriptions` is now keyed on household_id (PK, FK CASCADE) with apple_*
  fields instead of stripe_*. Free tier rows are re-seeded for every existing
  household.
- `apple_notifications` replaces `webhook_events`, keyed on Apple's
  notificationUUID for idempotent processing of Server Notifications V2.

The Stripe drop uses IF EXISTS so this migration is safe whether or not 008
was applied in this environment.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop Stripe schema, create Apple schema."""

    # --- Drop the Stripe-era schema (IF EXISTS makes this idempotent) ---
    op.execute("DROP TRIGGER IF EXISTS update_subscriptions_updated_at ON subscriptions;")
    op.execute("DROP TABLE IF EXISTS webhook_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS subscriptions CASCADE;")
    op.execute("DROP TYPE IF EXISTS subscriptiontier;")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus;")
    # The update_updated_at_column() function may still be useful, leave it.

    # --- Apple-era enums ---
    subscription_tier = sa.Enum(
        'free', 'premium', 'pro',
        name='subscription_tier',
    )
    subscription_status = sa.Enum(
        'active', 'expired', 'in_billing_retry', 'in_grace_period',
        'revoked', 'refunded', 'inactive',
        name='subscription_status',
    )
    subscription_tier.create(op.get_bind(), checkfirst=True)
    subscription_status.create(op.get_bind(), checkfirst=True)

    # --- subscriptions table (per-household) ---
    op.create_table(
        'subscriptions',
        sa.Column('household_id', UUID(as_uuid=True), nullable=False),
        sa.Column('tier', subscription_tier, nullable=False, server_default='free'),
        sa.Column('status', subscription_status, nullable=False, server_default='inactive'),
        sa.Column('apple_original_transaction_id', sa.String(255), nullable=True),
        sa.Column('apple_product_id', sa.String(255), nullable=True),
        sa.Column('apple_environment', sa.String(20), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('auto_renew_status', sa.Boolean(), nullable=True),
        sa.Column('auto_renew_product_id', sa.String(255), nullable=True),
        sa.Column('revocation_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revocation_reason', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('household_id'),
        sa.UniqueConstraint('apple_original_transaction_id', name='uq_subscriptions_apple_original_tx'),
    )
    op.create_index(
        'idx_subscriptions_apple_original_tx',
        'subscriptions',
        ['apple_original_transaction_id'],
    )

    # --- apple_notifications table (Server Notifications V2 log) ---
    op.create_table(
        'apple_notifications',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('notification_uuid', sa.String(255), nullable=False),
        sa.Column('notification_type', sa.String(100), nullable=False),
        sa.Column('subtype', sa.String(100), nullable=True),
        sa.Column('apple_original_transaction_id', sa.String(255), nullable=True),
        sa.Column('bundle_id', sa.String(255), nullable=True),
        sa.Column('environment', sa.String(20), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('raw_payload', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('notification_uuid', name='uq_apple_notifications_uuid'),
    )
    op.create_index('idx_apple_notifications_type', 'apple_notifications', ['notification_type'])
    op.create_index('idx_apple_notifications_apple_tx', 'apple_notifications', ['apple_original_transaction_id'])

    # --- updated_at trigger on subscriptions (function created in 008 may persist) ---
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

    # --- Seed a free-tier row for every existing household ---
    op.execute("""
        INSERT INTO subscriptions (household_id, tier, status)
        SELECT id, 'free', 'inactive' FROM households
        ON CONFLICT (household_id) DO NOTHING;
    """)


def downgrade() -> None:
    """Drop Apple schema. (Stripe schema is NOT re-created — irreversible.)"""
    op.execute("DROP TRIGGER IF EXISTS update_subscriptions_updated_at ON subscriptions;")
    op.drop_table('apple_notifications')
    op.drop_table('subscriptions')
    op.execute("DROP TYPE IF EXISTS subscription_status;")
    op.execute("DROP TYPE IF EXISTS subscription_tier;")
