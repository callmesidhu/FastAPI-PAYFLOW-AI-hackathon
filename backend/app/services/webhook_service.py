"""PayPal Webhook Verification & State Reconciliation Service (Prompt 23).

Enforces:
- Cryptographic signature verification via PayPal REST API (/v1/notifications/verify-webhook-signature).
- Strictly rejects unverified webhooks (HTTP 400/401).
- Replay protection & idempotency via db.webhook_events unique event_id index.
- Persists verified event before applying state mutations.
- Maps documented event types (INVOICING.INVOICE.PAID, INVOICING.INVOICE.CANCELLED, PAYMENT.CAPTURE.COMPLETED).
- Records transactions and append-only audit trail entries.
- Never marks an invoice paid on unverified requests.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.metrics import ErrorCategory, metrics_collector
from app.models.audit import ActorType, AuditLog
from app.models.enums import InvoiceStatus, SupportedCurrency
from app.models.transaction import Transaction
from app.models.webhook import WebhookEvent, utc_now
from app.schemas.webhook import WebhookProcessingResponse
from app.services.paypal_service import paypal_service

logger = get_logger("payflow.webhook_service")
settings = get_settings()

REQUIRED_HEADER_KEYS = [
    "paypal-auth-algo",
    "paypal-cert-url",
    "paypal-transmission-id",
    "paypal-transmission-sig",
    "paypal-transmission-time",
]


def extract_header_case_insensitive(headers: Dict[str, str], key: str) -> Optional[str]:
    """Retrieve header value regardless of letter casing."""
    lower_target = key.lower()
    for h_name, h_val in headers.items():
        if h_name.lower() == lower_target:
            return h_val
    return None


def redact_sensitive_payload(raw_event: Dict[str, Any]) -> Dict[str, Any]:
    """Create safe redacted snapshot of webhook payload for audit and debugging."""
    redacted = dict(raw_event)
    # Remove sensitive or oversized binary structures
    if "resource" in redacted and isinstance(redacted["resource"], dict):
        res = dict(redacted["resource"])
        if "links" in res:
            res["links"] = len(res["links"])  # Just count links
        redacted["resource"] = res
    return redacted


class WebhookService:
    """Service handling PayPal webhook verification, replay prevention, and ledger reconciliation."""

    @classmethod
    async def process_webhook(
        cls,
        db: AsyncIOMotorDatabase,
        headers: Dict[str, str],
        raw_event: Dict[str, Any],
    ) -> WebhookProcessingResponse:
        """Verify and process incoming PayPal webhook event.

        Raises:
            HTTPException 400: If required headers or event payload are missing.
            HTTPException 401: If PayPal signature verification fails.
        """
        # 1. Extract required cryptographic headers
        auth_algo = extract_header_case_insensitive(headers, "paypal-auth-algo")
        cert_url = extract_header_case_insensitive(headers, "paypal-cert-url")
        transmission_id = extract_header_case_insensitive(headers, "paypal-transmission-id")
        transmission_sig = extract_header_case_insensitive(headers, "paypal-transmission-sig")
        transmission_time = extract_header_case_insensitive(headers, "paypal-transmission-time")

        if not all([auth_algo, cert_url, transmission_id, transmission_sig, transmission_time]):
            logger.warning("PayPal webhook rejected: Missing required cryptographic headers.")
            metrics_collector.record_webhook_event(success=False, error_category=ErrorCategory.WEBHOOK_MALFORMED_HEADER)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required PayPal webhook cryptographic headers (auth-algo, cert-url, transmission-id, transmission-sig, transmission-time).",
            )

        webhook_id = settings.PAYPAL_WEBHOOK_ID
        if not webhook_id or "placeholder" in webhook_id.lower():
            logger.error("PayPal webhook rejected: PAYPAL_WEBHOOK_ID is not configured.")
            metrics_collector.record_webhook_event(success=False, error_category=ErrorCategory.WEBHOOK_MALFORMED_HEADER)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PAYPAL_WEBHOOK_ID is not configured in server environment.",
            )

        # 2. Verify signature using official PayPal verification endpoint
        is_verified = await paypal_service.verify_webhook_signature(
            transmission_id=transmission_id,
            transmission_time=transmission_time,
            transmission_sig=transmission_sig,
            cert_url=cert_url,
            auth_algo=auth_algo,
            webhook_id=webhook_id,
            raw_body=raw_event,
        )

        if not is_verified:
            logger.warning(
                "PayPal webhook rejected: Signature verification failed for transmission %s.",
                transmission_id,
            )
            metrics_collector.record_webhook_event(success=False, error_category=ErrorCategory.WEBHOOK_SIGNATURE_INVALID)
            # Log security audit failure
            audit_failure = AuditLog(
                user_id="system",
                actor=ActorType.PAYPAL_WEBHOOK,
                action="webhook.verification_failed",
                resource_type="webhook_event",
                resource_id=transmission_id,
                result="rejected",
                metadata={"transmission_id": transmission_id, "cert_url": cert_url},
            )
            await db.audit_logs.insert_one(audit_failure.model_dump())
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="PayPal webhook signature verification failed. Event authenticity could not be established.",
            )

        # 3. Extract event metadata
        event_id = raw_event.get("id")
        event_type = raw_event.get("event_type", "UNKNOWN")
        resource = raw_event.get("resource", {})
        resource_id = resource.get("id", "UNKNOWN_RESOURCE")

        if not event_id:
            metrics_collector.record_webhook_event(success=False, error_category=ErrorCategory.WEBHOOK_MALFORMED_HEADER)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed webhook event: missing event id.",
            )

        now = utc_now()

        # 4. Replay Protection & Idempotency Check
        existing_event = await db.webhook_events.find_one({"event_id": event_id})
        if existing_event:
            logger.info("Duplicate PayPal webhook event received (id: %s). Skipping effects.", event_id)
            metrics_collector.record_webhook_event(success=False, error_category=ErrorCategory.WEBHOOK_REPLAY_ATTACK)
            # Audit duplicate
            audit_dup = AuditLog(
                user_id="system",
                actor=ActorType.PAYPAL_WEBHOOK,
                action="webhook.duplicate_ignored",
                resource_type="webhook_event",
                resource_id=event_id,
                result="ignored",
                metadata={"event_id": event_id, "event_type": event_type},
            )
            await db.audit_logs.insert_one(audit_dup.model_dump())
            return WebhookProcessingResponse(
                status="duplicate",
                event_id=event_id,
                event_type=event_type,
                message=f"Event '{event_id}' has already been processed.",
                persisted=False,
                processed_at=now,
            )

        # 5. Persist verified event before applying state mutations
        redacted = redact_sensitive_payload(raw_event)
        event_doc = WebhookEvent(
            event_id=event_id,
            event_type=event_type,
            resource_type=raw_event.get("resource_type", "invoicing_invoice"),
            resource_id=resource_id,
            verified=True,
            received_at=now,
            processed_at=now,
            status="processed",
            summary=f"Verified PayPal webhook: {event_type} for resource {resource_id}",
            payload_redacted=redacted,
        )
        await db.webhook_events.insert_one(event_doc.model_dump())

        reconciled_invoice_id: Optional[str] = None

        # 6. Apply documented state transitions
        if event_type in ("INVOICING.INVOICE.PAID", "PAYMENT.CAPTURE.COMPLETED"):
            # Lookup invoice by PayPal invoice ID or invoice number
            paypal_inv_id = resource.get("id")
            detail = resource.get("detail", {})
            inv_number = detail.get("invoice_number")

            inv_query: Dict[str, Any] = {}
            if paypal_inv_id:
                inv_query = {"paypal_invoice_id": paypal_inv_id}
            elif inv_number:
                inv_query = {"invoice_number": inv_number}

            invoice_doc = await db.invoices.find_one(inv_query) if inv_query else None

            # Fallback probe to PayPal Invoicing API if resource detail is incomplete
            if not invoice_doc and paypal_inv_id and "INV2-" in paypal_inv_id:
                try:
                    fresh_paypal_inv = await paypal_service.get_invoice(paypal_inv_id)
                    fresh_num = fresh_paypal_inv.get("detail", {}).get("invoice_number")
                    if fresh_num:
                        invoice_doc = await db.invoices.find_one({"invoice_number": fresh_num})
                except Exception as probe_err:
                    logger.warning("Fallback probe for PayPal invoice %s failed: %s", paypal_inv_id, probe_err)

            if invoice_doc:
                reconciled_invoice_id = invoice_doc["internal_id"]
                user_id = invoice_doc["user_id"]

                # Extract settlement amount
                amount_str = resource.get("amount", {}).get("value") or str(invoice_doc["total"])
                currency_str = resource.get("amount", {}).get("currency_code") or invoice_doc["currency"]
                settlement_amount = Decimal(amount_str)

                # Update invoice status to PAID
                await db.invoices.update_one(
                    {"internal_id": reconciled_invoice_id},
                    {
                        "$set": {
                            "status": InvoiceStatus.PAID.value,
                            "paid_at": now,
                            "updated_at": now,
                        }
                    },
                )

                # Extract transaction reference
                capture_id = None
                payments = resource.get("payments", {})
                if payments and "transactions" in payments and payments["transactions"]:
                    capture_id = payments["transactions"][0].get("payment_id")
                if not capture_id:
                    capture_id = resource.get("id")

                payer_email = None
                primary_recipients = resource.get("primary_recipients", [])
                if primary_recipients and "billing_info" in primary_recipients[0]:
                    payer_email = primary_recipients[0]["billing_info"].get("email_address")

                # Insert authoritative transaction ledger record
                txn = Transaction(
                    user_id=user_id,
                    invoice_id=reconciled_invoice_id,
                    invoice_number=invoice_doc["invoice_number"],
                    customer_id=invoice_doc["customer_id"],
                    paypal_capture_id=capture_id,
                    amount=settlement_amount,
                    currency=SupportedCurrency(currency_str),
                    status="completed",
                    payer_email=payer_email,
                )
                await db.transactions.insert_one(txn.model_dump())

                # Record audit log
                audit_entry = AuditLog(
                    user_id=user_id,
                    actor=ActorType.PAYPAL_WEBHOOK,
                    action="payment.settled",
                    resource_type="invoice",
                    resource_id=reconciled_invoice_id,
                    result="success",
                    metadata={
                        "invoice_number": invoice_doc["invoice_number"],
                        "paypal_invoice_id": paypal_inv_id,
                        "amount": str(settlement_amount),
                        "currency": currency_str,
                        "capture_id": capture_id,
                        "event_id": event_id,
                    },
                )
                await db.audit_logs.insert_one(audit_entry.model_dump())
                logger.info(
                    "Reconciled invoice %s as PAID via verified webhook %s.",
                    invoice_doc["invoice_number"],
                    event_id,
                )

        elif event_type == "INVOICING.INVOICE.CANCELLED":
            paypal_inv_id = resource.get("id")
            invoice_doc = await db.invoices.find_one({"paypal_invoice_id": paypal_inv_id})
            if invoice_doc:
                reconciled_invoice_id = invoice_doc["internal_id"]
                user_id = invoice_doc["user_id"]
                await db.invoices.update_one(
                    {"internal_id": reconciled_invoice_id},
                    {"$set": {"status": InvoiceStatus.CANCELLED.value, "updated_at": now}},
                )
                audit_entry = AuditLog(
                    user_id=user_id,
                    actor=ActorType.PAYPAL_WEBHOOK,
                    action="invoice.cancelled_remotely",
                    resource_type="invoice",
                    resource_id=reconciled_invoice_id,
                    result="success",
                    metadata={"paypal_invoice_id": paypal_inv_id, "event_id": event_id},
                )
                await db.audit_logs.insert_one(audit_entry.model_dump())

        elif event_type in ("INVOICING.INVOICE.REFUNDED", "PAYMENT.CAPTURE.REFUNDED"):
            paypal_inv_id = resource.get("id")
            invoice_doc = await db.invoices.find_one({"paypal_invoice_id": paypal_inv_id})
            if invoice_doc:
                reconciled_invoice_id = invoice_doc["internal_id"]
                user_id = invoice_doc["user_id"]
                audit_entry = AuditLog(
                    user_id=user_id,
                    actor=ActorType.PAYPAL_WEBHOOK,
                    action="payment.refunded",
                    resource_type="invoice",
                    resource_id=reconciled_invoice_id,
                    result="success",
                    metadata={"paypal_invoice_id": paypal_inv_id, "event_id": event_id},
                )
                await db.audit_logs.insert_one(audit_entry.model_dump())

        else:
            # Undocumented / unhandled event type: Safely acknowledge without error
            logger.info("Ignored unsupported PayPal webhook event type: %s", event_type)
            await db.webhook_events.update_one({"event_id": event_id}, {"$set": {"status": "ignored"}})
            return WebhookProcessingResponse(
                status="ignored",
                event_id=event_id,
                event_type=event_type,
                message=f"Event type '{event_type}' acknowledged and safely ignored.",
                persisted=True,
                processed_at=now,
            )

        metrics_collector.record_webhook_event(success=True)
        return WebhookProcessingResponse(
            status="processed",
            event_id=event_id,
            event_type=event_type,
            message=f"Successfully processed verified PayPal webhook '{event_type}'.",
            persisted=True,
            reconciled_invoice_id=reconciled_invoice_id,
            processed_at=now,
        )

