# PAYFLOW AI — Demo Video Script & Production Guide (Prompt 37)

> **Duration Target:** 2 minutes 58 seconds (Strictly under 3:00 limit)  
> **Platform / Device:** Desktop Browser (1920×1080 display, Chrome) with mobile inspection  
> **Audio:** Clean voiceover, zero copyrighted music, no unlicensed third-party trademarks  
> **Pacing:** ~135 words per minute (Total spoken script: ~390 words)  
> **Safety:** All demo accounts, customer data, and invoices are fictional. No live API credentials, JWT tokens, or PayPal production secrets are visible.

---

## 1. Timeline & Video Structure Overview

| Timestamp | Segment | Visual Action | Narration Focus | Target Words |
|---|---|---|---|---|
| **0:00 – 0:15** | Problem & Product Intro | Quiet-luxury landing/login view → Dashboard transition | Freelancers waste hours chasing receivables; PAYFLOW AI is an autonomous, approval-gated AR agent | 34 words |
| **0:15 – 0:35** | Dashboard & AI Assistant | Receivables overview metrics, aging buckets, jump to AI chat | Real-time financial clarity; Gemini-powered assistant with strict guardrails | 46 words |
| **0:35 – 1:05** | Natural-Language Extraction | Typing prompt in AI Assistant; suggestion card renders | Gemini extracts customer, items, amounts, due dates with zero silent writes | 68 words |
| **1:05 – 1:35** | User Review & Approval Lock | Inspect draft in Approvals Center; review SHA-256 hash | Human-in-the-loop control; cryptographic hash lock guarantees tamper-evidence | 65 words |
| **1:35 – 2:00** | PayPal Sandbox Dispatch | Click "Approve & Send"; view PayPal Invoice ID & URL | Live PayPal Invoicing v2 API dispatch; merchant controls actual payment request | 56 words |
| **2:00 – 2:25** | Verified Status & Webhooks | Invoice detail page; PayPal status sync / verified badge | Idempotent RSASSA cryptographic webhook verification; zero fake payments | 54 words |
| **2:25 – 2:45** | Overdue Reminder & Approval | Select overdue invoice; review AI reminder draft | 6-stage reminder policy; owner reviews & approves before Zapier/email delivery | 45 words |
| **2:45 – 2:58** | Impact & Closing | AG Grid analytics view → Devpost title card | Editorial quiet luxury, financial precision, and PayPal peace of mind | 28 words |

**Total Duration:** 2:58 | **Total Spoken Words:** 396 words

---

## 2. Word-for-Word Voiceover Script with Visual Action Cues

### [0:00 – 0:15] Segment 1: Problem & Product
* **Visual Cue:** Start on the login screen (`/login`). Click **[ Fill Demo Credentials ]** and hit **Sign In**. Smoothly transition to the Dashboard (`/dashboard`).
* **Voiceover:**
  > *"For freelancers and boutique agencies, managing unpaid invoices is an exhausting administrative burden. Meet **PAYFLOW AI**: an autonomous, approval-gated accounts receivable agent built with FastAPI, React, and the official PayPal Invoicing v2 API."*

---

### [0:15 – 0:35] Segment 2: Dashboard & AI Assistant
* **Visual Cue:** Cursor glides across Dashboard summary cards: **Total Outstanding ($32.6k)**, **Paid This Month ($4.4k)**, **Overdue ($7.5k)**. Hover over the aging breakdown. Click **AI Assistant** in the sidebar nav.
* **Voiceover:**
  > *"Our editorial quiet-luxury dashboard delivers instant clarity on cash flow and aging receivables. Behind the scenes, our AI assistant is powered by Google Gemini, operating strictly under a deterministic five-tool allowlist that prevents autonomous writes."*

---

### [0:35 – 1:05] Segment 3: Natural-Language Invoice Extraction
* **Visual Cue:** In the AI Assistant chat box, paste or type:  
  `"Create a $500 invoice for website development for Acme Global Solutions, due in 14 days"`  
  Press Enter. The AI processes and outputs a structured **Invoice Suggestion Card** showing customer, amount ($500.00 USD), line item, and due date. Click **[ Confirm Invoice Draft ]**.
* **Voiceover:**
  > *"Instead of filling out complex forms, you simply describe the work in natural language. Gemini extracts line items, quantities, currency, and payment terms, presenting an editable draft. Crucially, the AI cannot approve or send invoices on its own—every action requires explicit human confirmation."*

---

### [1:05 – 1:35] Segment 4: User Review & Approval Lock
* **Visual Cue:** Navigate to **Approvals** (`/approvals`). Click on the newly submitted draft. Point cursor to the **SHA-256 Payload Hash** and the line-item breakdown.
* **Voiceover:**
  > *"In the Approval Center, the business owner holds complete authority. The backend computes a deterministic SHA-256 hash of the exact invoice payload. If anything is altered between review and execution, the approval invalidates automatically, protecting the business from unauthorized changes."*

---

### [1:35 – 2:00] Segment 5: Real PayPal Sandbox Invoice Creation & Sending
* **Visual Cue:** Click **[ Approve & Send to PayPal ]**. A subtle confirmation toast appears. The invoice status badge updates to `Sent`. Click through to the invoice detail page (`/invoices/inv_...`) displaying the **PayPal Invoice ID** and **Sandbox Payment Link**.
* **Voiceover:**
  > *"Upon approval, our backend dispatches the request to the official PayPal Invoicing v2 API in the PayPal Sandbox. PayPal generates the invoice number, stores the line items, and produces an authentic payment link ready for client delivery."*

---

### [2:00 – 2:25] Segment 6: Verified Status & Cryptographic Webhooks
* **Visual Cue:** On the Invoice Detail timeline, highlight the status timeline and webhook verification event. Show the **Settings → PayPal Diagnostics** view showing Sandbox verification endpoints.
* **Voiceover:**
  > *"When the buyer pays, PayPal dispatches an asynchronous webhook. PAYFLOW AI verifies the RSASSA signature against PayPal's official certificate endpoint before updating internal state. We enforce replay protection and never record fake payment confirmations."*

---

### [2:45 – 2:45] Segment 7: Overdue Reminder Draft & Approval
* **Visual Cue:** Navigate to **Invoices** (`/invoices`). Filter for overdue items. Open invoice `INV-2026-0002` (Stark Advisory Group, 38 days overdue). Scroll down to the **AI Reminder** drawer showing a drafted Stage 4 follow-up message. Click **[ Approve Reminder ]**.
* **Voiceover:**
  > *"For overdue invoices, our background scheduler triggers a six-stage escalation policy. Gemini drafts a context-aware, respectful reminder tailored to the client's relationship. The owner reviews the message and approves it for signed webhook delivery."*

---

### [2:45 – 2:58] Segment 8: Impact & Closing
* **Visual Cue:** Navigate to **Analytics** (`/analytics`). Briefly scroll through the AG Grid aging table. Cut to closing screen showing the **PAYFLOW AI** wordmark, **Team XyphX**, and technology sponsor badges (PayPal, Gemini, AG Grid).
* **Voiceover:**
  > *"PAYFLOW AI combines the intelligence of generative AI with the rigorous reliability of PayPal Invoicing. Getting paid, finally made effortless. Thank you."*

---

## 3. Recording Setup & Quality Checklist

### Hardware & Environment
- [ ] **Display Resolution:** Set monitor to **1920×1080** (or 2560×1440 scaled 200%).
- [ ] **Browser:** Google Chrome in dedicated clean profile, zoom level 100%, bookmarks bar hidden.
- [ ] **Audio:** External USB/XLR condenser or dynamic microphone (avoid laptop built-in mic).
- [ ] **Room Acoustics:** Quiet room with minimal echo; run a 5-second room tone check.
- [ ] **No Secrets Exposed:** Confirm `.env`, API keys, and client secrets are NOT visible in dev tools or URLs.

### Pre-Recording Rehearsal Checklist
- [ ] Seed fresh demo data: `python scripts/seed_demo_data.py` (or launch `demo_runner.py`).
- [ ] Rehearse speaking along with the timer to ensure each segment completes within its time slot.
- [ ] Test the AI extraction prompt to ensure fast response.
- [ ] Verify that AG Grid renders immediately with quiet-luxury styling.
- [ ] Double-check that total recording runtime does not exceed **2 minutes and 58 seconds**.

---

## 4. YouTube Upload Guide

### Video Settings
* **Title:** `PAYFLOW AI — Autonomous Accounts Receivable with PayPal Invoicing v2 (Team XyphX)`
* **Privacy:** **Unlisted** (or **Public**). *Do not set to Private, or judges cannot view it.*
* **Category:** Science & Technology
* **Audience:** Not made for kids

### YouTube Description Template (Copy & Paste)
```markdown
PAYFLOW AI is an autonomous, approval-gated accounts receivable agent built for freelancers and boutique studios for the PayPal AI Hackathon 2026 by Team XyphX.

Built with FastAPI, React 18, Google Gemini 1.5/2.5 Flash, AG Grid Community v36, and official PayPal Invoicing v2 REST APIs.

TIMESTAMPS:
0:00 Problem & Introduction
0:15 Receivables Dashboard & AI Guardrails
0:35 Natural-Language Invoice Extraction (Gemini)
1:05 Human-in-the-Loop Approval & SHA-256 Lock
1:35 Real PayPal Sandbox Invoicing & Dispatch
2:00 Cryptographic Webhook Verification & Status
2:25 Overdue Reminder Policy & Approval
2:45 Analytics Ledger & Closing

GitHub Repository: https://github.com/gayurajeev/FastAPI-PAYFLOW-AI-hackathon
Built by Team XyphX.
```

