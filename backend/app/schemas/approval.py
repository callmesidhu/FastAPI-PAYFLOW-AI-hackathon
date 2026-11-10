"""Pydantic schemas for the Human Authorization Approval Engine."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import ActionType, ApprovalStatus


class ApprovalResponse(BaseModel):
    """Detailed approval record response schema."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    user_id: str
    action_type: ActionType
    resource_type: str
    resource_id: str
    payload_snapshot: Dict[str, Any]
    payload_hash: str
    status: ApprovalStatus
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    execution_result_ref: Optional[str] = None

    # Contextual display fields
    display_title: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_number: Optional[str] = None
    amount: Optional[str] = None
    currency: Optional[str] = None


class ApprovalListResponse(BaseModel):
    """Paginated or categorized list of approvals."""

    items: List[ApprovalResponse]
    total: int
    pending_count: int


class ApprovalDecisionRequest(BaseModel):
    """Payload to authorize or reject an approval request."""

    reason: Optional[str] = Field(default=None, max_length=500, description="Optional explanation or memo")
    idempotency_key: Optional[str] = Field(default=None, max_length=100, description="Client idempotency token")


class ApprovalDecisionResponse(BaseModel):
    """Result of an approval authorization or rejection."""

    approval_id: str
    status: str
    message: str
    decided_at: datetime
    audit_id: Optional[str] = None
