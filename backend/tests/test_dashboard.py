"""Dashboard receivables aggregation and multi-currency reconciliation tests."""

from datetime import date, datetime, timezone
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.enums import InvoiceStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def user_a() -> User:
    return User(
        id="user-dash-1",
        email="dash.owner@example.com",
        hashed_password=hash_password("Pass123!"),
        name="Dashboard Owner",
    )


@pytest.fixture
def user_b() -> User:
    return User(
        id="user-dash-2",
        email="other.owner@example.com",
        hashed_password=hash_password("Pass123!"),
        name="Other Owner",
    )


@pytest.mark.asyncio
async def test_dashboard_reconciles_totals_and_never_mixes_currencies(
    mock_db: MockDatabase,
    user_a: User,
    user_b: User,
):
    """Verify totals reconcile with underlying invoices and currencies are segregated."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())

    # User A: USD Invoice 1 (Sent, $500.00)
    inv1 = Invoice(
        user_id=user_a.id,
        customer_id="cust-1",
        invoice_number="INV-2026-0001",
        items=[InvoiceItem(name="Consulting", unit_price=Decimal("500.00"))],
        currency=SupportedCurrency.USD,
        due_date=date(2026, 11, 20),
        status=InvoiceStatus.SENT,
    )
    # User A: USD Invoice 2 (Overdue, $300.00)
    inv2 = Invoice(
        user_id=user_a.id,
        customer_id="cust-1",
        invoice_number="INV-2026-0002",
        items=[InvoiceItem(name="Design", unit_price=Decimal("300.00"))],
        currency=SupportedCurrency.USD,
        issue_date=date(2026, 10, 15),
        due_date=date(2026, 11, 1),
        status=InvoiceStatus.OVERDUE,
    )
    # User A: EUR Invoice 3 (Sent, €400.00)
    inv3 = Invoice(
        user_id=user_a.id,
        customer_id="cust-2",
        invoice_number="INV-2026-0003",
        items=[InvoiceItem(name="Translation", unit_price=Decimal("400.00"))],
        currency=SupportedCurrency.EUR,
        due_date=date(2026, 11, 25),
        status=InvoiceStatus.SENT,
    )
    # User B: USD Invoice (Should NOT leak into User A's totals)
    inv_b = Invoice(
        user_id=user_b.id,
        customer_id="cust-b",
        invoice_number="INV-B-001",
        items=[InvoiceItem(name="Secret Work", unit_price=Decimal("9999.00"))],
        currency=SupportedCurrency.USD,
        due_date=date(2026, 11, 20),
        status=InvoiceStatus.SENT,
    )

    await mock_db.invoices.insert_one(inv1.model_dump())
    await mock_db.invoices.insert_one(inv2.model_dump())
    await mock_db.invoices.insert_one(inv3.model_dump())
    await mock_db.invoices.insert_one(inv_b.model_dump())

    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}
            res = await client.get("/api/dashboard/summary", headers=headers)
            assert res.status_code == 200
            data = res.json()

            # 1. Total counts for User A (3 invoices, never 4)
            assert data["total_invoices"] == 3
            assert data["sent_count"] == 2
            assert data["overdue_count"] == 1

            # 2. Currencies are segregated — never mixed!
            by_curr = {c["currency"]: c for c in data["by_currency"]}
            assert "USD" in by_curr
            assert "EUR" in by_curr

            # USD: $500 (sent) + $300 (overdue) = $800.00 outstanding; $300.00 overdue
            assert by_curr["USD"]["outstanding"] == "800.00"
            assert by_curr["USD"]["overdue"] == "300.00"

            # EUR: €400 (sent) outstanding; €0.00 overdue
            assert by_curr["EUR"]["outstanding"] == "400.00"
            assert by_curr["EUR"]["overdue"] == "0.00"

            # User B's $9999 is NOT present
            assert by_curr["USD"]["outstanding"] != "10799.00"

            # 3. Attention needed list contains the overdue invoice
            assert len(data["attention_needed"]) == 1
            assert data["attention_needed"][0]["invoice_number"] == "INV-2026-0002"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_fresh_user_receives_clean_zero_state(mock_db: MockDatabase, user_a: User):
    """Verify that a brand-new user with 0 invoices gets a clean, non-fabricated zero state."""
    await mock_db.users.insert_one(user_a.model_dump())
    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}
            res = await client.get("/api/dashboard/summary", headers=headers)
            assert res.status_code == 200
            data = res.json()

            assert data["total_invoices"] == 0
            assert data["overdue_count"] == 0
            assert data["sent_count"] == 0
            assert len(data["attention_needed"]) == 0
            assert len(data["recent_invoices"]) == 0
            assert data["has_trend_data"] is False
            assert data["by_currency"][0]["outstanding"] == "0.00"
    finally:
        app.dependency_overrides.clear()
