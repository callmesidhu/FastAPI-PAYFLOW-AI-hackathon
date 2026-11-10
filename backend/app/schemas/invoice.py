"""Pydantic schemas for Invoice requests, responses, updates, and approval submission."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import InvoiceStatus, SupportedCurrency
from app.models.money import MoneyDecimal


class InvoiceItemCreate(BaseModel):
    """Line item creation schema."""

    name: str = Field(..., min_length=1, max_length=140, json_schema_extra={"example": "Website Design & Architecture"})
    description: Optional[str] = Field(default=None, max_length=500, json_schema_extra={"example": "Sprint 1: UX design and backend API contract"})
    quantity: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0.01"), json_schema_extra={"example": "1.00"})
    unit_price: MoneyDecimal = Field(..., ge=Decimal("0.00"), json_schema_extra={"example": "500.00"})
    tax: MoneyDecimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), json_schema_extra={"example": "0.00"})


class InvoiceItemResponse(BaseModel):
    """Line item response schema including calculated total."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    description: Optional[str] = None
    quantity: Decimal
    unit_price: MoneyDecimal
    tax: MoneyDecimal
    total: MoneyDecimal


class InvoiceCreate(BaseModel):
    """Invoice creation request schema."""

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

    customer_id: str = Field(..., min_length=1, description="Customer identifier")
    invoice_number: Optional[str] = Field(default=None, max_length=50, description="Optional custom reference; auto-generated if omitted")
    items: List[InvoiceItemCreate] = Field(..., min_length=1, description="At least one line item is required")
    currency: SupportedCurrency = Field(default=SupportedCurrency.USD, description="ISO 4217 currency code")
    issue_date: Optional[date] = Field(default=None, description="Invoice date (defaults to today)")
    due_date: date = Field(..., description="Due date for payment")
    notes: Optional[str] = Field(default=None, max_length=1000)
    # Any client-supplied subtotal or total will be authoritatively recalculated server-side
    client_total_preview: Optional[MoneyDecimal] = None


class InvoiceUpdate(BaseModel):
    """Invoice update request schema (restricted strictly to draft invoices)."""

    customer_id: Optional[str] = None
    items: Optional[List[InvoiceItemCreate]] = None
    currency: Optional[SupportedCurrency] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Complete invoice detail response schema."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    internal_id: str
    user_id: str
    customer_id: str
    customer_name: Optional[str] = None
    invoice_number: str
    items: List[InvoiceItemResponse]
    subtotal: MoneyDecimal
    tax: MoneyDecimal
    total: MoneyDecimal
    currency: SupportedCurrency
    issue_date: date
    due_date: date
    status: InvoiceStatus
    paypal_invoice_id: Optional[str] = None
    paypal_invoice_url: Optional[str] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    notes: Optional[str] = None


class InvoiceListResponse(BaseModel):
    """Paginated list of invoices with summary counts."""

    items: List[InvoiceResponse]
    total: int
    page: int
    page_size: int
    pages: int


class SubmitForApprovalResponse(BaseModel):
    """Response returned upon submitting an invoice draft for human authorization."""

    invoice: InvoiceResponse
    approval_id: str
    payload_hash: str
    status: str
    message: str
