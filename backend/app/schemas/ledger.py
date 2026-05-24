"""Ledger request/response schemas"""

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime as DateTime
from uuid import UUID
from typing import Union, Optional


class MakeSpendingRequest(BaseModel):
    """Request schema for creating a new spending entry"""
    amount: int
    currency: str = Field(max_length=3)
    budget_emoji: str = Field(max_length=10)
    description_text: Union[str, None] = None
    # Field name `datetime` would shadow the imported type inside the class
    # body and confuse pydantic's annotation resolution (it ends up treating
    # the annotation as None). Alias keeps the wire contract as "datetime".
    spent_at: Optional[DateTime] = Field(default=None, alias="datetime")

    model_config = ConfigDict(populate_by_name=True)


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
    spent_at: DateTime = Field(alias="datetime", serialization_alias="datetime")
    description_text: Union[str, None] = None
    category: Union[str, None] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UndoSpendingResponse(BaseModel):
    """Response schema after deleting a spending entry"""
    success: bool
    message: str
