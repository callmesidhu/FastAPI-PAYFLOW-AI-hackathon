"""Payment reminder domain model."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ReminderStage, ReminderStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Reminder(BaseModel):
    """Contextual payment reminder drafted by policy or AI assistant."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="User ID of authorized business owner")
    invoice_id: str = Field(..., description="Target invoice internal ID")
    customer_id: str = Field(..., description="Customer recipient ID")

    stage: ReminderStage = Field(..., description="Deterministic overdue stage")
    status: ReminderStatus = Field(default=ReminderStatus.DRAFT)

    subject: str = Field(..., min_length=1, max_length=200)
    message_body: str = Field(..., min_length=1, max_length=2000)
    channel: str = Field(default="approval_center", description="Delivery channel or queue")

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    sent_at: Optional[datetime] = None
