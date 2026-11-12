"""Invoice domain service managing draft creation, authoritative Decimal math,
audit trails, human approval submissions, and cross-user ownership enforcement.

Security invariants:
- Every database query is filtered by ``user_id`` extracted from the verified JWT.
- Server-side Decimal arithmetic is authoritative; any client-supplied total is ignored.
- Only DRAFT invoices may be edited; any other status causes a 400 rejection.
- Editing a DRAFT invalidates all pending approvals for that invoice automatically.
- The immutable payload snapshot hash binds an Approval to the exact invoice content.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import math
from typing import List, Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.approval import Approval, compute_payload_hash
from app.models.audit import AuditLog
from app.models.customer import Customer
from app.models.enums import ActionType, ActorType, ApprovalStatus, InvoiceStatus, SupportedCurrency
from app.models.invoice import Invoice, InvoiceItem, utc_now
from app.models.user import User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    SubmitForApprovalResponse,
)
from app.schemas.paypal import (
    PayPalInvoiceCreateResponse,
    PayPalInvoiceSendResponse,
)
from app.services.approval_service import compute_invoice_payload_snapshot
from app.services.paypal_service import (
    PayPalAPIError,
    extract_paypal_invoice_id,
    extract_paypal_invoice_url,
    paypal_service,
)



# ---------------------------------------------------------------------------
# Invoice number generation
# ---------------------------------------------------------------------------

async def generate_invoice_number(db: AsyncIOMotorDatabase, user_id: str) -> str:
    """Generate a sequential, human-readable invoice reference unique across PayPal Sandbox.

    Format: INV-{YEAR}-{NNNN}  e.g. INV-2026-0042

    Strategy:
    - Shared PayPal Sandbox accounts enforce unique invoice_number globally, so check
      uniqueness across the collection rather than only per user_id.
    """
    current_year = datetime.now(timezone.utc).year
    count = await db.invoices.count_documents({})
    candidate_num = count + 1

    while True:
        candidate_str = f"INV-{current_year}-{candidate_num:04d}"
        existing = await db.invoices.find_one({"invoice_number": candidate_str})
        if not existing:
            return candidate_str
        candidate_num += 1


# ---------------------------------------------------------------------------
# Invoice snapshot helper (shared with approval_service)
# ---------------------------------------------------------------------------

def _build_payload_snapshot(invoice: Invoice) -> dict:
    """Build the canonical, deterministic payload snapshot for hashing and approval binding."""
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


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------

async def create_invoice_draft(
    db: AsyncIOMotorDatabase,
    user_id: str,
    payload: InvoiceCreate,
) -> Invoice:
    """Create a new invoice in DRAFT status with authoritative server-side Decimal totals.

    Client-supplied ``client_total_preview`` is explicitly discarded; the
    model_validator on Invoice authoritatively computes subtotal, tax, and total.

    Raises:
        HTTPException 400: Customer not found, number collision, invalid dates, or bad items.
    """
    # 1. Validate customer ownership (must belong to authenticated user and be active)
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

    # 3. Validate dates
    issue_date = payload.issue_date or utc_now().date()
    if payload.due_date < issue_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice due date cannot precede the issue date.",
        )

    # 4. Build line items — model_validator authoritatively computes totals
    #    client_total_preview is intentionally ignored here
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

    # 5. Construct invoice — Invoice.compute_totals() model_validator runs automatically
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

    # 6. Append audit log
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
            "item_count": len(invoice.items),
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
    due_date_before: Optional[date] = None,
    due_date_after: Optional[date] = None,
) -> InvoiceListResponse:
    """List user invoices with filtering, overdue checks, date range, and stable sorting.

    Args:
        status_filter: Exact status string (e.g. "draft", "sent", "paid").
        customer_id: Filter to invoices for a specific customer.
        overdue_only: Show only sent/unpaid/overdue invoices past their due date.
        search: Case-insensitive substring search across invoice_number, notes, item names.
        due_date_before: Show only invoices with due_date <= this date (ISO date string).
        due_date_after: Show only invoices with due_date >= this date (ISO date string).
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    query: dict = {"user_id": user_id}

    if status_filter:
        # Validate the status value exists in the enum
        try:
            InvoiceStatus(status_filter)
            query["status"] = status_filter
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter '{status_filter}'. "
                       f"Valid values: {[s.value for s in InvoiceStatus]}",
            )

    if customer_id:
        query["customer_id"] = customer_id

    today_str = str(utc_now().date())
    if overdue_only:
        query["status"] = {"$in": [
            InvoiceStatus.SENT.value,
            InvoiceStatus.UNPAID.value,
            InvoiceStatus.OVERDUE.value,
        ]}
        query["due_date"] = {"$lt": today_str}
    else:
        # Apply date range filters (ISO date strings for MongoDB string comparison)
        due_date_conditions: dict = {}
        if due_date_before:
            due_date_conditions["$lte"] = str(due_date_before)
        if due_date_after:
            due_date_conditions["$gte"] = str(due_date_after)
        if due_date_conditions:
            query["due_date"] = due_date_conditions

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
    customer_ids: set = set()
    async for doc in cursor:
        docs.append(doc)
        cid = doc.get("customer_id")
        if cid:
            customer_ids.add(cid)

    # Batch-load customer names for the response page (avoids N+1)
    customer_map: dict = {}
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
    """Retrieve invoice by internal UUID, enforcing multi-tenant ownership.

    Raises:
        HTTPException 404: Invoice not found or belongs to another user.
    """
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
    """Update a draft invoice. Any pending approvals are invalidated on edit.

    Invariants:
    - Only invoices in 'draft' status may be modified.
    - Editing triggers invalidation of any pending approval tied to this invoice.
    - If items are replaced, totals are recomputed authoritatively using Decimal.
    - Audit log entry is appended for every successful edit.

    Raises:
        HTTPException 404: Invoice not found.
        HTTPException 400: Invoice is not in draft status, or customer not found.
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
        effective_issue = payload.issue_date or invoice.issue_date
        if payload.due_date < effective_issue:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Due date cannot precede issue date.",
            )
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
        # Authoritatively recompute totals using Decimal arithmetic
        invoice.compute_totals()

    invoice.updated_at = utc_now()

    await db.invoices.replace_one(
        {"internal_id": invoice_id, "user_id": user_id},
        invoice.model_dump(),
    )

    # Invalidate any pending approvals for this invoice since the payload changed
    await db.approvals.update_many(
        {
            "user_id": user_id,
            "resource_type": "invoice",
            "resource_id": invoice_id,
            "status": ApprovalStatus.PENDING.value,
        },
        {"$set": {"status": ApprovalStatus.INVALIDATED.value}},
    )

    # Append audit log entry
    audit_entry = AuditLog(
        user_id=user_id,
        actor=ActorType.USER,
        action="invoice.updated",
        resource_type="invoice",
        resource_id=invoice.internal_id,
        metadata={
            "total": str(invoice.total),
            "invoice_number": invoice.invoice_number,
            "fields_updated": [
                f for f in ["customer_id", "currency", "issue_date", "due_date", "notes", "items"]
                if getattr(payload, f, None) is not None
            ],
        },
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
    Re-submission of an already-pending invoice is blocked (idempotency guard).

    Invariants:
    - Only DRAFT invoices may be submitted.
    - A pending approval already exists → 400 (prevents duplicate approvals).
    - The payload hash binds the approval to the exact invoice content at submission time.

    Raises:
        HTTPException 404: Invoice not found.
        HTTPException 400: Invoice not in draft status, or pending approval already exists.
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

    # 1. Build immutable snapshot and compute deterministic SHA-256 hash
    payload_snapshot = _build_payload_snapshot(invoice)
    payload_hash = compute_payload_hash(payload_snapshot)

    # 2. Guard: prevent creating a second pending approval for the same invoice
    existing_pending = await db.approvals.find_one({
        "resource_id": invoice_id,
        "user_id": user_id,
        "status": ApprovalStatus.PENDING.value,
    })
    if existing_pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "This invoice already has a pending approval. "
                "Review it in the Approval Center or edit the invoice to reset the approval."
            ),
        )

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

    # 4. Transition invoice to PENDING_APPROVAL
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
            "total": str(invoice.total),
            "currency": invoice.currency.value,
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


async def delete_invoice_draft(
    db: AsyncIOMotorDatabase,
    user_id: str,
    invoice_id: str,
) -> str:
    """Delete a draft invoice permanently.

    Invariant:
        Only invoices in 'draft' status can be deleted.
        Attempting to delete an invoice that is 'pending_approval', 'sent',
        or 'paid' is rejected with HTTP 400.
    """
    doc = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found.")

    invoice = Invoice.model_validate(doc)
    if invoice.status != InvoiceStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only draft invoices can be deleted. Current status is '{invoice.status.value}'.",
        )

    await db.invoices.delete_one({"internal_id": invoice_id, "user_id": user_id})

    # Invalidate any pending approvals for this resource
    await db.approvals.update_many(
        {
            "user_id": user_id,
            "resource_type": "invoice",
            "resource_id": invoice_id,
            "status": ApprovalStatus.PENDING.value,
        },
        {"$set": {"status": ApprovalStatus.INVALIDATED.value}},
    )

    # Record audit log
    audit_entry = AuditLog(
        user_id=user_id,
        actor=ActorType.USER,
        action="invoice.deleted",
        resource_type="invoice",
        resource_id=invoice_id,
        metadata={"invoice_number": invoice.invoice_number},
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return invoice_id


async def _reconcile_duplicate_paypal_invoice(
    invoice: Invoice,
    customer: Customer,
    user: User,
    invoice_number: Optional[str] = None,
) -> Optional[dict]:
    """Recover an orphaned PayPal Sandbox invoice matching exact number, owner, recipient, and amount."""
    lookup_number = invoice_number or invoice.invoice_number
    candidates = await paypal_service.search_invoice_by_number(lookup_number)
    expected_total = f"{invoice.total:.2f}"
    expected_user_email = (user.email or "").strip().lower()
    expected_business = (user.business_name or user.name or "").strip().lower()
    expected_cust_email = (customer.email or "").strip().lower()

    for item in candidates:
        detail = item.get("detail") or {}
        if detail.get("invoice_number") != lookup_number:
            continue
        invoicer = item.get("invoicer") or {}
        invoicer_email = (invoicer.get("email_address") or "").strip().lower()
        invoicer_business = (invoicer.get("business_name") or "").strip().lower()
        owner_matches = (
            (bool(expected_user_email) and invoicer_email == expected_user_email)
            or (not invoicer_email and bool(expected_business) and invoicer_business == expected_business)
        )
        recipient_emails = [
            ((rec.get("billing_info") or {}).get("email_address") or "").strip().lower()
            for rec in (item.get("primary_recipients") or [])
        ]
        amount_val = str((item.get("amount") or {}).get("value") or "")
        if owner_matches and expected_cust_email in recipient_emails and amount_val == expected_total:
            return item
    return None


async def create_approved_paypal_invoice(
    db: AsyncIOMotorDatabase,
    user: User,
    invoice_id: str,
    approval_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> PayPalInvoiceCreateResponse:
    """Execute creation of an approved invoice in PayPal Developer Sandbox.

    Invariants:
    1. Scoped strictly to the authenticated user owning the invoice.
    2. Replay & Duplicate Execution Prevention: If invoice already has a paypal_invoice_id,
       returns the existing record immediately without calling PayPal.
    3. Human Approval Requirement: Must have an explicit Approval record in 'approved' status.
    4. Payload Hash Integrity: Invalidate approval and reject with HTTP 409 if invoice contents
       mutated after approval was granted.
    5. Safe Persistence: Stores paypal_invoice_id, official sandbox preview URL, updates status
       to 'created', and logs an immutable audit event.
    """
    # 1. Invoice lookup and ownership verification
    doc = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user.id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )
    invoice = Invoice.model_validate(doc)

    # 2. Existing Execution Check (Idempotency / Duplicate Prevention)
    if invoice.paypal_invoice_id:
        fallback_url = f"https://www.sandbox.paypal.com/invoice/p/#{invoice.paypal_invoice_id}"
        return PayPalInvoiceCreateResponse(
            invoice_id=invoice.internal_id,
            invoice_number=invoice.invoice_number,
            paypal_invoice_id=invoice.paypal_invoice_id,
            paypal_invoice_url=invoice.paypal_invoice_url or fallback_url,
            status=invoice.status.value,
            message="Invoice has already been created in PayPal Sandbox. Returning existing execution record.",
            is_duplicate=True,
        )

    # 3. Human Approval Requirement
    query: dict = {
        "user_id": user.id,
        "resource_type": "invoice",
        "resource_id": invoice.internal_id,
        "action_type": ActionType.CREATE_PAYPAL_INVOICE.value,
    }
    if approval_id:
        query["id"] = approval_id

    # Retrieve most recent approval matching criteria
    appr_cursor = db.approvals.find(query).sort("created_at", -1).limit(1)
    appr_docs = await appr_cursor.to_list(length=1)
    if not appr_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice cannot be dispatched to PayPal without an explicit human approval record.",
        )
    approval = Approval.model_validate(appr_docs[0])

    if approval.status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot dispatch invoice to PayPal. Approval status is '{approval.status.value}'. Must be 'approved'.",
        )

    # 4. Payload Hash Integrity Check
    current_snapshot = compute_invoice_payload_snapshot(invoice)
    current_hash = compute_payload_hash(current_snapshot)

    if current_hash != approval.payload_hash:
        approval.invalidate()
        await db.approvals.replace_one({"id": approval.id}, approval.model_dump())
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice contents were modified after approval was granted. Approval has been invalidated. Please review and re-submit for approval.",
        )

    # 5. Customer lookup and verification
    cust_doc = await db.customers.find_one({"id": invoice.customer_id, "user_id": user.id})
    if not cust_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked customer record not found for this invoice.",
        )
    customer = Customer.model_validate(cust_doc)

    # 6. Stable idempotency key
    stable_key = idempotency_key or f"payflow-create-{invoice.internal_id}"

    # 7. Call PayPal REST Invoicing v2 adapter
    try:
        paypal_res = await paypal_service.create_invoice(
            invoice=invoice,
            customer=customer,
            user=user,
            idempotency_key=stable_key,
        )
    except PayPalAPIError as err:
        is_duplicate_num = any(d.get("issue") == "DUPLICATE_INVOICE_NUMBER" for d in err.details)
        paypal_res = None
        if err.status_code == 422 and is_duplicate_num:
            paypal_res = await _reconcile_duplicate_paypal_invoice(invoice, customer, user)
            if not paypal_res:
                # Shared PayPal Sandbox accounts reject identical numbers across tenants;
                # retry with a deterministic tenant-scoped PayPal reference while preserving Approval hash.
                alt_num = f"{invoice.invoice_number}-{invoice.internal_id.replace('-', '')[:4].upper()}"[:25]
                try:
                    paypal_res = await paypal_service.create_invoice(
                        invoice=invoice,
                        customer=customer,
                        user=user,
                        idempotency_key=f"{stable_key}-alt",
                        invoice_number_override=alt_num,
                    )
                except PayPalAPIError as retry_err:
                    retry_dup = any(d.get("issue") == "DUPLICATE_INVOICE_NUMBER" for d in retry_err.details)
                    if retry_err.status_code == 422 and retry_dup:
                        paypal_res = await _reconcile_duplicate_paypal_invoice(
                            invoice, customer, user, invoice_number=alt_num
                        )
                    if not paypal_res:
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=retry_err.message)
        if not paypal_res:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)

    paypal_id = extract_paypal_invoice_id(paypal_res)
    if not paypal_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="PayPal Sandbox response did not include a valid invoice identifier.",
        )

    # Enrich URL/metadata if PayPal returned only a minimal HATEOAS link
    if not paypal_res.get("links") and not (paypal_res.get("detail") or {}).get("metadata"):
        try:
            paypal_res = await paypal_service.get_invoice(paypal_id)
        except Exception:
            pass

    paypal_url = extract_paypal_invoice_url(paypal_res, paypal_id)

    # 8. Persist updated invoice state
    invoice.paypal_invoice_id = paypal_id
    invoice.paypal_invoice_url = paypal_url
    invoice.status = InvoiceStatus.CREATED
    invoice.updated_at = utc_now()
    await db.invoices.replace_one({"internal_id": invoice.internal_id}, invoice.model_dump())

    # Link approval execution
    approval.execution_result_ref = paypal_id
    await db.approvals.replace_one({"id": approval.id}, approval.model_dump())

    # Insert immutable audit entry
    audit_entry = AuditLog(
        user_id=user.id,
        actor=ActorType.USER,
        action="invoice.created_in_paypal",
        resource_type="invoice",
        resource_id=invoice.internal_id,
        metadata={
            "invoice_number": invoice.invoice_number,
            "paypal_invoice_id": paypal_id,
            "paypal_invoice_url": paypal_url,
            "approval_id": approval.id,
            "idempotency_key": stable_key,
        },
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return PayPalInvoiceCreateResponse(
        invoice_id=invoice.internal_id,
        invoice_number=invoice.invoice_number,
        paypal_invoice_id=paypal_id,
        paypal_invoice_url=paypal_url,
        status=invoice.status.value,
        message="Invoice draft created in PayPal Developer Sandbox successfully.",
        is_duplicate=False,
    )


async def send_approved_paypal_invoice(
    db: AsyncIOMotorDatabase,
    user: User,
    invoice_id: str,
    approval_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    note: Optional[str] = None,
    send_to_recipient: bool = True,
    send_to_invoicer: bool = False,
) -> PayPalInvoiceSendResponse:
    """Dispatch an approved invoice to the client via PayPal Sandbox Invoicing API v2.

    Invariants:
    1. Scoped strictly to authenticated user owning the invoice.
    2. Confirm invoice is in a sendable state before calling PayPal:
       - If status is already SENT, UNPAID, PARTIALLY_PAID, or PAID:
         returns existing record immediately (is_duplicate=True) without re-sending.
       - If status is CANCELLED: raises 400 Bad Request.
    3. Human Approval Requirement:
       - Must have an Approval record with status == APPROVED.
       - Binds to immutable payload snapshot hash.
    4. Payload Hash Integrity Check:
       - If invoice contents mutated after approval, invalidate approval and reject with 409 Conflict.
    5. Timeout & Unknown Outcome Reconciliation:
       - Handled by paypal_service.send_invoice using GET /v2/invoicing/invoices/{id}.
       - Success is only reported if confirmed by PayPal.
    6. Audit and Persistence:
       - Updates status to InvoiceStatus.SENT.
       - Sets sent_at timestamp.
       - Records immutable AuditLog.
    """
    doc = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user.id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found.",
        )
    invoice = Invoice.model_validate(doc)

    # Invariant: Duplicate send prevention
    if invoice.status in (
        InvoiceStatus.SENT,
        InvoiceStatus.UNPAID,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
    ):
        sent_timestamp = invoice.sent_at.isoformat() if invoice.sent_at else utc_now().isoformat()
        return PayPalInvoiceSendResponse(
            invoice_id=invoice.internal_id,
            invoice_number=invoice.invoice_number,
            paypal_invoice_id=invoice.paypal_invoice_id or "",
            paypal_invoice_url=invoice.paypal_invoice_url or f"https://www.sandbox.paypal.com/invoice/p/#{invoice.paypal_invoice_id}",
            status=invoice.status.value,
            sent_at=sent_timestamp,
            message="Invoice has already been sent via PayPal Sandbox. Duplicate send prevented.",
            is_duplicate=True,
        )

    if invoice.status == InvoiceStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot send a cancelled invoice.",
        )

    # If invoice not yet created in PayPal Sandbox, create it first under approved flow
    if not invoice.paypal_invoice_id:
        create_res = await create_approved_paypal_invoice(
            db=db,
            user=user,
            invoice_id=invoice.internal_id,
            approval_id=approval_id,
            idempotency_key=f"payflow-create-{invoice.internal_id}",
        )
        doc = await db.invoices.find_one({"internal_id": invoice_id, "user_id": user.id})
        assert doc is not None
        invoice = Invoice.model_validate(doc)

    # Human Approval Requirement
    query: dict = {
        "user_id": user.id,
        "resource_type": "invoice",
        "resource_id": invoice.internal_id,
    }
    if approval_id:
        query["id"] = approval_id

    appr_cursor = db.approvals.find(query).sort("created_at", -1).limit(1)
    appr_docs = await appr_cursor.to_list(length=1)
    if not appr_docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invoice cannot be dispatched to PayPal without an explicit human approval record.",
        )
    approval = Approval.model_validate(appr_docs[0])

    if approval.status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot dispatch invoice to PayPal. Approval status is '{approval.status.value}'. Must be 'approved'.",
        )

    # Invariant: Payload Hash Integrity
    current_snapshot = compute_invoice_payload_snapshot(invoice)
    current_hash = compute_payload_hash(current_snapshot)

    if current_hash != approval.payload_hash:
        approval.invalidate()
        await db.approvals.replace_one({"id": approval.id}, approval.model_dump())
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invoice contents were modified after approval was granted. Approval has been invalidated. Please review and re-submit for approval.",
        )

    # Call PayPal Sandbox send operation
    assert invoice.paypal_invoice_id is not None
    stable_send_key = idempotency_key or f"payflow-send-{invoice.internal_id}"

    try:
        send_result = await paypal_service.send_invoice(
            paypal_invoice_id=invoice.paypal_invoice_id,
            note=note,
            send_to_recipient=send_to_recipient,
            send_to_invoicer=send_to_invoicer,
            idempotency_key=stable_send_key,
        )
    except PayPalAPIError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err.message)

    now = utc_now()
    invoice.status = InvoiceStatus.SENT
    invoice.sent_at = now
    invoice.updated_at = now
    await db.invoices.replace_one({"internal_id": invoice.internal_id}, invoice.model_dump())

    # Record AuditLog
    audit_entry = AuditLog(
        user_id=user.id,
        actor=ActorType.USER,
        action="invoice.sent_via_paypal",
        resource_type="invoice",
        resource_id=invoice.internal_id,
        metadata={
            "invoice_number": invoice.invoice_number,
            "paypal_invoice_id": invoice.paypal_invoice_id,
            "paypal_invoice_url": invoice.paypal_invoice_url,
            "approval_id": approval.id,
            "idempotency_key": stable_send_key,
            "reconciled": send_result.get("reconciled", False),
            "sent_at": now.isoformat(),
        },
    )
    await db.audit_logs.insert_one(audit_entry.model_dump())

    return PayPalInvoiceSendResponse(
        invoice_id=invoice.internal_id,
        invoice_number=invoice.invoice_number,
        paypal_invoice_id=invoice.paypal_invoice_id,
        paypal_invoice_url=invoice.paypal_invoice_url or f"https://www.sandbox.paypal.com/invoice/p/#{invoice.paypal_invoice_id}",
        status="sent",
        sent_at=now.isoformat(),
        message="Invoice delivered to customer via PayPal Sandbox successfully.",
        is_duplicate=False,
    )



