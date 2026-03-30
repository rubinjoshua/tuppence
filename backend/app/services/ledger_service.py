"""Ledger service - Queries and calculations"""

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


def get_amounts_for_current_year(db: Session, year: Optional[int] = None) -> List[BudgetWithTotal]:
    """
    Get total amount left per budget for current year.

    SQL: SELECT budget_emoji, SUM(amount) FROM ledger WHERE year=current_year GROUP BY budget_emoji

    Args:
        db: Database session
        year: Year to query (defaults to current year)

    Returns:
        List of budgets with total amounts
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    # Get all budgets
    budgets = db.query(Budget).all()

    # Calculate totals from ledger
    ledger_totals = db.query(
        LedgerEntry.budget_emoji,
        func.sum(LedgerEntry.amount).label('total')
    ).filter(
        LedgerEntry.year == year
    ).group_by(
        LedgerEntry.budget_emoji
    ).all()

    # Create lookup dict
    totals_dict = {emoji: total for emoji, total in ledger_totals}

    # Build response
    result = []
    for budget in budgets:
        total_amount = totals_dict.get(budget.emoji, 0)
        result.append(BudgetWithTotal(
            emoji=budget.emoji,
            label=budget.label,
            monthly_amount=budget.monthly_amount,
            total_amount=total_amount
        ))

    return result


def get_ledger_for_month(db: Session, month_str: str) -> List[LedgerEntryResponse]:
    """
    Get spending history for specified month.

    Args:
        db: Database session
        month_str: Month in format "YYYY-MM"

    Returns:
        List of ledger entries ordered by datetime DESC
    """
    # Parse month string
    year, month = map(int, month_str.split('-'))

    # Query ledger
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.year == year,
        extract('month', LedgerEntry.datetime) == month
    ).order_by(
        LedgerEntry.datetime.desc()
    ).all()

    return [LedgerEntryResponse.model_validate(entry) for entry in entries]


def get_category_map(
    db: Session,
    month_str: str,
    budget_emoji: str
) -> List[CategoryBreakdown]:
    """
    Get category breakdown for pie chart.

    Groups ledger entries by category with totals and colors.

    Args:
        db: Database session
        month_str: Month in format "YYYY-MM"
        budget_emoji: Budget emoji to filter by

    Returns:
        List of category breakdowns with colors and totals
    """
    # Parse month string
    year, month = map(int, month_str.split('-'))

    # Query ledger entries for this month and budget
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.year == year,
        extract('month', LedgerEntry.datetime) == month,
        LedgerEntry.budget_emoji == budget_emoji,
        LedgerEntry.category.isnot(None)  # Only entries with categories
    ).all()

    # Group by category
    category_data = {}
    for entry in entries:
        if entry.category not in category_data:
            category_data[entry.category] = {
                'texts': [],
                'total_amount': 0
            }
        category_data[entry.category]['texts'].append(entry.description_text or "")
        category_data[entry.category]['total_amount'] += abs(entry.amount)  # Use absolute value for pie chart

    # Get colors from categories table
    categories = db.query(Category).filter(
        Category.category_name.in_(category_data.keys())
    ).all()
    color_map = {cat.category_name: cat.hex_color for cat in categories}

    # Build response
    result = []
    for category_name, data in category_data.items():
        result.append(CategoryBreakdown(
            category_name=category_name,
            hex_color=color_map.get(category_name, "#CCCCCC"),  # Default gray if not found
            texts=data['texts'],
            total_amount=data['total_amount']
        ))

    # Sort by total_amount descending
    result.sort(key=lambda x: x.total_amount, reverse=True)

    return result


def delete_ledger_entry(db: Session, entry_uuid: UUID) -> bool:
    """
    Delete ledger entry by UUID.

    Args:
        db: Database session
        entry_uuid: UUID of entry to delete

    Returns:
        True if deleted, False if not found
    """
    entry = db.query(LedgerEntry).filter(LedgerEntry.uuid == entry_uuid).first()
    if not entry:
        return False

    db.delete(entry)
    db.commit()
    return True


def export_year_as_csv(db: Session, year: int) -> str:
    """
    Export all ledger entries for a year as CSV.

    Args:
        db: Database session
        year: Year to export

    Returns:
        CSV string with headers: Date, Budget, Description, Category, Amount, Currency
    """
    entries = db.query(LedgerEntry).filter(
        LedgerEntry.year == year
    ).order_by(
        LedgerEntry.datetime.asc()
    ).all()

    # Build CSV
    lines = ["Date,Budget,Description,Category,Amount,Currency"]
    for entry in entries:
        date_str = entry.datetime.strftime("%Y-%m-%d %H:%M:%S")
        description = (entry.description_text or "").replace('"', '""')  # Escape quotes
        category = (entry.category or "").replace('"', '""')
        lines.append(
            f'"{date_str}","{entry.budget_emoji}","{description}","{category}",{entry.amount},"{entry.currency}"'
        )

    return "\n".join(lines)
