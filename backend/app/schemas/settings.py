"""Settings request/response schemas"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class SyncSettingsRequest(BaseModel):
    """Request schema for syncing settings from iOS"""
    currency_symbol: str = Field(..., max_length=3, description="Currency symbol (e.g., $, €, ₪)")


class SyncSettingsResponse(BaseModel):
    """Response schema after syncing settings"""
    success: bool = True


class CheckAutomationsResponse(BaseModel):
    """Response schema for check automations endpoint"""
    monthly_update_ran: bool
    monthly_update_date: Optional[date]
    message: str


class ArchiveYearResponse(BaseModel):
    """Response schema after archiving a year"""
    success: bool = True
    year: int
