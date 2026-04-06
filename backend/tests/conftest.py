"""Pytest configuration and fixtures"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

# Mock init_db before importing app to prevent database initialization
with patch('app.database.init_db'):
    from app.main import app

from app.database import Base, get_db
from app.models import *  # Import all models


# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    """Create test client with database override and disabled rate limiting"""
    from app.database import SessionLocal as _SessionLocal

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_session_local():
        """Override SessionLocal for middleware to use test database"""
        return db

    # Disable rate limiting for tests
    app.state.limiter.enabled = False

    # Clear rate limiter storage to prevent cross-test contamination
    if hasattr(app.state.limiter, '_storage'):
        app.state.limiter._storage.reset()

    # Override both get_db and SessionLocal for middleware
    app.dependency_overrides[get_db] = override_get_db

    # Patch SessionLocal in middleware module
    import app.middleware.database_isolation as mid_module
    original_session_local = mid_module.SessionLocal
    mid_module.SessionLocal = override_session_local

    with TestClient(app) as test_client:
        yield test_client

    # Restore everything
    app.dependency_overrides.clear()
    mid_module.SessionLocal = original_session_local
    app.state.limiter.enabled = True


@pytest.fixture(scope="function")
def sample_budgets():
    """Sample budget data for testing"""
    return [
        {"emoji": "🛒", "label": "Groceries", "monthly_amount": 500},
        {"emoji": "✈️", "label": "Travel", "monthly_amount": 1000},
        {"emoji": "🎬", "label": "Entertainment", "monthly_amount": 200},
    ]
