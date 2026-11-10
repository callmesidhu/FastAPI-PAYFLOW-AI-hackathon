"""Receivables Analytics Service (Prompt 20).

Provides authoritative, timezone-aware database aggregations for accounts receivable:
- Standard aging buckets (0–7, 8–30, 31–60, 60+ days) citing underlying invoice numbers.
- Outstanding and overdue totals strictly isolated per currency (never mixed).
- Collections within a selectable period.
- Customer-grouped balances.
- Read-only AI financial intelligence with factual citations and guarded settlement estimates.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import get_logger
from app.models.enums import InvoiceStatus
from app.models.invoice import Invoice
from app.schemas.analytics import (
    AgingBucketDetail,
    AgingBuckets,
    AnalyticsAISummaryResponse,
    CurrencyAnalytics,
    CustomerBalance,
    ReceivablesAnalyticsResponse,
)

logger = get_logger("payflow.analytics_service")


def _get_tz_today(tz_str: Optional[str]) -> Tuple[date, str]:
    """Resolve today's date in user's timezone."""
    tz_name = tz_str.strip() if tz_str and tz_str.strip() else "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz_name = "UTC"
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date(), tz_name


class AnalyticsService:
    """Authoritative accounts receivable analytics engine."""

    @classmethod
    async def get_receivables_analytics(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        timezone_str: Optional[str] = "UTC",
    ) -> ReceivablesAnalyticsResponse:
        """Compute full receivables intelligence scoped strictly to authenticated user."""
        today, tz_disclosed = _get_tz_today(timezone_str)

        # Default period: last 30 days up to today
        if end_date:
            try:
                period_end = date.fromisoformat(end_date)
            except ValueError:
                period_end = today
        else:
            period_end = today

        if start_date:
            try:
                period_start = date.fromisoformat(start_date)
            except ValueError:
                period_start = period_end - timedelta(days=30)
        else:
            period_start = period_end - timedelta(days=30)

        # Fetch all user invoices
        cursor = db.invoices.find({"user_id": user_id})
        invoices: List[Invoice] = []
        async for doc in cursor:
            invoices.append(Invoice.model_validate(doc))

        if not invoices:
            return ReceivablesAnalyticsResponse(
                period_start=str(period_start),
                period_end=str(period_end),
                timezone=tz_disclosed,
                by_currency=[],
                customer_balances=[],
                has_data=False,
            )

        # Preload customer names from db.customers
        customer_lookup: Dict[str, Dict[str, str]] = {}
        cust_cursor = db.customers.find({"user_id": user_id})
        async for c_doc in cust_cursor:
            customer_lookup[c_doc["id"]] = {
                "name": c_doc["name"],
                "email": c_doc["email"],
            }

        # Per-currency accumulator structures
        curr_outstanding: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        curr_overdue: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        curr_collected: Dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        curr_open_count: Dict[str, int] = defaultdict(int)
        curr_overdue_count: Dict[str, int] = defaultdict(int)
        curr_paid_count: Dict[str, int] = defaultdict(int)

        # Aging buckets per currency: currency -> bucket_name -> (amount, count, invoice_numbers)
        aging_map: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
            lambda: {
                "0_7": {"amount": Decimal("0.00"), "count": 0, "invoices": []},
                "8_30": {"amount": Decimal("0.00"), "count": 0, "invoices": []},
                "31_60": {"amount": Decimal("0.00"), "count": 0, "invoices": []},
                "60_plus": {"amount": Decimal("0.00"), "count": 0, "invoices": []},
            }
        )

        # Customer balances: (customer_id, currency) -> info
        cust_balances: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {
                "outstanding": Decimal("0.00"),
                "overdue": Decimal("0.00"),
                "open_count": 0,
                "invoices": [],
            }
        )

        for inv in invoices:
            curr = inv.currency.value
            inv_total = inv.total
            due_d = inv.due_date
            if isinstance(due_d, str):
                due_d = date.fromisoformat(due_d)

            # Days overdue: positive if past due date
            days_overdue = (today - due_d).days
            is_overdue = inv.status == InvoiceStatus.OVERDUE or (
                inv.status in (InvoiceStatus.SENT, InvoiceStatus.UNPAID) and days_overdue > 0
            )

            # Check if paid in selected period
            if inv.status == InvoiceStatus.PAID and inv.paid_at:
                paid_d = inv.paid_at.date()
                if period_start <= paid_d <= period_end:
                    curr_collected[curr] += inv_total
                    curr_paid_count[curr] += 1

            # Check open/unpaid statuses
            is_open = inv.status in (
                InvoiceStatus.SENT,
                InvoiceStatus.UNPAID,
                InvoiceStatus.OVERDUE,
                InvoiceStatus.PENDING_APPROVAL,
            )

            if is_open:
                curr_outstanding[curr] += inv_total
                curr_open_count[curr] += 1

                # Update customer balance accumulator
                cb = cust_balances[(inv.customer_id, curr)]
                cb["outstanding"] += inv_total
                cb["open_count"] += 1
                cb["invoices"].append(inv.invoice_number)

                if is_overdue:
                    curr_overdue[curr] += inv_total
                    curr_overdue_count[curr] += 1
                    cb["overdue"] += inv_total

                    # Categorize into aging buckets
                    if days_overdue <= 7:
                        b = aging_map[curr]["0_7"]
                    elif days_overdue <= 30:
                        b = aging_map[curr]["8_30"]
                    elif days_overdue <= 60:
                        b = aging_map[curr]["31_60"]
                    else:
                        b = aging_map[curr]["60_plus"]

                    b["amount"] += inv_total
                    b["count"] += 1
                    b["invoices"].append(inv.invoice_number)
                elif days_overdue <= 0 and abs(days_overdue) <= 7:
                    # Due soon (within next 7 days): include in 0-7 day awareness bucket
                    b = aging_map[curr]["0_7"]
                    b["amount"] += inv_total
                    b["count"] += 1
                    b["invoices"].append(inv.invoice_number)

        # Build by_currency list
        by_currency_list: List[CurrencyAnalytics] = []
        all_active_currencies = sorted(
            list(
                set(curr_outstanding.keys())
                | set(curr_collected.keys())
                | {inv.currency.value for inv in invoices}
            )
        )

        for c in all_active_currencies:
            b_data = aging_map[c]
            buckets = AgingBuckets(
                bucket_0_7_days=AgingBucketDetail(
                    amount=f"{b_data['0_7']['amount']:.2f}",
                    count=b_data["0_7"]["count"],
                    invoice_numbers=b_data["0_7"]["invoices"],
                ),
                bucket_8_30_days=AgingBucketDetail(
                    amount=f"{b_data['8_30']['amount']:.2f}",
                    count=b_data["8_30"]["count"],
                    invoice_numbers=b_data["8_30"]["invoices"],
                ),
                bucket_31_60_days=AgingBucketDetail(
                    amount=f"{b_data['31_60']['amount']:.2f}",
                    count=b_data["31_60"]["count"],
                    invoice_numbers=b_data["31_60"]["invoices"],
                ),
                bucket_60_plus_days=AgingBucketDetail(
                    amount=f"{b_data['60_plus']['amount']:.2f}",
                    count=b_data["60_plus"]["count"],
                    invoice_numbers=b_data["60_plus"]["invoices"],
                ),
            )

            by_currency_list.append(
                CurrencyAnalytics(
                    currency=c,
                    total_outstanding=f"{curr_outstanding[c]:.2f}",
                    total_overdue=f"{curr_overdue[c]:.2f}",
                    total_collected_period=f"{curr_collected[c]:.2f}",
                    open_invoices_count=curr_open_count[c],
                    overdue_invoices_count=curr_overdue_count[c],
                    paid_invoices_count=curr_paid_count[c],
                    aging_buckets=buckets,
                )
            )

        # Build customer balances list
        customer_balances_list: List[CustomerBalance] = []
        for (c_id, c_curr), data in cust_balances.items():
            c_info = customer_lookup.get(c_id, {"name": "Client", "email": "client@example.com"})
            customer_balances_list.append(
                CustomerBalance(
                    customer_id=c_id,
                    customer_name=c_info["name"],
                    customer_email=c_info["email"],
                    currency=c_curr,
                    outstanding_amount=f"{data['outstanding']:.2f}",
                    overdue_amount=f"{data['overdue']:.2f}",
                    open_invoices_count=data["open_count"],
                    invoice_numbers=data["invoices"],
                )
            )

        # Sort customer balances descending by outstanding amount
        customer_balances_list.sort(key=lambda x: Decimal(x.outstanding_amount), reverse=True)

        return ReceivablesAnalyticsResponse(
            period_start=str(period_start),
            period_end=str(period_end),
            timezone=tz_disclosed,
            by_currency=by_currency_list,
            customer_balances=customer_balances_list,
            has_data=len(invoices) > 0,
        )

    @classmethod
    async def generate_ai_summary(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        currency_filter: Optional[str] = None,
        timezone_str: Optional[str] = "UTC",
    ) -> AnalyticsAISummaryResponse:
        """Generate read-only AI summary citing real invoice numbers and amounts.

        Strict requirements:
        - Cites exact invoice numbers (e.g. 'INV-2026-0001 ($500.00 USD)').
        - Never conflates different currencies.
        - Labels predictions strictly as estimates only if sufficient data exists.
        - Discloses when data is insufficient.
        """
        analytics = await cls.get_receivables_analytics(
            db=db,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            timezone_str=timezone_str,
        )

        analyzed_at = datetime.now(timezone.utc).isoformat()

        if not analytics.has_data or not analytics.by_currency:
            return AnalyticsAISummaryResponse(
                summary=(
                    "No invoice records were found in your accounts receivable ledger. "
                    "Once you create and dispatch invoices, portfolio analytics, aging schedules, "
                    "and collections velocity metrics will populate here."
                ),
                has_sufficient_data=False,
                insufficient_data_reason="Zero invoice records exist for authenticated user.",
                payment_velocity_estimate=None,
                by_currency=[],
                analyzed_at=analyzed_at,
            )

        # Filter by currency if requested
        filtered_currencies = analytics.by_currency
        if currency_filter:
            filtered_currencies = [c for c in filtered_currencies if c.currency == currency_filter.upper()]
            if not filtered_currencies:
                return AnalyticsAISummaryResponse(
                    summary=f"No receivables data found for requested currency '{currency_filter.upper()}'.",
                    has_sufficient_data=False,
                    insufficient_data_reason=f"No invoices found for currency {currency_filter.upper()}.",
                    payment_velocity_estimate=None,
                    by_currency=[],
                    analyzed_at=analyzed_at,
                )

        # Historical paid settlement check for velocity estimation guardrail
        cursor = db.invoices.find({"user_id": user_id, "status": InvoiceStatus.PAID})
        paid_invoices: List[Invoice] = []
        async for doc in cursor:
            paid_invoices.append(Invoice.model_validate(doc))

        velocity_estimate: Optional[str] = None
        if len(paid_invoices) >= 3:
            total_turnaround_days = 0
            valid_sample_count = 0
            for pi in paid_invoices:
                if pi.paid_at and pi.issue_date:
                    diff = (pi.paid_at.date() - pi.issue_date).days
                    if diff >= 0:
                        total_turnaround_days += diff
                        valid_sample_count += 1

            if valid_sample_count >= 3:
                avg_days = round(total_turnaround_days / valid_sample_count, 1)
                velocity_estimate = (
                    f"[ESTIMATE based on {valid_sample_count} settled invoices]: "
                    f"Historical payment turnaround averages {avg_days} days from issue date."
                )
        else:
            velocity_estimate = (
                "[INSUFFICIENT HISTORICAL DATA]: "
                "Predictive payment settlement velocity requires at least 3 settled invoices."
            )

        # Construct authoritative summary citing underlying invoices
        paragraphs: List[str] = []
        paragraphs.append(
            f"**Receivables Portfolio Intelligence (Period: {analytics.period_start} to {analytics.period_end}, Timezone: {analytics.timezone})**"
        )

        for curr_stat in filtered_currencies:
            c = curr_stat.currency
            paragraphs.append(
                f"\n### {c} Portfolio Position\n"
                f"- **Outstanding Balance**: ${curr_stat.total_outstanding} across {curr_stat.open_invoices_count} open invoice(s).\n"
                f"- **Overdue Balance**: ${curr_stat.total_overdue} across {curr_stat.overdue_invoices_count} overdue invoice(s).\n"
                f"- **Collections in Period**: ${curr_stat.total_collected_period} ({curr_stat.paid_invoices_count} paid)."
            )

            # Detail aging buckets with citations
            b = curr_stat.aging_buckets
            aging_lines: List[str] = []
            if b.bucket_60_plus_days.count > 0:
                inv_list = ", ".join(b.bucket_60_plus_days.invoice_numbers)
                aging_lines.append(
                    f"  - **60+ Days Overdue**: ${b.bucket_60_plus_days.amount} ({b.bucket_60_plus_days.count} invoice(s): {inv_list}) — *Critical attention required.*"
                )
            if b.bucket_31_60_days.count > 0:
                inv_list = ", ".join(b.bucket_31_60_days.invoice_numbers)
                aging_lines.append(
                    f"  - **31–60 Days Overdue**: ${b.bucket_31_60_days.amount} ({b.bucket_31_60_days.count} invoice(s): {inv_list}) — *Escalate polite reminders.*"
                )
            if b.bucket_8_30_days.count > 0:
                inv_list = ", ".join(b.bucket_8_30_days.invoice_numbers)
                aging_lines.append(
                    f"  - **8–30 Days Overdue**: ${b.bucket_8_30_days.amount} ({b.bucket_8_30_days.count} invoice(s): {inv_list})"
                )
            if b.bucket_0_7_days.count > 0:
                inv_list = ", ".join(b.bucket_0_7_days.invoice_numbers)
                aging_lines.append(
                    f"  - **0–7 Days Window**: ${b.bucket_0_7_days.amount} ({b.bucket_0_7_days.count} invoice(s): {inv_list})"
                )

            if aging_lines:
                paragraphs.append("**Aging Schedule & Invoice Citations:**\n" + "\n".join(aging_lines))
            else:
                paragraphs.append("*No invoices currently past due in this currency.*")

        # Top customer concentration
        relevant_cust_balances = [
            cb for cb in analytics.customer_balances
            if Decimal(cb.outstanding_amount) > 0 and (not currency_filter or cb.currency == currency_filter.upper())
        ]
        if relevant_cust_balances:
            cust_lines = [
                f"- **{cb.customer_name}**: ${cb.outstanding_amount} {cb.currency} (Invoices: {', '.join(cb.invoice_numbers)})"
                for cb in relevant_cust_balances[:5]
            ]
            paragraphs.append("\n**Top Customer Receivables Balances:**\n" + "\n".join(cust_lines))

        # Velocity note
        paragraphs.append(f"\n**Settlement Velocity Assessment:**\n{velocity_estimate}")

        summary_text = "\n".join(paragraphs)

        return AnalyticsAISummaryResponse(
            summary=summary_text,
            has_sufficient_data=True,
            insufficient_data_reason=None,
            payment_velocity_estimate=velocity_estimate,
            by_currency=[c.model_dump() for c in filtered_currencies],
            analyzed_at=analyzed_at,
        )

