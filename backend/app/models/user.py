"""User model - authentication and user accounts"""

from sqlalchemy import Column, String, Boolean, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.database import Base


class User(Base):
    """
    User table for authentication.

    Supports two authentication methods:
    - Email/password (password_hash is set, apple_id is NULL)
    - Apple Sign In (apple_id is set, password_hash is NULL)

    Schema:
        - id: Primary key (UUID)
        - email: User email (unique, required)
        - password_hash: Argon2id hash (nullable for Apple users)
        - apple_id: Apple Sign In identifier (nullable for email/password users)
        - full_name: User's full name (nullable)
        - created_at: Account creation timestamp
        - updated_at: Last update timestamp
        - last_login: Last successful login timestamp
        - is_active: Account status (soft delete support)
    """

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    apple_id = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Constraint: Must use either email/password OR Apple Sign In
    __table_args__ = (
        CheckConstraint(
            '(password_hash IS NOT NULL AND apple_id IS NULL) OR (password_hash IS NULL AND apple_id IS NOT NULL)',
            name='check_auth_method'
        ),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
