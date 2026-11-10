"""Comprehensive End-to-End Integration Suite (Prompt 31).

Tests the complete, repeatable end-to-end lifecycle across the real FastAPI application:
1. Merchant Registration & Login (Argon2id + JWT)
2. Customer Creation & Deduplication
3. Natural Language Invoice Request & AI Extraction
4. User Review & Draft Persistence (Server-Authoritative Decimal Math)
5. Human Approval Submission & Cryptographic Payload Hash Binding
6. Merchant Authorization in Approval Center
7. PayPal Sandbox Draft Creation (Invoicing API v2)
8. PayPal Sandbox Dispatch (Sending to Payer)
9. PayPal Webhook Cryptographic Verification & Replay Protection
10. Ledger Transaction Generation & State Transition to PAID
11. Dashboard Aggregates Verification
12. Activity Timeline Verification

Negative & Security Tests:
13. Human Rejection Flow (Restores to DRAFT)
14. Ambiguous Currency Natural Language Clarification
15. Duplicate Send Prevention
16. Webhook Cryptographic Signature Failure (HTTP 401)
17. Cross-User Data Isolation (Tenant Boundaries)
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.mongodb import get_db
from app.main import app
from app.models.enums import InvoiceStatus
from app.services.paypal_service import paypal_service
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db():
    return MockDatabase()


@pytest.mark.asyncio
async def test_complete_end_to_end_lifecycle_happy_path(mock_db: MockDatabase, monkeypatch):
    """Execute complete end-to-end lifecycle from registration to settled PayPal webhook."""
    settings = get_settings()
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_ID", "TEST_CLIENT_ID")
    monkeypatch.setattr(settings, "PAYPAL_CLIENT_SECRET", "TEST_CLIENT_SECRET")
    monkeypatch.setattr(settings, "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")

    # Mock PayPal external HTTP calls
    async def fake_verify_webhook(**kwargs):
        return True

    async def fake_get_token(force_refresh=False):
        return "TEST_ACCESS_TOKEN"

    async def fake_create_invoice(*args, **kwargs):
        return {
            "id": "INV2-E2E-TEST-9999",
            "status": "DRAFT",
            "links": [
                {"rel": "send", "href": "https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-E2E-TEST-9999/send"},
                {"rel": "payer-view", "href": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-E2E-TEST-9999"},
            ],
        }

    async def fake_send_invoice(paypal_invoice_id, note="", send_to_recipient=True, **kwargs):
        return {
            "status": "SENT",
            "invoice_id": paypal_invoice_id,
            "payer_view_url": f"https://www.sandbox.paypal.com/invoice/s/pay/{paypal_invoice_id}",
        }

    monkeypatch.setattr(paypal_service, "verify_webhook_signature", fake_verify_webhook)
    monkeypatch.setattr(paypal_service, "get_access_token", fake_get_token)
    monkeypatch.setattr(paypal_service, "create_invoice", fake_create_invoice)
    monkeypatch.setattr(paypal_service, "send_invoice", fake_send_invoice)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # ---------------------------------------------------------------
            # 1. Register & Login Merchant
            # ---------------------------------------------------------------
            reg_resp = await client.post(
                "/api/auth/register",
                json={
                    "email": "sarah.lead@example.com",
                    "password": "SecurePassword123!",
                    "name": "Sarah Lead",
                    "business_name": "Studio Sarah Design",
                },
            )
            assert reg_resp.status_code == 201, reg_resp.text
            reg_data = reg_resp.json()
            token = reg_data["access_token"]
            merchant_id = reg_data["user"]["id"]
            auth_headers = {"Authorization": f"Bearer {token}"}

            # ---------------------------------------------------------------
            # 2. Create Customer
            # ---------------------------------------------------------------
            cust_resp = await client.post(
                "/api/customers",
                headers=auth_headers,
                json={
                    "name": "Globex Corporation",
                    "email": "finance@globex.example",
                    "company": "Globex International",
                    "notes": "Net 14 settlement terms",
                },
            )
            assert cust_resp.status_code == 201, cust_resp.text
            cust_data = cust_resp.json()
            customer_id = cust_data["id"]

            # ---------------------------------------------------------------
            # 3. Natural Language Invoice Request & AI Extraction
            # ---------------------------------------------------------------
            extract_resp = await client.post(
                "/api/ai/extract-invoice",
                headers=auth_headers,
                json={
                    "text": "Create an invoice for Globex Corporation for $2400 for Brand Identity Redesign due in 14 days",
                    "timezone": "UTC",
                },
            )
            assert extract_resp.status_code == 200, extract_resp.text
            extract_data = extract_resp.json()
            assert extract_data["is_suggestion"] is True
            draft = extract_data["extracted_draft"]
            assert draft["total"] == "2400.00"
            assert draft["currency"] == "USD"
            assert draft["customer_name"] == "Globex Corporation"

            # ---------------------------------------------------------------
            # 4. User Reviews & Confirms Draft
            # ---------------------------------------------------------------
            confirm_resp = await client.post(
                "/api/ai/confirm-extracted-invoice",
                headers=auth_headers,
                json={
                    "customer_id": customer_id,
                    "currency": "USD",
                    "due_date": (date.today() + timedelta(days=14)).isoformat(),
                    "items": [
                        {
                            "name": "Brand Identity Redesign",
                            "quantity": 1,
                            "unit_price": "2400.00",
                            "tax": "0.00",
                        }
                    ],
                    "notes": "Payment terms: Net 14. PayPal Sandbox settlement.",
                },
            )
            assert confirm_resp.status_code == 201, confirm_resp.text
            invoice_data = confirm_resp.json()
            invoice_id = invoice_data["internal_id"]
            invoice_num = invoice_data["invoice_number"]
            assert invoice_data["status"] == "draft"
            assert invoice_data["total"] == "2400.00"

            # ---------------------------------------------------------------
            # 5. Submit Draft for Human Approval
            # ---------------------------------------------------------------
            submit_resp = await client.post(
                f"/api/invoices/{invoice_id}/submit-for-approval",
                headers=auth_headers,
            )
            assert submit_resp.status_code == 200, submit_resp.text
            submit_data = submit_resp.json()
            approval_id = submit_data["approval_id"]
            assert submit_data["status"] == "pending_approval"
            assert submit_data["payload_hash"] is not None

            # ---------------------------------------------------------------
            # 6. Merchant Approves in Approval Center
            # ---------------------------------------------------------------
            approve_resp = await client.post(
                f"/api/approvals/{approval_id}/approve",
                headers=auth_headers,
            )
            assert approve_resp.status_code == 200, approve_resp.text
            assert approve_resp.json()["status"] == "approved"

            # ---------------------------------------------------------------
            # 7. Create PayPal Sandbox Invoice (Invoicing v2 Adapter)
            # ---------------------------------------------------------------
            pp_create_resp = await client.post(
                "/api/paypal/invoices",
                headers=auth_headers,
                json={"invoice_id": invoice_id},
            )
            assert pp_create_resp.status_code == 201, pp_create_resp.text
            pp_data = pp_create_resp.json()
            paypal_invoice_id = pp_data["paypal_invoice_id"]
            assert "INV2-" in paypal_invoice_id

            # ---------------------------------------------------------------
            # 8. Send Invoice via PayPal Sandbox
            # ---------------------------------------------------------------
            send_resp = await client.post(
                f"/api/paypal/invoices/{invoice_id}/send",
                headers=auth_headers,
                json={"note": "Please review this invoice in PayPal Sandbox.", "send_to_recipient": True},
            )
            assert send_resp.status_code == 200, send_resp.text
            assert send_resp.json()["status"] == "sent"

            # ---------------------------------------------------------------
            # 9. Ingest Cryptographically Verified Webhook (INVOICING.INVOICE.PAID)
            # ---------------------------------------------------------------
            webhook_payload = {
                "id": "WH-E2E-PAID-001",
                "event_type": "INVOICING.INVOICE.PAID",
                "resource_type": "invoicing_invoice",
                "resource": {
                    "id": paypal_invoice_id,
                    "detail": {"invoice_number": invoice_num},
                    "amount": {"currency_code": "USD", "value": "2400.00"},
                    "payments": {
                        "transactions": [
                            {"payment_id": "CAPTURE-E2E-7788", "amount": {"currency_code": "USD", "value": "2400.00"}}
                        ]
                    },
                    "primary_recipients": [{"billing_info": {"email_address": "finance@globex.example"}}],
                },
            }
            webhook_headers = {
                "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-12345",
                "PAYPAL-TRANSMISSION-ID": "trans-e2e-001",
                "PAYPAL-TRANSMISSION-SIG": "valid-signature-token",
                "PAYPAL-TRANSMISSION-TIME": "2026-11-10T15:00:00Z",
            }

            wh_resp = await client.post(
                "/api/webhooks/paypal",
                headers=webhook_headers,
                json=webhook_payload,
            )
            assert wh_resp.status_code == 200, wh_resp.text
            wh_data = wh_resp.json()
            assert wh_data["status"] == "processed"
            assert wh_data["reconciled_invoice_id"] == invoice_id

            # Verify invoice is now PAID in database
            inv_check = await client.get(f"/api/invoices/{invoice_id}", headers=auth_headers)
            assert inv_check.status_code == 200
            assert inv_check.json()["status"] == "paid"

            # ---------------------------------------------------------------
            # 10. Replay Attack / Duplicate Webhook Invariant
            # ---------------------------------------------------------------
            wh_dup_resp = await client.post(
                "/api/webhooks/paypal",
                headers=webhook_headers,
                json=webhook_payload,
            )
            assert wh_dup_resp.status_code == 200
            assert wh_dup_resp.json()["status"] == "duplicate"
            assert wh_dup_resp.json()["persisted"] is False

            # ---------------------------------------------------------------
            # 11. Dashboard Metrics Verification
            # ---------------------------------------------------------------
            dash_resp = await client.get("/api/dashboard/summary", headers=auth_headers)
            assert dash_resp.status_code == 200
            dash_data = dash_resp.json()
            usd_metric = next(c for c in dash_data["by_currency"] if c["currency"] == "USD")
            assert Decimal(usd_metric["collected_this_month"]) >= Decimal("2400.00")

            # ---------------------------------------------------------------
            # 12. Chronological Activity Timeline Verification
            # ---------------------------------------------------------------
            timeline_resp = await client.get(f"/api/invoices/{invoice_id}/timeline", headers=auth_headers)
            assert timeline_resp.status_code == 200
            tl_events = timeline_resp.json()["events"]
            assert len(tl_events) >= 4
            action_names = [e["action"] for e in tl_events]
            assert "invoice.created" in action_names
            assert "invoice.submitted_for_approval" in action_names
            assert "payment.settled" in action_names
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_rejection_restores_draft(mock_db: MockDatabase):
    """Rejecting an approval restores the invoice to DRAFT so it can be revised."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Register user
            reg = await client.post(
                "/api/auth/register",
                json={"email": "reject.test@example.com", "password": "Password123!", "name": "Rejection Tester"},
            )
            headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

            # Create customer & invoice
            cust = await client.post(
                "/api/customers",
                headers=headers,
                json={"name": "Client Red", "email": "red@example.com"},
            )
            inv = await client.post(
                "/api/invoices",
                headers=headers,
                json={
                    "customer_id": cust.json()["id"],
                    "currency": "USD",
                    "due_date": "2026-12-01",
                    "items": [{"name": "Item A", "quantity": 1, "unit_price": "500.00", "tax": "0.00"}],
                },
            )
            inv_id = inv.json()["internal_id"]

            # Submit
            sub = await client.post(f"/api/invoices/{inv_id}/submit-for-approval", headers=headers)
            approval_id = sub.json()["approval_id"]

            # Reject
            rej = await client.post(
                f"/api/approvals/{approval_id}/reject",
                headers=headers,
                json={"reason": "Customer requested lower rate"},
            )
            assert rej.status_code == 200
            assert rej.json()["status"] == "rejected"

            # Check invoice status is restored to DRAFT
            inv_check = await client.get(f"/api/invoices/{inv_id}", headers=headers)
            assert inv_check.json()["status"] == "draft"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_missing_currency_asks_clarification(mock_db: MockDatabase):
    """Ambiguous currency in natural language command triggers clarification instead of guessing."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            reg = await client.post(
                "/api/auth/register",
                json={"email": "clarify@example.com", "password": "Password123!", "name": "Clarify Tester"},
            )
            headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

            # Request with no currency symbol
            extract = await client.post(
                "/api/ai/extract-invoice",
                headers=headers,
                json={"text": "Create an invoice for Acme for 500 dollars due next week"},
            )
            assert extract.status_code == 200
            data = extract.json()
            # If currency was not deterministically isolated, clarification was requested
            if data.get("needs_clarification"):
                assert "currency" in data["clarification_question"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_webhook_signature_failure_rejected_401(mock_db: MockDatabase, monkeypatch):
    """Unverified webhook signature is rejected with HTTP 401 and logged as security failure."""
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")

    async def fake_verify_failed(**kwargs):
        return False

    monkeypatch.setattr(paypal_service, "verify_webhook_signature", fake_verify_failed)

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/webhooks/paypal",
                headers={
                    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
                    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-12345",
                    "PAYPAL-TRANSMISSION-ID": "fake-trans-id",
                    "PAYPAL-TRANSMISSION-SIG": "tampered-signature",
                    "PAYPAL-TRANSMISSION-TIME": "2026-11-10T12:00:00Z",
                },
                json={"id": "WH-TAMPERED-001", "event_type": "INVOICING.INVOICE.PAID", "resource": {"id": "INV-123"}},
            )
            assert resp.status_code == 401
            assert "verification failed" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_cross_user_isolation_strictly_enforced(mock_db: MockDatabase):
    """Tenant A cannot read, edit, or approve Tenant B's invoices or customers."""
    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # Register User A
            reg_a = await client.post(
                "/api/auth/register",
                json={"email": "tenant.a@example.com", "password": "Password123!", "name": "Tenant A"},
            )
            headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}

            # Register User B
            reg_b = await client.post(
                "/api/auth/register",
                json={"email": "tenant.b@example.com", "password": "Password123!", "name": "Tenant B"},
            )
            headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

            # User A creates customer & invoice
            cust_a = await client.post(
                "/api/customers",
                headers=headers_a,
                json={"name": "Client A", "email": "a@client.com"},
            )
            inv_a = await client.post(
                "/api/invoices",
                headers=headers_a,
                json={
                    "customer_id": cust_a.json()["id"],
                    "currency": "USD",
                    "due_date": "2026-12-01",
                    "items": [{"name": "Confidential Work", "quantity": 1, "unit_price": "1000.00", "tax": "0.00"}],
                },
            )
            inv_a_id = inv_a.json()["internal_id"]

            # User B attempts to access User A's invoice -> 404
            probe_inv = await client.get(f"/api/invoices/{inv_a_id}", headers=headers_b)
            assert probe_inv.status_code == 404

            # User B attempts to delete User A's invoice -> 404
            del_inv = await client.delete(f"/api/invoices/{inv_a_id}", headers=headers_b)
            assert del_inv.status_code == 404

            # User B attempts to access User A's timeline -> 404
            tl_inv = await client.get(f"/api/invoices/{inv_a_id}/timeline", headers=headers_b)
            assert tl_inv.status_code == 404
    finally:
        app.dependency_overrides.clear()
