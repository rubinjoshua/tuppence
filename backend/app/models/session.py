"""Session model - UUID-based session authentication"""

from sqlalchemy import Column, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.database import Base


class Session(Base):
    """
    Session table for UUID-based authentication.

    Simple session model - no JWT, no signing, just UUID lookup.
    Each session represents an authenticated user in a specific household.

    Schema:
        - id: UUID primary key (the session token sent to client)
        - user_id: Foreign key to users
        - household_id: Foreign key to households (user's active household)
        - created_at: Session creation timestamp
        - expires_at: Absolute expiration (30 days from creation)
        - last_activity: Last request timestamp (for sliding window)

    Revocation:
        - DELETE FROM sessions WHERE user_id=X AND household_id=Y
        - Immediate revocation, zero vulnerability window

    Sliding Window:
        - Session expires 30 days after last_activity
        - Each request updates last_activity
        - Keeps active users logged in indefinitely
    """

    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    household_id = Column(UUID(as_uuid=True), ForeignKey('households.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_activity = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('idx_sessions_user_household', 'user_id', 'household_id'),
    )

    def __repr__(self):
        return f"<Session(id={self.id}, user_id={self.user_id}, household_id={self.household_id})>"
