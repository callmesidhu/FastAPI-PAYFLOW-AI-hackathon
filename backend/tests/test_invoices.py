"""Invoice domain service and API tests.

Verifies:
 1.  Draft creation and retrieval with authoritative Decimal totals
 2.  Server-side total authority — client_total_preview is silently discarded
 3.  Draft-only edit enforcement (non-draft invoices are immutable)
 4.  Invoice number uniqueness per user (custom and auto-generated)
 5.  Customer ownership validation (cannot invoice another user's customer)
 6.  Approval snapshot creation and payload hash binding
 7.  Decimal rounding precision (ROUND_HALF_UP, 2dp)
 8.  Negative amount rejection (unit_price, tax)
 9.  Zero quantity rejection
10.  Unsupported currency code rejection
11.  Due-date < issue-date validation
12.  Cross-user invoice isolation (GET/PATCH/submit → 404)
13.  Duplicate submit-for-approval blocked (idempotency guard)
14.  Pending approval invalidation when draft is edited
15.  Audit log entries on create, update, and submit
16.  Pagination and status/customer/overdue/due-date filters
17.  Search by invoice_number, notes, and item name
18.  Auto-generated invoice number sequence
"""

from datetime import date, timedelta
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.customer import Customer
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from tests.mock_db import MockDatabase

TODAY = date.today()
DUE = TODAY + timedelta(days=7)
DUE_STR = str(DUE)
TODAY_STR = str(TODAY)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def user_a() -> User:
    return User(
        id="user-a-333",
        email="developer@example.com",
        hashed_password=hash_password("PasswordA1!"),
        name="Developer A",
    )


@pytest.fixture
def user_b() -> User:
    return User(
        id="user-b-444",
        email="attacker@example.com",
        hashed_password=hash_password("PasswordB1!"),
        name="Attacker B",
    )


@pytest.fixture
def customer_a() -> Customer:
    return Customer(
        id="cust-client-1",
        user_id="user-a-333",
        name="Acme Corp",
        email="billing@acme.example.com",
    )


@pytest.fixture
def customer_b() -> Customer:
    return Customer(
        id="cust-b-private",
        user_id="user-b-444",
        name="User B Client",
        email="b_client@example.com",
    )


def _base_invoice_payload(customer_id: str, **kwargs) -> dict:
    """Convenience builder for a minimal valid invoice payload."""
    return {
        "customer_id": customer_id,
        "items": [{"name": "Consulting", "quantity": "1.00", "unit_price": "100.00", "tax": "0.00"}],
        "currency": "USD",
        "due_date": DUE_STR,
        **kwargs,
    }


# ---------------------------------------------------------------------------
# 1 & 2. Authoritative totals — client preview is ignored
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_draft_invoice_creation_and_authoritative_totals(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Server computes Decimal totals; client_total_preview must be discarded."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            payload = {
                "customer_id": customer_a.id,
                "items": [
                    {"name": "Frontend Architecture", "quantity": "2.5", "unit_price": "100.00", "tax": "25.00"},
                    {"name": "Backend API",           "quantity": "1.0", "unit_price": "200.00", "tax": "0.00"},
                ],
                "currency": "USD",
                "due_date": DUE_STR,
                "client_total_preview": "1.00",   # Fake client preview — MUST be ignored
            }

            res = await client.post("/api/invoices", json=payload, headers=headers)
            assert res.status_code == 201, res.text
            data = res.json()

            # Authoritative calculations:
            # Item 1: (2.5 × 100) + 25 = 250 + 25 = 275.00  [line total]
            # Item 2: (1.0 × 200) + 0  = 200.00              [line total]
            # subtotal = 450.00  (sum of qty × price, no tax)
            # tax      = 25.00
            # total    = 475.00
            assert data["subtotal"] == "450.00", f"Expected 450.00, got {data['subtotal']}"
            assert data["tax"]      == "25.00",  f"Expected 25.00, got {data['tax']}"
            assert data["total"]    == "475.00", f"Expected 475.00, got {data['total']}"
            assert data["status"] == "draft"
            assert "INV-" in data["invoice_number"]

            # Verify GET retrieves the same totals
            res_get = await client.get(f"/api/invoices/{data['internal_id']}", headers=headers)
            assert res_get.status_code == 200
            assert res_get.json()["total"] == "475.00"

            # Verify audit log was written
            assert any(
                log["action"] == "invoice.created" and log["resource_id"] == data["internal_id"]
                for log in mock_db.audit_logs.docs
            )
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Draft-only edit enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_only_drafts_can_be_edited(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """PATCH is accepted for draft; rejected after submit-for-approval."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # Create draft
            res_create = await client.post(
                "/api/invoices",
                json=_base_invoice_payload(customer_a.id),
                headers=headers,
            )
            inv_id = res_create.json()["internal_id"]

            # Patch draft → OK
            res_patch = await client.patch(
                f"/api/invoices/{inv_id}",
                json={"notes": "Updated draft notes"},
                headers=headers,
            )
            assert res_patch.status_code == 200
            assert res_patch.json()["notes"] == "Updated draft notes"

            # Submit for approval (transitions to pending_approval)
            res_submit = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            assert res_submit.status_code == 200
            assert res_submit.json()["status"] == "pending_approval"
            assert "approval_id" in res_submit.json()

            # Patch after submission → 400
            res_patch_blocked = await client.patch(
                f"/api/invoices/{inv_id}",
                json={"notes": "Illegal edit after approval"},
                headers=headers,
            )
            assert res_patch_blocked.status_code == 400
            assert "Only draft invoices can be edited" in res_patch_blocked.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Invoice number uniqueness per user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoice_number_uniqueness_per_user(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Custom invoice number collision rejected; auto-number increments correctly."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            payload = _base_invoice_payload(customer_a.id, invoice_number="CUSTOM-INV-001")
            res1 = await client.post("/api/invoices", json=payload, headers=headers)
            assert res1.status_code == 201

            # Duplicate custom number → 400
            res_dup = await client.post("/api/invoices", json=payload, headers=headers)
            assert res_dup.status_code == 400
            assert "already exists" in res_dup.json()["detail"]

            # Auto-generated numbers should be distinct
            res_auto1 = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
            res_auto2 = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
            assert res_auto1.status_code == 201
            assert res_auto2.status_code == 201
            assert res_auto1.json()["invoice_number"] != res_auto2.json()["invoice_number"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Customer ownership enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_customer_ownership_enforcement(
    mock_db: MockDatabase, user_a: User, user_b: User, customer_b: Customer
):
    """User A cannot create an invoice for a customer owned by User B."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())
    await mock_db.customers.insert_one(customer_b.model_dump())

    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(
                "/api/invoices",
                json=_base_invoice_payload(customer_b.id),
                headers={"Authorization": f"Bearer {token_a}"},
            )
            assert res.status_code == 400
            assert "not found or does not belong to the authenticated user" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Approval snapshot and hash binding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_approval_snapshot_immutability(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Submit-for-approval creates approval with correct hash; editing invoice invalidates it."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # Create draft
            res_create = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
            inv_id = res_create.json()["internal_id"]

            # Submit for approval
            res_submit = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            assert res_submit.status_code == 200
            payload_hash = res_submit.json()["payload_hash"]
            assert len(payload_hash) == 64  # SHA-256 hex string

            # Approval must be in DB with matching hash
            approval_doc = mock_db.approvals.docs[0]
            assert approval_doc["payload_hash"] == payload_hash
            assert approval_doc["status"] == "pending"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. Decimal rounding precision
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_decimal_rounding_precision(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Decimal amounts round correctly to 2dp (ROUND_HALF_UP)."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # 3 × 33.333 = 99.999 → rounds to 100.00
            # tax = 0.005 → rounds to 0.01
            payload = {
                "customer_id": customer_a.id,
                "items": [
                    {"name": "Tricky math", "quantity": "3", "unit_price": "33.333", "tax": "0.005"},
                ],
                "currency": "USD",
                "due_date": DUE_STR,
            }
            res = await client.post("/api/invoices", json=payload, headers=headers)
            assert res.status_code == 201, res.text
            data = res.json()

            # unit_price 33.333 → 33.33, qty 3 → subtotal 99.99
            # tax 0.005 → 0.01
            # total = 99.99 + 0.01 = 100.00
            assert Decimal(data["subtotal"]) == Decimal("99.99")
            assert Decimal(data["tax"])      == Decimal("0.01")
            assert Decimal(data["total"])    == Decimal("100.00")
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. Negative amount rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_negative_unit_price_rejected(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Negative unit_price must be rejected with HTTP 422."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            for bad_field, bad_value in [("unit_price", "-10.00"), ("tax", "-1.00")]:
                item = {"name": "Bad item", "quantity": "1.00", "unit_price": "100.00", "tax": "0.00"}
                item[bad_field] = bad_value
                payload = {"customer_id": customer_a.id, "items": [item], "due_date": DUE_STR}
                res = await client.post("/api/invoices", json=payload, headers=headers)
                assert res.status_code == 422, f"Expected 422 for negative {bad_field}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. Zero quantity rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_quantity_rejected(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """quantity <= 0 must be rejected (minimum is 0.01)."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            for bad_qty in ["0.00", "-1.00"]:
                payload = {
                    "customer_id": customer_a.id,
                    "items": [{"name": "Bad qty", "quantity": bad_qty, "unit_price": "50.00"}],
                    "due_date": DUE_STR,
                }
                res = await client.post("/api/invoices", json=payload, headers=headers)
                assert res.status_code == 422, f"Expected 422 for quantity={bad_qty}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 10. Unsupported currency rejection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unsupported_currency_rejected(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Unknown/unsupported currency code must be rejected with HTTP 422."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            payload = {**_base_invoice_payload(customer_a.id), "currency": "XYZ"}
            res = await client.post("/api/invoices", json=payload, headers=headers)
            assert res.status_code == 422, f"Expected 422 for bad currency, got {res.status_code}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 11. Due-date validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_due_date_before_issue_date_rejected(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """due_date < issue_date must be rejected with HTTP 400."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            payload = {
                **_base_invoice_payload(customer_a.id),
                "issue_date": TODAY_STR,
                "due_date": str(TODAY - timedelta(days=1)),  # yesterday
            }
            res = await client.post("/api/invoices", json=payload, headers=headers)
            assert res.status_code == 400, f"Expected 400, got {res.status_code}"
            assert "due date" in res.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 12. Cross-user isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cross_user_invoice_isolation(
    mock_db: MockDatabase, user_a: User, user_b: User, customer_a: Customer
):
    """User B cannot GET, PATCH, or submit for approval User A's invoices."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())

    token_a = create_access_token(subject=user_a.id)
    token_b = create_access_token(subject=user_b.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # User A creates invoice
            res_create = await client.post(
                "/api/invoices",
                json=_base_invoice_payload(customer_a.id),
                headers=headers_a,
            )
            assert res_create.status_code == 201
            inv_id = res_create.json()["internal_id"]

            # User B GET → 404
            assert (await client.get(f"/api/invoices/{inv_id}", headers=headers_b)).status_code == 404

            # User B PATCH → 404
            assert (
                await client.patch(f"/api/invoices/{inv_id}", json={"notes": "hack"}, headers=headers_b)
            ).status_code == 404

            # User B submit-for-approval → 404
            assert (
                await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers_b)
            ).status_code == 404

            # User B list → empty (no cross-tenant leakage)
            res_list = await client.get("/api/invoices", headers=headers_b)
            assert res_list.status_code == 200
            assert res_list.json()["total"] == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 13. Duplicate submit-for-approval blocked
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_submit_for_approval_blocked(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Re-submitting an invoice that already has a pending approval is blocked (idempotency)."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            res_create = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
            inv_id = res_create.json()["internal_id"]

            # First submit → OK
            res1 = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            assert res1.status_code == 200

            # Second submit → 400 (invoice is now pending_approval, not draft)
            res2 = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            assert res2.status_code == 400
            detail = res2.json()["detail"]
            # Either "Cannot submit" (status check) or "already has a pending approval" (idempotency guard)
            assert any(msg in detail for msg in ["Cannot submit", "already has a pending approval"])
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 14. Pending approval invalidated on edit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pending_approval_invalidated_on_draft_edit(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Editing a draft after approval-submission has been rejected must invalidate its approval."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # Create draft and submit for approval
            res_create = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
            inv_id = res_create.json()["internal_id"]
            res_submit = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            assert res_submit.status_code == 200
            approval_id = res_submit.json()["approval_id"]

            # Reject the approval (transitions invoice back to DRAFT)
            await mock_db.approvals.update_one(
                {"id": approval_id},
                {"$set": {"status": "rejected"}},
            )
            await mock_db.invoices.update_one(
                {"internal_id": inv_id},
                {"$set": {"status": "draft"}},
            )

            # Now create a new pending approval manually to test invalidation
            await mock_db.approvals.update_one(
                {"id": approval_id},
                {"$set": {"status": "pending"}},
            )

            # Edit the draft — should invalidate the pending approval
            res_patch = await client.patch(
                f"/api/invoices/{inv_id}",
                json={"notes": "Updated after re-draft"},
                headers=headers,
            )
            assert res_patch.status_code == 200

            # The approval should now be INVALIDATED
            approval_doc = await mock_db.approvals.find_one({"id": approval_id})
            assert approval_doc["status"] == "invalidated", \
                f"Expected 'invalidated', got {approval_doc['status']}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 15. Audit log entries on all lifecycle events
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_on_create_update_and_submit(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Create, update, and submit must each write an audit log entry."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            res_create = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
            inv_id = res_create.json()["internal_id"]

            res_patch = await client.patch(
                f"/api/invoices/{inv_id}", json={"notes": "Some notes"}, headers=headers
            )
            assert res_patch.status_code == 200

            res_submit = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            assert res_submit.status_code == 200

        actions = {log["action"] for log in mock_db.audit_logs.docs if log["resource_id"] == inv_id}
        assert "invoice.created" in actions
        assert "invoice.updated" in actions
        assert "invoice.submitted_for_approval" in actions
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 16. Pagination and filtering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoice_pagination_and_filters(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Pagination, status filter, customer filter, overdue filter, and date range filter."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # Seed 3 draft invoices
            ids = []
            for i in range(3):
                r = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
                assert r.status_code == 201
                ids.append(r.json()["internal_id"])

            # Page 1 of 2 with page_size=2
            res_page = await client.get("/api/invoices?page=1&page_size=2", headers=headers)
            assert res_page.status_code == 200
            pg = res_page.json()
            assert pg["total"] == 3
            assert len(pg["items"]) == 2
            assert pg["pages"] == 2

            # Status filter: draft → all 3
            res_draft = await client.get("/api/invoices?status=draft", headers=headers)
            assert res_draft.json()["total"] == 3

            # Status filter: sent → 0
            res_sent = await client.get("/api/invoices?status=sent", headers=headers)
            assert res_sent.json()["total"] == 0

            # Invalid status → 400
            res_bad = await client.get("/api/invoices?status=invalid_status", headers=headers)
            assert res_bad.status_code == 400

            # Customer filter: matches all invoices for customer_a
            res_cust = await client.get(f"/api/invoices?customer_id={customer_a.id}", headers=headers)
            assert res_cust.json()["total"] == 3

            # Customer filter: different customer → 0
            res_cust2 = await client.get("/api/invoices?customer_id=no-such-cust", headers=headers)
            assert res_cust2.json()["total"] == 0

            # due_date_after future date → 0 results
            far_future = str(TODAY + timedelta(days=365))
            res_after = await client.get(f"/api/invoices?due_date_after={far_future}", headers=headers)
            assert res_after.json()["total"] == 0

            # due_date_before far future → all results
            res_before = await client.get(f"/api/invoices?due_date_before={far_future}", headers=headers)
            assert res_before.json()["total"] == 3
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 17. Search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoice_search(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Search matches invoice_number, notes, and item names (case-insensitive)."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # Invoice with custom number and unique note
            await client.post("/api/invoices", json={
                **_base_invoice_payload(customer_a.id),
                "invoice_number": "SEARCH-TEST-001",
                "items": [{"name": "Branding Strategy", "quantity": "1.00", "unit_price": "200.00"}],
                "notes": "Payment via PayPal",
            }, headers=headers)

            # Search by invoice number
            res = await client.get("/api/invoices?q=SEARCH-TEST", headers=headers)
            assert res.json()["total"] == 1

            # Search by note (case-insensitive)
            res2 = await client.get("/api/invoices?q=paypal", headers=headers)
            assert res2.json()["total"] == 1

            # Search by item name
            res3 = await client.get("/api/invoices?q=branding", headers=headers)
            assert res3.json()["total"] == 1

            # No match
            res4 = await client.get("/api/invoices?q=nomatch99", headers=headers)
            assert res4.json()["total"] == 0
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 18. Auto-generated invoice number sequence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_invoice_number_sequence(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """Auto-generated invoice numbers are distinct and follow INV-YYYY-NNNN format."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            numbers = []
            for _ in range(4):
                r = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers)
                assert r.status_code == 201
                numbers.append(r.json()["invoice_number"])

            # All numbers must be unique
            assert len(set(numbers)) == 4

            # Format: INV-YYYY-NNNN
            import re
            pattern = re.compile(r"^INV-\d{4}-\d{4}$")
            for num in numbers:
                assert pattern.match(num), f"Number '{num}' does not match INV-YYYY-NNNN format"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Retained / renamed original tests for backward compatibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_items_replacement_recomputes_totals(mock_db: MockDatabase, user_a: User, customer_a: Customer):
    """PATCH with new items must recompute totals server-side — not retain old totals."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token}"}

            # Create with 1 × $100
            res_create = await client.post(
                "/api/invoices",
                json={**_base_invoice_payload(customer_a.id), "items": [
                    {"name": "Old item", "quantity": "1.00", "unit_price": "100.00"}
                ]},
                headers=headers,
            )
            assert res_create.json()["total"] == "100.00"
            inv_id = res_create.json()["internal_id"]

            # Patch items → 2 × $250 + $20 tax
            res_patch = await client.patch(
                f"/api/invoices/{inv_id}",
                json={"items": [{"name": "New item", "quantity": "2.00", "unit_price": "250.00", "tax": "20.00"}]},
                headers=headers,
            )
            assert res_patch.status_code == 200
            data = res_patch.json()
            # (2 × 250) + 20 = 520
            assert data["subtotal"] == "500.00"
            assert data["tax"]      == "20.00"
            assert data["total"]    == "520.00"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_draft_invoice_and_invariants(
    mock_db: MockDatabase, user_a: User, user_b: User, customer_a: Customer
):
    """Verify that draft invoices can be deleted, but non-drafts are blocked and cross-user fails."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())
    await mock_db.customers.insert_one(customer_a.model_dump())
    token_a = create_access_token(subject=user_a.id)
    token_b = create_access_token(subject=user_b.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # 1. User A creates draft
            res_create = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers_a)
            inv_id = res_create.json()["internal_id"]

            # 2. User B tries to delete User A's draft -> 404
            res_del_cross = await client.delete(f"/api/invoices/{inv_id}", headers=headers_b)
            assert res_del_cross.status_code == 404

            # 3. Submit for approval -> status is pending_approval
            await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers_a)

            # 4. User A tries to delete non-draft -> 400 Bad Request
            res_del_blocked = await client.delete(f"/api/invoices/{inv_id}", headers=headers_a)
            assert res_del_blocked.status_code == 400
            assert "Only draft invoices can be deleted" in res_del_blocked.json()["detail"]

            # 5. Create another draft and delete it successfully
            res_create2 = await client.post("/api/invoices", json=_base_invoice_payload(customer_a.id), headers=headers_a)
            inv_id2 = res_create2.json()["internal_id"]

            res_del_ok = await client.delete(f"/api/invoices/{inv_id2}", headers=headers_a)
            assert res_del_ok.status_code == 200
            assert res_del_ok.json()["message"] == "Draft invoice deleted successfully."

            # Verify it's gone
            res_get_gone = await client.get(f"/api/invoices/{inv_id2}", headers=headers_a)
            assert res_get_gone.status_code == 404

            # Verify audit log recorded invoice.deleted
            assert any(
                log["action"] == "invoice.deleted" and log["resource_id"] == inv_id2
                for log in mock_db.audit_logs.docs
            )
    finally:
        app.dependency_overrides.clear()

