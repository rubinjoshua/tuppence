"""Settings request/response schemas"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class SyncSettingsRequest(BaseModel):
    """Request schema for syncing settings from iOS"""
    currency_symbol: str = Field(..., max_length=3, description="Currency symbol (e.g., $, €, ₪)")
    split_budget_options: Optional[List[str]] = Field(
        default=None,
        description="Optional list of multi-emoji split-budget options. Omit to leave unchanged.",
    )


class SyncSettingsResponse(BaseModel):
    """Response schema after syncing settings"""
    success: bool = True


class GetSettingsResponse(BaseModel):
    """Response schema for fetching the household's current settings."""
    currency_symbol: str
    split_budget_options: List[str] = []


class CheckAutomationsResponse(BaseModel):
    """Response schema for check automations endpoint"""
    monthly_update_ran: bool
    monthly_update_date: Optional[date]
    message: str


class ArchiveYearResponse(BaseModel):
    """Response schema after archiving a year"""
    success: bool = True
    year: int
