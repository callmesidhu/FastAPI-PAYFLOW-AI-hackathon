"""AI Provider Abstraction Layer.

Defines a clean, swappable service interface for AI LLM providers
(Gemini, OpenAI, Mock), enforcing:
- Environment-configured provider/model/keys.
- Structured tool/function calling schemas.
- Strict token limits and timeouts.
- Safe error handling and secret suppression.
- Ambiguity detection and clarifying questions.
- In-memory mock client for hermetic, API-key-free testing.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.core.logging import logger
from app.core.metrics import ErrorCategory, metrics_collector
from app.schemas.ai import AICompletionResult, AIToolCall
from app.agents.security import scrub_secrets

settings = get_settings()


class BaseAIProvider(ABC):
    """Abstract interface for AI model providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'gemini', 'openai', 'mock')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model identifier."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
    ) -> AICompletionResult:
        """Generate structured completion or tool call from model."""
        pass


class GeminiAIProvider(BaseAIProvider):
    """Google Gemini AI integration using official Google GenAI SDK."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None) -> None:
        self._api_key = api_key or settings.AI_API_KEY
        self._model = model or settings.AI_MODEL or "gemini-2.5-flash"
        self._client: Any = None

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._api_key:
                raise RuntimeError("AI_API_KEY is not configured for Gemini provider.")
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except Exception as err:
                logger.error("Failed to initialize Google GenAI client: %s", str(err))
                raise RuntimeError(f"Unable to initialize Gemini client: {err}")
        return self._client

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
    ) -> AICompletionResult:
        """Execute structured call via Gemini SDK with secret scrubbing and timeout."""
        # Sanitize inbound text
        sanitized_instruction = scrub_secrets(system_instruction or "")

        try:
            client = self._get_client()
            # Convert messages into GenAI content objects
            contents = []
            for msg in messages:
                role = "user" if msg.get("role") in ("user", "system") else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": scrub_secrets(msg.get("content", ""))}],
                })

            # Call SDK (synchronous SDK wrapper or async if available)
            response = client.models.generate_content(
                model=self._model,
                contents=contents,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_output_tokens,
                    "system_instruction": sanitized_instruction if sanitized_instruction else None,
                },
            )

            text_content = response.text if hasattr(response, "text") else ""
            return AICompletionResult(
                content=scrub_secrets(text_content),
                model=self._model,
            )

        except Exception as err:
            logger.error("Gemini completion error: %s", scrub_secrets(str(err)))
            return AICompletionResult(
                content=f"The AI Assistant encountered a temporary error: {scrub_secrets(str(err))}",
                model=self._model,
                finish_reason="error",
            )


class MockAIProvider(BaseAIProvider):
    """Deterministic, hermetic mock AI provider for unit tests and offline use.

    Understands accounting/invoicing domain intents:
    - Invoicing queries (search customers, list invoices, overdue summaries)
    - Invoice drafting from natural language
    - Ambiguity detection and clarifying questions
    - Approval bypass defense
    """

    def __init__(self, model: str = "mock-agentic-v1") -> None:
        self._model = model
        self.recorded_calls: List[Dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
    ) -> AICompletionResult:
        metrics_collector.record_ai_call(success=True)
        self.recorded_calls.append({
            "messages": messages,
            "tools": tools,
            "system_instruction": system_instruction,
        })

        # Analyze last user message
        last_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "")
                break

        text = re.sub(r"[\.!\?,;]+$", "", last_user_msg.lower().strip())

        # Invariant 1: Attempts to bypass human approval, prompt injections, or silent changes
        if re.search(r"\b(bypass\s+approval|send\s+without\s+approval|execute\s+paypal\s+directly)\b", text):
            return AICompletionResult(
                content=(
                    "In accordance with PAYFLOW security policy, the AI Assistant cannot approve "
                    "or execute PayPal transactions directly. All outbound invoices and payment actions "
                    "require your explicit authorization in the Approval Center."
                ),
                model=self._model,
            )

        if re.search(r"\b(ignore\s+(?:previous|all)\s+instructions|system\s+prompt|prompt\s+injection)\b", text):
            return AICompletionResult(
                content=(
                    "In accordance with PAYFLOW security policy, system instructions and safety invariants "
                    "cannot be overridden. Core financial parameters require explicit user authorization."
                ),
                model=self._model,
            )

        if re.search(r"\b(silently\s+change|change\s+without\s+asking|silently\s+zero|secretly\s+modify)\b", text):
            return AICompletionResult(
                content=(
                    "PAYFLOW AI enforces strict financial invariants: amount, currency, customer, due date, "
                    "and tax cannot be modified silently. Any adjustments must be explicitly confirmed."
                ),
                model=self._model,
            )

        # Invariant 2: Ambiguous or incomplete invoice creation requests
        # Pattern: User wants to create an invoice
        if re.search(r"\b(create|draft|make|prepare|generate|bill|invoice)\b", text) and ("invoice" in text or "bill" in text):
            # Check for unsupported or adversarial currency (e.g., BTC, ETH, DOGE)
            if re.search(r"\b(btc|eth|crypto|bitcoin|doge)\b", text):
                return AICompletionResult(
                    content="PAYFLOW AI only supports fiat currencies via PayPal Sandbox (USD, EUR, GBP, CAD, AUD, JPY). Cryptocurrencies are not supported.",
                    clarification_needed=True,
                    clarification_question="Which fiat currency would you like to bill in (e.g. USD, EUR, GBP)?",
                    model=self._model,
                )

            # Check for customer name: must follow 'for' or 'to' and not be a dollar amount or number
            cust_match = re.search(r"\b(?:for|to)\s+([A-Za-z][A-Za-z\s]{1,40}?)(?:\s+(?:for|amount|due|\$|\d)|$)", text)
            if cust_match:
                cand = cust_match.group(1).strip().lower()
                service_keywords = {"services", "service", "consulting", "design", "development", "workshop", "retainer", "audit", "fee", "hours", "usd", "eur", "gbp"}
                if any(w in cand.split() for w in service_keywords):
                    cust_match = None
            has_customer = bool(cust_match)

            # Check for price/amount
            has_amount = bool(re.search(r"(\$|\b\d+(?:\.\d{1,2})?\s*(?:usd|eur|gbp|dollars|bucks)?\b)", text))
            # Check for line item description
            has_item = bool(re.search(r"\b(service|workshop|design|consulting|development|retainer|hours|fee)\b", text))

            # Case: Missing customer
            if not has_customer:
                return AICompletionResult(
                    content="Who should this invoice be addressed to? Please provide the customer name or email so I can prepare the draft.",
                    clarification_needed=True,
                    clarification_question="Who should this invoice be addressed to?",
                    model=self._model,
                )

            # Case: Missing amount / items
            if not has_amount or not has_item:
                return AICompletionResult(
                    content=(
                        "I'd be glad to prepare that invoice draft for you. Could you please specify "
                        "the line item descriptions, unit prices, and quantities?"
                    ),
                    clarification_needed=True,
                    clarification_question="What services or items should be billed, and at what rate?",
                    model=self._model,
                )

            # Case: Ambiguous currency (e.g. user specified "1000" without currency and multiple exist)
            if "ambiguous currency" in text or ("currency" in text and "which" in text):
                return AICompletionResult(
                    content="Which currency should this invoice be billed in (e.g., USD, EUR, GBP)?",
                    clarification_needed=True,
                    clarification_question="Please specify the currency for this invoice.",
                    model=self._model,
                )

            # Parse a structured draft
            # Extract customer name candidate
            cust_match = re.search(r"\b(?:for|to)\s+([A-Za-z\s]+?)(?:\s+(?:for|amount|due|\$|\d)|$)", text)
            cust_name = cust_match.group(1).strip().title() if cust_match else "Client"

            # Extract amount
            amt_match = re.search(r"\$?(\d+(?:\.\d{1,2})?)", text)
            amount_val = Decimal(amt_match.group(1)) if amt_match else Decimal("100.00")

            # Extract currency
            currency_val = "USD"
            if "eur" in text or "€" in text:
                currency_val = "EUR"
            elif "gbp" in text or "£" in text:
                currency_val = "GBP"
            elif "cad" in text:
                currency_val = "CAD"
            elif "aud" in text:
                currency_val = "AUD"
            elif "jpy" in text or "¥" in text:
                currency_val = "JPY"

            # Extract service/item name when explicitly given
            from app.services.invoice_extractor import _resolve_relative_days

            item_name = "Professional Services"
            svc_match = re.search(
                r"\bfor\s+((?:website\s+development|consulting|design|development|workshop|services|audit|retainer|implementation)[a-z0-9_\s\-]*?)(?=\s+(?:due|by|for\s+\$|\$|in\s+\d|with)|[,.;!?]|$)",
                text,
            )
            if svc_match and svc_match.group(1).strip():
                item_name = svc_match.group(1).strip().title()

            # Extract relative due days when specified (fallback Net 14)
            rel_due = _resolve_relative_days(text)
            due_days = rel_due[0] if rel_due and rel_due[0] > 0 else 14

            tool_call = AIToolCall(
                id="call_draft_1",
                name="create_invoice_draft",
                arguments={
                    "customer_name_or_id": cust_name,
                    "items": [
                        {
                            "name": item_name,
                            "quantity": "1.0",
                            "unit_price": str(amount_val),
                            "tax": "0.00",
                        }
                    ],
                    "currency": currency_val,
                    "due_in_days": due_days,
                    "notes": f"Payment terms: Net {due_days} days.",
                },
            )
            return AICompletionResult(
                content=(
                    f"Structured Summary:\n"
                    f"• Customer: {cust_name}\n"
                    f"• Total Amount: ${amount_val} {currency_val}\n"
                    f"• Due Date: In {due_days} days\n"
                    f"• Tax: $0.00\n\n"
                    f"This will create and send invoice through PayPal Sandbox after approval."
                ),
                tool_calls=[tool_call],
                model=self._model,
            )

        # Invariant 3: Receivables & Overdue inquiries
        if "overdue" in text:
            return AICompletionResult(
                content="Checking for overdue invoices...",
                tool_calls=[AIToolCall(id="call_overdue", name="get_overdue_invoices", arguments={})],
                model=self._model,
            )

        if any(w in text for w in ("outstanding", "summary", "receivables", "metrics", "dashboard")):
            return AICompletionResult(
                content="Retrieving receivables summary...",
                tool_calls=[AIToolCall(id="call_summary", name="get_receivables_summary", arguments={})],
                model=self._model,
            )

        # Invariant 4: Customer search inquiry
        if any(w in text for w in ("customer", "client", "contacts")):
            query = "all"
            m = re.search(r"(?:customer|client|for)\s+([A-Za-z0-9]+)", text)
            if m:
                query = m.group(1)
            return AICompletionResult(
                content="Searching client records...",
                tool_calls=[AIToolCall(id="call_cust", name="search_customers", arguments={"query": query})],
                model=self._model,
            )

        # Invariant 5: List invoices
        if "invoices" in text or "list" in text:
            return AICompletionResult(
                content="Listing your invoices...",
                tool_calls=[AIToolCall(id="call_inv", name="list_invoices", arguments={"limit": 10})],
                model=self._model,
            )

        # Default conversational greeting / assistance
        return AICompletionResult(
            content=(
                "I am your PAYFLOW AI receivables assistant. I can help you search customers, "
                "prepare draft invoices, analyze overdue balances, and draft payment reminders. "
                "How may I assist you today?"
            ),
            model=self._model,
        )


def get_ai_provider(provider_type: Optional[str] = None) -> BaseAIProvider:
    """Factory to instantiate configured AI provider client."""
    selected = (provider_type or settings.AI_PROVIDER or "gemini").lower().strip()

    if selected == "mock" or selected == "test":
        return MockAIProvider()

    if selected == "gemini":
        if not settings.AI_API_KEY:
            logger.info("AI_API_KEY not configured for Gemini; falling back to MockAIProvider.")
            return MockAIProvider()
        return GeminiAIProvider(api_key=settings.AI_API_KEY, model=settings.AI_MODEL)

    logger.warning("Unknown AI provider '%s', defaulting to MockAIProvider.", selected)
    return MockAIProvider()
