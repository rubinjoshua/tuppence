"""Remove refresh_tokens table (replaced by sessions)

Revision ID: 007
Revises: 006
Create Date: 2026-04-06

Removes the refresh_tokens table which was used for JWT refresh token
storage. This table is no longer needed with session-based authentication.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop refresh_tokens table"""
    # Drop table if it exists
    op.execute("""
        DROP TABLE IF EXISTS refresh_tokens CASCADE;
    """)


def downgrade() -> None:
    """Recreate refresh_tokens table"""
    # Recreate the table for rollback (in case needed)
    op.create_table(
        'refresh_tokens',
        sa.Column('id', UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('token', sa.String(500), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_refresh_tokens_token', 'refresh_tokens', ['token'], unique=True)
    op.create_index('idx_refresh_tokens_user_id', 'refresh_tokens', ['user_id'])
    op.create_index('idx_refresh_tokens_user_active', 'refresh_tokens', ['user_id', 'is_revoked', 'expires_at'])
