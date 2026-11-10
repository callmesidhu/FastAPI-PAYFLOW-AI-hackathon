"""Invoice domain model and line item definitions.

Enforces Decimal arithmetic, non-negative monetary constraints,
explicit ISO currency tracking, and strict status transitions.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import InvoiceStatus, SupportedCurrency, can_transition_invoice
from app.models.money import MoneyDecimal, to_decimal, validate_currency_code, validate_positive_money


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InvoiceItem(BaseModel):
    """Individual line item within an invoice."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(..., min_length=1, max_length=140, description="Service or product description")
    description: Optional[str] = Field(default=None, max_length=500)
    quantity: Decimal = Field(default=Decimal("1.00"), description="Quantity of units")
    unit_price: MoneyDecimal = Field(..., description="Per-unit price in invoice currency")
    tax: MoneyDecimal = Field(default=Decimal("0.00"), description="Tax amount for this line item")
    total: MoneyDecimal = Field(default=Decimal("0.00"), description="Authoritative line item total")

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: Decimal) -> Decimal:
        dec = to_decimal(v)
        if dec <= Decimal("0.00"):
            raise ValueError("Item quantity must be strictly greater than 0.")
        return dec

    @field_validator("unit_price", "tax")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        return validate_positive_money(v)

    @model_validator(mode="after")
    def calculate_line_total(self) -> "InvoiceItem":
        """Authoritatively calculate line item total: (quantity * unit_price) + tax."""
        raw_total = (self.quantity * self.unit_price) + self.tax
        self.total = to_decimal(raw_total)
        return self


class Invoice(BaseModel):
    """Authoritative invoice entity scoped to an authenticated user."""

    model_config = ConfigDict(populate_by_name=True)

    internal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="Owner user_id scoping this invoice")
    customer_id: str = Field(..., description="Linked customer ID")
    invoice_number: str = Field(..., min_length=1, max_length=50, description="Human-readable invoice reference")

    items: List[InvoiceItem] = Field(..., min_length=1, description="List of invoiced items/services")
    subtotal: MoneyDecimal = Field(default=Decimal("0.00"))
    tax: MoneyDecimal = Field(default=Decimal("0.00"))
    total: MoneyDecimal = Field(default=Decimal("0.00"))
    currency: SupportedCurrency = Field(default=SupportedCurrency.USD)

    issue_date: date = Field(default_factory=lambda: utc_now().date())
    due_date: date = Field(...)
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT)

    # PayPal Integration References (populated once created/sent)
    paypal_invoice_id: Optional[str] = Field(default=None, max_length=100)
    paypal_invoice_url: Optional[str] = Field(default=None, max_length=500)

    # Timestamps
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, v: Any) -> SupportedCurrency:
        if isinstance(v, SupportedCurrency):
            return v
        code = validate_currency_code(str(v))
        return SupportedCurrency(code)

    @model_validator(mode="after")
    def compute_totals(self) -> "Invoice":
        """Compute authoritative subtotal, tax, and total from line items using Decimal."""
        computed_subtotal = Decimal("0.00")
        computed_tax = Decimal("0.00")

        for item in self.items:
            computed_subtotal += (item.quantity * item.unit_price)
            computed_tax += item.tax

        self.subtotal = to_decimal(computed_subtotal)
        self.tax = to_decimal(computed_tax)
        self.total = to_decimal(self.subtotal + self.tax)

        if self.total < Decimal("0.00"):
            raise ValueError("Invoice total cannot be negative.")

        if self.due_date < self.issue_date:
            raise ValueError("Invoice due_date cannot be earlier than issue_date.")

        return self

    def transition_status(self, new_status: InvoiceStatus) -> None:
        """Validate and apply state transition."""
        if not can_transition_invoice(self.status, new_status):
            raise ValueError(
                f"Invalid status transition from '{self.status.value}' to '{new_status.value}'."
            )
        self.status = new_status
        self.updated_at = utc_now()
        if new_status == InvoiceStatus.SENT and not self.sent_at:
            self.sent_at = utc_now()
        elif new_status == InvoiceStatus.PAID and not self.paid_at:
            self.paid_at = utc_now()
