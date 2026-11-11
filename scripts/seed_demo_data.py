"""PAYFLOW AI — Standalone Demo Data Seed Script (Prompt 35).

Seeds a live MongoDB instance with clearly-labelled FICTIONAL demo data
for judges, evaluators, and local reviewers.

Usage:
    # From project root:
    MONGODB_URI="mongodb://localhost:27017" python scripts/seed_demo_data.py

    # Or with Atlas:
    MONGODB_URI="mongodb+srv://..." MONGODB_DB_NAME="payflow_demo" python scripts/seed_demo_data.py

IMPORTANT:
  - All data is FICTIONAL and labelled [DEMO/SANDBOX].
  - No real PayPal payment confirmations are created.
  - PayPal invoice IDs are sandbox-only placeholders; they look real but
    are never sent to live PayPal APIs by this script.
  - Run against an isolated demo/test database — never production.
"""

import asyncio
import os
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

# ---------------------------------------------------------------------------
# Allow running from project root without installing the package
# ---------------------------------------------------------------------------
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_backend_dir = os.path.join(_project_root, "backend")
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.core.security import hash_password
    from app.db.indexes import create_indexes
    from app.db.mongodb import get_codec_options
    from app.models.approval import ActionType, Approval, ApprovalStatus
    from app.models.audit import ActorType, AuditLog
    from app.models.customer import BillingAddress, Customer
    from app.models.enums import ReminderStage, ReminderStatus
    from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
    from app.models.reminder import Reminder
    from app.models.transaction import Transaction
    from app.models.user import User
    from app.services.invoice_service import compute_invoice_payload_snapshot, compute_payload_hash
except ImportError as exc:
    print(f"[ERROR] Import failed: {exc}")
    print("  Make sure you run this from the project root with PYTHONPATH=backend/ set,")
    print("  or just use the demo_runner.py for a zero-setup local demo.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "payflow_demo")

# [DEMO] Primary demo business-owner account
DEMO_USER_EMAIL = "demo@payflowai.com"
DEMO_USER_PASSWORD = "DemoPassword2026!"
DEMO_USER_ID = "usr_demo_vanguard_2026"

print("""
╔══════════════════════════════════════════════════════════════════════════╗
║          PAYFLOW AI — DEMO DATA SEED SCRIPT                              ║
║          ⚠  ALL DATA IS FICTIONAL / SANDBOX ONLY                        ║
║          ⚠  Run against an isolated demo database — NOT production       ║
╚══════════════════════════════════════════════════════════════════════════╝
""")


async def drop_existing_demo_data(db) -> None:
    """Remove only previously seeded demo documents (marked with _demo=True or demo IDs)."""
    print("[SEED] Dropping stale demo data...")
    for col_name in [
        "users",
        "customers",
        "invoices",
        "approvals",
        "reminders",
        "transactions",
        "audit_logs",
    ]:
        await db[col_name].delete_many({"_demo": True})
    # Also remove by demo user_id / email in case indexes exist
    await db.users.delete_many({"email": DEMO_USER_EMAIL})
    await db.customers.delete_many({"user_id": DEMO_USER_ID})
    await db.invoices.delete_many({"user_id": DEMO_USER_ID})
    await db.approvals.delete_many({"user_id": DEMO_USER_ID})
    await db.reminders.delete_many({"user_id": DEMO_USER_ID})
    await db.transactions.delete_many({"user_id": DEMO_USER_ID})
    await db.audit_logs.delete_many({"user_id": DEMO_USER_ID})
    print("  ✓ Stale demo records removed.")


async def seed(db) -> None:
    now = datetime.now(timezone.utc)
    today = now.date()

    # ------------------------------------------------------------------ #
    # 1. DEMO USER                                                        #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo user (FICTIONAL)...")
    demo_user = User(
        id=DEMO_USER_ID,
        email=DEMO_USER_EMAIL,
        name="Eleanor Vance",
        business_name="Vanguard Advisory Partners",
        hashed_password=hash_password(DEMO_USER_PASSWORD),
        is_active=True,
    )
    user_doc = {
        **demo_user.model_dump(),
        "_demo": True,
        "_demo_note": "FICTIONAL business owner — created by seed_demo_data.py",
    }
    await db.users.replace_one({"id": DEMO_USER_ID}, user_doc, upsert=True)
    print(f"  ✓ User: {DEMO_USER_EMAIL} (password: {DEMO_USER_PASSWORD})")

    # ------------------------------------------------------------------ #
    # 2. CUSTOMERS — 4 entirely fictional companies                       #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo customers (FICTIONAL)...")
    customers = [
        Customer(
            id="cust_001",
            user_id=DEMO_USER_ID,
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
            created_at=now - timedelta(days=90),
        ),
        Customer(
            id="cust_002",
            user_id=DEMO_USER_ID,
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
            notes="Net 14 payment terms. Settles promptly.",
            is_active=True,
            invoice_count=1,
            created_at=now - timedelta(days=60),
        ),
        Customer(
            id="cust_003",
            user_id=DEMO_USER_ID,
            name="Stark Advisory Group",
            email="ap@starkadvisory.example",
            company="Stark Advisory Group LLC",
            billing_address=BillingAddress(
                address_line_1="1 Avengers Tower, Floor 42",
                city="New York",
                state="NY",
                postal_code="10001",
                country_code="US",
            ),
            notes="Strategic consulting retainer. Invoiced quarterly.",
            is_active=True,
            invoice_count=1,
            created_at=now - timedelta(days=45),
        ),
        Customer(
            id="cust_004",
            user_id=DEMO_USER_ID,
            name="Cyberdyne Analytics",
            email="finance@cyberdyne.example",
            company="Cyberdyne Analytics Corp.",
            billing_address=BillingAddress(
                address_line_1="2144 Skynet Boulevard",
                city="Austin",
                state="TX",
                postal_code="78701",
                country_code="US",
            ),
            notes="New client. Net 30 terms agreed.",
            is_active=True,
            invoice_count=1,
            created_at=now - timedelta(days=20),
        ),
    ]
    for c in customers:
        doc = {**c.model_dump(), "_demo": True}
        await db.customers.replace_one({"id": c.id}, doc, upsert=True)
        print(f"  ✓ Customer: {c.name} <{c.email}>")

    # ------------------------------------------------------------------ #
    # 3. INVOICES — 5 invoices at different lifecycle stages              #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo invoices (FICTIONAL, Sandbox only)...")

    inv1 = Invoice(
        internal_id="inv_001_settled",
        user_id=DEMO_USER_ID,
        customer_id="cust_002",
        invoice_number="INV-2026-0001",
        items=[
            InvoiceItem(name="API Integration Services — Q3 2026", quantity=Decimal("1"), unit_price=Decimal("3500.00")),
            InvoiceItem(name="Technical Documentation Package", quantity=Decimal("1"), unit_price=Decimal("850.00")),
        ],
        subtotal=Decimal("4350.00"),
        tax=Decimal("0.00"),
        total=Decimal("4350.00"),
        currency="USD",
        issue_date=today - timedelta(days=28),
        due_date=today - timedelta(days=14),
        status=InvoiceStatus.PAID,
        paypal_invoice_id="INV2-XXXX-DEMO-0001-SANDBOX",
        paypal_invoice_url="https://www.sandbox.paypal.com/invoice/details/INV2-XXXX-DEMO-0001-SANDBOX",
        sent_at=now - timedelta(days=27),
        paid_at=now - timedelta(days=15),
        notes="Thank you for your prompt payment. [DEMO SANDBOX ONLY]",
        created_at=now - timedelta(days=28),
        updated_at=now - timedelta(days=15),
    )

    inv2 = Invoice(
        internal_id="inv_002_overdue",
        user_id=DEMO_USER_ID,
        customer_id="cust_003",
        invoice_number="INV-2026-0002",
        items=[
            InvoiceItem(name="Strategic Consulting Retainer — July 2026", quantity=Decimal("1"), unit_price=Decimal("7500.00")),
        ],
        subtotal=Decimal("7500.00"),
        tax=Decimal("0.00"),
        total=Decimal("7500.00"),
        currency="USD",
        issue_date=today - timedelta(days=52),
        due_date=today - timedelta(days=38),
        status=InvoiceStatus.OVERDUE,
        paypal_invoice_id="INV2-YYYY-DEMO-0002-SANDBOX",
        paypal_invoice_url="https://www.sandbox.paypal.com/invoice/details/INV2-YYYY-DEMO-0002-SANDBOX",
        sent_at=now - timedelta(days=51),
        notes="38 days past due. AI reminder drafted awaiting approval.",
        created_at=now - timedelta(days=52),
        updated_at=now - timedelta(days=5),
    )

    inv3 = Invoice(
        internal_id="inv_003_pending_approval",
        user_id=DEMO_USER_ID,
        customer_id="cust_001",
        invoice_number="INV-2026-0003",
        items=[
            InvoiceItem(name="Website Development — Phase 2 Delivery", quantity=Decimal("1"), unit_price=Decimal("12000.00")),
            InvoiceItem(name="Design System & Component Library", quantity=Decimal("1"), unit_price=Decimal("3500.00")),
        ],
        subtotal=Decimal("15500.00"),
        tax=Decimal("0.00"),
        total=Decimal("15500.00"),
        currency="USD",
        issue_date=today,
        due_date=today + timedelta(days=30),
        status=InvoiceStatus.PENDING_APPROVAL,
        notes="AI-extracted from natural language request. Awaiting merchant approval before PayPal dispatch.",
        created_at=now,
        updated_at=now,
    )

    inv4 = Invoice(
        internal_id="inv_004_draft",
        user_id=DEMO_USER_ID,
        customer_id="cust_004",
        invoice_number="INV-2026-0004",
        items=[
            InvoiceItem(name="Data Pipeline Architecture Consultation", quantity=Decimal("8"), unit_price=Decimal("375.00")),
        ],
        subtotal=Decimal("3000.00"),
        tax=Decimal("0.00"),
        total=Decimal("3000.00"),
        currency="USD",
        issue_date=today,
        due_date=today + timedelta(days=14),
        status=InvoiceStatus.DRAFT,
        notes="Draft — pending merchant review and submission.",
        created_at=now,
        updated_at=now,
    )

    inv5 = Invoice(
        internal_id="inv_005_sent",
        user_id=DEMO_USER_ID,
        customer_id="cust_001",
        invoice_number="INV-2026-0005",
        items=[
            InvoiceItem(name="Annual SaaS Platform License", quantity=Decimal("1"), unit_price=Decimal("9600.00")),
        ],
        subtotal=Decimal("9600.00"),
        tax=Decimal("0.00"),
        total=Decimal("9600.00"),
        currency="USD",
        issue_date=today - timedelta(days=5),
        due_date=today + timedelta(days=25),
        status=InvoiceStatus.SENT,
        paypal_invoice_id="INV2-ZZZZ-DEMO-0005-SANDBOX",
        paypal_invoice_url="https://www.sandbox.paypal.com/invoice/details/INV2-ZZZZ-DEMO-0005-SANDBOX",
        sent_at=now - timedelta(days=5),
        notes="Sent via PayPal Sandbox. Awaiting buyer payment.",
        created_at=now - timedelta(days=5),
        updated_at=now - timedelta(days=5),
    )

    customer_names = {c.id: c.name for c in customers}
    for inv in [inv1, inv2, inv3, inv4, inv5]:
        doc = {**inv.model_dump(), "_demo": True}
        await db.invoices.replace_one({"internal_id": inv.internal_id}, doc, upsert=True)
        cname = customer_names.get(inv.customer_id, inv.customer_id)
        print(f"  ✓ Invoice: {inv.invoice_number} [{inv.status.value}] ${inv.total} — {cname}")

    # ------------------------------------------------------------------ #
    # 4. APPROVAL RECORD for pending invoice                             #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo approval (FICTIONAL)...")
    snap3 = compute_invoice_payload_snapshot(inv3)
    hash3 = compute_payload_hash(snap3)
    approval = Approval(
        id="appr_003",
        user_id=DEMO_USER_ID,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=inv3.internal_id,
        payload_snapshot=snap3,
        payload_hash=hash3,
        status=ApprovalStatus.PENDING,
        created_at=now,
    )
    await db.approvals.replace_one({"id": "appr_003"}, {**approval.model_dump(), "_demo": True}, upsert=True)
    print(f"  ✓ Approval: appr_003 for {inv3.invoice_number} [pending] (hash={hash3[:12]}...)")

    # ------------------------------------------------------------------ #
    # 5. REMINDER for overdue invoice                                    #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo reminder (FICTIONAL)...")
    reminder = Reminder(
        id="rem_002",
        user_id=DEMO_USER_ID,
        invoice_id=inv2.internal_id,
        invoice_number=inv2.invoice_number,
        customer_id="cust_003",
        customer_name="Stark Advisory Group",
        customer_email="ap@starkadvisory.example",
        stage=ReminderStage.OVERDUE_15_PLUS,
        status=ReminderStatus.READY_FOR_APPROVAL,
        subject=f"Payment Reminder: Invoice {inv2.invoice_number} (38 Days Past Due)",
        message_body=(
            "Dear Stark Advisory Group,\n\n"
            f"This is a respectful reminder that invoice {inv2.invoice_number} for $7,500.00 USD "
            f"was due on {inv2.due_date.isoformat()} and remains outstanding.\n\n"
            "We kindly request immediate settlement via PayPal Sandbox at:\n"
            f"{inv2.paypal_invoice_url}\n\n"
            "Warm regards,\nVanguard Advisory Partners\n\n"
            "[DRAFT — awaiting merchant approval before delivery]"
        ),
        payment_link=inv2.paypal_invoice_url,
        channel="manual",
        created_at=now - timedelta(days=1),
        updated_at=now - timedelta(days=1),
    )
    await db.reminders.replace_one({"id": "rem_002"}, {**reminder.model_dump(), "_demo": True}, upsert=True)
    print(f"  ✓ Reminder: rem_002 for {inv2.invoice_number} [{reminder.status.value}]")

    # ------------------------------------------------------------------ #
    # 6. TRANSACTION RECORD for paid invoice                             #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo transaction record (FICTIONAL)...")
    transaction = Transaction(
        id="txn_001",
        user_id=DEMO_USER_ID,
        invoice_id=inv1.internal_id,
        paypal_capture_id="PAYID-DEMO-SANDBOX-TXNREF-001",
        amount=inv1.total,
        currency="USD",
        status="completed",
        created_at=now - timedelta(days=15),
    )
    await db.transactions.replace_one({"id": "txn_001"}, {**transaction.model_dump(), "_demo": True}, upsert=True)
    print("  ✓ Transaction: txn_001 [$4,350.00 settled — SANDBOX ONLY]")

    # ------------------------------------------------------------------ #
    # 7. AUDIT LOG entries                                               #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo audit log (FICTIONAL)...")
    audit_entries = [
        AuditLog(
            id="aud_001",
            user_id=DEMO_USER_ID,
            actor=ActorType.USER,
            actor_id=DEMO_USER_ID,
            action="invoice.created",
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={"invoice_number": inv1.invoice_number, "total": str(inv1.total)},
            created_at=now - timedelta(days=28),
        ),
        AuditLog(
            id="aud_002",
            user_id=DEMO_USER_ID,
            actor=ActorType.USER,
            actor_id=DEMO_USER_ID,
            action="invoice.approved",
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={"invoice_number": inv1.invoice_number},
            created_at=now - timedelta(days=27),
        ),
        AuditLog(
            id="aud_003",
            user_id=DEMO_USER_ID,
            actor=ActorType.SYSTEM,
            actor_id="paypal_adapter_v2",
            action="paypal.invoice_created",
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={"paypal_invoice_id": inv1.paypal_invoice_id},
            created_at=now - timedelta(days=27),
        ),
        AuditLog(
            id="aud_004",
            user_id=DEMO_USER_ID,
            actor=ActorType.PAYPAL_WEBHOOK,
            actor_id="DEMO-WH-EVENT-001-SANDBOX",
            action="webhook.invoice_paid",
            resource_type="invoice",
            resource_id=inv1.internal_id,
            metadata={
                "event_type": "INVOICING.INVOICE.PAID",
                "event_id": "DEMO-WH-EVENT-001-SANDBOX",
                "note": "SANDBOX webhook event — no real funds transferred",
            },
            created_at=now - timedelta(days=15),
        ),
        AuditLog(
            id="aud_005",
            user_id=DEMO_USER_ID,
            actor=ActorType.SYSTEM,
            actor_id="reminder_scheduler",
            action="reminder.scheduled",
            resource_type="reminder",
            resource_id="rem_002",
            metadata={"stage": "overdue_15_plus"},
            created_at=now - timedelta(days=1),
        ),
        AuditLog(
            id="aud_006",
            user_id=DEMO_USER_ID,
            actor=ActorType.AI_ASSISTANT,
            actor_id="invoice_extractor",
            action="invoice.created",
            resource_type="invoice",
            resource_id=inv3.internal_id,
            metadata={"extraction_method": "ai_natural_language"},
            created_at=now,
        ),
    ]
    for aud in audit_entries:
        await db.audit_logs.replace_one({"id": aud.id}, {**aud.model_dump(), "_demo": True}, upsert=True)
    print(f"  ✓ {len(audit_entries)} audit log entries inserted.")

    # ------------------------------------------------------------------ #
    # Summary                                                             #
    # ------------------------------------------------------------------ #
    print(f"""
╔══════════════════════════════════════════════════════════════════════════╗
║  SEED COMPLETE — PAYFLOW AI DEMO DATABASE                                ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Database : {MONGODB_DB_NAME:<61}║
║  Demo URL : http://localhost:3000  (or http://localhost:5173)            ║
║  Login    : {DEMO_USER_EMAIL:<61}║
║  Password : {DEMO_USER_PASSWORD:<61}║
╠══════════════════════════════════════════════════════════════════════════╣
║  ⚠  All data is FICTIONAL — no real PayPal charges or customers         ║
║  ⚠  PayPal IDs are sandbox placeholders; not live API resources         ║
║  ⚠  Remove with: db.<collection>.delete_many({{"_demo": True}})          ║
╚══════════════════════════════════════════════════════════════════════════╝
""")


async def main():
    print(f"[CONFIG] MongoDB URI  : {MONGODB_URI[:40]}...")
    print(f"[CONFIG] Database Name: {MONGODB_DB_NAME}")
    print()

    client = AsyncIOMotorClient(MONGODB_URI)
    db = client.get_database(MONGODB_DB_NAME, codec_options=get_codec_options())

    await create_indexes(db)
    await drop_existing_demo_data(db)
    await seed(db)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
