"""Ledger table - Single source of truth for all transactions"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from app.models._types import GUID
import uuid
from datetime import datetime, timezone

from app.database import Base


class LedgerEntry(Base):
    """
    Ledger table storing all financial transactions.

    Single source of truth for the entire app. All totals, amounts, and
    breakdowns are derived from this table via SQL queries.

    Schema:
        - uuid: Primary key (UUID)
        - household_id: Foreign key to households (NOT NULL, CASCADE delete)
        - amount: Transaction amount (positive for income/budget additions, negative for spending)
        - currency: Currency code (e.g., "USD", "EUR", "ILS")
        - budget_emoji: Budget category identifier
        - datetime: Transaction timestamp (timezone-aware)
        - description_text: User-provided free text description (nullable)
        - category: AI-generated category (nullable)
        - year: Year for partitioning/filtering data
    """

    __tablename__ = "ledger"

    uuid = Column(GUID(), primary_key=True, default=uuid.uuid4, index=True)
    household_id = Column(
        GUID(),
        ForeignKey('households.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    amount = Column(Integer, nullable=False)
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

    __table_args__ = (
        Index('idx_ledger_household_year', 'household_id', 'year'),
        Index('idx_ledger_household_budget_year', 'household_id', 'budget_emoji', 'year'),
    )

    def __repr__(self):
        return f"<LedgerEntry(uuid={self.uuid}, household={self.household_id}, amount={self.amount}, emoji={self.budget_emoji})>"
