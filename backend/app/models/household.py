"""Household models - multi-tenant budget groups"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime, timezone

from app.database import Base


class Household(Base):
    """
    Household table for multi-tenant budget groups.

    A household represents a shared budget group (family, roommates, etc.).
    Multiple users can belong to the same household.

    Schema:
        - id: Primary key (UUID)
        - name: Household display name
        - created_at: Creation timestamp
        - updated_at: Last update timestamp
    """

    __tablename__ = "households"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Household(id={self.id}, name={self.name})>"


class HouseholdMember(Base):
    """
    Household membership table (many-to-many: users <-> households).

    Tracks which users belong to which households and their role.

    Schema:
        - id: Primary key (UUID)
        - household_id: Foreign key to households
        - user_id: Foreign key to users
        - role: Member role ('owner' or 'member')
        - joined_at: Membership creation timestamp

    Roles:
        - owner: Can manage household, invite members, delete household
        - member: Can view/edit data, cannot manage members
    """

    __tablename__ = "household_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    household_id = Column(UUID(as_uuid=True), ForeignKey('households.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role = Column(String(50), nullable=False, default='member')
    joined_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        # Unique constraint: user can only be in household once
        {'schema': None},
    )

    def __repr__(self):
        return f"<HouseholdMember(user_id={self.user_id}, household_id={self.household_id}, role={self.role})>"
