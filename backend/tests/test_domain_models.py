"""Tests for domain models, Decimal money precision, status transitions, and user scoping."""

from datetime import date, datetime
from decimal import Decimal
import json
import pytest
from pydantic import ValidationError

from app.models.enums import InvoiceStatus, SupportedCurrency, can_transition_invoice
from app.models.money import to_decimal, validate_currency_code
from app.models.invoice import Invoice, InvoiceItem
from app.models.customer import Customer
from app.models.approval import Approval, compute_payload_hash
from app.models.reminder import Reminder, ReminderStage
from app.models.transaction import Transaction
from app.models.audit import AuditLog


def test_money_decimal_roundtrip_precision():
    """Verify that financial addition avoids binary float distortion (0.1 + 0.2 = 0.3)."""
    amount1 = to_decimal("0.10")
    amount2 = to_decimal("0.20")
    total = amount1 + amount2

    # Exact Decimal arithmetic
    assert total == Decimal("0.30")
    assert str(total) == "0.30"

    # Contrast against floating point error: 0.1 + 0.2 in floats produces 0.30000000000000004
    assert 0.1 + 0.2 != 0.3
    assert Decimal("0.10") + Decimal("0.20") == Decimal("0.30")


def test_invoice_authoritative_calculation_and_json_serialization():
    """Verify server-side authoritative Decimal calculations and clean JSON serialization."""
    item1 = InvoiceItem(
        name="Backend Development",
        quantity=Decimal("10.5"),
        unit_price=Decimal("100.00"),
        tax=Decimal("10.50"),
    )
    # Line total = 10.5 * 100 + 10.50 = 1050 + 10.50 = 1060.50
    assert item1.total == Decimal("1060.50")

    invoice = Invoice(
        user_id="user-12345",
        customer_id="cust-67890",
        invoice_number="INV-2026-001",
        items=[item1],
        currency=SupportedCurrency.USD,
        issue_date=date(2026, 11, 10),
        due_date=date(2026, 11, 24),
    )

    assert invoice.subtotal == Decimal("1050.00")
    assert invoice.tax == Decimal("10.50")
    assert invoice.total == Decimal("1060.50")

    # Serialize to JSON and verify format
    json_str = invoice.model_dump_json()
    data = json.loads(json_str)

    assert data["total"] == "1060.50"
    assert data["subtotal"] == "1050.00"
    assert data["tax"] == "10.50"
    assert data["issue_date"] == "2026-11-10"
    assert data["due_date"] == "2026-11-24"


def test_negative_amounts_are_rejected():
    """Negative unit prices, taxes, and quantities must be rejected."""
    with pytest.raises(ValidationError):
        InvoiceItem(name="Invalid Item", unit_price=Decimal("-10.00"))

    with pytest.raises(ValidationError):
        InvoiceItem(name="Invalid Tax", unit_price=Decimal("10.00"), tax=Decimal("-1.00"))

    with pytest.raises(ValidationError):
        InvoiceItem(name="Invalid Quantity", unit_price=Decimal("10.00"), quantity=Decimal("0.00"))


def test_unsupported_currency_codes_are_rejected():
    """Invalid currency codes must raise a descriptive validation error."""
    with pytest.raises(ValueError) as exc:
        validate_currency_code("XYZ")
    assert "Unsupported currency code 'XYZ'" in str(exc.value)

    # Valid currency
    assert validate_currency_code("USD") == "USD"
    assert validate_currency_code("eur") == "EUR"


def test_invoice_status_transition_rules():
    """Verify enforced state machine transitions."""
    # Permissible flow
    assert can_transition_invoice(InvoiceStatus.DRAFT, InvoiceStatus.PENDING_APPROVAL) is True
    assert can_transition_invoice(InvoiceStatus.PENDING_APPROVAL, InvoiceStatus.CREATED) is True
    assert can_transition_invoice(InvoiceStatus.CREATED, InvoiceStatus.SENT) is True
    assert can_transition_invoice(InvoiceStatus.SENT, InvoiceStatus.PAID) is True

    # Forbidden direct jumps
    assert can_transition_invoice(InvoiceStatus.DRAFT, InvoiceStatus.PAID) is False
    assert can_transition_invoice(InvoiceStatus.DRAFT, InvoiceStatus.SENT) is False
    assert can_transition_invoice(InvoiceStatus.PENDING_APPROVAL, InvoiceStatus.PAID) is False

    # Terminal states (Paid, Cancelled cannot transition)
    assert can_transition_invoice(InvoiceStatus.PAID, InvoiceStatus.DRAFT) is False
    assert can_transition_invoice(InvoiceStatus.PAID, InvoiceStatus.SENT) is False
    assert can_transition_invoice(InvoiceStatus.CANCELLED, InvoiceStatus.DRAFT) is False


def test_invoice_model_transition_method():
    """Verify transition_status method updates status and sets timestamps."""
    invoice = Invoice(
        user_id="user-12345",
        customer_id="cust-67890",
        invoice_number="INV-2026-002",
        items=[InvoiceItem(name="Design", unit_price=Decimal("50.00"))],
        due_date=date(2026, 11, 20),
    )
    assert invoice.status == InvoiceStatus.DRAFT

    # Transition to pending_approval
    invoice.transition_status(InvoiceStatus.PENDING_APPROVAL)
    assert invoice.status == InvoiceStatus.PENDING_APPROVAL

    # Invalid jump to PAID directly from pending_approval raises ValueError
    with pytest.raises(ValueError) as exc:
        invoice.transition_status(InvoiceStatus.PAID)
    assert "Invalid status transition" in str(exc.value)


def test_records_strictly_require_user_id_scoping():
    """Verify that all core business domain entities require user_id."""
    # Customer
    with pytest.raises(ValidationError):
        Customer(name="No User Customer", email="test@example.com")  # type: ignore

    # Invoice
    with pytest.raises(ValidationError):
        Invoice(  # type: ignore
            customer_id="cust-1",
            invoice_number="INV-1",
            items=[InvoiceItem(name="Test", unit_price=Decimal("10.00"))],
            due_date=date(2026, 11, 20),
        )

    # Reminder
    with pytest.raises(ValidationError):
        Reminder(  # type: ignore
            invoice_id="inv-1",
            customer_id="cust-1",
            stage=ReminderStage.DUE_TODAY,
            subject="Reminder",
            message_body="Please pay",
        )

    # Transaction
    with pytest.raises(ValidationError):
        Transaction(  # type: ignore
            invoice_id="inv-1",
            amount=Decimal("100.00"),
        )

    # AuditLog
    with pytest.raises(ValidationError):
        AuditLog(  # type: ignore
            action="invoice.created",
            resource_type="invoice",
            resource_id="inv-1",
        )


def test_approval_payload_hash_and_invalidation():
    """Verify approval token generation and state invalidation."""
    payload = {"invoice_number": "INV-100", "total": "500.00", "customer": "Alice"}
    hash1 = compute_payload_hash(payload)

    approval = Approval(
        user_id="user-owner-1",
        action_type="create_paypal_invoice",
        resource_id="inv-100",
        payload_snapshot=payload,
        payload_hash=hash1,
    )
    assert approval.status == "pending"

    approval.approve()
    assert approval.status == "approved"
    assert approval.approved_at is not None

    # Invalidate if contents change
    approval.invalidate()
    assert approval.status == "invalidated"
