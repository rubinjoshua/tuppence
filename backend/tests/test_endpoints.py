"""Basic endpoint tests"""

import pytest
from datetime import datetime, timezone


def test_health_check(client):
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "version" in response.json()


def test_sync_budgets(client, sample_budgets):
    """Test syncing budgets from iOS"""
    response = client.post("/sync_budgets", json={"budgets": sample_budgets})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["synced_count"] == 3


def test_get_monthly_budgets(client, sample_budgets):
    """Test getting monthly budgets"""
    # First sync budgets
    client.post("/sync_budgets", json={"budgets": sample_budgets})

    # Then get them
    response = client.get("/monthly_budgets")
    assert response.status_code == 200
    data = response.json()
    assert len(data["budgets"]) == 3
    assert data["budgets"][0]["emoji"] in ["🛒", "✈️", "🎬"]


def test_get_amounts_empty(client):
    """Test getting amounts with no data"""
    response = client.get("/amounts")
    assert response.status_code == 200
    data = response.json()
    assert "budgets" in data
    assert len(data["budgets"]) == 0


def test_sync_settings(client):
    """Test syncing settings"""
    response = client.post("/sync_settings", json={"currency_symbol": "$"})
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_make_spending(client, sample_budgets, monkeypatch):
    """Test making a spending entry"""
    # Mock the OpenAI categorization to avoid API calls
    async def mock_categorize(text, db):
        return "Groceries"

    from app.api import routes
    monkeypatch.setattr(routes, "get_or_create_category", mock_categorize)

    # Sync budgets first
    client.post("/sync_budgets", json={"budgets": sample_budgets})

    # Make spending
    response = client.post("/make_spending", json={
        "amount": -50,
        "currency": "USD",
        "budget_emoji": "🛒",
        "description_text": "milk and eggs"
    })

    assert response.status_code == 200
    data = response.json()
    assert "uuid" in data
    assert data["category"] == "Groceries"
    assert data["success"] is True


def test_get_ledger_empty(client):
    """Test getting ledger with no entries"""
    response = client.get("/ledger")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_ledger_with_month(client):
    """Test getting ledger for specific month"""
    response = client.get("/ledger?month=2026-03")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_category_map_missing_emoji(client):
    """Test category map without budget emoji"""
    response = client.get("/category_map")
    assert response.status_code == 400
    assert "budget_emoji" in response.json()["detail"]


def test_get_category_map_empty(client):
    """Test category map with no data"""
    response = client.get("/category_map?budget_emoji=🛒&month=2026-03")
    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert len(data["categories"]) == 0


def test_undo_spending_not_found(client):
    """Test deleting non-existent spending"""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.delete(f"/undo_spending/{fake_uuid}")
    assert response.status_code == 404


def test_check_automations(client):
    """Test check automations endpoint"""
    response = client.post("/check_automations")
    assert response.status_code == 200
    data = response.json()
    assert "monthly_update_ran" in data
    assert "message" in data


def test_export_year(client):
    """Test exporting year as CSV"""
    response = client.get("/export_year?year=2026")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "tuppence_ledger_2026.csv" in response.headers["content-disposition"]


def test_archive_year(client):
    """Test archiving a year"""
    response = client.post("/archive_year?year=2025")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["year"] == 2025


def test_make_spending_and_undo(client, sample_budgets, monkeypatch):
    """Test creating and then deleting a spending entry"""
    # Mock categorization
    async def mock_categorize(text, db):
        return "Groceries"

    from app.api import routes
    monkeypatch.setattr(routes, "get_or_create_category", mock_categorize)

    # Sync budgets
    client.post("/sync_budgets", json={"budgets": sample_budgets})

    # Make spending
    response = client.post("/make_spending", json={
        "amount": -30,
        "currency": "USD",
        "budget_emoji": "🛒",
        "description_text": "bread"
    })
    assert response.status_code == 200
    uuid = response.json()["uuid"]

    # Undo spending
    response = client.delete(f"/undo_spending/{uuid}")
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_full_workflow(client, sample_budgets, monkeypatch):
    """Test complete workflow: sync, spend, query"""
    # Mock categorization
    async def mock_categorize(text, db):
        return "Groceries"

    from app.api import routes
    monkeypatch.setattr(routes, "get_or_create_category", mock_categorize)

    # 1. Sync settings
    response = client.post("/sync_settings", json={"currency_symbol": "$"})
    assert response.status_code == 200

    # 2. Sync budgets
    response = client.post("/sync_budgets", json={"budgets": sample_budgets})
    assert response.status_code == 200

    # 3. Check automations
    response = client.post("/check_automations")
    assert response.status_code == 200

    # 4. Make spending
    response = client.post("/make_spending", json={
        "amount": -25,
        "currency": "USD",
        "budget_emoji": "🛒",
        "description_text": "coffee"
    })
    assert response.status_code == 200

    # 5. Get ledger
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    response = client.get(f"/ledger?month={month}")
    assert response.status_code == 200
    assert len(response.json()) >= 1

    # 6. Get amounts
    response = client.get("/amounts")
    assert response.status_code == 200
