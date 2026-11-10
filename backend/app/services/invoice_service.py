"""Invoice domain service managing draft creation, authoritative Decimal math,
audit trails, and human approval submissions.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import math
from typing import List, Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.approval import Approval, compute_payload_hash
from app.models.audit import AuditLog
from app.models.enums import ActionType, ActorType, ApprovalStatus, InvoiceStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem, utc_now
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    SubmitForApprovalResponse,
)


async def generate_invoice_number(db: AsyncIOMotorDatabase, user_id: str) -> str:
    """Generate a sequential, human-readable invoice reference unique per user."""
    current_year = datetime.now(timezone.utc).year
    count = await db.invoices.count_documents({"user_id": user_id})
    candidate_num = count + 1

    # Check for collisions and increment if necessary
    while True:
        candidate_str = f"INV-{current_year}-{candidate_num:04d}"
        existing = await db.invoices.find_one({"user_id": user_id, "invoice_number": candidate_str})
        if not existing:
            return candidate_str
        candidate_num += 1


async def create_invoice_draft(
    db: AsyncIOMotorDatabase,
    user_id: str,
    payload: InvoiceCreate,
) -> Invoice:
    """Create a new invoice in DRAFT status with authoritative server-side totals."""
    # 1. Validate customer ownership
    customer = await db.customers.find_one({
        "id": payload.customer_id,
        "user_id": user_id,
        "is_active": True,
    })
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Customer '{payload.customer_id}' not found or does not belong to the authenticated user.",
        )

    # 2. Resolve invoice number
    if payload.invoice_number and payload.invoice_number.strip():
        inv_number = payload.invoice_number.strip()
        existing = await db.invoices.find_one({"user_id": user_id, "invoice_number": inv_number})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice number '{inv_number}' already exists for your account.",
            )
    else:
        inv_number = await generate_invoice_number(db, user_id)

    # 3. Construct line items and compute authoritative totals
    issue_date = payload.issue_date or utc_now().date()
    if payload.due_date < issue_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice due date cannot precede the issue date.",
        )

    items = [
        InvoiceItem(
            name=item.name.strip(),
            description=item.description.strip() if item.description else None,
            quantity=item.quantity,
            unit_price=item.unit_price,
            tax=item.tax,
        )
        for item in payload.items
    ]

    # Note: Client-supplied previews are ignored; model computes authoritative Decimal totals
    invoice = Invoice(
        user_id=user_id,
        customer_id=payload.customer_id,
        invoice_number=inv_number,
        items=items,
        currency=payload.currency,
        issue_date=issue_date,
        due_date=payload.due_date,
        status=InvoiceStatus.DRAFT,
        notes=payload.notes.strip() if payload.notes else None,
    )

    await db.invoices.insert_one(invoice.model_dump())

    # 4. Append audit log
    audit_entry = AuditLog(
        user_id=user_id,
        actor=ActorType.USER,
        action="invoice.created",
        resource_type="invoice",
        resource_id=invoice.internal_id,
        metadata={
            "invoice_number": invoice.invoice_number,
            "total": str(invoice.total),
            "currency": invoice.currency.value,
            "customer_id": invoice.customer_id,
        },
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return invoice


async def list_invoices(
    db: AsyncIOMotorDatabase,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    customer_id: Optional[str] = None,
    overdue_only: bool = False,
    search: Optional[str] = None,
) -> InvoiceListResponse:
    """List user invoices with filtering, overdue checks, and stable sorting."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    query: dict = {"user_id": user_id}

    if status_filter:
        query["status"] = status_filter

    if customer_id:
        query["customer_id"] = customer_id

    today_str = str(utc_now().date())
    if overdue_only:
        query["status"] = {"$in": [InvoiceStatus.SENT.value, InvoiceStatus.UNPAID.value, InvoiceStatus.OVERDUE.value]}
        query["due_date"] = {"$lt": today_str}

    if search:
        search_regex = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [
            {"invoice_number": search_regex},
            {"notes": search_regex},
            {"items.name": search_regex},
        ]

    total = await db.invoices.count_documents(query)
    pages = math.ceil(total / page_size) if total > 0 else 1
    skip = (page - 1) * page_size

    cursor = db.invoices.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    docs = []
    customer_ids = set()
    async for doc in cursor:
        docs.append(doc)
        cid = doc.get("customer_id")
        if cid:
            customer_ids.add(cid)

    customer_map = {}
    if customer_ids:
        c_cursor = db.customers.find({"id": {"$in": list(customer_ids)}, "user_id": user_id})
        async for c in c_cursor:
            customer_map[c.get("id")] = c.get("name")

    items = []
    for doc in docs:
        resp = InvoiceResponse.model_validate(doc)
        resp.customer_name = customer_map.get(doc.get("customer_id"))
        items.append(resp)

    return InvoiceListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


async def get_invoice_by_id(
    db: AsyncIOMotorDatabase,
    user_id: str,
    invoice_id: str,
) -> Invoice:
    """Retrieve invoice by internal ID, enforcing multi-tenant ownership."""
    doc = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice '{invoice_id}' not found.",
        )
    return Invoice.model_validate(doc)


async def update_invoice_draft(
    db: AsyncIOMotorDatabase,
    user_id: str,
    invoice_id: str,
    payload: InvoiceUpdate,
) -> Invoice:
    """Update draft invoice details.

    Invariant:
        Only invoices in 'draft' status can be modified.
        Any attempt to edit a pending_approval, sent, or paid invoice is rejected.
    """
    doc = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    invoice = Invoice.model_validate(doc)

    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only draft invoices can be edited. Current status is '{invoice.status.value}'.",
        )

    # Validate customer ownership if changed
    if payload.customer_id and payload.customer_id != invoice.customer_id:
        customer = await db.customers.find_one({
            "id": payload.customer_id,
            "user_id": user_id,
            "is_active": True,
        })
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Customer '{payload.customer_id}' not found.",
            )
        invoice.customer_id = payload.customer_id

    if payload.currency:
        invoice.currency = payload.currency

    if payload.issue_date:
        invoice.issue_date = payload.issue_date

    if payload.due_date:
        if payload.due_date < invoice.issue_date:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Due date cannot precede issue date.")
        invoice.due_date = payload.due_date

    if payload.notes is not None:
        invoice.notes = payload.notes.strip() if payload.notes else None

    if payload.items is not None and len(payload.items) > 0:
        invoice.items = [
            InvoiceItem(
                name=it.name.strip(),
                description=it.description.strip() if it.description else None,
                quantity=it.quantity,
                unit_price=it.unit_price,
                tax=it.tax,
            )
            for it in payload.items
        ]
        # Recompute totals authoritatively
        invoice.compute_totals()

    invoice.updated_at = utc_now()

    await db.invoices.replace_one(
        {"internal_id": invoice_id, "user_id": user_id},
        invoice.model_dump(),
    )

    # Append audit log
    audit_entry = AuditLog(
        user_id=user_id,
        actor=ActorType.USER,
        action="invoice.updated",
        resource_type="invoice",
        resource_id=invoice.internal_id,
        metadata={"total": str(invoice.total), "invoice_number": invoice.invoice_number},
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return invoice


async def submit_invoice_for_approval(
    db: AsyncIOMotorDatabase,
    user_id: str,
    invoice_id: str,
) -> SubmitForApprovalResponse:
    """Submit an editable invoice draft for human approval before PayPal dispatch.

    Creates an immutable snapshot and cryptographically binds an Approval token.
    """
    doc = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    invoice = Invoice.model_validate(doc)

    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit invoice for approval. Expected 'draft', found '{invoice.status.value}'.",
        )

    # 1. Create immutable snapshot of the approved payload
    payload_snapshot = {
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

    # 2. Compute deterministic SHA-256 payload hash
    payload_hash = compute_payload_hash(payload_snapshot)

    # 3. Create Approval record
    approval = Approval(
        user_id=user_id,
        action_type=ActionType.CREATE_PAYPAL_INVOICE,
        resource_type="invoice",
        resource_id=invoice.internal_id,
        payload_snapshot=payload_snapshot,
        payload_hash=payload_hash,
        status=ApprovalStatus.PENDING,
    )
    await db.approvals.insert_one(approval.model_dump())

    # 4. Transition invoice status
    invoice.transition_status(InvoiceStatus.PENDING_APPROVAL)
    await db.invoices.replace_one(
        {"internal_id": invoice_id, "user_id": user_id},
        invoice.model_dump(),
    )

    # 5. Append audit log
    audit_entry = AuditLog(
        user_id=user_id,
        actor=ActorType.USER,
        action="invoice.submitted_for_approval",
        resource_type="invoice",
        resource_id=invoice.internal_id,
        metadata={
            "approval_id": approval.id,
            "payload_hash": payload_hash,
            "invoice_number": invoice.invoice_number,
        },
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return SubmitForApprovalResponse(
        invoice=InvoiceResponse.model_validate(invoice),
        approval_id=approval.id,
        payload_hash=payload_hash,
        status="pending_approval",
        message="Invoice submitted for human approval. Awaiting explicit authorization in Approval Center.",
    )
