"""Customer management service enforcing user isolation, deduplication, and invoice protection."""

import math
from typing import Optional
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.models.customer import Customer, utc_now
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate


async def create_customer(
    db: AsyncIOMotorDatabase,
    user_id: str,
    payload: CustomerCreate,
) -> Customer:
    """Create a new customer strictly scoped to the authenticated user.

    Raises:
        HTTPException: If a customer with the same email already exists for this user.
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
    return customer


async def list_customers(
    db: AsyncIOMotorDatabase,
    user_id: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
) -> CustomerListResponse:
    """List customers scoped to the user with pagination and name/email search."""
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    query: dict = {"user_id": user_id, "is_active": True}

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

    # Stable descending sort by creation timestamp
    cursor = db.customers.find(query).sort("created_at", -1).skip(skip).limit(page_size)
    items = []
    async for doc in cursor:
        items.append(CustomerResponse.model_validate(doc))

    return CustomerListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


async def get_customer_by_id(
    db: AsyncIOMotorDatabase,
    user_id: str,
    customer_id: str,
) -> Customer:
    """Retrieve customer by internal ID, enforcing user ownership."""
    doc = await db.customers.find_one({
        "id": customer_id,
        "user_id": user_id,
        "is_active": True,
    })
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found.",
        )
    return Customer.model_validate(doc)


async def update_customer(
    db: AsyncIOMotorDatabase,
    user_id: str,
    customer_id: str,
    payload: CustomerUpdate,
) -> Customer:
    """Update customer details with deduplication and ownership verification."""
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
            # Check for conflict with another customer of the same user
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
    return customer


async def delete_customer(
    db: AsyncIOMotorDatabase,
    user_id: str,
    customer_id: str,
) -> None:
    """Safely delete or archive a customer.

    Invariant:
        A customer with linked invoices cannot be destructively removed.
        Any active or historic invoice association blocks hard deletion and
        preserves the audit trail.
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

    # Invariant check: Check if customer has linked invoices
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

    # Use archive flag to preserve references safely
    await db.customers.update_one(
        {"id": customer_id, "user_id": user_id},
        {"$set": {"is_active": False, "updated_at": utc_now()}},
    )
