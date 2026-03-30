"""Ledger request/response schemas"""

from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import Union


class MakeSpendingRequest(BaseModel):
    """Request schema for creating a new spending entry"""
    amount: int
    currency: str = Field(max_length=3)
    budget_emoji: str = Field(max_length=10)
    description_text: Union[str, None] = None
    datetime: Union[datetime, None] = None


class MakeSpendingResponse(BaseModel):
    """Response schema after creating a spending entry"""
    uuid: UUID
    category: str
    success: bool = True


class LedgerEntryResponse(BaseModel):
    """Schema for ledger entry in list responses"""
    uuid: UUID
    amount: int
    currency: str
    budget_emoji: str
    datetime: datetime
    description_text: Union[str, None] = None
    category: Union[str, None] = None

    model_config = {"from_attributes": True}


class UndoSpendingResponse(BaseModel):
    """Response schema after deleting a spending entry"""
    success: bool
    message: str
