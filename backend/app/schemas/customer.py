"""Customer API request, response, and pagination schemas.

Provides strictly typed, frontend-ready Pydantic v2 models for all customer
management operations. No PayPal credentials or card/bank data are ever stored
or returned through these schemas.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.customer import BillingAddress


# ---------------------------------------------------------------------------
# Enum helpers (exposed so OpenAPI documents valid values)
# ---------------------------------------------------------------------------

class CustomerSortField(str, Enum):
    """Stable, indexed sort fields for customer list queries."""

    name = "name"
    email = "email"
    company = "company"
    created_at = "created_at"
    updated_at = "updated_at"


class SortOrder(str, Enum):
    """Sort direction."""

    asc = "asc"
    desc = "desc"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CustomerCreate(BaseModel):
    """Customer creation request schema.

    Only safe, non-sensitive billing fields are accepted. Card numbers, bank
    account details, and PayPal credentials are never accepted or stored here.
    """

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

    name: str = Field(
        ...,
        min_length=1,
        max_length=120,
        description="Full name or company representative. Used as the recipient name on PayPal invoices.",
    )
    email: EmailStr = Field(
        ...,
        description=(
            "Customer billing contact email. Must be a valid RFC-5322 address. "
            "Duplicate emails per user are rejected. "
            "Used as the PayPal invoice recipient address."
        ),
    )
    company: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Optional business / legal entity name. Surfaced on invoice headers.",
    )
    billing_address: Optional[BillingAddress] = Field(
        default=None,
        description=(
            "Postal billing address forwarded to PayPal invoice creation. "
            "All sub-fields are optional except country_code."
        ),
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Internal billing notes visible only to the authenticated user. Never sent to customers.",
    )


class CustomerUpdate(BaseModel):
    """Customer partial-update request schema.

    All fields are optional; only provided fields are mutated. Duplicate-email
    protection runs even on partial updates.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Sarah Connor",
                "company": "Cyberdyne Systems Corporation",
                "notes": "Updated billing terms to Net-14",
            }
        }
    )

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=120,
        description="Updated contact name.",
    )
    email: Optional[EmailStr] = Field(
        default=None,
        description="Updated billing email. Triggers duplicate-email check for the current user.",
    )
    company: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Updated business entity name.",
    )
    billing_address: Optional[BillingAddress] = Field(
        default=None,
        description="Replacement billing address. Sending null clears the address.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Replacement internal notes. Sending null clears notes.",
    )


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class BillingAddressResponse(BaseModel):
    """Read-only billing address representation."""

    model_config = ConfigDict(from_attributes=True)

    address_line_1: Optional[str] = Field(default=None, description="Street address line 1.")
    address_line_2: Optional[str] = Field(default=None, description="Street address line 2 / suite / floor.")
    city: Optional[str] = Field(default=None, description="City or locality.")
    state: Optional[str] = Field(default=None, description="State, province, or region.")
    postal_code: Optional[str] = Field(default=None, description="Postal / ZIP code.")
    country_code: str = Field(description="2-letter ISO 3166-1 alpha-2 country code (e.g. 'US', 'GB').")


class CustomerResponse(BaseModel):
    """Full customer representation returned by all read endpoints.

    Security guarantees:
    - No PayPal credentials are included.
    - No card or bank account numbers are included.
    - ``user_id`` is returned only to the authenticated owner via enforced
      JWT scope; never exposed to other users.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Stable internal customer UUID.")
    user_id: str = Field(description="Owner user ID. Always matches the authenticated caller.")
    name: str = Field(description="Customer contact name.")
    email: EmailStr = Field(description="Customer billing email.")
    company: Optional[str] = Field(default=None, description="Business entity name.")
    billing_address: Optional[BillingAddressResponse] = Field(
        default=None,
        description="Postal billing address forwarded to PayPal invoices.",
    )
    notes: Optional[str] = Field(default=None, description="Internal billing notes (owner-only).")
    is_active: bool = Field(
        description=(
            "Archive flag. ``true`` = active customer. ``false`` = archived. "
            "Archived customers remain readable but hidden from active lists."
        )
    )
    invoice_count: int = Field(
        default=0,
        description=(
            "Total number of invoices linked to this customer (all statuses). "
            "Non-zero value means deletion is blocked; archiving is used instead."
        ),
    )
    created_at: datetime = Field(description="UTC timestamp of record creation.")
    updated_at: datetime = Field(description="UTC timestamp of last modification.")


class CustomerArchiveResponse(BaseModel):
    """Response returned by the DELETE (archive) endpoint."""

    message: str = Field(description="Human-readable confirmation message.")
    id: str = Field(description="Archived customer ID.")
    is_active: bool = Field(
        default=False,
        description="Archive state after the operation. Always ``false`` after a successful archive.",
    )


class CustomerListResponse(BaseModel):
    """Paginated, sorted list of customer records.

    Designed for frontend table/grid rendering with stable cursor information.
    """

    items: List[CustomerResponse] = Field(description="Customer records for the current page.")
    total: int = Field(description="Total matching records across all pages.")
    page: int = Field(description="Current page number (1-indexed).")
    page_size: int = Field(description="Number of records per page.")
    pages: int = Field(description="Total number of pages for the current query.")
    sort_by: str = Field(
        default="created_at",
        description="Field used for sorting.",
    )
    sort_order: str = Field(
        default="desc",
        description="Sort direction: 'asc' or 'desc'.",
    )
