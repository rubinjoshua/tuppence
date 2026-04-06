"""Sharing token model - household invitation tokens"""

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Index, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.database import Base


class SharingToken(Base):
    """
    Sharing token table for household invitations.

    Stores one-time tokens for inviting users to join households.

    Schema:
        - id: Primary key (UUID)
        - household_id: Foreign key to households
        - token: Cryptographically secure random token (64 chars)
        - created_by: Foreign key to users (creator)
        - created_at: Token creation timestamp
        - expires_at: Token expiration timestamp (7 days default)
        - used_at: Token usage timestamp (NULL if unused)
        - used_by: Foreign key to users (who used token, NULL if unused)
        - is_active: Token status (can be manually deactivated)

    Security:
        - Tokens are 32-byte (256-bit) cryptographically secure random strings
        - Tokens are one-time use (used_at set after use)
        - Tokens expire after 7 days
        - Tokens can be manually revoked (is_active=False)
    """

    __tablename__ = "sharing_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey('households.id', ondelete='CASCADE'), nullable=False, index=True)
    token = Column(String(64), unique=True, nullable=False, index=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    used_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint('expires_at > created_at', name='check_token_not_expired'),
        Index('idx_sharing_tokens_token_active', 'token', 'is_active', postgresql_where="is_active = TRUE"),
        Index('idx_sharing_tokens_expires_active', 'expires_at', 'is_active', postgresql_where="is_active = TRUE"),
    )

    def __repr__(self):
        return f"<SharingToken(id={self.id}, household_id={self.household_id}, used={self.used_at is not None})>"
