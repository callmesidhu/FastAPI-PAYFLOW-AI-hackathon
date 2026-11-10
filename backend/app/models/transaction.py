"""Transaction ledger record domain model (Prompt 24)."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import SupportedCurrency
from app.models.money import MoneyDecimal


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(BaseModel):
    """Append-only ledger record reflecting a verified payment settlement or refund.

    Guarantees:
    - Scoped strictly to owner user_id.
    - Linked to authoritative internal invoice_id.
    - Application layer append-only (no update/delete routes exist).
    - Monies handled strictly with Decimal precision.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="Owner user_id scoping this record")
    invoice_id: str = Field(..., description="Associated invoice internal ID")
    invoice_number: Optional[str] = Field(default=None, description="Human-readable invoice reference")
    customer_id: Optional[str] = Field(default=None, description="Customer recipient ID")
    paypal_capture_id: Optional[str] = Field(default=None, description="PayPal Capture, Transaction, or Refund ID")

    amount: MoneyDecimal = Field(..., description="Gross verified monetary settlement amount")
    fee_amount: Optional[MoneyDecimal] = Field(default=None, description="PayPal transaction fee if reported")
    net_amount: Optional[MoneyDecimal] = Field(default=None, description="Net received amount after fees")
    currency: SupportedCurrency = Field(default=SupportedCurrency.USD)
    status: str = Field(default="completed", description="Payment status: completed, refunded, reversed")
    payer_email: Optional[str] = Field(default=None, description="Payer email reported by PayPal")

    created_at: datetime = Field(default_factory=utc_now)
