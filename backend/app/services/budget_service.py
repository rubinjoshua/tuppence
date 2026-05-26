"""Budget service - Household-scoped budget sync logic"""

from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.models.budget import Budget
from app.schemas.budget import BudgetItem


def sync_budgets(db: Session, household_id: UUID, budgets: List[BudgetItem]) -> int:
    """
    Sync budgets for a household (upsert by emoji).

    Upserts are scoped to the household: a budget for "🛒" in household A is
    independent from "🛒" in household B (UNIQUE constraint is on
    (household_id, emoji)).
    """
    synced_count = 0

    for budget_item in budgets:
        existing = db.query(Budget).filter_by(
            household_id=household_id,
            emoji=budget_item.emoji,
        ).first()

        if existing:
            existing.label = budget_item.label
            existing.monthly_amount = budget_item.monthly_amount
        else:
            db.add(Budget(
                household_id=household_id,
                emoji=budget_item.emoji,
                label=budget_item.label,
                monthly_amount=budget_item.monthly_amount,
            ))

        synced_count += 1

    db.commit()
    return synced_count


def get_all_budgets(db: Session, household_id: UUID) -> List[BudgetItem]:
    """Get all budgets for a household."""
    budgets = db.query(Budget).filter(
        Budget.household_id == household_id
    ).order_by(Budget.sort_order.asc(), Budget.created_at.asc()).all()
    return [
        BudgetItem(
            emoji=b.emoji,
            label=b.label,
            monthly_amount=b.monthly_amount,
        )
        for b in budgets
    ]
