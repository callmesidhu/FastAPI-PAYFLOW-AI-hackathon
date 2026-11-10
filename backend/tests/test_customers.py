"""Customer management API and business logic tests.

Verifies:
1. Customer CRUD endpoints
2. Deduplication per user
3. Pagination and search
4. Multi-tenant ownership isolation
5. Protection preventing deletion of customers with linked invoices
"""

import pytest
from httpx import ASGITransport, AsyncClient
from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.user import User
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def user_a() -> User:
    return User(
        id="user-a-111",
        email="owner.a@example.com",
        hashed_password=hash_password("PasswordA1!"),
        name="Owner A",
    )


@pytest.fixture
def user_b() -> User:
    return User(
        id="user-b-222",
        email="owner.b@example.com",
        hashed_password=hash_password("PasswordB1!"),
        name="Owner B",
    )


@pytest.mark.asyncio
async def test_customer_create_and_deduplication(mock_db: MockDatabase, user_a: User, user_b: User):
    """Verify customer creation and per-user email deduplication."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())

    token_a = create_access_token(subject=user_a.id)
    token_b = create_access_token(subject=user_b.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            customer_payload = {
                "name": "Wayne Enterprises",
                "email": "bruce@wayne.example.com",
                "company": "Wayne Enterprises Inc",
                "billing_address": {
                    "city": "Gotham",
                    "state": "NJ",
                    "country_code": "US",
                },
                "notes": "Net-30 terms",
            }

            # 1. User A creates customer
            res1 = await client.post("/api/customers", json=customer_payload, headers=headers_a)
            assert res1.status_code == 201
            cust_data = res1.json()
            assert cust_data["name"] == "Wayne Enterprises"
            assert cust_data["user_id"] == user_a.id

            # 2. User A attempts duplicate with same email -> 400 Bad Request
            res_dup = await client.post("/api/customers", json=customer_payload, headers=headers_a)
            assert res_dup.status_code == 400
            assert "already exists" in res_dup.json()["detail"]

            # 3. User B CAN create customer with that same email (isolation)
            res_b = await client.post("/api/customers", json=customer_payload, headers=headers_b)
            assert res_b.status_code == 201
            assert res_b.json()["user_id"] == user_b.id
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_customer_pagination_and_search(mock_db: MockDatabase, user_a: User):
    """Verify pagination controls and search filtering by name/email/company."""
    await mock_db.users.insert_one(user_a.model_dump())
    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            # Seed 3 customers
            customers = [
                {"name": "Alice Wonderland", "email": "alice@example.com", "company": "Rabbit Hole LLC"},
                {"name": "Bob Builder", "email": "bob@example.com", "company": "Construction Co"},
                {"name": "Charlie Chocolate", "email": "charlie@example.com", "company": "Wonka Factory"},
            ]
            for c in customers:
                res = await client.post("/api/customers", json=c, headers=headers)
                assert res.status_code == 201

            # Test pagination: page 1 with page_size 2
            res_page = await client.get("/api/customers?page=1&page_size=2", headers=headers)
            assert res_page.status_code == 200
            page_data = res_page.json()
            assert page_data["total"] == 3
            assert len(page_data["items"]) == 2
            assert page_data["page"] == 1
            assert page_data["pages"] == 2

            # Test search by name
            res_search = await client.get("/api/customers?q=Wonka", headers=headers)
            assert res_search.status_code == 200
            search_data = res_search.json()
            assert search_data["total"] == 1
            assert search_data["items"][0]["company"] == "Wonka Factory"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cross_user_customer_isolation(mock_db: MockDatabase, user_a: User, user_b: User):
    """Verify User B cannot read, update, or delete User A's customers."""
    await mock_db.users.insert_one(user_a.model_dump())
    await mock_db.users.insert_one(user_b.model_dump())

    token_a = create_access_token(subject=user_a.id)
    token_b = create_access_token(subject=user_b.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers_a = {"Authorization": f"Bearer {token_a}"}
            headers_b = {"Authorization": f"Bearer {token_b}"}

            # User A creates a customer
            res_create = await client.post(
                "/api/customers",
                json={"name": "Confidential Client", "email": "secret@client.example.com"},
                headers=headers_a,
            )
            cust_id = res_create.json()["id"]

            # User B attempts to GET -> 404 Not Found
            res_get = await client.get(f"/api/customers/{cust_id}", headers=headers_b)
            assert res_get.status_code == 404

            # User B attempts to PATCH -> 404 Not Found
            res_patch = await client.patch(
                f"/api/customers/{cust_id}",
                json={"name": "Hacked Name"},
                headers=headers_b,
            )
            assert res_patch.status_code == 404

            # User B attempts to DELETE -> 404 Not Found
            res_delete = await client.delete(f"/api/customers/{cust_id}", headers=headers_b)
            assert res_delete.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_customer_deletion_protection_with_linked_invoices(mock_db: MockDatabase, user_a: User):
    """Verify that a customer with linked invoices cannot be destructively removed."""
    await mock_db.users.insert_one(user_a.model_dump())
    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            # Create customer
            res_cust = await client.post(
                "/api/customers",
                json={"name": "Client With Invoice", "email": "client.invoice@example.com"},
                headers=headers,
            )
            cust_id = res_cust.json()["id"]

            # Add mock linked invoice to invoices collection
            linked_invoice = {
                "internal_id": "inv-linked-123",
                "user_id": user_a.id,
                "customer_id": cust_id,
                "invoice_number": "INV-2026-001",
                "total": "500.00",
                "status": "sent",
            }
            await mock_db.invoices.insert_one(linked_invoice)

            # Invariant: Attempting to delete customer with linked invoice must be rejected
            res_del_blocked = await client.delete(f"/api/customers/{cust_id}", headers=headers)
            assert res_del_blocked.status_code == 400
            assert "linked to 1 invoice(s)" in res_del_blocked.json()["detail"]

            # Remove linked invoice
            mock_db.invoices.docs.clear()

            # Now deletion succeeds (customer is archived)
            res_del_ok = await client.delete(f"/api/customers/{cust_id}", headers=headers)
            assert res_del_ok.status_code == 200
            assert res_del_ok.json()["message"] == "Customer archived successfully."
    finally:
        app.dependency_overrides.clear()
