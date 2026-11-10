"""Tests for PayPal Webhook Verification & State Reconciliation (Prompt 23).

Tests:
1. Missing cryptographic headers returns HTTP 400.
2. Unconfigured PAYPAL_WEBHOOK_ID returns HTTP 400.
3. Failed signature verification returns HTTP 401.
4. Valid INVOICING.INVOICE.PAID transitions invoice to PAID, creates Transaction, and emits AuditLog.
5. Duplicate webhook event is recognized, returns duplicate status, and prevents replay mutations.
6. INVOICING.INVOICE.CANCELLED transitions invoice to CANCELLED.
7. Unknown/unsupported event type returns ignored status safely without error.
8. HTTP endpoint POST /api/webhooks/paypal handles requests end-to-end.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict
import pytest
from httpx import ASGITransport, AsyncClient
import respx
from fastapi import HTTPException

from app.core.config import get_settings
from app.db.mongodb import get_db
from app.main import app
from app.models.enums import InvoiceStatus, SupportedCurrency
from app.services.paypal_service import paypal_service
from app.services.webhook_service import WebhookService
from tests.mock_db import MockDatabase

SAMPLE_HEADERS = {
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-12345",
    "PAYPAL-TRANSMISSION-ID": "trans-123e4567-e89b-12d3-a456-426614174000",
    "PAYPAL-TRANSMISSION-SIG": "dGhpcy1pcy1hLXRlc3Qtc2lnbmF0dXJl",
    "PAYPAL-TRANSMISSION-TIME": "2026-11-10T12:00:00Z",
}

SAMPLE_PAID_EVENT: Dict[str, Any] = {
    "id": "WH-987654321-PAID",
    "event_version": "1.0",
    "create_time": "2026-11-10T12:00:00Z",
    "resource_type": "invoicing_invoice",
    "event_type": "INVOICING.INVOICE.PAID",
    "summary": "Invoice INV2-TEST-123 was paid",
    "resource": {
        "id": "INV2-TEST-123",
        "detail": {
            "invoice_number": "INV-2026-0001",
            "invoice_date": "2026-11-10",
        },
        "amount": {
            "currency_code": "USD",
            "value": "1500.00",
        },
        "payments": {
            "transactions": [
                {
                    "payment_id": "CAPTURE-778899",
                    "payment_method": "PAYPAL",
                    "amount": {"currency_code": "USD", "value": "1500.00"},
                }
            ]
        },
        "primary_recipients": [
            {
                "billing_info": {
                    "email_address": "client@example.com",
                    "name": {"given_name": "Acme", "surname": "Corp"},
                }
            }
        ],
        "links": [{"href": "https://api.sandbox.paypal.com/v2/invoicing/invoices/INV2-TEST-123"}],
    },
}


@pytest.mark.asyncio
async def test_missing_crypto_headers_rejected_400():
    """Missing any required cryptographic header raises HTTP 400."""
    db = MockDatabase()
    incomplete_headers = {"PAYPAL-AUTH-ALGO": "SHA256withRSA"}

    with pytest.raises(HTTPException) as exc_info:
        await WebhookService.process_webhook(
            db=db,
            headers=incomplete_headers,
            raw_event=SAMPLE_PAID_EVENT,
        )
    assert exc_info.value.status_code == 400
    assert "Missing required PayPal webhook cryptographic headers" in exc_info.value.detail


@pytest.mark.asyncio
async def test_unconfigured_webhook_id_rejected_400(monkeypatch):
    """Missing or empty PAYPAL_WEBHOOK_ID in environment raises HTTP 400."""
    db = MockDatabase()
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "")

    with pytest.raises(HTTPException) as exc_info:
        await WebhookService.process_webhook(
            db=db,
            headers=SAMPLE_HEADERS,
            raw_event=SAMPLE_PAID_EVENT,
        )
    assert exc_info.value.status_code == 400
    assert "PAYPAL_WEBHOOK_ID is not configured" in exc_info.value.detail


@pytest.mark.asyncio
async def test_failed_signature_verification_rejected_401(monkeypatch):
    """If PayPal verification endpoint returns FAILURE, webhook is rejected with HTTP 401."""
    db = MockDatabase()
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")

    async def fake_verify_failed(**kwargs):
        return False

    monkeypatch.setattr(paypal_service, "verify_webhook_signature", fake_verify_failed)

    with pytest.raises(HTTPException) as exc_info:
        await WebhookService.process_webhook(
            db=db,
            headers=SAMPLE_HEADERS,
            raw_event=SAMPLE_PAID_EVENT,
        )
    assert exc_info.value.status_code == 401
    assert "verification failed" in exc_info.value.detail

    # Check security audit failure was logged
    fail_audit = await db.audit_logs.find_one({"action": "webhook.verification_failed"})
    assert fail_audit is not None
    assert fail_audit["result"] == "rejected"


@pytest.mark.asyncio
async def test_valid_invoice_paid_webhook_reconciliation(monkeypatch):
    """Verified INVOICING.INVOICE.PAID updates invoice to PAID, creates Transaction, and emits AuditLog."""
    db = MockDatabase()
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")

    # Seed invoice
    invoice_doc = {
        "internal_id": "inv_int_12345",
        "user_id": "user_merchant_1",
        "customer_id": "cust_acme_1",
        "invoice_number": "INV-2026-0001",
        "paypal_invoice_id": "INV2-TEST-123",
        "status": InvoiceStatus.SENT.value,
        "total": Decimal("1500.00"),
        "currency": "USD",
        "created_at": datetime.now(timezone.utc),
    }
    await db.invoices.insert_one(invoice_doc)

    async def fake_verify_success(**kwargs):
        return True

    monkeypatch.setattr(paypal_service, "verify_webhook_signature", fake_verify_success)

    resp = await WebhookService.process_webhook(
        db=db,
        headers=SAMPLE_HEADERS,
        raw_event=SAMPLE_PAID_EVENT,
    )

    assert resp.status == "processed"
    assert resp.event_id == "WH-987654321-PAID"
    assert resp.reconciled_invoice_id == "inv_int_12345"

    # 1. Invoice status updated to PAID
    updated_inv = await db.invoices.find_one({"internal_id": "inv_int_12345"})
    assert updated_inv["status"] == InvoiceStatus.PAID.value
    assert updated_inv["paid_at"] is not None

    # 2. Authoritative transaction ledger record created
    txn = await db.transactions.find_one({"invoice_id": "inv_int_12345"})
    assert txn is not None
    assert txn["amount"] == Decimal("1500.00")
    assert txn["currency"] == SupportedCurrency.USD.value
    assert txn["paypal_capture_id"] == "CAPTURE-778899"
    assert txn["payer_email"] == "client@example.com"
    assert txn["status"] == "completed"

    # 3. Append-only audit record created
    audit = await db.audit_logs.find_one({"action": "payment.settled"})
    assert audit is not None
    assert audit["actor"] == "paypal_webhook"
    assert audit["resource_id"] == "inv_int_12345"

    # 4. Verified event persisted in db.webhook_events
    stored_event = await db.webhook_events.find_one({"event_id": "WH-987654321-PAID"})
    assert stored_event is not None
    assert stored_event["verified"] is True
    assert stored_event["payload_redacted"]["resource"]["links"] == 1


@pytest.mark.asyncio
async def test_duplicate_webhook_replay_protection(monkeypatch):
    """Replaying an already-processed webhook returns duplicate status and skips mutations."""
    db = MockDatabase()
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")

    async def fake_verify_success(**kwargs):
        return True

    monkeypatch.setattr(paypal_service, "verify_webhook_signature", fake_verify_success)

    # Pre-seed verified event
    await db.webhook_events.insert_one(
        {
            "event_id": "WH-987654321-PAID",
            "event_type": "INVOICING.INVOICE.PAID",
            "verified": True,
            "status": "processed",
        }
    )

    resp = await WebhookService.process_webhook(
        db=db,
        headers=SAMPLE_HEADERS,
        raw_event=SAMPLE_PAID_EVENT,
    )

    assert resp.status == "duplicate"
    assert resp.persisted is False
    assert "already been processed" in resp.message

    # Verify duplicate was audited
    audit_dup = await db.audit_logs.find_one({"action": "webhook.duplicate_ignored"})
    assert audit_dup is not None


@pytest.mark.asyncio
async def test_invoice_cancelled_webhook(monkeypatch):
    """INVOICING.INVOICE.CANCELLED transitions invoice to CANCELLED."""
    db = MockDatabase()
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")

    await db.invoices.insert_one(
        {
            "internal_id": "inv_to_cancel",
            "user_id": "user_1",
            "invoice_number": "INV-2026-0002",
            "paypal_invoice_id": "INV2-CANCEL-999",
            "status": InvoiceStatus.SENT.value,
        }
    )

    cancel_event = {
        "id": "WH-CANCEL-001",
        "event_type": "INVOICING.INVOICE.CANCELLED",
        "resource": {"id": "INV2-CANCEL-999"},
    }

    monkeypatch.setattr(paypal_service, "verify_webhook_signature", lambda **kw: _async_val(True))

    resp = await WebhookService.process_webhook(
        db=db,
        headers=SAMPLE_HEADERS,
        raw_event=cancel_event,
    )

    assert resp.status == "processed"
    updated_inv = await db.invoices.find_one({"internal_id": "inv_to_cancel"})
    assert updated_inv["status"] == InvoiceStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_unknown_event_type_safely_ignored(monkeypatch):
    """Unsupported event types are safely recorded as ignored without throwing."""
    db = MockDatabase()
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")
    monkeypatch.setattr(paypal_service, "verify_webhook_signature", lambda **kw: _async_val(True))

    unknown_event = {
        "id": "WH-OTHER-999",
        "event_type": "BILLING.SUBSCRIPTION.CREATED",
        "resource": {"id": "SUB-123"},
    }

    resp = await WebhookService.process_webhook(
        db=db,
        headers=SAMPLE_HEADERS,
        raw_event=unknown_event,
    )

    assert resp.status == "ignored"
    assert "safely ignored" in resp.message
    saved_event = await db.webhook_events.find_one({"event_id": "WH-OTHER-999"})
    assert saved_event["status"] == "ignored"


@pytest.mark.asyncio
async def test_http_api_webhook_endpoint(monkeypatch):
    """POST /api/webhooks/paypal processes valid webhook via HTTP."""
    mock_db = MockDatabase()
    monkeypatch.setattr(get_settings(), "PAYPAL_WEBHOOK_ID", "WH-CONFIGURED-ID-12345")
    monkeypatch.setattr(paypal_service, "verify_webhook_signature", lambda **kw: _async_val(True))

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post(
                "/api/webhooks/paypal",
                headers=SAMPLE_HEADERS,
                json=SAMPLE_PAID_EVENT,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "processed"
            assert data["event_id"] == "WH-987654321-PAID"
    finally:
        app.dependency_overrides.clear()


async def _async_val(val: Any) -> Any:
    return val

