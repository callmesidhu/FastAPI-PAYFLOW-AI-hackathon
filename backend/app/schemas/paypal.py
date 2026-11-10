"""Pydantic schemas for PayPal Sandbox integration diagnostics and status."""

from typing import Optional
from pydantic import BaseModel, Field


class PayPalStatusResponse(BaseModel):
    """Safe diagnostic report of PayPal Sandbox connectivity.

    Guarantees:
    - Never exposes client secrets, raw access tokens, or sensitive credentials.
    """

    configured: bool = Field(description="True if PayPal client credentials are set.")
    connected: bool = Field(description="True if server can reach PayPal Sandbox and authenticate.")
    environment: str = Field(default="sandbox", description="Active PayPal environment ('sandbox').")
    base_url: str = Field(description="PayPal REST API base endpoint.")
    webhook_configured: bool = Field(description="True if PAYPAL_WEBHOOK_ID is non-empty.")
    token_masked: Optional[str] = Field(default=None, description="Redacted token prefix for verification.")
    message: str = Field(description="Human-readable status summary.")


class PayPalInvoiceCreateRequest(BaseModel):
    """Payload to trigger creation of an approved invoice in PayPal Sandbox."""

    invoice_id: str = Field(..., description="Internal UUID of the invoice to dispatch to PayPal")
    approval_id: Optional[str] = Field(default=None, description="Optional explicit approval UUID")
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Optional client idempotency key to prevent double execution",
    )


class PayPalInvoiceCreateResponse(BaseModel):
    """Response returned upon successful creation in PayPal Sandbox."""

    invoice_id: str = Field(..., description="Internal invoice UUID")
    invoice_number: str = Field(..., description="Authoritative invoice reference")
    paypal_invoice_id: str = Field(..., description="PayPal assigned invoice ID (e.g. INV2-XXXX-XXXX)")
    paypal_invoice_url: str = Field(..., description="Official Sandbox preview/payment URL")
    status: str = Field(..., description="New invoice status ('created')")
    message: str = Field(..., description="Human-readable execution confirmation")
    is_duplicate: bool = Field(default=False, description="True if returning an already-created invoice")


class PayPalInvoiceSendRequest(BaseModel):
    """Payload to send an existing approved invoice to a customer via PayPal Sandbox."""

    approval_id: Optional[str] = Field(default=None, description="Optional explicit approval UUID")
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Client idempotency key to prevent double execution",
    )
    send_to_recipient: bool = Field(
        default=True,
        description="Whether to deliver the invoice email to the recipient",
    )
    send_to_invoicer: bool = Field(
        default=False,
        description="Whether to deliver a copy of the invoice to the business owner",
    )
    note: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional greeting or delivery note",
    )


class PayPalInvoiceSendResponse(BaseModel):
    """Response returned upon successful invoice dispatch in PayPal Sandbox."""

    invoice_id: str = Field(..., description="Internal invoice UUID")
    invoice_number: str = Field(..., description="Human-readable invoice reference")
    paypal_invoice_id: str = Field(..., description="PayPal assigned invoice ID")
    paypal_invoice_url: str = Field(..., description="Official Sandbox preview/payment URL")
    status: str = Field(..., description="New invoice status ('sent')")
    sent_at: str = Field(..., description="ISO 8601 timestamp when dispatch was recorded")
    message: str = Field(..., description="Human-readable delivery confirmation")
    is_duplicate: bool = Field(default=False, description="True if invoice was already sent")


