"""Pydantic schemas for append-only-style audit logs and invoice timelines (Prompt 24)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActorType


class AuditLogResponse(BaseModel):
    """Safe, redacted representation of an audit event."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str
    actor: ActorType
    action: str
    resource_type: str
    resource_id: str
    result: str
    correlation_id: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    """List of audit events."""

    total: int
    items: List[AuditLogResponse]


class TimelineEvent(BaseModel):
    """User-visible lifecycle event for an invoice details timeline."""

    id: str
    action: str
    action_label: str
    actor_type: str
    timestamp: datetime
    result: str
    metadata: Dict[str, Any]


class InvoiceTimelineResponse(BaseModel):
    """Chronological activity timeline for an invoice."""

    invoice_id: str
    invoice_number: str
    events: List[TimelineEvent]
