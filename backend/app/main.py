"""FastAPI application entry point"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import init_db
from app.api.routes import router
from app.middleware.database_isolation import DatabaseIsolationMiddleware

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Runs on startup:
    - Initialize database (create tables, seed data)

    Runs on shutdown:
    - Cleanup if needed
    """
    # Startup
    print("Initializing database...")
    init_db()
    print("Database initialized successfully")

    yield

    # Shutdown
    print("Shutting down...")


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
