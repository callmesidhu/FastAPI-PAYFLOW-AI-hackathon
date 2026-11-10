"""Approval Center API endpoints for human authorization workflows."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.approval import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalListResponse,
    ApprovalResponse,
)
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get(
    "",
    response_model=ApprovalListResponse,
    summary="List Approvals",
    description="Retrieve approvals scoped strictly to the authenticated user with optional status filtering.",
)
async def list_approvals(
    status: Optional[str] = Query(default=None, description="Filter by status (pending, approved, rejected, invalidated)"),
    resource_id: Optional[str] = Query(default=None, description="Filter by target resource ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ApprovalListResponse:
    return await approval_service.list_approvals(
        db=db,
        user_id=current_user.id,
        status_filter=status,
        resource_id=resource_id,
    )


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    summary="Inspect Approval",
    description="Inspect an approval request, including its cryptographic payload snapshot and hash.",
)
async def get_approval(
    approval_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ApprovalResponse:
    return await approval_service.get_approval_by_id(
        db=db,
        user_id=current_user.id,
        approval_id=approval_id,
    )


@router.post(
    "/{approval_id}/approve",
    response_model=ApprovalDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Authorize Pending Action",
    description="Authorize a pending action. Verifies payload hash match and enforces replay protection.",
)
async def approve_action(
    approval_id: str,
    payload: Optional[ApprovalDecisionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ApprovalDecisionResponse:
    return await approval_service.approve_action(
        db=db,
        user_id=current_user.id,
        approval_id=approval_id,
        payload=payload,
    )


@router.post(
    "/{approval_id}/reject",
    response_model=ApprovalDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject Pending Action",
    description="Reject a pending action and safely restore the linked resource to draft status.",
)
async def reject_action(
    approval_id: str,
    payload: Optional[ApprovalDecisionRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ApprovalDecisionResponse:
    return await approval_service.reject_action(
        db=db,
        user_id=current_user.id,
        approval_id=approval_id,
        payload=payload,
    )
