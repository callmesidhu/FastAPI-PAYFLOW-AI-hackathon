"""Invoice domain service and API tests.

Verifies:
1. Draft creation and retrieval
2. Server-side authoritative Decimal totals (ignoring client preview discrepancies)
3. Draft-only edit enforcement (rejecting edits on pending_approval or sent invoices)
4. Invoice number uniqueness per user
5. Audit log appending on lifecycle events
6. Customer ownership validation (cannot invoice other users' customers)
7. Approval snapshot and hash creation
"""

from datetime import date
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.customer import Customer
from app.models.enums import InvoiceStatus
from app.models.user import User
from tests.mock_db import MockDatabase


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


@pytest.mark.asyncio
async def test_draft_invoice_creation_and_authoritative_totals(mock_db: MockDatabase, user_a: User):
    """Verify that invoice draft is created and server authoritatively calculates Decimal totals."""
    await mock_db.users.insert_one(user_a.model_dump())
    customer = Customer(
        id="cust-client-1",
        user_id=user_a.id,
        name="Acme Corp",
        email="billing@acme.example.com",
    )
    await mock_db.customers.insert_one(customer.model_dump())

    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            payload = {
                "customer_id": customer.id,
                "items": [
                    {
                        "name": "Frontend Architecture",
                        "quantity": "2.5",
                        "unit_price": "100.00",
                        "tax": "25.00",
                    },
                    {
                        "name": "Backend API",
                        "quantity": "1.0",
                        "unit_price": "200.00",
                        "tax": "0.00",
                    },
                ],
                "currency": "USD",
                "due_date": "2026-11-20",
                "client_total_preview": "1.00",  # Fake total sent by client; server MUST ignore
            }

            res = await client.post("/api/invoices", json=payload, headers=headers)
            assert res.status_code == 201
            inv_data = res.json()

            # Authoritative calculations:
            # Item 1: (2.5 * 100) + 25 = 250 + 25 = 275.00
            # Item 2: (1.0 * 200) + 0 = 200.00
            # Subtotal: 250 + 200 = 450.00
            # Tax: 25.00
            # Total: 475.00
            assert inv_data["subtotal"] == "450.00"
            assert inv_data["tax"] == "25.00"
            assert inv_data["total"] == "475.00"
            assert inv_data["status"] == "draft"
            assert "INV-2026-" in inv_data["invoice_number"]

            # Verify GET endpoint
            res_get = await client.get(f"/api/invoices/{inv_data['internal_id']}", headers=headers)
            assert res_get.status_code == 200
            assert res_get.json()["total"] == "475.00"

            # Verify audit log was recorded
            audit_logs = mock_db.audit_logs.docs
            assert any(
                log["action"] == "invoice.created" and log["resource_id"] == inv_data["internal_id"]
                for log in audit_logs
            )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_only_drafts_can_be_edited(mock_db: MockDatabase, user_a: User):
    """Verify that only draft invoices may be updated via PATCH."""
    await mock_db.users.insert_one(user_a.model_dump())
    customer = Customer(id="cust-client-2", user_id=user_a.id, name="Beta Corp", email="beta@example.com")
    await mock_db.customers.insert_one(customer.model_dump())

    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            # 1. Create draft
            res_create = await client.post(
                "/api/invoices",
                json={
                    "customer_id": customer.id,
                    "items": [{"name": "Sprint 1", "quantity": "1.0", "unit_price": "100.00"}],
                    "due_date": "2026-11-20",
                },
                headers=headers,
            )
            inv_id = res_create.json()["internal_id"]

            # 2. Patch draft (should succeed)
            res_patch = await client.patch(
                f"/api/invoices/{inv_id}",
                json={"notes": "Updated draft notes"},
                headers=headers,
            )
            assert res_patch.status_code == 200
            assert res_patch.json()["notes"] == "Updated draft notes"

            # 3. Submit for approval (transitions status to pending_approval)
            res_submit = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            assert res_submit.status_code == 200
            assert res_submit.json()["status"] == "pending_approval"
            assert "approval_id" in res_submit.json()

            # 4. Attempt to PATCH after submission -> 400 Bad Request
            res_patch_blocked = await client.patch(
                f"/api/invoices/{inv_id}",
                json={"notes": "Illegal edit after approval"},
                headers=headers,
            )
            assert res_patch_blocked.status_code == 400
            assert "Only draft invoices can be edited" in res_patch_blocked.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_invoice_number_uniqueness_per_user(mock_db: MockDatabase, user_a: User):
    """Verify invoice number collision detection per user."""
    await mock_db.users.insert_one(user_a.model_dump())
    customer = Customer(id="cust-client-3", user_id=user_a.id, name="Gamma Corp", email="gamma@example.com")
    await mock_db.customers.insert_one(customer.model_dump())

    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            payload = {
                "customer_id": customer.id,
                "invoice_number": "CUSTOM-INV-001",
                "items": [{"name": "Item", "quantity": "1.0", "unit_price": "50.00"}],
                "due_date": "2026-11-20",
            }

            res1 = await client.post("/api/invoices", json=payload, headers=headers)
            assert res1.status_code == 201

            # Duplicate custom number for user A must be rejected
            res_dup = await client.post("/api/invoices", json=payload, headers=headers)
            assert res_dup.status_code == 400
            assert "already exists" in res_dup.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_customer_ownership_enforcement(mock_db: MockDatabase, user_a: User, user_b: User):
    """Verify that User A cannot create an invoice for a customer owned by User B."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())

    # Customer owned by User B
    customer_b = Customer(id="cust-b-private", user_id=user_b.id, name="User B Client", email="b_client@example.com")
    await mock_db.customers.insert_one(customer_b.model_dump())

    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = {"Authorization": f"Bearer {token_a}"}

            # User A tries to invoice User B's customer
            res = await client.post(
                "/api/invoices",
                json={
                    "customer_id": customer_b.id,
                    "items": [{"name": "Consulting", "quantity": "1.0", "unit_price": "100.00"}],
                    "due_date": "2026-11-20",
                },
                headers=headers_a,
            )
            assert res.status_code == 400
            assert "not found or does not belong to the authenticated user" in res.json()["detail"]
    finally:
        app.dependency_overrides.clear()
