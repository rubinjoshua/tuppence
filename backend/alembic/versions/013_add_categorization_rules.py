"""Add categorization_rules column to settings

Revision ID: 013
Revises: 012
Create Date: 2026-08-07

Adds a per-household, free-text field holding the categorization rules injected
into the AI categorization prompt. Editable from the app's Settings screen and
shared across all household members (like the other settings). NULL means the
household hasn't overridden the built-in DEFAULT_CATEGORIZATION_RULES, so no
backfill is needed — existing households keep the previous default behaviour.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '013'
down_revision: Union[str, None] = '012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'settings',
        sa.Column('categorization_rules', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('settings', 'categorization_rules')
