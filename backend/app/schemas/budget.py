"""Budget request/response schemas"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class BudgetItem(BaseModel):
    """Schema for a single budget item"""
    emoji: str = Field(..., max_length=10, description="Budget emoji identifier")
    label: str = Field(..., max_length=100, description="Budget display name")
    monthly_amount: int = Field(..., description="Monthly budget increment amount")


class CreateBudgetRequest(BaseModel):
    """Request schema for creating a new budget"""
    emoji: str = Field(..., max_length=10, description="Budget emoji identifier")
    label: str = Field(..., max_length=100, description="Budget display name")
    monthly_amount: int = Field(..., gt=0, description="Monthly budget increment amount (must be positive)")


class UpdateBudgetRequest(BaseModel):
    """Request schema for updating an existing budget"""
    emoji: Optional[str] = Field(None, max_length=10, description="Budget emoji identifier")
    label: Optional[str] = Field(None, max_length=100, description="Budget display name")
    monthly_amount: Optional[int] = Field(None, gt=0, description="Monthly budget increment amount (must be positive)")


class BudgetResponse(BaseModel):
    """Response schema for a single budget"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    household_id: UUID
    emoji: str
    label: str
    monthly_amount: int
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ListBudgetsResponse(BaseModel):
    """Response schema for listing budgets"""
    budgets: List[BudgetResponse]


class DeleteBudgetResponse(BaseModel):
    """Response schema for deleting a budget"""
    success: bool = True
    message: str = "Budget deleted successfully"


class ReorderBudgetsRequest(BaseModel):
    """Request schema for updating budget display order"""
    budget_ids: List[int] = Field(..., description="Budget IDs in desired display order (first = first shown)")


class ReorderBudgetsResponse(BaseModel):
    """Response schema for reordering budgets"""
    success: bool = True


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
