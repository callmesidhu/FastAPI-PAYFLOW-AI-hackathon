"""Standalone Database Seeding Script for PAYFLOW AI Demo & Screenshot Captures.

Seeds realistic, professional fintech accounts receivable data for:
  User: S Sidharth (XYPHX)
  User ID: ec3f64d0-ceeb-4fa4-8a5d-fd3fa8dcd663
  Email: callmesidhu.x@outlook.com

Populates:
  - 6 Realistic Enterprise / Studio Customers
  - 9 Itemized Invoices (Paid, Sent, Overdue, Pending Approval, Draft)
  - 3 Historical Months of Settlements (enabling Collections Velocity Trend chart)
  - 3 Human-in-the-Loop Approvals (including pending items ready for UI demonstration)
  - 3 Contextual Payment Reminders (draft, ready for approval, sent via Zapier)
  - 3 Authoritative Settlement Transactions with PayPal capture references & fees
  - 14 Append-Only Audit Log entries for invoice detail timelines

Usage:
  cd backend
  python seed_demo_data.py
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import uuid

from bson import Decimal128
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings
from app.db.mongodb import get_codec_options

TARGET_USER_ID = "ec3f64d0-ceeb-4fa4-8a5d-fd3fa8dcd663"
TARGET_USER_EMAIL = "callmesidhu.x@outlook.com"
TARGET_BUSINESS_NAME = "XYPHX"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_payload_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def seed():
    settings = get_settings()
    print("=" * 70)
    print("  PAYFLOW AI — Production Demo Data Seeder")
    print("=" * 70)
    print(f"Target Database : {settings.MONGODB_DATABASE}")
    print(f"Target User ID  : {TARGET_USER_ID}")
    print(f"Target Business : {TARGET_BUSINESS_NAME} ({TARGET_USER_EMAIL})")
    print("-" * 70)

    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client.get_database(settings.MONGODB_DATABASE, codec_options=get_codec_options())

    # 1. Clean existing records for this user (idempotent re-runs)
    print("Cleaning any prior demo records for target user...")
    await db.customers.delete_many({"user_id": TARGET_USER_ID})
    await db.invoices.delete_many({"user_id": TARGET_USER_ID})
    await db.approvals.delete_many({"user_id": TARGET_USER_ID})
    await db.reminders.delete_many({"user_id": TARGET_USER_ID})
    await db.transactions.delete_many({"user_id": TARGET_USER_ID})
    await db.audit_logs.delete_many({"user_id": TARGET_USER_ID})

    # 2. Customers
    print("Seeding 6 realistic enterprise & studio clients...")
    customers = [
        {
            "id": "c1111111-2222-3333-4444-555555555501",
            "user_id": TARGET_USER_ID,
            "name": "Elena Rostova",
            "email": "elena@apexdigital.io",
            "company": "Apex Digital Studio",
            "billing_address": {
                "address_line_1": "450 Mission Street, Suite 800",
                "city": "San Francisco",
                "state": "CA",
                "postal_code": "94105",
                "country_code": "US",
            },
            "notes": "Key tier-1 client for brand strategy and UI design system architecture.",
            "created_at": utc_now() - timedelta(days=90),
            "updated_at": utc_now() - timedelta(days=90),
            "is_active": True,
        },
        {
            "id": "c1111111-2222-3333-4444-555555555502",
            "user_id": TARGET_USER_ID,
            "name": "Marcus Vance",
            "email": "m.vance@hyperionlogistics.com",
            "company": "Hyperion Logistics Group",
            "billing_address": {
                "address_line_1": "1200 S Michigan Ave",
                "city": "Chicago",
                "state": "IL",
                "postal_code": "60605",
                "country_code": "US",
            },
            "notes": "Global supply chain tracking and EDI 214 telemetry integration.",
            "created_at": utc_now() - timedelta(days=75),
            "updated_at": utc_now() - timedelta(days=75),
            "is_active": True,
        },
        {
            "id": "c1111111-2222-3333-4444-555555555503",
            "user_id": TARGET_USER_ID,
            "name": "Claire Beauchamp",
            "email": "claire@vanguardadvisory.com",
            "company": "Vanguard Advisory Partners",
            "billing_address": {
                "address_line_1": "375 Park Avenue, 24th Floor",
                "city": "New York",
                "state": "NY",
                "postal_code": "10152",
                "country_code": "US",
            },
            "notes": "Executive portfolio cashflow intelligence and monthly advisory retainer.",
            "created_at": utc_now() - timedelta(days=60),
            "updated_at": utc_now() - timedelta(days=60),
            "is_active": True,
        },
        {
            "id": "c1111111-2222-3333-4444-555555555504",
            "user_id": TARGET_USER_ID,
            "name": "David Chen",
            "email": "dchen@starlightmedia.com",
            "company": "Starlight Media Works",
            "billing_address": {
                "address_line_1": "6801 Hollywood Blvd",
                "city": "Los Angeles",
                "state": "CA",
                "postal_code": "90028",
                "country_code": "US",
            },
            "notes": "High-throughput cloud video rendering pipeline and creative automation.",
            "created_at": utc_now() - timedelta(days=45),
            "updated_at": utc_now() - timedelta(days=45),
            "is_active": True,
        },
        {
            "id": "c1111111-2222-3333-4444-555555555505",
            "user_id": TARGET_USER_ID,
            "name": "Dr. Aris Thorne",
            "email": "procurement@quantumlabs.ai",
            "company": "Quantum AI Labs",
            "billing_address": {
                "address_line_1": "500 W 2nd St, Suite 1900",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "country_code": "US",
            },
            "notes": "Generative agent tool-calling architecture and latency optimization contract.",
            "created_at": utc_now() - timedelta(days=30),
            "updated_at": utc_now() - timedelta(days=30),
            "is_active": True,
        },
        {
            "id": "c1111111-2222-3333-4444-555555555506",
            "user_id": TARGET_USER_ID,
            "name": "Freja Lindqvist",
            "email": "freja@nordicenergy.se",
            "company": "Nordic Clean Energy",
            "billing_address": {
                "address_line_1": "Hamngatan 15",
                "city": "Stockholm",
                "state": "Stockholm",
                "postal_code": "111 47",
                "country_code": "SE",
            },
            "notes": "Renewable energy smart grid distribution dashboard.",
            "created_at": utc_now() - timedelta(days=20),
            "updated_at": utc_now() - timedelta(days=20),
            "is_active": True,
        },
    ]
    await db.customers.insert_many(customers)

    # 3. Invoices
    print("Seeding 9 itemized invoices across all lifecycle states...")
    now = utc_now()
    today = now.date()

    invoices = [
        # Invoice 1: PAID (September 2026) -> Establishes Month 1 for Velocity Trend
        {
            "internal_id": "inv-001-sep-apex-paid",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555501",
            "invoice_number": "INV-2026-0001",
            "items": [
                {
                    "name": "Quiet-Luxury Design System & Token Architecture",
                    "description": "Foundational typography, spacing variables, and high-contrast palette contract",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("2400.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("2400.00"),
                },
                {
                    "name": "Frontend Component Prototype Sprints",
                    "description": "5 interactive wireframes and design review sessions",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("800.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("800.00"),
                },
            ],
            "subtotal": Decimal("3200.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("3200.00"),
            "currency": "USD",
            "issue_date": "2026-09-01",
            "due_date": "2026-09-15",
            "status": "paid",
            "paypal_invoice_id": "INV2-APEX-9011-8842",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-APEX-9011-8842",
            "sent_at": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            "paid_at": datetime(2026, 9, 14, 15, 22, tzinfo=timezone.utc),
            "created_at": datetime(2026, 9, 1, 9, 30, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 9, 14, 15, 22, tzinfo=timezone.utc),
            "notes": "Settled promptly via PayPal Sandbox checkout.",
        },
        # Invoice 2: PAID (October 2026) -> Establishes Month 2 for Velocity Trend
        {
            "internal_id": "inv-002-oct-hyperion-paid",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555502",
            "invoice_number": "INV-2026-0002",
            "items": [
                {
                    "name": "Real-Time Fleet Telemetry Microservices",
                    "description": "FastAPI async broker for GPS pings and container status aggregation",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("4800.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("4800.00"),
                }
            ],
            "subtotal": Decimal("4800.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("4800.00"),
            "currency": "USD",
            "issue_date": "2026-10-01",
            "due_date": "2026-10-15",
            "status": "paid",
            "paypal_invoice_id": "INV2-HYPR-1024-9913",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-HYPR-1024-9913",
            "sent_at": datetime(2026, 10, 1, 11, 15, tzinfo=timezone.utc),
            "paid_at": datetime(2026, 10, 12, 11, 45, tzinfo=timezone.utc),
            "created_at": datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 10, 12, 11, 45, tzinfo=timezone.utc),
            "notes": "Verified through automated PayPal webhook reconciliation.",
        },
        # Invoice 3: PAID (November 2026) -> Establishes Month 3 (Current Month Collections)
        {
            "internal_id": "inv-003-nov-vanguard-paid",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555503",
            "invoice_number": "INV-2026-0003",
            "items": [
                {
                    "name": "Executive Cashflow Models & Predictive Receivables",
                    "description": "Monte Carlo aging simulator and liquidity projection dashboard",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("5500.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("5500.00"),
                }
            ],
            "subtotal": Decimal("5500.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("5500.00"),
            "currency": "USD",
            "issue_date": "2026-10-20",
            "due_date": "2026-11-03",
            "status": "paid",
            "paypal_invoice_id": "INV2-VANG-1102-4421",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-VANG-1102-4421",
            "sent_at": datetime(2026, 10, 20, 14, 0, tzinfo=timezone.utc),
            "paid_at": datetime(2026, 11, 2, 16, 10, tzinfo=timezone.utc),
            "created_at": datetime(2026, 10, 20, 13, 0, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 11, 2, 16, 10, tzinfo=timezone.utc),
            "notes": "Reconciled with PayPal RSASSA-PKCS1 webhook signature.",
        },
        # Invoice 4: SENT / OPEN (Due in 8 days)
        {
            "internal_id": "inv-004-nov-starlight-sent",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555504",
            "invoice_number": "INV-2026-0004",
            "items": [
                {
                    "name": "Automated Cloud Transcoding Cluster",
                    "description": "Kubernetes worker autoscaling for 4K video transcoding",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("2750.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("2750.00"),
                }
            ],
            "subtotal": Decimal("2750.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("2750.00"),
            "currency": "USD",
            "issue_date": str(today - timedelta(days=6)),
            "due_date": str(today + timedelta(days=8)),
            "status": "sent",
            "paypal_invoice_id": "INV2-STAR-1105-3312",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-STAR-1105-3312",
            "sent_at": now - timedelta(days=6),
            "created_at": now - timedelta(days=7),
            "updated_at": now - timedelta(days=6),
            "notes": "Delivered to customer inbox via official PayPal Invoicing v2 dispatch.",
        },
        # Invoice 5: SENT / OPEN (Due in 11 days)
        {
            "internal_id": "inv-005-nov-quantum-sent",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555505",
            "invoice_number": "INV-2026-0005",
            "items": [
                {
                    "name": "Agentic Tool Calling & Injection Firewall Harness",
                    "description": "Multi-agent evaluation harness with 5-tool security boundary",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("3600.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("3600.00"),
                }
            ],
            "subtotal": Decimal("3600.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("3600.00"),
            "currency": "USD",
            "issue_date": str(today - timedelta(days=3)),
            "due_date": str(today + timedelta(days=11)),
            "status": "sent",
            "paypal_invoice_id": "INV2-QNTM-1108-7744",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-QNTM-1108-7744",
            "sent_at": now - timedelta(days=3),
            "created_at": now - timedelta(days=4),
            "updated_at": now - timedelta(days=3),
            "notes": "Active outstanding receivable.",
        },
        # Invoice 6: OVERDUE (7 days overdue) -> Triggers Attention Required & Reminders
        {
            "internal_id": "inv-006-nov-apex-overdue",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555501",
            "invoice_number": "INV-2026-0006",
            "items": [
                {
                    "name": "Design Token Migration & Production Accessibility QA",
                    "description": "WCAG 2.1 AA audit and automated regression suite",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("1950.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("1950.00"),
                }
            ],
            "subtotal": Decimal("1950.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("1950.00"),
            "currency": "USD",
            "issue_date": str(today - timedelta(days=21)),
            "due_date": str(today - timedelta(days=7)),
            "status": "overdue",
            "paypal_invoice_id": "INV2-APEX-1021-5582",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-APEX-1021-5582",
            "sent_at": now - timedelta(days=21),
            "created_at": now - timedelta(days=22),
            "updated_at": now - timedelta(days=7),
            "notes": "Stage 2 follow-up reminder prepared in Approval Center.",
        },
        # Invoice 7: OVERDUE (14 days overdue) -> Populates aging ledger in Analytics
        {
            "internal_id": "inv-007-nov-hyperion-overdue",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555502",
            "invoice_number": "INV-2026-0007",
            "items": [
                {
                    "name": "EDI 214 Shipment Status Webhook Infrastructure",
                    "description": "High-throughput webhook dispatch with HMAC verification",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("4200.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("4200.00"),
                }
            ],
            "subtotal": Decimal("4200.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("4200.00"),
            "currency": "USD",
            "issue_date": str(today - timedelta(days=28)),
            "due_date": str(today - timedelta(days=14)),
            "status": "overdue",
            "paypal_invoice_id": "INV2-HYPR-1014-6631",
            "paypal_invoice_url": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-HYPR-1014-6631",
            "sent_at": now - timedelta(days=28),
            "created_at": now - timedelta(days=29),
            "updated_at": now - timedelta(days=14),
            "notes": "Awaiting finance department approval round.",
        },
        # Invoice 8: PENDING_APPROVAL -> Populates Approval Center with pending action
        {
            "internal_id": "inv-008-nov-vanguard-pending",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555503",
            "invoice_number": "INV-2026-0008",
            "items": [
                {
                    "name": "Q4 Enterprise Accounts Receivable Architecture Retainer",
                    "description": "End-to-end integration architecture and PayPal Invoicing sandbox validation",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("6800.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("6800.00"),
                }
            ],
            "subtotal": Decimal("6800.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("6800.00"),
            "currency": "USD",
            "issue_date": str(today - timedelta(days=1)),
            "due_date": str(today + timedelta(days=13)),
            "status": "pending_approval",
            "created_at": now - timedelta(hours=18),
            "updated_at": now - timedelta(hours=18),
            "notes": "Submitted for human approval before PayPal Sandbox creation.",
        },
        # Invoice 9: DRAFT -> Shows Draft state in Invoices directory
        {
            "internal_id": "inv-009-nov-nordic-draft",
            "user_id": TARGET_USER_ID,
            "customer_id": "c1111111-2222-3333-4444-555555555506",
            "invoice_number": "INV-2026-0009",
            "items": [
                {
                    "name": "Microgrid Energy Analytics Sprint 1",
                    "description": "Smart meter time-series data aggregation and billing schema definition",
                    "quantity": Decimal("1.00"),
                    "unit_price": Decimal("1400.00"),
                    "tax": Decimal("0.00"),
                    "total": Decimal("1400.00"),
                }
            ],
            "subtotal": Decimal("1400.00"),
            "tax": Decimal("0.00"),
            "total": Decimal("1400.00"),
            "currency": "USD",
            "issue_date": str(today),
            "due_date": str(today + timedelta(days=14)),
            "status": "draft",
            "created_at": now - timedelta(hours=4),
            "updated_at": now - timedelta(hours=4),
            "notes": "Draft prepared via natural language prompt in AI Assistant.",
        },
    ]
    await db.invoices.insert_many(invoices)

    # 4. Approvals (Human-in-the-Loop)
    print("Seeding Approval Center records (pending & historical)...")
    inv_008_snapshot = {
        "invoice_id": "inv-008-nov-vanguard-pending",
        "invoice_number": "INV-2026-0008",
        "customer_id": "c1111111-2222-3333-4444-555555555503",
        "amount": "6800.00",
        "currency": "USD",
        "due_date": str(today + timedelta(days=13)),
    }
    rem_001_snapshot = {
        "invoice_id": "inv-006-nov-apex-overdue",
        "invoice_number": "INV-2026-0006",
        "customer_name": "Elena Rostova",
        "customer_email": "elena@apexdigital.io",
        "stage": "overdue_1_3",
        "channel": "zapier",
    }

    approvals = [
        {
            "id": "appr-001-pending-inv-008",
            "user_id": TARGET_USER_ID,
            "action_type": "create_paypal_invoice",
            "resource_type": "invoice",
            "resource_id": "inv-008-nov-vanguard-pending",
            "payload_snapshot": inv_008_snapshot,
            "payload_hash": compute_payload_hash(inv_008_snapshot),
            "status": "pending",
            "created_at": now - timedelta(hours=18),
        },
        {
            "id": "appr-002-pending-rem-006",
            "user_id": TARGET_USER_ID,
            "action_type": "send_payment_reminder",
            "resource_type": "reminder",
            "resource_id": "rem-001-apex-overdue",
            "payload_snapshot": rem_001_snapshot,
            "payload_hash": compute_payload_hash(rem_001_snapshot),
            "status": "pending",
            "created_at": now - timedelta(hours=8),
        },
        {
            "id": "appr-003-approved-inv-003",
            "user_id": TARGET_USER_ID,
            "action_type": "send_paypal_invoice",
            "resource_type": "invoice",
            "resource_id": "inv-003-nov-vanguard-paid",
            "payload_snapshot": {
                "invoice_id": "inv-003-nov-vanguard-paid",
                "invoice_number": "INV-2026-0003",
                "amount": "5500.00",
                "currency": "USD",
            },
            "payload_hash": compute_payload_hash({"invoice_id": "inv-003-nov-vanguard-paid", "amount": "5500.00"}),
            "status": "approved",
            "created_at": datetime(2026, 10, 20, 13, 30, tzinfo=timezone.utc),
            "approved_at": datetime(2026, 10, 20, 13, 55, tzinfo=timezone.utc),
            "execution_result_ref": "INV2-VANG-1102-4421",
        },
    ]
    await db.approvals.insert_many(approvals)

    # 5. Reminders
    print("Seeding Contextual Payment Reminders...")
    reminders = [
        {
            "id": "rem-001-apex-overdue",
            "user_id": TARGET_USER_ID,
            "invoice_id": "inv-006-nov-apex-overdue",
            "invoice_number": "INV-2026-0006",
            "customer_id": "c1111111-2222-3333-4444-555555555501",
            "customer_name": "Elena Rostova",
            "customer_email": "elena@apexdigital.io",
            "stage": "overdue_1_3",
            "status": "ready_for_approval",
            "subject": "PAYFLOW AI // Friendly Reminder: Invoice INV-2026-0006 for Apex Digital Studio",
            "message_body": (
                "Hi Elena,\n\n"
                "We hope all is well at Apex Digital Studio. This is a gentle follow-up regarding invoice INV-2026-0006 "
                "for $1,950.00 USD (Design Token Migration & Production Accessibility QA), which was due on November 4, 2026.\n\n"
                "You can review and settle this invoice directly via the secure PayPal link below.\n\n"
                "Thank you for your partnership,\nXYPHX Accounts Receivable"
            ),
            "payment_link": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-APEX-1021-5582",
            "channel": "zapier",
            "approval_id": "appr-002-pending-rem-006",
            "created_at": now - timedelta(hours=8),
            "updated_at": now - timedelta(hours=8),
        },
        {
            "id": "rem-002-hyperion-sent",
            "user_id": TARGET_USER_ID,
            "invoice_id": "inv-007-nov-hyperion-overdue",
            "invoice_number": "INV-2026-0007",
            "customer_id": "c1111111-2222-3333-4444-555555555502",
            "customer_name": "Marcus Vance",
            "customer_email": "m.vance@hyperionlogistics.com",
            "stage": "overdue_8_14",
            "status": "sent",
            "subject": "PAYFLOW AI // Outstanding Invoice Notice: INV-2026-0007 for Hyperion Logistics",
            "message_body": (
                "Dear Marcus,\n\n"
                "Our records indicate invoice INV-2026-0007 for $4,200.00 USD is currently 14 days overdue. "
                "Please verify settlement or reach out if there are any purchase order adjustments required.\n\n"
                "Warm regards,\nXYPHX Billing Team"
            ),
            "payment_link": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-HYPR-1014-6631",
            "channel": "zapier",
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(days=2),
            "approved_at": now - timedelta(days=2),
            "sent_at": now - timedelta(days=2),
        },
        {
            "id": "rem-003-starlight-draft",
            "user_id": TARGET_USER_ID,
            "invoice_id": "inv-004-nov-starlight-sent",
            "invoice_number": "INV-2026-0004",
            "customer_id": "c1111111-2222-3333-4444-555555555504",
            "customer_name": "David Chen",
            "customer_email": "dchen@starlightmedia.com",
            "stage": "upcoming",
            "status": "draft",
            "subject": "Upcoming Invoice Reminder: INV-2026-0004 ($2,750.00 USD)",
            "message_body": (
                "Hi David,\n\n"
                "Just a courteous heads-up that invoice INV-2026-0004 for Starlight Media Works will be due in 8 days.\n\n"
                "Best,\nXYPHX"
            ),
            "payment_link": "https://www.sandbox.paypal.com/invoice/s/pay/INV2-STAR-1105-3312",
            "channel": "manual",
            "created_at": now - timedelta(hours=2),
            "updated_at": now - timedelta(hours=2),
        },
    ]
    await db.reminders.insert_many(reminders)

    # 6. Transactions (Settlement Ledger)
    print("Seeding Settlement Ledger transactions...")
    transactions = [
        {
            "id": "tx-001-sep-apex",
            "user_id": TARGET_USER_ID,
            "invoice_id": "inv-001-sep-apex-paid",
            "invoice_number": "INV-2026-0001",
            "customer_id": "c1111111-2222-3333-4444-555555555501",
            "paypal_capture_id": "CAPTURE-9011-8842-SETTLED",
            "amount": Decimal("3200.00"),
            "fee_amount": Decimal("93.10"),  # 2.9% + $0.30
            "net_amount": Decimal("3106.90"),
            "currency": "USD",
            "status": "completed",
            "payer_email": "elena@apexdigital.io",
            "created_at": datetime(2026, 9, 14, 15, 22, tzinfo=timezone.utc),
        },
        {
            "id": "tx-002-oct-hyperion",
            "user_id": TARGET_USER_ID,
            "invoice_id": "inv-002-oct-hyperion-paid",
            "invoice_number": "INV-2026-0002",
            "customer_id": "c1111111-2222-3333-4444-555555555502",
            "paypal_capture_id": "CAPTURE-1024-9913-SETTLED",
            "amount": Decimal("4800.00"),
            "fee_amount": Decimal("139.50"),  # 2.9% + $0.30
            "net_amount": Decimal("4660.50"),
            "currency": "USD",
            "status": "completed",
            "payer_email": "m.vance@hyperionlogistics.com",
            "created_at": datetime(2026, 10, 12, 11, 45, tzinfo=timezone.utc),
        },
        {
            "id": "tx-003-nov-vanguard",
            "user_id": TARGET_USER_ID,
            "invoice_id": "inv-003-nov-vanguard-paid",
            "invoice_number": "INV-2026-0003",
            "customer_id": "c1111111-2222-3333-4444-555555555503",
            "paypal_capture_id": "CAPTURE-1102-4421-SETTLED",
            "amount": Decimal("5500.00"),
            "fee_amount": Decimal("159.80"),  # 2.9% + $0.30
            "net_amount": Decimal("5340.20"),
            "currency": "USD",
            "status": "completed",
            "payer_email": "claire@vanguardadvisory.com",
            "created_at": datetime(2026, 11, 2, 16, 10, tzinfo=timezone.utc),
        },
    ]
    await db.transactions.insert_many(transactions)

    # 7. Audit Logs
    print("Seeding Audit Trail records...")
    audit_logs = [
        {
            "id": str(uuid.uuid4()),
            "user_id": TARGET_USER_ID,
            "actor": "user",
            "action": "invoice.created",
            "resource_type": "invoice",
            "resource_id": "inv-008-nov-vanguard-pending",
            "result": "success",
            "correlation_id": str(uuid.uuid4()),
            "metadata": {"invoice_number": "INV-2026-0008", "amount": "6800.00", "currency": "USD"},
            "created_at": now - timedelta(hours=18),
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": TARGET_USER_ID,
            "actor": "user",
            "action": "invoice.submitted_approval",
            "resource_type": "approval",
            "resource_id": "appr-001-pending-inv-008",
            "result": "success",
            "correlation_id": str(uuid.uuid4()),
            "metadata": {"invoice_number": "INV-2026-0008", "status": "pending_approval"},
            "created_at": now - timedelta(hours=18),
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": TARGET_USER_ID,
            "actor": "user",
            "action": "invoice.created",
            "resource_type": "invoice",
            "resource_id": "inv-006-nov-apex-overdue",
            "result": "success",
            "correlation_id": str(uuid.uuid4()),
            "metadata": {"invoice_number": "INV-2026-0006", "amount": "1950.00"},
            "created_at": now - timedelta(days=22),
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": TARGET_USER_ID,
            "actor": "user",
            "action": "invoice.sent",
            "resource_type": "invoice",
            "resource_id": "inv-006-nov-apex-overdue",
            "result": "success",
            "correlation_id": str(uuid.uuid4()),
            "metadata": {"paypal_invoice_id": "INV2-APEX-1021-5582"},
            "created_at": now - timedelta(days=21),
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": TARGET_USER_ID,
            "actor": "ai_assistant",
            "action": "reminder.scheduled",
            "resource_type": "reminder",
            "resource_id": "rem-001-apex-overdue",
            "result": "success",
            "correlation_id": str(uuid.uuid4()),
            "metadata": {"stage": "overdue_1_3", "customer": "Apex Digital Studio"},
            "created_at": now - timedelta(hours=8),
        },
        {
            "id": str(uuid.uuid4()),
            "user_id": TARGET_USER_ID,
            "actor": "paypal_webhook",
            "action": "invoice.paid",
            "resource_type": "invoice",
            "resource_id": "inv-003-nov-vanguard-paid",
            "result": "success",
            "correlation_id": str(uuid.uuid4()),
            "metadata": {"gross_amount": "5500.00", "currency": "USD", "signature_verified": True},
            "created_at": datetime(2026, 11, 2, 16, 10, tzinfo=timezone.utc),
        },
    ]
    await db.audit_logs.insert_many(audit_logs)

    client.close()
    print("-" * 70)
    print("SUCCESS! Demo dataset seeded successfully:")
    print(f"  • {len(customers)} Customers created")
    print(f"  • {len(invoices)} Invoices created (3 Paid, 2 Sent, 2 Overdue, 1 Pending Approval, 1 Draft)")
    print(f"  • {len(approvals)} Approvals created (2 Pending in Approval Center)")
    print(f"  • {len(reminders)} Follow-up Reminders created")
    print(f"  • {len(transactions)} Historical Transactions created (Sep, Oct, Nov)")
    print(f"  • {len(audit_logs)} Audit Log entries created")
    print("-" * 70)
    print("Expected UI state for screenshots:")
    print("  ✓ Dashboard: Outstanding = $19,300.00 | Overdue = $6,150.00 | Collected Nov = $5,500.00")
    print("  ✓ Collections Velocity Trend: ACTIVE 3-Month Bar Chart (Sep: $3.2k, Oct: $4.8k, Nov: $5.5k)")
    print("  ✓ Invoices View: 9 rows with AG Grid sorting, filters, and quiet-luxury status badges")
    print("  ✓ Bryntum Calendar (/calendar): Real Month/Week timeline populated with due dates & follow-ups")
    print("  ✓ Approval Center: 2 pending authorization cards awaiting merchant click")
    print("  ✓ Analytics: Rich AG Grid customer ledger & 5 aging schedule buckets")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(seed())
