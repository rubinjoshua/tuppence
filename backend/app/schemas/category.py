"""Category request/response schemas"""

from datetime import datetime
from pydantic import BaseModel
from typing import List


class CategoryEntry(BaseModel):
    """One spending entry inside a category breakdown."""
    description: str
    amount: int  # positive; expense magnitude
    datetime: datetime


class CategoryBreakdown(BaseModel):
    """Schema for category breakdown in pie chart"""
    category_name: str
    hex_color: str
    entries: List[CategoryEntry]  # Individual spendings in this category, newest first
    total_amount: int  # Sum of amounts for this category


class CategoryMapResponse(BaseModel):
    """Response schema for category map endpoint"""
    categories: List[CategoryBreakdown]
