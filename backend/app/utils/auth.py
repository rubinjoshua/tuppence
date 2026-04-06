"""Authentication utilities - Argon2id password hashing and session validation"""

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session as DBSession


# Argon2id configuration (as per security spec)
# memory=65536 KiB (64 MB), time=3 iterations, parallelism=4 threads
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    encoding='utf-8',
    type=Type.ID  # Argon2id
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Argon2id hash string (safe to store in database)

    Example:
        >>> hash_password("my_password")
        '$argon2id$v=19$m=65536,t=3,p=4$...'
    """
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against an Argon2id hash.

    Args:
        password: Plain text password
        password_hash: Stored Argon2id hash

    Returns:
        True if password matches, False otherwise

    Example:
        >>> verify_password("my_password", hash_password("my_password"))
        True
        >>> verify_password("wrong_password", hash_password("my_password"))
        False
    """
    try:
        ph.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_session(db: DBSession, session_id: UUID) -> Optional[Tuple[UUID, UUID]]:
    """
    Validate session and return user/household context.

    Args:
        db: Database session
        session_id: Session UUID to validate

    Returns:
        Tuple of (user_id, household_id) if session is valid, None otherwise

    Side effects:
        - Updates session.last_activity (sliding window)
        - Extends session validity by updating timestamp
    """
    from app.models.session import Session

    # Look up session (handle both naive and aware datetimes for SQLite compatibility)
    session = db.query(Session).filter(Session.id == session_id).first()

    if not session:
        return None

    # Check expiration (handle both naive and timezone-aware datetimes)
    now = datetime.now(timezone.utc) if session.expires_at.tzinfo else datetime.now()
    if session.expires_at <= now:
        return None

    # Update last activity (sliding window - extends session life)
    session.last_activity = now
    db.commit()

    return (session.user_id, session.household_id)
