"""Invoice management API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.invoice import (
    InvoiceCreate,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceUpdate,
    SubmitForApprovalResponse,
)
from app.services import invoice_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Draft Invoice",
    description="Create an invoice draft. Subtotals and totals are authoritatively calculated server-side.",
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
    description="Retrieve paginated invoices filtered by status, customer, or overdue state.",
)
async def list_invoices(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page"),
    status: Optional[str] = Query(default=None, description="Filter by status (e.g., draft, sent, paid)"),
    customer_id: Optional[str] = Query(default=None, description="Filter by customer ID"),
    overdue: bool = Query(default=False, description="Filter only overdue invoices"),
    q: Optional[str] = Query(default=None, description="Search invoice numbers or line item descriptions"),
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
    )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Get Invoice Detail",
    description="Retrieve a specific invoice by its internal ID, verifying authenticated ownership.",
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
    description="Update an invoice. Invariant: Only invoices in 'draft' status may be edited.",
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
    summary="Submit Draft for Approval",
    description="Transition invoice from draft to pending_approval and create an immutable approval record.",
)
async def submit_for_approval(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> SubmitForApprovalResponse:
    return await invoice_service.submit_invoice_for_approval(db, current_user.id, invoice_id)
