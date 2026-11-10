"""Financial precision and money utilities using Python Decimal.

Enforces zero floating-point arithmetic on currency values, ISO 4217 validation,
and strict non-negative rules.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated, Any, Union
from pydantic import BeforeValidator, PlainSerializer
from app.models.enums import SupportedCurrency

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def to_decimal(v: Any) -> Decimal:
    """Safely convert numeric input to rounded Decimal without binary float distortion."""
    if isinstance(v, Decimal):
        return v.quantize(CENTS, rounding=ROUND_HALF_UP)
    if isinstance(v, (int, str)):
        return Decimal(str(v)).quantize(CENTS, rounding=ROUND_HALF_UP)
    if isinstance(v, float):
        # Convert through string representation to prevent float binary inaccuracy (e.g. 0.1 + 0.2 != 0.3)
        return Decimal(str(round(v, 2))).quantize(CENTS, rounding=ROUND_HALF_UP)
    raise ValueError(f"Cannot convert {type(v)} to Decimal money value.")


def serialize_decimal(v: Decimal) -> str:
    """Serialize Decimal as two-decimal string format (e.g., '100.00')."""
    return f"{v.quantize(CENTS, rounding=ROUND_HALF_UP):.2f}"


# Annotated Decimal type enforcing two-decimal precision and string serialization
MoneyDecimal = Annotated[
    Decimal,
    BeforeValidator(to_decimal),
    PlainSerializer(serialize_decimal, return_type=str, when_used="json"),
]


def validate_positive_money(v: Union[Decimal, int, str]) -> Decimal:
    """Ensure money amount is strictly non-negative (>= 0)."""
    dec = to_decimal(v)
    if dec < ZERO:
        raise ValueError("Monetary amount cannot be negative.")
    return dec


def validate_currency_code(code: str) -> str:
    """Validate ISO 4217 currency code against supported currencies."""
    cleaned = code.strip().upper()
    valid_codes = {c.value for c in SupportedCurrency}
    if cleaned not in valid_codes:
        raise ValueError(
            f"Unsupported currency code '{code}'. Supported currencies are: {', '.join(sorted(valid_codes))}"
        )
    return cleaned
