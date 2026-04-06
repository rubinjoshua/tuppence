"""Authentication endpoints - Session-based (UUID tokens, not JWT)"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session as DBSession
from slowapi import Limiter
from slowapi.util import get_remote_address
from datetime import datetime, timedelta, timezone
import uuid

from app.database import get_db
from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.models.session import Session
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    AppleSignInRequest,
    AuthResponse,
    LogoutResponse,
)
from app.utils.auth import hash_password, verify_password
from app.utils.apple_auth import extract_apple_user_info

router = APIRouter(prefix="/auth", tags=["authentication"])

# Rate limiter: 5 requests per minute for login/register
limiter = Limiter(key_func=get_remote_address)


def create_session(db: DBSession, user_id: uuid.UUID, household_id: uuid.UUID) -> Session:
    """
    Create a new session for user in household.

    Returns session object with UUID that will be sent to client as bearer token.
    """
    session = Session(
        user_id=user_id,
        household_id=household_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(session)
    db.flush()  # Get session.id
    return session


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    data: RegisterRequest,
    db: DBSession = Depends(get_db)
):
    """
    Register a new user with email/password.

    If household_token provided:
    - Validates token and joins existing household as member

    If no household_token:
    - Creates default household (named "My Household")
    - Makes user the owner

    Always creates:
    - User account (with Argon2id hashed password)
    - Household membership
    - Session (UUID token)

    Returns session_token (UUID) to be used as bearer token.
    Rate limit: 5 requests/minute
    """
    from app.models.sharing_token import SharingToken

    # Check if email already exists
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Hash password with Argon2id
    password_hash = hash_password(data.password)

    # Create user
    user = User(
        email=data.email,
        password_hash=password_hash,
        full_name=data.full_name,
        last_login=datetime.now(timezone.utc)
    )
    db.add(user)
    db.flush()  # Get user.id

    # Handle household creation or joining
    if data.household_token:
        # Validate sharing token
        sharing_token = db.query(SharingToken).filter(
            SharingToken.token == data.household_token,
            SharingToken.is_active == True
        ).first()

        if not sharing_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or inactive sharing token"
            )

        # Check if token is expired (handle both naive and aware datetimes)
        now = datetime.now(timezone.utc) if sharing_token.expires_at.tzinfo else datetime.now()
        if sharing_token.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sharing token has expired"
            )

        # Check if token has been used
        if sharing_token.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sharing token has already been used"
            )

        # Use existing household
        household = db.query(Household).filter(Household.id == sharing_token.household_id).first()

        # Add user as member (not owner)
        membership = HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role="member"
        )
        db.add(membership)

        # Mark token as used
        sharing_token.used_at = datetime.now(timezone.utc)
        sharing_token.used_by = user.id
    else:
        # Create default household
        household = Household(name="My Household")
        db.add(household)
        db.flush()  # Get household.id

        # Add user as household owner
        membership = HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role="owner"
        )
        db.add(membership)

    # Create session
    session = create_session(db, user.id, household.id)

    db.commit()
    db.refresh(user)
    db.refresh(household)
    db.refresh(session)

    return AuthResponse(
        sessionToken=str(session.id),
        userId=str(user.id),
        householdId=str(household.id),
        email=user.email,
        householdName=household.name
    )


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    db: DBSession = Depends(get_db)
):
    """
    Login with email/password.

    Returns:
    - User info
    - Default household
    - Session token (UUID)

    Rate limit: 5 requests/minute
    """
    # Find user by email
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Verify password
    if not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )

    # Get user's default household (first household they're a member of)
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.user_id == user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User has no household (data corruption)"
        )

    household = db.query(Household).filter(Household.id == membership.household_id).first()

    # Update last login
    user.last_login = datetime.now(timezone.utc)

    # Create session
    session = create_session(db, user.id, household.id)

    db.commit()
    db.refresh(session)

    return AuthResponse(
        sessionToken=str(session.id),
        userId=str(user.id),
        householdId=str(household.id),
        email=user.email,
        householdName=household.name
    )


@router.post("/apple-signin", response_model=AuthResponse, status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def apple_signin(
    request: Request,
    data: AppleSignInRequest,
    db: DBSession = Depends(get_db)
):
    """
    Sign in or register with Apple Sign In.

    Verifies Apple identity token and either:
    - Creates new user account with Apple ID
    - Signs in existing user with Apple ID

    If household_token provided:
    - Validates token and joins existing household as member

    If no household_token (new user):
    - Creates default household (named "My Household")
    - Makes user the owner

    Returns session_token (UUID) to be used as bearer token.
    Rate limit: 5 requests/minute
    """
    from app.models.sharing_token import SharingToken

    # Verify Apple identity token and extract user info
    try:
        user_info = extract_apple_user_info(data.identity_token, data.full_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to verify Apple identity token: {str(e)}"
        )

    apple_id = user_info["apple_id"]
    email = user_info["email"]
    full_name = user_info.get("full_name")

    # Check if user already exists with this Apple ID
    existing_user = db.query(User).filter(User.apple_id == apple_id).first()

    if existing_user:
        # Existing user - sign in
        user = existing_user

        # Update last login
        user.last_login = datetime.now(timezone.utc)

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )

        # Get user's default household (first household they're a member of)
        membership = db.query(HouseholdMember).filter(
            HouseholdMember.user_id == user.id
        ).first()

        if not membership:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User has no household (data corruption)"
            )

        household = db.query(Household).filter(Household.id == membership.household_id).first()

        # Create session
        session = create_session(db, user.id, household.id)
        db.commit()
        db.refresh(session)

        return AuthResponse(
            sessionToken=str(session.id),
            userId=str(user.id),
            householdId=str(household.id),
            email=user.email,
            householdName=household.name
        )

    else:
        # New user - register
        # Email might be privatized (e.g., abc@privaterelay.appleid.com)
        # Check if email already exists (edge case: user previously registered with email/password)
        if email:
            email_user = db.query(User).filter(User.email == email).first()
            if email_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered with different authentication method"
                )

        # Create new user with Apple ID
        user = User(
            email=email or f"{apple_id}@appleid.private",  # Fallback if no email
            apple_id=apple_id,
            full_name=full_name,
            last_login=datetime.now(timezone.utc)
        )
        db.add(user)
        db.flush()  # Get user.id

        # Handle household creation or joining
        if data.household_token:
            # Validate sharing token
            sharing_token = db.query(SharingToken).filter(
                SharingToken.token == data.household_token,
                SharingToken.is_active == True
            ).first()

            if not sharing_token:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or inactive sharing token"
                )

            # Check if token is expired
            now = datetime.now(timezone.utc) if sharing_token.expires_at.tzinfo else datetime.now()
            if sharing_token.expires_at < now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sharing token has expired"
                )

            # Check if token has been used
            if sharing_token.used_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sharing token has already been used"
                )

            # Use existing household
            household = db.query(Household).filter(Household.id == sharing_token.household_id).first()

            # Add user as member (not owner)
            membership = HouseholdMember(
                household_id=household.id,
                user_id=user.id,
                role="member"
            )
            db.add(membership)

            # Mark token as used
            sharing_token.used_at = datetime.now(timezone.utc)
            sharing_token.used_by = user.id
        else:
            # Create default household
            household = Household(name="My Household")
            db.add(household)
            db.flush()  # Get household.id

            # Add user as household owner
            membership = HouseholdMember(
                household_id=household.id,
                user_id=user.id,
                role="owner"
            )
            db.add(membership)

        # Create session
        session = create_session(db, user.id, household.id)

        db.commit()
        db.refresh(user)
        db.refresh(household)
        db.refresh(session)

        return AuthResponse(
            sessionToken=str(session.id),
            userId=str(user.id),
            householdId=str(household.id),
            email=user.email,
            householdName=household.name
        )


def get_authorization_header(request: Request) -> str:
    """Dependency to extract authorization header"""
    return request.headers.get("Authorization", "")


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    authorization: str = Depends(get_authorization_header),
    db: DBSession = Depends(get_db)
):
    """
    Logout user by deleting their session.

    This provides immediate revocation - once the session is deleted,
    the next API call with that session token will fail with 401.

    Zero vulnerability window.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization header"
        )

    # Extract session ID (UUID)
    session_token = authorization[7:]  # Remove "Bearer "

    try:
        session_id = uuid.UUID(session_token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session token format"
        )

    # Delete session (immediate revocation)
    result = db.query(Session).filter(Session.id == session_id).delete()
    db.commit()

    if result == 0:
        # Session already deleted or doesn't exist - still return success
        pass

    return LogoutResponse(message="Successfully logged out")
