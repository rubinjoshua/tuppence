"""Household management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import secrets

from app.database import get_db
from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.models.sharing_token import SharingToken
from app.schemas.household import (
    CreateHouseholdRequest,
    UpdateHouseholdRequest,
    GenerateSharingTokenRequest,
    JoinHouseholdRequest,
    HouseholdDetailResponse,
    HouseholdMemberResponse,
    SharingTokenResponse,
    ListHouseholdsResponse,
    JoinHouseholdResponse,
    LeaveHouseholdResponse,
    DeleteHouseholdResponse,
    DisconnectAndMigrateRequest,
    DisconnectAndMigrateResponse,
)
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/households", tags=["households"])


def generate_secure_token() -> str:
    """
    Generate cryptographically secure sharing token.

    Returns 32-byte (256-bit) random token as 64-char hex string.
    """
    return secrets.token_hex(32)  # 32 bytes = 64 hex chars


@router.get("", response_model=ListHouseholdsResponse)
async def list_households(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all households the current user belongs to.
    """
    memberships = db.query(HouseholdMember).filter(
        HouseholdMember.user_id == user.id
    ).all()

    households = []
    for membership in memberships:
        household = db.query(Household).filter(Household.id == membership.household_id).first()
        if not household:
            continue

        # Get all members of this household
        all_members = db.query(HouseholdMember).filter(
            HouseholdMember.household_id == household.id
        ).all()

        members = []
        for member in all_members:
            member_user = db.query(User).filter(User.id == member.user_id).first()
            if member_user:
                members.append(HouseholdMemberResponse(
                    user_id=member_user.id,
                    email=member_user.email,
                    full_name=member_user.full_name,
                    role=member.role,
                    joined_at=member.joined_at
                ))

        households.append(HouseholdDetailResponse(
            id=household.id,
            name=household.name,
            role=membership.role,
            created_at=household.created_at,
            member_count=len(members),
            members=members
        ))

    return ListHouseholdsResponse(households=households)


@router.post("", response_model=HouseholdDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_household(
    data: CreateHouseholdRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new household with current user as owner.
    """
    # Create household
    household = Household(name=data.name)
    db.add(household)
    db.flush()

    # Add user as owner
    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)
    db.commit()
    db.refresh(household)

    return HouseholdDetailResponse(
        id=household.id,
        name=household.name,
        role="owner",
        created_at=household.created_at,
        member_count=1,
        members=[HouseholdMemberResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            role="owner",
            joined_at=membership.joined_at
        )]
    )


@router.get("/{household_id}", response_model=HouseholdDetailResponse)
async def get_household(
    household_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get household details by ID.
    """
    # Verify user is member of household
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this household"
        )

    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Get all members
    all_members = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household.id
    ).all()

    members = []
    for member in all_members:
        member_user = db.query(User).filter(User.id == member.user_id).first()
        if member_user:
            members.append(HouseholdMemberResponse(
                user_id=member_user.id,
                email=member_user.email,
                full_name=member_user.full_name,
                role=member.role,
                joined_at=member.joined_at
            ))

    return HouseholdDetailResponse(
        id=household.id,
        name=household.name,
        role=membership.role,
        created_at=household.created_at,
        member_count=len(members),
        members=members
    )


@router.patch("/{household_id}", response_model=HouseholdDetailResponse)
async def update_household(
    household_id: str,
    data: UpdateHouseholdRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update household name (owner only).
    """
    # Verify user is owner of household
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == user.id,
        HouseholdMember.role == "owner"
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household owner can update name"
        )

    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    household.name = data.name
    household.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(household)

    # Get all members
    all_members = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household.id
    ).all()

    members = []
    for member in all_members:
        member_user = db.query(User).filter(User.id == member.user_id).first()
        if member_user:
            members.append(HouseholdMemberResponse(
                user_id=member_user.id,
                email=member_user.email,
                full_name=member_user.full_name,
                role=member.role,
                joined_at=member.joined_at
            ))

    return HouseholdDetailResponse(
        id=household.id,
        name=household.name,
        role=membership.role,
        created_at=household.created_at,
        member_count=len(members),
        members=members
    )


@router.post("/{household_id}/share-token", response_model=SharingTokenResponse)
async def generate_sharing_token(
    household_id: str,
    data: GenerateSharingTokenRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a sharing token for household (owner only).

    Token allows other users to join this household.
    Tokens expire after specified days (default 7, max 30).
    """
    # Verify user is owner of household
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == user.id,
        HouseholdMember.role == "owner"
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household owner can generate sharing tokens"
        )

    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Generate cryptographically secure token
    token = generate_secure_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    # Store token
    sharing_token = SharingToken(
        household_id=household.id,
        token=token,
        created_by=user.id,
        expires_at=expires_at
    )
    db.add(sharing_token)
    db.commit()
    db.refresh(sharing_token)

    return SharingTokenResponse(
        token=token,
        expires_at=expires_at,
        created_at=sharing_token.created_at
    )


@router.post("/join", response_model=JoinHouseholdResponse)
async def join_household(
    data: JoinHouseholdRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Join a household using a sharing token.

    Validates token and adds user as member.
    """
    # Find token
    sharing_token = db.query(SharingToken).filter(
        SharingToken.token == data.token,
        SharingToken.is_active == True
    ).first()

    if not sharing_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or inactive sharing token"
        )

    # Check if token is expired
    if sharing_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sharing token has expired"
        )

    # Check if token has been used
    if sharing_token.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sharing token has already been used"
        )

    # Check if user is already a member
    existing_membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == sharing_token.household_id,
        HouseholdMember.user_id == user.id
    ).first()

    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already a member of this household"
        )

    # Add user as member
    membership = HouseholdMember(
        household_id=sharing_token.household_id,
        user_id=user.id,
        role="member"
    )
    db.add(membership)

    # Mark token as used
    sharing_token.used_at = datetime.now(timezone.utc)
    sharing_token.used_by = user.id

    db.commit()

    # Get household details
    household = db.query(Household).filter(Household.id == sharing_token.household_id).first()

    # Get all members
    all_members = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household.id
    ).all()

    members = []
    for member in all_members:
        member_user = db.query(User).filter(User.id == member.user_id).first()
        if member_user:
            members.append(HouseholdMemberResponse(
                user_id=member_user.id,
                email=member_user.email,
                full_name=member_user.full_name,
                role=member.role,
                joined_at=member.joined_at
            ))

    return JoinHouseholdResponse(
        household=HouseholdDetailResponse(
            id=household.id,
            name=household.name,
            role="member",
            created_at=household.created_at,
            member_count=len(members),
            members=members
        )
    )


@router.post("/{household_id}/leave", response_model=LeaveHouseholdResponse)
async def leave_household(
    household_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Leave a household (members only, not owners).

    Owners must transfer ownership before leaving.
    """
    # Find membership
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not a member of this household"
        )

    # Prevent owner from leaving (must transfer ownership first)
    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owners cannot leave household. Transfer ownership or delete household first."
        )

    # Remove membership
    db.delete(membership)
    db.commit()

    return LeaveHouseholdResponse()


@router.delete("/{household_id}", response_model=DeleteHouseholdResponse)
async def delete_household(
    household_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a household (owner only).

    Deletes household and all associated data (cascading delete).
    """
    # Verify user is owner of household
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == user.id,
        HouseholdMember.role == "owner"
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only household owner can delete household"
        )

    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Delete household (cascades to members, ledger, budgets, etc.)
    db.delete(household)
    db.commit()

    return DeleteHouseholdResponse()


@router.post("/{household_id}/disconnect", response_model=DisconnectAndMigrateResponse)
async def disconnect_and_migrate(
    household_id: str,
    data: DisconnectAndMigrateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect from household and create new household.

    This is a "start fresh" operation for users who want to leave
    a shared household and create their own.

    Options:
    - Create new household with specified name
    - Optionally copy budgets and settings (not ledger data)
    - Remove user from old household
    - Make user owner of new household

    Note: Ledger data is never copied (fresh start).
    """
    from app.models.budget import Budget
    from app.models.settings import Settings as SettingsModel

    # Verify user is member of household
    membership = db.query(HouseholdMember).filter(
        HouseholdMember.household_id == household_id,
        HouseholdMember.user_id == user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not a member of this household"
        )

    old_household = db.query(Household).filter(Household.id == household_id).first()
    if not old_household:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Household not found"
        )

    # Prevent owner from using this endpoint (must delete household instead)
    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owners cannot disconnect. Transfer ownership, delete household, or leave household first."
        )

    # Create new household
    new_household = Household(name=data.new_household_name)
    db.add(new_household)
    db.flush()

    # Add user as owner of new household
    new_membership = HouseholdMember(
        household_id=new_household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(new_membership)
    db.flush()

    copied_items = {"budgets": 0, "settings": 0}

    # Copy data if requested
    if data.copy_data:
        # Copy budgets (budget definitions, not transactions)
        old_budgets = db.query(Budget).filter(Budget.household_id == household_id).all()
        for old_budget in old_budgets:
            new_budget = Budget(
                household_id=new_household.id,
                emoji=old_budget.emoji,
                monthly_amount=old_budget.monthly_amount,
                label=old_budget.label
            )
            db.add(new_budget)
            copied_items["budgets"] += 1

        # Copy settings
        old_settings = db.query(SettingsModel).filter(SettingsModel.household_id == household_id).first()
        if old_settings:
            new_settings = SettingsModel(
                household_id=new_household.id,
                currency_symbol=old_settings.currency_symbol
            )
            db.add(new_settings)
            copied_items["settings"] = 1

    # Remove user from old household
    db.delete(membership)

    db.commit()
    db.refresh(new_household)

    # Build response
    return DisconnectAndMigrateResponse(
        old_household_id=old_household.id,
        new_household=HouseholdDetailResponse(
            id=new_household.id,
            name=new_household.name,
            role="owner",
            created_at=new_household.created_at,
            member_count=1,
            members=[HouseholdMemberResponse(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role="owner",
                joined_at=new_membership.joined_at
            )]
        ),
        copied_items=copied_items if data.copy_data else None,
        message=f"Successfully disconnected from '{old_household.name}' and created '{new_household.name}'"
    )
