"""Migrate existing data to default household

Revision ID: 004
Revises: 003
Create Date: 2026-04-06

Creates a default "Legacy Household" and assigns all existing data to it.
This allows existing users to continue using the app without disruption.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create default household and migrate existing data"""

    # Create default household
    # Note: We use a fixed UUID for the default household to make rollback easier
    default_household_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'

    op.execute(f"""
        INSERT INTO households (id, name, created_at, updated_at)
        VALUES ('{default_household_id}', 'My Household', NOW(), NOW())
        ON CONFLICT (id) DO NOTHING
    """)

    # Migrate ledger entries to default household
    op.execute(f"""
        UPDATE ledger
        SET household_id = '{default_household_id}'
        WHERE household_id IS NULL
    """)

    # Migrate budgets to default household
    op.execute(f"""
        UPDATE budgets
        SET household_id = '{default_household_id}'
        WHERE household_id IS NULL
    """)

    # Migrate settings to default household
    op.execute(f"""
        UPDATE settings
        SET household_id = '{default_household_id}'
        WHERE household_id IS NULL
    """)

    # Migrate text_category_cache to default household
    op.execute(f"""
        UPDATE text_category_cache
        SET household_id = '{default_household_id}'
        WHERE household_id IS NULL
    """)

    # Note: We don't create a default user or household_member entry here.
    # This will be done when the first user signs up or logs in.
    # The app will detect the legacy household and allow claiming it.


def downgrade() -> None:
    """Clear household_id from all data"""

    # Clear household_id from text_category_cache
    op.execute("""
        UPDATE text_category_cache
        SET household_id = NULL
    """)

    # Clear household_id from settings
    op.execute("""
        UPDATE settings
        SET household_id = NULL
    """)

    # Clear household_id from budgets
    op.execute("""
        UPDATE budgets
        SET household_id = NULL
    """)

    # Clear household_id from ledger
    op.execute("""
        UPDATE ledger
        SET household_id = NULL
    """)

    # Delete default household
    default_household_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    op.execute(f"""
        DELETE FROM households WHERE id = '{default_household_id}'
    """)
