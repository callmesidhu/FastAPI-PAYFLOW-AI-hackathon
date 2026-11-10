"""Customer management service enforcing user isolation, deduplication, and invoice protection.

Security invariants:
- Every database query is filtered by ``user_id`` extracted from the verified JWT.
- Duplicate active customer emails per user are rejected at the service layer.
- Customers with linked invoices cannot be hard-deleted; archiving is used instead.
- No PayPal credentials or card/bank data are stored or returned.
"""

import math
from typing import Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.customer import Customer, utc_now
from app.schemas.customer import (
    CustomerCreate,
    CustomerListResponse,
    CustomerResponse,
    CustomerSortField,
    CustomerUpdate,
    SortOrder,
)

# Mapping from sort field enum value to MongoDB document field name
_SORT_FIELD_MAP: dict[str, str] = {
    CustomerSortField.name: "name",
    CustomerSortField.email: "email",
    CustomerSortField.company: "company",
    CustomerSortField.created_at: "created_at",
    CustomerSortField.updated_at: "updated_at",
}


async def _get_invoice_count(db: AsyncIOMotorDatabase, customer_id: str, user_id: str) -> int:
    """Return the total number of invoices linked to this customer for the given user."""
    return await db.invoices.count_documents({"customer_id": customer_id, "user_id": user_id})


async def _build_customer_response(
    db: AsyncIOMotorDatabase,
    customer: Customer,
) -> CustomerResponse:
    """Build a CustomerResponse with computed invoice_count."""
    invoice_count = await _get_invoice_count(db, customer.id, customer.user_id)
    data = customer.model_dump()
    data["invoice_count"] = invoice_count
    # Ensure billing_address dict maps correctly
    return CustomerResponse.model_validate(data)


async def create_customer(
    db: AsyncIOMotorDatabase,
    user_id: str,
    payload: CustomerCreate,
) -> CustomerResponse:
    """Create a new customer strictly scoped to the authenticated user.

    Raises:
        HTTPException 400: If a customer with the same email already exists for this user.
    """
    normalized_email = payload.email.lower().strip()

    # Prevent duplicate active customer records for the same user
    existing = await db.customers.find_one({
        "user_id": user_id,
        "email": normalized_email,
        "is_active": True,
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"A customer with email '{normalized_email}' already exists.",
        )

    customer = Customer(
        user_id=user_id,
        name=payload.name.strip(),
        email=normalized_email,
        company=payload.company.strip() if payload.company else None,
        billing_address=payload.billing_address,
        notes=payload.notes.strip() if payload.notes else None,
    )

    await db.customers.insert_one(customer.model_dump())
    return await _build_customer_response(db, customer)


async def list_customers(
    db: AsyncIOMotorDatabase,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    sort_by: str = CustomerSortField.created_at,
    sort_order: str = SortOrder.desc,
    include_archived: bool = False,
) -> CustomerListResponse:
    """List customers scoped to the user with pagination, search, and stable sorting.

    Args:
        db: Async MongoDB database handle.
        user_id: Authenticated caller's ID (never trusted from request body).
        page: 1-indexed page number.
        page_size: Records per page (clamped to 1–100).
        search: Optional substring search across name, email, and company fields (case-insensitive).
        sort_by: Field to sort by. Defaults to 'created_at'.
        sort_order: 'asc' or 'desc'. Defaults to 'desc'.
        include_archived: If True, include soft-deleted (is_active=False) records.
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    query: dict = {"user_id": user_id}
    if not include_archived:
        query["is_active"] = True

    if search:
        search_regex = {"$regex": search.strip(), "$options": "i"}
        query["$or"] = [
            {"name": search_regex},
            {"email": search_regex},
            {"company": search_regex},
        ]

    total = await db.customers.count_documents(query)
    pages = math.ceil(total / page_size) if total > 0 else 1
    skip = (page - 1) * page_size

    # Resolve sort field to MongoDB document field; fall back to created_at for safety
    mongo_sort_field = _SORT_FIELD_MAP.get(sort_by, "created_at")
    mongo_sort_direction = -1 if sort_order == SortOrder.desc else 1

    # Stable secondary sort: always append _id ascending to break ties deterministically
    cursor = (
        db.customers.find(query)
        .sort([(mongo_sort_field, mongo_sort_direction), ("id", 1)])
        .skip(skip)
        .limit(page_size)
    )

    items = []
    async for doc in cursor:
        customer = Customer.model_validate(doc)
        items.append(await _build_customer_response(db, customer))

    return CustomerListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        sort_by=sort_by,
        sort_order=sort_order,
    )


async def get_customer_by_id(
    db: AsyncIOMotorDatabase,
    user_id: str,
    customer_id: str,
    include_archived: bool = False,
) -> CustomerResponse:
    """Retrieve customer by internal ID, enforcing user ownership.

    Args:
        include_archived: If True, also return archived (is_active=False) customers.

    Raises:
        HTTPException 404: If the customer does not exist or belongs to another user.
    """
    query: dict = {"id": customer_id, "user_id": user_id}
    if not include_archived:
        query["is_active"] = True

    doc = await db.customers.find_one(query)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    customer = Customer.model_validate(doc)
    return await _build_customer_response(db, customer)


async def update_customer(
    db: AsyncIOMotorDatabase,
    user_id: str,
    customer_id: str,
    payload: CustomerUpdate,
) -> CustomerResponse:
    """Update customer details with deduplication and ownership verification.

    Only active (non-archived) customers may be updated.

    Raises:
        HTTPException 404: Customer not found or archived.
        HTTPException 400: Email conflict with another customer of the same user.
    """
    existing_doc = await db.customers.find_one({
        "id": customer_id,
        "user_id": user_id,
        "is_active": True,
    })
    if not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    customer = Customer.model_validate(existing_doc)
    update_data = payload.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"]:
        new_email = update_data["email"].lower().strip()
        if new_email != customer.email:
            # Check for conflict with another active customer of the same user
            conflict = await db.customers.find_one({
                "user_id": user_id,
                "email": new_email,
                "is_active": True,
                "id": {"$ne": customer_id},
            })
            if conflict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"A customer with email '{new_email}' already exists.",
                )
            customer.email = new_email

    if "name" in update_data and update_data["name"]:
        customer.name = update_data["name"].strip()
    if "company" in update_data:
        customer.company = update_data["company"].strip() if update_data["company"] else None
    if "billing_address" in update_data:
        customer.billing_address = payload.billing_address
    if "notes" in update_data:
        customer.notes = update_data["notes"].strip() if update_data["notes"] else None

    customer.updated_at = utc_now()

    await db.customers.replace_one(
        {"id": customer_id, "user_id": user_id},
        customer.model_dump(),
    )
    return await _build_customer_response(db, customer)


async def delete_customer(
    db: AsyncIOMotorDatabase,
    user_id: str,
    customer_id: str,
) -> str:
    """Safely archive a customer using a soft-delete flag.

    Deletion invariant:
        A customer with **any** linked invoices (regardless of invoice status)
        cannot be hard-deleted. This preserves financial record integrity and
        audit trails. The record is instead marked ``is_active=False`` (archived)
        so it remains accessible to historical invoice views.

    Returns:
        The archived customer_id string.

    Raises:
        HTTPException 404: Customer not found or already archived.
        HTTPException 400: Customer has linked invoices and cannot be deleted.
    """
    existing_doc = await db.customers.find_one({
        "id": customer_id,
        "user_id": user_id,
        "is_active": True,
    })
    if not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )

    # Invariant check: block hard deletion if any invoices reference this customer
    linked_invoices_count = await db.invoices.count_documents({
        "customer_id": customer_id,
        "user_id": user_id,
    })

    if linked_invoices_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete customer. This customer is linked to {linked_invoices_count} "
                "invoice(s). Financial records must maintain historical integrity."
            ),
        )

    # Soft-delete: archive flag preserves references safely
    await db.customers.update_one(
        {"id": customer_id, "user_id": user_id},
        {"$set": {"is_active": False, "updated_at": utc_now()}},
    )
    return customer_id
