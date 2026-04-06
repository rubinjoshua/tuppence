"""Authentication endpoint tests - Session-based auth with UUID tokens"""

import pytest
from datetime import datetime, timedelta, timezone
import uuid

from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.models.session import Session
from app.models.sharing_token import SharingToken
from app.utils.auth import hash_password


def test_register_creates_user_and_household(client, db):
    """Test basic registration creates user and household"""
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePass123",
        "full_name": "Test User"
    })

    assert response.status_code == 201
    data = response.json()

    # Check response structure
    assert "sessionToken" in data
    assert "userId" in data
    assert "householdId" in data
    assert data["email"] == "test@example.com"
    assert data["householdName"] == "My Household"

    # Verify session token is valid UUID
    session_uuid = uuid.UUID(data["sessionToken"])
    assert session_uuid is not None

    # Verify user exists in database
    user = db.query(User).filter(User.email == "test@example.com").first()
    assert user is not None
    assert user.full_name == "Test User"

    # Verify household exists
    household_id_uuid = uuid.UUID(data["householdId"])
    household = db.query(Household).filter(Household.id == household_id_uuid).first()
    assert household is not None
    assert household.name == "My Household"

    # Verify membership exists with owner role
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.user_id == user.id,
        HouseholdMember.household_id == household_id_uuid
    ).first()
    assert membership is not None
    assert membership.role == "owner"

    # Verify session exists
    session = db.query(Session).filter(Session.id == session_uuid).first()
    assert session is not None
    assert session.user_id == user.id
    assert session.household_id == household.id


def test_register_with_household_token(client, db):
    """Test registration with household sharing token joins existing household"""
    # Create existing household and owner
    owner = User(
        email="owner@example.com",
        password_hash=hash_password("OwnerPass123"),
        full_name="Owner"
    )
    db.add(owner)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=owner.id,
        role="owner"
    )
    db.add(membership)

    # Create sharing token (use naive datetime for SQLite)
    sharing_token = SharingToken(
        household_id=household.id,
        token="test_token_123",
        created_by=owner.id,
        expires_at=datetime.now() + timedelta(days=7)
    )
    db.add(sharing_token)
    db.commit()

    # Register new user with token
    response = client.post("/auth/register", json={
        "email": "newuser@example.com",
        "password": "SecurePass123",
        "household_token": "test_token_123"
    })

    assert response.status_code == 201
    data = response.json()

    # Should join existing household
    assert data["householdId"] == str(household.id)
    assert data["householdName"] == "Test Household"

    # Verify new user is member (not owner)
    new_user = db.query(User).filter(User.email == "newuser@example.com").first()
    new_membership = db.query(HouseholdMember).filter(
        HouseholdMember.user_id == new_user.id,
        HouseholdMember.household_id == household.id
    ).first()
    assert new_membership is not None
    assert new_membership.role == "member"

    # Verify token is marked as used
    db.refresh(sharing_token)
    assert sharing_token.used_at is not None
    assert sharing_token.used_by == new_user.id


def test_register_with_expired_token(client, db):
    """Test registration with expired token fails"""
    # Create household and expired token
    owner = User(
        email="owner@example.com",
        password_hash=hash_password("OwnerPass123")
    )
    db.add(owner)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=owner.id,
        role="owner"
    )
    db.add(membership)

    # Create EXPIRED token (use naive datetime for SQLite)
    # Set created_at before expires_at to satisfy CHECK constraint
    expired_token = SharingToken(
        household_id=household.id,
        token="expired_token",
        created_by=owner.id,
        created_at=datetime.now() - timedelta(days=8),  # Created 8 days ago
        expires_at=datetime.now() - timedelta(days=1)  # Expired yesterday
    )
    db.add(expired_token)
    db.commit()

    # Try to register with expired token
    response = client.post("/auth/register", json={
        "email": "newuser@example.com",
        "password": "SecurePass123",
        "household_token": "expired_token"
    })

    assert response.status_code == 400
    assert "expired" in response.json()["detail"].lower()


def test_register_with_used_token(client, db):
    """Test registration with already-used token fails"""
    # Create household and used token
    owner = User(
        email="owner@example.com",
        password_hash=hash_password("OwnerPass123")
    )
    db.add(owner)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=owner.id,
        role="owner"
    )
    db.add(membership)

    # Create token that's already been used (use naive datetime for SQLite)
    used_token = SharingToken(
        household_id=household.id,
        token="used_token",
        created_by=owner.id,
        expires_at=datetime.now() + timedelta(days=7),
        used_at=datetime.now(),  # Already used
        used_by=owner.id
    )
    db.add(used_token)
    db.commit()

    # Try to register with used token
    response = client.post("/auth/register", json={
        "email": "newuser@example.com",
        "password": "SecurePass123",
        "household_token": "used_token"
    })

    assert response.status_code == 400
    assert "already been used" in response.json()["detail"]


def test_register_duplicate_email(client, db):
    """Test registration with existing email fails"""
    # Create existing user
    existing_user = User(
        email="existing@example.com",
        password_hash=hash_password("Pass123")
    )
    db.add(existing_user)
    db.commit()

    # Try to register with same email
    response = client.post("/auth/register", json={
        "email": "existing@example.com",
        "password": "SecurePass123"
    })

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()


def test_register_weak_password(client, db):
    """Test registration with weak password fails"""
    # Missing uppercase
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "weakpass123"
    })
    assert response.status_code == 422

    # Missing lowercase
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "WEAKPASS123"
    })
    assert response.status_code == 422

    # Missing digit
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "WeakPass"
    })
    assert response.status_code == 422

    # Too short
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "Weak1"
    })
    assert response.status_code == 422


def test_login_success(client, db):
    """Test successful login returns session token"""
    # Create user
    user = User(
        email="test@example.com",
        password_hash=hash_password("SecurePass123"),
        full_name="Test User"
    )
    db.add(user)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)
    db.commit()

    # Login
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123"
    })

    assert response.status_code == 200
    data = response.json()

    assert "sessionToken" in data
    assert data["email"] == "test@example.com"
    assert data["householdId"] == str(household.id)

    # Verify session exists
    session_uuid = uuid.UUID(data["sessionToken"])
    session = db.query(Session).filter(Session.id == session_uuid).first()
    assert session is not None
    assert session.user_id == user.id


def test_login_wrong_password(client, db):
    """Test login with wrong password fails"""
    # Create user
    user = User(
        email="test@example.com",
        password_hash=hash_password("CorrectPass123")
    )
    db.add(user)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)
    db.commit()

    # Try wrong password
    response = client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPass123"
    })

    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_nonexistent_user(client, db):
    """Test login with non-existent email fails"""
    response = client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "SecurePass123"
    })

    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]


def test_login_inactive_user(client, db):
    """Test login with inactive user fails"""
    # Create inactive user
    user = User(
        email="inactive@example.com",
        password_hash=hash_password("SecurePass123"),
        is_active=False
    )
    db.add(user)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)
    db.commit()

    # Try to login
    response = client.post("/auth/login", json={
        "email": "inactive@example.com",
        "password": "SecurePass123"
    })

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


def test_logout_success(client, db):
    """Test logout deletes session"""
    # Create user and session
    user = User(
        email="test@example.com",
        password_hash=hash_password("SecurePass123")
    )
    db.add(user)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)

    # Use naive datetime for SQLite
    session = Session(
        user_id=user.id,
        household_id=household.id,
        expires_at=datetime.now() + timedelta(days=30)
    )
    db.add(session)
    db.commit()

    session_token = str(session.id)

    # Logout
    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {session_token}"}
    )

    assert response.status_code == 200
    assert "logged out" in response.json()["message"].lower()

    # Verify session is deleted
    db.expire_all()
    deleted_session = db.query(Session).filter(Session.id == session.id).first()
    assert deleted_session is None


def test_logout_invalid_token(client, db):
    """Test logout with invalid token format fails"""
    response = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer not-a-uuid"}
    )

    assert response.status_code == 401
    assert "Invalid session token" in response.json()["detail"]


def test_logout_missing_authorization(client, db):
    """Test logout without authorization header fails"""
    response = client.post("/auth/logout")

    assert response.status_code == 401
    assert "authorization" in response.json()["detail"].lower()


def test_logout_nonexistent_session(client, db):
    """Test logout with non-existent session succeeds (idempotent)"""
    fake_uuid = str(uuid.uuid4())

    response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {fake_uuid}"}
    )

    # Should still succeed (idempotent logout)
    assert response.status_code == 200


def test_session_sliding_window(client, db):
    """Test that session last_activity updates extend session life"""
    from app.utils.auth import validate_session

    # Create session
    user = User(
        email="test@example.com",
        password_hash=hash_password("Pass123")
    )
    db.add(user)
    db.flush()

    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)

    # Use naive datetime for SQLite
    initial_time = datetime.now()
    session = Session(
        user_id=user.id,
        household_id=household.id,
        expires_at=initial_time + timedelta(days=30),
        last_activity=initial_time
    )
    db.add(session)
    db.commit()

    # Validate session (should update last_activity)
    result = validate_session(db, session.id)
    assert result is not None
    assert result == (user.id, household.id)

    # Check that last_activity was updated
    db.refresh(session)
    assert session.last_activity > initial_time


def test_password_hashing_security(client, db):
    """Test that passwords are hashed with Argon2id"""
    from app.utils.auth import verify_password

    # Register user
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePass123"
    })

    assert response.status_code == 201

    # Verify password is hashed in database
    user = db.query(User).filter(User.email == "test@example.com").first()
    assert user.password_hash is not None
    assert user.password_hash != "SecurePass123"
    assert user.password_hash.startswith("$argon2id$")

    # Verify password can be verified
    assert verify_password("SecurePass123", user.password_hash)
    assert not verify_password("WrongPass", user.password_hash)


def test_full_auth_workflow(client, db):
    """Test complete authentication workflow: register -> login -> logout"""
    # 1. Register
    register_response = client.post("/auth/register", json={
        "email": "workflow@example.com",
        "password": "SecurePass123",
        "full_name": "Workflow User"
    })
    assert register_response.status_code == 201
    first_token = register_response.json()["sessionToken"]

    # 2. Logout from first session
    logout_response = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {first_token}"}
    )
    assert logout_response.status_code == 200

    # 3. Login again
    login_response = client.post("/auth/login", json={
        "email": "workflow@example.com",
        "password": "SecurePass123"
    })
    assert login_response.status_code == 200
    second_token = login_response.json()["sessionToken"]

    # Tokens should be different (new session)
    assert first_token != second_token

    # 4. Logout from second session
    logout_response2 = client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {second_token}"}
    )
    assert logout_response2.status_code == 200
