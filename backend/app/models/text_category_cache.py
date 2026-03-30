"""Text-category cache table - Cache AI categorization results"""

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone

from app.database import Base


class TextCategoryCache(Base):
    """
    Cache table for AI categorization results.

    Stores mapping between cleaned text descriptions and categories to minimize OpenAI API calls.

    Schema:
        - id: Primary key (autoincrement)
        - cleaned_text: Normalized text (lowercase, no punctuation, unique)
        - category_name: AI-assigned category
        - created_at: Timestamp of cache entry creation

    Process:
        1. User spending text is cleaned (lowercase, no punctuation)
        2. Check cache for exact match
        3. If miss, call OpenAI API and cache result
        4. If hit, return cached category

    Note:
        Cleaned text is unique to prevent duplicate cache entries.
    """

    __tablename__ = "text_category_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cleaned_text = Column(String(500), nullable=False, unique=True, index=True)
    category_name = Column(String(100), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self):
        return f"<TextCategoryCache(text='{self.cleaned_text}', category={self.category_name})>"
