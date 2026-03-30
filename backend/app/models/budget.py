"""Budget table - Monthly budget definitions"""

from sqlalchemy import Column, Integer, String, Index

from app.database import Base


class Budget(Base):
    """
    Budget table storing monthly budget definitions.

    Each budget is identified by an emoji and has a monthly increment amount.

    Schema:
        - id: Primary key (autoincrement)
        - emoji: Unique emoji identifier (e.g., "🛒" for groceries)
        - monthly_amount: Amount added to budget each month
        - label: Display name (e.g., "Groceries", "Travel")
        - user_id: Future multi-user support (nullable, not used yet)

    Note:
        Emoji must be unique per user (currently all users share budgets)
    """

    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    emoji = Column(String(10), nullable=False, unique=True, index=True)
    monthly_amount = Column(Integer, nullable=False)  # Stored as cents/smallest unit
    label = Column(String(100), nullable=False)
    user_id = Column(Integer, nullable=True, index=True)

    def __repr__(self):
        return f"<Budget(emoji={self.emoji}, label={self.label}, monthly={self.monthly_amount})>"
