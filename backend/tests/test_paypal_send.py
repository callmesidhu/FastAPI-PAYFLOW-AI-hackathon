"""PayPal Invoice Send & Timeout Reconciliation Tests (Prompt 16).

Verifies:
1. Only approved invoices can be sent via PayPal Invoicing API v2.
2. Rejected or unapproved invoices are rejected.
3. Post-approval payload mutations invalidate the approval (HTTP 409).
4. Duplicate send requests are prevented safely without re-calling PayPal.
5. Timeout / unknown outcome reconciliation via GET /v2/invoicing/invoices/{id}.
6. Timeout without PayPal confirmation fails safely and does NOT report false success.
7. Atomic 'approve-and-send' workflow.
8. Multi-tenant user isolation.
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.approval import Approval, compute_payload_hash
from app.models.customer import Customer
from app.models.enums import ActionType, ApprovalStatus, InvoiceStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.services.approval_service import compute_invoice_payload_snapshot
from app.services.paypal_service import paypal_service
from tests.mock_db import MockDatabase

settings = get_settings()
TODAY = date.today()
DUE = TODAY + timedelta(days=14)


@pytest.fixture(autouse=True)
def reset_paypal_token():
    paypal_service._cached_token = None
    yield
    paypal_service._cached_token = None


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def user_a() -> User:
    return User(
        id="user-send-a",
        email="owner.send@example.com",
        hashed_password=hash_password("Pass123!"),
        name="Morgan Sender",
        business_name="Sender Studio",
    )


@pytest.fixture
def user_b() -> User:
    return User(
        id="user-send-b",
        email="other.send@example.com",
        hashed_password=hash_password("Pass123!"),
        name="Jordan Lee",
        business_name="Lee Studio",
    )


@pytest.fixture
def sample_customer(user_a: User) -> Customer:
    return Customer(
        id="cust-send-1",
        user_id=user_a.id,
        name="David Sterling",
        email="david@sterling.io",
        company="Sterling Capital",
    )


@pytest.fixture
def created_invoice(user_a: User, sample_customer: Customer) -> Invoice:
    return Invoice(
        internal_id="inv-send-1",
        user_id=user_a.id,
        customer_id=sample_customer.id,
        invoice_number="INV-2026-0099",
        issue_date=TODAY,
        due_date=DUE,
        status=InvoiceStatus.CREATED,
        currency=SupportedCurrency.USD,
        paypal_invoice_id="INV2-SEND-9999",
        paypal_invoice_url="https://www.sandbox.paypal.com/invoice/p/#SEND9999",
        items=[
            InvoiceItem(
                name="Quarterly Advisory Retainer",
                quantity=Decimal("1.00"),
                unit_price=Decimal("4500.00"),
                tax=Decimal("0.00"),
            )
        ],
    )


# ==============================================================================
# Unit & Integration Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_send_invoice_rejected_approval(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    created_invoice: Invoice,
):
    """Invoice without an approved Approval record cannot be sent (400)."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(created_invoice.model_dump())

    # Create a REJECTED approval record
    snapshot = compute_invoice_payload_snapshot(created_invoice)
    appr_hash = compute_payload_hash(snapshot)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.SEND_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=created_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=appr_hash,
        status=ApprovalStatus.REJECTED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(f"/api/paypal/invoices/{created_invoice.internal_id}/send")
        assert res.status_code == 400
        assert "Approval status is 'rejected'. Must be 'approved'" in res.json()["detail"]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_send_invoice_tampered_payload_rejected(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    created_invoice: Invoice,
):
    """Tampering with invoice contents after approval invalidates the approval and rejects send with 409."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())

    snapshot = compute_invoice_payload_snapshot(created_invoice)
    initial_hash = compute_payload_hash(snapshot)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.SEND_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=created_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=initial_hash,
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    # Alter unit price in DB
    tampered_invoice = created_invoice.model_copy(deep=True)
    tampered_invoice.items[0].unit_price = Decimal("9999.00")
    tampered_invoice.compute_totals()
    await mock_db.invoices.insert_one(tampered_invoice.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(f"/api/paypal/invoices/{created_invoice.internal_id}/send")
        assert res.status_code == 409
        assert "modified after approval was granted" in res.json()["detail"]

    # Verify approval invalidated in DB
    appr_after = await mock_db.approvals.find_one({"id": approval.id})
    assert appr_after is not None
    assert appr_after["status"] == ApprovalStatus.INVALIDATED.value

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_send_invoice_success(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    created_invoice: Invoice,
    monkeypatch,
):
    """Successful send dispatches via PayPal Invoicing, transitions to 'sent', and logs audit entry."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "mock-send-client-id")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "mock-send-client-secret")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(created_invoice.model_dump())

    snapshot = compute_invoice_payload_snapshot(created_invoice)
    appr_hash = compute_payload_hash(snapshot)
    approval = Approval(
        id="appr-send-ok",
        user_id=user_a.id,
        action_type=ActionType.SEND_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=created_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=appr_hash,
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    # Mock PayPal token and send endpoint
    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "ACCESS_TOKEN_SEND_1", "expires_in": 3600})
    )
    mock_send = respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/{created_invoice.paypal_invoice_id}/send").mock(
        return_value=Response(200, json={"links": [{"rel": "self", "href": "..."}]})
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(
            f"/api/paypal/invoices/{created_invoice.internal_id}/send",
            json={"note": "Thank you for your business!"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "sent"
        assert data["paypal_invoice_id"] == created_invoice.paypal_invoice_id
        assert data["is_duplicate"] is False
        assert "delivered to customer" in data["message"]

    assert mock_send.called
    req_body = mock_send.calls.last.request.read().decode("utf-8")
    assert "Thank you for your business!" in req_body

    # Invariant: Database persistence verification
    inv_after = await mock_db.invoices.find_one({"internal_id": created_invoice.internal_id})
    assert inv_after is not None
    assert inv_after["status"] == InvoiceStatus.SENT.value
    assert inv_after["sent_at"] is not None

    audit_after = await mock_db.audit_logs.find_one({
        "resource_id": created_invoice.internal_id,
        "action": "invoice.sent_via_paypal",
    })
    assert audit_after is not None
    assert audit_after["metadata"]["paypal_invoice_id"] == created_invoice.paypal_invoice_id

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_send_invoice_duplicate_send_prevention(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    created_invoice: Invoice,
    monkeypatch,
):
    """Calling send on an invoice that is already sent returns existing state with is_duplicate=True without calling PayPal."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "mock-send-client-id")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "mock-send-client-secret")

    # Already in SENT state
    from datetime import datetime, timezone
    created_invoice.status = InvoiceStatus.SENT
    created_invoice.sent_at = datetime.now(timezone.utc)
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(created_invoice.model_dump())

    mock_send = respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/{created_invoice.paypal_invoice_id}/send").mock(
        return_value=Response(500, json={"error": "Must not be called"})
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(f"/api/paypal/invoices/{created_invoice.internal_id}/send")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "sent"
        assert data["is_duplicate"] is True
        assert "Duplicate send prevented" in data["message"]

    assert not mock_send.called
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_send_invoice_timeout_with_reconciliation(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    created_invoice: Invoice,
    monkeypatch,
):
    """If send request times out, service probes GET /invoices/{id}. If PayPal reports SENT, success is reconciled."""
    import httpx

    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "mock-send-client-id")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "mock-send-client-secret")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(created_invoice.model_dump())

    snapshot = compute_invoice_payload_snapshot(created_invoice)
    appr_hash = compute_payload_hash(snapshot)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.SEND_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=created_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=appr_hash,
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "ACCESS_TOKEN_SEND_2", "expires_in": 3600})
    )

    # 1. POST /send raises network TimeoutException
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/{created_invoice.paypal_invoice_id}/send").mock(
        side_effect=httpx.TimeoutException("Read timed out on socket")
    )

    # 2. GET /invoices/{id} returns confirmed status SENT
    respx.get(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/{created_invoice.paypal_invoice_id}").mock(
        return_value=Response(
            200,
            json={
                "id": created_invoice.paypal_invoice_id,
                "status": "SENT",
                "detail": {"metadata": {"recipient_view_url": "https://www.sandbox.paypal.com/invoice/p/#CONFIRMED"}},
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
        res = await client.post(f"/api/paypal/invoices/{created_invoice.internal_id}/send")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "sent"

    # Verify status updated in DB and audit recorded reconciliation
    inv_after = await mock_db.invoices.find_one({"internal_id": created_invoice.internal_id})
    assert inv_after is not None
    assert inv_after["status"] == InvoiceStatus.SENT.value

    audit_after = await mock_db.audit_logs.find_one({"resource_id": created_invoice.internal_id})
    assert audit_after is not None
    assert audit_after["metadata"]["reconciled"] is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_send_invoice_timeout_unconfirmed_fails_safely(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    created_invoice: Invoice,
    monkeypatch,
):
    """If send times out and GET status check shows invoice is still DRAFT, fail safely and do not report success."""
    import httpx

    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "mock-send-client-id")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "mock-send-client-secret")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(created_invoice.model_dump())

    snapshot = compute_invoice_payload_snapshot(created_invoice)
    appr_hash = compute_payload_hash(snapshot)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.SEND_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=created_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=appr_hash,
        status=ApprovalStatus.APPROVED,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "ACCESS_TOKEN_SEND_3", "expires_in": 3600})
    )

    # 1. POST /send raises network TimeoutException
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/{created_invoice.paypal_invoice_id}/send").mock(
        side_effect=httpx.TimeoutException("Read timed out on socket")
    )

    # 2. GET /invoices/{id} returns status DRAFT (not sent)
    respx.get(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/{created_invoice.paypal_invoice_id}").mock(
        return_value=Response(
            200,
            json={
                "id": created_invoice.paypal_invoice_id,
                "status": "DRAFT",
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
        res = await client.post(f"/api/paypal/invoices/{created_invoice.internal_id}/send")
        assert res.status_code == 400
        assert "not confirmed as sent" in res.json()["detail"]

    # Invariant: Invoice in DB must remain CREATED, not prematurely marked SENT
    inv_after = await mock_db.invoices.find_one({"internal_id": created_invoice.internal_id})
    assert inv_after is not None
    assert inv_after["status"] == InvoiceStatus.CREATED.value

    app.dependency_overrides.clear()


@pytest.mark.asyncio
@respx.mock
async def test_send_invoice_atomic_approve_and_send(
    mock_db: MockDatabase,
    user_a: User,
    sample_customer: Customer,
    created_invoice: Invoice,
    monkeypatch,
):
    """The /approve-and-send endpoint approves pending action and executes send atomically."""
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "mock-send-client-id")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "mock-send-client-secret")

    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(created_invoice.model_dump())

    # Pending approval
    snapshot = compute_invoice_payload_snapshot(created_invoice)
    appr_hash = compute_payload_hash(snapshot)
    approval = Approval(
        user_id=user_a.id,
        action_type=ActionType.SEND_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=created_invoice.internal_id,
        payload_snapshot=snapshot,
        payload_hash=appr_hash,
        status=ApprovalStatus.PENDING,
    )
    await mock_db.approvals.insert_one(approval.model_dump())

    respx.post(f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "ACCESS_TOKEN_SEND_4", "expires_in": 3600})
    )
    respx.post(f"{settings.PAYPAL_BASE_URL}/v2/invoicing/invoices/{created_invoice.paypal_invoice_id}/send").mock(
        return_value=Response(200, json={"links": []})
    )

    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        res = await client.post(f"/api/paypal/invoices/{created_invoice.internal_id}/approve-and-send")
        assert res.status_code == 200
        assert res.json()["status"] == "sent"

    # Verify approval is now APPROVED
    appr_after = await mock_db.approvals.find_one({"id": approval.id})
    assert appr_after is not None
    assert appr_after["status"] == ApprovalStatus.APPROVED.value

    # Verify invoice is now SENT
    inv_after = await mock_db.invoices.find_one({"internal_id": created_invoice.internal_id})
    assert inv_after is not None
    assert inv_after["status"] == InvoiceStatus.SENT.value

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cross_user_isolation_on_send(
    mock_db: MockDatabase,
    user_a: User,
    user_b: User,
    sample_customer: Customer,
    created_invoice: Invoice,
):
    """User B cannot send User A's invoice."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())
    await mock_db.customers.insert_one(sample_customer.model_dump())
    await mock_db.invoices.insert_one(created_invoice.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    token_b = create_access_token(subject=user_b.id)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token_b}"},
    ) as client:
        res = await client.post(f"/api/paypal/invoices/{created_invoice.internal_id}/send")
        assert res.status_code == 404
        assert "Invoice not found" in res.json()["detail"]

    app.dependency_overrides.clear()
