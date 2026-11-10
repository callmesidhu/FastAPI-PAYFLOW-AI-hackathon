"""Customer API request, response, and pagination schemas."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.customer import BillingAddress


class CustomerCreate(BaseModel):
    """Customer creation request schema."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Sarah Connor",
                "email": "sarah.connor@example.com",
                "company": "Cyberdyne Systems",
                "billing_address": {
                    "address_line_1": "100 Tech Blvd",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "country_code": "US",
                },
                "notes": "Preferred payment schedule: Net-7",
            }
        }
    )

    name: str = Field(..., min_length=1, max_length=120, description="Full name or company representative")
    email: EmailStr = Field(..., description="Customer billing email")
    company: Optional[str] = Field(default=None, max_length=120, description="Optional business entity name")
    billing_address: Optional[BillingAddress] = None
    notes: Optional[str] = Field(default=None, max_length=500, description="Internal billing notes")


class CustomerUpdate(BaseModel):
    """Customer update request schema allowing partial modifications."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Sarah Connor",
                "company": "Cyberdyne Systems Corporation",
                "notes": "Updated billing terms to Net-14",
            }
        }
    )

    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    email: Optional[EmailStr] = None
    company: Optional[str] = Field(default=None, max_length=120)
    billing_address: Optional[BillingAddress] = None
    notes: Optional[str] = Field(default=None, max_length=500)


class CustomerResponse(BaseModel):
    """Customer representation response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    email: EmailStr
    company: Optional[str] = None
    billing_address: Optional[BillingAddress] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool


class CustomerListResponse(BaseModel):
    """Paginated list of customer records."""

    items: List[CustomerResponse]
    total: int
    page: int
    page_size: int
    pages: int
