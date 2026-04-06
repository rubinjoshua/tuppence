"""Enforce household constraints and enable RLS

Revision ID: 005
Revises: 004
Create Date: 2026-04-06

Makes household_id NOT NULL and enables Row-Level Security policies.
Also updates indexes and drops old user_id columns.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enforce constraints and enable RLS"""

    # Make household_id NOT NULL on all tables
    op.alter_column('ledger', 'household_id', nullable=False)
    op.alter_column('budgets', 'household_id', nullable=False)
    op.alter_column('settings', 'household_id', nullable=False)
    op.alter_column('text_category_cache', 'household_id', nullable=False)

    # Drop old user_id columns (no longer needed with household model)
    op.drop_index('idx_ledger_user_id', 'ledger')
    op.drop_column('ledger', 'user_id')

    op.drop_index('idx_budgets_user_id', 'budgets')
    op.drop_column('budgets', 'user_id')

    # Update budgets unique constraint (emoji must be unique per household, not globally)
    op.drop_constraint('budgets_emoji_key', 'budgets', type_='unique')
    op.create_unique_constraint('uq_budgets_household_emoji', 'budgets', ['household_id', 'emoji'])

    # Add composite indexes for household-scoped queries
    op.create_index('idx_ledger_household_year', 'ledger', ['household_id', 'year'])
    op.create_index('idx_ledger_household_budget_year', 'ledger', ['household_id', 'budget_emoji', 'year'])

    # Update settings table to use household_id as primary key
    # (Each household has exactly one settings row)
    op.drop_constraint('settings_pkey', 'settings', type_='primary')
    op.create_primary_key('settings_pkey', 'settings', ['household_id'])
    op.drop_column('settings', 'id')

    # Note: Row-Level Security (RLS) not enabled for MVP
    # Using middleware-based household filtering instead
    # RLS can be added in Phase 2 as defense-in-depth


def downgrade() -> None:
    """Revert constraints"""

    # Note: No RLS policies to drop (not using RLS for MVP)

    # Revert settings primary key
    op.add_column('settings', sa.Column('id', sa.Integer(), nullable=False))
    op.drop_constraint('settings_pkey', 'settings', type_='primary')
    op.create_primary_key('settings_pkey', 'settings', ['id'])

    # Drop composite indexes
    op.drop_index('idx_ledger_household_budget_year', 'ledger')
    op.drop_index('idx_ledger_household_year', 'ledger')

    # Restore budgets unique constraint
    op.drop_constraint('uq_budgets_household_emoji', 'budgets', type_='unique')
    op.create_unique_constraint('budgets_emoji_key', 'budgets', ['emoji'])

    # Re-add user_id columns
    op.add_column('budgets', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('idx_budgets_user_id', 'budgets', ['user_id'])

    op.add_column('ledger', sa.Column('user_id', sa.Integer(), nullable=True))
    op.create_index('idx_ledger_user_id', 'ledger', ['user_id'])

    # Make household_id nullable again
    op.alter_column('text_category_cache', 'household_id', nullable=True)
    op.alter_column('settings', 'household_id', nullable=True)
    op.alter_column('budgets', 'household_id', nullable=True)
    op.alter_column('ledger', 'household_id', nullable=True)
