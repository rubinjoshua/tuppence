"""API dependencies"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db


# Re-export get_db for convenience
def get_database() -> Session:
    """Get database session dependency"""
    return get_db()
