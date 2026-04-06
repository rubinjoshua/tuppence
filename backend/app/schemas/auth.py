"""Pydantic schemas for authentication - Session-based (UUID tokens, not JWT)"""

from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
import uuid


# Request schemas

class RegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: Optional[str] = Field(None, max_length=255)
    household_token: Optional[str] = Field(None, max_length=128, description="Optional sharing token to join existing household")

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validate password strength"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one digit')
        return v


class LoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class AppleSignInRequest(BaseModel):
    """Apple Sign In request"""
    identity_token: str = Field(..., description="Apple identity token (JWT)")
    authorization_code: str = Field(..., description="Apple authorization code")
    full_name: Optional[str] = Field(None, max_length=255, description="User's full name from Apple")
    household_token: Optional[str] = Field(None, max_length=128, description="Optional sharing token to join existing household")


# Response schemas

class AuthResponse(BaseModel):
    """
    Complete authentication response (session-based, not JWT).

    Flat structure to match frontend expectations (Swift camelCase).
    """
    sessionToken: str  # UUID session ID (sent as bearer token)
    userId: str  # User UUID string
    householdId: str  # Household UUID string
    email: str
    householdName: str


class LogoutResponse(BaseModel):
    """Logout response"""
    message: str = "Successfully logged out"
