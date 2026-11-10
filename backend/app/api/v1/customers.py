"""Customer management API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.customer import CustomerCreate, CustomerListResponse, CustomerResponse, CustomerUpdate
from app.services import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Customer",
    description="Add a new customer scoped strictly to the authenticated user.",
)
async def create_customer(
    payload: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerResponse:
    customer = await customer_service.create_customer(db, current_user.id, payload)
    return CustomerResponse.model_validate(customer)


@router.get(
    "",
    response_model=CustomerListResponse,
    summary="List Customers",
    description="Retrieve paginated customer records with optional name or email search.",
)
async def list_customers(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Records per page"),
    q: Optional[str] = Query(default=None, description="Search term matching name, email, or company"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerListResponse:
    return await customer_service.list_customers(
        db=db,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        search=q,
    )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get Customer",
    description="Retrieve specific customer details by internal ID.",
)
async def get_customer(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerResponse:
    customer = await customer_service.get_customer_by_id(db, current_user.id, customer_id)
    return CustomerResponse.model_validate(customer)


@router.patch(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update Customer",
    description="Partially update customer information with deduplication safety.",
)
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> CustomerResponse:
    customer = await customer_service.update_customer(db, current_user.id, customer_id, payload)
    return CustomerResponse.model_validate(customer)


@router.delete(
    "/{customer_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete / Archive Customer",
    description="Safely archive customer. Blocks deletion if customer has linked invoices.",
)
async def delete_customer(
    customer_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    await customer_service.delete_customer(db, current_user.id, customer_id)
    return {"message": "Customer archived successfully.", "id": customer_id}
