"""Pydantic schemas for AI provider abstraction, structured tool arguments,
and assistant interactions.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DraftItemArgs(BaseModel):
    """Line item argument schema for AI invoice creation."""

    name: str = Field(..., min_length=1, max_length=140, description="Service or product description")
    quantity: Decimal = Field(default=Decimal("1.0"), gt=0, description="Quantity of units")
    unit_price: Decimal = Field(..., ge=0, description="Per-unit price in invoice currency")
    tax: Decimal = Field(default=Decimal("0.00"), ge=0, description="Tax amount for this line item")
    description: Optional[str] = Field(default=None, max_length=500, description="Optional detailed description")


class CreateInvoiceDraftArgs(BaseModel):
    """Schema-validated arguments for create_invoice_draft tool."""

    customer_name_or_id: str = Field(
        ...,
        min_length=1,
        description="Name or ID of customer to invoice. If name is ambiguous, clarify first.",
    )
    items: List[DraftItemArgs] = Field(
        ...,
        min_length=1,
        description="List of items/services to bill. Must have at least one item with unit price.",
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="ISO 4217 currency code (e.g. USD, EUR, GBP, CAD, AUD). Do not guess if ambiguous.",
    )
    due_date: Optional[str] = Field(
        default=None,
        description="Explicit payment due date in YYYY-MM-DD format.",
    )
    due_in_days: Optional[int] = Field(
        default=14,
        ge=0,
        le=365,
        description="Days from today if exact date not given. Defaults to 14 days.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional payment terms or client memo.",
    )


class SearchCustomersArgs(BaseModel):
    """Arguments for search_customers tool."""

    query: str = Field(..., min_length=1, description="Search term for customer name, email, or company")


class ListInvoicesArgs(BaseModel):
    """Arguments for list_invoices tool."""

    status: Optional[str] = Field(
        default=None,
        description="Optional filter by status: draft, pending_approval, created, sent, unpaid, paid, overdue",
    )
    customer_name: Optional[str] = Field(
        default=None,
        description="Optional filter by customer name",
    )
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of records to return")


class GetOverdueInvoicesArgs(BaseModel):
    """Arguments for get_overdue_invoices tool."""

    currency: Optional[str] = Field(default=None, description="Optional currency filter")


class GetInvoiceDetailArgs(BaseModel):
    """Arguments for get_invoice_detail tool."""

    invoice_ref: str = Field(..., description="Invoice number (e.g. INV-2026-0001) or internal UUID")


class PrepareReminderDraftArgs(BaseModel):
    """Arguments for prepare_reminder_draft tool."""

    invoice_ref: str = Field(..., description="Invoice reference to prepare reminder for")
    tone: Optional[str] = Field(
        default="courteous",
        description="Tone of reminder message: 'courteous', 'firm', or 'urgent'",
    )


class GetReceivablesSummaryArgs(BaseModel):
    """Arguments for get_receivables_summary tool."""

    currency: Optional[str] = Field(default=None, description="Optional ISO currency code")


class RequestApprovalArgs(BaseModel):
    """Arguments for request_approval tool."""

    invoice_id: str = Field(..., description="Internal invoice UUID to submit for owner approval")
    action_type: str = Field(
        default="create_paypal_invoice",
        description="Action type: create_paypal_invoice or send_payment_reminder",
    )


# ==============================================================================
# Chat / Completion Schemas
# ==============================================================================

class AIToolCall(BaseModel):
    """Structured tool call produced by an AI model."""

    id: str = Field(default="call_0")
    name: str
    arguments: Dict[str, Any]


class AICompletionResult(BaseModel):
    """Unified completion result from an AI provider."""

    content: Optional[str] = None
    tool_calls: List[AIToolCall] = Field(default_factory=list)
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    model: str = "default"
    finish_reason: Optional[str] = None


class AIChatMessage(BaseModel):
    """Individual message in conversation history."""

    role: str = Field(..., description="'user', 'assistant', 'system', or 'tool'")
    content: str = Field(default="")
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None


class AIChatRequest(BaseModel):
    """Inbound chat message from the user."""

    message: str = Field(..., min_length=1, max_length=2000, description="User instruction or prompt")
    conversation_id: Optional[str] = Field(default=None, description="Optional existing conversation thread ID")


class AIChatResponse(BaseModel):
    """Outbound response from the AI Assistant."""

    conversation_id: str
    message: str
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    clarification_needed: bool = False
    preview_data: Optional[Dict[str, Any]] = None
    approval_requested: bool = False
    approval_id: Optional[str] = None


# ==============================================================================
# Prompt 19: AI Natural Language Invoice Extraction & Preview Schemas
# ==============================================================================

class CustomerMatchCandidate(BaseModel):
    """Customer candidate for disambiguation."""

    id: str
    name: str
    email: str
    company: Optional[str] = None


class ExtractedDraftItem(BaseModel):
    """Individual line item extracted from natural language command."""

    name: str = Field(..., description="Item or service name")
    description: Optional[str] = Field(default=None, description="Optional service notes")
    quantity: Decimal = Field(default=Decimal("1.0"), gt=0)
    unit_price: Decimal = Field(..., ge=0)
    tax: Decimal = Field(default=Decimal("0.00"), ge=0)
    total: Decimal = Field(default=Decimal("0.00"), ge=0)


class ExtractedInvoiceDraft(BaseModel):
    """Structured draft preview extracted by AI before user confirmation."""

    customer_id: Optional[str] = None
    customer_name: str
    customer_email: Optional[str] = None
    currency: str = "USD"
    issue_date: str
    due_date: str
    due_date_relative_text: Optional[str] = None
    timezone_disclosed: str = "UTC"
    items: List[ExtractedDraftItem]
    subtotal: str
    tax: str
    total: str
    notes: Optional[str] = None


class InvoiceExtractionRequest(BaseModel):
    """Inbound request to extract structured invoice from natural language."""

    text: str = Field(..., min_length=1, max_length=2000, description="Natural language command")
    timezone: Optional[str] = Field(default="UTC", description="User configured timezone (defaults to UTC)")


class InvoiceExtractionResponse(BaseModel):
    """Response containing editable preview or clarification request."""

    is_suggestion: bool = True  # Distinguishes 'AI suggestion' from 'saved invoice'
    clarification_needed: bool = False
    clarification_question: Optional[str] = None
    ambiguity_reason: Optional[str] = None
    customer_matches: List[CustomerMatchCandidate] = Field(default_factory=list)
    extracted_draft: Optional[ExtractedInvoiceDraft] = None


class ConfirmExtractedInvoiceRequest(BaseModel):
    """User confirmation and edits for the extracted invoice draft."""

    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    items: List[DraftItemArgs] = Field(..., min_length=1)
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None


