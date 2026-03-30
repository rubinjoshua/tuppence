"""Automation service - Monthly budget additions"""

from sqlalchemy.orm import Session
from datetime import date, datetime, timezone
from typing import Tuple, Optional

from app.models.settings import Settings
from app.models.budget import Budget
from app.models.ledger import LedgerEntry


def check_and_run_monthly_automation(db: Session) -> Tuple[bool, Optional[date], str]:
    """
    Check and run monthly automation if needed.

    Logic:
    1. Check if today is 1st of month
    2. Check settings.last_monthly_update_date
    3. If last update != today, run automation:
       - Query all budgets
       - Insert positive ledger entry for each budget's monthly_amount
       - Update last_monthly_update_date = today
    4. This prevents duplicate updates even if called multiple times

    Args:
        db: Database session

    Returns:
        Tuple of (update_ran, update_date, message)
    """
    today = date.today()

    # Check if today is 1st of month
    if today.day != 1:
        return False, None, "Not the first of the month"

    # Get settings
    settings = db.query(Settings).filter_by(id=1).first()

    # Check if already ran today
    if settings and settings.last_monthly_update_date == today:
        return False, today, "Monthly update already ran today"

    # Run automation
    budgets = db.query(Budget).all()

    if not budgets:
        return False, None, "No budgets configured"

    # Get currency from settings
    currency = settings.currency_symbol if settings else "$"

    # Add positive ledger entry for each budget
    for budget in budgets:
        entry = LedgerEntry(
            amount=budget.monthly_amount,
            currency=currency,
            budget_emoji=budget.emoji,
            description_text=f"Monthly budget: {budget.label}",
            category=None,  # No category for budget additions
            year=today.year
        )
        db.add(entry)

    # Update settings
    if settings:
        settings.last_monthly_update_date = today
    else:
        # Create settings if doesn't exist
        settings = Settings(id=1, currency_symbol=currency, last_monthly_update_date=today)
        db.add(settings)

    db.commit()

    return True, today, f"Monthly update completed for {len(budgets)} budgets"


def archive_year(db: Session, year: int) -> bool:
    """
    Mark year as archived.

    Updates last_yearly_archive_date in settings.

    Args:
        db: Database session
        year: Year to archive

    Returns:
        True if successful
    """
    settings = db.query(Settings).filter_by(id=1).first()

    if settings:
        settings.last_yearly_archive_date = date(year, 12, 31)
    else:
        # Create settings if doesn't exist
        settings = Settings(
            id=1,
            currency_symbol="$",
            last_yearly_archive_date=date(year, 12, 31)
        )
        db.add(settings)

    db.commit()
    return True
