"""API routes - All endpoint definitions"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from uuid import UUID
from typing import List, Tuple

from app.database import get_db
from app.models.ledger import LedgerEntry
from app.models.user import User
from app.models.household import Household
from app.models.settings import Settings as SettingsModel
from app.schemas.ledger import (
    MakeSpendingRequest,
    MakeSpendingResponse,
    LedgerEntryResponse,
    UndoSpendingResponse,
)
from app.schemas.budget import (
    MonthlyBudgetsResponse,
    AmountsResponse,
)
from app.schemas.category import CategoryMapResponse
from app.schemas.settings import (
    SyncSettingsRequest,
    SyncSettingsResponse,
    CheckAutomationsResponse,
    ArchiveYearResponse,
)
from app.dependencies.auth import get_current_user_and_household
from app.services.categorization_service import get_or_create_category
from app.services.ledger_service import (
    get_amounts_for_current_year,
    get_ledger_for_month,
    get_category_map,
    delete_ledger_entry,
    export_year_as_csv,
)
from app.services.budget_service import get_all_budgets
from app.services.automation_service import check_and_run_monthly_automation, archive_year
from app.api.auth import router as auth_router
from app.api.household import router as household_router
from app.api.budgets import router as budgets_router
from app.api.subscriptions import router as subscriptions_router

router = APIRouter()

router.include_router(auth_router)
router.include_router(household_router)
router.include_router(budgets_router)
router.include_router(subscriptions_router)


# ============================================================================
# Core Data Endpoints
# ============================================================================

@router.get("/amounts", response_model=AmountsResponse)
def get_amounts(
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Get total amount left per budget for current year (household-scoped)."""
    _, household = user_household
    budgets = get_amounts_for_current_year(db, household.id)
    return AmountsResponse(budgets=budgets)


@router.get("/monthly_budgets", response_model=MonthlyBudgetsResponse)
def get_monthly_budgets(
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Get monthly increment amounts per budget (household-scoped)."""
    _, household = user_household
    budgets = get_all_budgets(db, household.id)
    return MonthlyBudgetsResponse(budgets=budgets)


@router.get("/ledger", response_model=List[LedgerEntryResponse])
def get_ledger(
    month: str = None,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """
    Get spending history for the specified month (household-scoped).

    Args:
        month: "YYYY-MM" (defaults to current month)
    """
    _, household = user_household

    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        return get_ledger_for_month(db, household.id, month)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")


@router.get("/category_map", response_model=CategoryMapResponse)
def get_category_breakdown(
    month: str = None,
    budget_emoji: str = None,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Get category breakdown for pie chart (household-scoped)."""
    _, household = user_household

    if budget_emoji is None:
        raise HTTPException(status_code=400, detail="budget_emoji parameter is required")

    if month is None:
        month = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        categories = get_category_map(db, household.id, month, budget_emoji)
        return CategoryMapResponse(categories=categories)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")


# ============================================================================
# Spending Management
# ============================================================================

@router.post("/make_spending", response_model=MakeSpendingResponse)
async def make_spending(
    request: MakeSpendingRequest,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Log a new spending with AI categorization, scoped to the household."""
    _, household = user_household

    category = await get_or_create_category(request.description_text or "", db)

    dt = request.spent_at or datetime.now(timezone.utc)

    entry = LedgerEntry(
        household_id=household.id,
        amount=request.amount,
        currency=request.currency,
        budget_emoji=request.budget_emoji,
        datetime=dt,
        description_text=request.description_text,
        category=category,
        year=dt.year,
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return MakeSpendingResponse(
        uuid=entry.uuid,
        category=category,
        success=True,
    )


@router.delete("/undo_spending/{entry_uuid}", response_model=UndoSpendingResponse)
def undo_spending(
    entry_uuid: UUID,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Remove a ledger entry by UUID, only if it belongs to this household."""
    _, household = user_household

    if not delete_ledger_entry(db, household.id, entry_uuid):
        raise HTTPException(status_code=404, detail="Ledger entry not found")

    return UndoSpendingResponse(
        success=True,
        message="Spending entry deleted successfully",
    )


# ============================================================================
# Configuration Sync
# ============================================================================

@router.post("/sync_settings", response_model=SyncSettingsResponse)
def sync_settings_endpoint(
    request: SyncSettingsRequest,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Upsert per-household settings (currency symbol)."""
    _, household = user_household

    settings = db.query(SettingsModel).filter_by(household_id=household.id).first()

    if settings:
        settings.currency_symbol = request.currency_symbol
    else:
        db.add(SettingsModel(
            household_id=household.id,
            currency_symbol=request.currency_symbol,
        ))

    db.commit()
    return SyncSettingsResponse(success=True)


# ============================================================================
# Automations
# ============================================================================

@router.post("/check_automations", response_model=CheckAutomationsResponse)
def check_automations(
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """
    Run this household's monthly budget addition if it hasn't run this month.

    Called by frontend on every app launch.
    """
    _, household = user_household
    ran, update_date, message = check_and_run_monthly_automation(db, household.id)

    return CheckAutomationsResponse(
        monthly_update_ran=ran,
        monthly_update_date=update_date,
        message=message,
    )


# ============================================================================
# Year-End Export
# ============================================================================

@router.get("/export_year")
def export_year(
    year: int,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Export this household's ledger entries for a year as CSV."""
    _, household = user_household
    csv_content = export_year_as_csv(db, household.id, year)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=tuppence_ledger_{year}.csv"
        },
    )


@router.post("/archive_year", response_model=ArchiveYearResponse)
def archive_year_endpoint(
    year: int,
    user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
    db: Session = Depends(get_db),
):
    """Mark this household's year as archived (after frontend exports CSV)."""
    _, household = user_household
    success = archive_year(db, household.id, year)

    return ArchiveYearResponse(success=success, year=year)


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "service": "tuppence-backend"}
