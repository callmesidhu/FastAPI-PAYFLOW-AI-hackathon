"""Payment reminder domain model (Prompts 21 & 22)."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ReminderStage, ReminderStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Reminder(BaseModel):
    """Contextual payment reminder drafted by policy or AI assistant.

    Guarantees:
    - Strictly scoped to user_id.
    - Idempotency via (invoice_id, stage) compound unique index.
    - Contains only verified invoice data.
    - Stored as draft first; never sent without explicit authorization and configured channel.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="User ID of authorized business owner")
    invoice_id: str = Field(..., description="Target invoice internal ID")
    invoice_number: str = Field(..., description="Human-readable invoice reference")
    customer_id: str = Field(..., description="Customer recipient ID")
    customer_name: str = Field(..., description="Verified recipient name")
    customer_email: str = Field(..., description="Verified recipient email")

    stage: ReminderStage = Field(..., description="Deterministic overdue stage")
    status: ReminderStatus = Field(default=ReminderStatus.DRAFT)

    subject: str = Field(..., min_length=1, max_length=200)
    message_body: str = Field(..., min_length=1, max_length=4000)
    payment_link: Optional[str] = Field(default=None, description="Official PayPal invoice payment URL if available")
    channel: str = Field(default="manual", description="Delivery channel (email, zapier, manual)")

    retry_count: int = Field(default=0, ge=0)
    delivery_error: Optional[str] = Field(default=None)
    approval_id: Optional[str] = Field(default=None, description="Linked human approval ID")

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    approved_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
