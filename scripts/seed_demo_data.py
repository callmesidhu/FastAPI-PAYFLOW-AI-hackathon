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
    from app.core.security import create_access_token, hash_password
    from app.models.approval import ActionType, Approval, ApprovalStatus
    from app.models.audit import ActorType, AuditLog
    from app.models.customer import BillingAddress, Customer
    from app.models.invoice import Invoice, InvoiceItem, InvoiceStatus
    from app.models.reminder import Reminder
    from app.models.enums import ReminderStage, ReminderStatus
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
    """Remove any stale demo data from a previous run."""
    print("[SEED] Dropping stale demo data...")
    for collection in [
        "users", "customers", "invoices",
        "approvals", "reminders", "audit_logs", "transactions", "webhook_events",
    ]:
        await db[collection].delete_many({"_demo": True})
    print("  ✓ Stale demo records removed.")


async def seed(db) -> None:
    """Insert all FICTIONAL demo records."""

    now = datetime.now(tz=timezone.utc)
    today = date.today()

    # ------------------------------------------------------------------ #
    # 1. DEMO USER                                                        #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo user (FICTIONAL)...")
    demo_user = {
        "_demo": True,
        "_demo_note": "FICTIONAL business owner — created by seed_demo_data.py",
        "id": DEMO_USER_ID,
        "email": DEMO_USER_EMAIL,
        "name": "Eleanor Vance",
        "business_name": "Vanguard Advisory Partners",          # fictional firm
        "hashed_password": hash_password(DEMO_USER_PASSWORD),
        "is_active": True,
        "created_at": now.isoformat(),
        "paypal_connected": False,
    }
    await db.users.replace_one({"id": DEMO_USER_ID}, demo_user, upsert=True)
    print(f"  ✓ User: {DEMO_USER_EMAIL} (password: {DEMO_USER_PASSWORD})")

    # ------------------------------------------------------------------ #
    # 2. CUSTOMERS  — 4 entirely fictional companies                      #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo customers (FICTIONAL)...")
    customers = [
        {
            "_demo": True,
            "_demo_note": "FICTIONAL customer — Acme Global Solutions",
            "id": "cust_001",
            "user_id": DEMO_USER_ID,
            "name": "Acme Global Solutions",
            "email": "finance@acmeglobal.example",
            "company": "Acme Global Solutions Inc.",
            "billing_address": {
                "address_line_1": "100 Enterprise Way, Suite 400",
                "city": "San Francisco", "state": "CA",
                "postal_code": "94107", "country_code": "US",
            },
            "notes": "Net 30 enterprise terms. Requires purchase order citations.",
            "is_active": True,
            "invoice_count": 2,
            "created_at": (now - timedelta(days=90)).isoformat(),
        },
        {
            "_demo": True,
            "_demo_note": "FICTIONAL customer — Globex Corporation",
            "id": "cust_002",
            "user_id": DEMO_USER_ID,
            "name": "Globex Corporation",
            "email": "billing@globex.example",
            "company": "Globex Corporation Ltd.",
            "billing_address": {
                "address_line_1": "742 Evergreen Terrace",
                "city": "Springfield", "state": "OR",
                "postal_code": "97477", "country_code": "US",
            },
            "notes": "Net 14 payment terms. Settles promptly.",
            "is_active": True,
            "invoice_count": 1,
            "created_at": (now - timedelta(days=60)).isoformat(),
        },
        {
            "_demo": True,
            "_demo_note": "FICTIONAL customer — Stark Advisory Group",
            "id": "cust_003",
            "user_id": DEMO_USER_ID,
            "name": "Stark Advisory Group",
            "email": "ap@starkadvisory.example",
            "company": "Stark Advisory Group LLC",
            "billing_address": {
                "address_line_1": "1 Avengers Tower, Floor 42",
                "city": "New York", "state": "NY",
                "postal_code": "10001", "country_code": "US",
            },
            "notes": "Strategic consulting retainer. Invoiced quarterly.",
            "is_active": True,
            "invoice_count": 1,
            "created_at": (now - timedelta(days=45)).isoformat(),
        },
        {
            "_demo": True,
            "_demo_note": "FICTIONAL customer — Cyberdyne Analytics",
            "id": "cust_004",
            "user_id": DEMO_USER_ID,
            "name": "Cyberdyne Analytics",
            "email": "finance@cyberdyne.example",
            "company": "Cyberdyne Analytics Corp.",
            "billing_address": {
                "address_line_1": "2144 Skynet Boulevard",
                "city": "Austin", "state": "TX",
                "postal_code": "78701", "country_code": "US",
            },
            "notes": "New client. Net 30 terms agreed.",
            "is_active": True,
            "invoice_count": 1,
            "created_at": (now - timedelta(days=20)).isoformat(),
        },
    ]
    for c in customers:
        await db.customers.replace_one({"id": c["id"]}, c, upsert=True)
        print(f"  ✓ Customer: {c['name']} <{c['email']}>")

    # ------------------------------------------------------------------ #
    # 3. INVOICES  — 5 invoices at different lifecycle stages             #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo invoices (FICTIONAL, Sandbox only)...")

    invoices = [
        # --- PAID (settled 15 days ago via PayPal Sandbox) ---
        {
            "_demo": True,
            "_demo_note": "FICTIONAL — settled via PayPal Sandbox. No real payment occurred.",
            "id": "inv_001_settled",
            "user_id": DEMO_USER_ID,
            "invoice_number": "INV-2026-0001",
            "customer_id": "cust_002",
            "customer_name": "Globex Corporation",
            "customer_email": "billing@globex.example",
            "line_items": [
                {"description": "API Integration Services — Q3 2026", "quantity": 1, "unit_price": "3500.00", "amount": "3500.00"},
                {"description": "Technical Documentation Package", "quantity": 1, "unit_price": "850.00", "amount": "850.00"},
            ],
            "subtotal": "4350.00",
            "tax_percent": "0.00",
            "tax_amount": "0.00",
            "total_amount": "4350.00",
            "currency": "USD",
            "issue_date": (today - timedelta(days=28)).isoformat(),
            "due_date": (today - timedelta(days=14)).isoformat(),
            "status": "paid",
            "paypal_invoice_id": "INV2-XXXX-DEMO-0001-SANDBOX",  # sandbox placeholder
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/details/INV2-XXXX-DEMO-0001-SANDBOX",
            "notes": "Thank you for your prompt payment.",
            "created_at": (now - timedelta(days=28)).isoformat(),
            "updated_at": (now - timedelta(days=15)).isoformat(),
        },
        # --- OVERDUE (38 days past due) ---
        {
            "_demo": True,
            "_demo_note": "FICTIONAL — overdue invoice for demo reminder flow.",
            "id": "inv_002_overdue",
            "user_id": DEMO_USER_ID,
            "invoice_number": "INV-2026-0002",
            "customer_id": "cust_003",
            "customer_name": "Stark Advisory Group",
            "customer_email": "ap@starkadvisory.example",
            "line_items": [
                {"description": "Strategic Consulting Retainer — July 2026", "quantity": 1, "unit_price": "7500.00", "amount": "7500.00"},
            ],
            "subtotal": "7500.00",
            "tax_percent": "0.00",
            "tax_amount": "0.00",
            "total_amount": "7500.00",
            "currency": "USD",
            "issue_date": (today - timedelta(days=52)).isoformat(),
            "due_date": (today - timedelta(days=38)).isoformat(),
            "status": "overdue",
            "paypal_invoice_id": "INV2-YYYY-DEMO-0002-SANDBOX",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/details/INV2-YYYY-DEMO-0002-SANDBOX",
            "notes": "Third reminder sent. Escalation pending.",
            "created_at": (now - timedelta(days=52)).isoformat(),
            "updated_at": (now - timedelta(days=5)).isoformat(),
        },
        # --- PENDING APPROVAL (waiting merchant sign-off before dispatch) ---
        {
            "_demo": True,
            "_demo_note": "FICTIONAL — pending approval; demonstrates Approval Center.",
            "id": "inv_003_pending_approval",
            "user_id": DEMO_USER_ID,
            "invoice_number": "INV-2026-0003",
            "customer_id": "cust_001",
            "customer_name": "Acme Global Solutions",
            "customer_email": "finance@acmeglobal.example",
            "line_items": [
                {"description": "Website Development — Phase 2 Delivery", "quantity": 1, "unit_price": "12000.00", "amount": "12000.00"},
                {"description": "Design System & Component Library", "quantity": 1, "unit_price": "3500.00", "amount": "3500.00"},
            ],
            "subtotal": "15500.00",
            "tax_percent": "0.00",
            "tax_amount": "0.00",
            "total_amount": "15500.00",
            "currency": "USD",
            "issue_date": today.isoformat(),
            "due_date": (today + timedelta(days=30)).isoformat(),
            "status": "pending_approval",
            "notes": "AI-extracted from natural language request. Awaiting merchant approval before PayPal dispatch.",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
        # --- DRAFT (AI-extracted, not yet submitted) ---
        {
            "_demo": True,
            "_demo_note": "FICTIONAL — draft created via AI invoice extraction.",
            "id": "inv_004_draft",
            "user_id": DEMO_USER_ID,
            "invoice_number": "INV-2026-0004",
            "customer_id": "cust_004",
            "customer_name": "Cyberdyne Analytics",
            "customer_email": "finance@cyberdyne.example",
            "line_items": [
                {"description": "Data Pipeline Architecture Consultation", "quantity": 8, "unit_price": "375.00", "amount": "3000.00"},
            ],
            "subtotal": "3000.00",
            "tax_percent": "0.00",
            "tax_amount": "0.00",
            "total_amount": "3000.00",
            "currency": "USD",
            "issue_date": today.isoformat(),
            "due_date": (today + timedelta(days=14)).isoformat(),
            "status": "draft",
            "notes": "Draft — pending merchant review and submission.",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
        # --- SENT (live on PayPal Sandbox, awaiting buyer payment) ---
        {
            "_demo": True,
            "_demo_note": "FICTIONAL — sent to PayPal Sandbox. Awaiting sandbox payment.",
            "id": "inv_005_sent",
            "user_id": DEMO_USER_ID,
            "invoice_number": "INV-2026-0005",
            "customer_id": "cust_001",
            "customer_name": "Acme Global Solutions",
            "customer_email": "finance@acmeglobal.example",
            "line_items": [
                {"description": "Annual SaaS Platform License", "quantity": 1, "unit_price": "9600.00", "amount": "9600.00"},
            ],
            "subtotal": "9600.00",
            "tax_percent": "0.00",
            "tax_amount": "0.00",
            "total_amount": "9600.00",
            "currency": "USD",
            "issue_date": (today - timedelta(days=5)).isoformat(),
            "due_date": (today + timedelta(days=25)).isoformat(),
            "status": "sent",
            "paypal_invoice_id": "INV2-ZZZZ-DEMO-0005-SANDBOX",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/details/INV2-ZZZZ-DEMO-0005-SANDBOX",
            "notes": "Sent via PayPal Sandbox on " + (today - timedelta(days=5)).isoformat(),
            "created_at": (now - timedelta(days=5)).isoformat(),
            "updated_at": (now - timedelta(days=5)).isoformat(),
        },
    ]
    for inv in invoices:
        await db.invoices.replace_one({"id": inv["id"]}, inv, upsert=True)
        print(f"  ✓ Invoice: {inv['invoice_number']} [{inv['status']}] ${inv['total_amount']} — {inv['customer_name']}")

    # ------------------------------------------------------------------ #
    # 4. APPROVAL RECORD for pending invoice                             #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo approval (FICTIONAL)...")
    approval_payload = {
        "invoice_id": "inv_003_pending_approval",
        "invoice_number": "INV-2026-0003",
        "customer_name": "Acme Global Solutions",
        "total_amount": "15500.00",
        "currency": "USD",
        "line_items": invoices[2]["line_items"],
    }
    approval = {
        "_demo": True,
        "id": "appr_003",
        "invoice_id": "inv_003_pending_approval",
        "user_id": DEMO_USER_ID,
        "status": "pending",
        "payload_snapshot": str(approval_payload),
        "payload_hash": "demo-sha256-hash-placeholder-not-real",
        "submitted_by": DEMO_USER_ID,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }
    await db.approvals.replace_one({"id": "appr_003"}, approval, upsert=True)
    print("  ✓ Approval: appr_003 for INV-2026-0003 [pending]")

    # ------------------------------------------------------------------ #
    # 5. REMINDER for overdue invoice                                     #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo reminder (FICTIONAL)...")
    reminder = {
        "_demo": True,
        "_demo_note": "FICTIONAL — AI-drafted reminder for overdue invoice.",
        "id": "rem_002",
        "invoice_id": "inv_002_overdue",
        "user_id": DEMO_USER_ID,
        "stage": "overdue_30_plus",
        "status": "pending_approval",
        "channel": "email",
        "draft_message": (
            "Dear Stark Advisory Group,\n\n"
            "This is a respectful reminder that invoice INV-2026-0002 for $7,500.00 "
            "was due on " + (today - timedelta(days=38)).isoformat() + " and remains outstanding. "
            "We kindly request immediate settlement or contact us to arrange a payment plan.\n\n"
            "Vanguard Advisory Partners\n\n"
            "[DRAFT — awaiting merchant approval before delivery]"
        ),
        "ai_generated": True,
        "approved_by": None,
        "created_at": (now - timedelta(days=1)).isoformat(),
        "updated_at": (now - timedelta(days=1)).isoformat(),
    }
    await db.reminders.replace_one({"id": "rem_002"}, reminder, upsert=True)
    print("  ✓ Reminder: rem_002 for INV-2026-0002 [pending_approval]")

    # ------------------------------------------------------------------ #
    # 6. TRANSACTION RECORD for paid invoice                             #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo transaction record (FICTIONAL)...")
    transaction = {
        "_demo": True,
        "_demo_note": "FICTIONAL — simulated PayPal Sandbox capture. No real funds transferred.",
        "id": "txn_001",
        "invoice_id": "inv_001_settled",
        "user_id": DEMO_USER_ID,
        "amount": "4350.00",
        "currency": "USD",
        "status": "completed",
        "gateway": "paypal_sandbox",
        "gateway_transaction_id": "PAYID-DEMO-SANDBOX-TXNREF-001",
        "created_at": (now - timedelta(days=15)).isoformat(),
    }
    await db.transactions.replace_one({"id": "txn_001"}, transaction, upsert=True)
    print("  ✓ Transaction: txn_001 [$4,350.00 settled — SANDBOX ONLY]")

    # ------------------------------------------------------------------ #
    # 7. AUDIT LOG entries                                               #
    # ------------------------------------------------------------------ #
    print("\n[SEED] Inserting demo audit log (FICTIONAL)...")
    audit_entries = [
        {
            "_demo": True, "id": "aud_001",
            "user_id": DEMO_USER_ID, "actor_type": "user",
            "action": "invoice_created", "resource_type": "invoice",
            "resource_id": "inv_001_settled", "result": "success",
            "correlation_id": "demo-corr-001",
            "created_at": (now - timedelta(days=28)).isoformat(),
        },
        {
            "_demo": True, "id": "aud_002",
            "user_id": DEMO_USER_ID, "actor_type": "user",
            "action": "invoice_approved", "resource_type": "invoice",
            "resource_id": "inv_001_settled", "result": "success",
            "correlation_id": "demo-corr-002",
            "created_at": (now - timedelta(days=27)).isoformat(),
        },
        {
            "_demo": True, "id": "aud_003",
            "user_id": DEMO_USER_ID, "actor_type": "system",
            "action": "paypal_invoice_created", "resource_type": "invoice",
            "resource_id": "inv_001_settled", "result": "success",
            "correlation_id": "demo-corr-003",
            "metadata": {"paypal_invoice_id": "INV2-XXXX-DEMO-0001-SANDBOX"},
            "created_at": (now - timedelta(days=27)).isoformat(),
        },
        {
            "_demo": True, "id": "aud_004",
            "user_id": DEMO_USER_ID, "actor_type": "paypal_webhook",
            "action": "webhook_payment_received", "resource_type": "invoice",
            "resource_id": "inv_001_settled", "result": "success",
            "correlation_id": "demo-corr-004",
            "metadata": {
                "event_type": "INVOICING.INVOICE.PAID",
                "event_id": "DEMO-WH-EVENT-001-SANDBOX",
                "note": "SANDBOX webhook event — no real funds transferred",
            },
            "created_at": (now - timedelta(days=15)).isoformat(),
        },
        {
            "_demo": True, "id": "aud_005",
            "user_id": DEMO_USER_ID, "actor_type": "system",
            "action": "reminder_scheduled", "resource_type": "reminder",
            "resource_id": "rem_002", "result": "success",
            "correlation_id": "demo-corr-005",
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "_demo": True, "id": "aud_006",
            "user_id": DEMO_USER_ID, "actor_type": "user",
            "action": "invoice_created", "resource_type": "invoice",
            "resource_id": "inv_003_pending_approval", "result": "success",
            "correlation_id": "demo-corr-006",
            "metadata": {"extraction_method": "ai_natural_language"},
            "created_at": now.isoformat(),
        },
    ]
    for aud in audit_entries:
        await db.audit_logs.replace_one({"id": aud["id"]}, aud, upsert=True)
    print(f"  ✓ {len(audit_entries)} audit log entries inserted.")

    # ------------------------------------------------------------------ #
    # Summary                                                             #
    # ------------------------------------------------------------------ #
    print(f"""
╔══════════════════════════════════════════════════════════════════════════╗
║  SEED COMPLETE — PAYFLOW AI DEMO DATABASE                                ║
╠══════════════════════════════════════════════════════════════════════════╣
║  Database : {MONGODB_DB_NAME:<61}║
║  Demo URL : http://localhost:5173  (or your frontend URL)               ║
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
    db = client[MONGODB_DB_NAME]

    await drop_existing_demo_data(db)
    await seed(db)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())

