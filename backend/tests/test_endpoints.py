"""Core endpoint tests - auth-gated and household-scoped."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import UUID

from app.models.user import User
from app.models.household import Household, HouseholdMember
from app.models.budget import Budget
from app.models.ledger import LedgerEntry
from app.models.session import Session


def _build_account(db, email: str, name: str):
    user = User(email=email, password_hash="x", full_name=name, is_active=True)
    db.add(user)
    db.flush()

    household = Household(name=f"{name}'s House")
    db.add(household)
    db.flush()

    db.add(HouseholdMember(household_id=household.id, user_id=user.id, role="owner"))
    db.flush()

    session = Session(
        user_id=user.id,
        household_id=household.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )
    db.add(session)
    db.commit()

    # Capture primitive IDs so tests can compare after the ORM session expires the instances.
    return {
        "user_id": user.id,
        "household_id": household.id,
        "session_id": session.id,
        "headers": {"Authorization": f"Bearer {session.id}"},
    }


@pytest.fixture
def alice(client, db):
    return _build_account(db, "alice@test.com", "Alice")


@pytest.fixture
def bob(client, db, alice):
    return _build_account(db, "bob@test.com", "Bob")


@pytest.fixture
def mock_categorizer(monkeypatch):
    async def mock_categorize(text, db):
        return "Groceries"

    from app.api import routes
    monkeypatch.setattr(routes, "get_or_create_category", mock_categorize)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "version" in response.json()


class TestAuthGating:
    """Every core endpoint must reject unauthenticated requests."""

    @pytest.mark.parametrize("method,path", [
        ("get", "/amounts"),
        ("get", "/monthly_budgets"),
        ("get", "/ledger"),
        ("get", "/category_map?budget_emoji=🛒"),
        ("post", "/make_spending"),
        ("delete", "/undo_spending/00000000-0000-0000-0000-000000000000"),
        ("post", "/sync_settings"),
        ("get", "/settings"),
        ("post", "/check_automations"),
        ("get", "/export_year?year=2026"),
        ("post", "/archive_year?year=2026"),
    ])
    def test_unauthenticated_rejected(self, client, method, path):
        response = getattr(client, method)(path) if method != "post" else client.post(path, json={})
        assert response.status_code == 401


class TestAmounts:
    def test_empty(self, client, alice):
        response = client.get("/amounts", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json() == {"budgets": []}

    def test_household_isolation(self, client, db, alice, bob):
        db.add_all([
            Budget(household_id=alice["household_id"], emoji="🛒", label="Alice Groc", monthly_amount=500),
            Budget(household_id=bob["household_id"], emoji="🛒", label="Bob Groc", monthly_amount=600),
        ])
        db.commit()

        alice_resp = client.get("/amounts", headers=alice["headers"]).json()
        bob_resp = client.get("/amounts", headers=bob["headers"]).json()

        assert len(alice_resp["budgets"]) == 1
        assert alice_resp["budgets"][0]["label"] == "Alice Groc"
        assert len(bob_resp["budgets"]) == 1
        assert bob_resp["budgets"][0]["label"] == "Bob Groc"


class TestMonthlyBudgets:
    def test_household_isolation(self, client, db, alice, bob):
        db.add(Budget(household_id=alice["household_id"], emoji="🛒", label="A", monthly_amount=500))
        db.add(Budget(household_id=bob["household_id"], emoji="✈️", label="B", monthly_amount=1000))
        db.commit()

        alice_resp = client.get("/monthly_budgets", headers=alice["headers"]).json()
        bob_resp = client.get("/monthly_budgets", headers=bob["headers"]).json()

        assert [b["emoji"] for b in alice_resp["budgets"]] == ["🛒"]
        assert [b["emoji"] for b in bob_resp["budgets"]] == ["✈️"]


class TestMakeSpending:
    def test_stamps_household_id(self, client, db, alice, mock_categorizer):
        db.add(Budget(household_id=alice["household_id"], emoji="🛒", label="Groceries", monthly_amount=500))
        db.commit()

        response = client.post(
            "/make_spending",
            json={"amount": -50, "currency": "USD", "budget_emoji": "🛒", "description_text": "milk"},
            headers=alice["headers"],
        )
        assert response.status_code == 200

        entry = db.query(LedgerEntry).first()
        assert entry.household_id == alice["household_id"]
        assert entry.amount == -50


class TestLedger:
    def test_household_isolation(self, client, db, alice, bob, mock_categorizer):
        client.post(
            "/make_spending",
            json={"amount": -10, "currency": "USD", "budget_emoji": "🛒", "description_text": "alice"},
            headers=alice["headers"],
        )
        client.post(
            "/make_spending",
            json={"amount": -20, "currency": "USD", "budget_emoji": "🛒", "description_text": "bob"},
            headers=bob["headers"],
        )

        alice_ledger = client.get("/ledger", headers=alice["headers"]).json()
        bob_ledger = client.get("/ledger", headers=bob["headers"]).json()

        assert len(alice_ledger) == 1
        assert alice_ledger[0]["description_text"] == "alice"
        assert len(bob_ledger) == 1
        assert bob_ledger[0]["description_text"] == "bob"


class TestUndoSpending:
    def test_cannot_delete_other_household_entry(self, client, db, alice, bob, mock_categorizer):
        """Critical security check: user B must not be able to delete user A's entry by UUID."""
        resp = client.post(
            "/make_spending",
            json={"amount": -10, "currency": "USD", "budget_emoji": "🛒", "description_text": "alice"},
            headers=alice["headers"],
        )
        entry_uuid = UUID(resp.json()["uuid"])

        bob_delete = client.delete(f"/undo_spending/{entry_uuid}", headers=bob["headers"])
        assert bob_delete.status_code == 404

        assert db.query(LedgerEntry).filter_by(uuid=entry_uuid).first() is not None

        alice_delete = client.delete(f"/undo_spending/{entry_uuid}", headers=alice["headers"])
        assert alice_delete.status_code == 200
        assert db.query(LedgerEntry).filter_by(uuid=entry_uuid).first() is None

    def test_unknown_uuid_404(self, client, alice):
        response = client.delete(
            "/undo_spending/00000000-0000-0000-0000-000000000000",
            headers=alice["headers"],
        )
        assert response.status_code == 404


class TestSyncSettings:
    def test_creates_then_updates_per_household(self, client, db, alice, bob):
        from app.models.settings import Settings

        client.post("/sync_settings", json={"currency_symbol": "$"}, headers=alice["headers"])
        client.post("/sync_settings", json={"currency_symbol": "€"}, headers=bob["headers"])

        alice_settings = db.query(Settings).filter_by(household_id=alice["household_id"]).first()
        bob_settings = db.query(Settings).filter_by(household_id=bob["household_id"]).first()
        assert alice_settings.currency_symbol == "$"
        assert bob_settings.currency_symbol == "€"

        # Update path
        client.post("/sync_settings", json={"currency_symbol": "₪"}, headers=alice["headers"])
        updated = db.query(Settings).filter_by(household_id=alice["household_id"]).first()
        assert updated.currency_symbol == "₪"

    def test_split_budget_options_roundtrip(self, client, alice):
        client.post(
            "/sync_settings",
            json={"currency_symbol": "$", "split_budget_options": ["🛒🦊", "🛒🦊🦩"]},
            headers=alice["headers"],
        )

        resp = client.get("/settings", headers=alice["headers"]).json()
        assert resp["currency_symbol"] == "$"
        assert resp["split_budget_options"] == ["🛒🦊", "🛒🦊🦩"]

    def test_split_budget_options_omitted_leaves_existing(self, client, alice):
        client.post(
            "/sync_settings",
            json={"currency_symbol": "$", "split_budget_options": ["🛒🦊"]},
            headers=alice["headers"],
        )
        # Omit the field — must not clobber the stored list.
        client.post(
            "/sync_settings",
            json={"currency_symbol": "€"},
            headers=alice["headers"],
        )
        resp = client.get("/settings", headers=alice["headers"]).json()
        assert resp["currency_symbol"] == "€"
        assert resp["split_budget_options"] == ["🛒🦊"]

    def test_split_budget_options_can_be_explicitly_cleared(self, client, alice):
        client.post(
            "/sync_settings",
            json={"currency_symbol": "$", "split_budget_options": ["🛒🦊"]},
            headers=alice["headers"],
        )
        client.post(
            "/sync_settings",
            json={"currency_symbol": "$", "split_budget_options": []},
            headers=alice["headers"],
        )
        resp = client.get("/settings", headers=alice["headers"]).json()
        assert resp["split_budget_options"] == []

    def test_get_settings_defaults_when_no_row(self, client, alice):
        resp = client.get("/settings", headers=alice["headers"]).json()
        assert resp == {"currency_symbol": "$", "split_budget_options": []}


class TestCheckAutomations:
    def test_no_budgets(self, client, alice):
        response = client.post("/check_automations", headers=alice["headers"])
        assert response.status_code == 200
        assert response.json()["monthly_update_ran"] is False

    def test_runs_once_per_month(self, client, db, alice):
        db.add(Budget(household_id=alice["household_id"], emoji="🛒", label="Groc", monthly_amount=500))
        db.commit()

        first = client.post("/check_automations", headers=alice["headers"]).json()
        assert first["monthly_update_ran"] is True

        second = client.post("/check_automations", headers=alice["headers"]).json()
        assert second["monthly_update_ran"] is False

    def test_household_isolation(self, client, db, alice, bob):
        db.add(Budget(household_id=alice["household_id"], emoji="🛒", label="A", monthly_amount=500))
        db.add(Budget(household_id=bob["household_id"], emoji="✈️", label="B", monthly_amount=300))
        db.commit()

        client.post("/check_automations", headers=alice["headers"])

        alice_entries = db.query(LedgerEntry).filter_by(household_id=alice["household_id"]).all()
        bob_entries = db.query(LedgerEntry).filter_by(household_id=bob["household_id"]).all()
        assert len(alice_entries) == 1
        assert alice_entries[0].budget_emoji == "🛒"
        assert len(bob_entries) == 0


class TestExportYear:
    def test_only_returns_own_household(self, client, db, alice, bob, mock_categorizer):
        client.post(
            "/make_spending",
            json={"amount": -10, "currency": "USD", "budget_emoji": "🛒", "description_text": "alice"},
            headers=alice["headers"],
        )
        client.post(
            "/make_spending",
            json={"amount": -20, "currency": "USD", "budget_emoji": "🛒", "description_text": "bob"},
            headers=bob["headers"],
        )

        year = datetime.now(timezone.utc).year
        alice_csv = client.get(f"/export_year?year={year}", headers=alice["headers"]).text
        assert "alice" in alice_csv
        assert "bob" not in alice_csv


class TestCategoryMap:
    def test_missing_emoji_returns_400(self, client, alice):
        response = client.get("/category_map", headers=alice["headers"])
        assert response.status_code == 400

    def test_returns_per_entry_amount_and_datetime(self, client, db, alice, mock_categorizer):
        db.add(Budget(household_id=alice["household_id"], emoji="🛒", label="Groc", monthly_amount=500))
        db.commit()

        client.post(
            "/make_spending",
            json={"amount": -10, "currency": "USD", "budget_emoji": "🛒", "description_text": "milk"},
            headers=alice["headers"],
        )
        client.post(
            "/make_spending",
            json={"amount": -25, "currency": "USD", "budget_emoji": "🛒", "description_text": "bread"},
            headers=alice["headers"],
        )

        resp = client.get("/category_map?budget_emoji=🛒", headers=alice["headers"]).json()
        assert "categories" in resp
        assert len(resp["categories"]) == 1

        category = resp["categories"][0]
        assert category["category_name"] == "Groceries"
        assert category["total_amount"] == 35
        assert "entries" in category
        assert len(category["entries"]) == 2

        # Each entry has description + amount (positive abs) + datetime (ISO string)
        for entry in category["entries"]:
            assert isinstance(entry["description"], str)
            assert isinstance(entry["amount"], int)
            assert entry["amount"] > 0
            assert isinstance(entry["datetime"], str)

        descriptions = {e["description"] for e in category["entries"]}
        assert descriptions == {"milk", "bread"}
