"""PayPal Sandbox REST API Service.

Handles server-side OAuth 2.0 client-credentials token acquisition, in-memory
token caching with expiry safety, timeouts, bounded retries for safe requests,
and structured redacted logging.

Security invariants:
- Targets PayPal Sandbox ONLY (https://api-m.sandbox.paypal.com).
- Live endpoints are strictly forbidden and blocked.
- Credentials and access tokens are never returned to the client or written to logs.
- Token caching is strictly in-memory — never written to disk or persistent stores.
"""

import asyncio
from datetime import datetime, timezone
import re
import time
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.logging import logger
from app.core.metrics import ErrorCategory, metrics_collector
from app.models.customer import Customer
from app.models.invoice import Invoice
from app.models.user import User

settings = get_settings()


class PayPalAPIError(Exception):
    """Structured, safe PayPal REST API exception."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        details: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or []


def mask_secret(value: Optional[str], show_chars: int = 4) -> str:
    """Mask a secret or credential for safe logging."""
    if not value:
        return "<not-set>"
    if len(value) <= show_chars * 2:
        return "***"
    return f"{value[:show_chars]}***{value[-show_chars:]}"


def build_paypal_invoice_payload(
    invoice: Invoice,
    customer: Customer,
    user: User,
) -> Dict[str, Any]:
    """Map internal invoice domain model to official PayPal Invoicing v2 payload.

    Reference: https://developer.paypal.com/docs/api/invoicing/v2/#invoices_create
    """
    # Invoicer (Merchant profile)
    user_name = (user.name or "Business Owner").strip()
    name_parts = user_name.split(" ", 1)
    invoicer_given = name_parts[0]
    invoicer_surname = name_parts[1] if len(name_parts) > 1 else "Owner"

    # Customer (Primary recipient)
    cust_name = (customer.name or "Client").strip()
    cust_parts = cust_name.split(" ", 1)
    cust_given = cust_parts[0]
    cust_surname = cust_parts[1] if len(cust_parts) > 1 else "Client"

    billing_info: Dict[str, Any] = {
        "name": {
            "given_name": cust_given,
            "surname": cust_surname,
        },
        "email_address": customer.email,
    }
    if customer.company:
        billing_info["business_name"] = customer.company

    if customer.billing_address:
        address_dict: Dict[str, Any] = {}
        if customer.billing_address.address_line_1:
            address_dict["address_line_1"] = customer.billing_address.address_line_1
        if customer.billing_address.address_line_2:
            address_dict["address_line_2"] = customer.billing_address.address_line_2
        if customer.billing_address.city:
            address_dict["admin_area_2"] = customer.billing_address.city
        if customer.billing_address.state:
            address_dict["admin_area_1"] = customer.billing_address.state
        if customer.billing_address.postal_code:
            address_dict["postal_code"] = customer.billing_address.postal_code
        if customer.billing_address.country_code:
            address_dict["country_code"] = customer.billing_address.country_code
        if address_dict:
            billing_info["address"] = address_dict

    # Line items with Decimal precision converted safely to string values
    items: List[Dict[str, Any]] = []
    for item in invoice.items:
        item_obj: Dict[str, Any] = {
            "name": item.name,
            "quantity": str(item.quantity),
            "unit_amount": {
                "currency_code": invoice.currency.value,
                "value": f"{item.unit_price:.2f}",
            },
            "unit_of_measure": "QUANTITY",
        }
        if item.description:
            item_obj["description"] = item.description
        if item.tax and item.tax > 0:
            item_obj["tax"] = {
                "name": "Tax",
                "amount": {
                    "currency_code": invoice.currency.value,
                    "value": f"{item.tax:.2f}",
                },
            }
        items.append(item_obj)

    detail: Dict[str, Any] = {
        "invoice_number": invoice.invoice_number,
        "invoice_date": str(invoice.issue_date),
        "currency_code": invoice.currency.value,
        "payment_term": {
            "term_type": "DUE_ON_DATE_SPECIFIED",
            "due_date": str(invoice.due_date),
        },
    }
    if invoice.notes:
        detail["note"] = invoice.notes[:1000]

    return {
        "detail": detail,
        "invoicer": {
            "name": {
                "given_name": invoicer_given,
                "surname": invoicer_surname,
            },
            "business_name": user.business_name or user.name,
            "email_address": user.email,
        },
        "primary_recipients": [{"billing_info": billing_info}],
        "items": items,
        "configuration": {
            "allow_tip": False,
            "tax_calculated_after_discount": True,
            "tax_inclusive": False,
        },
    }


def extract_paypal_invoice_id(data: Dict[str, Any]) -> Optional[str]:
    """Extract PayPal invoice ID from full representation or HATEOAS 'self' link responses."""
    raw_id = data.get("id")
    if isinstance(raw_id, str) and raw_id.strip():
        return raw_id.strip()

    marker = "/v2/invoicing/invoices/"
    candidates: List[str] = []
    if data.get("rel") == "self" and isinstance(data.get("href"), str):
        candidates.append(data["href"])
    for link in data.get("links", []):
        if isinstance(link, dict) and link.get("rel") == "self" and isinstance(link.get("href"), str):
            candidates.append(link["href"])

    for href in candidates:
        if marker in href:
            tail = href.split(marker, 1)[1].split("?", 1)[0].strip("/")
            if tail and "/" not in tail:
                return tail
    return None


def extract_paypal_invoice_url(data: Dict[str, Any], paypal_id: str) -> str:
    """Extract official invoice preview URL from PayPal response or construct official sandbox URL."""
    # Check HATEOAS links
    for link in data.get("links", []):
        if link.get("rel") in ("payer-view", "view", "recipient-view"):
            return str(link.get("href"))

    # Check detail metadata
    recipient_url = data.get("detail", {}).get("metadata", {}).get("recipient_view_url")
    if recipient_url:
        return str(recipient_url)

    # Official PayPal Sandbox preview URL fallback
    clean_id = paypal_id.replace("INV2-", "").replace("-", "")
    return f"https://www.sandbox.paypal.com/invoice/p/#{clean_id}"


def parse_paypal_error(response: httpx.Response) -> PayPalAPIError:
    """Safely parse PayPal REST API error payload without exposing credentials or internal tokens."""
    try:
        data = response.json()
        error_name = data.get("name", "PAYPAL_API_ERROR")
        raw_msg = data.get("message", "An error occurred with PayPal Sandbox.")
        details = data.get("details", [])

        issue_messages = []
        for d in details:
            issue = d.get("issue", "")
            desc = d.get("description", "")
            field = d.get("field", "")
            if issue == "DUPLICATE_INVOICE_NUMBER":
                issue_messages.append(
                    "The invoice number has already been used in your PayPal account. Please provide a unique invoice number."
                )
            elif issue == "INVALID_CURRENCY_CODE":
                issue_messages.append("The specified currency code is not supported by PayPal Invoicing.")
            elif desc:
                issue_messages.append(f"{desc} ({field})" if field else desc)

        if issue_messages:
            combined = " ".join(issue_messages)
            return PayPalAPIError(
                f"PayPal Error ({error_name}): {combined}",
                status_code=response.status_code,
                details=details,
            )
        return PayPalAPIError(
            f"PayPal Error ({error_name}): {raw_msg}",
            status_code=response.status_code,
            details=details,
        )
    except Exception:
        return PayPalAPIError(
            f"PayPal Sandbox returned HTTP status {response.status_code}.",
            status_code=response.status_code,
        )



class PayPalOAuthToken(BaseModel):
    """In-memory OAuth 2.0 access token representation."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: float  # Unix timestamp


class PayPalService:
    """Service client for official PayPal Sandbox REST API interactions."""

    def __init__(self) -> None:
        self._cached_token: Optional[PayPalOAuthToken] = None
        self._lock = asyncio.Lock()
        self._timeout = httpx.Timeout(timeout=10.0, connect=5.0)

    @property
    def base_url(self) -> str:
        return settings.PAYPAL_BASE_URL.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return settings.is_paypal_configured

    def _is_token_valid(self) -> bool:
        """Check if cached token exists and has at least 60 seconds of validity."""
        if not self._cached_token:
            return False
        # Buffer of 60 seconds before expiration
        return time.time() < (self._cached_token.expires_at - 60)

    async def get_access_token(self, force_refresh: bool = False) -> str:
        """Obtain a valid OAuth 2.0 access token using client credentials flow.

        Uses in-memory caching with expiry safety and asyncio locking to prevent
        redundant concurrent token requests.

        Raises:
            RuntimeError: If PayPal credentials are not configured or request fails.
        """
        if not self.is_configured:
            raise RuntimeError(
                "PayPal credentials are not configured. Set PAYPAL_CLIENT_ID and "
                "PAYPAL_CLIENT_SECRET in backend/.env to connect to PayPal Sandbox."
            )

        async with self._lock:
            if not force_refresh and self._is_token_valid():
                assert self._cached_token is not None
                return self._cached_token.access_token

            token_url = f"{self.base_url}/v1/oauth2/token"
            logger.info(
                "Requesting PayPal OAuth token from %s (client_id=%s)",
                token_url,
                mask_secret(settings.PAYPAL_CLIENT_ID),
            )

            # Bounded retry: up to 2 attempts for transient networking issues
            last_err: Optional[Exception] = None
            for attempt in range(1, 3):
                try:
                    async with httpx.AsyncClient(timeout=self._timeout) as client:
                        response = await client.post(
                            token_url,
                            headers={
                                "Accept": "application/json",
                                "Accept-Language": "en_US",
                            },
                            data={"grant_type": "client_credentials"},
                            auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
                        )

                    if response.status_code == 200:
                        data = response.json()
                        token = data.get("access_token")
                        expires_in = int(data.get("expires_in", 32400))

                        if not token:
                            raise RuntimeError("PayPal token response missing 'access_token'")

                        self._cached_token = PayPalOAuthToken(
                            access_token=token,
                            token_type=data.get("token_type", "Bearer"),
                            expires_at=time.time() + expires_in,
                        )
                        logger.info(
                            "PayPal OAuth token acquired successfully (expires_in=%ds, token=%s)",
                            expires_in,
                            mask_secret(token, show_chars=3),
                        )
                        metrics_collector.record_paypal_call(success=True)
                        return token

                    err_msg = f"PayPal OAuth failed (status {response.status_code}): {response.text[:200]}"
                    logger.error("PayPal OAuth attempt %d error: %s", attempt, err_msg)
                    last_err = RuntimeError(err_msg)

                except (httpx.RequestError, httpx.TimeoutException) as err:
                    logger.warning("PayPal OAuth attempt %d network exception: %s", attempt, str(err))
                    last_err = err
                    if attempt < 2:
                        await asyncio.sleep(0.5)

            metrics_collector.record_paypal_call(success=False, error_category=ErrorCategory.PAYPAL_AUTH_FAILURE)
            raise RuntimeError(f"Unable to acquire PayPal OAuth token: {last_err}")

    async def check_connection(self) -> Dict[str, Any]:
        """Diagnostic verification of PayPal Sandbox connectivity.

        Returns safe diagnostic information without leaking client secrets or access tokens.
        """
        if not self.is_configured:
            return {
                "configured": False,
                "connected": False,
                "environment": "sandbox",
                "base_url": self.base_url,
                "webhook_configured": bool(settings.PAYPAL_WEBHOOK_ID),
                "message": (
                    "PayPal Sandbox credentials not configured. "
                    "Add PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET to backend/.env."
                ),
            }

        try:
            # Attempt to acquire or verify token
            token = await self.get_access_token()
            return {
                "configured": True,
                "connected": True,
                "environment": "sandbox",
                "base_url": self.base_url,
                "webhook_configured": bool(settings.PAYPAL_WEBHOOK_ID),
                "token_masked": mask_secret(token, show_chars=3),
                "message": "Successfully connected to PayPal Sandbox REST API.",
            }
        except Exception as err:
            logger.error("PayPal Sandbox connection diagnostic failed: %s", str(err))
            return {
                "configured": True,
                "connected": False,
                "environment": "sandbox",
                "base_url": self.base_url,
                "webhook_configured": bool(settings.PAYPAL_WEBHOOK_ID),
                "message": f"Connection check failed: {str(err)}",
            }

    async def create_invoice(
        self,
        invoice: Invoice,
        customer: Customer,
        user: User,
        idempotency_key: Optional[str] = None,
        invoice_number_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a draft invoice in PayPal Sandbox via Invoicing API v2.

        Enforces:
        - Bearer authentication via cached OAuth token.
        - Official Invoicing payload mapping without invented fields.
        - Idempotency using PayPal-Request-Id header.
        - Safe structured logging without PII or access tokens.
        - Parsed actionable exceptions on PayPal failure.
        """
        token = await self.get_access_token()
        url = f"{self.base_url}/v2/invoicing/invoices"
        payload = build_paypal_invoice_payload(invoice, customer, user)
        if invoice_number_override:
            payload["detail"]["invoice_number"] = invoice_number_override[:25]
        # PayPal allows arbitrary invoicer.email_address on draft creation, then
        # rejects /send with 422 USER_NOT_FOUND unless it belongs to the OAuth merchant.
        # Omitting it at transport time lets PayPal bind the sandbox merchant account.
        if isinstance(payload.get("invoicer"), dict):
            payload["invoicer"].pop("email_address", None)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Prefer": "return=representation",
        }
        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        logger.info(
            "Creating invoice in PayPal Sandbox (invoice_number=%s, currency=%s, idempotency_key=%s)",
            invoice.invoice_number,
            invoice.currency.value,
            idempotency_key or "none",
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code in (200, 201):
                data = response.json()
                resolved_id = extract_paypal_invoice_id(data)
                logger.info(
                    "PayPal invoice created successfully (paypal_id=%s, invoice_number=%s)",
                    resolved_id,
                    invoice.invoice_number,
                )
                return data

            logger.error(
                "PayPal create invoice failed with HTTP %d: %s",
                response.status_code,
                response.text[:300],
            )
            raise parse_paypal_error(response)

        except httpx.TimeoutException as err:
            logger.error("Timeout connecting to PayPal Sandbox: %s", str(err))
            raise PayPalAPIError("Network timeout connecting to PayPal Sandbox. Please try again.", status_code=504)
        except httpx.RequestError as err:
            logger.error("Network error communicating with PayPal Sandbox: %s", str(err))
            raise PayPalAPIError("Network communication error with PayPal Sandbox.", status_code=502)

    async def search_invoice_by_number(self, invoice_number: str) -> List[Dict[str, Any]]:
        """Query PayPal Sandbox Invoicing API v2 for existing invoices matching an invoice number."""
        token = await self.get_access_token()
        url = f"{self.base_url}/v2/invoicing/search-invoices"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json={"invoice_number": invoice_number})
            if response.status_code == 200:
                return list(response.json().get("items") or [])
            return []
        except (httpx.TimeoutException, httpx.RequestError) as err:
            logger.warning("PayPal invoice search error for %s: %s", invoice_number, str(err))
            return []

    async def _clear_invoicer_email_from_draft(
        self,
        client: httpx.AsyncClient,
        token: str,
        paypal_invoice_id: str,
    ) -> bool:
        """Remove unassociated invoicer.email_address from an existing PayPal draft before retrying send."""
        draft_url = f"{self.base_url}/v2/invoicing/invoices/{paypal_invoice_id}"
        auth_headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        get_resp = await client.get(draft_url, headers=auth_headers)
        if get_resp.status_code != 200:
            return False

        draft = get_resp.json()
        invoicer = draft.get("invoicer")
        if not isinstance(invoicer, dict) or not invoicer.pop("email_address", None):
            return False

        put_resp = await client.put(
            draft_url,
            headers={**auth_headers, "Content-Type": "application/json"},
            json=draft,
        )
        if put_resp.status_code not in (200, 204):
            logger.warning(
                "Failed to strip invoicer.email_address on PayPal draft %s: HTTP %d",
                paypal_invoice_id,
                put_resp.status_code,
            )
            return False
        return True

    async def send_invoice(
        self,
        paypal_invoice_id: str,
        note: Optional[str] = None,
        send_to_recipient: bool = True,
        send_to_invoicer: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send an existing invoice via PayPal Sandbox Invoicing API v2.

        Endpoint: POST /v2/invoicing/invoices/{paypal_invoice_id}/send
        Timeout & Unknown Outcome Guard:
        - If a timeout occurs, does NOT assume failure or retry blindly.
        - Immediately queries invoice via GET /v2/invoicing/invoices/{id} to reconcile state.
        - Only confirms success if PayPal reports status 'SENT', 'UNPAID', or settled.
        """
        token = await self.get_access_token()
        url = f"{self.base_url}/v2/invoicing/invoices/{paypal_invoice_id}/send"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        body: Dict[str, Any] = {
            "send_to_recipient": send_to_recipient,
            "send_to_invoicer": send_to_invoicer,
        }
        if note:
            body["note"] = note[:500]

        logger.info(
            "Sending invoice via PayPal Sandbox (paypal_id=%s, idempotency_key=%s)",
            paypal_invoice_id,
            idempotency_key or "none",
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=body)

                if (
                    response.status_code == 422
                    and (
                        "USER_NOT_FOUND" in response.text
                        or "invoicer email" in response.text.lower()
                    )
                    and await self._clear_invoicer_email_from_draft(client, token, paypal_invoice_id)
                ):
                    retry_headers = dict(headers)
                    if idempotency_key:
                        retry_headers["PayPal-Request-Id"] = f"{idempotency_key}-repaired"
                    response = await client.post(url, headers=retry_headers, json=body)

            if response.status_code in (200, 202):
                data = response.json() if response.content else {}
                logger.info(
                    "PayPal invoice sent successfully (paypal_id=%s, status=%d)",
                    paypal_invoice_id,
                    response.status_code,
                )
                return {
                    "paypal_invoice_id": paypal_invoice_id,
                    "status": "SENT",
                    "links": data.get("links", []),
                    "reconciled": False,
                }

            logger.error(
                "PayPal send invoice failed with HTTP %d: %s",
                response.status_code,
                response.text[:300],
            )
            raise parse_paypal_error(response)

        except (httpx.TimeoutException, httpx.RequestError) as net_err:
            logger.warning(
                "Network exception sending PayPal invoice %s: %s. Probing invoice status for reconciliation...",
                paypal_invoice_id,
                str(net_err),
            )
            # Reconcile unknown outcome by querying PayPal Invoicing API
            try:
                current_state = await self.get_invoice(paypal_invoice_id)
                paypal_status = current_state.get("status", "").upper()
                if paypal_status in ("SENT", "UNPAID", "MARKED_AS_PAID", "PAID"):
                    logger.info(
                        "Timeout reconciled: PayPal confirms invoice %s is in status %s",
                        paypal_invoice_id,
                        paypal_status,
                    )
                    return {
                        "paypal_invoice_id": paypal_invoice_id,
                        "status": paypal_status,
                        "links": current_state.get("links", []),
                        "reconciled": True,
                    }
                logger.error(
                    "Reconciliation check: Invoice %s remains in status %s after timeout.",
                    paypal_invoice_id,
                    paypal_status,
                )
            except Exception as probe_err:
                logger.error("Failed to reconcile invoice status after timeout: %s", str(probe_err))

            raise PayPalAPIError(
                "Network timeout during invoice send. PayPal status checked and invoice was not confirmed as sent. Please retry.",
                status_code=504,
            )

    async def get_invoice(self, paypal_invoice_id: str) -> Dict[str, Any]:
        """Fetch current authoritative invoice state from PayPal Sandbox.

        GET /v2/invoicing/invoices/{paypal_invoice_id}
        """
        token = await self.get_access_token()
        url = f"{self.base_url}/v2/invoicing/invoices/{paypal_invoice_id}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                    },
                )
            if resp.status_code != 200:
                raise parse_paypal_error(resp)
            return resp.json()
        except (httpx.TimeoutException, httpx.RequestError) as err:
            raise PayPalAPIError(f"Network error retrieving invoice {paypal_invoice_id}: {err}", status_code=502)

    async def verify_webhook_signature(
        self,
        transmission_id: str,
        transmission_time: str,
        transmission_sig: str,
        cert_url: str,
        auth_algo: str,
        webhook_id: str,
        raw_body: Dict[str, Any],
    ) -> bool:
        """Call PayPal POST /v1/notifications/verify-webhook-signature to verify cryptographic signature.

        Guaranteed:
        - Only returns True when PayPal returns {"verification_status": "SUCCESS"}.
        """
        # SSRF / Domain Spoofing Defense: Validate cert_url belongs to official PayPal infrastructure
        if not re.match(
            r"^https://([a-zA-Z0-9\-]+\.)?(sandbox\.)?paypal\.com/.*",
            cert_url,
            re.IGNORECASE,
        ):
            logger.warning("Rejected webhook verification: cert_url '%s' is not an authorized PayPal domain.", cert_url)
            return False

        token = await self.get_access_token()
        url = f"{self.base_url}/v1/notifications/verify-webhook-signature"
        payload = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": transmission_time,
            "webhook_id": webhook_id,
            "webhook_event": raw_body,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            if resp.status_code != 200:
                logger.warning(
                    "PayPal webhook signature verification returned HTTP %s",
                    resp.status_code,
                )
                return False

            data = resp.json()
            return data.get("verification_status") == "SUCCESS"


# Singleton service instance
paypal_service = PayPalService()

