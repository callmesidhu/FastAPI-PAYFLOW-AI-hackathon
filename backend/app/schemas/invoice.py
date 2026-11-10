"""Pydantic schemas for Invoice requests, responses, updates, and approval submission.

All monetary amounts are serialized as 2-decimal strings (e.g. "475.00") using the
authoritative Python Decimal type. Client-supplied totals are accepted for display
convenience but are always overridden by the server-calculated values.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.models.enums import InvoiceStatus, SupportedCurrency
from app.models.money import MoneyDecimal


# ---------------------------------------------------------------------------
# Line items
# ---------------------------------------------------------------------------

class InvoiceItemCreate(BaseModel):
    """Line item for an invoice. All monetary fields use Decimal precision."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=140,
        description="Service or product name shown on the invoice line.",
        json_schema_extra={"example": "Website Design & Architecture"},
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional detailed description of the line item.",
        json_schema_extra={"example": "Sprint 1: UX design and backend API contract"},
    )
    quantity: Decimal = Field(
        default=Decimal("1.00"),
        ge=Decimal("0.01"),
        description="Quantity of units (must be > 0).",
        json_schema_extra={"example": "1.00"},
    )
    unit_price: MoneyDecimal = Field(
        ...,
        ge=Decimal("0.00"),
        description="Per-unit price in the invoice currency. Must be >= 0.",
        json_schema_extra={"example": "500.00"},
    )
    tax: MoneyDecimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        description="Tax amount for this line item in the invoice currency. Must be >= 0.",
        json_schema_extra={"example": "0.00"},
    )


class InvoiceItemResponse(BaseModel):
    """Line item in an invoice response — includes server-authoritative line total."""

    model_config = ConfigDict(from_attributes=True)

    name: str = Field(description="Service or product name.")
    description: Optional[str] = Field(default=None, description="Optional line item description.")
    quantity: Decimal = Field(description="Number of units.")
    unit_price: MoneyDecimal = Field(description="Price per unit.")
    tax: MoneyDecimal = Field(description="Tax amount for this line.")
    total: MoneyDecimal = Field(description="Authoritative line total: (quantity × unit_price) + tax.")


# ---------------------------------------------------------------------------
# Invoice request schemas
# ---------------------------------------------------------------------------

class InvoiceCreate(BaseModel):
    """Invoice creation request schema.

    Server-side invariants:
    - ``total``, ``subtotal``, and ``tax`` are always computed server-side from line items.
    - ``client_total_preview`` is accepted but silently discarded — it is never persisted.
    - ``invoice_number`` is auto-generated if omitted (format: INV-YYYY-NNNN).
    - ``due_date`` must be >= ``issue_date``.
    - ``customer_id`` must belong to the authenticated user.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "customer_id": "cust-8823f9b1",
                "invoice_number": "INV-2026-0001",
                "items": [
                    {
                        "name": "Full-Stack Web Development",
                        "description": "5 days consulting sprint",
                        "quantity": "1.00",
                        "unit_price": "500.00",
                        "tax": "0.00",
                    }
                ],
                "currency": "USD",
                "issue_date": "2026-11-10",
                "due_date": "2026-11-17",
                "notes": "Thank you for your business. Payment via PayPal Sandbox.",
            }
        }
    )

    customer_id: str = Field(
        ...,
        min_length=1,
        description="Customer UUID. Must belong to the authenticated user and be active.",
    )
    invoice_number: Optional[str] = Field(
        default=None,
        max_length=50,
        description=(
            "Optional custom invoice reference (e.g. 'INV-2026-001'). "
            "Must be unique per user. Auto-generated as INV-YYYY-NNNN if omitted."
        ),
    )
    items: List[InvoiceItemCreate] = Field(
        ...,
        min_length=1,
        description="One or more line items. Totals are computed server-side from these values.",
    )
    currency: SupportedCurrency = Field(
        default=SupportedCurrency.USD,
        description=(
            "ISO 4217 currency code for the invoice. "
            "Supported: USD, EUR, GBP, CAD, AUD, JPY, CHF, SGD, NZD, INR."
        ),
    )
    issue_date: Optional[date] = Field(
        default=None,
        description="Invoice issue date. Defaults to today (UTC) if omitted.",
    )
    due_date: date = Field(
        ...,
        description="Payment due date. Must be >= issue_date.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional invoice-level notes shown to the customer.",
    )
    # Client preview is accepted for UX convenience but always discarded server-side
    client_total_preview: Optional[MoneyDecimal] = Field(
        default=None,
        description=(
            "[Ignored by server] Client-side total preview for UI display only. "
            "The authoritative total is always computed server-side from line items."
        ),
    )


class InvoiceUpdate(BaseModel):
    """Invoice update request schema. Restricted strictly to draft invoices.

    All fields are optional — only provided fields are mutated. If ``items`` is
    supplied, all line items are replaced and totals are recomputed server-side.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "notes": "Updated payment terms: Net-14.",
                "due_date": "2026-11-24",
            }
        }
    )

    customer_id: Optional[str] = Field(
        default=None,
        description="Replacement customer UUID. Must belong to the authenticated user.",
    )
    items: Optional[List[InvoiceItemCreate]] = Field(
        default=None,
        min_length=1,
        description=(
            "Replacement line items. When provided, all previous items are replaced "
            "and totals are recomputed authoritatively."
        ),
    )
    currency: Optional[SupportedCurrency] = Field(
        default=None,
        description="Replacement ISO 4217 currency code.",
    )
    issue_date: Optional[date] = Field(
        default=None,
        description="Replacement issue date. Must be <= due_date.",
    )
    due_date: Optional[date] = Field(
        default=None,
        description="Replacement due date. Must be >= issue_date.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Replacement invoice notes. Send null/empty string to clear.",
    )

    @model_validator(mode="after")
    def validate_items_non_empty_if_provided(self) -> "InvoiceUpdate":
        """Reject an explicit empty items list — a draft must always have at least one item."""
        if self.items is not None and len(self.items) == 0:
            raise ValueError("At least one line item is required when providing 'items'.")
        return self


# ---------------------------------------------------------------------------
# Invoice response schemas
# ---------------------------------------------------------------------------

class InvoiceResponse(BaseModel):
    """Complete invoice representation including server-computed totals.

    Security:
    - ``paypal_invoice_id`` and ``paypal_invoice_url`` are populated only after PayPal
      sandbox integration (Phase 15). They are never client-supplied.
    - ``user_id`` is returned only to the authenticated owner via enforced JWT scope.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    internal_id: str = Field(description="Stable internal invoice UUID.")
    user_id: str = Field(description="Owner user ID. Always matches the authenticated caller.")
    customer_id: str = Field(description="Linked customer UUID.")
    customer_name: Optional[str] = Field(
        default=None,
        description="Customer name resolved from the customers collection (enriched on read).",
    )
    invoice_number: str = Field(description="Human-readable invoice reference (e.g. INV-2026-0001).")
    items: List[InvoiceItemResponse] = Field(description="Line items with server-computed line totals.")
    subtotal: MoneyDecimal = Field(description="Sum of (quantity × unit_price) across all items.")
    tax: MoneyDecimal = Field(description="Sum of tax amounts across all items.")
    total: MoneyDecimal = Field(description="Authoritative invoice total: subtotal + tax.")
    currency: SupportedCurrency = Field(description="ISO 4217 currency code.")
    issue_date: date = Field(description="Invoice issue date.")
    due_date: date = Field(description="Payment due date.")
    status: InvoiceStatus = Field(
        description=(
            "Invoice lifecycle status. Allowed values: draft, pending_approval, created, "
            "sent, unpaid, partially_paid, paid, overdue, cancelled, failed."
        )
    )
    paypal_invoice_id: Optional[str] = Field(
        default=None,
        description="PayPal invoice ID assigned by PayPal API (populated after sandbox creation).",
    )
    paypal_invoice_url: Optional[str] = Field(
        default=None,
        description="PayPal-hosted invoice URL (populated after sandbox creation).",
    )
    sent_at: Optional[datetime] = Field(default=None, description="UTC timestamp when invoice was sent.")
    paid_at: Optional[datetime] = Field(default=None, description="UTC timestamp when invoice was marked paid.")
    created_at: datetime = Field(description="UTC creation timestamp.")
    updated_at: datetime = Field(description="UTC last-modification timestamp.")
    notes: Optional[str] = Field(default=None, description="Invoice-level notes.")


class InvoiceListResponse(BaseModel):
    """Paginated list of invoice records with stable metadata."""

    items: List[InvoiceResponse] = Field(description="Invoice records for the current page.")
    total: int = Field(description="Total matching invoices across all pages.")
    page: int = Field(description="Current 1-indexed page number.")
    page_size: int = Field(description="Number of records per page.")
    pages: int = Field(description="Total number of pages for the current query.")


class SubmitForApprovalResponse(BaseModel):
    """Response returned when an invoice draft is submitted for human authorization.

    The ``payload_hash`` is a SHA-256 of the immutable snapshot. If the invoice
    is edited after submission, the approval is invalidated and a new one must
    be requested.
    """

    invoice: InvoiceResponse = Field(description="Current invoice state after status transition.")
    approval_id: str = Field(description="Approval record UUID to track in the Approval Center.")
    payload_hash: str = Field(
        description=(
            "SHA-256 hash of the immutable invoice payload snapshot. "
            "Any edit after submission will invalidate this approval."
        )
    )
    status: str = Field(description="Current approval status (always 'pending_approval' on fresh submit).")
    message: str = Field(description="Human-readable confirmation message.")


class InvoiceDeleteResponse(BaseModel):
    """Response returned when an invoice draft is deleted."""

    message: str = Field(description="Confirmation message.")
    id: str = Field(description="Internal ID of the deleted invoice.")
