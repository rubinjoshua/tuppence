"""FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.api.routes import router


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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (iOS app, web clients)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
