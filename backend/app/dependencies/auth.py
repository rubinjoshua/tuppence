"""Authentication dependencies for protected endpoints - Session-based auth"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Tuple
import uuid

from app.database import get_db
from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.utils.auth import validate_session


# HTTP Bearer token scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from session token.

    Usage:
        @router.get("/protected")
        def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}

    Raises:
        HTTPException 401: Invalid/expired session or inactive user
    """
    token = credentials.credentials

    # Parse session UUID
    try:
        session_id = uuid.UUID(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate session
    result = validate_session(db, session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id, _ = result

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


async def get_current_user_and_household(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Tuple[User, Household]:
    """
    Dependency to get current user and their active household from session token.

    Usage:
        @router.get("/protected")
        def protected_route(
            user_household: Tuple[User, Household] = Depends(get_current_user_and_household)
        ):
            user, household = user_household
            return {"user_id": user.id, "household_id": household.id}

    Raises:
        HTTPException 401: Invalid/expired session or inactive user
        HTTPException 403: User not in household
    """
    token = credentials.credentials

    # Parse session UUID
    try:
        session_id = uuid.UUID(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate session
    result = validate_session(db, session_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id, household_id = result

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get household from session
    household = db.query(Household).filter(Household.id == household_id).first()

    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found",
        )

    # Verify user is member of household
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.user_id == user.id,
        HouseholdMember.household_id == household.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this household",
        )

    return user, household
