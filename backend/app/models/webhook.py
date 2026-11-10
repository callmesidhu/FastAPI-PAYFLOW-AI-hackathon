"""PayPal Webhook event domain model."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WebhookEvent(BaseModel):
    """Persisted PayPal webhook event ensuring replay protection and idempotency."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = Field(..., description="PayPal assigned unique event ID (WH-...)")
    event_type: str = Field(..., description="PayPal event type (e.g., INVOICING.INVOICE.PAID)")
    resource_type: str = Field(default="invoicing_invoice")
    resource_id: str = Field(..., description="PayPal resource ID referenced by event")
    verified: bool = Field(default=False, description="Whether PayPal cryptographic signature passed")
    received_at: datetime = Field(default_factory=utc_now)
    processed_at: Optional[datetime] = None
    status: str = Field(default="received", description="Processing status: received, processed, ignored, duplicate")
    summary: str = Field(default="", description="Safe human-readable event summary")
    payload_redacted: Dict[str, Any] = Field(default_factory=dict, description="Redacted event payload")
