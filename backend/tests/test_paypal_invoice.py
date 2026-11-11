"""PayPal Invoicing Adapter & Execution Tests (Prompt 15).

Verifies:
1. Approved invoice execution via official Invoicing API v2.
2. Unapproved invoices are rejected.
3. Payload mutations after approval invalidate the approval and reject with HTTP 409.
4. PayPal invoice ID and official URL are persisted.
5. Invoicing status transitions cleanly to 'created'.
6. Duplicate execution prevention (idempotency safety).
7. Safe, actionable error mapping on PayPal API failures without leaking credentials.
8. Multi-tenant user isolation.
9. Verified mapping of internal models to official PayPal v2 payloads.
"""

from datetime import date, timedelta
from decimal import Decimal
import json
import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.approval import Approval, compute_payload_hash
from app.models.customer import BillingAddress, Customer
from app.models.enums import ActionType, ApprovalStatus, InvoiceStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.services.approval_service import compute_invoice_payload_snapshot
from app.services.paypal_service import (
    PayPalService,
    build_paypal_invoice_payload,
    extract_paypal_invoice_id,
    extract_paypal_invoice_url,
    paypal_service,
)
from tests.mock_db import MockDatabase

settings = get_settings()
TODAY = date.today()
DUE = TODAY + timedelta(days=14)


@pytest.fixture(autouse=True)
def reset_paypal_service_cache():
    """Ensure in-memory token cache is isolated between tests."""
    paypal_service._cached_token = None
    yield
    paypal_service._cached_token = None


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def user_a() -> User:
    return User(
        id="user-a-paypal",
        email="owner.a@example.com",
        hashed_password=hash_password("Secret123!"),
        name="Alex Morgan",
        business_name="Morgan Studio",
    )


@pytest.fixture
def user_b() -> User:
    return User(
        id="user-b-paypal",
        email="owner.b@example.com",
        hashed_password=hash_password("Secret123!"),
        name="Jordan Lee",
        business_name="Lee Design",
    )


@pytest.fixture
def sample_customer(user_a: User) -> Customer:
    return Customer(
        id="cust-paypal-1",
        user_id=user_a.id,
        name="Elena Rostova",
        email="elena@rostova.com",
        company="Rostova Enterprises",
        billing_address=BillingAddress(
            address_line_1="100 Howard St",
            city="San Francisco",
            state="CA",
            postal_code="94105",
            country_code="US",
        ),
    )


@pytest.fixture
def sample_invoice(user_a: User, sample_customer: Customer) -> Invoice:
    return Invoice(
        internal_id="inv-paypal-1",
        user_id=user_a.id,
        customer_id=sample_customer.id,
        invoice_number="INV-2026-0001",
        issue_date=TODAY,
        due_date=DUE,
        currency=SupportedCurrency.USD,
        notes="Net 14 payment terms via PayPal Sandbox.",
        items=[
            InvoiceItem(
                name="Brand Strategy Workshop",
                description="Discovery sprint and deliverables",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1250.00"),
                tax=Decimal("0.00"),
            ),
            InvoiceItem(
                name="Design Token Assets",
                quantity=Decimal("2.00"),
                unit_price=Decimal("350.00"),
                tax=Decimal("0.00"),
            ),
        ],
    )


# ==============================================================================
# Unit Mapping Tests
# ==============================================================================

def test_build_paypal_invoice_payload_mapping(
    sample_invoice: Invoice,
    sample_customer: Customer,
    user_a: User,
):
    """Verify exact payload mapping adhering strictly to official PayPal Invoicing v2 schema."""
    payload = build_paypal_invoice_payload(sample_invoice, sample_customer, user_a)

    # Invoicer mapping
    assert payload["invoicer"]["business_name"] == "Morgan Studio"
    assert payload["invoicer"]["email_address"] == "owner.a@example.com"
    assert payload["invoicer"]["name"]["given_name"] == "Alex"
    assert payload["invoicer"]["name"]["surname"] == "Morgan"

    # Detail mapping
    assert payload["detail"]["invoice_number"] == "INV-2026-0001"
    assert payload["detail"]["currency_code"] == "USD"
    assert payload["detail"]["payment_term"]["due_date"] == str(DUE)

    # Primary recipient billing mapping
    recipients = payload["primary_recipients"]
    assert len(recipients) == 1
    billing = recipients[0]["billing_info"]
    assert billing["name"]["given_name"] == "Elena"
    assert billing["name"]["surname"] == "Rostova"
    assert billing["email_address"] == "elena@rostova.com"
    assert billing["business_name"] == "Rostova Enterprises"
    assert billing["address"]["admin_area_2"] == "San Francisco"
    assert billing["address"]["admin_area_1"] == "CA"
    assert billing["address"]["postal_code"] == "94105"
    assert billing["address"]["country_code"] == "US"

    # Line items mapping
    items = payload["items"]
    assert len(items) == 2
    assert items[0]["name"] == "Brand Strategy Workshop"
    assert items[0]["quantity"] == "1.00"
    assert items[0]["unit_amount"]["value"] == "1250.00"
    assert items[1]["name"] == "Design Token Assets"
    assert items[1]["quantity"] == "2.00"
    assert items[1]["unit_amount"]["value"] == "350.00"


def test_extract_paypal_invoice_url():
    """Verify payer-view extraction and fallback URL generation."""
    # With payer-view link
    data_with_link = {
        "links": [
            {"rel": "self", "href": "https://api-m.sandbox.paypal.com/v2/invoicing/invoices/INV2-123"},
            {"rel": "payer-view", "href": "https://www.sandbox.paypal.com/invoice/p/#CUSTOM123"},
        ]
    }
    assert extract_paypal_invoice_url(data_with_link, "INV2-123") == "https://www.sandbox.paypal.com/invoice/p/#CUSTOM123"

    # Fallback to standard sandbox URL
    data_no_link = {"links": []}
    assert extract_paypal_invoice_url(data_no_link, "INV2-ABCD-EFGH") == "https://www.sandbox.paypal.com/invoice/p/#ABCDEFGH"


# ==============================================================================
# Endpoint Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_unapproved_invoice_rejected(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
):
    """Calling create PayPal invoice without prior human approval must return 400."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id},
        )
        assert res.status_code == 400
        assert "without an explicit human approval record" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_modified_invoice_invalidates_approval_and_rejects(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
):
    """If invoice contents mutate after approval, the approval is invalidated and execution rejected (409)."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())

    # Create approved approval record matching initial snapshot
    snapshot = compute_invoice_payload_snapshot(sample_invoice)
    initial_hash = compute_payload_hash(snapshot)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=sample_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=initial_hash,
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    # Now mutate the invoice total behind the scenes (e.g. tampering or edit)
    mutated_invoice = sample_invoice.model_copy(deep=True)
    mutated_invoice.items[0].unit_price = Decimal("2500.00")
    mutated_invoice.compute_totals()
    await mock_db.invoices.insert_one(mutated_invoice.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id},
        )
        assert res.status_code == 409
        assert "modified after approval was granted" in res.json()["detail"]

    # Invariant: Approval must now be marked 'invalidated'
    appr_after = await mock_db.approvals.find_one({"id": approval.id})
    assert appr_after is not None
    assert appr_after["status"] == ApprovalStatus.INVALIDATED.value

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_create_paypal_invoice_success_and_persisted(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
    monkeypatch,
):
    """Verify successful dispatch to PayPal Sandbox, ID/URL persistence, and audit log."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client-id-xyz")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret-xyz")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    sample_invoice.status = InvoiceStatus.PENDING_APPROVAL
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    # Snapshot & Approval
    snapshot = compute_invoice_payload_snapshot(sample_invoice)
    appr_hash = compute_payload_hash(snapshot)
    approval = Approval(
        id="appr-test-success",
        user_id=user_a.id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=sample_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=appr_hash,
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    # Mock PayPal OAuth token
    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(
            200,
            json={
                "access_token": "SANDBOX_MOCK_ACCESS_TOKEN_ABC",
                "token_type": "Bearer",
                "expires_in": 32400,
            },
        )
    )

    # Mock PayPal Create Invoice endpoint
    mock_create_route = respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices").mock(
        return_value=Response(
            201,
            json={
                "id": "INV2-SANDBOX-9876-5432",
                "status": "DRAFT",
                "links": [
                    {
                        "rel": "self",
                        "href": f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/INV2-SANDBOX-9876-5432",
                        "method": "GET",
                    },
                    {
                        "rel": "payer-view",
                        "href": "https://www.sandbox.paypal.com/invoice/p/#SANDBOX98765432",
                        "method": "GET",
                    },
                ],
            },
        )
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["paypal_invoice_id"] == "INV2-SANDBOX-9876-5432"
        assert data["paypal_invoice_url"] == "https://www.sandbox.paypal.com/invoice/p/#SANDBOX98765432"
        assert data["status"] == "created"
        assert data["is_duplicate"] is False

    # Check PayPal Request Headers
    assert mock_create_route.called
    last_req = mock_create_route.calls.last.request
    assert last_req.headers.get("PayPal-Request-Id") == f"payflow-create-{sample_invoice.internal_id}"
    assert "Bearer SANDBOX_MOCK_ACCESS_TOKEN_ABC" in last_req.headers.get("Authorization", "")
    sent_payload = json.loads(last_req.content)
    assert "email_address" not in sent_payload["invoicer"]

    # Invariant: Database persistence verification
    inv_after = await mock_db.invoices.find_one({"internal_id": sample_invoice.internal_id})
    assert inv_after is not None
    assert inv_after["status"] == InvoiceStatus.CREATED.value
    assert inv_after["paypal_invoice_id"] == "INV2-SANDBOX-9876-5432"
    assert inv_after["paypal_invoice_url"] == "https://www.sandbox.paypal.com/invoice/p/#SANDBOX98765432"

    appr_after = await mock_db.approvals.find_one({"id": approval.id})
    assert appr_after is not None
    assert appr_after["execution_result_ref"] == "INV2-SANDBOX-9876-5432"

    # Invariant: Audit log was created
    audit_after = await mock_db.audit_logs.find_one({
        "resource_id": sample_invoice.internal_id,
        "action": "invoice.created_in_paypal",
    })
    assert audit_after is not None
    assert audit_after["metadata"]["paypal_invoice_id"] == "INV2-SANDBOX-9876-5432"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_duplicate_execution_prevented(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
    monkeypatch,
):
    """Calling creation endpoint on an invoice that already has paypal_invoice_id returns existing without re-calling PayPal."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client-id-xyz")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret-xyz")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())

    # Invoice already has PayPal references from previous execution
    sample_invoice.status = InvoiceStatus.CREATED
    sample_invoice.paypal_invoice_id = "INV2-EXISTING-1111"
    sample_invoice.paypal_invoice_url = "https://www.sandbox.paypal.com/invoice/p/#EXISTING1111"
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    # Respx route to detect if any PayPal call is made
    mock_create_route = respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices").mock(
        return_value=Response(500, json={"error": "Should not be called"})
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["paypal_invoice_id"] == "INV2-EXISTING-1111"
        assert data["is_duplicate"] is True
        assert "already been created" in data["message"]

    # Verify PayPal API was NEVER invoked
    assert not mock_create_route.called

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_safe_error_mapping_on_paypal_failure(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
    monkeypatch,
):
    """Verify PayPal API errors are mapped to safe, actionable client errors without credential leaks."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client-id-xyz")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret-xyz")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    snapshot = compute_invoice_payload_snapshot(sample_invoice)
    appr_hash = compute_payload_hash(snapshot)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=sample_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=appr_hash,
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "TOKEN_XYZ", "expires_in": 3600})
    )

    # Mock PayPal 400 error with structured detail
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices").mock(
        return_value=Response(
            400,
            json={
                "name": "INVALID_REQUEST",
                "message": "Validation error in request payload",
                "details": [
                    {
                        "field": "/detail/invoice_number",
                        "issue": "DUPLICATE_INVOICE_NUMBER",
                        "description": "Invoice number already exists.",
                    }
                ],
            },
        )
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id},
        )
        assert res.status_code == 400
        detail = res.json()["detail"]
        assert "already been used in your PayPal account" in detail
        assert "sandbox-client-secret-xyz" not in detail
        assert "TOKEN_XYZ" not in detail

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cross_user_isolation(
    mock_db: MockDatabase,
    user_a: User,
    user_b: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
):
    """User B cannot dispatch User A's invoice to PayPal."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    token_b = create_access_token(subject=user_b.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token_b}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id},
        )
        assert res.status_code == 404
        assert "Invoice not found" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_paypal_hateoas_link_id_extraction_and_creation(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
    monkeypatch,
):
    """Creating a PayPal invoice handles minimal HATEOAS 'self' link responses lacking a top-level 'id'."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client-id-xyz")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret-xyz")

    assert extract_paypal_invoice_id({
        "rel": "self",
        "href": "https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-HATEOAS-0001",
        "method": "GET",
    }) == "INV2-HATEOAS-0001"

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    snapshot = compute_invoice_payload_snapshot(sample_invoice)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=sample_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=compute_payload_hash(snapshot),
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "TOKEN_XYZ", "expires_in": 3600})
    )
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices").mock(
        return_value=Response(
            201,
            json={
                "rel": "self",
                "href": "https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-HATEOAS-0001",
                "method": "GET",
            },
        )
    )
    respx.get(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/INV2-HATEOAS-0001").mock(
        return_value=Response(
            200,
            json={
                "id": "INV2-HATEOAS-0001",
                "status": "DRAFT",
                "detail": {
                    "metadata": {
                        "recipient_view_url": "https://www.sandbox.paypal.com/invoice/p/#HATEOAS0001"
                    }
                },
            },
        )
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id, "approval_id": approval.id},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["paypal_invoice_id"] == "INV2-HATEOAS-0001"
        assert "INV2-HATEOAS-0001" in data["paypal_invoice_url"] or "HATEOAS0001" in data["paypal_invoice_url"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_paypal_duplicate_422_reconciles_matching_owner_invoice(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
    monkeypatch,
):
    """HTTP 422 DUPLICATE_INVOICE_NUMBER safely reconciles when matching user/recipient/total invoice already exists."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client-id-xyz")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret-xyz")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    snapshot = compute_invoice_payload_snapshot(sample_invoice)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=sample_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=compute_payload_hash(snapshot),
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "TOKEN_XYZ", "expires_in": 3600})
    )
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices").mock(
        return_value=Response(
            422,
            json={
                "name": "UNPROCESSABLE_ENTITY",
                "message": "The requested action could not be performed.",
                "details": [{"issue": "DUPLICATE_INVOICE_NUMBER", "description": "Invoice number is duplicate."}],
            },
        )
    )
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/search-invoices").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "INV2-RECOVERED-9999",
                        "detail": {
                            "invoice_number": sample_invoice.invoice_number,
                            "metadata": {"recipient_view_url": "https://www.sandbox.paypal.com/invoice/p/#RECOVERED9999"},
                        },
                        "invoicer": {"email_address": user_a.email},
                        "primary_recipients": [{"billing_info": {"email_address": sample_customer.email}}],
                        "amount": {"value": f"{sample_invoice.total:.2f}", "currency_code": "USD"},
                    }
                ]
            },
        )
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id, "approval_id": approval.id},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["paypal_invoice_id"] == "INV2-RECOVERED-9999"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_paypal_duplicate_422_disambiguates_cross_tenant_number(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    sample_invoice: Invoice,
    monkeypatch,
):
    """If 422 DUPLICATE_INVOICE_NUMBER belongs to another user, retry with tenant-scoped number."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "sandbox-client-id-xyz")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "sandbox-client-secret-xyz")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    sample_invoice.status = InvoiceStatus.PENDING_APPROVAL
    await mock_db.invoices.insert_one(sample_invoice.model_dump())

    snapshot = compute_invoice_payload_snapshot(sample_invoice)
    approval = Approval(
        id="appr-test-cross-tenant-dup",
        user_id=user_a.id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=sample_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=compute_payload_hash(snapshot),
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "TOKEN_XYZ", "expires_in": 3600})
    )
    mock_create = respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices").mock(
        side_effect=[
            Response(
                422,
                json={
                    "name": "UNPROCESSABLE_ENTITY",
                    "details": [{"issue": "DUPLICATE_INVOICE_NUMBER", "description": "Duplicate."}],
                },
            ),
            Response(
                201,
                json={
                    "id": "INV2-DISAMBIG-2026",
                    "links": [{"rel": "payer-view", "href": "https://www.sandbox.paypal.com/invoice/p/#INV2-DISAMBIG-2026"}],
                },
            ),
        ]
    )
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/search-invoices").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "INV2-OTHER-TENANT",
                        "detail": {"invoice_number": sample_invoice.invoice_number},
                        "invoicer": {"email_address": "other.tenant@example.com"},
                        "primary_recipients": [{"billing_info": {"email_address": "other.buyer@example.com"}}],
                        "amount": {"value": f"{sample_invoice.total:.2f}", "currency_code": "USD"},
                    }
                ]
            },
        )
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            "/api/paypal/invoices",
            json={"invoice_id": sample_invoice.internal_id, "approval_id": approval.id},
        )
        assert res.status_code == 201
        assert res.json()["paypal_invoice_id"] == "INV2-DISAMBIG-2026"

    assert mock_create.call_count == 2
    retry_payload = json.loads(mock_create.calls[1].request.content)
    assert retry_payload["detail"]["invoice_number"].startswith(f"{sample_invoice.invoice_number}-")

    app.dependency_overrides.clear()
