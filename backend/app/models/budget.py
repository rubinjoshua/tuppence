"""Budget table - Monthly budget definitions"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone

from app.database import Base


class Budget(Base):
    """
    Budget table storing monthly budget definitions.

    Each budget is identified by an emoji and has a monthly increment amount.
    Budgets are scoped to households - all members see the same budgets.

    Schema:
        - id: Primary key (autoincrement)
        - household_id: Foreign key to households (NOT NULL, CASCADE delete)
        - emoji: Emoji identifier (e.g., "🛒" for groceries)
        - label: Display name (e.g., "Groceries", "Travel")
        - monthly_amount: Amount added to budget each month (cents/smallest unit)
        - created_at: Budget creation timestamp
        - updated_at: Last update timestamp

    Constraints:
        - Emoji must be unique per household (not globally)
    """

    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    household_id = Column(UUID(as_uuid=True), ForeignKey('households.id', ondelete='CASCADE'), nullable=False, index=True)
    emoji = Column(String(10), nullable=False, index=True)
    label = Column(String(100), nullable=False)
    monthly_amount = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint('household_id', 'emoji', name='uq_budgets_household_emoji'),
    )

    def __repr__(self):
        return f"<Budget(household_id={self.household_id}, emoji={self.emoji}, label={self.label}, monthly={self.monthly_amount})>"
