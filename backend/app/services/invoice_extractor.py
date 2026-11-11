"""Natural language invoice extraction engine (Prompt 19).

Extracts customer identity, amount, currency, service description, and due date
from unstructured natural language instructions. Performs customer resolution against
the authenticated user's records, handles relative dates with timezone disclosure,
and produces an editable preview without writing to the database or sending PayPal invoices.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import get_logger
from app.models.invoice import InvoiceStatus
from app.schemas.ai import (
    CustomerMatchCandidate,
    ExtractedDraftItem,
    ExtractedInvoiceDraft,
    InvoiceExtractionResponse,
    ConfirmExtractedInvoiceRequest,
)
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceResponse
from app.services import customer_service, invoice_service

logger = get_logger("payflow.invoice_extractor")

# Number word mappings for relative date parsing
WORD_TO_NUM: Dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fourteen": 14,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "sixty": 60,
    "ninety": 90,
}

CURRENCY_SYMBOLS: Dict[str, str] = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}

SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF"}


def _resolve_relative_days(text: str) -> Optional[Tuple[int, str]]:
    """Parse relative due date phrases into integer day offset and original phrase."""
    lower = text.lower()

    if "tomorrow" in lower:
        return 1, "tomorrow"

    if "next week" in lower:
        return 7, "next week"

    if "two weeks" in lower:
        return 14, "two weeks"

    if "next month" in lower or "a month" in lower:
        return 30, "next month"

    # Match patterns like: due in 7 days, due in seven days, in 14 days, within 30 days
    pattern = r"(?:due\s+in|in|within)\s+([a-z0-9]+)\s*(?:business\s+)?(days?|weeks?|months?)"
    match = re.search(pattern, lower)
    if match:
        raw_num = match.group(1)
        unit = match.group(2)

        count = None
        if raw_num.isdigit():
            count = int(raw_num)
        elif raw_num in WORD_TO_NUM:
            count = WORD_TO_NUM[raw_num]

        if count is not None:
            if "week" in unit:
                count *= 7
            elif "month" in unit:
                count *= 30
            return count, match.group(0)

    return None


def _resolve_timezone_date(tz_str: Optional[str]) -> Tuple[date, str]:
    """Get today's date in user's timezone, or default to UTC with explicit disclosure."""
    tz_name = tz_str.strip() if tz_str and tz_str.strip() else "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz_name = "UTC"
        tz = ZoneInfo("UTC")

    now_tz = datetime.now(tz)
    return now_tz.date(), tz_name


class InvoiceExtractor:
    """Service to parse, resolve, and preview invoice drafts from natural language."""

    @classmethod
    async def extract_invoice(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        text: str,
        user_timezone: Optional[str] = "UTC",
    ) -> InvoiceExtractionResponse:
        """Extract invoice parameters, resolve customer, and build editable preview.

        Guaranteed:
        - Read-only: Does NOT insert into db.invoices or call PayPal.
        - Returns is_suggestion=True to distinguish from saved draft.
        - Asks clarifying questions for ambiguous customer, missing currency, or invalid date.
        """
        raw_text = text.strip()
        issue_date, tz_disclosed = _resolve_timezone_date(user_timezone)

        # 1. Detect Currency
        currency: Optional[str] = None
        for code in SUPPORTED_CURRENCIES:
            if re.search(rf"\b{code}\b", raw_text, re.IGNORECASE):
                currency = code.upper()
                break

        if not currency:
            for symbol, code in CURRENCY_SYMBOLS.items():
                if symbol in raw_text:
                    currency = code
                    break

        if not currency:
            # Check if there is an ambiguous symbol or no currency specified at all
            return InvoiceExtractionResponse(
                is_suggestion=True,
                clarification_needed=True,
                ambiguity_reason="missing_currency",
                clarification_question=(
                    "Which currency should this invoice use (e.g. USD, EUR, GBP, CAD, AUD)?"
                ),
            )

        # 2. Extract Amount
        amount_val: Optional[Decimal] = None
        amount_patterns = [
            r"[$€£¥]\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",
            r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)\s*(?:USD|EUR|GBP|CAD|AUD|JPY|CHF)",
            r"(?:for|amount of|total of)\s+([0-9]+(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)",
        ]
        for pat in amount_patterns:
            m = re.search(pat, raw_text, re.IGNORECASE)
            if m:
                raw_amt = m.group(1).replace(",", "")
                try:
                    cand = Decimal(raw_amt)
                    if cand > 0:
                        amount_val = cand
                        break
                except InvalidOperation:
                    continue

        if amount_val is None:
            # Look for any standalone numeric token
            num_matches = re.findall(r"\b([0-9]+(?:\.[0-9]{1,2})?)\b", raw_text)
            for raw_amt in num_matches:
                try:
                    cand = Decimal(raw_amt)
                    if cand > 0:
                        amount_val = cand
                        break
                except InvalidOperation:
                    continue

        if amount_val is None:
            return InvoiceExtractionResponse(
                is_suggestion=True,
                clarification_needed=True,
                ambiguity_reason="missing_amount",
                clarification_question="What is the invoice amount?",
            )

        # 3. Extract Due Date
        due_date: Optional[date] = None
        relative_text: Optional[str] = None

        # Check explicit ISO date: YYYY-MM-DD
        iso_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", raw_text)
        if iso_match:
            try:
                parsed_date = date.fromisoformat(iso_match.group(1))
                if parsed_date < issue_date:
                    return InvoiceExtractionResponse(
                        is_suggestion=True,
                        clarification_needed=True,
                        ambiguity_reason="invalid_due_date",
                        clarification_question=(
                            f"The due date ({parsed_date}) cannot be in the past. "
                            f"Issue date is {issue_date}. Please specify a future due date."
                        ),
                    )
                due_date = parsed_date
            except ValueError:
                return InvoiceExtractionResponse(
                    is_suggestion=True,
                    clarification_needed=True,
                    ambiguity_reason="invalid_due_date",
                    clarification_question="The provided due date format is invalid. Please use YYYY-MM-DD.",
                )

        if not due_date:
            rel = _resolve_relative_days(raw_text)
            if rel:
                offset_days, rel_str = rel
                due_date = issue_date + timedelta(days=offset_days)
                relative_text = rel_str
            else:
                # Default to 14 days if not explicitly mentioned, disclosed to user
                due_date = issue_date + timedelta(days=14)
                relative_text = "14 days (default)"

        # 4. Extract Description / Service Name
        description = "Professional Services"
        desc_patterns = [
            r"for\s+((?:website\s+development|consulting|design|development|workshop|services|audit|retainer|implementation)[a-z0-9_\s\-]*?)(?=\s+(?:due|by|for\s+\$|\$|in\s+\d|with)|[,.;!?]|$)",
            r"(?:for|description:|item:)\s+([A-Za-z0-9\s\-_,]+?)(?=\s+(?:due|by|for\s+\$|\$|in\s+\d|with)|[,.;!?]|$)",
        ]
        for pat in desc_patterns:
            dm = re.search(pat, raw_text, re.IGNORECASE)
            if dm:
                extracted_desc = dm.group(0 if dm.lastindex is None else dm.lastindex).strip()
                if extracted_desc.lower().startswith("for "):
                    extracted_desc = extracted_desc[4:].strip()
                # Exclude customer name or amounts accidentally matched
                if not re.match(r"^[\$0-9]+", extracted_desc) and len(extracted_desc) >= 3:
                    description = extracted_desc
                    break

        # 5. Extract and Resolve Customer Identity
        customer_query = ""
        cust_patterns = [
            r"(?:invoice|bill|for)\s+([A-Z][a-zA-Z0-9\s\.\&]+?)(?=\s+(?:for|\$|[0-9]|due|with)|$)",
            r"(?:customer|client):\s*([A-Za-z0-9\s\.\&]+)",
        ]
        for pat in cust_patterns:
            cm = re.search(pat, raw_text)
            if cm:
                cand = cm.group(1).strip()
                # Exclude common action keywords
                cand_lower = cand.lower()
                if not any(cand_lower.startswith(k) for k in ["a ", "an ", "invoice", "payment", "$"]):
                    customer_query = cand
                    break

        if not customer_query:
            # Fallback search for capitalized names
            words = [w for w in raw_text.split() if w.istitle() and w.lower() not in {"create", "invoice", "bill", "due"}]
            if words:
                customer_query = " ".join(words[:2])

        matched_customer_id: Optional[str] = None
        matched_customer_name = customer_query or "Client"
        matched_customer_email: Optional[str] = None
        customer_matches: List[CustomerMatchCandidate] = []

        if customer_query:
            # Query db.customers for user_id with search regex
            search_regex = {"$regex": re.escape(customer_query.strip()), "$options": "i"}
            cursor = db.customers.find({
                "user_id": user_id,
                "is_active": True,
                "$or": [
                    {"name": search_regex},
                    {"company": search_regex},
                    {"email": search_regex},
                ],
            })
            matching_docs = await cursor.to_list(length=10)

            if len(matching_docs) == 1:
                doc = matching_docs[0]
                matched_customer_id = doc["id"]
                matched_customer_name = doc["name"]
                matched_customer_email = doc["email"]
            elif len(matching_docs) > 1:
                # Check for exact case-insensitive match
                exact_matches = [
                    d for d in matching_docs
                    if d["name"].lower() == customer_query.lower() or (d.get("company") and d["company"].lower() == customer_query.lower())
                ]
                if len(exact_matches) == 1:
                    doc = exact_matches[0]
                    matched_customer_id = doc["id"]
                    matched_customer_name = doc["name"]
                    matched_customer_email = doc["email"]
                else:
                    # Multiple matches exist: require user clarification!
                    customer_matches = [
                        CustomerMatchCandidate(
                            id=d["id"],
                            name=d["name"],
                            email=d["email"],
                            company=d.get("company"),
                        )
                        for d in matching_docs
                    ]
                    names_str = ", ".join(f"'{c.name}' ({c.email})" for c in customer_matches)
                    return InvoiceExtractionResponse(
                        is_suggestion=True,
                        clarification_needed=True,
                        ambiguity_reason="multiple_customer_matches",
                        clarification_question=(
                            f"Multiple customers match '{customer_query}': {names_str}. "
                            f"Which customer would you like to invoice?"
                        ),
                        customer_matches=customer_matches,
                    )

        # 6. Build Extracted Draft Items (Strict rule: DO NOT infer tax unless requested)
        tax_amount = Decimal("0.00")
        item = ExtractedDraftItem(
            name=description,
            description=None,
            quantity=Decimal("1.0"),
            unit_price=amount_val,
            tax=tax_amount,
            total=amount_val,
        )

        subtotal_str = f"{amount_val:.2f}"
        tax_str = f"{tax_amount:.2f}"
        total_str = f"{amount_val:.2f}"

        draft_preview = ExtractedInvoiceDraft(
            customer_id=matched_customer_id,
            customer_name=matched_customer_name,
            customer_email=matched_customer_email,
            currency=currency,
            issue_date=str(issue_date),
            due_date=str(due_date),
            due_date_relative_text=relative_text,
            timezone_disclosed=tz_disclosed,
            items=[item],
            subtotal=subtotal_str,
            tax=tax_str,
            total=total_str,
            notes=f"Created via natural language instruction in timezone {tz_disclosed}.",
        )

        return InvoiceExtractionResponse(
            is_suggestion=True,
            clarification_needed=False,
            extracted_draft=draft_preview,
        )

    @classmethod
    async def confirm_extracted_draft(
        cls,
        db: AsyncIOMotorDatabase,
        user_id: str,
        payload: ConfirmExtractedInvoiceRequest,
    ) -> InvoiceResponse:
        """Validate all editable fields and persist draft invoice via domain service.

        Guaranteed:
        - Fully validates customer ownership and decimal prices.
        - Persists status='draft'.
        - Never sends to PayPal automatically.
        """
        customer_id = payload.customer_id

        # 1. Resolve or create customer if needed
        if not customer_id:
            if not payload.customer_name:
                raise ValueError("Customer name or customer ID is required to save an invoice draft.")

            # Create customer record for this user
            new_cust_payload = CustomerCreate(
                name=payload.customer_name.strip(),
                email=payload.customer_email.strip() if payload.customer_email else f"{re.sub(r'[^a-zA-Z0-9]', '', payload.customer_name.lower())}@example.com",
            )
            created_cust = await customer_service.create_customer(
                db=db,
                user_id=user_id,
                payload=new_cust_payload,
            )
            customer_id = created_cust.id

        # 2. Build line items with Decimal precision
        items_to_create = [
            InvoiceItemCreate(
                name=it.name.strip(),
                description=it.description.strip() if it.description else None,
                quantity=it.quantity,
                unit_price=it.unit_price,
                tax=it.tax,
            )
            for it in payload.items
        ]

        # 3. Parse dates
        issue_d = date.fromisoformat(payload.issue_date) if payload.issue_date else date.today()
        due_d = date.fromisoformat(payload.due_date) if payload.due_date else issue_d + timedelta(days=14)

        invoice_payload = InvoiceCreate(
            customer_id=customer_id,
            currency=payload.currency.upper(),
            items=items_to_create,
            issue_date=issue_d,
            due_date=due_d,
            notes=payload.notes,
        )

        created_invoice = await invoice_service.create_invoice_draft(
            db=db,
            user_id=user_id,
            payload=invoice_payload,
        )

        resp = InvoiceResponse.model_validate(created_invoice)
        cust = await db.customers.find_one({"id": created_invoice.customer_id, "user_id": user_id})
        if cust:
            resp.customer_name = cust.get("name")
        return resp
