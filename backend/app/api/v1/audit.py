"""Audit Trail and Financial Transaction Ledger API router (Prompt 24).

Architecture & Invariants:
- Represents an append-only-style audit log at the application layer.
- Strictly omits PUT, PATCH, and DELETE endpoints from the application API.
- All records are scoped to the authenticated user via verified JWT tokens.
- Sensitive credentials and keys are scrubbed before persistence.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.audit import AuditLogListResponse
from app.schemas.transaction import TransactionListResponse
from app.services.audit_service import AuditService

router = APIRouter(tags=["Audit & Ledger"])


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Audit Log Events",
    description=(
        "Retrieve append-only-style audit events scoped to the authenticated user. "
        "Secrets, tokens, and sensitive credentials are permanently scrubbed from metadata. "
        "Application layer strictly prohibits update or deletion of audit logs."
    ),
)
async def list_audit_logs(
    resource_type: Optional[str] = Query(None, description="Filter by resource type (e.g. invoice)"),
    resource_id: Optional[str] = Query(None, description="Filter by specific resource identifier"),
    action: Optional[str] = Query(None, description="Filter by action name (e.g. invoice.created)"),
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AuditLogListResponse:
    """List append-only audit trail entries for the authenticated merchant."""
    items = await AuditService.list_audit_logs(
        db=db,
        user_id=current_user.id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        limit=limit,
    )
    return AuditLogListResponse(total=len(items), items=items)


@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Financial Transactions",
    description=(
        "Retrieve authoritative ledger transaction records for settled PayPal payments scoped to the authenticated user. "
        "Application layer strictly prohibits update or deletion of financial transactions."
    ),
)
async def list_transactions(
    invoice_id: Optional[str] = Query(None, description="Filter transactions for specific invoice internal_id"),
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> TransactionListResponse:
    """List financial transaction records for the authenticated merchant."""
    items = await AuditService.list_transactions(
        db=db,
        user_id=current_user.id,
        invoice_id=invoice_id,
        limit=limit,
    )
    return TransactionListResponse(total=len(items), items=items)

