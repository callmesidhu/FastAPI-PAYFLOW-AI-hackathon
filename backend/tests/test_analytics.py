"""Tests for Prompt 20: Receivables queries, aging buckets, multi-currency isolation,
and read-only AI financial intelligence.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.mongodb import get_db
from app.main import app
from app.models.customer import Customer
from app.models.enums import InvoiceStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.schemas.analytics import AnalyticsAISummaryRequest
from app.services.analytics_service import AnalyticsService
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def test_user() -> User:
    return User(
        id="usr-analytics-1",
        email="analytics.user@example.com",
        hashed_password="hashed_pw_test",
        name="Finance Manager",
    )


@pytest.fixture
def foreign_user() -> User:
    return User(
        id="usr-analytics-2",
        email="foreign.user@example.com",
        hashed_password="hashed_pw_test",
        name="Foreign Manager",
    )


@pytest.fixture
def customer_acme(test_user: User) -> Customer:
    return Customer(
        id="cust-acme-1",
        user_id=test_user.id,
        name="Acme Global",
        email="billing@acme.com",
        company="Acme Global Inc",
    )


@pytest.fixture
def customer_beta(test_user: User) -> Customer:
    return Customer(
        id="cust-beta-2",
        user_id=test_user.id,
        name="Beta Labs",
        email="accounts@betalabs.io",
        company="Beta Labs Ltd",
    )


@pytest.mark.asyncio
async def test_empty_receivables_analytics_returns_clean_zero_state(
    mock_db: MockDatabase,
    test_user: User,
):
    """When a merchant has no invoices, analytics returns has_data=False and empty lists."""
    await mock_db.users.insert_one(test_user.model_dump())

    res = await AnalyticsService.get_receivables_analytics(
        db=mock_db,
        user_id=test_user.id,
    )

    assert res.has_data is False
    assert len(res.by_currency) == 0
    assert len(res.customer_balances) == 0


@pytest.mark.asyncio
async def test_aging_buckets_reconciliation_and_invoice_citations(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """Test overdue invoices correctly bucket into 0-7, 8-30, 31-60, and 60+ days with invoice citations."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()

    # Invoice 1: Due in 2 days (bucket 0_7)
    inv1 = Invoice(
        internal_id="inv-due-soon",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-2026-0001",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=10),
        due_date=today + timedelta(days=2),
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Consulting", quantity=Decimal("1"), unit_price=Decimal("500.00"), tax=Decimal("0"))],
    )
    # Invoice 2: 15 days past due (bucket 8_30)
    inv2 = Invoice(
        internal_id="inv-overdue-15",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-2026-0002",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=30),
        due_date=today - timedelta(days=15),
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Design", quantity=Decimal("1"), unit_price=Decimal("1200.00"), tax=Decimal("0"))],
    )
    # Invoice 3: 45 days past due (bucket 31_60)
    inv3 = Invoice(
        internal_id="inv-overdue-45",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-2026-0003",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=60),
        due_date=today - timedelta(days=45),
        status=InvoiceStatus.OVERDUE,
        items=[InvoiceItem(name="Retainer", quantity=Decimal("1"), unit_price=Decimal("2000.00"), tax=Decimal("0"))],
    )
    # Invoice 4: 75 days past due (bucket 60_plus)
    inv4 = Invoice(
        internal_id="inv-overdue-75",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-2026-0004",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=90),
        due_date=today - timedelta(days=75),
        status=InvoiceStatus.OVERDUE,
        items=[InvoiceItem(name="Audit", quantity=Decimal("1"), unit_price=Decimal("3500.00"), tax=Decimal("0"))],
    )

    for inv in [inv1, inv2, inv3, inv4]:
        await mock_db.invoices.insert_one(inv.model_dump())

    res = await AnalyticsService.get_receivables_analytics(
        db=mock_db,
        user_id=test_user.id,
    )

    assert res.has_data is True
    assert len(res.by_currency) == 1
    usd_stats = res.by_currency[0]
    assert usd_stats.currency == "USD"
    assert usd_stats.total_outstanding == "7200.00"
    assert usd_stats.total_overdue == "6700.00"  # inv2 + inv3 + inv4

    # Verify bucket amounts and citations
    b = usd_stats.aging_buckets
    assert b.bucket_0_7_days.amount == "500.00"
    assert "INV-2026-0001" in b.bucket_0_7_days.invoice_numbers

    assert b.bucket_8_30_days.amount == "1200.00"
    assert "INV-2026-0002" in b.bucket_8_30_days.invoice_numbers

    assert b.bucket_31_60_days.amount == "2000.00"
    assert "INV-2026-0003" in b.bucket_31_60_days.invoice_numbers

    assert b.bucket_60_plus_days.amount == "3500.00"
    assert "INV-2026-0004" in b.bucket_60_plus_days.invoice_numbers


@pytest.mark.asyncio
async def test_multi_currency_strict_segregation(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
    customer_beta: Customer,
):
    """Invoices in USD and EUR must never be combined into a single balance."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())
    await mock_db.customers.insert_one(customer_beta.model_dump())

    today = date.today()

    inv_usd = Invoice(
        internal_id="inv-usd-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-USD-001",
        currency=SupportedCurrency.USD,
        issue_date=today,
        due_date=today + timedelta(days=14),
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="US Work", quantity=Decimal("1"), unit_price=Decimal("1000.00"), tax=Decimal("0"))],
    )
    inv_eur = Invoice(
        internal_id="inv-eur-1",
        user_id=test_user.id,
        customer_id=customer_beta.id,
        invoice_number="INV-EUR-001",
        currency=SupportedCurrency.EUR,
        issue_date=today,
        due_date=today + timedelta(days=14),
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="EU Work", quantity=Decimal("1"), unit_price=Decimal("800.00"), tax=Decimal("0"))],
    )

    await mock_db.invoices.insert_one(inv_usd.model_dump())
    await mock_db.invoices.insert_one(inv_eur.model_dump())

    res = await AnalyticsService.get_receivables_analytics(
        db=mock_db,
        user_id=test_user.id,
    )

    assert len(res.by_currency) == 2
    curr_map = {c.currency: c for c in res.by_currency}
    assert "USD" in curr_map
    assert "EUR" in curr_map

    assert curr_map["USD"].total_outstanding == "1000.00"
    assert curr_map["EUR"].total_outstanding == "800.00"

    # Verify customer balances grouped by customer and currency
    assert len(res.customer_balances) == 2
    c_names = {cb.customer_name: cb for cb in res.customer_balances}
    assert c_names["Acme Global"].currency == "USD"
    assert c_names["Acme Global"].outstanding_amount == "1000.00"
    assert c_names["Beta Labs"].currency == "EUR"
    assert c_names["Beta Labs"].outstanding_amount == "800.00"


@pytest.mark.asyncio
async def test_ai_summary_cites_invoices_and_respects_insufficient_data(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """AI summary must cite actual invoice numbers, and refuse predictions without enough data."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()

    inv = Invoice(
        internal_id="inv-cite-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-2026-0099",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=10),
        status=InvoiceStatus.OVERDUE,
        items=[InvoiceItem(name="Engineering", quantity=Decimal("1"), unit_price=Decimal("1500.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv.model_dump())

    summary_resp = await AnalyticsService.generate_ai_summary(
        db=mock_db,
        user_id=test_user.id,
    )

    assert summary_resp.has_sufficient_data is True
    # Invariant: Must cite the exact invoice number and balance
    assert "INV-2026-0099" in summary_resp.summary
    assert "1500.00" in summary_resp.summary

    # Velocity prediction guard: only 0 paid invoices exist -> must state insufficient data
    assert "INSUFFICIENT HISTORICAL DATA" in summary_resp.payment_velocity_estimate


@pytest.mark.asyncio
async def test_ai_summary_settlement_velocity_estimate_with_sufficient_history(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """When >= 3 settled invoices exist, velocity is computed and explicitly labeled as an estimate."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    now = datetime.now(timezone.utc)
    base_date = date.today() - timedelta(days=60)

    # Insert 3 paid invoices with 10-day turnaround
    for i in range(1, 4):
        paid_inv = Invoice(
            internal_id=f"inv-paid-{i}",
            user_id=test_user.id,
            customer_id=customer_acme.id,
            invoice_number=f"INV-PAID-00{i}",
            currency=SupportedCurrency.USD,
            issue_date=base_date + timedelta(days=i * 10),
            due_date=base_date + timedelta(days=i * 10 + 14),
            status=InvoiceStatus.PAID,
            paid_at=datetime.combine(base_date + timedelta(days=i * 10 + 8), datetime.min.time(), tzinfo=timezone.utc),
            items=[InvoiceItem(name="Settled Work", quantity=Decimal("1"), unit_price=Decimal("1000.00"), tax=Decimal("0"))],
        )
        await mock_db.invoices.insert_one(paid_inv.model_dump())

    summary_resp = await AnalyticsService.generate_ai_summary(
        db=mock_db,
        user_id=test_user.id,
    )

    assert summary_resp.payment_velocity_estimate is not None
    # Invariant: Must be explicitly labeled as an ESTIMATE
    assert "[ESTIMATE" in summary_resp.payment_velocity_estimate
    assert "8.0 days" in summary_resp.payment_velocity_estimate


@pytest.mark.asyncio
async def test_analytics_multi_tenant_user_isolation(
    mock_db: MockDatabase,
    test_user: User,
    foreign_user: User,
    customer_acme: Customer,
):
    """User A cannot access or aggregate User B's receivables analytics."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.users.insert_one(foreign_user.model_dump())

    # Insert invoice for foreign_user
    inv_foreign = Invoice(
        internal_id="inv-foreign-1",
        user_id=foreign_user.id,
        customer_id="cust-foreign-1",
        invoice_number="INV-SECRET-001",
        currency=SupportedCurrency.USD,
        issue_date=date.today(),
        due_date=date.today() + timedelta(days=14),
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Secret Work", quantity=Decimal("1"), unit_price=Decimal("9999.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv_foreign.model_dump())

    res = await AnalyticsService.get_receivables_analytics(
        db=mock_db,
        user_id=test_user.id,
    )

    # test_user has 0 invoices, should not see foreign_user's $9999.00
    assert res.has_data is False
    assert len(res.by_currency) == 0


@pytest.mark.asyncio
async def test_analytics_http_api_endpoints(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """Verify HTTP GET /api/analytics/receivables and POST /api/analytics/ai-summary."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()
    inv = Invoice(
        internal_id="inv-http-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-2026-HTTP",
        currency=SupportedCurrency.USD,
        issue_date=today,
        due_date=today + timedelta(days=14),
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="API Service", quantity=Decimal("1"), unit_price=Decimal("750.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        token = create_access_token(subject=test_user.id)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            # 1. GET /api/analytics/receivables
            get_res = await ac.get("/api/analytics/receivables")
            assert get_res.status_code == 200
            data = get_res.json()
            assert data["has_data"] is True
            assert len(data["by_currency"]) == 1
            assert data["by_currency"][0]["total_outstanding"] == "750.00"

            # 2. POST /api/analytics/ai-summary
            post_res = await ac.post(
                "/api/analytics/ai-summary",
                json={"timezone": "UTC"},
            )
            assert post_res.status_code == 200
            summary_data = post_res.json()
            assert summary_data["has_sufficient_data"] is True
            assert "INV-2026-HTTP" in summary_data["summary"]
            assert "750.00" in summary_data["summary"]
    finally:
        app.dependency_overrides.clear()
