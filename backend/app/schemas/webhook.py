"""Pydantic schemas for PayPal webhook processing and verification (Prompt 23)."""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PayPalWebhookVerificationPayload(BaseModel):
    """Payload sent to PayPal POST /v1/notifications/verify-webhook-signature."""

    auth_algo: str
    cert_url: str
    transmission_id: str
    transmission_sig: str
    transmission_time: str
    webhook_id: str
    webhook_event: Dict[str, Any]


class WebhookProcessingResponse(BaseModel):
    """Response returned to PayPal webhook delivery caller."""

    status: str = Field(..., description="Outcome: processed, duplicate, ignored, unverified")
    event_id: str
    event_type: str
    message: str
    persisted: bool = False
    reconciled_invoice_id: Optional[str] = None
    processed_at: datetime

