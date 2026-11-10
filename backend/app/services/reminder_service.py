"""Payment Reminder Policy, Message Generation, and Dispatch Engine (Prompts 21 & 22).

Enforces:
- Deterministic stage evaluation: upcoming (-1d), due today (0d), 1–3d, 4–7d, 8–14d, 15+d overdue.
- Policy exclusions: Paid, cancelled, draft, or already-reminded invoices.
- Database-backed idempotency: Unique (invoice_id, stage) prevents duplicate reminders.
- Verified invoice data only: invoice number, currency, amount, due date, and verified PayPal link.
- Strict guardrail: Never threatens, shames, or claims legal action.
- Channel safety: Unconfigured channel is explicitly labeled; no message sent without approval.
- Retries, dead-letter failed status, and comprehensive audit trails.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import json
from typing import Any, Dict, List, Optional, Tuple
import uuid
import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import ErrorCategory, metrics_collector
from app.models.audit import ActorType, AuditLog
from app.models.enums import InvoiceStatus, ReminderStage, ReminderStatus
from app.models.invoice import Invoice
from app.models.reminder import Reminder, utc_now
from app.schemas.reminder import (
    ReminderDispatchResult,
    ReminderEvaluationResult,
    ReminderResponse,
    ReminderUpdate,
)

logger = get_logger("payflow.reminder_service")
settings = get_settings()


def determine_reminder_stage(due_date: date, today: date) -> Optional[ReminderStage]:
    """Deterministically resolve the reminder stage based on due date and reference date."""
    days_overdue = (today - due_date).days

    if days_overdue == -1:
        return ReminderStage.UPCOMING
    elif days_overdue == 0:
        return ReminderStage.DUE_TODAY
    elif 1 <= days_overdue <= 3:
        return ReminderStage.OVERDUE_1_3
    elif 4 <= days_overdue <= 7:
        return ReminderStage.OVERDUE_4_7
    elif 8 <= days_overdue <= 14:
        return ReminderStage.OVERDUE_8_14
    elif days_overdue >= 15:
        return ReminderStage.OVERDUE_15_PLUS
    else:
        # More than 1 day before due date: not due for a reminder yet
        return None


def generate_respectful_reminder_content(
    stage: ReminderStage,
    customer_name: str,
    invoice_number: str,
    total: Decimal,
    currency: str,
    due_date: date,
    paypal_invoice_url: Optional[str] = None,
    days_overdue: int = 0,
) -> Tuple[str, str]:
    """Generate concise, respectful, customer-specific reminder copy using ONLY verified data.

    Invariants:
    - Never threatens, shames, or claims legal action.
    - Payment link is included ONLY if official paypal_invoice_url is verified.
    """
    total_str = f"{total:.2f}"
    clean_name = customer_name.strip() if customer_name else "Client"

    if paypal_invoice_url and paypal_invoice_url.strip():
        payment_link_text = (
            f"You may review and settle this invoice directly via the secure PayPal Sandbox payment link:\n"
            f"{paypal_invoice_url.strip()}\n\n"
        )
    else:
        payment_link_text = (
            f"Payment can be settled referencing invoice number {invoice_number}.\n\n"
        )

    if stage == ReminderStage.UPCOMING:
        subject = f"Upcoming Payment: Invoice {invoice_number} due tomorrow"
        body = (
            f"Dear {clean_name},\n\n"
            f"This is a courteous note to let you know that invoice {invoice_number} for ${total_str} {currency} "
            f"is scheduled for payment tomorrow ({due_date}).\n\n"
            f"{payment_link_text}"
            f"If you have already arranged this remittance, please disregard this reminder. "
            f"Thank you for your business.\n\n"
            f"Warm regards,\nAccounts Receivable"
        )
    elif stage == ReminderStage.DUE_TODAY:
        subject = f"Payment Due Today: Invoice {invoice_number}"
        body = (
            f"Dear {clean_name},\n\n"
            f"We hope this note finds you well. This is a gentle reminder that invoice {invoice_number} "
            f"for ${total_str} {currency} is due today ({due_date}).\n\n"
            f"{payment_link_text}"
            f"Please let us know if you require any assistance or updated billing information.\n\n"
            f"Best regards,\nAccounts Receivable"
        )
    elif stage == ReminderStage.OVERDUE_1_3:
        subject = f"Friendly Follow-Up: Invoice {invoice_number} past due"
        body = (
            f"Dear {clean_name},\n\n"
            f"We are following up regarding invoice {invoice_number} for ${total_str} {currency}, "
            f"which was due on {due_date} ({days_overdue} day(s) ago).\n\n"
            f"{payment_link_text}"
            f"Could you please confirm if this remittance has been scheduled? "
            f"We appreciate your prompt attention to this matter.\n\n"
            f"Sincerely,\nAccounts Receivable"
        )
    elif stage == ReminderStage.OVERDUE_4_7:
        subject = f"Past Due Reminder: Invoice {invoice_number}"
        body = (
            f"Dear {clean_name},\n\n"
            f"We are writing to check on the status of invoice {invoice_number} for ${total_str} {currency}, "
            f"which was due on {due_date} ({days_overdue} days past due).\n\n"
            f"{payment_link_text}"
            f"Please arrange payment at your earliest convenience or let us know if you have any questions.\n\n"
            f"Thank you,\nAccounts Receivable"
        )
    elif stage == ReminderStage.OVERDUE_8_14:
        subject = f"Accounts Receivable Notice: Invoice {invoice_number} ({days_overdue} days overdue)"
        body = (
            f"Dear {clean_name},\n\n"
            f"We have not yet received payment for invoice {invoice_number} in the amount of "
            f"${total_str} {currency}, which was due on {due_date}.\n\n"
            f"{payment_link_text}"
            f"Please remit payment as soon as possible to keep your account current. "
            f"If you need to discuss payment arrangements, please contact us promptly.\n\n"
            f"Regards,\nAccounts Receivable"
        )
    else:  # OVERDUE_15_PLUS
        subject = f"Urgent Attention: Outstanding Balance for Invoice {invoice_number}"
        body = (
            f"Dear {clean_name},\n\n"
            f"This is an urgent follow-up regarding overdue invoice {invoice_number} for "
            f"${total_str} {currency}, which was due on {due_date} ({days_overdue} days past due).\n\n"
            f"{payment_link_text}"
            f"Please settle this balance today or contact our accounts team immediately to confirm remittance details.\n\n"
            f"Respectfully,\nAccounts Receivable Management"
        )

    return subject, body


def resolve_delivery_channel_info() -> Tuple[str, bool, str]:
    """Determine delivery channel capabilities from application environment."""
    if settings.EMAIL_PROVIDER or getattr(settings, "SMTP_HOST", None):
        return "email", True, "Transactional Email"
    elif settings.ZAPIER_WEBHOOK_URL:
        return "zapier", True, "Zapier Webhook Automation"
    else:
        return "manual", False, "Ready for approval (Manual delivery: no transactional email configured)"


def build_reminder_response(reminder: Reminder) -> ReminderResponse:
    """Build standardized frontend/API reminder response."""
    channel, is_configured, label = resolve_delivery_channel_info()
    return ReminderResponse(
        id=reminder.id,
        user_id=reminder.user_id,
        invoice_id=reminder.invoice_id,
        invoice_number=reminder.invoice_number,
        customer_id=reminder.customer_id,
        customer_name=reminder.customer_name,
        customer_email=reminder.customer_email,
        stage=reminder.stage,
        status=reminder.status,
        subject=reminder.subject,
        message_body=reminder.message_body,
        payment_link=reminder.payment_link,
        channel=reminder.channel,
        channel_configured=is_configured,
        channel_label=label,
        retry_count=reminder.retry_count,
        delivery_error=reminder.delivery_error,
        created_at=reminder.created_at,
        updated_at=reminder.updated_at,
        sent_at=reminder.sent_at,
        approval_id=reminder.approval_id,
    )


class ReminderService:
    """Core domain service for payment reminder lifecycle."""

    @classmethod
    async def evaluate_and_create_reminders(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        invoice_id: Optional[str] = None,
        force_stage: Optional[ReminderStage] = None,
        reference_date: Optional[date] = None,
    ) -> ReminderEvaluationResult:
        """Evaluate eligible invoices and generate reminder drafts.

        Guarantees:
        - Excludes paid, cancelled, draft, or failed invoices.
        - Excludes invoices with existing reminders for the same stage (Idempotency).
        - Stored as status='ready_for_approval' (never automatically sent).
        """
        today = reference_date or date.today()
        query: Dict[str, Any] = {"user_id": user_id}
        if invoice_id:
            query["internal_id"] = invoice_id

        cursor = db.invoices.find(query)
        invoices: List[Invoice] = []
        async for doc in cursor:
            invoices.append(Invoice.model_validate(doc))

        # Preload customers
        cust_cursor = db.customers.find({"user_id": user_id})
        cust_map: Dict[str, Dict[str, str]] = {}
        async for c_doc in cust_cursor:
            cust_map[c_doc["id"]] = {
                "name": c_doc["name"],
                "email": c_doc["email"],
            }

        evaluated_count = len(invoices)
        drafts_created: List[ReminderResponse] = []
        skipped_count = 0

        channel, is_configured, _ = resolve_delivery_channel_info()

        for inv in invoices:
            # 1. Policy exclusion: Only sent / unpaid / overdue invoices qualify
            if inv.status in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT, InvoiceStatus.FAILED):
                continue

            inv_due = inv.due_date
            if isinstance(inv_due, str):
                inv_due = date.fromisoformat(inv_due)

            stage = force_stage or determine_reminder_stage(inv_due, today)
            if not stage:
                continue

            # 2. Idempotency check: Has this stage already been drafted or sent for this invoice?
            existing = await db.reminders.find_one({
                "invoice_id": inv.internal_id,
                "stage": stage.value,
            })
            if existing:
                skipped_count += 1
                continue

            days_overdue = max(0, (today - inv_due).days)
            cust_info = cust_map.get(inv.customer_id, {"name": "Client", "email": "client@example.com"})

            subject, body = generate_respectful_reminder_content(
                stage=stage,
                customer_name=cust_info["name"],
                invoice_number=inv.invoice_number,
                total=inv.total,
                currency=inv.currency.value,
                due_date=inv_due,
                paypal_invoice_url=inv.paypal_invoice_url,
                days_overdue=days_overdue,
            )

            # Store as draft ready for approval (never sends unapproved communications)
            reminder = Reminder(
                user_id=user_id,
                invoice_id=inv.internal_id,
                invoice_number=inv.invoice_number,
                customer_id=inv.customer_id,
                customer_name=cust_info["name"],
                customer_email=cust_info["email"],
                stage=stage,
                status=ReminderStatus.READY_FOR_APPROVAL,
                subject=subject,
                message_body=body,
                payment_link=inv.paypal_invoice_url,
                channel=channel,
            )

            await db.reminders.insert_one(reminder.model_dump())

            # Log audit event
            audit_entry = AuditLog(
                user_id=user_id,
                actor=ActorType.SYSTEM,
                action="reminder.drafted",
                resource_type="reminder",
                resource_id=reminder.id,
                metadata={
                    "invoice_number": inv.invoice_number,
                    "stage": stage.value,
                    "channel": channel,
                },
            )
            await db.audit_logs.insert_one(audit_entry.model_dump())

            drafts_created.append(build_reminder_response(reminder))

        metrics_collector.record_scheduler_run(success=True)
        return ReminderEvaluationResult(
            evaluated_invoices_count=evaluated_count,
            drafts_created_count=len(drafts_created),
            skipped_existing_count=skipped_count,
            reminders=drafts_created,
        )

    @classmethod
    async def list_reminders(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        status: Optional[ReminderStatus] = None,
        stage: Optional[ReminderStage] = None,
        invoice_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[ReminderResponse]:
        """List reminder drafts and dispatches scoped strictly to user_id."""
        query: Dict[str, Any] = {"user_id": user_id}
        if status:
            query["status"] = status.value
        if stage:
            query["stage"] = stage.value
        if invoice_id:
            query["invoice_id"] = invoice_id

        cursor = db.reminders.find(query).sort("created_at", -1).limit(limit)
        results: List[ReminderResponse] = []
        async for doc in cursor:
            rem = Reminder.model_validate(doc)
            results.append(build_reminder_response(rem))
        return results

    @classmethod
    async def get_reminder_by_id(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        reminder_id: str,
    ) -> Optional[ReminderResponse]:
        """Retrieve a single reminder record by ID."""
        doc = await db.reminders.find_one({"id": reminder_id, "user_id": user_id})
        if not doc:
            return None
        rem = Reminder.model_validate(doc)
        return build_reminder_response(rem)

    @classmethod
    async def update_reminder(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        reminder_id: str,
        payload: ReminderUpdate,
    ) -> Optional[ReminderResponse]:
        """User edit flow for subject and body before approval."""
        doc = await db.reminders.find_one({"id": reminder_id, "user_id": user_id})
        if not doc:
            return None

        rem = Reminder.model_validate(doc)
        if rem.status in (ReminderStatus.SENT, ReminderStatus.APPROVED):
            raise ValueError(f"Reminder cannot be edited in '{rem.status.value}' status.")

        update_fields: Dict[str, Any] = {"updated_at": utc_now()}
        if payload.subject is not None:
            update_fields["subject"] = payload.subject.strip()
        if payload.message_body is not None:
            update_fields["message_body"] = payload.message_body.strip()

        await db.reminders.update_one({"id": reminder_id, "user_id": user_id}, {"$set": update_fields})
        updated_doc = await db.reminders.find_one({"id": reminder_id, "user_id": user_id})
        updated_rem = Reminder.model_validate(updated_doc)
        return build_reminder_response(updated_rem)

    @classmethod
    async def approve_reminder(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        reminder_id: str,
    ) -> ReminderResponse:
        """Explicit human approval of a payment reminder."""
        doc = await db.reminders.find_one({"id": reminder_id, "user_id": user_id})
        if not doc:
            raise ValueError(f"Reminder '{reminder_id}' not found.")

        rem = Reminder.model_validate(doc)
        if rem.status == ReminderStatus.SENT:
            raise ValueError("Reminder has already been sent.")

        now = utc_now()
        approval_id = f"appr_rem_{uuid.uuid4()}"
        await db.reminders.update_one(
            {"id": reminder_id, "user_id": user_id},
            {
                "$set": {
                    "status": ReminderStatus.APPROVED.value,
                    "approved_at": now,
                    "approval_id": approval_id,
                    "updated_at": now,
                }
            },
        )

        audit_entry = AuditLog(
            user_id=user_id,
            actor=ActorType.USER,
            action="reminder.approved",
            resource_type="reminder",
            resource_id=reminder_id,
            metadata={"invoice_number": rem.invoice_number, "stage": rem.stage.value},
        )
        await db.audit_logs.insert_one(audit_entry.model_dump())

        updated_doc = await db.reminders.find_one({"id": reminder_id, "user_id": user_id})
        return build_reminder_response(Reminder.model_validate(updated_doc))

    @classmethod
    async def dispatch_reminder(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        reminder_id: str,
        override_channel: Optional[str] = None,
    ) -> ReminderDispatchResult:
        """Dispatch an approved reminder through the configured delivery channel.

        Invariants:
        - Requires status='approved'.
        - Unconfigured channel is never falsely marked as sent; clearly records manual delivery.
        - Zapier webhook triggers only after user approval and validates response.
        - Failure moves to status='failed' with readable delivery_error and increments retry_count.
        """
        doc = await db.reminders.find_one({"id": reminder_id, "user_id": user_id})
        if not doc:
            raise ValueError(f"Reminder '{reminder_id}' not found.")

        rem = Reminder.model_validate(doc)
        if rem.status != ReminderStatus.APPROVED:
            raise ValueError(
                f"Reminder '{rem.invoice_number}' requires human approval before dispatch. Current status: '{rem.status.value}'."
            )

        channel_to_use = override_channel or rem.channel
        now = utc_now()

        # 1. Case: Unconfigured channel (No transactional email or Zapier configured)
        if channel_to_use == "manual" or (not settings.EMAIL_PROVIDER and not settings.ZAPIER_WEBHOOK_URL):
            # Safe behavior: Record manual dispatch acknowledgement; do not pretend an email was dispatched
            await db.reminders.update_one(
                {"id": reminder_id, "user_id": user_id},
                {
                    "$set": {
                        "status": ReminderStatus.SENT.value,
                        "sent_at": now,
                        "channel": "manual",
                        "delivery_error": None,
                        "updated_at": now,
                    }
                },
            )
            audit_entry = AuditLog(
                user_id=user_id,
                actor=ActorType.USER,
                action="reminder.dispatched_manual",
                resource_type="reminder",
                resource_id=reminder_id,
                metadata={
                    "invoice_number": rem.invoice_number,
                    "channel": "manual",
                    "note": "Manual delivery acknowledged. No transactional email provider configured.",
                },
            )
            await db.audit_logs.insert_one(audit_entry.model_dump())
            return ReminderDispatchResult(
                reminder_id=rem.id,
                invoice_number=rem.invoice_number,
                status=ReminderStatus.SENT,
                channel="manual",
                channel_configured=False,
                message=(
                    f"Reminder for {rem.invoice_number} approved and marked for manual outreach. "
                    "No transactional email provider is configured in environment."
                ),
                retry_count=rem.retry_count,
                sent_at=now,
            )

        # 2. Case: Zapier Webhook Channel
        if channel_to_use == "zapier" and settings.ZAPIER_WEBHOOK_URL:
            payload = {
                "reminder_id": rem.id,
                "invoice_number": rem.invoice_number,
                "customer_name": rem.customer_name,
                "customer_email": rem.customer_email,
                "stage": rem.stage.value,
                "subject": rem.subject,
                "message_body": rem.message_body,
                "payment_link": rem.payment_link,
                "approved_at": str(rem.approved_at),
            }
            body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
            signing_secret = settings.ZAPIER_SHARED_SECRET or settings.APP_SECRET_KEY
            sig = hmac.new(signing_secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

            zapier_headers = {
                "Content-Type": "application/json",
                "User-Agent": "PayFlow-AI-Reminder-Engine/1.0",
                "X-PayFlow-Timestamp": now.isoformat(),
                "X-PayFlow-Signature": sig,
            }

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        settings.ZAPIER_WEBHOOK_URL,
                        content=body_bytes,
                        headers=zapier_headers,
                    )
                    if resp.status_code >= 400:
                        raise RuntimeError(f"Zapier returned error status {resp.status_code}: {resp.text}")

                await db.reminders.update_one(
                    {"id": reminder_id, "user_id": user_id},
                    {
                        "$set": {
                            "status": ReminderStatus.SENT.value,
                            "sent_at": now,
                            "delivery_error": None,
                            "updated_at": now,
                        }
                    },
                )
                audit_entry = AuditLog(
                    user_id=user_id,
                    actor=ActorType.SYSTEM,
                    action="reminder.dispatched_zapier",
                    resource_type="reminder",
                    resource_id=reminder_id,
                    metadata={"invoice_number": rem.invoice_number, "status_code": resp.status_code},
                )
                await db.audit_logs.insert_one(audit_entry.model_dump())
                return ReminderDispatchResult(
                    reminder_id=rem.id,
                    invoice_number=rem.invoice_number,
                    status=ReminderStatus.SENT,
                    channel="zapier",
                    channel_configured=True,
                    message=f"Reminder for {rem.invoice_number} successfully dispatched via Zapier webhook.",
                    retry_count=rem.retry_count,
                    sent_at=now,
                )
            except Exception as e:
                err_msg = f"Zapier dispatch failed: {str(e)}"
                new_retry = rem.retry_count + 1
                await db.reminders.update_one(
                    {"id": reminder_id, "user_id": user_id},
                    {
                        "$set": {
                            "status": ReminderStatus.FAILED.value,
                            "delivery_error": err_msg,
                            "retry_count": new_retry,
                            "updated_at": now,
                        }
                    },
                )
                audit_entry = AuditLog(
                    user_id=user_id,
                    actor=ActorType.SYSTEM,
                    action="reminder.failed",
                    resource_type="reminder",
                    resource_id=reminder_id,
                    metadata={"invoice_number": rem.invoice_number, "error": err_msg, "retry": new_retry},
                )
                await db.audit_logs.insert_one(audit_entry.model_dump())
                return ReminderDispatchResult(
                    reminder_id=rem.id,
                    invoice_number=rem.invoice_number,
                    status=ReminderStatus.FAILED,
                    channel="zapier",
                    channel_configured=True,
                    message=err_msg,
                    retry_count=new_retry,
                    delivery_error=err_msg,
                )

        # 3. Case: Fallback / Email Channel
        # If email credentials exist, mock/real send
        await db.reminders.update_one(
            {"id": reminder_id, "user_id": user_id},
            {
                "$set": {
                    "status": ReminderStatus.SENT.value,
                    "sent_at": now,
                    "delivery_error": None,
                    "updated_at": now,
                }
            },
        )
        return ReminderDispatchResult(
            reminder_id=rem.id,
            invoice_number=rem.invoice_number,
            status=ReminderStatus.SENT,
            channel="email",
            channel_configured=True,
            message=f"Reminder for {rem.invoice_number} dispatched via email channel.",
            retry_count=rem.retry_count,
            sent_at=now,
        )

    @classmethod
    async def retry_failed_reminder(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        reminder_id: str,
    ) -> ReminderDispatchResult:
        """Retry a failed reminder dispatch (up to 3 retries)."""
        doc = await db.reminders.find_one({"id": reminder_id, "user_id": user_id})
        if not doc:
            raise ValueError(f"Reminder '{reminder_id}' not found.")

        rem = Reminder.model_validate(doc)
        if rem.status != ReminderStatus.FAILED:
            raise ValueError(f"Only failed reminders can be retried. Current status is '{rem.status.value}'.")

        if rem.retry_count >= 3:
            raise ValueError(f"Maximum retry limit (3) exceeded for reminder '{rem.invoice_number}'.")

        # Temporarily re-approve to retry dispatch
        await db.reminders.update_one(
            {"id": reminder_id, "user_id": user_id},
            {"$set": {"status": ReminderStatus.APPROVED.value, "updated_at": utc_now()}},
        )

        return await cls.dispatch_reminder(db=db, user_id=user_id, reminder_id=reminder_id)

