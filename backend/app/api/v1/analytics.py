"""Receivables Analytics & Financial Intelligence Endpoints (Prompt 20)."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit_ai_dependency
from app.db.mongodb import get_db
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsAISummaryRequest,
    AnalyticsAISummaryResponse,
    ReceivablesAnalyticsResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Receivables Analytics"])


@router.get(
    "/receivables",
    response_model=ReceivablesAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get authoritative receivables analytics",
    description=(
        "Returns timezone-aware receivables metrics: standard aging buckets (0–7, 8–30, 31–60, 60+ days) "
        "citing invoice numbers, per-currency totals (never mixed), period collections, and customer balances."
    ),
)
async def get_receivables_analytics(
    start_date: Optional[str] = Query(default=None, description="Period start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="Period end date YYYY-MM-DD"),
    timezone: Optional[str] = Query(default="UTC", description="User timezone (e.g. America/New_York, UTC)"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ReceivablesAnalyticsResponse:
    return await AnalyticsService.get_receivables_analytics(
        db=db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        timezone_str=timezone,
    )


@router.post(
    "/ai-summary",
    response_model=AnalyticsAISummaryResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(rate_limit_ai_dependency)],
    summary="Generate read-only AI receivables intelligence summary",
    description=(
        "Generates an authoritative executive analysis of receivables backed strictly by actual database "
        "aggregates. Cites exact invoice numbers and balances, keeps currencies distinct, states when data is "
        "insufficient, and labels any payment velocity projection strictly as an estimate."
    ),
)
async def get_analytics_ai_summary(
    payload: AnalyticsAISummaryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AnalyticsAISummaryResponse:
    return await AnalyticsService.generate_ai_summary(
        db=db,
        user_id=current_user.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        currency_filter=payload.currency,
        timezone_str=payload.timezone or "UTC",
    )

