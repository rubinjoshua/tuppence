"""Settings table - Per-household application settings"""

from sqlalchemy import Column, String, Date, ForeignKey
from app.models._types import GUID

from app.database import Base


class Settings(Base):
    """
    Per-household settings (one row per household, keyed by household_id).

    Schema:
        - household_id: Primary key, FK to households (CASCADE delete)
        - currency_symbol: Currency symbol (e.g., "$", "€", "₪")
        - last_monthly_update_date: Last date monthly automation ran
        - last_yearly_archive_date: Last date year was archived
    """

    __tablename__ = "settings"

    household_id = Column(
        GUID(),
        ForeignKey('households.id', ondelete='CASCADE'),
        primary_key=True,
    )
    currency_symbol = Column(String(3), nullable=False, default="$")
    last_monthly_update_date = Column(Date, nullable=True)
    last_yearly_archive_date = Column(Date, nullable=True)

    def __repr__(self):
        return f"<Settings(household={self.household_id}, currency={self.currency_symbol}, last_update={self.last_monthly_update_date})>"
