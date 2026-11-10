# PAYFLOW AI — Milestone Roadmap & Execution Order

This phased roadmap aligns directly with the **PayPal AI Hackathon Master Prompt Playbook**. Each prompt represents a bounded milestone with strict acceptance checks.

---

### Milestone 1: Foundations & Core Persistence (Prompts 01 – 08)
- [x] **PROMPT 01 — Workspace inspection and build contract**
  - Inspect repository, verify existing assets, establish build contract, directory tree, and `.gitignore` / `.env.example`.
- [x] **PROMPT 02 — Create repository scaffold**
  - Minimal runnable FastAPI backend (`/health`) and Vite + React + TypeScript frontend.
- [x] **PROMPT 03 — Environment configuration and safe settings**
  - Typed `pydantic-settings` with secret masking, CORS configuration, and zero credential leakage.
- [x] **PROMPT 04 — MongoDB connection and persistence layer**
  - Async MongoDB (`motor`) setup, lifecycle management, index creation, and connection ping.
- [x] **PROMPT 05 — Domain models and money rules**
  - Pydantic models with `Decimal` precision, ISO 4217 currencies, and immutable state transitions.
- [x] **PROMPT 06 — Authentication and user ownership**
  - User registration, login, Argon2id password hashing, JWTs, and strict `user_id` record scoping.
- [x] **PROMPT 07 — Customer management APIs**
  - User-scoped customer CRUD, pagination, search, and safe deletion protections.
- [x] **PROMPT 08 — Invoice domain service and APIs**
  - Authoritative draft creation, unique human-readable invoice numbers, decimal arithmetic, and audit logging.

---

### Milestone 2: Editorial Frontend & Application Shell (Prompts 09 – 13)
- [x] **PROMPT 09 — Frontend foundation and editorial design tokens**
  - Editorial quiet-luxury CSS variables, typography, flat square geometry, and accessible core components.
- [x] **PROMPT 10 — App navigation and authentication screens**
  - Routing, Login/Register screens, layout sidebar, authenticated API client, and calm UX.
- [x] **PROMPT 11 — Dashboard with real receivables data**
  - Real receivables aggregates, per-currency totals, attention section, and black feature cards.
- [x] **PROMPT 12 — Invoice list, detail, and creation UI**
  - Flat cream data tables, invoice drafting form with live calculation preview, and detail view.
- [x] **PROMPT 13 — Approval center and policy engine**
  - Human-in-the-loop approval mechanism: payload hashing, invalidation on modification, audit trails.

---

### Milestone 3: PayPal Sandbox Integration (Prompts 14 – 16)
- [ ] **PROMPT 14 — PayPal Sandbox developer setup**
  - Official REST API documentation review (`docs/paypal-integration.md`), OAuth client-credentials flow, memory token caching.
- [ ] **PROMPT 15 — PayPal invoice creation adapter**
  - Mapping internal invoice model to official PayPal invoicing payload, idempotency, and URL persistence.
- [ ] **PROMPT 16 — Send invoice through PayPal**
  - Executing approved invoice sending via PayPal Sandbox, audit log tracking, and visible Sandbox labeling.

---

### Milestone 4: AI Assistant & Natural Language Processing (Prompts 17 – 20)
- [ ] **PROMPT 17 — AI provider abstraction and structured output**
  - Pluggable AI service, Pydantic tool schemas, clarification mechanism, and secret sandboxing.
- [ ] **PROMPT 18 — AI assistant tool calling**
  - Orchestrator with safe backend tools (`search_customers`, `create_invoice_draft`, `get_receivables_summary`, etc.).
- [ ] **PROMPT 19 — AI invoice extraction and preview**
  - Conversational invoice creation ("Create a $500 invoice for John Smith..."), structured editable preview.
- [ ] **PROMPT 20 — Receivables queries and analytics**
  - Natural-language queries over aging buckets (0–7, 8–30, 31–60, 60+ days) backed by real database aggregates.

---

### Milestone 5: Reminders, Webhooks & Ledger (Prompts 21 – 24)
- [ ] **PROMPT 21 — Reminder policy and message generation**
  - Stage-based reminder policies (upcoming, due today, overdue), respectful AI copy generation.
- [ ] **PROMPT 22 — Reminder scheduler and delivery channel**
  - Background scheduler candidate generation, queueing to Approval Center, audit logs.
- [ ] **PROMPT 23 — PayPal webhook verification and reconciliation**
  - Official PayPal webhook signature verification, replay prevention, and payment status sync.
- [ ] **PROMPT 24 — Transaction ledger and audit trail**
  - Append-only activity timeline tracking all user and system lifecycle events.

---

### Milestone 6: Sponsor Integrations & Deployment (Prompts 25 – 30)
- [ ] **PROMPT 25 — AG Grid meaningful sponsor integration** (Sponsor: AG Grid)
- [ ] **PROMPT 26 — Bryntum calendar integration** (Optional)
- [ ] **PROMPT 27 — Postman API collection** (Sponsor: Postman)
- [ ] **PROMPT 28 — APIMatic Context Plugin usage** (Sponsor: APIMatic)
- [ ] **PROMPT 29 — Zapier integration** (Optional Sponsor: Zapier)
- [ ] **PROMPT 30 — Render deployment preparation** (Sponsor: Render)

---

### Milestone 7: End-to-End Testing & Judge Readiness (Prompts 31 – 38)
- [ ] **PROMPT 31 — End-to-end integration test**
- [ ] **PROMPT 32 — UI polish and responsive quality pass**
- [ ] **PROMPT 33 — Security review and abuse cases**
- [ ] **PROMPT 34 — README, license, and public repository readiness**
- [ ] **PROMPT 35 — Demo data and judge testing experience**
- [ ] **PROMPT 36 — Project screenshots and thumbnail assets**
- [ ] **PROMPT 37 — Three-minute YouTube demo script**
- [ ] **PROMPT 38 — Devpost submission fact-check and finalization**

---

### Optional Improvement Prompts (Prompts 39 – 41)
- [ ] **PROMPT 39 — Natural-language correction and confirmation quality**
- [ ] **PROMPT 40 — Operational observability and graceful failure**
- [ ] **PROMPT 41 — Final regression and release candidate**
