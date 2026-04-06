"""API routes - All endpoint definitions"""

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from uuid import UUID
from typing import List

from app.database import get_db
from app.models.ledger import LedgerEntry
from app.models.settings import Settings as SettingsModel
from app.schemas.ledger import (
    MakeSpendingRequest,
    MakeSpendingResponse,
    LedgerEntryResponse,
    UndoSpendingResponse
)
from app.schemas.budget import (
    SyncBudgetsRequest,
    SyncBudgetsResponse,
    MonthlyBudgetsResponse,
    AmountsResponse,
    BudgetItem
)
from app.schemas.category import CategoryMapResponse
from app.schemas.settings import (
    SyncSettingsRequest,
    SyncSettingsResponse,
    CheckAutomationsResponse,
    ArchiveYearResponse
)
from app.services.categorization_service import get_or_create_category
from app.services.ledger_service import (
    get_amounts_for_current_year,
    get_ledger_for_month,
    get_category_map,
    delete_ledger_entry,
    export_year_as_csv
)
from app.services.budget_service import sync_budgets, get_all_budgets
from app.services.automation_service import check_and_run_monthly_automation, archive_year
from app.api.auth import router as auth_router
from app.api.household import router as household_router

router = APIRouter()

# Include auth and household routes
router.include_router(auth_router)
router.include_router(household_router)


# ============================================================================
# Core Data Endpoints
# ============================================================================

@router.get("/amounts", response_model=AmountsResponse)
def get_amounts(db: Session = Depends(get_db)):
    """
    Get total amount left per budget for current year.

    Returns list of budgets with their total amounts (derived from ledger).
    """
    budgets = get_amounts_for_current_year(db)
    return AmountsResponse(budgets=budgets)


@router.get("/monthly_budgets", response_model=MonthlyBudgetsResponse)
def get_monthly_budgets(db: Session = Depends(get_db)):
    """
    Get monthly increment amounts per budget.

    Returns list of budgets with their monthly amounts.
    """
    budgets = get_all_budgets(db)
    return MonthlyBudgetsResponse(budgets=budgets)


@router.get("/ledger", response_model=List[LedgerEntryResponse])
def get_ledger(
    month: str = None,
    db: Session = Depends(get_db)
):
    """
    Get spending history for specified month.

    Args:
        month: Month in format "YYYY-MM" (defaults to current month)

    Returns:
        List of ledger entries ordered by datetime DESC
    """
    if month is None:
        # Default to current month
        now = datetime.now(timezone.utc)
        month = now.strftime("%Y-%m")

    try:
        entries = get_ledger_for_month(db, month)
        return entries
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")


@router.get("/category_map", response_model=CategoryMapResponse)
def get_category_breakdown(
    month: str = None,
    budget_emoji: str = None,
    db: Session = Depends(get_db)
):
    """
    Get category breakdown for pie chart.

    Args:
        month: Month in format "YYYY-MM" (defaults to current month)
        budget_emoji: Budget emoji to filter by (required)

    Returns:
        List of categories with totals, colors, and texts
    """
    if budget_emoji is None:
        raise HTTPException(status_code=400, detail="budget_emoji parameter is required")

    if month is None:
        # Default to current month
        now = datetime.now(timezone.utc)
        month = now.strftime("%Y-%m")

    try:
        categories = get_category_map(db, month, budget_emoji)
        return CategoryMapResponse(categories=categories)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")


# ============================================================================
# Spending Management
# ============================================================================

@router.post("/make_spending", response_model=MakeSpendingResponse)
async def make_spending(
    request: MakeSpendingRequest,
    db: Session = Depends(get_db)
):
    """
    Log new spending with AI categorization.

    Process:
    1. Round amount to integer (already expected from frontend)
    2. Get category via AI (with caching)
    3. Insert into ledger
    4. Return UUID and category

    Args:
        request: Spending details

    Returns:
        UUID, category, and success flag
    """
    # Get category (with caching)
    category = await get_or_create_category(request.description_text or "", db)

    # Determine year
    dt = request.datetime or datetime.now(timezone.utc)
    year = dt.year

    # Create ledger entry
    entry = LedgerEntry(
        amount=request.amount,
        currency=request.currency,
        budget_emoji=request.budget_emoji,
        datetime=dt,
        description_text=request.description_text,
        category=category,
        year=year
    )

    db.add(entry)
    db.commit()
    db.refresh(entry)

    return MakeSpendingResponse(
        uuid=entry.uuid,
        category=category,
        success=True
    )


@router.delete("/undo_spending/{entry_uuid}", response_model=UndoSpendingResponse)
def undo_spending(
    entry_uuid: UUID,
    db: Session = Depends(get_db)
):
    """
    Remove ledger entry by UUID.

    Args:
        entry_uuid: UUID of entry to delete

    Returns:
        Success flag and message
    """
    success = delete_ledger_entry(db, entry_uuid)

    if not success:
        raise HTTPException(status_code=404, detail="Ledger entry not found")

    return UndoSpendingResponse(
        success=True,
        message="Spending entry deleted successfully"
    )


# ============================================================================
# Configuration Sync
# ============================================================================

@router.post("/sync_budgets", response_model=SyncBudgetsResponse)
def sync_budgets_endpoint(
    request: SyncBudgetsRequest,
    db: Session = Depends(get_db)
):
    """
    Sync budgets from iOS Settings.

    Upserts budgets (adds new, updates existing).

    Args:
        request: List of budget items

    Returns:
        Success flag and count of synced budgets
    """
    synced_count = sync_budgets(db, request.budgets)

    return SyncBudgetsResponse(
        success=True,
        synced_count=synced_count
    )


@router.post("/sync_settings", response_model=SyncSettingsResponse)
def sync_settings_endpoint(
    request: SyncSettingsRequest,
    db: Session = Depends(get_db)
):
    """
    Sync settings from iOS.

    Updates or creates settings row (id=1).

    Args:
        request: Settings data

    Returns:
        Success flag
    """
    settings = db.query(SettingsModel).filter_by(id=1).first()

    if settings:
        settings.currency_symbol = request.currency_symbol
    else:
        settings = SettingsModel(
            id=1,
            currency_symbol=request.currency_symbol
        )
        db.add(settings)

    db.commit()

    return SyncSettingsResponse(success=True)


# ============================================================================
# Automations
# ============================================================================

@router.post("/check_automations", response_model=CheckAutomationsResponse)
def check_automations(db: Session = Depends(get_db)):
    """
    Check and run monthly automation if needed.

    Called by frontend on app open. Adds monthly budget amounts if:
    - Today is 1st of month
    - Last update date != today

    Returns:
        Whether update ran, date, and message
    """
    ran, update_date, message = check_and_run_monthly_automation(db)

    return CheckAutomationsResponse(
        monthly_update_ran=ran,
        monthly_update_date=update_date,
        message=message
    )


# ============================================================================
# Year-End Export
# ============================================================================

@router.get("/export_year")
def export_year(
    year: int,
    db: Session = Depends(get_db)
):
    """
    Export all ledger entries for a year as CSV.

    Args:
        year: Year to export (e.g., 2025)

    Returns:
        CSV file for download
    """
    csv_content = export_year_as_csv(db, year)

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=tuppence_ledger_{year}.csv"
        }
    )


@router.post("/archive_year", response_model=ArchiveYearResponse)
def archive_year_endpoint(
    year: int,
    db: Session = Depends(get_db)
):
    """
    Mark year as archived.

    Called after frontend successfully exports CSV.

    Args:
        year: Year to archive

    Returns:
        Success flag and year
    """
    success = archive_year(db, year)

    return ArchiveYearResponse(
        success=success,
        year=year
    )


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
def health_check():
    """Simple health check endpoint"""
    return {"status": "ok", "service": "tuppence-backend"}
