"""Drop household_id from text_category_cache (keep cache global)

Revision ID: 009
Revises: 008
Create Date: 2026-05-17

The text->category mapping is a pure lookup table (e.g., "starbucks latte" ->
"Coffee & Cafe") containing no PII. Scoping it per-household lowers the cache
hit rate and multiplies OpenAI costs with no privacy benefit, so we drop the
column entirely.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop household_id from text_category_cache."""
    op.drop_index('idx_text_category_cache_household', table_name='text_category_cache')
    op.drop_constraint('fk_text_category_cache_household', 'text_category_cache', type_='foreignkey')
    op.drop_column('text_category_cache', 'household_id')


def downgrade() -> None:
    """Re-add household_id (nullable) to text_category_cache."""
    op.add_column(
        'text_category_cache',
        sa.Column('household_id', UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_text_category_cache_household',
        'text_category_cache',
        'households',
        ['household_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index(
        'idx_text_category_cache_household',
        'text_category_cache',
        ['household_id'],
    )
