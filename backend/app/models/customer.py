"""Customer domain model."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
import uuid


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BillingAddress(BaseModel):
    """Minimal customer billing address required for PayPal invoicing."""

    address_line_1: Optional[str] = Field(default=None, max_length=150)
    address_line_2: Optional[str] = Field(default=None, max_length=150)
    city: Optional[str] = Field(default=None, max_length=80)
    state: Optional[str] = Field(default=None, max_length=80)
    postal_code: Optional[str] = Field(default=None, max_length=30)
    country_code: str = Field(default="US", min_length=2, max_length=2, description="2-letter ISO country code")


class Customer(BaseModel):
    """Customer entity scoped strictly to the authenticated user."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="Owner user_id scoping this record")
    name: str = Field(..., min_length=1, max_length=120, description="Contact person or client name")
    email: EmailStr = Field(..., description="Customer billing/contact email")
    company: Optional[str] = Field(default=None, max_length=120)
    billing_address: Optional[BillingAddress] = None
    notes: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    is_active: bool = True
