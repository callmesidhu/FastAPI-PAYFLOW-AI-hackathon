"""Append-Only-Style Audit Trail and Transaction Ledger Service (Prompt 24).

Architecture & Security Invariants:
- Described strictly as an "append-only-style audit log" at the application layer.
- Enforces zero update or delete endpoints across the entire application API.
- Masks and scrubs secrets and PII from metadata before persistence.
- Provides chronological activity timelines for invoice details.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.security import scrub_secrets
from app.core.logging import get_logger
from app.models.audit import ActorType, AuditLog, utc_now
from app.models.transaction import Transaction
from app.schemas.audit import AuditLogResponse, InvoiceTimelineResponse, TimelineEvent
from app.schemas.transaction import TransactionResponse

logger = get_logger("payflow.audit_service")

# User-friendly activity timeline label mapping
ACTION_LABEL_MAP: Dict[str, str] = {
    "invoice.created": "Invoice Draft Created",
    "invoice.updated": "Draft Invoice Modified",
    "invoice.submitted_for_approval": "Submitted for Owner Approval",
    "invoice.approved": "Authorized by Owner",
    "invoice.rejected": "Rejected by Owner",
    "invoice.cancelled": "Invoice Cancelled",
    "invoice.deleted": "Draft Invoice Deleted",
    "paypal.invoice_created": "Created in PayPal Sandbox",
    "paypal.invoice_sent": "Dispatched to Client via PayPal",
    "paypal.invoice_cancelled": "Cancelled in PayPal Sandbox",
    "payment.settled": "Payment Settled via PayPal",
    "payment.refunded": "Payment Refunded",
    "reminder.drafted": "Payment Reminder Drafted",
    "reminder.approved": "Reminder Authorized for Dispatch",
    "reminder.dispatched": "Reminder Dispatched to Client",
    "reminder.dispatched_manual": "Manual Outreach Acknowledged",
    "reminder.dispatched_zapier": "Dispatched via Zapier Webhook",
    "reminder.failed": "Reminder Dispatch Failed",
    "webhook.received": "PayPal Webhook Event Received",
    "webhook.verified": "PayPal Webhook Cryptographically Verified",
    "system.error": "System Operational Error",
}


def sanitize_audit_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Scrub tokens, secrets, hashes, and passwords from metadata values."""
    sanitized: Dict[str, Any] = {}
    for k, v in metadata.items():
        if isinstance(v, str):
            sanitized[k] = scrub_secrets(v)
        elif isinstance(v, dict):
            sanitized[k] = sanitize_audit_metadata(v)
        else:
            sanitized[k] = v
    return sanitized


class AuditService:
    """Service managing append-only-style audit logs and transaction ledger records."""

    @classmethod
    async def record_event(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        actor: ActorType = ActorType.USER,
        result: str = "success",
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Append an event to the audit trail.

        Invariant:
        - Application layer is strictly append-only.
        - Secrets and credentials scrubbed before write.
        """
        clean_metadata = sanitize_audit_metadata(metadata or {})
        entry = AuditLog(
            user_id=user_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            result=result,
            correlation_id=correlation_id or str(uuid.uuid4()),
            metadata=clean_metadata,
            created_at=utc_now(),
        )
        await db.audit_logs.insert_one(entry.model_dump())
        return entry

    @classmethod
    async def list_audit_logs(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[AuditLogResponse]:
        """List audit events scoped strictly to user_id."""
        query: Dict[str, Any] = {"user_id": user_id}
        if resource_type:
            query["resource_type"] = resource_type
        if resource_id:
            query["resource_id"] = resource_id
        if action:
            query["action"] = action

        cursor = db.audit_logs.find(query).sort("created_at", -1).limit(limit)
        results: List[AuditLogResponse] = []
        async for doc in cursor:
            results.append(AuditLogResponse.model_validate(doc))
        return results

    @classmethod
    async def get_invoice_timeline(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        invoice_id: str,
    ) -> InvoiceTimelineResponse:
        """Build user-visible chronological activity timeline for an invoice."""
        inv = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user_id})
        if not inv:
            inv = await db.invoices.find_one({"invoice_number": invoice_id, "user_id": user_id})
        if not inv:
            raise ValueError(f"Invoice '{invoice_id}' not found.")

        actual_id = inv["internal_id"]
        inv_number = inv["invoice_number"]

        # Find all audit records relating to this invoice
        query = {
            "user_id": user_id,
            "$or": [
                {"resource_id": actual_id},
                {"metadata.invoice_number": inv_number},
                {"metadata.paypal_invoice_id": inv.get("paypal_invoice_id")},
            ],
        }

        cursor = db.audit_logs.find(query).sort("created_at", 1)
        events: List[TimelineEvent] = []
        async for doc in cursor:
            action_raw = doc.get("action", "")
            action_label = ACTION_LABEL_MAP.get(action_raw, action_raw.replace(".", " ").title())
            actor_raw = doc.get("actor", ActorType.USER)
            actor_str = actor_raw.value if hasattr(actor_raw, "value") else str(actor_raw)

            events.append(
                TimelineEvent(
                    id=doc["id"],
                    action=action_raw,
                    action_label=action_label,
                    actor_type=actor_str,
                    timestamp=doc["created_at"],
                    result=doc.get("result", "success"),
                    metadata=doc.get("metadata", {}),
                )
            )

        return InvoiceTimelineResponse(
            invoice_id=actual_id,
            invoice_number=inv_number,
            events=events,
        )

    @classmethod
    async def list_transactions(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        invoice_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[TransactionResponse]:
        """List verified financial transactions scoped to user_id."""
        query: Dict[str, Any] = {"user_id": user_id}
        if invoice_id:
            query["invoice_id"] = invoice_id

        cursor = db.transactions.find(query).sort("created_at", -1).limit(limit)
        results: List[TransactionResponse] = []
        async for doc in cursor:
            results.append(TransactionResponse.model_validate(doc))
        return results

