"""Budget service - Budget sync logic"""

from sqlalchemy.orm import Session
from typing import List

from app.models.budget import Budget
from app.schemas.budget import BudgetItem


def sync_budgets(db: Session, budgets: List[BudgetItem]) -> int:
    """
    Sync budgets from iOS Settings.

    Upserts budgets (adds new, updates existing based on emoji).

    Args:
        db: Database session
        budgets: List of budget items from iOS

    Returns:
        Number of budgets synced
    """
    synced_count = 0

    for budget_item in budgets:
        # Check if budget exists
        existing = db.query(Budget).filter_by(emoji=budget_item.emoji).first()

        if existing:
            # Update existing
            existing.label = budget_item.label
            existing.monthly_amount = budget_item.monthly_amount
        else:
            # Create new
            new_budget = Budget(
                emoji=budget_item.emoji,
                label=budget_item.label,
                monthly_amount=budget_item.monthly_amount
            )
            db.add(new_budget)

        synced_count += 1

    db.commit()
    return synced_count


def get_all_budgets(db: Session) -> List[BudgetItem]:
    """
    Get all budgets.

    Args:
        db: Database session

    Returns:
        List of all budgets
    """
    budgets = db.query(Budget).all()
    return [
        BudgetItem(
            emoji=b.emoji,
            label=b.label,
            monthly_amount=b.monthly_amount
        )
        for b in budgets
    ]
