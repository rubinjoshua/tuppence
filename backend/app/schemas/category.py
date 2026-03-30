"""Category request/response schemas"""

from pydantic import BaseModel
from typing import List


class CategoryBreakdown(BaseModel):
    """Schema for category breakdown in pie chart"""
    category_name: str
    hex_color: str
    texts: List[str]  # List of description texts in this category
    total_amount: int  # Sum of amounts for this category


class CategoryMapResponse(BaseModel):
    """Response schema for category map endpoint"""
    categories: List[CategoryBreakdown]
