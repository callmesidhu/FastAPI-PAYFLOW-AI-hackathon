"""Tests for Transaction Ledger & Append-Only-Style Audit Trail (Prompt 24).

Invariants & Assertions:
1. Append-only guarantee at application layer: No PUT, PATCH, or DELETE endpoints exist for audit logs or transactions.
2. Metadata secret scrubbing: Tokens, secrets, and credentials in audit metadata are scrubbed before persistence.
3. Chronological activity timeline on invoice details: Maps all lifecycle actions into readable labels and actor tags.
4. Financial transaction records: Scoped to user, immutable, and accurately records capture ID, amount, and payer.
5. Strict multi-tenant isolation across audit logs, transactions, and invoice timelines.
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token
from app.db.mongodb import get_db
from app.main import app
from app.models.audit import ActorType, AuditLog
from app.models.enums import InvoiceStatus, SupportedCurrency
from app.models.transaction import Transaction
from app.services.audit_service import AuditService, sanitize_audit_metadata
from tests.mock_db import MockDatabase


def test_append_only_guarantee_no_update_or_delete_routes():
    """Verify that NO routes in FastAPI router allow updating or deleting audit logs or transactions.

    Strict application-layer append-only invariant.
    """
    forbidden_methods = {"PUT", "PATCH", "DELETE"}
    sensitive_prefixes = ("/api/audit-logs", "/api/transactions")

    for route in app.routes:
        path = getattr(route, "path", "")
        methods = getattr(route, "methods", set())
        for prefix in sensitive_prefixes:
            if path.startswith(prefix):
                intersection = methods.intersection(forbidden_methods)
                assert not intersection, (
                    f"Violation of append-only invariant: Route {path} allows modification methods: {intersection}"
                )


def test_sanitize_audit_metadata_scrubs_secrets():
    """Verify passwords, tokens, and hashes are safely scrubbed from audit metadata."""
    dirty_metadata = {
        "access_token": "A21AAJ-SampleSecretTokenPayload12345",
        "nested": {
            "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$somehashhere",
            "safe_field": "invoice_total_100",
        },
        "invoice_number": "INV-2026-0001",
    }
    clean = sanitize_audit_metadata(dirty_metadata)

    assert "[REDACTED_SECRET]" in clean["access_token"]
    assert "[REDACTED_SECRET]" in clean["nested"]["password_hash"]
    assert clean["nested"]["safe_field"] == "invoice_total_100"
    assert clean["invoice_number"] == "INV-2026-0001"


@pytest.mark.asyncio
async def test_record_audit_event_persists_safely():
    """AuditService.record_event persists an append-only entry with correlation ID and scrubbed metadata."""
    db = MockDatabase()
    entry = await AuditService.record_event(
        db=db,
        user_id="user_123",
        action="invoice.created",
        resource_type="invoice",
        resource_id="inv_abc",
        actor=ActorType.USER,
        result="success",
        metadata={"amount": "500.00", "bearer_token": "Bearer secret-payload-here"},
    )

    assert entry.user_id == "user_123"
    assert entry.action == "invoice.created"
    assert entry.correlation_id is not None
    assert "[REDACTED_SECRET]" in entry.metadata["bearer_token"]

    saved = await db.audit_logs.find_one({"id": entry.id})
    assert saved is not None
    assert saved["resource_id"] == "inv_abc"


@pytest.mark.asyncio
async def test_invoice_timeline_chronological_ordering_and_mapping():
    """get_invoice_timeline retrieves events in chronological ascending order with formatted labels."""
    db = MockDatabase()
    user_id = "user_timeline_test"

    # Seed invoice
    await db.invoices.insert_one(
        {
            "internal_id": "inv_tl_1",
            "invoice_number": "INV-2026-0099",
            "user_id": user_id,
            "paypal_invoice_id": "INV2-PP-99",
            "status": InvoiceStatus.PAID.value,
        }
    )

    # Seed 3 chronological audit events
    t1 = datetime(2026, 11, 10, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 10, 11, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 11, 10, 12, 0, 0, tzinfo=timezone.utc)

    await db.audit_logs.insert_one(
        {
            "id": "aud_1",
            "user_id": user_id,
            "actor": "user",
            "action": "invoice.created",
            "resource_type": "invoice",
            "resource_id": "inv_tl_1",
            "result": "success",
            "metadata": {"invoice_number": "INV-2026-0099"},
            "created_at": t1,
        }
    )
    await db.audit_logs.insert_one(
        {
            "id": "aud_2",
            "user_id": user_id,
            "actor": "user",
            "action": "invoice.submitted_for_approval",
            "resource_type": "invoice",
            "resource_id": "inv_tl_1",
            "result": "success",
            "metadata": {"invoice_number": "INV-2026-0099"},
            "created_at": t2,
        }
    )
    await db.audit_logs.insert_one(
        {
            "id": "aud_3",
            "user_id": user_id,
            "actor": "paypal_webhook",
            "action": "payment.settled",
            "resource_type": "invoice",
            "resource_id": "inv_tl_1",
            "result": "success",
            "metadata": {"paypal_invoice_id": "INV2-PP-99", "amount": "1200.00"},
            "created_at": t3,
        }
    )

    timeline = await AuditService.get_invoice_timeline(db=db, user_id=user_id, invoice_id="inv_tl_1")

    assert timeline.invoice_id == "inv_tl_1"
    assert timeline.invoice_number == "INV-2026-0099"
    assert len(timeline.events) == 3

    assert timeline.events[0].action == "invoice.created"
    assert timeline.events[0].action_label == "Invoice Draft Created"
    assert timeline.events[0].actor_type == "user"

    assert timeline.events[1].action == "invoice.submitted_for_approval"
    assert timeline.events[1].action_label == "Submitted for Owner Approval"

    assert timeline.events[2].action == "payment.settled"
    assert timeline.events[2].action_label == "Payment Settled via PayPal"
    assert timeline.events[2].actor_type == "paypal_webhook"


@pytest.mark.asyncio
async def test_audit_and_transaction_multi_tenant_isolation():
    """Ensure User A cannot view User B's audit events or transactions."""
    db = MockDatabase()
    user_a = "user_alpha"
    user_b = "user_beta"

    # User A records
    await db.audit_logs.insert_one(
        {
            "id": "aud_a",
            "user_id": user_a,
            "actor": "user",
            "action": "invoice.created",
            "resource_type": "invoice",
            "resource_id": "inv_a",
            "result": "success",
            "metadata": {},
            "created_at": datetime.now(timezone.utc),
        }
    )
    await db.transactions.insert_one(
        {
            "id": "txn_a",
            "user_id": user_a,
            "invoice_id": "inv_a",
            "amount": Decimal("100.00"),
            "currency": SupportedCurrency.USD.value,
            "status": "completed",
            "created_at": datetime.now(timezone.utc),
        }
    )

    # User B records
    await db.audit_logs.insert_one(
        {
            "id": "aud_b",
            "user_id": user_b,
            "actor": "user",
            "action": "invoice.created",
            "resource_type": "invoice",
            "resource_id": "inv_b",
            "result": "success",
            "metadata": {},
            "created_at": datetime.now(timezone.utc),
        }
    )

    # Query as User A
    logs_a = await AuditService.list_audit_logs(db=db, user_id=user_a)
    assert len(logs_a) == 1
    assert logs_a[0].id == "aud_a"

    txns_a = await AuditService.list_transactions(db=db, user_id=user_a)
    assert len(txns_a) == 1
    assert txns_a[0].id == "txn_a"

    # Query as User B
    txns_b = await AuditService.list_transactions(db=db, user_id=user_b)
    assert len(txns_b) == 0


@pytest.mark.asyncio
async def test_http_api_audit_and_timeline_endpoints():
    """Verify HTTP endpoints /api/audit-logs, /api/transactions, and /api/invoices/{id}/timeline."""
    mock_db = MockDatabase()
    user_id = "user_http_test"

    # Seed User
    user_doc = {
        "id": user_id,
        "email": "auditor@example.com",
        "hashed_password": "pw",
        "name": "Audit Tester",
        "created_at": datetime.now(timezone.utc),
    }
    await mock_db.users.insert_one(user_doc)

    # Seed Invoice
    inv_doc = {
        "internal_id": "inv_api_test",
        "invoice_number": "INV-2026-0500",
        "user_id": user_id,
        "customer_id": "cust_1",
        "currency": "USD",
        "total": Decimal("250.00"),
        "status": InvoiceStatus.DRAFT.value,
        "created_at": datetime.now(timezone.utc),
    }
    await mock_db.invoices.insert_one(inv_doc)

    # Seed Audit Log
    await mock_db.audit_logs.insert_one(
        {
            "id": "aud_log_1",
            "user_id": user_id,
            "actor": "user",
            "action": "invoice.created",
            "resource_type": "invoice",
            "resource_id": "inv_api_test",
            "result": "success",
            "correlation_id": "corr-1",
            "metadata": {"invoice_number": "INV-2026-0500"},
            "created_at": datetime.now(timezone.utc),
        }
    )

    # Seed Transaction
    await mock_db.transactions.insert_one(
        {
            "id": "txn_1",
            "user_id": user_id,
            "invoice_id": "inv_api_test",
            "invoice_number": "INV-2026-0500",
            "amount": Decimal("250.00"),
            "currency": SupportedCurrency.USD.value,
            "status": "completed",
            "created_at": datetime.now(timezone.utc),
        }
    )

    token = create_access_token(subject=user_id)
    headers = {"Authorization": f"Bearer {token}"}

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 1. Audit logs list
            r_logs = await client.get("/api/audit-logs", headers=headers)
            assert r_logs.status_code == 200
            data_logs = r_logs.json()
            assert data_logs["total"] == 1
            assert data_logs["items"][0]["action"] == "invoice.created"

            # 2. Transactions list
            r_txns = await client.get("/api/transactions", headers=headers)
            assert r_txns.status_code == 200
            data_txns = r_txns.json()
            assert data_txns["total"] == 1
            assert data_txns["items"][0]["amount"] == "250.00"

            # 3. Invoice timeline
            r_timeline = await client.get("/api/invoices/inv_api_test/timeline", headers=headers)
            assert r_timeline.status_code == 200
            data_timeline = r_timeline.json()
            assert data_timeline["invoice_id"] == "inv_api_test"
            assert len(data_timeline["events"]) == 1
            assert data_timeline["events"][0]["action_label"] == "Invoice Draft Created"
    finally:
        app.dependency_overrides.clear()
