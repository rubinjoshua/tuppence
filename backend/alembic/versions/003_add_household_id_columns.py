"""Add household_id to existing tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-06

Adds household_id columns to:
- ledger
- budgets
- settings
- text_category_cache

Columns are nullable initially to allow data migration.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add household_id columns (nullable)"""

    # Add household_id to ledger
    op.add_column('ledger', sa.Column('household_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_ledger_household', 'ledger', 'households', ['household_id'], ['id'], ondelete='CASCADE')
    op.create_index('idx_ledger_household', 'ledger', ['household_id'])

    # Add household_id to budgets
    op.add_column('budgets', sa.Column('household_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_budgets_household', 'budgets', 'households', ['household_id'], ['id'], ondelete='CASCADE')
    op.create_index('idx_budgets_household', 'budgets', ['household_id'])

    # Add household_id to settings
    op.add_column('settings', sa.Column('household_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_settings_household', 'settings', 'households', ['household_id'], ['id'], ondelete='CASCADE')

    # Add household_id to text_category_cache
    op.add_column('text_category_cache', sa.Column('household_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_text_category_cache_household', 'text_category_cache', 'households',
                         ['household_id'], ['id'], ondelete='CASCADE')
    op.create_index('idx_text_category_cache_household', 'text_category_cache', ['household_id'])


def downgrade() -> None:
    """Remove household_id columns"""
    op.drop_index('idx_text_category_cache_household', 'text_category_cache')
    op.drop_constraint('fk_text_category_cache_household', 'text_category_cache', type_='foreignkey')
    op.drop_column('text_category_cache', 'household_id')

    op.drop_constraint('fk_settings_household', 'settings', type_='foreignkey')
    op.drop_column('settings', 'household_id')

    op.drop_index('idx_budgets_household', 'budgets')
    op.drop_constraint('fk_budgets_household', 'budgets', type_='foreignkey')
    op.drop_column('budgets', 'household_id')

    op.drop_index('idx_ledger_household', 'ledger')
    op.drop_constraint('fk_ledger_household', 'ledger', type_='foreignkey')
    op.drop_column('ledger', 'household_id')
