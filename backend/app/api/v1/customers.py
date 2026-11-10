"""Customer management API endpoints.

All endpoints are scoped strictly to the authenticated user. The ``user_id``
used for every database query is extracted from the cryptographically verified
JWT — never trusted from request bodies or query parameters.

No PayPal credentials, card numbers, or bank details are accepted or returned
by any endpoint in this module.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.customer import (
    CustomerArchiveResponse,
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerSortField,
    CustomerUpdate,
    SortOrder,
)
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Customer",
    description=(
        "Add a new customer record scoped strictly to the authenticated user. "
        "Duplicate active customer emails per user are rejected with HTTP 400. "
        "No card, bank, or PayPal credential fields are accepted."
    ),
)
async def create_customer(
    payload: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerResponse:
    return await customer_service.create_customer(db, current_user.id, payload)


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List Customers",
    description=(
        "Retrieve a paginated, sorted list of customer records owned by the authenticated user. "
        "Supports case-insensitive substring search across name, email, and company fields. "
        "By default only active (non-archived) customers are returned; set ``include_archived=true`` "
        "to include soft-deleted records. Sorting is stable: a secondary sort on ``id`` breaks ties."
    ),
)
async def list_customers(
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)."),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page (max 100)."),
    q: Optional[str] = Query(
        default=None,
        description="Search term. Case-insensitive substring match against name, email, and company.",
    ),
    sort_by: CustomerSortField = Query(
        default=CustomerSortField.created_at,
        description="Field to sort results by.",
    ),
    sort_order: SortOrder = Query(
        default=SortOrder.desc,
        description="Sort direction: 'asc' or 'desc'.",
    ),
    include_archived: bool = Query(
        default=False,
        description="Include archived (soft-deleted) customers in results.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerListResponse:
    return await customer_service.list_customers(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        search=q,
        sort_by=sort_by,
        sort_order=sort_order,
        include_archived=include_archived,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get Customer",
    description=(
        "Retrieve a specific customer by its internal UUID. "
        "Returns HTTP 404 if the customer does not exist or belongs to another user. "
        "Active customers only by default; use ``include_archived=true`` to retrieve archived records."
    ),
)
async def get_customer(
    customer_id: str,
    include_archived: bool = Query(
        default=False,
        description="Allow retrieving archived (soft-deleted) customers.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerResponse:
    return await customer_service.get_customer_by_id(
        db, current_user.id, customer_id, include_archived=include_archived
    )


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update Customer",
    description=(
        "Partially update customer information. Only provided fields are modified. "
        "Email changes trigger duplicate-email validation. "
        "Only active (non-archived) customers may be updated."
    ),
)
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerResponse:
    return await customer_service.update_customer(db, current_user.id, customer_id, payload)


@router.delete(
    "/{customer_id}",
    response_model=CustomerArchiveResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive Customer",
    description=(
        "Soft-delete (archive) a customer by setting ``is_active=false``. "
        "Hard deletion is blocked if the customer has any linked invoices — "
        "this preserves financial history and audit integrity. "
        "Archived customers remain readable via ``include_archived=true`` but are "
        "excluded from active lists by default."
    ),
)
async def delete_customer(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerArchiveResponse:
    archived_id = await customer_service.delete_customer(db, current_user.id, customer_id)
    return CustomerArchiveResponse(
        message="Customer archived successfully.",
        id=archived_id,
        is_active=False,
    )
