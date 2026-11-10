"""Dashboard aggregate service.

Reconciles financial receivables metrics authoritatively from database records,
guarantees per-currency isolation (never mixing currencies), identifies
attention-needed items with customer names enriched, and computes historical
collections velocity when sufficient data exists.
"""

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice, utc_now
from app.models.money import serialize_decimal, to_decimal
from app.schemas.dashboard import CurrencySummary, DashboardSummaryResponse, TrendItem
from app.schemas.invoice import InvoiceResponse


async def get_dashboard_summary(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> DashboardSummaryResponse:
    """Compute receivables summary scoped strictly to the authenticated user."""
    today_str = str(utc_now().date())
    now = utc_now()
    current_year = now.year
    current_month = now.month

    # Retrieve all invoices for this user
    cursor = db.invoices.find({"user_id": user_id})
    invoices: List[Invoice] = []
    async for doc in cursor:
        invoices.append(Invoice.model_validate(doc))

    total_invoices = len(invoices)
    draft_count = 0
    pending_approval_count = 0
    sent_count = 0
    paid_count = 0
    overdue_count = 0

    # Per-currency accumulator maps
    outstanding_by_curr: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    overdue_by_curr: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    collected_month_by_curr: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))

    # Active currencies encountered
    active_currencies = set()

    attention_candidates: List[Invoice] = []

    # Track historical collections for trend calculation
    monthly_collections: Dict[tuple, Decimal] = defaultdict(lambda: Decimal("0.00"))

    for inv in invoices:
        curr = inv.currency.value
        active_currencies.add(curr)
        inv_total = inv.total
        is_overdue = inv.status == InvoiceStatus.OVERDUE or (
            inv.status in (InvoiceStatus.SENT, InvoiceStatus.UNPAID) and str(inv.due_date) < today_str
        )

        if inv.status == InvoiceStatus.DRAFT:
            draft_count += 1
        elif inv.status == InvoiceStatus.PENDING_APPROVAL:
            pending_approval_count += 1
            outstanding_by_curr[curr] += inv_total
            attention_candidates.append(inv)
        elif inv.status == InvoiceStatus.SENT or inv.status == InvoiceStatus.UNPAID:
            sent_count += 1
            outstanding_by_curr[curr] += inv_total
            if is_overdue:
                overdue_count += 1
                overdue_by_curr[curr] += inv_total
                attention_candidates.append(inv)
        elif inv.status == InvoiceStatus.OVERDUE:
            overdue_count += 1
            outstanding_by_curr[curr] += inv_total
            overdue_by_curr[curr] += inv_total
            attention_candidates.append(inv)
        elif inv.status == InvoiceStatus.PAID:
            paid_count += 1
            if inv.paid_at:
                if inv.paid_at.year == current_year and inv.paid_at.month == current_month:
                    collected_month_by_curr[curr] += inv_total
                period_str = inv.paid_at.strftime("%Y-%m")
                monthly_collections[(period_str, curr)] += inv_total

    # Build currency summary list — strictly separated per currency
    currency_summaries: List[CurrencySummary] = []
    # If no invoices yet, provide a clean default USD summary
    if not active_currencies:
        currency_summaries.append(
            CurrencySummary(
                currency="USD",
                outstanding="0.00",
                overdue="0.00",
                collected_this_month="0.00",
            )
        )
    else:
        for curr in sorted(active_currencies):
            currency_summaries.append(
                CurrencySummary(
                    currency=curr,
                    outstanding=serialize_decimal(outstanding_by_curr[curr]),
                    overdue=serialize_decimal(overdue_by_curr[curr]),
                    collected_this_month=serialize_decimal(collected_month_by_curr[curr]),
                )
            )

    # Sort attention needed items by due date ascending
    attention_candidates.sort(key=lambda x: str(x.due_date))

    # Sort recent invoices by created_at descending
    sorted_recent = sorted(invoices, key=lambda x: x.created_at, reverse=True)

    # Batch-load customer names for attention and recent items
    customer_ids = {
        inv.customer_id
        for inv in (attention_candidates[:5] + sorted_recent[:5])
        if inv.customer_id
    }
    customer_map: Dict[str, str] = {}
    if customer_ids:
        c_cursor = db.customers.find({"id": {"$in": list(customer_ids)}, "user_id": user_id})
        async for c in c_cursor:
            customer_map[c.get("id")] = c.get("name")

    attention_needed: List[InvoiceResponse] = []
    for inv in attention_candidates[:5]:
        resp = InvoiceResponse.model_validate(inv)
        resp.customer_name = customer_map.get(inv.customer_id)
        attention_needed.append(resp)

    recent_invoices: List[InvoiceResponse] = []
    for inv in sorted_recent[:5]:
        resp = InvoiceResponse.model_validate(inv)
        resp.customer_name = customer_map.get(inv.customer_id)
        recent_invoices.append(resp)

    # Collections trend requires at least 3 distinct periods (months)
    distinct_periods = {period for (period, _) in monthly_collections.keys()}
    has_trend_data = len(distinct_periods) >= 3
    collections_trend: List[TrendItem] = []

    if has_trend_data:
        for (period, curr) in sorted(monthly_collections.keys()):
            collections_trend.append(
                TrendItem(
                    period=period,
                    amount=serialize_decimal(monthly_collections[(period, curr)]),
                    currency=curr,
                )
            )

    return DashboardSummaryResponse(
        total_invoices=total_invoices,
        draft_count=draft_count,
        pending_approval_count=pending_approval_count,
        sent_count=sent_count,
        paid_count=paid_count,
        overdue_count=overdue_count,
        by_currency=currency_summaries,
        attention_needed=attention_needed,
        recent_invoices=recent_invoices,
        collections_trend=collections_trend,
        has_trend_data=has_trend_data,
    )
