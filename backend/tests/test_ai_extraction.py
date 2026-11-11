"""Tests for Prompt 19: Natural language invoice extraction, ambiguity handling,
editable preview generation, and safe confirmation.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.main import app
from app.models.customer import Customer
from app.models.invoice import InvoiceStatus
from app.models.user import User
from app.schemas.ai import (
    ConfirmExtractedInvoiceRequest,
    DraftItemArgs,
    InvoiceExtractionRequest,
)
from app.services.invoice_extractor import InvoiceExtractor
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def test_user() -> User:
    return User(
        id="usr-extract-1",
        email="merchant@example.com",
        hashed_password="hashed_pw_test",
        name="Merchant User",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id="usr-extract-2",
        email="other@example.com",
        hashed_password="hashed_pw_test",
        name="Other User",
    )


@pytest.fixture
def customer_john(test_user: User) -> Customer:
    return Customer(
        id="cust-john-1",
        user_id=test_user.id,
        name="John Smith",
        email="john.smith@example.com",
        company="Smith Tech LLC",
    )


@pytest.mark.asyncio
async def test_natural_language_extraction_standard_flow(
    mock_db: MockDatabase,
    test_user: User,
    customer_john: Customer,
):
    """'Create a $500 invoice for John Smith for website development, due in seven days.'

    Extracts customer identity, amount, currency, description, and relative due date.
    Tax is not inferred (defaults to 0.00). Returns is_suggestion=True without saving to DB.
    """
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_john.model_dump())

    text = "Create a $500 invoice for John Smith for website development, due in seven days."
    response = await InvoiceExtractor.extract_invoice(
        db=mock_db,
        user_id=test_user.id,
        text=text,
        user_timezone="UTC",
    )

    assert response.is_suggestion is True
    assert response.clarification_needed is False
    assert response.extracted_draft is not None

    draft = response.extracted_draft
    assert draft.customer_id == customer_john.id
    assert draft.customer_name == "John Smith"
    assert draft.currency == "USD"
    assert draft.total == "500.00"
    assert draft.subtotal == "500.00"
    assert draft.tax == "0.00"  # Tax must not be inferred unless requested

    # Check relative date calculation (user_timezone="UTC")
    today = datetime.now(timezone.utc).date()
    expected_due = today + timedelta(days=7)
    assert draft.due_date == str(expected_due)
    assert draft.due_date_relative_text == "due in seven days"
    assert draft.timezone_disclosed == "UTC"

    # Line item checks
    assert len(draft.items) == 1
    assert "website development" in draft.items[0].name.lower()
    assert draft.items[0].unit_price == Decimal("500.00")
    assert draft.items[0].quantity == Decimal("1.0")

    # Invariant check: Extraction is read-only, NO records written to db.invoices
    assert len(mock_db.invoices.docs) == 0


@pytest.mark.asyncio
async def test_ambiguous_customer_name_asks_clarification(
    mock_db: MockDatabase,
    test_user: User,
):
    """When multiple customers match a partial search query, the extractor must ask which one."""
    cust_a = Customer(
        id="cust-smith-1",
        user_id=test_user.id,
        name="John Smith",
        email="john@smithcorp.com",
    )
    cust_b = Customer(
        id="cust-smith-2",
        user_id=test_user.id,
        name="Alice Smith",
        email="alice@smithdesign.com",
    )
    await mock_db.customers.insert_one(cust_a.model_dump())
    await mock_db.customers.insert_one(cust_b.model_dump())

    text = "Bill Smith 1200 USD for branding services due in 14 days"
    response = await InvoiceExtractor.extract_invoice(
        db=mock_db,
        user_id=test_user.id,
        text=text,
    )

    assert response.clarification_needed is True
    assert response.ambiguity_reason == "multiple_customer_matches"
    assert len(response.customer_matches) == 2
    assert "John Smith" in response.clarification_question
    assert "Alice Smith" in response.clarification_question


@pytest.mark.asyncio
async def test_missing_currency_asks_clarification(
    mock_db: MockDatabase,
    test_user: User,
    customer_john: Customer,
):
    """When an instruction specifies amount but omits currency, clarification is requested."""
    await mock_db.customers.insert_one(customer_john.model_dump())

    text = "Invoice John Smith 750 for consultation services due tomorrow"
    response = await InvoiceExtractor.extract_invoice(
        db=mock_db,
        user_id=test_user.id,
        text=text,
    )

    assert response.clarification_needed is True
    assert response.ambiguity_reason == "missing_currency"
    assert "currency" in response.clarification_question.lower()


@pytest.mark.asyncio
async def test_invalid_past_due_date_asks_clarification(
    mock_db: MockDatabase,
    test_user: User,
    customer_john: Customer,
):
    """Due dates in the past are rejected with a clarification question."""
    await mock_db.customers.insert_one(customer_john.model_dump())

    text = "Create an invoice for John Smith for $300 USD due 2020-01-01"
    response = await InvoiceExtractor.extract_invoice(
        db=mock_db,
        user_id=test_user.id,
        text=text,
    )

    assert response.clarification_needed is True
    assert response.ambiguity_reason == "invalid_due_date"
    assert "past" in response.clarification_question.lower()


@pytest.mark.asyncio
async def test_confirm_extracted_draft_persists_authoritative_draft(
    mock_db: MockDatabase,
    test_user: User,
    customer_john: Customer,
):
    """User-confirmed draft passes through backend validation and creates a real draft invoice."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_john.model_dump())

    confirm_payload = ConfirmExtractedInvoiceRequest(
        customer_id=customer_john.id,
        currency="USD",
        items=[
            DraftItemArgs(
                name="Website Development",
                quantity=Decimal("1.0"),
                unit_price=Decimal("500.00"),
                tax=Decimal("0.00"),
            )
        ],
        issue_date=str(date.today()),
        due_date=str(date.today() + timedelta(days=7)),
        notes="Net 7 payment terms",
    )

    created = await InvoiceExtractor.confirm_extracted_draft(
        db=mock_db,
        user_id=test_user.id,
        payload=confirm_payload,
    )

    assert created.status == InvoiceStatus.DRAFT
    assert created.invoice_number.startswith("INV-")
    assert created.customer_name == "John Smith"
    assert created.total == Decimal("500.00")
    assert created.tax == Decimal("0.00")
    assert created.currency == "USD"
    # Ensure it is persisted in database
    assert len(mock_db.invoices.docs) == 1
    # Ensure no PayPal ID or URL was fabricated
    assert created.paypal_invoice_id is None
    assert created.paypal_invoice_url is None


@pytest.mark.asyncio
async def test_backend_revalidates_and_rejects_negative_unit_price(
    mock_db: MockDatabase,
    test_user: User,
    customer_john: Customer,
):
    """Backend strictly rejects invalid numbers (e.g. negative unit price) on confirm."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_john.model_dump())

    # Pydantic validates ge=0 on DraftItemArgs, so negative unit_price raises ValueError
    with pytest.raises(Exception):
        ConfirmExtractedInvoiceRequest(
            customer_id=customer_john.id,
            currency="USD",
            items=[
                DraftItemArgs(
                    name="Invalid Item",
                    quantity=Decimal("1.0"),
                    unit_price=Decimal("-100.00"),
                    tax=Decimal("0.00"),
                )
            ],
        )


@pytest.mark.asyncio
async def test_user_cannot_confirm_for_other_users_customer(
    mock_db: MockDatabase,
    test_user: User,
    other_user: User,
):
    """Confirming a draft for a customer owned by another user is strictly blocked (404/403)."""
    other_customer = Customer(
        id="cust-other-99",
        user_id=other_user.id,
        name="Foreign Client",
        email="foreign@client.com",
    )
    await mock_db.customers.insert_one(other_customer.model_dump())

    confirm_payload = ConfirmExtractedInvoiceRequest(
        customer_id=other_customer.id,
        currency="USD",
        items=[
            DraftItemArgs(
                name="Consulting",
                quantity=Decimal("1.0"),
                unit_price=Decimal("200.00"),
                tax=Decimal("0.00"),
            )
        ],
    )

    with pytest.raises(Exception) as exc_info:
        await InvoiceExtractor.confirm_extracted_draft(
            db=mock_db,
            user_id=test_user.id,
            payload=confirm_payload,
        )
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_extract_and_confirm_http_api_endpoints(
    mock_db: MockDatabase,
    test_user: User,
    customer_john: Customer,
):
    """Verify HTTP POST /api/ai/extract-invoice and /api/ai/confirm-extracted-invoice."""
    from app.db.mongodb import get_db

    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_john.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        token = create_access_token(subject=test_user.id)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            # 1. Test extraction
            extract_res = await ac.post(
                "/api/ai/extract-invoice",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "text": "Create a $500 invoice for John Smith for website development, due in seven days.",
                    "timezone": "UTC",
                },
            )
            assert extract_res.status_code == 200
            data = extract_res.json()
            assert data["is_suggestion"] is True
            assert data["clarification_needed"] is False
            assert data["extracted_draft"]["total"] == "500.00"
            assert data["extracted_draft"]["customer_id"] == customer_john.id

            # 2. Test confirmation
            confirm_res = await ac.post(
                "/api/ai/confirm-extracted-invoice",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "customer_id": customer_john.id,
                    "currency": "USD",
                    "items": [
                        {
                            "name": "website development",
                            "quantity": 1,
                            "unit_price": 500,
                            "tax": 0,
                        }
                    ],
                    "issue_date": str(date.today()),
                    "due_date": str(date.today() + timedelta(days=7)),
                    "notes": "Fast-draft via AI",
                },
            )
            assert confirm_res.status_code == 201
            saved = confirm_res.json()
            assert saved["status"] == "draft"
            assert saved["customer_name"] == "John Smith"
            assert saved["total"] == "500.00"
    finally:
        app.dependency_overrides.clear()
