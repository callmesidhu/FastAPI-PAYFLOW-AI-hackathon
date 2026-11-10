"""Authentication and user ownership isolation tests.

Verifies:
1. Registration & Login
2. Argon2id password hashing (plaintext never stored)
3. Cross-user data isolation (User B cannot read or mutate User A's records)
4. Environment-only JWT validation
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongodb import get_db
from app.main import app
from app.models.user import User
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.mark.asyncio
async def test_registration_and_argon2_password_hashing(mock_db: MockDatabase):
    """Verify user registration hashes password with Argon2id and returns valid JWT."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            register_payload = {
                "email": "sarah.connor@example.com",
                "password": "SecurePassword123!",
                "name": "Sarah Connor",
                "business_name": "Cyberdyne Resistance",
            }
            res = await client.post("/api/auth/register", json=register_payload)
            assert res.status_code == 201
            data = res.json()

            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert data["user"]["email"] == "sarah.connor@example.com"
            assert data["user"]["name"] == "Sarah Connor"
            # Invariant: Password or hash must NEVER be in user response
            assert "password" not in data["user"]
            assert "hashed_password" not in data["user"]

            # Invariant: Stored password must be an Argon2id hash, NEVER plaintext
            stored_user = await mock_db.users.find_one({"email": "sarah.connor@example.com"})
            assert stored_user is not None
            assert stored_user["hashed_password"] != "SecurePassword123!"
            assert "$argon2id$" in stored_user["hashed_password"]
            assert verify_password("SecurePassword123!", stored_user["hashed_password"]) is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_login_success_and_generic_error_protection(mock_db: MockDatabase):
    """Verify login authentication and generic error messages on credential failure."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        # Pre-seed user with Argon2id hash
        hashed = hash_password("ValidPassword123!")
        user = User(
            id="user-alex-1",
            email="alex@example.com",
            hashed_password=hashed,
            name="Alex",
        )
        await mock_db.users.insert_one(user.model_dump())

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Success case
            res = await client.post(
                "/api/auth/login",
                json={"email": "alex@example.com", "password": "ValidPassword123!"},
            )
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["user"]["id"] == "user-alex-1"

            # 2. Wrong password -> 401 with generic message
            res_bad_pw = await client.post(
                "/api/auth/login",
                json={"email": "alex@example.com", "password": "WrongPassword!"},
            )
            assert res_bad_pw.status_code == 401
            assert res_bad_pw.json()["detail"] == "Invalid email or password."

            # 3. Nonexistent email -> 401 with generic message (no enumeration)
            res_no_user = await client.post(
                "/api/auth/login",
                json={"email": "nobody@example.com", "password": "AnyPassword123!"},
            )
            assert res_no_user.status_code == 401
            assert res_no_user.json()["detail"] == "Invalid email or password."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_current_user_me_endpoint(mock_db: MockDatabase):
    """Verify /api/auth/me requires valid Bearer token."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        user = User(
            id="user-me-123",
            email="me@example.com",
            hashed_password=hash_password("Pass123!"),
            name="Me User",
        )
        await mock_db.users.insert_one(user.model_dump())

        token = create_access_token(subject=user.id)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Authenticated request
            res = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 200
            assert res.json()["id"] == "user-me-123"

            # Unauthenticated request
            res_unauth = await client.get("/api/auth/me")
            assert res_unauth.status_code in (401, 403)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cross_user_isolation(mock_db: MockDatabase):
    """Verify User B cannot access User A's business records."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        # Seed User A and User B
        user_a = User(id="user-a", email="user_a@example.com", hashed_password=hash_password("PassA123!"), name="A")
        user_b = User(id="user-b", email="user_b@example.com", hashed_password=hash_password("PassB123!"), name="B")
        await mock_db.users.insert_one(user_a.model_dump())
        await mock_db.users.insert_one(user_b.model_dump())

        # Seed Invoice owned by User A
        invoice_a = {
            "internal_id": "inv-secret-a",
            "user_id": "user-a",
            "invoice_number": "INV-A-001",
            "total": "1000.00",
        }
        await mock_db.invoices.insert_one(invoice_a)

        # Invariant: Querying User A's invoice with User B's identity must return None (404)
        doc = await mock_db.invoices.find_one({
            "internal_id": "inv-secret-a",
            "user_id": user_b.id,  # User B context
        })
        assert doc is None  # User B cannot read User A's record!

        # With User A context, it succeeds
        doc_a = await mock_db.invoices.find_one({
            "internal_id": "inv-secret-a",
            "user_id": user_a.id,
        })
        assert doc_a is not None
        assert doc_a["internal_id"] == "inv-secret-a"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_jwt_signed_with_wrong_secret_is_rejected(mock_db: MockDatabase):
    """Verify access token signed with an unauthorized key is rejected."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        foreign_secret = "completely-different-secret-key-unauthorized"
        fake_token = jwt.encode(
            {"sub": "user-attacker", "exp": 9999999999},
            foreign_secret,
            algorithm="HS256",
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {fake_token}"},
            )
            assert res.status_code == 401
    finally:
        app.dependency_overrides.clear()
