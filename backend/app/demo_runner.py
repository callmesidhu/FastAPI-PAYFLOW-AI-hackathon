"""PAYFLOW AI — Standalone Interactive Demo Server.

Enables evaluators, judges, and developers to explore the full application locally
without requiring an external MongoDB instance or PayPal live credentials.
Pre-seeds realistic accounts receivable data matching the quiet-luxury specifications.
"""

import asyncio
from contextlib import asynccontextmanager
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uvicorn

_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.main import app
from app.db.mongodb import get_db
from app.models.approval import ActionType, Approval, ApprovalStatus
from app.models.audit import ActorType, AuditLog
from app.models.customer import BillingAddress, Customer
from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
from app.models.reminder import Reminder
from app.models.enums import ReminderStage, ReminderStatus
from app.models.transaction import Transaction
from app.models.user import User
from app.core.security import create_access_token, hash_password
from app.services.invoice_service import compute_invoice_payload_snapshot, compute_payload_hash
from tests.mock_db import MockDatabase


async def seed_demo_data(db: MockDatabase) -> str:
    """Pre-seed database with realistic quiet-luxury receivables data."""
    # 1. Demo User / Business Owner
    user_id = "usr_demo_vanguard_2026"
    demo_user = User(
        id=user_id,
        email="demo@payflowai.com",
        name="Eleanor Vance",
        business_name="Vanguard Advisory Partners",
        hashed_password=hash_password("DemoPassword2026!"),
        is_active=True,
    )
    await db.users.insert_one(demo_user.model_dump())

    # Also insert alias demo user
    alias_user = User(
        id="usr_demo_vanguard_local",
        email="demo@payflow.example",
        name="Eleanor Vance",
        business_name="Vanguard Advisory Partners",
        hashed_password=hash_password("PayflowDemo2026!"),
        is_active=True,
    )
    await db.users.insert_one(alias_user.model_dump())

    # 2. Customers
    customers_data = [
        Customer(
            id="cust_001",
            user_id=user_id,
            name="Acme Global Solutions",
            email="finance@acmeglobal.example",
            company="Acme Global Solutions Inc.",
            billing_address=BillingAddress(
                address_line_1="100 Enterprise Way, Suite 400",
                city="San Francisco",
                state="CA",
                postal_code="94107",
                country_code="US",
            ),
            notes="Net 30 enterprise terms. Requires purchase order citations.",
            is_active=True,
            invoice_count=2,
        ),
        Customer(
            id="cust_002",
            user_id=user_id,
            name="Globex Corporation",
            email="billing@globex.example",
            company="Globex Corporation Ltd.",
            billing_address=BillingAddress(
                address_line_1="742 Evergreen Terrace",
                city="Springfield",
                state="OR",
                postal_code="97477",
                country_code="US",
            ),
            notes="Net 14 payment terms. Settles promptly via PayPal.",
            is_active=True,
            invoice_count=1,
        ),
        Customer(
            id="cust_003",
            user_id=user_id,
            name="Stark Advisory Group",
            email="ap@starkadvisory.example",
            company="Stark Advisory Group",
            billing_address=BillingAddress(
                address_line_1="890 Fifth Avenue",
                city="New York",
                state="NY",
                postal_code="10021",
                country_code="US",
            ),
            notes="Net 14. Currently undergoing accounts payable audit.",
            is_active=True,
            invoice_count=1,
        ),
        Customer(
            id="cust_004",
            user_id=user_id,
            name="Cyberdyne Analytics",
            email="accounts@cyberdyne.example",
            company="Cyberdyne Analytics LLC",
            billing_address=BillingAddress(
                address_line_1="18144 El Camino Real",
                city="Sunnyvale",
                state="CA",
                postal_code="94086",
                country_code="US",
            ),
            notes="Net 30. Quarterly retainer engagements.",
            is_active=True,
            invoice_count=1,
        ),
    ]
    for c in customers_data:
        await db.customers.insert_one(c.model_dump())

    # 3. Invoices
    today = date.today()

    # Invoice 1: PAID ($2,400)
    inv1 = Invoice(
        internal_id="inv_001_settled",
        user_id=user_id,
        customer_id="cust_002",
        customer_name="Globex Corporation",
        invoice_number="INV-2026-0001",
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=6),
        currency="USD",
        items=[
            InvoiceItem(name="Brand Identity & Design System", quantity=1, unit_price=Decimal("2400.00"), tax=Decimal("0.00"))
        ],
        subtotal=Decimal("2400.00"),
        tax=Decimal("0.00"),
        total=Decimal("2400.00"),
        status=InvoiceStatus.PAID,
        paypal_invoice_id="INV2-9988-E2E-PAID",
        paypal_invoice_url="https://www.sandbox.paypal.com/invoice/s/pay/INV2-9988-E2E-PAID",
        sent_at=datetime.now(timezone.utc) - timedelta(days=19),
        paid_at=datetime.now(timezone.utc) - timedelta(days=5),
        notes="Net 14 terms. Settled via verified PayPal Webhook.",
    )
    await db.invoices.insert_one(inv1.model_dump())

    # Transaction for Invoice 1
    tx1 = Transaction(
        id="tx_001_capture",
        user_id=user_id,
        invoice_id=inv1.internal_id,
        paypal_capture_id="CAPTURE-SANDBOX-7788",
        amount=inv1.total,
        currency=inv1.currency,
        status="completed",
    )
    await db.transactions.insert_one(tx1.model_dump())

    # Invoice 2: SENT / Outstanding ($3,500)
    inv2 = Invoice(
        internal_id="inv_002_sent",
        user_id=user_id,
        customer_id="cust_001",
        customer_name="Acme Global Solutions",
        invoice_number="INV-2026-0002",
        issue_date=today - timedelta(days=7),
        due_date=today + timedelta(days=7),
        currency="USD",
        items=[
            InvoiceItem(name="Executive Strategic Advisory - Phase 1", quantity=1, unit_price=Decimal("3500.00"), tax=Decimal("0.00"))
        ],
        subtotal=Decimal("3500.00"),
        tax=Decimal("0.00"),
        total=Decimal("3500.00"),
        status=InvoiceStatus.SENT,
        paypal_invoice_id="INV2-1122-SANDBOX-SENT",
        paypal_invoice_url="https://www.sandbox.paypal.com/invoice/s/pay/INV2-1122-SANDBOX-SENT",
        sent_at=datetime.now(timezone.utc) - timedelta(days=7),
        notes="Net 14 terms. Awaiting client settlement.",
    )
    await db.invoices.insert_one(inv2.model_dump())

    # Invoice 3: OVERDUE ($4,800)
    inv3 = Invoice(
        internal_id="inv_003_overdue",
        user_id=user_id,
        customer_id="cust_003",
        customer_name="Stark Advisory Group",
        invoice_number="INV-2026-0003",
        issue_date=today - timedelta(days=22),
        due_date=today - timedelta(days=5),
        currency="USD",
        items=[
            InvoiceItem(name="Financial Restructuring & Advisory", quantity=1, unit_price=Decimal("4800.00"), tax=Decimal("0.00"))
        ],
        subtotal=Decimal("4800.00"),
        tax=Decimal("0.00"),
        total=Decimal("4800.00"),
        status=InvoiceStatus.OVERDUE,
        paypal_invoice_id="INV2-3344-SANDBOX-OVERDUE",
        paypal_invoice_url="https://www.sandbox.paypal.com/invoice/s/pay/INV2-3344-SANDBOX-OVERDUE",
        sent_at=datetime.now(timezone.utc) - timedelta(days=22),
        notes="Net 14 terms. 5 days overdue (Stage: 4-7 days overdue).",
    )
    await db.invoices.insert_one(inv3.model_dump())

    # Invoice 4: PENDING APPROVAL ($5,200)
    inv4 = Invoice(
        internal_id="inv_004_approval",
        user_id=user_id,
        customer_id="cust_001",
        customer_name="Acme Global Solutions",
        invoice_number="INV-2026-0004",
        issue_date=today,
        due_date=today + timedelta(days=14),
        currency="USD",
        items=[
            InvoiceItem(name="Quarterly Retainer - Enterprise Systems", quantity=1, unit_price=Decimal("5200.00"), tax=Decimal("0.00"))
        ],
        subtotal=Decimal("5200.00"),
        tax=Decimal("0.00"),
        total=Decimal("5200.00"),
        status=InvoiceStatus.PENDING_APPROVAL,
        notes="Net 14 terms. Awaiting merchant authorization.",
    )
    await db.invoices.insert_one(inv4.model_dump())

    # Approval Item for Invoice 4
    snap4 = compute_invoice_payload_snapshot(inv4)
    hash4 = compute_payload_hash(snap4)
    appr4 = Approval(
        id="appr_004_pending",
        user_id=user_id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=inv4.internal_id,
        payload_snapshot=snap4,
        payload_hash=hash4,
        status=ApprovalStatus.PENDING,
    )
    await db.approvals.insert_one(appr4.model_dump())

    # Invoice 5: DRAFT ($1,850)
    inv5 = Invoice(
        internal_id="inv_005_draft",
        user_id=user_id,
        customer_id="cust_004",
        customer_name="Cyberdyne Analytics",
        invoice_number="INV-2026-0005",
        issue_date=today,
        due_date=today + timedelta(days=30),
        currency="USD",
        items=[
            InvoiceItem(name="Security Compliance Review", quantity=1, unit_price=Decimal("1850.00"), tax=Decimal("0.00"))
        ],
        subtotal=Decimal("1850.00"),
        tax=Decimal("0.00"),
        total=Decimal("1850.00"),
        status=InvoiceStatus.DRAFT,
        notes="Net 30 terms. Internal draft under review.",
    )
    await db.invoices.insert_one(inv5.model_dump())

    # 4. Payment Reminder (4-7 days overdue for Invoice 3)
    rem3 = Reminder(
        id="rem_003_stage2",
        user_id=user_id,
        invoice_id=inv3.internal_id,
        invoice_number=inv3.invoice_number,
        customer_id="cust_003",
        customer_name="Stark Advisory Group",
        customer_email="ap@starkadvisory.example",
        stage=ReminderStage.OVERDUE_4_7,
        status=ReminderStatus.READY_FOR_APPROVAL,
        subject=f"Friendly follow-up regarding invoice {inv3.invoice_number}",
        message_body=(
            f"Dear Stark Advisory Group,\n\n"
            f"This is a respectful follow-up regarding invoice {inv3.invoice_number} for ${inv3.total} USD, "
            f"which was due on {inv3.due_date.isoformat()}.\n\n"
            f"If payment is already in progress, please disregard this note. You may review and settle the invoice "
            f"securely via PayPal Developer Sandbox at:\n{inv3.paypal_invoice_url}\n\n"
            f"Warm regards,\nVanguard Advisory Partners"
        ),
        payment_link=inv3.paypal_invoice_url,
        channel="manual",
    )
    await db.reminders.insert_one(rem3.model_dump())

    # 5. Chronological Audit Logs for Invoice 1
    audit_events = [
        AuditLog(
            id="aud_001_create",
            user_id=user_id,
            action="invoice.created",
            actor=ActorType.USER,
            actor_id=user_id,
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={"invoice_number": inv1.invoice_number, "total": str(inv1.total)},
            created_at=datetime.now(timezone.utc) - timedelta(days=20),
        ),
        AuditLog(
            id="aud_001_submit",
            user_id=user_id,
            action="invoice.submitted_for_approval",
            actor=ActorType.USER,
            actor_id=user_id,
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={"invoice_number": inv1.invoice_number},
            created_at=datetime.now(timezone.utc) - timedelta(days=19, hours=2),
        ),
        AuditLog(
            id="aud_001_approve",
            user_id=user_id,
            action="invoice.approved",
            actor=ActorType.USER,
            actor_id=user_id,
            resource_type="approval",
            resource_id=inv1.internal_id,
            metadata={"invoice_number": inv1.invoice_number},
            created_at=datetime.now(timezone.utc) - timedelta(days=19, hours=1),
        ),
        AuditLog(
            id="aud_001_sandbox_create",
            user_id=user_id,
            action="paypal.invoice_created",
            actor=ActorType.SYSTEM,
            actor_id="paypal_adapter_v2",
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={"paypal_invoice_id": inv1.paypal_invoice_id},
            created_at=datetime.now(timezone.utc) - timedelta(days=19),
        ),
        AuditLog(
            id="aud_001_sandbox_send",
            user_id=user_id,
            action="paypal.invoice_sent",
            actor=ActorType.USER,
            actor_id=user_id,
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={"paypal_invoice_id": inv1.paypal_invoice_id, "recipient": "billing@globex.example"},
            created_at=datetime.now(timezone.utc) - timedelta(days=19),
        ),
        AuditLog(
            id="aud_001_settle",
            user_id=user_id,
            action="payment.settled",
            actor=ActorType.PAYPAL_WEBHOOK,
            actor_id="paypal_webhook_engine",
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={
                "paypal_invoice_id": inv1.paypal_invoice_id,
                "amount": str(inv1.total),
                "event_type": "INVOICING.INVOICE.PAID",
            },
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
        ),
    ]
    for a in audit_events:
        await db.audit_logs.insert_one(a.model_dump())

    # Return valid JWT token for demo user
    token = create_access_token(subject=user_id)
    return token


demo_db = MockDatabase()
_seeded_token: str = ""


@asynccontextmanager
async def demo_lifespan(app):
    """Seed demo database and override get_db dependency on server startup without external MongoDB."""
    global _seeded_token
    _seeded_token = await seed_demo_data(demo_db)
    app.dependency_overrides[get_db] = lambda: demo_db
    print(f"\n[PAYFLOW DEMO READY] Pre-seeded demo account initialized.")
    print(f"  User Email : demo@payflowai.com")
    print(f"  Password   : DemoPassword2026!")
    print(f"  Demo Token : {_seeded_token[:20]}...\n")
    yield


app.router.lifespan_context = demo_lifespan


if __name__ == "__main__":
    uvicorn.run("app.demo_runner:app", host="127.0.0.1", port=8000, reload=False)
