"""Pydantic schemas for Payment Reminder generation, evaluation, editing,
approval, and dispatch (Prompts 21 & 22).
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReminderStage, ReminderStatus


class ReminderBase(BaseModel):
    """Core reminder fields."""

    subject: str = Field(..., min_length=1, max_length=200, description="Email/notification subject line")
    message_body: str = Field(..., min_length=1, max_length=4000, description="Respectful body text")


class ReminderUpdate(BaseModel):
    """User edits to reminder draft before approval."""

    subject: Optional[str] = Field(default=None, min_length=1, max_length=200)
    message_body: Optional[str] = Field(default=None, min_length=1, max_length=4000)


class ReminderResponse(BaseModel):
    """Full reminder representation for UI and API clients."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str
    invoice_id: str
    invoice_number: str
    customer_id: str
    customer_name: str
    customer_email: str
    stage: ReminderStage
    status: ReminderStatus
    subject: str
    message_body: str
    payment_link: Optional[str] = None
    channel: str
    channel_configured: bool = False
    channel_label: str = "Unconfigured (Manual Dispatch)"
    retry_count: int = 0
    delivery_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    approval_id: Optional[str] = None


class ReminderListResponse(BaseModel):
    """Paginated or filtered list of reminders."""

    total: int
    items: List[ReminderResponse]


class ReminderEvaluationRequest(BaseModel):
    """Request to evaluate eligible invoices for reminder draft preparation."""

    invoice_id: Optional[str] = Field(
        default=None,
        description="Optional single invoice ID to evaluate; if omitted, evaluates all user invoices",
    )
    force_stage: Optional[ReminderStage] = Field(
        default=None,
        description="Optional forced stage for preview/manual drafting",
    )


class ReminderEvaluationResult(BaseModel):
    """Summary of reminder evaluation run."""

    evaluated_invoices_count: int
    drafts_created_count: int
    skipped_existing_count: int
    reminders: List[ReminderResponse]


class ReminderDispatchRequest(BaseModel):
    """Request to dispatch an approved reminder."""

    override_channel: Optional[str] = Field(
        default=None,
        description="Optional channel override (email, zapier, manual)",
    )


class ReminderDispatchResult(BaseModel):
    """Outcome of reminder dispatch attempt."""

    reminder_id: str
    invoice_number: str
    status: ReminderStatus
    channel: str
    channel_configured: bool
    message: str
    retry_count: int
    delivery_error: Optional[str] = None
    sent_at: Optional[datetime] = None

