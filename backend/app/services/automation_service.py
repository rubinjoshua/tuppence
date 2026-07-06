"""Automation service - Monthly budget additions, per-household"""

from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import date, datetime, timezone
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

    Idempotency: SELECT ... FOR UPDATE on the settings row serializes
    concurrent callers so two simultaneous /check_automations or scheduler
    runs can't both insert a second copy. Falls back to a row-existence
    re-check for the settings-doesn't-yet-exist case.

    The ledger entry's datetime is stamped to the 1st of the current month
    at 00:00 UTC regardless of when the automation actually runs — that
    way late-running automations still sort at the top of the spendings
    list for the month.

    Returns:
        (update_ran, update_date, message)
    """
    # Use UTC calendar so container timezone doesn't shift the month boundary.
    today = datetime.now(timezone.utc).date()
    first_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)

    # SELECT ... FOR UPDATE to serialize concurrent callers per household.
    settings = (
        db.execute(
            select(Settings)
            .where(Settings.household_id == household_id)
            .with_for_update()
        )
        .scalars()
        .first()
    )

    if settings and settings.last_monthly_update_date:
        last = settings.last_monthly_update_date
        if last.year == today.year and last.month == today.month:
            return False, last, "Monthly update already ran this month"

    # Secondary guard: if a ledger entry for this month's automation already
    # exists for this household, treat as already-ran. Protects against the
    # race where settings was just created in another transaction.
    already_inserted = db.query(LedgerEntry).filter(
        LedgerEntry.household_id == household_id,
        LedgerEntry.datetime == first_of_month,
        LedgerEntry.description_text.like("Monthly budget:%"),
    ).first()
    if already_inserted is not None:
        if settings:
            settings.last_monthly_update_date = today
            db.commit()
        return False, today, "Monthly update already ran this month"

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
            datetime=first_of_month,
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


def run_monthly_automation_for_all(db: Session) -> int:
    """
    Run the monthly automation for every household whose last update was
    in a prior month (or never). Intended for the backend scheduler so
    the automation fires even when no client opens the app.

    Returns the number of households updated.
    """
    from app.models.household import Household

    households = db.query(Household).all()
    updated = 0
    for household in households:
        try:
            ran, _, _ = check_and_run_monthly_automation(db, household.id)
            if ran:
                updated += 1
        except Exception as exc:
            # One bad household mustn't block the rest. Roll back the aborted
            # transaction so the session is usable for the next iteration.
            print(f"Monthly automation failed for household {household.id}: {exc}")
            db.rollback()
    return updated


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
