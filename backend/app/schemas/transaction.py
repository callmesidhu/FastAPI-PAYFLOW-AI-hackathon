"""Pydantic schemas for Transaction ledger records (Prompt 24)."""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SupportedCurrency


class TransactionResponse(BaseModel):
    """Authoritative representation of a financial settlement transaction."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    user_id: str
    invoice_id: str
    invoice_number: Optional[str] = None
    customer_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    amount: Decimal
    fee_amount: Optional[Decimal] = None
    net_amount: Optional[Decimal] = None
    currency: SupportedCurrency
    status: str
    payer_email: Optional[str] = None
    created_at: datetime


class TransactionListResponse(BaseModel):
    """Paginated list of ledger transactions."""

    total: int
    items: List[TransactionResponse]

