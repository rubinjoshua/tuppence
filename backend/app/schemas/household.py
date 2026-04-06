"""Pydantic schemas for household management"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import uuid


# Request schemas

class CreateHouseholdRequest(BaseModel):
    """Create new household request"""
    name: str = Field(..., min_length=1, max_length=255)


class UpdateHouseholdRequest(BaseModel):
    """Update household name request"""
    name: str = Field(..., min_length=1, max_length=255)


class GenerateSharingTokenRequest(BaseModel):
    """Generate sharing token request"""
    expires_in_days: int = Field(default=7, ge=1, le=30)


class JoinHouseholdRequest(BaseModel):
    """Join household via token request"""
    token: str = Field(..., min_length=1, max_length=64)


# Response schemas

class HouseholdMemberResponse(BaseModel):
    """Household member information"""
    user_id: uuid.UUID
    email: str
    full_name: Optional[str]
    role: str
    joined_at: datetime

    class Config:
        from_attributes = True


class HouseholdDetailResponse(BaseModel):
    """Detailed household information"""
    id: uuid.UUID
    name: str
    role: str  # Current user's role
    created_at: datetime
    member_count: int
    members: List[HouseholdMemberResponse]

    class Config:
        from_attributes = True


class SharingTokenResponse(BaseModel):
    """Sharing token information"""
    token: str
    expires_at: datetime
    created_at: datetime


class ListHouseholdsResponse(BaseModel):
    """List of user's households"""
    households: List[HouseholdDetailResponse]


class JoinHouseholdResponse(BaseModel):
    """Join household response"""
    household: HouseholdDetailResponse
    message: str = "Successfully joined household"


class LeaveHouseholdResponse(BaseModel):
    """Leave household response"""
    message: str = "Successfully left household"


class DeleteHouseholdResponse(BaseModel):
    """Delete household response"""
    message: str = "Household deleted successfully"


class DisconnectAndMigrateRequest(BaseModel):
    """Disconnect from household and create new one"""
    new_household_name: str = Field(default="My Household", min_length=1, max_length=255)
    copy_data: bool = Field(default=False, description="Copy budgets and settings to new household")


class DisconnectAndMigrateResponse(BaseModel):
    """Disconnect and migrate response"""
    old_household_id: uuid.UUID
    new_household: HouseholdDetailResponse
    copied_items: Optional[dict] = None  # {"budgets": 3, "settings": 1}
    message: str = "Successfully disconnected and created new household"
