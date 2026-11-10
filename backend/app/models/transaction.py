"""Transaction ledger record domain model."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import SupportedCurrency
from app.models.money import MoneyDecimal


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(BaseModel):
    """Immutable ledger record reflecting a verified payment or settlement."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., description="Owner user_id scoping this record")
    invoice_id: str = Field(..., description="Associated invoice internal ID")
    paypal_capture_id: Optional[str] = Field(default=None, description="PayPal Capture or Transaction ID")

    amount: MoneyDecimal = Field(..., description="Verified monetary settlement amount")
    currency: SupportedCurrency = Field(default=SupportedCurrency.USD)
    status: str = Field(default="completed", description="Payment status: completed, refunded, reversed")
    payer_email: Optional[str] = Field(default=None, description="Payer email reported by PayPal")

    created_at: datetime = Field(default_factory=utc_now)
