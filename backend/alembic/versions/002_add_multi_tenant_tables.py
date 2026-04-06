"""Add multi-tenant tables

Revision ID: 002
Revises: 001
Create Date: 2026-04-06

Adds:
- users table (authentication)
- households table (multi-tenancy)
- household_members table (user-household relationships)
- sharing_tokens table (household invitations)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add multi-tenant tables"""

    # Users table - authentication
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('apple_id', sa.String(length=255), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('apple_id'),
        sa.CheckConstraint(
            '(password_hash IS NOT NULL AND apple_id IS NULL) OR (password_hash IS NULL AND apple_id IS NOT NULL)',
            name='check_auth_method'
        )
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_apple_id', 'users', ['apple_id'], postgresql_where=sa.text('apple_id IS NOT NULL'))
    op.create_index('idx_users_created_at', 'users', ['created_at'])

    # Households table - budget groups
    op.create_table(
        'households',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_households_created_at', 'households', ['created_at'])

    # Household members table - user-household relationships
    op.create_table(
        'household_members',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('household_id', UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('household_id', 'user_id', name='uq_household_user')
    )
    op.create_index('idx_household_members_household', 'household_members', ['household_id'])
    op.create_index('idx_household_members_user', 'household_members', ['user_id'])

    # Sharing tokens table - household invitations
    op.create_table(
        'sharing_tokens',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('household_id', UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('created_by', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('used_by', UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('TRUE')),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['used_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
        sa.CheckConstraint('expires_at > created_at', name='check_token_not_expired')
    )
    op.create_index('idx_sharing_tokens_token', 'sharing_tokens', ['token'],
                    postgresql_where=sa.text('is_active = TRUE'))
    op.create_index('idx_sharing_tokens_household', 'sharing_tokens', ['household_id'])
    op.create_index('idx_sharing_tokens_expires', 'sharing_tokens', ['expires_at'],
                    postgresql_where=sa.text('is_active = TRUE'))


def downgrade() -> None:
    """Remove multi-tenant tables"""
    op.drop_table('sharing_tokens')
    op.drop_table('household_members')
    op.drop_table('households')
    op.drop_table('users')
