#!/usr/bin/env python3
"""Generate the authoritative Postman Collection v2.1.0 for PAYFLOW AI (Prompt 27).

Invariants:
- Uses collection variables for baseUrl, accessToken, customerId, invoiceId, approvalId, reminderId.
- Never embeds real secrets or production credentials.
- Contains realistic sample request bodies and documented response expectations.
- Includes step-by-step guidance for testing verified PayPal Sandbox webhooks.
"""

import json
from pathlib import Path

collection = {
    "info": {
        "_postman_id": "payflow-ai-master-collection-v1",
        "name": "PAYFLOW AI - Official REST API Collection",
        "description": (
            "Authoritative Postman API Collection for PAYFLOW AI — an AI-powered accounts receivable assistant "
            "for freelancers and small businesses.\n\n"
            "Features:\n"
            "- Authentication (Argon2id + JWT)\n"
            "- Customer CRUD with deduplication\n"
            "- Invoice drafting with server-authoritative Decimal math\n"
            "- Human Approval Center with cryptographic snapshot binding\n"
            "- PayPal Developer Sandbox Invoicing v2 adapter\n"
            "- AI Assistant with structured tool calling & natural language invoice extraction\n"
            "- Aging receivables analytics and multi-currency metrics\n"
            "- Automated reminder policy engine & Zapier notification webhooks\n"
            "- PayPal Webhook cryptographic signature verification\n"
            "- Append-only-style audit trail and financial ledger\n\n"
            "Security Invariant: Credentials and tokens are managed via collection variables. "
            "No secrets are embedded in this collection."
        ),
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        "version": "1.0.0",
    },
    "variable": [
        {"key": "baseUrl", "value": "http://localhost:8000", "type": "string"},
        {"key": "accessToken", "value": "", "type": "string"},
        {"key": "customerId", "value": "", "type": "string"},
        {"key": "invoiceId", "value": "", "type": "string"},
        {"key": "approvalId", "value": "", "type": "string"},
        {"key": "reminderId", "value": "", "type": "string"},
    ],
    "item": [],
}

def make_req(name, method, path, desc="", headers=None, body=None, auth_required=True, test_script=""):
    req_headers = headers or []
    if auth_required:
        req_headers.append({
            "key": "Authorization",
            "value": "Bearer {{accessToken}}",
            "type": "text",
        })
    if body:
        req_headers.append({
            "key": "Content-Type",
            "value": "application/json",
            "type": "text",
        })

    url_parts = [p for p in path.strip("/").split("/") if p]
    
    events = []
    if test_script:
        events.append({
            "listen": "test",
            "script": {
                "type": "text/javascript",
                "exec": test_script.strip().split("\n"),
            },
        })

    item_dict = {
        "name": name,
        "request": {
            "method": method,
            "header": req_headers,
            "description": desc,
            "url": {
                "raw": "{{baseUrl}}" + path,
                "host": ["{{baseUrl}}"],
                "path": url_parts,
            },
        },
        "response": [],
    }

    if body:
        item_dict["request"]["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2),
            "options": {"raw": {"language": "json"}},
        }

    if events:
        item_dict["event"] = events

    return item_dict


# ---------------------------------------------------------------------------
# 01 - Health & Diagnostics
# ---------------------------------------------------------------------------
health_folder = {
    "name": "01 - Health & Diagnostics",
    "description": "System health and PayPal Developer Sandbox diagnostic probes.",
    "item": [
        make_req(
            name="Health Check",
            method="GET",
            path="/health",
            desc="Liveness and readiness check. Returns status, environment name, and masked service indicators. Secrets are never exposed.",
            auth_required=False,
            test_script="""pm.test('Status is 200 OK', function () {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.status).to.eql('healthy');
    pm.expect(data.paypal_mode).to.eql('sandbox');
});""",
        ),
        make_req(
            name="PayPal Sandbox Diagnostics",
            method="GET",
            path="/api/paypal/status",
            desc="Inspects PayPal Developer Sandbox connectivity, OAuth token validity, and webhook configuration. Secrets remain masked.",
            auth_required=True,
            test_script="""pm.test('PayPal Sandbox is connected', function () {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.mode).to.eql('sandbox');
});""",
        ),
    ],
}

# ---------------------------------------------------------------------------
# 02 - Authentication
# ---------------------------------------------------------------------------
auth_folder = {
    "name": "02 - Authentication",
    "description": "User registration and login using Argon2id password hashing and short-lived JWT tokens.",
    "item": [
        make_req(
            name="Register New Merchant",
            method="POST",
            path="/api/auth/register",
            desc="Create a new merchant tenant. Automatically stores the returned access token in {{accessToken}}.",
            body={
                "email": "sarah.designer@example.com",
                "password": "SecurePassword123!",
                "name": "Sarah Designer",
                "business_name": "Studio Sarah Design LLC",
            },
            auth_required=False,
            test_script="""if (pm.response.code === 201) {
    const data = pm.response.json();
    pm.collectionVariables.set('accessToken', data.access_token);
    pm.test('Registration succeeded & accessToken set', function() {
        pm.expect(data.access_token).to.be.a('string');
        pm.expect(data.user.email).to.eql('sarah.designer@example.com');
    });
}""",
        ),
        make_req(
            name="Login Existing Merchant",
            method="POST",
            path="/api/auth/login",
            desc="Authenticate with email and password. Updates {{accessToken}} collection variable.",
            body={
                "email": "sarah.designer@example.com",
                "password": "SecurePassword123!",
            },
            auth_required=False,
            test_script="""if (pm.response.code === 200) {
    const data = pm.response.json();
    pm.collectionVariables.set('accessToken', data.access_token);
    pm.test('Login succeeded & token set', function() {
        pm.expect(data.access_token).to.be.a('string');
    });
}""",
        ),
        make_req(
            name="Get Current User Profile",
            method="GET",
            path="/api/auth/me",
            desc="Retrieve authenticated merchant profile.",
            auth_required=True,
            test_script="""pm.test('Returns profile of authenticated merchant', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.email).to.be.a('string');
});""",
        ),
    ],
}

# ---------------------------------------------------------------------------
# 03 - Customers
# ---------------------------------------------------------------------------
customers_folder = {
    "name": "03 - Customer Management",
    "description": "Customer entity management with duplicate prevention, search, and deletion invariants.",
    "item": [
        make_req(
            name="Create Customer",
            method="POST",
            path="/api/customers",
            desc="Add a client recipient. Saves customer ID to {{customerId}} variable.",
            body={
                "name": "Acme Global Ventures",
                "email": "accounting@acmeglobal.example",
                "company": "Acme Corp",
                "notes": "Net 14 payment terms agreed upon.",
                "billing_address": {
                    "address_line_1": "100 Innovation Way",
                    "admin_area_2": "San Francisco",
                    "admin_area_1": "CA",
                    "postal_code": "94105",
                    "country_code": "US",
                },
            },
            auth_required=True,
            test_script="""if (pm.response.code === 201) {
    const data = pm.response.json();
    pm.collectionVariables.set('customerId', data.id);
    pm.test('Customer created and ID captured', function() {
        pm.expect(data.id).to.be.a('string');
        pm.expect(data.email).to.eql('accounting@acmeglobal.example');
    });
}""",
        ),
        make_req(
            name="List Customers (Search & Pagination)",
            method="GET",
            path="/api/customers?q=Acme&page=1&page_size=20",
            desc="Retrieve paginated list of customers owned by the authenticated merchant.",
            auth_required=True,
            test_script="""pm.test('Returns paginated customer list', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.items).to.be.an('array');
});""",
        ),
        make_req(
            name="Get Customer By ID",
            method="GET",
            path="/api/customers/{{customerId}}",
            desc="Fetch specific customer details.",
            auth_required=True,
            test_script="""pm.test('Returns customer record', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.id).to.eql(pm.collectionVariables.get('customerId'));
});""",
        ),
        make_req(
            name="Update Customer Details",
            method="PATCH",
            path="/api/customers/{{customerId}}",
            desc="Partially update customer information.",
            body={
                "notes": "Updated terms: Net 7 terms for fast PayPal Sandbox settlement.",
            },
            auth_required=True,
            test_script="""pm.test('Customer updated', function() {
    pm.response.to.have.status(200);
});""",
        ),
        make_req(
            name="Delete / Archive Customer",
            method="DELETE",
            path="/api/customers/{{customerId}}",
            desc="Deletes customer or archives if linked to invoices.",
            auth_required=True,
        ),
    ],
}

# ---------------------------------------------------------------------------
# 04 - Invoices (Drafts & Calculations)
# ---------------------------------------------------------------------------
invoices_folder = {
    "name": "04 - Invoices (Drafts & Calculations)",
    "description": "Invoice draft creation, server-authoritative Decimal calculations, and lifecycle transitions.",
    "item": [
        make_req(
            name="Create Draft Invoice",
            method="POST",
            path="/api/invoices",
            desc="Create invoice draft. Totals computed server-side via Decimal. Saves invoice internal_id to {{invoiceId}}.",
            body={
                "customer_id": "{{customerId}}",
                "currency": "USD",
                "issue_date": "2026-11-10",
                "due_date": "2026-11-24",
                "notes": "Thank you for partnering with Studio Sarah Design LLC.",
                "items": [
                    {
                        "name": "Brand Identity Redesign",
                        "description": "Comprehensive design sprint including typography, tokens, and style guide",
                        "quantity": "1",
                        "unit_price": "2400.00",
                        "tax": "0.00",
                    },
                    {
                        "name": "Design System Documentation",
                        "description": "Figma component library and token specifications",
                        "quantity": "10",
                        "unit_price": "80.00",
                        "tax": "0.00",
                    },
                ],
            },
            auth_required=True,
            test_script="""if (pm.response.code === 201) {
    const data = pm.response.json();
    pm.collectionVariables.set('invoiceId', data.internal_id);
    pm.test('Invoice draft created with authoritative calculations', function() {
        pm.expect(data.internal_id).to.be.a('string');
        pm.expect(data.total).to.eql('3200.00');
        pm.expect(data.status).to.eql('draft');
    });
}""",
        ),
        make_req(
            name="List Invoices",
            method="GET",
            path="/api/invoices?page=1&page_size=20",
            desc="Retrieve invoices owned by authenticated merchant with optional filters.",
            auth_required=True,
        ),
        make_req(
            name="Get Invoice Details",
            method="GET",
            path="/api/invoices/{{invoiceId}}",
            desc="Retrieve complete invoice detail including line items and calculation breakdown.",
            auth_required=True,
            test_script="""pm.test('Invoice details returned', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.internal_id).to.eql(pm.collectionVariables.get('invoiceId'));
});""",
        ),
        make_req(
            name="Submit Invoice for Human Approval",
            method="POST",
            path="/api/invoices/{{invoiceId}}/submit-for-approval",
            desc="Transitions draft to PENDING_APPROVAL and generates an immutable Approval record with cryptographic payload_hash. Captures {{approvalId}}.",
            auth_required=True,
            test_script="""if (pm.response.code === 200) {
    const data = pm.response.json();
    pm.collectionVariables.set('approvalId', data.approval_id);
    pm.test('Submitted for approval with payload hash', function() {
        pm.expect(data.approval_id).to.be.a('string');
        pm.expect(data.payload_hash).to.be.a('string');
    });
}""",
        ),
        make_req(
            name="Get Invoice Activity Timeline",
            method="GET",
            path="/api/invoices/{{invoiceId}}/timeline",
            desc="Retrieve chronological append-only audit trail and lifecycle events for this invoice.",
            auth_required=True,
            test_script="""pm.test('Returns chronological activity timeline', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.events).to.be.an('array');
});""",
        ),
    ],
}

# ---------------------------------------------------------------------------
# 05 - Human Approval Center
# ---------------------------------------------------------------------------
approvals_folder = {
    "name": "05 - Human Approval Center",
    "description": "Human-in-the-loop governance: lists pending approvals and records merchant decisions.",
    "item": [
        make_req(
            name="List Pending Approvals",
            method="GET",
            path="/api/approvals?status=pending",
            desc="Inspect all pending actions requiring business owner verification.",
            auth_required=True,
        ),
        make_req(
            name="Get Approval Details",
            method="GET",
            path="/api/approvals/{{approvalId}}",
            desc="Inspect approval record, immutable snapshot, and bound payload hash.",
            auth_required=True,
        ),
        make_req(
            name="Approve Action",
            method="POST",
            path="/api/approvals/{{approvalId}}/approve",
            desc="Merchant grants authorization for the action. Verifies payload integrity.",
            auth_required=True,
            test_script="""pm.test('Action approved', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.status).to.eql('approved');
});""",
        ),
        make_req(
            name="Reject Action",
            method="POST",
            path="/api/approvals/{{approvalId}}/reject",
            desc="Merchant rejects action, reverting invoice back to DRAFT state.",
            auth_required=True,
        ),
    ],
}

# ---------------------------------------------------------------------------
# 06 - PayPal Sandbox Invoicing
# ---------------------------------------------------------------------------
paypal_folder = {
    "name": "06 - PayPal Sandbox Invoicing",
    "description": "Official PayPal Invoicing API v2 Sandbox integration. Enforces approved state verification before network calls.",
    "item": [
        make_req(
            name="Create Draft in PayPal Sandbox",
            method="POST",
            path="/api/paypal/invoices",
            desc="Maps internal draft to official PayPal invoice payload. Strictly verifies human authorization.",
            body={
                "invoice_id": "{{invoiceId}}",
            },
            auth_required=True,
            test_script="""if (pm.response.code === 201) {
    const data = pm.response.json();
    pm.test('PayPal Sandbox invoice created', function() {
        pm.expect(data.paypal_invoice_id).to.be.a('string');
    });
}""",
        ),
        make_req(
            name="Send PayPal Sandbox Invoice",
            method="POST",
            path="/api/paypal/invoices/{{invoiceId}}/send",
            desc="Dispatches official notification to payer in Sandbox environment. Requires prior owner approval.",
            body={
                "note": "Payment invoice delivered via PayPal Sandbox. Please review details.",
                "send_to_recipient": True,
            },
            auth_required=True,
        ),
        make_req(
            name="Approve & Send (Atomic Pipeline)",
            method="POST",
            path="/api/paypal/invoices/{{invoiceId}}/approve-and-send",
            desc="One-click authorized dispatch: verifies owner identity, approves action, drafts and sends via PayPal Invoicing API.",
            body={
                "note": "Authorized invoice from Sarah Designer via PayPal Sandbox.",
            },
            auth_required=True,
        ),
    ],
}

# ---------------------------------------------------------------------------
# 07 - AI Assistant & Extraction
# ---------------------------------------------------------------------------
ai_folder = {
    "name": "07 - AI Assistant & Natural Language",
    "description": "AI orchestrator with strict allowlist backend tools and natural-language invoice extraction.",
    "item": [
        make_req(
            name="AI Assistant Conversational Chat",
            method="POST",
            path="/api/ai/chat",
            desc="Chat with AI accounts receivable assistant. Queries receivables with verified tools.",
            body={
                "message": "What is my total outstanding receivables across all clients right now?",
            },
            auth_required=True,
            test_script="""pm.test('AI response returned with tool output', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.reply).to.be.a('string');
});""",
        ),
        make_req(
            name="Extract Invoice from Natural Language",
            method="POST",
            path="/api/ai/extract-invoice",
            desc="Extracts structured draft preview from natural language (e.g. 'Create a $500 invoice for Acme for logo design due in 7 days').",
            body={
                "text": "Create an invoice for Acme Global Ventures for $1500 for website design consultation due in 14 days",
                "timezone": "America/New_York",
            },
            auth_required=True,
            test_script="""pm.test('AI extracts structured draft preview', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.amount).to.eql('1500');
    pm.expect(data.currency).to.eql('USD');
});""",
        ),
        make_req(
            name="Confirm & Persist Extracted Draft",
            method="POST",
            path="/api/ai/confirm-extracted-invoice",
            desc="Validates and persists the AI-extracted invoice draft as an authoritative database record.",
            body={
                "customer_id": "{{customerId}}",
                "currency": "USD",
                "due_date": "2026-11-24",
                "line_items": [
                    {
                        "name": "Website design consultation",
                        "quantity": 1,
                        "unit_price": "1500.00",
                        "tax": "0.00",
                    }
                ],
                "notes": "Generated from natural language prompt.",
            },
            auth_required=True,
        ),
    ],
}

# ---------------------------------------------------------------------------
# 08 - Receivables Analytics & AI Summaries
# ---------------------------------------------------------------------------
analytics_folder = {
    "name": "08 - Receivables Analytics",
    "description": "Accounts receivable aging breakdown and cited AI portfolio analysis.",
    "item": [
        make_req(
            name="Dashboard Summary Metrics",
            method="GET",
            path="/api/dashboard/summary",
            desc="Real backend aggregate metrics: total outstanding, overdue, collected this month, and attention-needed queue.",
            auth_required=True,
            test_script="""pm.test('Dashboard aggregate data returned', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.currencies).to.be.an('array');
});""",
        ),
        make_req(
            name="Receivables Aging Buckets",
            method="GET",
            path="/api/analytics/receivables?start_date=2026-10-01&end_date=2026-11-10&timezone=UTC",
            desc="Calculates 0–7, 8–30, 31–60, and 60+ days aging buckets with per-customer balance segregation.",
            auth_required=True,
        ),
        make_req(
            name="AI Receivables Portfolio Analysis",
            method="POST",
            path="/api/analytics/ai-summary",
            desc="AI generates evidence-based financial summary with citations to exact invoice numbers.",
            body={
                "start_date": "2026-10-01",
                "end_date": "2026-11-10",
                "timezone": "UTC",
            },
            auth_required=True,
        ),
    ],
}

# ---------------------------------------------------------------------------
# 09 - Payment Reminders & Policy
# ---------------------------------------------------------------------------
reminders_folder = {
    "name": "09 - Payment Reminders & Policy",
    "description": "Deterministic reminder stages, guardrails against shaming/threats, and Zapier webhook integration.",
    "item": [
        make_req(
            name="Evaluate Reminder Candidates",
            method="POST",
            path="/api/reminders/evaluate",
            desc="Evaluates portfolio invoices against stages (upcoming, due today, 1-3d, 4-7d, 8-14d, 15+d overdue) and drafts respectful reminders.",
            auth_required=True,
            test_script="""if (pm.response.code === 200) {
    const data = pm.response.json();
    if (data.items && data.items.length > 0) {
        pm.collectionVariables.set('reminderId', data.items[0].id);
    }
}""",
        ),
        make_req(
            name="List Reminders",
            method="GET",
            path="/api/reminders?status=draft",
            desc="Retrieve drafted or dispatched payment reminders.",
            auth_required=True,
        ),
        make_req(
            name="Approve Reminder",
            method="POST",
            path="/api/reminders/{{reminderId}}/approve",
            desc="Merchant authorizes reminder message for delivery.",
            auth_required=True,
        ),
        make_req(
            name="Dispatch Reminder via Configured Channel",
            method="POST",
            path="/api/reminders/{{reminderId}}/dispatch",
            desc="Dispatches approved reminder via Zapier Catch Hook or acknowledges manual outreach.",
            auth_required=True,
        ),
        make_req(
            name="Run Scheduler Evaluation Cycle",
            method="POST",
            path="/api/reminders/run-scheduler",
            desc="Executes the periodic scheduler job to evaluate upcoming and overdue reminder policies.",
            auth_required=True,
        ),
    ],
}

# ---------------------------------------------------------------------------
# 10 - Ledger Transactions & Append-Only Audit Trail
# ---------------------------------------------------------------------------
ledger_folder = {
    "name": "10 - Ledger & Audit Trail",
    "description": "Application-layer append-only audit logs and financial settlement transactions.",
    "item": [
        make_req(
            name="List Audit Log Events",
            method="GET",
            path="/api/audit-logs?limit=50",
            desc="Retrieve append-only audit trail scoped to authenticated merchant. Secrets are permanently scrubbed.",
            auth_required=True,
            test_script="""pm.test('Audit trail returned', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.items).to.be.an('array');
});""",
        ),
        make_req(
            name="List Financial Transactions",
            method="GET",
            path="/api/transactions?limit=50",
            desc="Retrieve settled PayPal transaction ledger records with capture IDs and net amounts.",
            auth_required=True,
            test_script="""pm.test('Transactions returned', function() {
    pm.response.to.have.status(200);
    const data = pm.response.json();
    pm.expect(data.items).to.be.an('array');
});""",
        ),
    ],
}

# ---------------------------------------------------------------------------
# 11 - PayPal Webhook Receiver (Testing Guidance)
# ---------------------------------------------------------------------------
webhooks_folder = {
    "name": "11 - PayPal Webhook Ingestion",
    "description": (
        "Official PayPal Webhook receiver. "
        "CRITICAL SECURITY INVARIANT: This endpoint cryptographically verifies signatures against PayPal's REST API. "
        "A manually posted JSON body without official PayPal headers will be rejected (HTTP 400/401).\n\n"
        "TO TEST LIVE SANDBOX WEBHOOKS:\n"
        "1. Open PayPal Developer Dashboard > Webhook Simulator (https://developer.paypal.com/dashboard/webhooksSimulator)\n"
        "2. Set Webhook URL to: <Your-Public-URL>/api/webhooks/paypal\n"
        "3. Select Event Type: INVOICING.INVOICE.PAID or PAYMENT.CAPTURE.COMPLETED\n"
        "4. Click 'Send test'\n"
        "5. The simulator transmits authentic headers and signature, which PayFlow cryptographically verifies and reconciles."
    ),
    "item": [
        make_req(
            name="PayPal Webhook Receiver (Live Simulator Endpoint)",
            method="POST",
            path="/api/webhooks/paypal",
            desc=(
                "Receives PayPal webhook events. Cryptographically verifies signatures. "
                "Notice: Must include authentic PayPal cryptographic headers: "
                "PAYPAL-AUTH-ALGO, PAYPAL-CERT-URL, PAYPAL-TRANSMISSION-ID, PAYPAL-TRANSMISSION-SIG, PAYPAL-TRANSMISSION-TIME."
            ),
            headers=[
                {"key": "PAYPAL-AUTH-ALGO", "value": "SHA256withRSA", "type": "text"},
                {"key": "PAYPAL-CERT-URL", "value": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-12345", "type": "text"},
                {"key": "PAYPAL-TRANSMISSION-ID", "value": "trans-12345-sample", "type": "text"},
                {"key": "PAYPAL-TRANSMISSION-SIG", "value": "dGhpcy1pcy1hLXNhbXBsZS1zaWduYXR1cmU=", "type": "text"},
                {"key": "PAYPAL-TRANSMISSION-TIME", "value": "2026-11-10T12:00:00Z", "type": "text"},
            ],
            body={
                "id": "WH-SAMPLE-EVENT-001",
                "event_type": "INVOICING.INVOICE.PAID",
                "resource_type": "invoicing_invoice",
                "resource": {
                    "id": "INV2-SAMPLE-ID",
                    "amount": {"currency_code": "USD", "value": "1500.00"},
                },
            },
            auth_required=False,
        ),
    ],
}

collection["item"] = [
    health_folder,
    auth_folder,
    customers_folder,
    invoices_folder,
    approvals_folder,
    paypal_folder,
    ai_folder,
    analytics_folder,
    reminders_folder,
    ledger_folder,
    webhooks_folder,
]

output_path = Path("docs/postman/PayflowAI.postman_collection.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(collection, f, indent=2)

print(f"Generated Postman Collection at {output_path} with {len(collection['item'])} folders.")

