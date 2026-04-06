"""Budget management endpoints - Household-scoped CRUD operations"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Tuple
from datetime import datetime, timezone

from app.database import get_db
from app.models.user import User
from app.models.household import Household
from app.models.budget import Budget
from app.schemas.budget import (
    CreateBudgetRequest,
    UpdateBudgetRequest,
    BudgetResponse,
    ListBudgetsResponse,
    DeleteBudgetResponse,
)
from app.dependencies.auth import get_current_user_and_household

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=ListBudgetsResponse)
async def list_budgets(
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db)
):
    """
    List all budgets for authenticated user's household.

    Returns all budgets scoped to the user's current household.
    All household members see the same budgets.
    """
    user, household = user_household

    budgets = db.query(Budget).filter(
        Budget.household_id == household.id
    ).order_by(Budget.created_at.asc()).all()

    return ListBudgetsResponse(
        budgets=[BudgetResponse.model_validate(budget) for budget in budgets]
    )


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    data: CreateBudgetRequest,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db)
):
    """
    Create a new budget for authenticated user's household.

    Validates that emoji is unique within the household.
    All household members will see this budget.
    """
    user, household = user_household

    # Check if emoji already exists in this household
    existing_budget = db.query(Budget).filter(
        Budget.household_id == household.id,
        Budget.emoji == data.emoji
    ).first()

    if existing_budget:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Budget with emoji '{data.emoji}' already exists in this household"
        )

    # Create budget
    budget = Budget(
        household_id=household.id,
        emoji=data.emoji,
        label=data.label,
        monthly_amount=data.monthly_amount
    )

    db.add(budget)
    db.commit()
    db.refresh(budget)

    return BudgetResponse.model_validate(budget)


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: int,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db)
):
    """
    Get a specific budget by ID.

    Only returns budget if it belongs to the user's household.
    """
    user, household = user_household

    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.household_id == household.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    return BudgetResponse.model_validate(budget)


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: int,
    data: UpdateBudgetRequest,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db)
):
    """
    Update an existing budget.

    Only allows updating budgets that belong to the user's household.
    If emoji is changed, validates uniqueness within household.
    """
    user, household = user_household

    # Find budget (household-scoped)
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.household_id == household.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    # Check if emoji is being changed and if it conflicts
    if data.emoji is not None and data.emoji != budget.emoji:
        existing_budget = db.query(Budget).filter(
            Budget.household_id == household.id,
            Budget.emoji == data.emoji,
            Budget.id != budget_id
        ).first()

        if existing_budget:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Budget with emoji '{data.emoji}' already exists in this household"
            )

        budget.emoji = data.emoji

    # Update fields if provided
    if data.label is not None:
        budget.label = data.label

    if data.monthly_amount is not None:
        budget.monthly_amount = data.monthly_amount

    budget.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(budget)

    return BudgetResponse.model_validate(budget)


@router.delete("/{budget_id}", response_model=DeleteBudgetResponse)
async def delete_budget(
    budget_id: int,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db)
):
    """
    Delete a budget.

    Only allows deleting budgets that belong to the user's household.
    Note: This will cascade delete all ledger entries for this budget.
    """
    user, household = user_household

    # Find budget (household-scoped)
    budget = db.query(Budget).filter(
        Budget.id == budget_id,
        Budget.household_id == household.id
    ).first()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )

    db.delete(budget)
    db.commit()

    return DeleteBudgetResponse()
