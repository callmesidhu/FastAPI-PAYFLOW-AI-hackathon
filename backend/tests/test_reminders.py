"""Tests for Prompts 21 & 22: Payment reminder policy, deterministic stages,
respectful message drafting, idempotency, unconfigured channel safety,
human approval gating, and background scheduler.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from httpx import ASGITransport, AsyncClient
import respx

from app.core.config import get_settings
from app.core.security import create_access_token
from app.db.mongodb import get_db
from app.jobs.reminder_job import run_reminder_evaluation_cycle
from app.main import app
from app.models.customer import Customer
from app.models.enums import InvoiceStatus, ReminderStage, ReminderStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem
from app.models.user import User
from app.schemas.reminder import ReminderUpdate
from app.services.reminder_service import (
    ReminderService,
    determine_reminder_stage,
    generate_respectful_reminder_content,
)
from tests.mock_db import MockDatabase


@pytest.fixture
def mock_db() -> MockDatabase:
    return MockDatabase()


@pytest.fixture
def test_user() -> User:
    return User(
        id="usr-rem-1",
        email="merchant.rem@example.com",
        hashed_password="hashed_pw_test",
        name="Merchant One",
    )


@pytest.fixture
def other_user() -> User:
    return User(
        id="usr-rem-2",
        email="other.rem@example.com",
        hashed_password="hashed_pw_test",
        name="Merchant Two",
    )


@pytest.fixture
def customer_acme(test_user: User) -> Customer:
    return Customer(
        id="cust-rem-acme",
        user_id=test_user.id,
        name="Acme Corp",
        email="billing@acmecorp.com",
        company="Acme Corporation",
    )


def test_deterministic_stage_calculation():
    """Verify that reminder stages are computed deterministically from due dates."""
    today = date(2026, 11, 10)

    # 1 day before due date -> UPCOMING
    assert determine_reminder_stage(due_date=date(2026, 11, 11), today=today) == ReminderStage.UPCOMING

    # Due date is today -> DUE_TODAY
    assert determine_reminder_stage(due_date=date(2026, 11, 10), today=today) == ReminderStage.DUE_TODAY

    # 1-3 days overdue -> OVERDUE_1_3
    assert determine_reminder_stage(due_date=date(2026, 11, 9), today=today) == ReminderStage.OVERDUE_1_3
    assert determine_reminder_stage(due_date=date(2026, 11, 7), today=today) == ReminderStage.OVERDUE_1_3

    # 4-7 days overdue -> OVERDUE_4_7
    assert determine_reminder_stage(due_date=date(2026, 11, 5), today=today) == ReminderStage.OVERDUE_4_7
    assert determine_reminder_stage(due_date=date(2026, 11, 3), today=today) == ReminderStage.OVERDUE_4_7

    # 8-14 days overdue -> OVERDUE_8_14
    assert determine_reminder_stage(due_date=date(2026, 11, 2), today=today) == ReminderStage.OVERDUE_8_14
    assert determine_reminder_stage(due_date=date(2026, 10, 27), today=today) == ReminderStage.OVERDUE_8_14

    # 15+ days overdue -> OVERDUE_15_PLUS
    assert determine_reminder_stage(due_date=date(2026, 10, 26), today=today) == ReminderStage.OVERDUE_15_PLUS
    assert determine_reminder_stage(due_date=date(2026, 9, 1), today=today) == ReminderStage.OVERDUE_15_PLUS

    # Too early (e.g. 5 days in the future) -> None
    assert determine_reminder_stage(due_date=date(2026, 11, 15), today=today) is None


def test_guardrails_no_threats_or_shaming_in_messages():
    """Verify generated messages across all stages contain only respectful, non-threatening language."""
    due = date(2026, 11, 10)
    stages = [
        ReminderStage.UPCOMING,
        ReminderStage.DUE_TODAY,
        ReminderStage.OVERDUE_1_3,
        ReminderStage.OVERDUE_4_7,
        ReminderStage.OVERDUE_8_14,
        ReminderStage.OVERDUE_15_PLUS,
    ]

    import re

    forbidden_phrases = ["court", "lawyer", "legal action", "sue", "penalty", "shame", "consequences", "police"]

    for stage in stages:
        subject, body = generate_respectful_reminder_content(
            stage=stage,
            customer_name="Acme Corp",
            invoice_number="INV-2026-0001",
            total=Decimal("1500.00"),
            currency="USD",
            due_date=due,
            paypal_invoice_url="https://www.sandbox.paypal.com/invoice/p/#12345",
            days_overdue=10,
        )

        full_text = f"{subject} {body}".lower()
        for phrase in forbidden_phrases:
            assert not re.search(rf"\b{re.escape(phrase)}\b", full_text), f"Forbidden phrase '{phrase}' found in stage {stage} message!"

        # Invariant: Must contain invoice number and amount
        assert "INV-2026-0001" in f"{subject} {body}"
        assert "1500.00" in full_text
        assert "usd" in full_text
        # Invariant: Must contain verified payment link
        assert "https://www.sandbox.paypal.com/invoice/p/#12345" in body


def test_payment_link_omitted_if_not_available():
    """When an invoice does not have a verified PayPal invoice URL, no payment link is hallucinated."""
    subject, body = generate_respectful_reminder_content(
        stage=ReminderStage.DUE_TODAY,
        customer_name="Acme Corp",
        invoice_number="INV-2026-0002",
        total=Decimal("400.00"),
        currency="USD",
        due_date=date.today(),
        paypal_invoice_url=None,  # No PayPal link available
    )

    assert "http://" not in body
    assert "https://" not in body
    assert "referencing invoice number INV-2026-0002" in body


@pytest.mark.asyncio
async def test_policy_exclusions_and_idempotency(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """Paid, cancelled, or draft invoices are excluded. Duplicate reminders for same stage are prevented."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()

    # 1. Paid invoice -> MUST BE EXCLUDED
    inv_paid = Invoice(
        internal_id="inv-paid-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-PAID",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        status=InvoiceStatus.PAID,
        items=[InvoiceItem(name="Paid Work", quantity=Decimal("1"), unit_price=Decimal("500.00"), tax=Decimal("0"))],
    )
    # 2. Cancelled invoice -> MUST BE EXCLUDED
    inv_cancelled = Invoice(
        internal_id="inv-canc-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-CANC",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        status=InvoiceStatus.CANCELLED,
        items=[InvoiceItem(name="Cancelled Work", quantity=Decimal("1"), unit_price=Decimal("500.00"), tax=Decimal("0"))],
    )
    # 3. Draft invoice -> MUST BE EXCLUDED
    inv_draft = Invoice(
        internal_id="inv-draft-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-DRAFT",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        status=InvoiceStatus.DRAFT,
        items=[InvoiceItem(name="Draft Work", quantity=Decimal("1"), unit_price=Decimal("500.00"), tax=Decimal("0"))],
    )
    # 4. Overdue invoice -> QUALIFIES FOR OVERDUE_4_7
    inv_overdue = Invoice(
        internal_id="inv-overdue-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-ACTIVE-OVERDUE",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=5),
        status=InvoiceStatus.OVERDUE,
        items=[InvoiceItem(name="Overdue Work", quantity=Decimal("1"), unit_price=Decimal("1000.00"), tax=Decimal("0"))],
    )

    for inv in [inv_paid, inv_cancelled, inv_draft, inv_overdue]:
        await mock_db.invoices.insert_one(inv.model_dump())

    # First Evaluation Run
    result1 = await ReminderService.evaluate_and_create_reminders(
        db=mock_db,
        user_id=test_user.id,
        reference_date=today,
    )

    # Only 1 reminder should be drafted (for inv_overdue)
    assert result1.drafts_created_count == 1
    assert result1.reminders[0].invoice_number == "INV-ACTIVE-OVERDUE"
    assert result1.reminders[0].stage == ReminderStage.OVERDUE_4_7
    assert result1.reminders[0].status == ReminderStatus.READY_FOR_APPROVAL

    # Second Evaluation Run (Idempotency Check)
    result2 = await ReminderService.evaluate_and_create_reminders(
        db=mock_db,
        user_id=test_user.id,
        reference_date=today,
    )

    # Invariant: 0 duplicates created!
    assert result2.drafts_created_count == 0
    assert result2.skipped_existing_count == 1
    assert len(mock_db.reminders.docs) == 1


@pytest.mark.asyncio
async def test_human_approval_required_before_dispatch(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """A reminder draft cannot be dispatched without explicit human approval."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()
    inv = Invoice(
        internal_id="inv-gate-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-GATE-01",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=5),
        due_date=today,
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Service", quantity=Decimal("1"), unit_price=Decimal("500.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv.model_dump())

    # Create draft
    eval_res = await ReminderService.evaluate_and_create_reminders(
        db=mock_db,
        user_id=test_user.id,
        reference_date=today,
    )
    rem_id = eval_res.reminders[0].id

    # Attempt dispatch without approval -> Must fail!
    with pytest.raises(ValueError) as exc_info:
        await ReminderService.dispatch_reminder(
            db=mock_db,
            user_id=test_user.id,
            reminder_id=rem_id,
        )
    assert "requires human approval" in str(exc_info.value).lower()

    # Now approve reminder
    approved = await ReminderService.approve_reminder(
        db=mock_db,
        user_id=test_user.id,
        reminder_id=rem_id,
    )
    assert approved.status == ReminderStatus.APPROVED
    assert approved.approval_id is not None

    # Now dispatch succeeds
    dispatch_res = await ReminderService.dispatch_reminder(
        db=mock_db,
        user_id=test_user.id,
        reminder_id=rem_id,
    )
    assert dispatch_res.status == ReminderStatus.SENT


@pytest.mark.asyncio
async def test_user_can_edit_reminder_before_approval(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """User can edit the subject and body of a drafted reminder before approving it."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()
    inv = Invoice(
        internal_id="inv-edit-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-EDIT-01",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=5),
        due_date=today,
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Service", quantity=Decimal("1"), unit_price=Decimal("700.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv.model_dump())

    eval_res = await ReminderService.evaluate_and_create_reminders(mock_db, test_user.id, reference_date=today)
    rem_id = eval_res.reminders[0].id

    # Edit reminder
    updated = await ReminderService.update_reminder(
        db=mock_db,
        user_id=test_user.id,
        reminder_id=rem_id,
        payload=ReminderUpdate(
            subject="Custom Subject: Friendly check-in for INV-EDIT-01",
            message_body="Custom message body tailored specifically for Acme Corp.",
        ),
    )

    assert updated.subject == "Custom Subject: Friendly check-in for INV-EDIT-01"
    assert "Custom message body tailored specifically" in updated.message_body


@pytest.mark.asyncio
async def test_unconfigured_channel_labeled_safely(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """When email and Zapier are unconfigured, reminders are labeled as manual/unconfigured."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()
    inv = Invoice(
        internal_id="inv-chan-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-CHAN-01",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=5),
        due_date=today,
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Service", quantity=Decimal("1"), unit_price=Decimal("300.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv.model_dump())

    eval_res = await ReminderService.evaluate_and_create_reminders(mock_db, test_user.id, reference_date=today)
    rem = eval_res.reminders[0]

    # Verify channel info
    assert rem.channel_configured is False
    assert "Manual delivery" in rem.channel_label

    # Approve and dispatch
    await ReminderService.approve_reminder(mock_db, test_user.id, rem.id)
    dispatch = await ReminderService.dispatch_reminder(mock_db, test_user.id, rem.id)

    # Invariant: Dispatched message notes manual handling, never falsely claims email sent
    assert "marked for manual outreach" in dispatch.message
    assert "No transactional email provider" in dispatch.message


@pytest.mark.asyncio
async def test_zapier_channel_dispatch_success_and_failure_retry(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
    monkeypatch,
):
    """Zapier dispatch validates response and sets failed status on errors, allowing retry."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    # Configure Zapier webhook in settings
    zapier_url = "https://hooks.zapier.com/hooks/catch/12345/abcde/"
    monkeypatch.setattr(get_settings(), "ZAPIER_WEBHOOK_URL", zapier_url)

    today = date.today()
    inv = Invoice(
        internal_id="inv-zap-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-ZAP-01",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=5),
        due_date=today,
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Service", quantity=Decimal("1"), unit_price=Decimal("900.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv.model_dump())

    eval_res = await ReminderService.evaluate_and_create_reminders(mock_db, test_user.id, reference_date=today)
    rem_id = eval_res.reminders[0].id
    await ReminderService.approve_reminder(mock_db, test_user.id, rem_id)

    # 1. Simulate failure (e.g. Zapier 500 error)
    with respx.mock:
        respx.post(zapier_url).respond(status_code=500, text="Internal Server Error")
        fail_res = await ReminderService.dispatch_reminder(
            mock_db,
            test_user.id,
            rem_id,
            override_channel="zapier",
        )
        assert fail_res.status == ReminderStatus.FAILED
        assert fail_res.retry_count == 1
        assert "Zapier returned error status 500" in fail_res.delivery_error

    # 2. Simulate retry success
    with respx.mock:
        respx.post(zapier_url).respond(status_code=200, json={"status": "success"})
        retry_res = await ReminderService.retry_failed_reminder(
            mock_db,
            test_user.id,
            rem_id,
        )
        assert retry_res.status == ReminderStatus.SENT
        assert "dispatched via Zapier" in retry_res.message


@pytest.mark.asyncio
async def test_scheduler_evaluation_cycle(
    mock_db: MockDatabase,
    test_user: User,
    other_user: User,
    customer_acme: Customer,
):
    """Background scheduler pass evaluates all active users idempotently."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.users.insert_one(other_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()
    inv1 = Invoice(
        internal_id="inv-sched-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-SCHED-01",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=2),
        due_date=today,
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="Service", quantity=Decimal("1"), unit_price=Decimal("100.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv1.model_dump())

    cycle_result = await run_reminder_evaluation_cycle(mock_db, reference_date=today)
    assert cycle_result["status"] == "completed"
    assert cycle_result["users_evaluated"] == 2
    assert cycle_result["drafts_created"] == 1


@pytest.mark.asyncio
async def test_reminders_http_api_endpoints(
    mock_db: MockDatabase,
    test_user: User,
    customer_acme: Customer,
):
    """Verify HTTP API endpoints for reminder evaluation, listing, approval, and dispatch."""
    await mock_db.users.insert_one(test_user.model_dump())
    await mock_db.customers.insert_one(customer_acme.model_dump())

    today = date.today()
    inv = Invoice(
        internal_id="inv-api-1",
        user_id=test_user.id,
        customer_id=customer_acme.id,
        invoice_number="INV-API-01",
        currency=SupportedCurrency.USD,
        issue_date=today - timedelta(days=3),
        due_date=today,
        status=InvoiceStatus.SENT,
        items=[InvoiceItem(name="API Service", quantity=Decimal("1"), unit_price=Decimal("500.00"), tax=Decimal("0"))],
    )
    await mock_db.invoices.insert_one(inv.model_dump())

    app.dependency_overrides[get_db] = lambda: mock_db
    try:
        token = create_access_token(subject=test_user.id)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            # 1. POST /api/reminders/evaluate
            eval_res = await ac.post("/api/reminders/evaluate", json={})
            assert eval_res.status_code == 200
            eval_data = eval_res.json()
            assert eval_data["drafts_created_count"] == 1
            rem_id = eval_data["reminders"][0]["id"]

            # 2. GET /api/reminders
            list_res = await ac.get("/api/reminders")
            assert list_res.status_code == 200
            list_data = list_res.json()
            assert list_data["total"] == 1
            assert list_data["items"][0]["id"] == rem_id

            # 3. PATCH /api/reminders/{id}
            patch_res = await ac.patch(
                f"/api/reminders/{rem_id}",
                json={"subject": "Updated API Subject"},
            )
            assert patch_res.status_code == 200
            assert patch_res.json()["subject"] == "Updated API Subject"

            # 4. POST /api/reminders/{id}/approve
            appr_res = await ac.post(f"/api/reminders/{rem_id}/approve")
            assert appr_res.status_code == 200
            assert appr_res.json()["status"] == "approved"

            # 5. POST /api/reminders/{id}/dispatch
            disp_res = await ac.post(f"/api/reminders/{rem_id}/dispatch", json={})
            assert disp_res.status_code == 200
            assert disp_res.json()["status"] == "sent"
    finally:
        app.dependency_overrides.clear()
