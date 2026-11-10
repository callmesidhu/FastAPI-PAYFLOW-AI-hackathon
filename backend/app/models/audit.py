"""Append-only audit trail domain model."""

from datetime import datetime, timezone
from typing import Any, Dict
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ActorType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(BaseModel):
    """Append-only record of domain events, authorization decisions, and API transactions."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="Owner user_id scoping this audit event")
    actor: ActorType = Field(default=ActorType.USER)
    action: str = Field(..., description="Event name (e.g., invoice.created, invoice.approved, reminder.sent)")
    resource_type: str = Field(..., description="Entity type affected (invoice, customer, approval)")
    resource_id: str = Field(..., description="Target entity ID")
    result: str = Field(default="success", description="Outcome: success, failure, rejected")
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Safe event metadata (no secrets or PII)")
    created_at: datetime = Field(default_factory=utc_now)
