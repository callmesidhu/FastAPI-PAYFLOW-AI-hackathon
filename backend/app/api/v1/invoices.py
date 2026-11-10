"""Invoice management API endpoints.

All endpoints are scoped strictly to the authenticated user. ``user_id`` for
every database query comes from the cryptographically verified JWT, never from
request bodies or query parameters.

Financial invariants:
- Server-side Decimal arithmetic is authoritative for all totals.
- Client-supplied total previews are accepted but silently discarded.
- Only DRAFT invoices may be edited or re-submitted for approval.
"""

from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.audit import InvoiceTimelineResponse
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceDeleteResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    SubmitForApprovalResponse,
)
from app.services import invoice_service
from app.services.audit_service import AuditService

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Invoice",
    description=(
        "Create a new invoice in DRAFT status. "
        "Subtotals and totals are authoritatively computed server-side from line items using Decimal arithmetic. "
        "Any client-supplied ``client_total_preview`` is silently discarded. "
        "Invoice number is auto-generated (INV-YYYY-NNNN) if not provided. "
        "Customer must belong to the authenticated user."
    ),
)
async def create_invoice(
    payload: InvoiceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceResponse:
    invoice = await invoice_service.create_invoice_draft(db, current_user.id, payload)
    return InvoiceResponse.model_validate(invoice)


@router.get(
    "",
    response_model=InvoiceListResponse,
    summary="List Invoices",
    description=(
        "Retrieve paginated invoices owned by the authenticated user. "
        "Supports filtering by status, customer, due date range, and overdue state. "
        "Case-insensitive search matches invoice_number, notes, and line item names. "
        "Results are sorted by creation date descending (newest first)."
    ),
)
async def list_invoices(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page (max 100)."),
    status: Optional[str] = Query(
        default=None,
        description=(
            "Filter by exact invoice status. "
            "Valid values: draft, pending_approval, created, sent, unpaid, "
            "partially_paid, paid, overdue, cancelled, failed."
        ),
    ),
    customer_id: Optional[str] = Query(
        default=None,
        description="Filter to invoices for a specific customer UUID.",
    ),
    overdue: bool = Query(
        default=False,
        description=(
            "When true, return only sent/unpaid/overdue invoices past their due date. "
            "Cannot be combined with ``due_date_before`` / ``due_date_after``."
        ),
    ),
    due_date_before: Optional[date] = Query(
        default=None,
        description="Return only invoices with due_date on or before this date (YYYY-MM-DD).",
    ),
    due_date_after: Optional[date] = Query(
        default=None,
        description="Return only invoices with due_date on or after this date (YYYY-MM-DD).",
    ),
    q: Optional[str] = Query(
        default=None,
        description="Case-insensitive search term matched against invoice_number, notes, and item names.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceListResponse:
    return await invoice_service.list_invoices(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        status_filter=status,
        customer_id=customer_id,
        overdue_only=overdue,
        search=q,
        due_date_before=due_date_before,
        due_date_after=due_date_after,
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get Invoice Detail",
    description=(
        "Retrieve a specific invoice by its internal UUID. "
        "Returns HTTP 404 if the invoice does not exist or belongs to another user. "
        "``customer_name`` is enriched from the customers collection."
    ),
)
async def get_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceResponse:
    invoice = await invoice_service.get_invoice_by_id(db, current_user.id, invoice_id)
    resp = InvoiceResponse.model_validate(invoice)
    customer = await db.customers.find_one({"id": invoice.customer_id, "user_id": current_user.id})
    if customer:
        resp.customer_name = customer.get("name")
    return resp


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Edit Draft Invoice",
    description=(
        "Update a draft invoice. "
        "Invariant: Only invoices in 'draft' status may be edited — HTTP 400 otherwise. "
        "When ``items`` is provided, all line items are replaced and totals are recomputed server-side. "
        "Any pending approvals tied to this invoice are automatically invalidated on edit."
    ),
)
async def update_invoice(
    invoice_id: str,
    payload: InvoiceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceResponse:
    invoice = await invoice_service.update_invoice_draft(db, current_user.id, invoice_id, payload)
    return InvoiceResponse.model_validate(invoice)


@router.post(
    "/{invoice_id}/submit-for-approval",
    response_model=SubmitForApprovalResponse,
    summary="Submit Draft for Human Approval",
    description=(
        "Transition a DRAFT invoice to PENDING_APPROVAL and create an immutable Approval record. "
        "The ``payload_hash`` cryptographically binds the approval to the exact invoice state. "
        "Editing the invoice after submission invalidates the approval. "
        "Re-submitting an invoice that already has a pending approval is blocked (HTTP 400). "
        "PayPal execution does NOT occur here — it requires explicit approval in the Approval Center."
    ),
)
async def submit_for_approval(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SubmitForApprovalResponse:
    return await invoice_service.submit_invoice_for_approval(db, current_user.id, invoice_id)


@router.get(
    "/{invoice_id}/timeline",
    response_model=InvoiceTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Invoice Activity Timeline",
    description=(
        "Retrieve the chronological append-only audit trail and lifecycle events for a specific invoice. "
        "Strictly scoped to the authenticated user."
    ),
)
async def get_invoice_timeline(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceTimelineResponse:
    try:
        return await AuditService.get_invoice_timeline(
            db=db,
            user_id=current_user.id,
            invoice_id=invoice_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{invoice_id}",
    response_model=InvoiceDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete Draft Invoice",
    description="Permanently delete a draft invoice. Invariant: Only drafts can be deleted.",
)
async def delete_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> InvoiceDeleteResponse:
    deleted_id = await invoice_service.delete_invoice_draft(db, current_user.id, invoice_id)
    return InvoiceDeleteResponse(
        message="Draft invoice deleted successfully.",
        id=deleted_id,
    )

