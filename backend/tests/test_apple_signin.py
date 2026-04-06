"""Tests for Apple Sign In endpoint"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone, timedelta

from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.models.sharing_token import SharingToken


@pytest.fixture
def mock_apple_user_info():
    """Mock Apple user info extracted from token"""
    return {
        "apple_id": "001234.abcd1234abcd1234abcd1234abcd1234.1234",
        "email": "user@example.com",
        "email_verified": True,
        "full_name": "Test User"
    }


@pytest.fixture
def sharing_token_fixture(client, db):
    """Create a valid sharing token for testing"""
    # Create household
    household = Household(name="Shared Household")
    db.add(household)
    db.flush()

    # Create owner user
    owner = User(
        email="owner@example.com",
        password_hash="hashed_password",
        full_name="Owner User",
        is_active=True
    )
    db.add(owner)
    db.flush()

    # Add owner to household
    membership = HouseholdMember(
        household_id=household.id,
        user_id=owner.id,
        role="owner"
    )
    db.add(membership)
    db.flush()

    # Create sharing token
    token = SharingToken(
        household_id=household.id,
        token="test_sharing_token_123",
        created_by=owner.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_active=True
    )
    db.add(token)
    db.commit()

    return {
        "household": household,
        "owner": owner,
        "token": token
    }


class TestAppleSignIn:
    """Test POST /auth/apple-signin"""

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_new_user(self, mock_extract, client, db, mock_apple_user_info):
        """New user signs in with Apple - creates account and household"""
        mock_extract.return_value = mock_apple_user_info

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code",
            "full_name": "Test User"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "sessionToken" in data
        assert "userId" in data
        assert "householdId" in data
        assert "email" in data
        assert "householdName" in data
        assert data["email"] == "user@example.com"
        assert data["householdName"] == "My Household"

        # Verify user was created
        user = db.query(User).filter(User.apple_id == mock_apple_user_info["apple_id"]).first()
        assert user is not None
        assert user.email == "user@example.com"
        assert user.full_name == "Test User"
        assert user.apple_id == mock_apple_user_info["apple_id"]
        assert user.password_hash is None  # No password for Apple users

        # Verify household was created
        household = db.query(Household).filter(Household.name == "My Household").first()
        assert household is not None

        # Verify user is owner of household
        membership = db.query(HouseholdMember).filter(
            HouseholdMember.user_id == user.id,
            HouseholdMember.household_id == household.id
        ).first()
        assert membership is not None
        assert membership.role == "owner"

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_existing_user(self, mock_extract, client, db, mock_apple_user_info):
        """Existing Apple user signs in - returns session"""
        mock_extract.return_value = mock_apple_user_info

        # Create existing user
        user = User(
            email="user@example.com",
            apple_id=mock_apple_user_info["apple_id"],
            full_name="Test User",
            is_active=True
        )
        db.add(user)
        db.flush()

        # Create household
        household = Household(name="Existing Household")
        db.add(household)
        db.flush()

        # Add user to household
        membership = HouseholdMember(
            household_id=household.id,
            user_id=user.id,
            role="owner"
        )
        db.add(membership)
        db.commit()

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["email"] == "user@example.com"
        assert data["householdName"] == "Existing Household"

        # Should not create a new user
        user_count = db.query(User).filter(User.apple_id == mock_apple_user_info["apple_id"]).count()
        assert user_count == 1

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_with_household_token(self, mock_extract, client, db, mock_apple_user_info, sharing_token_fixture):
        """New user signs in with household token - joins existing household"""
        mock_extract.return_value = mock_apple_user_info

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code",
            "full_name": "Test User",
            "household_token": sharing_token_fixture["token"].token
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["householdName"] == "Shared Household"

        # Verify user was created
        user = db.query(User).filter(User.apple_id == mock_apple_user_info["apple_id"]).first()
        assert user is not None

        # Verify user joined the shared household as member (not owner)
        membership = db.query(HouseholdMember).filter(
            HouseholdMember.user_id == user.id,
            HouseholdMember.household_id == sharing_token_fixture["household"].id
        ).first()
        assert membership is not None
        assert membership.role == "member"

        # Verify token was marked as used
        db.refresh(sharing_token_fixture["token"])
        assert sharing_token_fixture["token"].used_at is not None
        assert sharing_token_fixture["token"].used_by == user.id

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_invalid_household_token(self, mock_extract, client, db, mock_apple_user_info):
        """Sign in with invalid household token returns error"""
        mock_extract.return_value = mock_apple_user_info

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code",
            "household_token": "invalid_token"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_expired_household_token(self, mock_extract, client, db, mock_apple_user_info):
        """Sign in with expired household token returns error"""
        mock_extract.return_value = mock_apple_user_info

        # Create a household with owner
        household = Household(name="Shared Household")
        db.add(household)
        db.flush()

        owner = User(
            email="owner@example.com",
            password_hash="hashed_password",
            full_name="Owner User",
            is_active=True
        )
        db.add(owner)
        db.flush()

        membership = HouseholdMember(
            household_id=household.id,
            user_id=owner.id,
            role="owner"
        )
        db.add(membership)
        db.flush()

        # Create token that's already expired (created_at and expires_at both in the past)
        past_time = datetime.now(timezone.utc) - timedelta(days=10)
        expired_token = SharingToken(
            household_id=household.id,
            token="expired_token_123",
            created_by=owner.id,
            created_at=past_time,
            expires_at=past_time + timedelta(days=1),  # Still past
            is_active=True
        )
        db.add(expired_token)
        db.commit()

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code",
            "household_token": "expired_token_123"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_used_household_token(self, mock_extract, client, db, mock_apple_user_info, sharing_token_fixture):
        """Sign in with already-used household token returns error"""
        mock_extract.return_value = mock_apple_user_info

        # Mark token as used
        token = sharing_token_fixture["token"]
        token.used_at = datetime.now(timezone.utc)
        token.used_by = sharing_token_fixture["owner"].id
        db.commit()

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code",
            "household_token": token.token
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 400
        assert "already been used" in response.json()["detail"].lower()

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_email_conflict(self, mock_extract, client, db, mock_apple_user_info):
        """Sign in with email already registered via email/password returns error"""
        mock_extract.return_value = mock_apple_user_info

        # Create existing user with same email but different auth method
        existing_user = User(
            email="user@example.com",
            password_hash="hashed_password",
            full_name="Existing User",
            is_active=True
        )
        db.add(existing_user)
        db.flush()

        household = Household(name="Existing Household")
        db.add(household)
        db.flush()

        membership = HouseholdMember(
            household_id=household.id,
            user_id=existing_user.id,
            role="owner"
        )
        db.add(membership)
        db.commit()

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_inactive_user(self, mock_extract, client, db, mock_apple_user_info):
        """Inactive user cannot sign in"""
        mock_extract.return_value = mock_apple_user_info

        # Create inactive user
        user = User(
            email="user@example.com",
            apple_id=mock_apple_user_info["apple_id"],
            full_name="Test User",
            is_active=False  # Inactive
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

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 403
        assert "inactive" in response.json()["detail"].lower()

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_token_verification_failure(self, mock_extract, client, db):
        """Invalid Apple token returns error"""
        from fastapi import HTTPException, status

        # Simulate token verification failure
        mock_extract.side_effect = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identity token"
        )

        request_data = {
            "identity_token": "invalid_token",
            "authorization_code": "fake_auth_code"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    @patch('app.api.auth.extract_apple_user_info')
    def test_apple_signin_no_email_fallback(self, mock_extract, client, db):
        """Apple user with no email uses fallback email"""
        # Mock user info without email
        mock_extract.return_value = {
            "apple_id": "001234.abcd1234abcd1234abcd1234abcd1234.1234",
            "email": None,
            "email_verified": False,
            "full_name": "Test User"
        }

        request_data = {
            "identity_token": "fake_apple_token",
            "authorization_code": "fake_auth_code",
            "full_name": "Test User"
        }

        response = client.post("/auth/apple-signin", json=request_data)

        assert response.status_code == 200
        data = response.json()

        # Should use fallback email
        assert "@appleid.private" in data["email"]

        # Verify user was created with fallback email
        user = db.query(User).filter(
            User.apple_id == "001234.abcd1234abcd1234abcd1234abcd1234.1234"
        ).first()
        assert user is not None
        assert "@appleid.private" in user.email
