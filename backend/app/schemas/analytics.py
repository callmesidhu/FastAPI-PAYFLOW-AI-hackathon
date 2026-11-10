"""Pydantic schemas for Receivables Analytics and read-only AI financial intelligence.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgingBucketDetail(BaseModel):
    """Details for a specific aging bucket."""

    amount: str = Field(..., description="Decimal-formatted string of outstanding amount in bucket")
    count: int = Field(..., description="Number of unpaid invoices in this bucket")
    invoice_numbers: List[str] = Field(default_factory=list, description="List of cited invoice numbers")


class AgingBuckets(BaseModel):
    """Breakdown of overdue invoices into standard AR aging buckets."""

    bucket_0_7_days: AgingBucketDetail = Field(..., description="Due in 0-7 days or 0-7 days past due")
    bucket_8_30_days: AgingBucketDetail = Field(..., description="8 to 30 days past due")
    bucket_31_60_days: AgingBucketDetail = Field(..., description="31 to 60 days past due")
    bucket_60_plus_days: AgingBucketDetail = Field(..., description="61+ days past due")


class CurrencyAnalytics(BaseModel):
    """Aggregate AR metrics strictly isolated per currency (never conflated)."""

    currency: str = Field(..., description="ISO 4217 currency code")
    total_outstanding: str = Field(..., description="Outstanding unpaid balance")
    total_overdue: str = Field(..., description="Overdue unpaid balance")
    total_collected_period: str = Field(..., description="Total collected during selected period")
    open_invoices_count: int = Field(..., description="Number of open / sent / draft invoices")
    overdue_invoices_count: int = Field(..., description="Number of overdue invoices")
    paid_invoices_count: int = Field(..., description="Number of paid invoices in period")
    aging_buckets: AgingBuckets


class CustomerBalance(BaseModel):
    """Outstanding balance grouped by customer and currency."""

    customer_id: str
    customer_name: str
    customer_email: str
    currency: str
    outstanding_amount: str
    overdue_amount: str
    open_invoices_count: int
    invoice_numbers: List[str] = Field(default_factory=list)


class ReceivablesAnalyticsResponse(BaseModel):
    """Comprehensive receivables analytics response backed by authoritative aggregates."""

    period_start: str
    period_end: str
    timezone: str
    by_currency: List[CurrencyAnalytics] = Field(default_factory=list)
    customer_balances: List[CustomerBalance] = Field(default_factory=list)
    has_data: bool = False


class AnalyticsAISummaryRequest(BaseModel):
    """Request for read-only AI analysis of receivables."""

    start_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD")
    end_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD")
    currency: Optional[str] = Field(default=None, description="Optional ISO currency filter")
    timezone: Optional[str] = Field(default="UTC", description="Timezone for aging calculations")


class AnalyticsAISummaryResponse(BaseModel):
    """Authoritative AI analysis citing exact invoice numbers and amounts."""

    summary: str = Field(..., description="AI narrative citing exact invoice numbers and balances")
    has_sufficient_data: bool = True
    insufficient_data_reason: Optional[str] = None
    payment_velocity_estimate: Optional[str] = Field(
        default=None,
        description="Explicitly labeled estimate of payment turnaround days, or null if insufficient history",
    )
    by_currency: List[Dict[str, Any]] = Field(default_factory=list)
    analyzed_at: str

