"""Database setup and initialization"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool
import os

from app.config import settings

# Base class for all models
Base = declarative_base()

# Lazy engine creation - only create when needed
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine"""
    global _engine
    if _engine is None:
        # For testing, allow SQLite; for production, use PostgreSQL
        db_url = settings.DATABASE_URL
        connect_args = {}

        # SQLite specific settings
        if db_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}

        _engine = create_engine(
            db_url,
            echo=settings.DEBUG,
            pool_pre_ping=True,  # Verify connections before using
            connect_args=connect_args
        )
    return _engine


def get_session_local():
    """Get or create the session factory"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def SessionLocal():
    return get_session_local()()


def get_db() -> Session:
    """
    Database session dependency for FastAPI.

    Usage:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db here
            pass

    Yields:
        Session: Database session that automatically closes after request
    """
    session_local = get_session_local()
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def get_db_with_rls(request=None) -> Session:
    """
    Database session dependency with Row-Level Security (RLS) enabled.

    Sets PostgreSQL session variable `app.current_user_id` for RLS policies.
    This ensures users can only access data from households they belong to.

    Usage:
        from fastapi import Request

        @app.get("/endpoint")
        def endpoint(request: Request, db: Session = Depends(get_db_with_rls)):
            # db session has RLS variable set
            # Queries are automatically filtered by household membership
            pass

    Args:
        request: FastAPI Request object (automatically injected)

    Yields:
        Session: Database session with RLS variable set
    """
    from sqlalchemy import text
    from fastapi import Request

    session_local = get_session_local()
    db = session_local()

    try:
        # Get user_id from request state (set by DatabaseIsolationMiddleware)
        if request and hasattr(request, 'state') and hasattr(request.state, 'user_id'):
            user_id = request.state.user_id
            if user_id:
                # Set PostgreSQL session variable for RLS
                # Use parameterized query to prevent SQL injection
                db.execute(text("SET LOCAL app.current_user_id = :user_id"), {"user_id": str(user_id)})

        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize global seed data on application startup.

    Schema management lives in alembic — `alembic upgrade head` runs as part of
    container start (see nixpacks.toml) and is the authoritative source for
    table structure. `create_all` is still called here so a fresh dev DB
    (e.g. SQLite for tests) can boot without alembic; in production it's a
    harmless no-op because alembic already built everything.

    Settings is per-household and seeded lazily when a household first writes
    to `/sync_settings`, so we don't seed it here.

    Safe to call multiple times.
    """
    from app.models.category import Category
    from app.utils.categories import PREDEFINED_CATEGORIES
    from app.utils.colors import WES_ANDERSON_COLORS

    engine = get_engine()
    Base.metadata.create_all(bind=engine)

    session_local = get_session_local()
    db = session_local()
    try:
        if db.query(Category).count() == 0:
            print("Seeding categories...")
            for i, category_name in enumerate(PREDEFINED_CATEGORIES):
                color = WES_ANDERSON_COLORS[i % len(WES_ANDERSON_COLORS)]
                db.add(Category(category_name=category_name, hex_color=color))
            db.commit()
            print(f"Seeded {len(PREDEFINED_CATEGORIES)} categories")
    finally:
        db.close()
