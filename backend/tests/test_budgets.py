"""Tests for budget API endpoints"""

import pytest
from datetime import datetime, timezone

from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.models.budget import Budget
from app.models.session import Session


@pytest.fixture
def auth_headers(client, db):
    """Create authenticated user and return auth headers"""
    # Create user
    user = User(
        email="test@example.com",
        password_hash="hashed_password",
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    db.flush()

    # Create household
    household = Household(name="Test Household")
    db.add(household)
    db.flush()

    # Add user to household as owner
    membership = HouseholdMember(
        household_id=household.id,
        user_id=user.id,
        role="owner"
    )
    db.add(membership)
    db.flush()

    # Create session
    from datetime import timedelta
    session = Session(
        user_id=user.id,
        household_id=household.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(session)
    db.commit()

    return {
        "Authorization": f"Bearer {session.id}",
        "user": user,
        "household": household,
        "session": session
    }


@pytest.fixture
def second_household(client, db, auth_headers):
    """Create a second household with a different user"""
    # Create second user
    user2 = User(
        email="user2@example.com",
        password_hash="hashed_password",
        full_name="User Two",
        is_active=True
    )
    db.add(user2)
    db.flush()

    # Create second household
    household2 = Household(name="Second Household")
    db.add(household2)
    db.flush()

    # Add user2 to household2 as owner
    membership2 = HouseholdMember(
        household_id=household2.id,
        user_id=user2.id,
        role="owner"
    )
    db.add(membership2)
    db.flush()

    # Create session for user2
    from datetime import timedelta
    session2 = Session(
        user_id=user2.id,
        household_id=household2.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db.add(session2)
    db.commit()

    return {
        "household": household2,
        "user": user2,
        "session": session2,
        "headers": {"Authorization": f"Bearer {session2.id}"}
    }


class TestListBudgets:
    """Test GET /budgets"""

    def test_list_budgets_empty(self, client, auth_headers):
        """List budgets when none exist"""
        response = client.get("/budgets", headers={"Authorization": auth_headers["Authorization"]})

        assert response.status_code == 200
        data = response.json()
        assert data["budgets"] == []

    def test_list_budgets_with_data(self, client, db, auth_headers):
        """List budgets when budgets exist"""
        household = auth_headers["household"]

        # Create test budgets
        budget1 = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        budget2 = Budget(
            household_id=household.id,
            emoji="✈️",
            label="Travel",
            monthly_amount=1000
        )
        db.add_all([budget1, budget2])
        db.commit()

        response = client.get("/budgets", headers={"Authorization": auth_headers["Authorization"]})

        assert response.status_code == 200
        data = response.json()
        assert len(data["budgets"]) == 2
        assert data["budgets"][0]["emoji"] == "🛒"
        assert data["budgets"][0]["label"] == "Groceries"
        assert data["budgets"][0]["monthly_amount"] == 500

    def test_list_budgets_household_isolation(self, client, db, auth_headers, second_household):
        """Verify budgets are isolated per household"""
        household1 = auth_headers["household"]
        household2 = second_household["household"]

        # Create budget for household 1
        budget1 = Budget(
            household_id=household1.id,
            emoji="🛒",
            label="Groceries H1",
            monthly_amount=500
        )
        # Create budget for household 2
        budget2 = Budget(
            household_id=household2.id,
            emoji="🛒",
            label="Groceries H2",
            monthly_amount=600
        )
        db.add_all([budget1, budget2])
        db.commit()

        # User 1 should only see their household's budget
        response = client.get("/budgets", headers={"Authorization": auth_headers["Authorization"]})
        assert response.status_code == 200
        data = response.json()
        assert len(data["budgets"]) == 1
        assert data["budgets"][0]["label"] == "Groceries H1"

        # User 2 should only see their household's budget
        response = client.get("/budgets", headers=second_household["headers"])
        assert response.status_code == 200
        data = response.json()
        assert len(data["budgets"]) == 1
        assert data["budgets"][0]["label"] == "Groceries H2"

    def test_list_budgets_unauthorized(self, client):
        """List budgets without authentication"""
        response = client.get("/budgets")
        assert response.status_code == 401  # HTTPBearer returns 401 for missing auth


class TestCreateBudget:
    """Test POST /budgets"""

    def test_create_budget_success(self, client, auth_headers):
        """Create a new budget"""
        budget_data = {
            "emoji": "🛒",
            "label": "Groceries",
            "monthly_amount": 500
        }

        response = client.post(
            "/budgets",
            json=budget_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["emoji"] == "🛒"
        assert data["label"] == "Groceries"
        assert data["monthly_amount"] == 500
        assert "id" in data
        assert "household_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_budget_duplicate_emoji(self, client, db, auth_headers):
        """Cannot create budget with duplicate emoji in same household"""
        household = auth_headers["household"]

        # Create first budget
        budget1 = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget1)
        db.commit()

        # Try to create duplicate
        budget_data = {
            "emoji": "🛒",
            "label": "Shopping",
            "monthly_amount": 600
        }

        response = client.post(
            "/budgets",
            json=budget_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_create_budget_duplicate_emoji_different_household(self, client, db, auth_headers, second_household):
        """Can create budget with same emoji in different household"""
        household1 = auth_headers["household"]

        # Create budget in household 1
        budget1 = Budget(
            household_id=household1.id,
            emoji="🛒",
            label="Groceries H1",
            monthly_amount=500
        )
        db.add(budget1)
        db.commit()

        # Create same emoji in household 2 (should succeed)
        budget_data = {
            "emoji": "🛒",
            "label": "Groceries H2",
            "monthly_amount": 600
        }

        response = client.post(
            "/budgets",
            json=budget_data,
            headers=second_household["headers"]
        )

        assert response.status_code == 201
        data = response.json()
        assert data["emoji"] == "🛒"
        assert data["label"] == "Groceries H2"

    def test_create_budget_invalid_amount(self, client, auth_headers):
        """Cannot create budget with zero or negative amount"""
        budget_data = {
            "emoji": "🛒",
            "label": "Groceries",
            "monthly_amount": 0
        }

        response = client.post(
            "/budgets",
            json=budget_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 422  # Validation error

    def test_create_budget_unauthorized(self, client):
        """Cannot create budget without authentication"""
        budget_data = {
            "emoji": "🛒",
            "label": "Groceries",
            "monthly_amount": 500
        }

        response = client.post("/budgets", json=budget_data)
        assert response.status_code == 401


class TestGetBudget:
    """Test GET /budgets/{budget_id}"""

    def test_get_budget_success(self, client, db, auth_headers):
        """Get a specific budget"""
        household = auth_headers["household"]

        budget = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()
        budget_id = budget.id  # Store ID before potential detachment

        response = client.get(
            f"/budgets/{budget_id}",
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == budget_id
        assert data["emoji"] == "🛒"

    def test_get_budget_not_found(self, client, auth_headers):
        """Get non-existent budget"""
        response = client.get(
            "/budgets/99999",
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 404

    def test_get_budget_wrong_household(self, client, db, auth_headers, second_household):
        """Cannot get budget from different household"""
        household2 = second_household["household"]

        # Create budget in household 2
        budget = Budget(
            household_id=household2.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()

        # Try to access with household 1 credentials
        response = client.get(
            f"/budgets/{budget.id}",
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 404  # Not found (household isolation)


class TestUpdateBudget:
    """Test PUT /budgets/{budget_id}"""

    def test_update_budget_label(self, client, db, auth_headers):
        """Update budget label"""
        household = auth_headers["household"]

        budget = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()

        update_data = {"label": "Food Shopping"}

        response = client.put(
            f"/budgets/{budget.id}",
            json=update_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "Food Shopping"
        assert data["emoji"] == "🛒"  # Unchanged
        assert data["monthly_amount"] == 500  # Unchanged

    def test_update_budget_amount(self, client, db, auth_headers):
        """Update budget amount"""
        household = auth_headers["household"]

        budget = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()

        update_data = {"monthly_amount": 750}

        response = client.put(
            f"/budgets/{budget.id}",
            json=update_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["monthly_amount"] == 750

    def test_update_budget_emoji(self, client, db, auth_headers):
        """Update budget emoji"""
        household = auth_headers["household"]

        budget = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()

        update_data = {"emoji": "🍎"}

        response = client.put(
            f"/budgets/{budget.id}",
            json=update_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["emoji"] == "🍎"

    def test_update_budget_emoji_conflict(self, client, db, auth_headers):
        """Cannot update emoji to one that already exists"""
        household = auth_headers["household"]

        budget1 = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        budget2 = Budget(
            household_id=household.id,
            emoji="✈️",
            label="Travel",
            monthly_amount=1000
        )
        db.add_all([budget1, budget2])
        db.commit()

        # Try to change budget2's emoji to match budget1
        update_data = {"emoji": "🛒"}

        response = client.put(
            f"/budgets/{budget2.id}",
            json=update_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()

    def test_update_budget_not_found(self, client, auth_headers):
        """Update non-existent budget"""
        update_data = {"label": "New Label"}

        response = client.put(
            "/budgets/99999",
            json=update_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 404

    def test_update_budget_wrong_household(self, client, db, auth_headers, second_household):
        """Cannot update budget from different household"""
        household2 = second_household["household"]

        budget = Budget(
            household_id=household2.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()

        update_data = {"label": "Hacked"}

        response = client.put(
            f"/budgets/{budget.id}",
            json=update_data,
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 404


class TestDeleteBudget:
    """Test DELETE /budgets/{budget_id}"""

    def test_delete_budget_success(self, client, db, auth_headers):
        """Delete a budget"""
        household = auth_headers["household"]

        budget = Budget(
            household_id=household.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()
        budget_id = budget.id

        response = client.delete(
            f"/budgets/{budget_id}",
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify budget is deleted
        deleted_budget = db.query(Budget).filter(Budget.id == budget_id).first()
        assert deleted_budget is None

    def test_delete_budget_not_found(self, client, auth_headers):
        """Delete non-existent budget"""
        response = client.delete(
            "/budgets/99999",
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 404

    def test_delete_budget_wrong_household(self, client, db, auth_headers, second_household):
        """Cannot delete budget from different household"""
        household2 = second_household["household"]

        budget = Budget(
            household_id=household2.id,
            emoji="🛒",
            label="Groceries",
            monthly_amount=500
        )
        db.add(budget)
        db.commit()
        budget_id = budget.id  # Store ID before potential detachment

        response = client.delete(
            f"/budgets/{budget_id}",
            headers={"Authorization": auth_headers["Authorization"]}
        )

        assert response.status_code == 404

        # Verify budget still exists
        budget = db.query(Budget).filter(Budget.id == budget_id).first()
        assert budget is not None
