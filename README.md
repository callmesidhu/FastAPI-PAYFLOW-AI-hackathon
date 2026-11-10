# PAYFLOW AI

> AI-Powered Accounts Receivable Agent for Freelancers and Small Businesses.
> Built for the **PayPal AI Hackathon** by **Team XyphX**.

---

## Architecture & Design System

PAYFLOW AI combines a modern **FastAPI** backend with a high-performance **React + Vite + TypeScript** frontend adhering strictly to an **editorial quiet-luxury** aesthetic:
- **Palette**: Canvas `#FAF7F2`, Sand `#D9CFBA`, Cream `#EDE6D6`, Ink `#0B0B0B`, Muted `#4A4036`, Hairline `#3A342C`, Paid `#7A7F5A`, Pending `#B5835A`, Overdue `#8C4A3F`.
- **Typography**: Serif uppercase headings (`Playfair Display` / `Cormorant Garamond`) and clean sans-serif UI body (`Inter`).
- **Geometry**: Sharp 2px square corners, zero pills, no glassmorphism, no artificial gradients.
- **Financial Precision**: Authoritative backend arithmetic using Python `Decimal` with explicit ISO 4217 currencies.

---

## Repository Layout

```
payflow-ai/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI entrypoint, lifespan & /health
│   │   ├── api/               # API routers & endpoint definitions
│   │   ├── core/              # Typed pydantic-settings, logging & security
│   │   ├── db/                # MongoDB async connection & lifecycle
│   │   ├── models/            # Domain entities
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # PayPal, Invoice, and Auth domain services
│   │   ├── agents/            # AI orchestrator & tool definitions
│   │   ├── jobs/              # Reminder scheduling tasks
│   │   └── webhooks/          # PayPal webhook handlers & verification
│   ├── tests/                 # Automated pytest suite
│   ├── pyproject.toml         # Backend package configuration
│   └── requirements.txt       # Pinned dependency ranges
├── frontend/
│   ├── src/
│   │   ├── app/               # Main application shell & routing
│   │   ├── components/        # Error boundaries, loaders & UI primitives
│   │   ├── features/          # Dashboard, assistant, invoices, approvals
│   │   ├── lib/               # Typed API clients & utilities
│   │   └── styles/            # Quiet-luxury CSS design tokens
│   ├── index.html             # HTML entrypoint with typography links
│   ├── package.json           # React + Vite dependencies
│   ├── tsconfig.json          # TypeScript strict configuration
│   └── vite.config.ts         # Vite bundler & backend proxy config
├── docs/                      # Architectural specs & milestone tracking
├── public/                    # Project brand assets
├── .env.example               # Root environment configuration template
├── .gitignore                 # Comprehensive git ignore rules
└── LICENSE                    # MIT License
```

---

## Local Development Setup (Windows PowerShell)

For complete environment variable documentation and Render deployment settings, see [Environment Setup Guide](file:///c:/Users/sidha/OneDrive/Desktop/CodeDOT/FastAPI-PAYFLOW-AI-hackathon/docs/environment-setup.md).

### Prerequisites
- Python 3.11+ (Python 3.13 supported)
- Node.js 18+ (Node 22 LTS recommended)
- MongoDB instance (Atlas or local)
- PayPal Developer Sandbox account

### 1. Backend Setup

Open a Windows PowerShell terminal in the repository root:

```powershell
# Copy environment template
Copy-Item backend\.env.example backend\.env

# Navigate to backend
cd backend

# (Optional) Create and activate a Python virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run backend tests
python -m pytest tests

# Start FastAPI development server (with auto-reload)
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://127.0.0.1:8000`.
- Health check: `http://127.0.0.1:8000/health`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

### 2. Frontend Setup

Open a second Windows PowerShell terminal in the repository root:

```powershell
# Navigate to frontend
cd frontend

# Install Node dependencies
npm install

# Typecheck
npm run lint

# Start Vite development server
npm run dev
```

The application shell will be available at `http://localhost:5173`.

---

## Non-Negotiable Invariants

1. **Zero Secret Leakage**: No API keys, database URIs, or PayPal secrets in version control or browser client bundles.
2. **Deterministic Financial Math**: Monetary calculations execute via Python `Decimal` on the backend only.
3. **Multi-Tenant User Isolation**: Every database interaction is scoped to the authenticated `user_id`.
4. **Human-in-the-Loop**: The AI prepares proposals; the business owner explicitly authorizes PayPal sends.
5. **Strict Sandbox**: All PayPal operations strictly target the PayPal Sandbox (`api-m.sandbox.paypal.com`).
