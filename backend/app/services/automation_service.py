"""Automation service - Monthly budget additions, per-household"""

from sqlalchemy.orm import Session
from datetime import date
from typing import Tuple, Optional
from uuid import UUID

from app.models.settings import Settings
from app.models.budget import Budget
from app.models.ledger import LedgerEntry


def check_and_run_monthly_automation(
    db: Session,
    household_id: UUID,
) -> Tuple[bool, Optional[date], str]:
    """
    Add this household's monthly budget amounts if they haven't been added
    for the current calendar month yet.

    The original spec says "an automation at the first of every month that
    adds each budget's amount to that budget". Triggering only on the 1st
    causes the entire month to be skipped if no one opens the app that day,
    so we instead key off month/year: if the last update was in a previous
    month (or never), run it now and stamp today's date.

    Returns:
        (update_ran, update_date, message)
    """
    today = date.today()

    settings = db.query(Settings).filter_by(household_id=household_id).first()

    if settings and settings.last_monthly_update_date:
        last = settings.last_monthly_update_date
        if last.year == today.year and last.month == today.month:
            return False, last, "Monthly update already ran this month"

    budgets = db.query(Budget).filter(Budget.household_id == household_id).all()
    if not budgets:
        return False, None, "No budgets configured"

    currency = settings.currency_symbol if settings else "$"

    for budget in budgets:
        db.add(LedgerEntry(
            household_id=household_id,
            amount=budget.monthly_amount,
            currency=currency,
            budget_emoji=budget.emoji,
            description_text=f"Monthly budget: {budget.label}",
            category=None,
            year=today.year,
        ))

    if settings:
        settings.last_monthly_update_date = today
    else:
        db.add(Settings(
            household_id=household_id,
            currency_symbol=currency,
            last_monthly_update_date=today,
        ))

    db.commit()

    return True, today, f"Monthly update completed for {len(budgets)} budgets"


def archive_year(db: Session, household_id: UUID, year: int) -> bool:
    """Mark a year as archived for this household."""
    settings = db.query(Settings).filter_by(household_id=household_id).first()

    if settings:
        settings.last_yearly_archive_date = date(year, 12, 31)
    else:
        db.add(Settings(
            household_id=household_id,
            currency_symbol="$",
            last_yearly_archive_date=date(year, 12, 31),
        ))

    db.commit()
    return True
