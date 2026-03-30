"""Budget request/response schemas"""

from pydantic import BaseModel, Field
from typing import List


class BudgetItem(BaseModel):
    """Schema for a single budget item"""
    emoji: str = Field(..., max_length=10, description="Budget emoji identifier")
    label: str = Field(..., max_length=100, description="Budget display name")
    monthly_amount: int = Field(..., description="Monthly budget increment amount")


class SyncBudgetsRequest(BaseModel):
    """Request schema for syncing budgets from iOS Settings"""
    budgets: List[BudgetItem]


class SyncBudgetsResponse(BaseModel):
    """Response schema after syncing budgets"""
    success: bool = True
    synced_count: int


class BudgetWithTotal(BaseModel):
    """Schema for budget with current total amount"""
    emoji: str
    label: str
    monthly_amount: int
    total_amount: int  # Derived from ledger


class MonthlyBudgetsResponse(BaseModel):
    """Response schema for monthly budgets endpoint"""
    budgets: List[BudgetItem]


class AmountsResponse(BaseModel):
    """Response schema for amounts endpoint"""
    budgets: List[BudgetWithTotal]
