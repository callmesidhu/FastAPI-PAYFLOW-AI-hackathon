"""Human authorization approval domain model."""

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ActionType, ApprovalStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """Compute deterministic SHA256 hash of a payload dictionary."""
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class Approval(BaseModel):
    """Explicit human-in-the-loop approval record bound to an immutable snapshot."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="User ID of authorized business owner")
    action_type: ActionType
    resource_type: str = Field(default="invoice", description="Target resource type, e.g., invoice")
    resource_id: str = Field(..., description="Target internal resource identifier")

    payload_snapshot: Dict[str, Any] = Field(..., description="Immutable snapshot of action parameters")
    payload_hash: str = Field(..., description="SHA-256 hash of payload_snapshot")

    status: ApprovalStatus = Field(default=ApprovalStatus.PENDING)
    created_at: datetime = Field(default_factory=utc_now)
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    execution_result_ref: Optional[str] = Field(default=None, description="PayPal ID or result correlation")

    def approve(self) -> None:
        """Mark as approved."""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve an action currently in '{self.status.value}' state.")
        self.status = ApprovalStatus.APPROVED
        self.approved_at = utc_now()

    def reject(self) -> None:
        """Mark as rejected."""
        if self.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot reject an action currently in '{self.status.value}' state.")
        self.status = ApprovalStatus.REJECTED
        self.rejected_at = utc_now()

    def invalidate(self) -> None:
        """Invalidate approval if payload content changes before execution."""
        self.status = ApprovalStatus.INVALIDATED
