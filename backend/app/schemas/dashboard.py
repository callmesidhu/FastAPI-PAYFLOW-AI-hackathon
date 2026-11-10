"""Pydantic response schemas for Dashboard aggregates and summaries."""

from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.invoice import InvoiceResponse


class CurrencySummary(BaseModel):
    """Monetary summary for a single ISO currency to prevent cross-currency summation."""

    currency: str
    outstanding: str
    overdue: str
    collected_this_month: str


class TrendItem(BaseModel):
    """Historical collections data point."""

    period: str
    amount: str
    currency: str


class DashboardSummaryResponse(BaseModel):
    """Dashboard aggregate summary scoped strictly to the authenticated user."""

    model_config = ConfigDict(from_attributes=True)

    # Invoice Counts
    total_invoices: int
    draft_count: int
    pending_approval_count: int
    sent_count: int
    paid_count: int
    overdue_count: int

    # Currencies are separated strictly — never summed across different ISO currencies
    by_currency: List[CurrencySummary]

    # Quick Action Lists
    attention_needed: List[InvoiceResponse]
    recent_invoices: List[InvoiceResponse]

    # Collections Trend (empty if insufficient history)
    collections_trend: List[TrendItem]
    has_trend_data: bool
