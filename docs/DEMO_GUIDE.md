# PAYFLOW AI — Judge Demo Guide

> **⚠ All demo data is entirely fictional.**
> No real customers, invoices, or financial transactions exist.
> PayPal interactions target the **Sandbox environment** only. No real charges occur.

---

## Quick Start (2 minutes)

### Option A — Zero-setup Local Demo Runner

```bash
# Clone the repo
git clone https://github.com/gayurajeev/FastAPI-PAYFLOW-AI-hackathon.git
cd FastAPI-PAYFLOW-AI-hackathon

# Install backend dependencies
cd backend && pip install -r requirements.txt && cd ..

# Install frontend dependencies
cd frontend && npm install && npm run build && cd ..

# Launch the all-in-one demo (pre-seeds FICTIONAL data, no MongoDB needed)
cd backend && PYTHONPATH=$(pwd) python -m app.demo_runner
```

Open **http://127.0.0.1:5173** in another terminal:
```bash
cd frontend && npx vite --port 5173
```

**Demo credentials** (pre-filled on the login page):
| Field    | Value                  |
|----------|------------------------|
| Email    | `demo@payflowai.com`   |
| Password | `DemoPassword2026!`    |

Click **[ Fill Demo Credentials ]** on the login screen to auto-populate.

---

### Option B — Seed a Live MongoDB Instance

```bash
# Requires a running MongoDB (local or Atlas)
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB_NAME="payflow_demo"

cd /path/to/repo
python scripts/seed_demo_data.py
```

The script creates clearly-labelled **[DEMO]** records and prints a summary.
Run it again to reset (old demo records are dropped first).

---

## The 2–3 Minute Judge Scenario

### 1 · Login and Dashboard

1. Open `/login` → click **Fill Demo Credentials** → **Sign In**
2. Land on **Dashboard** — observe the receivables summary:
   - \$32,600 outstanding across 4 open invoices
   - \$7,500 overdue (Stark Advisory Group)
   - \$4,350 paid (Globex Corporation, settled via sandbox)
3. Notice the aging buckets in the chart: 0–30 days, 30–60 days, 60+ days.

> **What this shows:** real-time AR position computed server-side from seeded FICTIONAL data.

---

### 2 · AI Invoice Extraction (Core Demo Feature)

1. Navigate to **AI Assistant** in the left nav.
2. Type this natural-language request:

   > *Create a \$500 invoice for website development for Acme Global Solutions, due in 14 days*

3. The Gemini AI orchestrator extracts structured fields and returns a **suggestion card**:
   - Customer: Acme Global Solutions
   - Description: Website Development Services
   - Amount: $500.00 USD
   - Due: 14 days from today
4. Click **Confirm Invoice Draft** to persist it.

> **What this shows:** Gemini AI field extraction with prompt-injection defenses and human-in-the-loop confirmation.
> The AI cannot approve or dispatch anything autonomously.

---

### 3 · Invoice Approval (Human-in-the-Loop)

1. Navigate to **Invoices** → find the newly created draft.
2. Click **Submit for Approval** — the invoice hash is computed and an approval record is created.
3. Navigate to **Approvals** — the pending approval appears with:
   - SHA-256 payload hash (tamper-evidence)
   - Full line-item preview
   - Approve / Reject action buttons

**To approve and dispatch to PayPal Sandbox:**

> ⚠ **This step requires real PayPal Sandbox credentials** configured in `.env`:
> ```
> PAYPAL_CLIENT_ID=...your sandbox client ID...
> PAYPAL_CLIENT_SECRET=...your sandbox secret...
> PAYPAL_WEBHOOK_ID=...your webhook ID...
> ```
> See [docs/environment-setup.md](environment-setup.md) for step-by-step PayPal Developer setup.

4. Click **Approve & Send to PayPal** → backend calls PayPal Invoicing v2 API → invoice appears in PayPal Sandbox merchant account.
5. The invoice `status` transitions: `pending_approval` → `sent`.
6. A PayPal invoice URL is returned and shown in the invoice detail view.

**Without live PayPal credentials**, click **Settings → PayPal Diagnostics** to see the connection status page and understand what the sandbox call would have done.

---

### 4 · Overdue Invoice & AI Reminder

1. Navigate to **Invoices** → click **INV-2026-0002** (Stark Advisory Group — 38 days overdue).
2. Scroll to the **Reminders** section — an AI-drafted Stage 4 reminder awaits approval:
   - Drafted by Gemini AI based on the invoice amount and days overdue
   - Status: `pending_approval` — the merchant must review before delivery
3. Click **Approve Reminder** to approve the reminder for dispatch.

> **What this shows:** graduated reminder policy (6 configurable stages), human-in-the-loop reminder approval,
> and Zapier-connected notification flow (see [docs/zapier-integration.md](zapier-integration.md)).

---

### 5 · Analytics & AG Grid

1. Navigate to **Analytics** → observe the aging grid (AG Grid Community v36):
   - Sortable columns, column filters, pagination
   - Currency-aware formatting in USD
   - Status-coded rows (quiet-luxury color scheme)
2. Use the column filter on **Status** to isolate overdue invoices.
3. Click any row to navigate to the invoice detail.

---

### 6 · PayPal Sandbox Verification

If you have configured sandbox credentials:

1. Log into [developer.paypal.com](https://developer.paypal.com) → Sandbox → Business account.
2. Open the PayPal merchant dashboard → Invoices.
3. The sandbox invoice created in Step 3 should appear there with the same amount and customer details.
4. Use the PayPal sandbox buyer account to simulate payment.
5. The webhook event (if sandbox webhook is configured) will update the PAYFLOW AI invoice status to `paid`.

> **Limitation disclosure:** Webhook delivery from PayPal Sandbox to a localhost app requires a tunneling tool
> (e.g. ngrok). On the hosted Render demo, webhooks are received directly.
> If you cannot trigger a live webhook, check the invoice status manually via
> **Settings → Sync PayPal Status** to fetch current state from the PayPal API.

---

## Pre-Seeded FICTIONAL Demo Data Summary

| Record | Description | Note |
|--------|-------------|------|
| `demo@payflowai.com` | Eleanor Vance · Vanguard Advisory Partners | FICTIONAL business owner |
| Acme Global Solutions | Enterprise client · 2 invoices | FICTIONAL company |
| Globex Corporation | Prompt payer · 1 invoice paid | FICTIONAL company |
| Stark Advisory Group | Overdue client · 38 days | FICTIONAL company |
| Cyberdyne Analytics | New client · draft invoice | FICTIONAL company |
| INV-2026-0001 | \$4,350 · Paid · Globex | SANDBOX payment only |
| INV-2026-0002 | \$7,500 · Overdue · Stark | FICTIONAL overdue |
| INV-2026-0003 | \$15,500 · Pending Approval · Acme | FICTIONAL approval demo |
| INV-2026-0004 | \$3,000 · Draft · Cyberdyne | FICTIONAL draft |
| INV-2026-0005 | \$9,600 · Sent · Acme | SANDBOX sent |

**PayPal IDs in demo data** (`INV2-XXXX-DEMO-...`) are placeholder strings.
They are **not live PayPal resources** and were inserted by the seed script,
not by calling the PayPal API.

---

## What Judges Can Create Themselves

1. Register a new account at `/register` with any fictional email.
2. Create a customer via **Customers → Add Customer**.
3. Use the AI Assistant to extract an invoice in natural language.
4. Submit for approval, review the SHA-256 hash and payload preview.
5. Approve → if PayPal sandbox credentials are configured, the invoice goes live in sandbox.

---

## Running the Test Suite

```bash
cd backend
pytest tests/ -v
# Expected: 145 passed
```

---

## Known Limitations

| Limitation | Status |
|------------|--------|
| PayPal Sandbox requires developer credentials to dispatch real invoices | Documented — see `.env.example` |
| Webhook verification requires a public HTTPS URL (not localhost) | Use Render deployment or ngrok tunnel |
| AI reminders require `AI_API_KEY` (Gemini); falls back to mock without it | Disclosed in app settings |
| In-memory rate limiter resets on process restart | Acceptable for MVP |
| No real financial data is ever created or stored | ✅ By design |

