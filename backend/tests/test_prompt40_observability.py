"""Tests for Prompt 40: Operational Observability, Diagnostics, and Graceful Failure.

Verifies:
1. Correlation ID and Request ID headers on all HTTP responses.
2. Structured metrics collection and safe error categorization.
3. Protected /api/diagnostics endpoint (requires auth, zero credentials exposed).
4. App usability when AI provider is unavailable (manual invoice creation continues).
5. Dashboard usability when PayPal is disconnected.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.user import User
from app.core.metrics import ErrorCategory, metrics_collector
from app.core.security import create_access_token, hash_password
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.fixture
def test_user():
    return User(
        id="usr_obs_test_001",
        email="obs_tester@payflow.example",
        name="Alex Vance",
        business_name="Vance Studio LLC",
        hashed_password=hash_password("SafePassword2026!"),
        is_active=True,
    )


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_correlation_id_middleware_headers():
    """Responses include X-Correlation-ID and X-Request-ID headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case A: Generated correlation ID
        res = await client.get("/health")
        assert res.status_code == 200
        assert "x-correlation-id" in res.headers
        assert "x-request-id" in res.headers
        assert len(res.headers["x-correlation-id"]) > 10

        # Case B: Inbound client correlation ID preserved
        custom_cid = "client-req-9999-custom"
        res_custom = await client.get("/health", headers={"X-Correlation-ID": custom_cid})
        assert res_custom.status_code == 200
        assert res_custom.headers["x-correlation-id"] == custom_cid
        assert res_custom.headers["x-request-id"] == custom_cid


@pytest.mark.asyncio
async def test_diagnostics_requires_authentication():
    """Unauthenticated access to /api/diagnostics is rejected with 401."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/diagnostics")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_diagnostics_payload_security_and_structure(mock_db, test_user, auth_headers, monkeypatch):
    """Authenticated /api/diagnostics returns health, metrics, recovery guidance, and NO secrets."""
    monkeypatch.setattr("app.db.mongodb.db_manager.db", mock_db)
    monkeypatch.setattr("app.api.deps.get_db", lambda: mock_db)
    monkeypatch.setattr("app.api.v1.diagnostics.get_db", lambda: mock_db)
    await mock_db.users.insert_one(test_user.model_dump())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/diagnostics", headers=auth_headers)

    assert res.status_code == 200
    data = res.json()

    # Structural fields
    assert data["status"] == "healthy"
    assert "services" in data
    assert "backend" in data["services"]
    assert "paypal_sandbox" in data["services"]
    assert "ai_provider" in data["services"]
    assert "metrics" in data
    assert "recovery_guidance" in data

    # Recovery guidance checks
    guidance = data["recovery_guidance"]
    assert "ai_unavailable" in guidance
    assert "paypal_unavailable" in guidance
    assert "webhook_failure" in guidance

    # ZERO SECRETS INVARIANT
    raw_str = res.text.lower()
    assert "client_secret" not in raw_str or "client_secret=" not in raw_str
    assert "app_secret_key" not in raw_str
    assert "password" not in raw_str or "password=" not in raw_str


@pytest.mark.asyncio
async def test_metrics_collector_categorization():
    """Metrics collector correctly increments requests and error categories."""
    metrics_collector.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Generate 404
        await client.get("/api/non-existent-route-999")
        # Generate 401
        await client.get("/api/diagnostics")

    summary = metrics_collector.get_summary()
    assert summary["api"]["total_requests"] >= 2
    errors = summary["api"]["errors_by_category"]
    assert ErrorCategory.API_NOT_FOUND.value in errors
    assert ErrorCategory.API_AUTH_ERROR.value in errors


@pytest.mark.asyncio
async def test_manual_invoice_creation_works_without_ai(mock_db, test_user, auth_headers, monkeypatch):
    """Manual invoice creation at /api/invoices operates 100% reliably even if AI fails."""
    monkeypatch.setattr("app.db.mongodb.db_manager.db", mock_db)
    monkeypatch.setattr("app.api.deps.get_db", lambda: mock_db)
    monkeypatch.setattr("app.api.v1.invoices.get_db", lambda: mock_db)
    monkeypatch.setattr("app.api.v1.customers.get_db", lambda: mock_db)
    await mock_db.users.insert_one(test_user.model_dump())

    # Create customer directly
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        cust_res = await client.post(
            "/api/customers",
            json={"name": "Manual Client Corp", "email": "billing@manualclient.example"},
            headers=auth_headers,
        )
        assert cust_res.status_code == 201
        cust_id = cust_res.json()["id"]

        # Create invoice draft without AI
        inv_res = await client.post(
            "/api/invoices",
            json={
                "customer_id": cust_id,
                "currency": "USD",
                "items": [
                    {"name": "Standard Consulting", "quantity": 1, "unit_price": "750.00", "tax": "0.00"}
                ],
                "issue_date": "2026-11-10",
                "due_date": "2026-11-24",
                "notes": "Direct manual creation without AI provider.",
            },
            headers=auth_headers,
        )

    assert inv_res.status_code == 201
    inv_data = inv_res.json()
    assert inv_data["status"] == "draft"
    assert inv_data["total"] == "750.00"


@pytest.mark.asyncio
async def test_dashboard_usable_when_paypal_disconnected(mock_db, test_user, auth_headers, monkeypatch):
    """Dashboard metrics query operates cleanly without errors when PayPal is disconnected."""
    monkeypatch.setattr("app.db.mongodb.db_manager.db", mock_db)
    monkeypatch.setattr("app.api.deps.get_db", lambda: mock_db)
    monkeypatch.setattr("app.api.v1.dashboard.get_db", lambda: mock_db)
    await mock_db.users.insert_one(test_user.model_dump())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/dashboard/summary", headers=auth_headers)

    assert res.status_code == 200
    data = res.json()
    assert "by_currency" in data
    assert "attention_needed" in data
