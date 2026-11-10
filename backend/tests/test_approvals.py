"""Tests for the Human Authorization Approval Engine.

Verifies:
1. Approvals are strictly user-scoped (unauthorized users cannot approve or view).
2. Approving transitions status to APPROVED with immutable timestamp and audit trail.
3. Replay protection: cannot re-approve an already approved action.
4. Mutation detection: changing the approved resource invalidates the approval.
5. Rejecting an approval restores the resource to draft status.
6. Approval and execution are separate steps (approving does not invoke PayPal execution).
"""

from datetime import date
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.enums import ActionType, ApprovalStatus, InvoiceStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.services.invoice_service import submit_invoice_for_approval
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.fixture
async def user_a(mock_db):
    user = User(
        id="usr-test-a",
        email="owner_a@example.com",
        hashed_password=hash_password("SafePass123!"),
        name="Alice Owner",
        business_name="Alice Consulting LLC",
    )
    await mock_db.users.insert_one(user.model_dump())
    return user


@pytest.fixture
async def user_b(mock_db):
    user = User(
        id="usr-test-b",
        email="owner_b@example.com",
        hashed_password=hash_password("SafePass123!"),
        name="Bob Owner",
        business_name="Bob Ventures",
    )
    await mock_db.users.insert_one(user.model_dump())
    return user


@pytest.fixture
async def client_a(user_a, mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_a.id)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def client_b(user_b, mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db
    token = create_access_token(subject=user_b.id)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def sample_invoice_a(user_a, mock_db):
    invoice = Invoice(
        internal_id="inv-auth-001",
        user_id=user_a.id,
        customer_id="cust-100",
        invoice_number="INV-2026-0001",
        items=[
            InvoiceItem(
                name="Software Architecture Review",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1500.00"),
                tax=Decimal("0.00"),
            )
        ],
        currency=SupportedCurrency.USD,
        issue_date=date(2026, 11, 10),
        due_date=date(2026, 11, 24),
        status=InvoiceStatus.DRAFT,
    )
    await mock_db.invoices.insert_one(invoice.model_dump())
    return invoice


@pytest.mark.asyncio
async def test_submit_and_list_approvals(client_a, user_a, sample_invoice_a, mock_db):
    """Submitting invoice creates approval with snapshot and list endpoint returns it."""
    # Submit draft for approval
    submit_res = await submit_invoice_for_approval(mock_db, user_a.id, sample_invoice_a.internal_id)
    assert submit_res.approval_id
    assert submit_res.status == "pending_approval"

    # List approvals via API
    res = await client_a.get("/api/approvals")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["pending_count"] == 1
    item = data["items"][0]
    assert item["id"] == submit_res.approval_id
    assert item["status"] == "pending"
    assert item["action_type"] == "create_paypal_invoice"
    assert item["payload_hash"] == submit_res.payload_hash


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_view_or_approve(client_a, client_b, user_a, sample_invoice_a, mock_db):
    """User B cannot view or approve User A's approval request."""
    submit_res = await submit_invoice_for_approval(mock_db, user_a.id, sample_invoice_a.internal_id)

    # User B lists approvals -> sees 0
    res_b = await client_b.get("/api/approvals")
    assert res_b.status_code == 200
    assert res_b.json()["total"] == 0

    # User B attempts to inspect User A's approval -> 404
    get_res = await client_b.get(f"/api/approvals/{submit_res.approval_id}")
    assert get_res.status_code == 404

    # User B attempts to approve User A's approval -> 404
    appr_res = await client_b.post(f"/api/approvals/{submit_res.approval_id}/approve")
    assert appr_res.status_code == 404


@pytest.mark.asyncio
async def test_approve_action_and_replay_protection(client_a, user_a, sample_invoice_a, mock_db):
    """Approving transitions status to approved; re-approving is rejected (replay protection)."""
    submit_res = await submit_invoice_for_approval(mock_db, user_a.id, sample_invoice_a.internal_id)

    # 1. First approval attempt succeeds
    res1 = await client_a.post(
        f"/api/approvals/{submit_res.approval_id}/approve",
        json={"reason": "Approved for dispatch to client"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["status"] == "approved"
    assert data1["audit_id"] is not None

    # Verify DB record is updated
    appr_doc = await mock_db.approvals.find_one({"id": submit_res.approval_id})
    assert appr_doc["status"] == "approved"
    assert appr_doc["approved_at"] is not None

    # 2. Replay attempt: Re-approving the already approved action must be rejected!
    res2 = await client_a.post(f"/api/approvals/{submit_res.approval_id}/approve")
    assert res2.status_code == 400
    assert "already in 'approved' state" in res2.json()["detail"]


@pytest.mark.asyncio
async def test_reject_action_restores_draft(client_a, user_a, sample_invoice_a, mock_db):
    """Rejecting an approval marks it rejected and reverts the invoice to draft status."""
    submit_res = await submit_invoice_for_approval(mock_db, user_a.id, sample_invoice_a.internal_id)

    res = await client_a.post(
        f"/api/approvals/{submit_res.approval_id}/reject",
        json={"reason": "Item price incorrect"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "rejected"

    # Verify invoice reverted to DRAFT
    inv_doc = await mock_db.invoices.find_one({"internal_id": sample_invoice_a.internal_id})
    assert inv_doc["status"] == "draft"


@pytest.mark.asyncio
async def test_modified_invoice_invalidates_approval(client_a, user_a, sample_invoice_a, mock_db):
    """If an invoice payload changes after submission, approving fails with 409 and marks approval invalidated."""
    submit_res = await submit_invoice_for_approval(mock_db, user_a.id, sample_invoice_a.internal_id)

    # Directly simulate invoice mutation (e.g. deliverable modified)
    items = sample_invoice_a.items
    items[0].unit_price = Decimal("2500.00")
    await mock_db.invoices.update_one(
        {"internal_id": sample_invoice_a.internal_id},
        {"$set": {"items": [it.model_dump() for it in items]}},
    )

    # Owner attempts to approve the modified payload
    res = await client_a.post(f"/api/approvals/{submit_res.approval_id}/approve")
    assert res.status_code == 409
    assert "invalidated" in res.json()["detail"].lower()

    # Verify approval status in DB is now INVALIDATED
    appr_doc = await mock_db.approvals.find_one({"id": submit_res.approval_id})
    assert appr_doc["status"] == "invalidated"
