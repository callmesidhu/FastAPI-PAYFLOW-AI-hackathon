"""Allowlisted application tools available to the AI Assistant.

Rules:
1. Tools must call application domain services, NEVER raw database queries.
2. Every tool strictly enforces current user_id scoping.
3. Arguments are schema-validated using Pydantic.
4. Tools NEVER approve or execute PayPal operations directly.
5. Inbound/external strings are sanitized for secret scrubbing and injection defense.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.agents.security import scrub_secrets, wrap_untrusted_content
from app.models.enums import InvoiceStatus
from app.models.invoice import InvoiceItem
from app.schemas.ai import (
    CreateInvoiceDraftArgs,
    GetInvoiceDetailArgs,
    GetOverdueInvoicesArgs,
    GetReceivablesSummaryArgs,
    ListInvoicesArgs,
    PrepareReminderDraftArgs,
    RequestApprovalArgs,
    SearchCustomersArgs,
)
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate
from app.services import (
    customer_service,
    dashboard_service,
    invoice_service,
)


async def tool_search_customers(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Search the user's customers by name, email, or company."""
    parsed = SearchCustomersArgs.model_validate(args)
    query = scrub_secrets(parsed.query.strip())
    if query.lower() in ("all", "*", ""):
        query = ""

    result = await customer_service.list_customers(
        db=db,
        user_id=user_id,
        search=query if query else None,
        page_size=10,
    )

    customers_data = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "company": c.company or "",
            "active_invoices": c.active_invoice_count,
        }
        for c in result.items
    ]
    return {
        "count": len(customers_data),
        "total": result.total,
        "customers": customers_data,
    }


async def tool_create_invoice_draft(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Create a draft invoice via the invoice domain service."""
    parsed = CreateInvoiceDraftArgs.model_validate(args)

    # 1. Resolve customer
    cust_query = scrub_secrets(parsed.customer_name_or_id.strip())
    customers_res = await customer_service.list_customers(
        db=db,
        user_id=user_id,
        search=cust_query,
        page_size=5,
    )

    customer_id = None
    customer_name = cust_query
    if customers_res.items:
        # Match exact ID or best name match
        for c in customers_res.items:
            if c.id == cust_query or c.name.lower() == cust_query.lower():
                customer_id = c.id
                customer_name = c.name
                break
        if not customer_id:
            customer_id = customers_res.items[0].id
            customer_name = customers_res.items[0].name
    else:
        # Auto-create customer record if it doesn't exist
        email_cand = f"{cust_query.lower().replace(' ', '.')}@example.com"
        new_cust = await customer_service.create_customer(
            db=db,
            user_id=user_id,
            payload=CustomerCreate(
                name=cust_query,
                email=email_cand,
            ),
        )
        customer_id = new_cust.id
        customer_name = new_cust.name

    # 2. Determine due date
    issue_date = date.today()
    if parsed.due_date:
        due_date = date.fromisoformat(parsed.due_date)
    else:
        due_date = issue_date + timedelta(days=parsed.due_in_days or 14)

    # 3. Build line items
    items_to_create = [
        InvoiceItemCreate(
            name=scrub_secrets(it.name),
            description=scrub_secrets(it.description) if it.description else None,
            quantity=it.quantity,
            unit_price=it.unit_price,
            tax=it.tax,
        )
        for it in parsed.items
    ]

    # 4. Create authoritative draft through invoice_service
    invoice_payload = InvoiceCreate(
        customer_id=customer_id,
        items=items_to_create,
        currency=parsed.currency.upper(),
        issue_date=issue_date,
        due_date=due_date,
        notes=scrub_secrets(parsed.notes) if parsed.notes else None,
    )

    created = await invoice_service.create_invoice_draft(
        db=db,
        user_id=user_id,
        payload=invoice_payload,
    )

    def _val(v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)

    return {
        "invoice_id": created.internal_id,
        "invoice_number": created.invoice_number,
        "customer_name": customer_name,
        "customer_id": customer_id,
        "subtotal": str(created.subtotal),
        "tax": str(created.tax),
        "total": str(created.total),
        "currency": _val(created.currency),
        "issue_date": str(created.issue_date),
        "due_date": str(created.due_date),
        "status": _val(created.status),
        "message": f"Draft invoice {created.invoice_number} created for {customer_name}.",
    }


async def tool_list_invoices(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Retrieve invoices scoped to user with optional status filter."""
    parsed = ListInvoicesArgs.model_validate(args)

    result = await invoice_service.list_invoices(
        db=db,
        user_id=user_id,
        status_filter=parsed.status,
        page_size=parsed.limit,
    )

    items = [
        {
            "id": inv.internal_id,
            "invoice_number": inv.invoice_number,
            "customer_name": inv.customer_name or "Client",
            "total": str(inv.total),
            "currency": inv.currency.value if hasattr(inv.currency, "value") else str(inv.currency),
            "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            "due_date": str(inv.due_date),
            "paypal_invoice_id": inv.paypal_invoice_id,
        }
        for inv in result.items
    ]
    return {
        "count": len(items),
        "total": result.total,
        "invoices": items,
    }


async def tool_get_overdue_invoices(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Retrieve past-due unpaid invoices."""
    _ = GetOverdueInvoicesArgs.model_validate(args)
    today = date.today()

    result = await invoice_service.list_invoices(
        db=db,
        user_id=user_id,
        due_date_before=today,
        page_size=20,
    )

    # Filter to unpaid/sent/overdue
    overdue_items = [
        {
            "id": inv.internal_id,
            "invoice_number": inv.invoice_number,
            "customer_name": inv.customer_name or "Client",
            "total": str(inv.total),
            "currency": inv.currency.value if hasattr(inv.currency, "value") else str(inv.currency),
            "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            "due_date": str(inv.due_date),
            "days_overdue": (today - inv.due_date).days,
        }
        for inv in result.items
        if inv.status in (InvoiceStatus.SENT, InvoiceStatus.UNPAID, InvoiceStatus.OVERDUE)
    ]
    return {
        "count": len(overdue_items),
        "overdue_invoices": overdue_items,
    }


async def tool_get_invoice_detail(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Retrieve full details for an invoice by number or ID."""
    parsed = GetInvoiceDetailArgs.model_validate(args)
    ref = scrub_secrets(parsed.invoice_ref.strip())

    # Try lookup by internal_id first, then invoice_number
    inv = await db.invoices.find_one({"internal_id": ref, "user_id": user_id})
    if not inv:
        inv = await db.invoices.find_one({"invoice_number": ref, "user_id": user_id})

    if not inv:
        return {"error": f"Invoice '{ref}' not found."}

    detail = await invoice_service.get_invoice_by_id(db, user_id, inv["internal_id"])
    return {
        "invoice_id": detail.internal_id,
        "invoice_number": detail.invoice_number,
        "customer_name": detail.customer_name,
        "status": detail.status.value if hasattr(detail.status, "value") else str(detail.status),
        "total": str(detail.total),
        "currency": detail.currency.value if hasattr(detail.currency, "value") else str(detail.currency),
        "issue_date": str(detail.issue_date),
        "due_date": str(detail.due_date),
        "paypal_invoice_id": detail.paypal_invoice_id,
        "paypal_invoice_url": detail.paypal_invoice_url,
        "items": [
            {
                "name": it.name,
                "quantity": str(it.quantity),
                "unit_price": str(it.unit_price),
                "total": str(it.total),
            }
            for it in detail.items
        ],
    }


async def tool_prepare_reminder_draft(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Draft payment reminder message without executing dispatch."""
    parsed = PrepareReminderDraftArgs.model_validate(args)
    ref = scrub_secrets(parsed.invoice_ref.strip())

    inv = await db.invoices.find_one({"internal_id": ref, "user_id": user_id})
    if not inv:
        inv = await db.invoices.find_one({"invoice_number": ref, "user_id": user_id})
    if not inv:
        return {"error": f"Invoice '{ref}' not found."}

    cust = await db.customers.find_one({"id": inv["customer_id"], "user_id": user_id})
    cust_name = cust.get("name", "Client") if cust else "Client"

    today = date.today()
    due_date = inv["due_date"]
    if isinstance(due_date, str):
        due_date = date.fromisoformat(due_date)

    days_overdue = max(0, (today - due_date).days)
    tone = (parsed.tone or "courteous").lower()

    if tone == "urgent" or days_overdue > 14:
        subject = f"URGENT: Outstanding Balance for {inv['invoice_number']}"
        body = (
            f"Dear {cust_name},\n\n"
            f"This is an urgent follow-up regarding invoice {inv['invoice_number']} for ${inv['total']} {inv['currency']}, "
            f"which was due on {due_date} ({days_overdue} days past due).\n\n"
            f"Please arrange payment at your earliest convenience via the PayPal payment link provided.\n\n"
            f"Warm regards,\nAccounts Receivable"
        )
    elif tone == "firm" or days_overdue > 3:
        subject = f"Past Due Reminder: Invoice {inv['invoice_number']}"
        body = (
            f"Dear {cust_name},\n\n"
            f"We are writing to check on the status of invoice {inv['invoice_number']} for ${inv['total']} {inv['currency']}. "
            f"Payment was due on {due_date}. Please review and settle this balance.\n\n"
            f"Thank you,\nAccounts Receivable"
        )
    else:
        subject = f"Friendly Reminder: Invoice {inv['invoice_number']}"
        body = (
            f"Dear {cust_name},\n\n"
            f"This is a gentle reminder that invoice {inv['invoice_number']} for ${inv['total']} {inv['currency']} "
            f"is due on {due_date}. Please let us know if you have any questions.\n\n"
            f"Best regards,\nAccounts Receivable"
        )

    return {
        "invoice_id": inv["internal_id"],
        "invoice_number": inv["invoice_number"],
        "customer_name": cust_name,
        "days_overdue": days_overdue,
        "tone": tone,
        "subject": subject,
        "body": body,
        "preview_note": "Reminder draft generated. Human authorization required before dispatch.",
    }


async def tool_get_receivables_summary(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Retrieve aggregate receivables metrics for the user."""
    _ = GetReceivablesSummaryArgs.model_validate(args)
    summary = await dashboard_service.get_dashboard_summary(db=db, user_id=user_id)

    primary = summary.by_currency[0] if summary.by_currency else None
    return {
        "total_outstanding": primary.outstanding if primary else "0.00",
        "total_overdue": primary.overdue if primary else "0.00",
        "collected_this_month": primary.collected_this_month if primary else "0.00",
        "invoice_count": summary.total_invoices,
        "attention_needed_count": len(summary.attention_needed),
        "by_currency": [c.model_dump() for c in summary.by_currency],
    }


async def tool_request_approval(
    user_id: str,
    args: Dict[str, Any],
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    """Submit an invoice for human authorization in the Approval Center."""
    parsed = RequestApprovalArgs.model_validate(args)
    invoice_id = scrub_secrets(parsed.invoice_id.strip())

    res = await invoice_service.submit_for_approval(
        db=db,
        user_id=user_id,
        invoice_id=invoice_id,
    )

    return {
        "approval_id": res.approval_id,
        "invoice_id": invoice_id,
        "invoice_number": res.invoice.invoice_number,
        "status": res.status,
        "payload_hash": res.payload_hash,
        "message": res.message,
    }


# Map of allowlisted tools
ALLOWLISTED_TOOLS = {
    "search_customers": tool_search_customers,
    "create_invoice_draft": tool_create_invoice_draft,
    "list_invoices": tool_list_invoices,
    "get_overdue_invoices": tool_get_overdue_invoices,
    "get_invoice_detail": tool_get_invoice_detail,
    "prepare_reminder_draft": tool_prepare_reminder_draft,
    "get_receivables_summary": tool_get_receivables_summary,
    "request_approval": tool_request_approval,
}
