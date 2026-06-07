"""Add split_budget_options column to settings

Revision ID: 012
Revises: 011
Create Date: 2026-06-07

Adds a per-household configurable list of "split-budget options". Each option
is a string of concatenated budget emojis (e.g. "🛒🦊"); when picked at expense
time the amount is divided evenly across the listed budgets and one ledger
entry is created per budget. Stored as JSON-encoded text for SQLite/Postgres
parity (same approach used elsewhere in the codebase).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '012'
down_revision: Union[str, None] = '011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'settings',
        sa.Column('split_budget_options', sa.Text(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('settings', 'split_budget_options')
