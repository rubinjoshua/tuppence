"""Add sort_order column to budgets

Revision ID: 011
Revises: 010
Create Date: 2026-05-26

Allows household members to control the display order of budgets across the
app (Amount page, Analysis pie chart, Add Expense picker, shortcuts, etc.).
Order is per-household — all members of a household share the same order.

Backfill: existing rows get sort_order assigned in (created_at, id) order so
the visible order doesn't change for current users.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '011'
down_revision: Union[str, None] = '010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'budgets',
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
    )

    # Backfill: assign sort_order per-household based on existing creation order.
    op.execute("""
        UPDATE budgets b
        SET sort_order = sub.rn - 1
        FROM (
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY household_id
                ORDER BY created_at ASC, id ASC
            ) AS rn
            FROM budgets
        ) sub
        WHERE b.id = sub.id;
    """)


def downgrade() -> None:
    op.drop_column('budgets', 'sort_order')
