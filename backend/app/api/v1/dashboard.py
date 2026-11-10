"""Dashboard summary API endpoints."""

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.api.deps import get_current_user
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummaryResponse
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    summary="Get Dashboard Receivables Summary",
    description="Calculates reconciled receivables aggregates, per-currency totals, and attention-needed items strictly scoped to the authenticated user.",
)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> DashboardSummaryResponse:
    return await dashboard_service.get_dashboard_summary(db, current_user.id)
