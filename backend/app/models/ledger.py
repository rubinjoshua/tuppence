"""Ledger table - Single source of truth for all transactions"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.database import Base


class LedgerEntry(Base):
    """
    Ledger table storing all financial transactions.

    This is the single source of truth for the entire app.
    All totals, amounts, and breakdowns are derived from this table via SQL queries.

    Schema:
        - uuid: Primary key (UUID)
        - amount: Transaction amount (positive for income/budget additions, negative for spending)
        - currency: Currency code (e.g., "USD", "EUR", "ILS")
        - budget_emoji: Budget category identifier (emoji like "🛒", "✈️")
        - datetime: Transaction timestamp (timezone-aware)
        - description_text: User-provided free text description (nullable)
        - category: AI-generated category (nullable)
        - year: Year for partitioning/filtering data
        - user_id: Future multi-user support (nullable, not used yet)

    Indexes:
        - year: For filtering by year
        - budget_emoji + year: For calculating per-budget totals
        - datetime: For chronological ordering
        - user_id: For future multi-user support
    """

    __tablename__ = "ledger"

    uuid = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    amount = Column(Integer, nullable=False)  # Stored as cents/smallest unit
    currency = Column(String(3), nullable=False, default="USD")
    budget_emoji = Column(String(10), nullable=False, index=True)
    datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    description_text = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    year = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_budget_year', 'budget_emoji', 'year'),
        Index('idx_year_datetime', 'year', 'datetime'),
    )

    def __repr__(self):
        return f"<LedgerEntry(uuid={self.uuid}, amount={self.amount}, emoji={self.budget_emoji}, date={self.datetime})>"
