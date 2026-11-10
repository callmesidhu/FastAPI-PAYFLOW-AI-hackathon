"""Approval domain service managing human authorization workflows,
payload hash validation, replay prevention, and immutable decision audit trails.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.approval import Approval, compute_payload_hash
from app.models.audit import AuditLog
from app.models.enums import ActionType, ActorType, ApprovalStatus, InvoiceStatus
from app.models.invoice import Invoice
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalListResponse,
    ApprovalResponse,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_invoice_payload_snapshot(invoice: Invoice) -> Dict[str, Any]:
    """Generate canonical snapshot dictionary for an invoice."""
    return {
        "internal_id": invoice.internal_id,
        "user_id": invoice.user_id,
        "customer_id": invoice.customer_id,
        "invoice_number": invoice.invoice_number,
        "currency": invoice.currency.value,
        "subtotal": str(invoice.subtotal),
        "tax": str(invoice.tax),
        "total": str(invoice.total),
        "due_date": str(invoice.due_date),
        "items": [
            {
                "name": item.name,
                "quantity": str(item.quantity),
                "unit_price": str(item.unit_price),
                "tax": str(item.tax),
                "total": str(item.total),
            }
            for item in invoice.items
        ],
    }


async def enrich_approval_response(
    db: AsyncIOMotorDatabase,
    approval: Approval,
    user_id: str,
) -> ApprovalResponse:
    """Enrich an approval record with human-readable display parameters."""
    resp = ApprovalResponse.model_validate(approval)

    # Contextual fields extracted from payload snapshot or current db
    snapshot = approval.payload_snapshot or {}
    resp.invoice_number = snapshot.get("invoice_number")
    resp.amount = snapshot.get("total")
    resp.currency = snapshot.get("currency")

    customer_id = snapshot.get("customer_id")
    if customer_id:
        cust = await db.customers.find_one({"id": customer_id, "user_id": user_id})
        if cust:
            resp.customer_name = cust.get("name")

    if approval.action_type == ActionType.CREATE_PAYPAL_INVOICE:
        resp.display_title = f"Send PayPal Invoice {resp.invoice_number or ''}"
    elif approval.action_type == ActionType.SEND_REMINDER:
        resp.display_title = f"Dispatch Overdue Reminder for {resp.invoice_number or ''}"
    else:
        resp.display_title = f"Authorize {approval.action_type.value}"

    return resp


async def list_approvals(
    db: AsyncIOMotorDatabase,
    user_id: str,
    status_filter: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> ApprovalListResponse:
    """Retrieve approvals scoped strictly to the authenticated user."""
    query: Dict[str, Any] = {"user_id": user_id}

    if status_filter:
        query["status"] = status_filter

    if resource_id:
        query["resource_id"] = resource_id

    cursor = db.approvals.find(query).sort("created_at", -1)
    items: List[ApprovalResponse] = []

    async for doc in cursor:
        appr = Approval.model_validate(doc)
        enriched = await enrich_approval_response(db, appr, user_id)
        items.append(enriched)

    pending_count = await db.approvals.count_documents({
        "user_id": user_id,
        "status": ApprovalStatus.PENDING.value,
    })

    return ApprovalListResponse(
        items=items,
        total=len(items),
        pending_count=pending_count,
    )


async def get_approval_by_id(
    db: AsyncIOMotorDatabase,
    user_id: str,
    approval_id: str,
) -> ApprovalResponse:
    """Retrieve and verify single approval record."""
    doc = await db.approvals.find_one({"id": approval_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found.",
        )
    appr = Approval.model_validate(doc)
    return await enrich_approval_response(db, appr, user_id)


async def approve_action(
    db: AsyncIOMotorDatabase,
    user_id: str,
    approval_id: str,
    payload: Optional[ApprovalDecisionRequest] = None,
) -> ApprovalDecisionResponse:
    """Approve a pending action with strict hash verification and replay protection.

    Invariants:
        1. Only the resource owner (authenticated user) can approve.
        2. Approvals already in 'approved', 'rejected', or 'invalidated' state cannot be approved again.
        3. If underlying resource payload changed since the approval was requested, invalidate and reject.
        4. Approval does NOT execute PayPal directly; execution is a separate step.
    """
    doc = await db.approvals.find_one({"id": approval_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found.",
        )

    approval = Approval.model_validate(doc)

    # Replay protection: verify status is strictly PENDING
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve action. Approval is already in '{approval.status.value}' state.",
        )

    # Invariant: Verify underlying resource has not mutated since approval creation
    if approval.resource_type == "invoice":
        inv_doc = await db.invoices.find_one({"internal_id": approval.resource_id, "user_id": user_id})
        if not inv_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Underlying invoice '{approval.resource_id}' no longer exists.",
            )

        invoice = Invoice.model_validate(inv_doc)
        current_snapshot = compute_invoice_payload_snapshot(invoice)
        current_hash = compute_payload_hash(current_snapshot)

        if current_hash != approval.payload_hash:
            # Payload was modified! Invalidate approval to prevent unauthorized altered execution.
            approval.invalidate()
            await db.approvals.replace_one({"id": approval.id}, approval.model_dump())
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invoice contents have changed since approval was requested. The approval has been invalidated. Please review and re-submit.",
            )

    # Mark approved
    approval.approve()
    await db.approvals.replace_one({"id": approval.id}, approval.model_dump())

    # Create immutable AuditLog
    audit_entry = AuditLog(
        user_id=user_id,
        actor=ActorType.USER,
        action="approval.approved",
        resource_type=approval.resource_type,
        resource_id=approval.resource_id,
        metadata={
            "approval_id": approval.id,
            "action_type": approval.action_type.value,
            "payload_hash": approval.payload_hash,
            "reason": payload.reason if payload else None,
            "idempotency_key": payload.idempotency_key if payload else None,
        },
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return ApprovalDecisionResponse(
        approval_id=approval.id,
        status=approval.status.value,
        message=f"Action '{approval.action_type.value}' has been approved by the account owner. Ready for execution.",
        decided_at=approval.approved_at or utc_now(),
        audit_id=audit_entry.id,
    )


async def reject_action(
    db: AsyncIOMotorDatabase,
    user_id: str,
    approval_id: str,
    payload: Optional[ApprovalDecisionRequest] = None,
) -> ApprovalDecisionResponse:
    """Reject a pending action and return the underlying resource to a safe editable state."""
    doc = await db.approvals.find_one({"id": approval_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request '{approval_id}' not found.",
        )

    approval = Approval.model_validate(doc)

    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject action. Approval is already in '{approval.status.value}' state.",
        )

    # Mark rejected
    approval.reject()
    await db.approvals.replace_one({"id": approval.id}, approval.model_dump())

    # If linked to an invoice in pending_approval, transition invoice back to draft
    if approval.resource_type == "invoice":
        inv_doc = await db.invoices.find_one({"internal_id": approval.resource_id, "user_id": user_id})
        if inv_doc:
            invoice = Invoice.model_validate(inv_doc)
            if invoice.status == InvoiceStatus.PENDING_APPROVAL:
                # Transition back to DRAFT so the business owner can edit or discard
                invoice.status = InvoiceStatus.DRAFT
                invoice.updated_at = utc_now()
                await db.invoices.replace_one({"internal_id": invoice.internal_id}, invoice.model_dump())

    # Create immutable AuditLog
    audit_entry = AuditLog(
        user_id=user_id,
        actor=ActorType.USER,
        action="approval.rejected",
        resource_type=approval.resource_type,
        resource_id=approval.resource_id,
        metadata={
            "approval_id": approval.id,
            "action_type": approval.action_type.value,
            "reason": payload.reason if payload else None,
        },
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return ApprovalDecisionResponse(
        approval_id=approval.id,
        status=approval.status.value,
        message="Approval request rejected. Resource returned to draft state.",
        decided_at=approval.rejected_at or utc_now(),
        audit_id=audit_entry.id,
    )


async def invalidate_pending_approvals_for_resource(
    db: AsyncIOMotorDatabase,
    user_id: str,
    resource_type: str,
    resource_id: str,
) -> int:
    """Invalidate all pending approvals for a resource when it is mutated."""
    result = await db.approvals.update_many(
        {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": ApprovalStatus.PENDING.value,
        },
        {"$set": {"status": ApprovalStatus.INVALIDATED.value}},
    )
    return result.modified_count
