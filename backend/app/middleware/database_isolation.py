"""Database isolation middleware for multi-tenant Row-Level Security (RLS)"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Optional
from uuid import UUID

from app.utils.auth import validate_session
from app.database import SessionLocal


class DatabaseIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware to validate session and extract user context for multi-tenancy.

    The actual PostgreSQL session variable is set in get_db_with_rls() dependency.
    This ensures the variable is set on the same session the endpoint uses.

    How it works:
    1. Middleware validates session UUID from Authorization header
    2. Looks up session in database (validates expiration)
    3. Updates last_activity and extends expiration (sliding window)
    4. Stores user_id and household_id in request.state
    5. get_db_with_rls() dependency reads request.state values
    6. Dependency sets PostgreSQL session variables
    7. RLS policies use variables to filter data

    Security:
    - Immediate revocation: Delete session → instant 401
    - Sliding expiration: Active sessions auto-extend 30 days
    - Session variable scoped to current database connection
    - RLS policies enforced at database level (even if app has bugs)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        """
        Validate session and store user context in request state.
        """
        user_context = self._validate_and_extract_session(request)

        if user_context:
            user_id, household_id = user_context
            request.state.user_id = str(user_id)
            request.state.household_id = str(household_id)
        else:
            request.state.user_id = None
            request.state.household_id = None

        # Process request
        response = await call_next(request)
        return response

    def _validate_and_extract_session(self, request: Request) -> Optional[tuple]:
        """
        Validate session UUID from Authorization header and return user context.

        Returns:
            Tuple of (user_id UUID, household_id UUID) if session is valid,
            None otherwise.

        Side effects:
            - Updates session last_activity in database
            - Extends session expiration (sliding window)
        """
        # Get Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        # Parse Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        session_id_str = parts[1]

        # Parse UUID
        try:
            session_id = UUID(session_id_str)
        except ValueError:
            return None

        # Validate session in database
        # Create database session for this request
        db = SessionLocal()
        try:
            result = validate_session(db, session_id)
            return result  # Returns (user_id, household_id) or None
        finally:
            db.close()
