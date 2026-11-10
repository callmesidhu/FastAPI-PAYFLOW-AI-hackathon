"""Payment Reminders API Endpoints (Prompts 21 & 22)."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.jobs.reminder_job import run_reminder_evaluation_cycle
from app.models.enums import ReminderStage, ReminderStatus
from app.models.user import User
from app.schemas.reminder import (
    ReminderDispatchRequest,
    ReminderDispatchResult,
    ReminderEvaluationRequest,
    ReminderEvaluationResult,
    ReminderListResponse,
    ReminderResponse,
    ReminderUpdate,
)
from app.services.reminder_service import ReminderService

router = APIRouter(prefix="/reminders", tags=["Payment Reminders"])


@router.post(
    "/evaluate",
    response_model=ReminderEvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate eligible invoices and generate reminder drafts",
    description=(
        "Evaluates merchant invoices against deterministic policy stages: upcoming (-1d), due today (0d), "
        "and overdue (1-3d, 4-7d, 8-14d, 15+d). Excludes paid, cancelled, draft, or already-reminded invoices. "
        "Drafts are stored with status='ready_for_approval'; no communications are sent automatically."
    ),
)
async def evaluate_reminders(
    payload: ReminderEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReminderEvaluationResult:
    return await ReminderService.evaluate_and_create_reminders(
        db=db,
        user_id=current_user.id,
        invoice_id=payload.invoice_id,
        force_stage=payload.force_stage,
    )


@router.get(
    "",
    response_model=ReminderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List payment reminders",
    description="Retrieve reminders scoped strictly to the authenticated user with optional status/stage filters.",
)
async def list_reminders(
    status_filter: Optional[ReminderStatus] = Query(default=None, alias="status"),
    stage_filter: Optional[ReminderStage] = Query(default=None, alias="stage"),
    invoice_id: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReminderListResponse:
    items = await ReminderService.list_reminders(
        db=db,
        user_id=current_user.id,
        status=status_filter,
        stage=stage_filter,
        invoice_id=invoice_id,
        limit=limit,
    )
    return ReminderListResponse(total=len(items), items=items)


@router.get(
    "/{reminder_id}",
    response_model=ReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Inspect reminder draft",
)
async def get_reminder(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReminderResponse:
    rem = await ReminderService.get_reminder_by_id(db, current_user.id, reminder_id)
    if not rem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reminder '{reminder_id}' not found.",
        )
    return rem


@router.patch(
    "/{reminder_id}",
    response_model=ReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Edit reminder subject or message body before approval",
)
async def update_reminder(
    reminder_id: str,
    payload: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReminderResponse:
    try:
        updated = await ReminderService.update_reminder(
            db=db,
            user_id=current_user.id,
            reminder_id=reminder_id,
            payload=payload,
        )
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reminder '{reminder_id}' not found.",
            )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{reminder_id}/approve",
    response_model=ReminderResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve payment reminder draft",
    description="Explicit human approval of a reminder. Moves status to 'approved' and authorizes dispatch.",
)
async def approve_reminder(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReminderResponse:
    try:
        return await ReminderService.approve_reminder(db, current_user.id, reminder_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{reminder_id}/dispatch",
    response_model=ReminderDispatchResult,
    status_code=status.HTTP_200_OK,
    summary="Dispatch approved reminder through delivery channel",
    description=(
        "Dispatches an approved reminder. If delivery channel (email or Zapier) is unconfigured, "
        "it records manual delivery acknowledgement without falsely claiming an email was sent."
    ),
)
async def dispatch_reminder(
    reminder_id: str,
    payload: Optional[ReminderDispatchRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReminderDispatchResult:
    try:
        override = payload.override_channel if payload else None
        return await ReminderService.dispatch_reminder(
            db=db,
            user_id=current_user.id,
            reminder_id=reminder_id,
            override_channel=override,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{reminder_id}/retry",
    response_model=ReminderDispatchResult,
    status_code=status.HTTP_200_OK,
    summary="Retry failed reminder dispatch",
)
async def retry_reminder(
    reminder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReminderDispatchResult:
    try:
        return await ReminderService.retry_failed_reminder(db, current_user.id, reminder_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/run-scheduler",
    status_code=status.HTTP_200_OK,
    summary="Trigger immediate background reminder scheduler cycle",
    description="Executes a safe, idempotent reminder evaluation pass across all active merchants.",
)
async def trigger_scheduler_cycle(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> dict:
    return await run_reminder_evaluation_cycle(db)

