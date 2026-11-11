"""Domain enumerations for PAYFLOW AI.

Defines invoice statuses, allowed transitions, approval workflows,
reminder stages, currencies, and actors.
"""

from enum import Enum
from typing import Dict, Set


class SupportedCurrency(str, Enum):
    """Supported ISO 4217 currencies supported by PayPal REST Invoicing."""

    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"
    CHF = "CHF"
    SGD = "SGD"
    NZD = "NZD"
    INR = "INR"


class InvoiceStatus(str, Enum):
    """Lifecycle statuses for invoices in PAYFLOW AI."""

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    CREATED = "created"
    SENT = "sent"
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"
    FAILED = "failed"


# Allowed state transitions enforcing business rules
# Invariant: Terminal states (PAID, CANCELLED) cannot transition to any other status
ALLOWED_INVOICE_TRANSITIONS: Dict[InvoiceStatus, Set[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: {
        InvoiceStatus.PENDING_APPROVAL,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.PENDING_APPROVAL: {
        InvoiceStatus.DRAFT,
        InvoiceStatus.CREATED,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.CREATED: {
        InvoiceStatus.SENT,
        InvoiceStatus.FAILED,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.SENT: {
        InvoiceStatus.UNPAID,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.CANCELLED,
        InvoiceStatus.FAILED,
    },
    InvoiceStatus.UNPAID: {
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.PARTIALLY_PAID: {
        InvoiceStatus.PAID,
        InvoiceStatus.OVERDUE,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.OVERDUE: {
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.FAILED: {
        InvoiceStatus.DRAFT,  # Can revert to draft for correction
        InvoiceStatus.CANCELLED,
    },
    InvoiceStatus.PAID: set(),  # Terminal state
    InvoiceStatus.CANCELLED: set(),  # Terminal state
}


def can_transition_invoice(current: InvoiceStatus, target: InvoiceStatus) -> bool:
    """Validate whether an invoice transition is permissible."""
    if current == target:
        return True
    allowed = ALLOWED_INVOICE_TRANSITIONS.get(current, set())
    return target in allowed


class ApprovalStatus(str, Enum):
    """Status for human authorization decisions."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"  # Invalidated if underlying payload changes after approval


class ActionType(str, Enum):
    """Categorized operations subject to human authorization."""

    CREATE_PAYPAL_INVOICE = "create_paypal_invoice"
    SEND_PAYPAL_INVOICE = "send_paypal_invoice"
    SEND_PAYMENT_REMINDER = "send_payment_reminder"
    SEND_REMINDER = "send_payment_reminder"  # Backwards-compatible alias
    CANCEL_PAYPAL_INVOICE = "cancel_paypal_invoice"


class ReminderStage(str, Enum):
    """Deterministic reminder policy stages."""

    UPCOMING = "upcoming"  # e.g., 1 day before due date
    DUE_TODAY = "due_today"  # On due date
    OVERDUE_1_3 = "overdue_1_3"  # 1-3 days overdue
    OVERDUE_4_7 = "overdue_4_7"  # 4-7 days overdue
    OVERDUE_8_14 = "overdue_8_14"  # 8-14 days overdue
    OVERDUE_15_PLUS = "overdue_15_plus"  # 15+ days overdue


class ReminderStatus(str, Enum):
    """Status of a reminder notification."""

    DRAFT = "draft"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    DISMISSED = "dismissed"


class ActorType(str, Enum):
    """Identity type triggering an action."""

    USER = "user"
    SYSTEM = "system"
    AI_ASSISTANT = "ai_assistant"
    PAYPAL_WEBHOOK = "paypal_webhook"
