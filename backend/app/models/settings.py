"""Settings table - Global application settings"""

from sqlalchemy import Column, Integer, String, Date, CheckConstraint

from app.database import Base


class Settings(Base):
    """
    Settings table storing global application settings.

    This is a single-row table (id always = 1) enforced by CHECK constraint.

    Schema:
        - id: Primary key (always = 1, enforced by CHECK)
        - currency_symbol: Currency symbol (e.g., "$", "€", "₪")
        - last_monthly_update_date: Last date monthly automation ran
        - last_yearly_archive_date: Last date year was archived
        - user_id: Future multi-user support (nullable, not used yet)

    Note:
        Only one settings row should exist. Use upsert pattern for updates.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    currency_symbol = Column(String(3), nullable=False, default="$")
    last_monthly_update_date = Column(Date, nullable=True)
    last_yearly_archive_date = Column(Date, nullable=True)
    user_id = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint('id = 1', name='single_row_check'),
    )

    def __repr__(self):
        return f"<Settings(currency={self.currency_symbol}, last_update={self.last_monthly_update_date})>"
