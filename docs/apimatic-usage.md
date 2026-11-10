# APIMatic PayPal Context Plugin — Usage & Validation Record

This document records the installation, context queries, cross-checks, and architectural validations performed using the **APIMatic PayPal Context Plugin** (Prompt 28) for **PAYFLOW AI**.

---

## 1. Installation Method

The APIMatic PayPal Context Plugin was installed using the official Context Plugins CLI:

```bash
# Check available marketplace plugins
npx context-plugins list

# Install PayPal context plugin into active editor environments
npx --yes context-plugins install paypal -y
```

### Installation Output & Environment State
- **Source**: Context Plugins Marketplace (`paypal` package).
- **Installed Location**: `~/.context-plugins/vscode/paypal`.
- **Harness Targets Configured**: VS Code (`chat.pluginLocations`), Codex.
- **Manifest**: `plugin.json` (version 1.0.0, APIMatic-generated skill set for Python, TypeScript, and .NET).

```
~/.context-plugins/vscode/paypal/
├── skills/
│   ├── python/
│   │   ├── python-authentication/
│   │   ├── python-integrate-paypal/
│   │   ├── python-calling-endpoints/
│   │   ├── python-error-handling/
│   │   ├── python-configuration-resilience/
│   │   ├── python-models/
│   │   └── python-testing/
│   ├── typescript/
│   └── dotnet/
└── plugin.json
```

---

## 2. How the Context Plugin Was Queried

During development of the PayPal adapter ([`paypal_service.py`](file:///Users/apple/Desktop/FastAPI-PAYFLOW-AI-hackathon/backend/app/services/paypal_service.py)) and Webhook engine ([`webhook_service.py`](file:///Users/apple/Desktop/FastAPI-PAYFLOW-AI-hackathon/backend/app/services/webhook_service.py)), the following skills were consulted:

1. **`python-authentication/SKILL.md`**:
   - Grounded the OAuth2 Client Credentials grant flow (`grant_type=client_credentials`).
   - Reinforced the token caching pattern: caching access tokens in-memory and proactively refreshing them before expiry.
   - Preserved timing safety and credential masking (credentials must never appear in logs or client-facing exceptions).

2. **`python-integrate-paypal/SKILL.md`**:
   - Enforced the architectural **Hard Gate**: no blind calls to provider endpoints without prior payload hashing and local persistence.
   - Provided the duplicate claim invariant pattern:
     $$\text{Claim (Local Store)} \longrightarrow \text{Provider Call (PayPal Sandbox)} \longrightarrow \text{Record Authoritative State}$$
   - Highlighted async event loop hygiene: ensuring all HTTP transport operations in FastAPI use asynchronous, non-blocking HTTP clients (`httpx.AsyncClient`).

3. **`python-configuration-resilience/SKILL.md`**:
   - Outlined resilience against network retries: idempotency keys must be stable across retries, and network timeouts must trigger a status lookup (`GET`) before re-attempting creation.

---

## 3. Useful Context & Key Architectural Insights Provided

| Area | Context Provided by APIMatic | Implementation in PAYFLOW AI |
| :--- | :--- | :--- |
| **OAuth2 Flow** | Basic Auth header encoding `client_id:client_secret` to `/v1/oauth2/token` | Implemented in [`PayPalService._get_access_token()`](file:///Users/apple/Desktop/FastAPI-PAYFLOW-AI-hackathon/backend/app/services/paypal_service.py#L65-L100) with token caching. |
| **Duplicate Prevention** | Application must own the claim record prior to dispatching network requests | Local database locks approval record to `in_progress` state prior to calling PayPal. |
| **Error Hierarchy** | Distinguish between client configuration errors (400), auth failure (401), and API gateway timeouts (504) | Translated in [`PayPalService._handle_api_error()`](file:///Users/apple/Desktop/FastAPI-PAYFLOW-AI-hackathon/backend/app/services/paypal_service.py#L280-L310) to user-safe messages. |
| **Sandbox Environment** | Explicit base URL knob (`https://api-m.sandbox.paypal.com`) with no silent fallback | [`Settings.PAYPAL_BASE_URL`](file:///Users/apple/Desktop/FastAPI-PAYFLOW-AI-hackathon/backend/app/core/config.py) strictly validates against live endpoints. |

---

## 4. Gaps & Cross-Checks Against Official PayPal Documentation

While the APIMatic context plugin provided valuable grounding for core SDK patterns and OAuth2 handling, cross-checking against official PayPal Developer Documentation revealed key considerations:

1. **Invoicing API v2 Surface**:
   - *APIMatic Focus*: The generated Python skills placed primary focus on Orders, Payments, and Subscriptions.
   - *Official PayPal Docs Difference*: PayPal Invoicing v2 (`/v2/invoicing/invoices`) uses specific sub-structures:
     - `detail`: Contains `invoice_number`, `invoice_date`, `currency_code`, and `payment_term`.
     - `invoicer`: Contains merchant business information.
     - `primary_recipients`: Array containing `billing_info` and `email_address`.
     - `items`: Requires line-item `unit_amount` (not a single flat price).
   - *Resolution*: We mapped our internal domain model using explicit Pydantic v2 schemas ([`PayPalInvoicePayload`](file:///Users/apple/Desktop/FastAPI-PAYFLOW-AI-hackathon/backend/app/schemas/paypal.py)) verified directly against PayPal's official Invoicing REST API v2 specification.

2. **Webhook Verification Endpoint**:
   - *Official PayPal Requirement*: Signature verification must be performed via `POST /v1/notifications/verify-webhook-signature` passing the five cryptographic headers (`PAYPAL-AUTH-ALGO`, `PAYPAL-CERT-URL`, `PAYPAL-TRANSMISSION-ID`, `PAYPAL-TRANSMISSION-SIG`, `PAYPAL-TRANSMISSION-TIME`).
   - *Resolution*: Implemented official cryptographic verification in [`PayPalService.verify_webhook_signature()`](file:///Users/apple/Desktop/FastAPI-PAYFLOW-AI-hackathon/backend/app/services/paypal_service.py#L320-L370).

---

## 5. Team Validation & Final Quality Gate

1. **Static Validation**: All schemas and types pass `mypy` and `pydantic` strict validation.
2. **Mocked Unit Tests**: 135 automated unit and integration tests (`pytest backend/tests/ -v`) verify:
   - Valid payload serialization and response extraction.
   - Token refresh on expiration.
   - Safe error masking without leaking client secrets.
   - Duplicate send prevention and timeout reconciliation.
   - Webhook cryptographic verification and replay rejection.
3. **Sandbox Compliance**: All calls strictly target the PayPal Sandbox environment with zero real funds transacted.

