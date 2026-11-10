"""Customer management API and business logic tests.

Verifies:
1.  Customer CRUD endpoints — create, read, update, archive
2.  Email deduplication per authenticated user
3.  Pagination controls and page calculation
4.  Search filtering by name, email, and company
5.  Stable multi-field sorting (sort_by + sort_order)
6.  Multi-tenant ownership isolation (cross-user 404 enforcement)
7.  Protection preventing archive of customers with linked invoices
8.  Archive flag behavior — archived customers hidden by default, accessible via include_archived
9.  Unauthenticated request rejection (401)
10. Invalid email format validation (422)
11. Update deduplication — email conflict with another customer
12. invoice_count field in CustomerResponse
"""

import pytest
from httpx import ASGITransport, AsyncClient
from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password
from app.db.mongodb import get_db
from app.main import app
from app.models.user import User
from tests.mock_db import MockDatabase


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 1. Create + deduplication
# ---------------------------------------------------------------------------

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

            # 1a. User A creates customer → 201 with correct fields
            res1 = await client.post("/api/customers", json=customer_payload, headers=headers_a)
            assert res1.status_code == 201
            cust_data = res1.json()
            assert cust_data["name"] == "Wayne Enterprises"
            assert cust_data["user_id"] == user_a.id
            assert cust_data["is_active"] is True
            assert cust_data["invoice_count"] == 0
            assert "id" in cust_data
            assert "created_at" in cust_data
            assert "updated_at" in cust_data

            # 1b. User A duplicate with same email → 400
            res_dup = await client.post("/api/customers", json=customer_payload, headers=headers_a)
            assert res_dup.status_code == 400
            assert "already exists" in res_dup.json()["detail"]

            # 1c. User B CAN create customer with that same email (per-user isolation)
            res_b = await client.post("/api/customers", json=customer_payload, headers=headers_b)
            assert res_b.status_code == 201
            assert res_b.json()["user_id"] == user_b.id
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 2. Pagination and search
# ---------------------------------------------------------------------------

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

            # Test pagination: page 1 with page_size=2
            res_page = await client.get("/api/customers?page=1&page_size=2", headers=headers)
            assert res_page.status_code == 200
            page_data = res_page.json()
            assert page_data["total"] == 3
            assert len(page_data["items"]) == 2
            assert page_data["page"] == 1
            assert page_data["pages"] == 2

            # Test page 2
            res_page2 = await client.get("/api/customers?page=2&page_size=2", headers=headers)
            assert res_page2.status_code == 200
            assert len(res_page2.json()["items"]) == 1

            # Search by company name
            res_search = await client.get("/api/customers?q=Wonka", headers=headers)
            assert res_search.status_code == 200
            search_data = res_search.json()
            assert search_data["total"] == 1
            assert search_data["items"][0]["company"] == "Wonka Factory"

            # Search by partial email
            res_email = await client.get("/api/customers?q=alice", headers=headers)
            assert res_email.status_code == 200
            assert res_email.json()["total"] == 1
            assert res_email.json()["items"][0]["email"] == "alice@example.com"

            # Search by partial name
            res_name = await client.get("/api/customers?q=Bob", headers=headers)
            assert res_name.status_code == 200
            assert res_name.json()["total"] == 1
            assert res_name.json()["items"][0]["name"] == "Bob Builder"

            # Empty search matches all
            res_all = await client.get("/api/customers", headers=headers)
            assert res_all.status_code == 200
            assert res_all.json()["total"] == 3
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Sorting
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_customer_sorting(mock_db: MockDatabase, user_a: User):
    """Verify stable sorting by name asc/desc and created_at desc."""
    await mock_db.users.insert_one(user_a.model_dump())
    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            for name, email in [
                ("Zara Doe", "zara@example.com"),
                ("Alice Doe", "alice@example.com"),
                ("Mia Doe", "mia@example.com"),
            ]:
                r = await client.post("/api/customers", json={"name": name, "email": email}, headers=headers)
                assert r.status_code == 201

            # Sort by name ascending
            res_asc = await client.get("/api/customers?sort_by=name&sort_order=asc", headers=headers)
            assert res_asc.status_code == 200
            names_asc = [c["name"] for c in res_asc.json()["items"]]
            assert names_asc == sorted(names_asc), "Items must be in ascending name order"

            # Sort by name descending
            res_desc = await client.get("/api/customers?sort_by=name&sort_order=desc", headers=headers)
            assert res_desc.status_code == 200
            names_desc = [c["name"] for c in res_desc.json()["items"]]
            assert names_desc == sorted(names_desc, reverse=True), "Items must be in descending name order"

            # Response envelope reflects requested sort
            assert res_asc.json()["sort_by"] == "name"
            assert res_asc.json()["sort_order"] == "asc"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. Cross-user isolation
# ---------------------------------------------------------------------------

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
            assert res_create.status_code == 201
            cust_id = res_create.json()["id"]

            # User B GET → 404
            res_get = await client.get(f"/api/customers/{cust_id}", headers=headers_b)
            assert res_get.status_code == 404

            # User B PATCH → 404
            res_patch = await client.patch(
                f"/api/customers/{cust_id}",
                json={"name": "Hacked Name"},
                headers=headers_b,
            )
            assert res_patch.status_code == 404

            # User B DELETE → 404
            res_delete = await client.delete(f"/api/customers/{cust_id}", headers=headers_b)
            assert res_delete.status_code == 404

            # User A's list must only show own customers
            res_list = await client.get("/api/customers", headers=headers_a)
            assert res_list.status_code == 200
            assert all(c["user_id"] == user_a.id for c in res_list.json()["items"])
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 5. Invoice-linked deletion protection
# ---------------------------------------------------------------------------

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
            assert res_cust.status_code == 201
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

            # Attempting to archive customer with linked invoice → 400
            res_del_blocked = await client.delete(f"/api/customers/{cust_id}", headers=headers)
            assert res_del_blocked.status_code == 400
            assert "linked to 1 invoice(s)" in res_del_blocked.json()["detail"]

            # Remove linked invoice
            mock_db.invoices.docs.clear()

            # Archive succeeds now
            res_del_ok = await client.delete(f"/api/customers/{cust_id}", headers=headers)
            assert res_del_ok.status_code == 200
            body = res_del_ok.json()
            assert body["message"] == "Customer archived successfully."
            assert body["id"] == cust_id
            assert body["is_active"] is False
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 6. Archive flag and visibility
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archived_customer_hidden_by_default_accessible_via_flag(mock_db: MockDatabase, user_a: User):
    """Archived customers must be hidden from default listing but visible with include_archived=true."""
    await mock_db.users.insert_one(user_a.model_dump())
    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            # Create two customers
            res1 = await client.post(
                "/api/customers",
                json={"name": "Active Customer", "email": "active@example.com"},
                headers=headers,
            )
            res2 = await client.post(
                "/api/customers",
                json={"name": "To Archive", "email": "archive@example.com"},
                headers=headers,
            )
            assert res1.status_code == 201
            assert res2.status_code == 201
            cust_id2 = res2.json()["id"]

            # Archive the second customer
            res_del = await client.delete(f"/api/customers/{cust_id2}", headers=headers)
            assert res_del.status_code == 200

            # Default list → only active, 1 record
            res_list = await client.get("/api/customers", headers=headers)
            assert res_list.status_code == 200
            assert res_list.json()["total"] == 1
            assert res_list.json()["items"][0]["name"] == "Active Customer"

            # With include_archived=true → 2 records
            res_all = await client.get("/api/customers?include_archived=true", headers=headers)
            assert res_all.status_code == 200
            assert res_all.json()["total"] == 2

            # GET by ID: archived customer returns 404 by default
            res_get_archived = await client.get(f"/api/customers/{cust_id2}", headers=headers)
            assert res_get_archived.status_code == 404

            # GET by ID with include_archived=true → 200 with is_active=false
            res_get_incl = await client.get(
                f"/api/customers/{cust_id2}?include_archived=true", headers=headers
            )
            assert res_get_incl.status_code == 200
            assert res_get_incl.json()["is_active"] is False
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 7. Update endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_customer_update_partial_and_email_deduplication(mock_db: MockDatabase, user_a: User):
    """Verify partial update and email deduplication on update."""
    await mock_db.users.insert_one(user_a.model_dump())
    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            # Create two customers
            res1 = await client.post(
                "/api/customers",
                json={"name": "Client A", "email": "clienta@example.com"},
                headers=headers,
            )
            res2 = await client.post(
                "/api/customers",
                json={"name": "Client B", "email": "clientb@example.com"},
                headers=headers,
            )
            cust_id1 = res1.json()["id"]

            # Partial update: only name
            res_patch = await client.patch(
                f"/api/customers/{cust_id1}",
                json={"name": "Client A Updated"},
                headers=headers,
            )
            assert res_patch.status_code == 200
            assert res_patch.json()["name"] == "Client A Updated"
            assert res_patch.json()["email"] == "clienta@example.com"  # unchanged

            # Update email to Client B's email → conflict → 400
            res_conflict = await client.patch(
                f"/api/customers/{cust_id1}",
                json={"email": "clientb@example.com"},
                headers=headers,
            )
            assert res_conflict.status_code == 400
            assert "already exists" in res_conflict.json()["detail"]

            # Update email to a fresh unique one → succeeds
            res_ok = await client.patch(
                f"/api/customers/{cust_id1}",
                json={"email": "new.unique@example.com"},
                headers=headers,
            )
            assert res_ok.status_code == 200
            assert res_ok.json()["email"] == "new.unique@example.com"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 8. Unauthenticated access
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(mock_db: MockDatabase):
    """All customer endpoints must reject requests without a valid Bearer token."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # HTTPBearer with auto_error=True returns 403 when Authorization header is absent,
            # and 401 when an invalid/expired token is supplied.
            # Without any Authorization header, FastAPI returns 403.
            UNAUTH_CODES = {401, 403}

            # GET list
            res = await client.get("/api/customers")
            assert res.status_code in UNAUTH_CODES

            # POST create
            res = await client.post("/api/customers", json={"name": "X", "email": "x@x.com"})
            assert res.status_code in UNAUTH_CODES

            # GET detail
            res = await client.get("/api/customers/fake-id")
            assert res.status_code in UNAUTH_CODES

            # PATCH
            res = await client.patch("/api/customers/fake-id", json={"name": "Y"})
            assert res.status_code in UNAUTH_CODES

            # DELETE
            res = await client.delete("/api/customers/fake-id")
            assert res.status_code in UNAUTH_CODES
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 9. Invalid email validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_email_rejected_on_create(mock_db: MockDatabase, user_a: User):
    """Pydantic email validation must reject malformed addresses with HTTP 422."""
    await mock_db.users.insert_one(user_a.model_dump())
    token_a = create_access_token(subject=user_a.id)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"Authorization": f"Bearer {token_a}"}

            for bad_email in ["not-an-email", "missing@", "@nodomain", "spaces in@email.com"]:
                res = await client.post(
                    "/api/customers",
                    json={"name": "Test", "email": bad_email},
                    headers=headers,
                )
                assert res.status_code == 422, f"Expected 422 for email '{bad_email}', got {res.status_code}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 10. invoice_count in response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invoice_count_reflects_linked_invoices(mock_db: MockDatabase, user_a: User):
    """CustomerResponse.invoice_count must accurately reflect the number of linked invoices."""
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
                json={"name": "Invoice Test Client", "email": "inv.test@example.com"},
                headers=headers,
            )
            assert res_cust.status_code == 201
            cust_id = res_cust.json()["id"]

            # Initially 0 invoices
            res_get = await client.get(f"/api/customers/{cust_id}", headers=headers)
            assert res_get.json()["invoice_count"] == 0

            # Add two mock invoices
            for i in range(2):
                await mock_db.invoices.insert_one({
                    "internal_id": f"inv-{i}",
                    "user_id": user_a.id,
                    "customer_id": cust_id,
                    "invoice_number": f"INV-{i}",
                })

            # invoice_count should now be 2
            res_get2 = await client.get(f"/api/customers/{cust_id}", headers=headers)
            assert res_get2.json()["invoice_count"] == 2

            # List also shows invoice_count
            res_list = await client.get("/api/customers", headers=headers)
            assert res_list.json()["items"][0]["invoice_count"] == 2
    finally:
        app.dependency_overrides.clear()
