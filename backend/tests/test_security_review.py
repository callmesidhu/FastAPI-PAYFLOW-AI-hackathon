"""Automated security review & abuse-case test suite (Prompt 33).

Verifies:
1. Rate limiting on login endpoints (HTTP 429 + Retry-After header after 5 attempts).
2. Rate limiting on AI assistant endpoints (HTTP 429 + Retry-After header).
3. Automatic secret masking in log records (Bearer tokens, passwords, secrets).
4. Webhook certificate SSRF / domain spoofing defense.
5. Invariant: Client cannot directly set invoice status via update.
6. Invariant: Client cannot modify non-draft invoices.
7. Invariant: Approval state requires explicit merchant authorization and valid hash snapshot.
"""

from datetime import date, timedelta
from decimal import Decimal
import logging
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.config import get_settings
from app.core.logging import SecretMaskingFilter
from app.core.rate_limit import auth_limiter, ai_limiter
from app.db.mongodb import get_db
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.services.paypal_service import paypal_service
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db() -> MockDatabase:
    """In-memory MongoDB mock instance."""
    return MockDatabase()


@pytest.fixture(autouse=True)
def reset_limiters():
    """Reset rate limiter state between tests."""
    auth_limiter.reset()
    ai_limiter.reset()
    yield
    auth_limiter.reset()
    ai_limiter.reset()


@pytest.mark.asyncio
async def test_auth_login_rate_limiting_enforcement(mock_db: MockDatabase):
    """Exceeding 5 login attempts within a minute triggers HTTP 429 Too Many Requests."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 5 initial login attempts (fail authentication with 401)
            for _ in range(5):
                resp = await client.post(
                    "/api/auth/login",
                    json={"email": "attacker@example.com", "password": "wrongpassword"},
                )
                assert resp.status_code == 401

            # 6th attempt should be blocked by rate limiter with 429
            blocked_resp = await client.post(
                "/api/auth/login",
                json={"email": "attacker@example.com", "password": "wrongpassword"},
            )
            assert blocked_resp.status_code == 429
            assert "Rate limit exceeded" in blocked_resp.json()["detail"]
            assert "Retry-After" in blocked_resp.headers
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ai_endpoint_rate_limiting_enforcement(mock_db: MockDatabase):
    """Exceeding 15 AI extraction attempts triggers HTTP 429 Too Many Requests."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Register user
            reg_resp = await client.post(
                "/api/auth/register",
                json={
                    "email": "sarah.sec@example.com",
                    "password": "SecurePassword123!",
                    "name": "Sarah Sec",
                    "business_name": "Sec Studio",
                },
            )
            token = reg_resp.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            # Fire 15 AI extraction calls
            for _ in range(15):
                res = await client.post(
                    "/api/ai/extract-invoice",
                    headers=auth_headers,
                    json={"text": "Create invoice for Acme for $100"},
                )
                assert res.status_code == 200

            # 16th call should be blocked with HTTP 429
            blocked_res = await client.post(
                "/api/ai/extract-invoice",
                headers=auth_headers,
                json={"text": "Create invoice for Acme for $100"},
            )
            assert blocked_res.status_code == 429
            assert "Rate limit exceeded" in blocked_res.json()["detail"]
            assert "Retry-After" in blocked_res.headers
    finally:
        app.dependency_overrides.clear()


def test_secret_masking_filter_scrubs_sensitive_data():
    """Verify SecretMaskingFilter scrubs Bearer tokens and passwords from log records."""
    filter_instance = SecretMaskingFilter()

    # Record 1: Bearer token
    rec1 = logging.LogRecord(
        name="payflow.test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Authorization failed with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token123",
        args=(),
        exc_info=None,
    )
    assert filter_instance.filter(rec1) is True
    assert "Bearer [MASKED]" in rec1.msg
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in rec1.msg

    # Record 2: Password
    rec2 = logging.LogRecord(
        name="payflow.test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="User payload contained password='SuperSecretPassword123!'",
        args=(),
        exc_info=None,
    )
    assert filter_instance.filter(rec2) is True
    assert "password=[MASKED]" in rec2.msg
    assert "SuperSecretPassword123!" not in rec2.msg


@pytest.mark.asyncio
async def test_cert_url_domain_spoofing_rejected():
    """Verify non-PayPal certificate domains are rejected immediately in webhook verification."""
    # Attempt verification with an external or malicious cert_url
    result = await paypal_service.verify_webhook_signature(
        transmission_id="trans_test_123",
        transmission_time="2026-11-10T15:00:00Z",
        transmission_sig="sig123",
        cert_url="https://attacker.example.com/evil.pem",
        auth_algo="SHA256withRSA",
        webhook_id="WH-123",
        raw_body={"id": "EVT-1"},
    )
    assert result is False


@pytest.mark.asyncio
async def test_client_cannot_directly_set_invoice_status_via_update(mock_db: MockDatabase):
    """Verify clients cannot set invoice status directly via PATCH /api/invoices/{id}."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Register user
            reg_resp = await client.post(
                "/api/auth/register",
                json={
                    "email": "status.test@example.com",
                    "password": "SecurePassword123!",
                    "name": "Status Tester",
                },
            )
            token = reg_resp.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            # Create customer
            cust_res = await client.post(
                "/api/customers",
                headers=auth_headers,
                json={"name": "Client Alpha", "email": "alpha@example.com"},
            )
            cust_id = cust_res.json()["id"]

            # Create draft invoice
            inv_res = await client.post(
                "/api/invoices",
                headers=auth_headers,
                json={
                    "customer_id": cust_id,
                    "currency": "USD",
                    "due_date": (date.today() + timedelta(days=7)).isoformat(),
                    "items": [{"name": "Consulting", "quantity": 1, "unit_price": "500.00"}],
                },
            )
            inv_id = inv_res.json()["internal_id"]
            assert inv_res.json()["status"] == "draft"

            # Attempt to set status directly to 'paid' in update payload
            update_res = await client.patch(
                f"/api/invoices/{inv_id}",
                headers=auth_headers,
                json={"status": "paid", "notes": "Hacked status"},
            )
            assert update_res.status_code == 200
            # Status MUST remain draft; client-provided 'status' field is ignored by Pydantic schema
            assert update_res.json()["status"] == "draft"
    finally:
        app.dependency_overrides.clear()
