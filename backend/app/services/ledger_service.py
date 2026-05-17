"""Ledger service - Household-scoped queries and calculations"""

from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from typing import List, Optional
from datetime import datetime, timezone
from uuid import UUID

from app.models.ledger import LedgerEntry
from app.models.budget import Budget
from app.models.category import Category
from app.schemas.ledger import LedgerEntryResponse
from app.schemas.budget import BudgetWithTotal
from app.schemas.category import CategoryBreakdown


def get_amounts_for_current_year(
    db: Session,
    household_id: UUID,
    year: Optional[int] = None,
) -> List[BudgetWithTotal]:
    """
    Get total amount left per budget for current year, scoped to a household.

    SQL: SELECT budget_emoji, SUM(amount) FROM ledger
         WHERE year=? AND household_id=? GROUP BY budget_emoji
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    budgets = db.query(Budget).filter(Budget.household_id == household_id).all()

    ledger_totals = db.query(
        LedgerEntry.budget_emoji,
        func.sum(LedgerEntry.amount).label('total')
    ).filter(
        LedgerEntry.year == year,
        LedgerEntry.household_id == household_id,
    ).group_by(
        LedgerEntry.budget_emoji
    ).all()

    totals_dict = {emoji: total for emoji, total in ledger_totals}

    return [
        BudgetWithTotal(
            emoji=budget.emoji,
            label=budget.label,
            monthly_amount=budget.monthly_amount,
            total_amount=totals_dict.get(budget.emoji, 0),
        )
        for budget in budgets
    ]


def get_ledger_for_month(
    db: Session,
    household_id: UUID,
    month_str: str,
) -> List[LedgerEntryResponse]:
    """
    Get spending history for specified month, scoped to a household.

    Args:
        month_str: Month in format "YYYY-MM"
    """
    year, month = map(int, month_str.split('-'))

    entries = db.query(LedgerEntry).filter(
        LedgerEntry.household_id == household_id,
        LedgerEntry.year == year,
        extract('month', LedgerEntry.datetime) == month,
    ).order_by(
        LedgerEntry.datetime.desc()
    ).all()

    return [LedgerEntryResponse.model_validate(entry) for entry in entries]


def get_category_map(
    db: Session,
    household_id: UUID,
    month_str: str,
    budget_emoji: str,
) -> List[CategoryBreakdown]:
    """
    Get category breakdown for pie chart, scoped to a household.
    """
    year, month = map(int, month_str.split('-'))

    entries = db.query(LedgerEntry).filter(
        LedgerEntry.household_id == household_id,
        LedgerEntry.year == year,
        extract('month', LedgerEntry.datetime) == month,
        LedgerEntry.budget_emoji == budget_emoji,
        LedgerEntry.category.isnot(None),
    ).all()

    category_data = {}
    for entry in entries:
        if entry.category not in category_data:
            category_data[entry.category] = {'texts': [], 'total_amount': 0}
        category_data[entry.category]['texts'].append(entry.description_text or "")
        category_data[entry.category]['total_amount'] += abs(entry.amount)

    categories = db.query(Category).filter(
        Category.category_name.in_(category_data.keys())
    ).all()
    color_map = {cat.category_name: cat.hex_color for cat in categories}

    result = [
        CategoryBreakdown(
            category_name=category_name,
            hex_color=color_map.get(category_name, "#CCCCCC"),
            texts=data['texts'],
            total_amount=data['total_amount'],
        )
        for category_name, data in category_data.items()
    ]

    result.sort(key=lambda x: x.total_amount, reverse=True)
    return result


def delete_ledger_entry(db: Session, household_id: UUID, entry_uuid: UUID) -> bool:
    """
    Delete ledger entry by UUID, only if it belongs to the given household.

    Filtering by household_id prevents user A from deleting user B's entries
    by guessing UUIDs.
    """
    entry = db.query(LedgerEntry).filter(
        LedgerEntry.uuid == entry_uuid,
        LedgerEntry.household_id == household_id,
    ).first()
    if not entry:
        return False

    db.delete(entry)
    db.commit()
    return True


def export_year_as_csv(db: Session, household_id: UUID, year: int) -> str:
    """
    Export all ledger entries for a year as CSV, scoped to a household.
    """
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.household_id == household_id,
        LedgerEntry.year == year,
    ).order_by(
        LedgerEntry.datetime.asc()
    ).all()

    lines = ["Date,Budget,Description,Category,Amount,Currency"]
    for entry in entries:
        date_str = entry.datetime.strftime("%Y-%m-%d %H:%M:%S")
        description = (entry.description_text or "").replace('"', '""')
        category = (entry.category or "").replace('"', '""')
        lines.append(
            f'"{date_str}","{entry.budget_emoji}","{description}","{category}",{entry.amount},"{entry.currency}"'
        )

    return "\n".join(lines)
