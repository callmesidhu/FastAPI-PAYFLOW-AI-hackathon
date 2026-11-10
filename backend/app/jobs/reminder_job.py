"""Background Reminder Scheduler (Prompt 22).

Architecture & Deployment Invariants:
- Designed for single-instance hackathon deployment (e.g. Render Web Service).
- In-memory schedulers can duplicate or miss jobs if multiple replicas run.
  To guarantee safety across any number of instances:
  1. MongoDB compound unique index on (invoice_id, stage) prevents duplicate reminders.
  2. The scheduler strictly prepares drafts in 'ready_for_approval' status.
  3. No communications are EVER dispatched silently or without explicit merchant approval.
"""

import asyncio
from datetime import date
from typing import Any, Callable, Coroutine, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import get_logger
from app.services.reminder_service import ReminderService

logger = get_logger("payflow.reminder_scheduler")

_scheduler_task: Optional[asyncio.Task] = None
_stop_event = asyncio.Event()


async def run_reminder_evaluation_cycle(
    db: AsyncIOMotorDatabase,
    reference_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Execute a single evaluation pass across all active merchants.

    Identifies due reminder candidates and creates drafts in 'ready_for_approval' status.
    Database-backed idempotency (invoice_id, stage) prevents duplicate drafts across runs.
    """
    logger.info("Starting background reminder evaluation pass...")
    cursor = db.users.find({"is_active": True})
    total_users = 0
    total_drafts_created = 0
    total_skipped = 0

    async for user_doc in cursor:
        total_users += 1
        user_id = user_doc["id"]
        try:
            result = await ReminderService.evaluate_and_create_reminders(
                db=db,
                user_id=user_id,
                reference_date=reference_date,
            )
            total_drafts_created += result.drafts_created_count
            total_skipped += result.skipped_existing_count
        except Exception as e:
            logger.error(f"Error evaluating reminders for user {user_id}: {e}")

    summary = {
        "status": "completed",
        "users_evaluated": total_users,
        "drafts_created": total_drafts_created,
        "skipped_existing": total_skipped,
    }
    logger.info(f"Reminder evaluation pass completed: {summary}")
    return summary


async def _background_scheduler_loop(
    db_getter: Callable[[], Coroutine[Any, Any, AsyncIOMotorDatabase]],
    interval_seconds: int = 3600,
):
    """Background polling loop executing reminder evaluations on interval."""
    logger.info(f"Reminder background scheduler initialized (interval: {interval_seconds}s).")
    while not _stop_event.is_set():
        try:
            db = await db_getter()
            if db is not None:
                await run_reminder_evaluation_cycle(db)
        except Exception as e:
            logger.error(f"Unexpected error in reminder scheduler loop: {e}")

        try:
            # Wait for interval or stop event
            await asyncio.wait_for(_stop_event.wait(), timeout=float(interval_seconds))
        except asyncio.TimeoutError:
            pass


def start_scheduler(
    db_getter: Callable[[], Coroutine[Any, Any, AsyncIOMotorDatabase]],
    interval_seconds: int = 3600,
):
    """Start background scheduler task if not already running."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _stop_event.clear()
        _scheduler_task = asyncio.create_task(
            _background_scheduler_loop(db_getter, interval_seconds=interval_seconds)
        )
        logger.info("Reminder background scheduler task started.")


def stop_scheduler():
    """Signal background scheduler to stop cleanly."""
    global _scheduler_task
    _stop_event.set()
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        logger.info("Reminder background scheduler stopped.")
    _scheduler_task = None

