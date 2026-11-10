# PayPal Sandbox Integration Specification

> **Environment**: PayPal Developer Sandbox ONLY (`https://api-m.sandbox.paypal.com`)  
> **API Version**: Invoicing API v2 & OAuth 2.0  
> **Source of Truth**: Official PayPal Developer Platform (REST API Documentation)

---

## 1. Official Endpoints Reference

All requests must target the official PayPal Sandbox host. Live endpoints (`api.paypal.com`) are explicitly prohibited and blocked at the settings layer.

| Operation | HTTP Verb | Sandbox Endpoint Path | Purpose |
|---|---|---|---|
| **OAuth 2.0 Token** | `POST` | `/v1/oauth2/token` | Obtain short-lived Bearer access token using client credentials |
| **Create Invoice** | `POST` | `/v2/invoicing/invoices` | Create a draft invoice in PayPal Sandbox |
| **Get Invoice** | `GET` | `/v2/invoicing/invoices/{invoice_id}` | Retrieve current state and payment status of an invoice |
| **Send Invoice** | `POST` | `/v2/invoicing/invoices/{invoice_id}/send` | Deliver an approved invoice from PayPal to customer |
| **Send Reminder** | `POST` | `/v2/invoicing/invoices/{invoice_id}/remind` | Dispatch a follow-up payment reminder notification |
| **Cancel Invoice** | `POST` | `/v2/invoicing/invoices/{invoice_id}/cancel` | Cancel an existing unpaid or sent invoice |
| **Generate Invoice Number** | `POST` | `/v2/invoicing/generate-next-invoice-number` | Retrieve next suggested sequential invoice number |
| **Verify Webhook** | `POST` | `/v1/notifications/verify-webhook-signature` | Validate incoming PayPal webhook cryptographic signature |

---

## 2. OAuth 2.0 Client-Credentials Flow

### Authentication Headers & Body
- **URL**: `https://api-m.sandbox.paypal.com/v1/oauth2/token`
- **Headers**:
  - `Accept`: `application/json`
  - `Accept-Language`: `en_US`
  - `Content-Type`: `application/x-www-form-urlencoded`
  - `Authorization`: `Basic <base64(PAYPAL_CLIENT_ID:PAYPAL_CLIENT_SECRET)>`
- **Body**:
  - `grant_type=client_credentials`

### Expected PayPal Response
```json
{
  "scope": "https://api.paypal.com/v2/invoicing/ ...",
  "access_token": "A21A...",
  "token_type": "Bearer",
  "app_id": "APP-80W284485P519543T",
  "expires_in": 32400,
  "nonce": "2026-11-10T11:20:00Z"
}
```

### In-Memory Token Caching & Expiry Safety
- Store `access_token` and `expires_at` in server memory.
- Deduct a safety margin (e.g., 60 seconds) from `expires_in` to guarantee the token is refreshed before it expires.
- Never write the raw token or client secret to disk, logs, or API responses.

---

## 3. Supported Currencies (ISO 4217)

PayPal REST Invoicing v2 natively supports the following currencies used in PAYFLOW AI:

- `USD` — United States Dollar
- `EUR` — Euro
- `GBP` — British Pound Sterling
- `CAD` — Canadian Dollar
- `AUD` — Australian Dollar
- `JPY` — Japanese Yen (0 decimal currency)
- `CHF` — Swiss Franc
- `SGD` — Singapore Dollar
- `NZD` — New Zealand Dollar
- `INR` — Indian Rupee

---

## 4. Invoice Lifecycle State Mapping

| Internal PAYFLOW Status | PayPal Invoicing Status | Description |
|---|---|---|
| `draft` | *Not yet created in PayPal* | Prepared in PAYFLOW; awaiting human approval |
| `pending_approval` | *Not yet created in PayPal* | Immutable snapshot created; awaiting owner approval |
| `created` | `DRAFT` | Created in PayPal Sandbox via POST `/v2/invoicing/invoices` |
| `sent` | `SENT` | Dispatched to customer via PayPal Invoicing |
| `unpaid` | `SENT` / `UNPAID` | Invoice delivered and awaiting customer payment |
| `partially_paid` | `PARTIALLY_PAID` | Partial payment captured |
| `paid` | `PAID` / `MARKED_AS_PAID` | Fully settled and captured via PayPal Sandbox |
| `overdue` | `SENT` (past due date) | Payment past due date; triggers reminder workflow |
| `cancelled` | `CANCELLED` | Voided in PayPal Sandbox |
| `failed` | *Any non-2xx outcome* | Dispatch failed; requires owner intervention |

---

## 4.1 Invoicing API v2 Payload Mapping Specification

### Create Draft Invoice (`POST /v2/invoicing/invoices`)
- **Headers**:
  - `Authorization: Bearer <access_token>`
  - `Content-Type: application/json`
  - `PayPal-Request-Id: <idempotency_key>` (guarantees idempotency and safe retries)
- **Request Body Fields**:
  - `detail`:
    - `invoice_number` (string, max 25 chars): Authoritative invoice number from PAYFLOW
    - `invoice_date` (string, `YYYY-MM-DD`): Local issue date
    - `currency_code` (string, ISO 4217): Active currency (e.g. `USD`, `EUR`)
    - `note` (string, optional, max 1000 chars): Payment terms or client memo
    - `payment_term`: `{"term_type": "DUE_ON_DATE_SPECIFIED", "due_date": "YYYY-MM-DD"}`
  - `invoicer`:
    - `name`: `{"given_name": "<owner_first>", "surname": "<owner_last>"}`
    - `business_name` (string): Business studio name from user profile
    - `email_address` (string): Business owner's email address
  - `primary_recipients` (list of 1 object):
    - `billing_info`:
      - `name`: `{"given_name": "<client_first>", "surname": "<client_last>"}`
      - `email_address`: Customer billing email
      - `business_name`: Customer company name (optional)
      - `address`: Billing address structure (`address_line_1`, `admin_area_2`, `admin_area_1`, `postal_code`, `country_code`)
  - `items` (array of line items):
    - `name` (string, max 140 chars): Line item title
    - `description` (string, optional, max 500 chars): Detailed description
    - `quantity` (string decimal): Number of units (e.g. `"1"`, `"2.5"`)
    - `unit_amount`: `{"currency_code": "<CURRENCY>", "value": "<0.00>"}`
    - `tax` (optional): `{"name": "Tax", "amount": {"currency_code": "<CURRENCY>", "value": "<0.00>"}}`
    - `unit_of_measure`: `"QUANTITY"`
  - `configuration`:
    - `allow_tip`: `false`
    - `tax_calculated_after_discount`: `true`
    - `tax_inclusive`: `false`

### Response Extraction (`201 Created`)
- `id`: Persisted as `paypal_invoice_id` (format: `INV2-XXXX-XXXX-XXXX-XXXX`).
- `links`: Extracted URL for preview/buyer view (`payer-view` or `https://www.sandbox.paypal.com/invoice/p/#{id}`).
- Internal status transitions to `created`.

---

## 4.2 Invoice Send Workflow & Timeout Reconciliation (`POST /v2/invoicing/invoices/{id}/send`)

### Operation Specification
- **Endpoint**: `POST https://api-m.sandbox.paypal.com/v2/invoicing/invoices/{invoice_id}/send`
- **Headers**:
  - `Authorization: Bearer <access_token>`
  - `Content-Type: application/json`
  - `PayPal-Request-Id: <idempotency_key>`
- **Request Body**:
  ```json
  {
    "send_to_recipient": true,
    "send_to_invoicer": false
  }
  ```
- **Success Response**: `200 OK` or `202 Accepted`

### Invariants & Guardrails:
1. **Sendable Status Requirement**: The invoice must be created in PayPal and exist in a sendable status (`DRAFT` / `created`).
2. **Human Approval Prerequisite**: Requires an explicit `Approval` record bound to the exact payload hash.
3. **Duplicate Send Prevention**: If already `SENT` or `PAID`, duplicate calls return the existing send state safely without re-dispatching.
4. **Timeout & Unknown Outcome Reconciliation**:
   - If network timeout occurs during `POST .../send`, PAYFLOW issues `GET /v2/invoicing/invoices/{id}`.
   - If PayPal reports status `SENT` or `UNPAID`, the send is confirmed and reconciled.
   - Success is NEVER reported unless confirmed by PayPal.
5. **Auditing**: Every send attempt, status outcome, and timestamp is captured in immutable audit logs.

### Error Handling & Sanitization
PayPal errors contain:
- `name`: Error identifier (e.g., `INVALID_REQUEST`)
- `message`: High-level error summary
- `details`: Array of issues (`field`, `issue`, `description`)
  - E.g., `DUPLICATE_INVOICE_NUMBER` is translated into: *"This invoice number has already been used in your PayPal account. Please use a unique invoice number."*
  - Secrets, raw tokens, and internal stack traces are strictly stripped before reaching the client.

## 5. Webhook Verification Specification

When PayPal dispatches an asynchronous payment or invoice event, the payload must be verified before mutating application state:

- **Endpoint**: `POST https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature`
- **Required Verification Fields**:
  - `auth_algo`: Value from HTTP header `PAYPAL-AUTH-ALGO`
  - `cert_url`: Value from HTTP header `PAYPAL-CERT-URL`
  - `transmission_id`: Value from HTTP header `PAYPAL-TRANSMISSION-ID`
  - `transmission_sig`: Value from HTTP header `PAYPAL-TRANSMISSION-SIG`
  - `transmission_time`: Value from HTTP header `PAYPAL-TRANSMISSION-TIME`
  - `webhook_id`: Value of configured `PAYPAL_WEBHOOK_ID`
  - `webhook_event`: Raw JSON body of the received webhook event
- **Verification Rule**: Update local invoice state ONLY when PayPal returns `"verification_status": "SUCCESS"`.

---

## 6. Security & Data Protection Invariants

1. **Zero Secret Leakage**: `PAYPAL_CLIENT_SECRET` and access tokens are never sent to the browser or logged.
2. **PII Masking**: Structured logs mask customer emails, invoice numbers, and bearer headers (`Bearer A21A***`).
3. **Bounded Retries**: Safe GET or token requests retry up to 2 times with exponential backoff; mutation endpoints use idempotency keys.
4. **Isolated Test Harness**: Unit and integration tests mock PayPal network requests via `respx` — credentials are not required to run the test suite.

---

## 7. Manual Sandbox Testing Guide

For end-to-end evaluation using official PayPal Sandbox accounts:

1. **Sign in to PayPal Developer Dashboard**: [https://developer.paypal.com](https://developer.paypal.com).
2. **Navigate to Testing Tools > Sandbox Accounts**:
   - Ensure a **Business (Merchant)** account and a **Personal (Buyer)** account exist.
3. **Obtain API Credentials**:
   - Navigate to **Apps & Credentials** > Create an App under Sandbox.
   - Copy `Client ID` and `Client Secret` into `backend/.env`:
     ```env
     PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com
     PAYPAL_CLIENT_ID=<your-sandbox-client-id>
     PAYPAL_CLIENT_SECRET=<your-sandbox-client-secret>
     ```
4. **Test Diagnostic Endpoint**:
   - Issue: `GET /api/paypal/status` with your JWT Bearer token.
   - Confirm response returns `"connected": true` and `"environment": "sandbox"`.
5. **Simulate Invoice Flow**:
   - Create invoice draft in PAYFLOW UI (`/invoices/new`).
   - Submit for approval and approve in Approval Center (`/approvals`).
   - Confirm PayPal invoice ID and official Sandbox invoice URL appear.
   - Open invoice URL in a private browser window to preview the buyer payment screen.

