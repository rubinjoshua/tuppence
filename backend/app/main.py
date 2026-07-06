"""FastAPI application entry point"""

import asyncio

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db, SessionLocal
from app.api.routes import router
from app.middleware.database_isolation import DatabaseIsolationMiddleware
from app.limiter import limiter
from app.services.automation_service import run_monthly_automation_for_all


# Run monthly automation every hour. The automation itself is idempotent
# (per-household SELECT FOR UPDATE + secondary ledger-existence check),
# so an hourly cadence is just "check often, only act when stale".
_AUTOMATION_INTERVAL_SECONDS = 3600


async def _monthly_automation_loop():
    while True:
        try:
            db = SessionLocal()
            try:
                updated = run_monthly_automation_for_all(db)
                if updated:
                    print(f"Monthly automation: updated {updated} household(s)")
            finally:
                db.close()
        except Exception as exc:
            # Never let a transient DB error kill the loop. Sleep and retry.
            print(f"Monthly automation loop error: {exc}")
        await asyncio.sleep(_AUTOMATION_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Runs on startup:
    - Initialize database (create tables, seed data)
    - Spawn monthly-automation background task so monthly budgets are added
      automatically without depending on a client opening the app.

    Runs on shutdown:
    - Cancel background tasks
    """
    print("Initializing database...")
    init_db()
    print("Database initialized successfully")

    automation_task = asyncio.create_task(_monthly_automation_loop())

    yield

    print("Shutting down...")
    automation_task.cancel()
    try:
        await automation_task
    except asyncio.CancelledError:
        pass


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="FastAPI backend for Tuppence personal budgeting app with AI categorization",
    lifespan=lifespan
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS (must be added before other middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (iOS app, web clients)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add database isolation middleware (sets RLS session variable)
app.add_middleware(DatabaseIsolationMiddleware)

# Include API routes
app.include_router(router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "docs": "/docs"
    }
