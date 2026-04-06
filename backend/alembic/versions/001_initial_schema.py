"""Initial schema - current state before multi-tenancy

Revision ID: 001
Revises:
Create Date: 2026-04-06

This migration captures the current single-tenant database schema.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema (current state)"""

    # Categories table (global, shared across all households)
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('category_name', sa.String(length=100), nullable=False),
        sa.Column('hex_color', sa.String(length=7), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category_name')
    )
    op.create_index('idx_categories_name', 'categories', ['category_name'])

    # Budgets table (will become household-scoped)
    op.create_table(
        'budgets',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('emoji', sa.String(length=10), nullable=False),
        sa.Column('monthly_amount', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),  # Will be replaced with household_id
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('emoji')
    )
    op.create_index('idx_budgets_emoji', 'budgets', ['emoji'])
    op.create_index('idx_budgets_user_id', 'budgets', ['user_id'])

    # Ledger table (will become household-scoped)
    op.create_table(
        'ledger',
        sa.Column('uuid', UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('budget_emoji', sa.String(length=10), nullable=False),
        sa.Column('datetime', sa.DateTime(timezone=True), nullable=False),
        sa.Column('description_text', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),  # Will be replaced with household_id
        sa.PrimaryKeyConstraint('uuid')
    )
    op.create_index('idx_ledger_uuid', 'ledger', ['uuid'])
    op.create_index('idx_ledger_budget_emoji', 'ledger', ['budget_emoji'])
    op.create_index('idx_ledger_datetime', 'ledger', ['datetime'])
    op.create_index('idx_ledger_year', 'ledger', ['year'])
    op.create_index('idx_ledger_user_id', 'ledger', ['user_id'])
    op.create_index('idx_ledger_budget_year', 'ledger', ['budget_emoji', 'year'])
    op.create_index('idx_ledger_year_datetime', 'ledger', ['year', 'datetime'])

    # Settings table (will become household-scoped)
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('currency_symbol', sa.String(length=10), nullable=False, server_default='$'),
        sa.PrimaryKeyConstraint('id')
    )

    # Text category cache (will become household-scoped)
    op.create_table(
        'text_category_cache',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('description_text', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_text_category_cache_text', 'text_category_cache', ['description_text'])


def downgrade() -> None:
    """Drop all tables"""
    op.drop_table('text_category_cache')
    op.drop_table('settings')
    op.drop_table('ledger')
    op.drop_table('budgets')
    op.drop_table('categories')
