# PAYFLOW AI — Build Contract & Architecture Specification

## 1. Project Overview & Mission
**PAYFLOW AI** is an AI-powered accounts receivable assistant for freelancers and small businesses. It streamlines the invoice-to-payment workflow:
1. Natural language invoice instruction
2. Structured invoice draft extraction
3. Explicit human approval via an Approval Center
4. PayPal Sandbox invoice creation and sending
5. Idempotent webhook verification and status synchronization
6. Receivables monitoring and contextual payment reminder generation

## 2. Core Architecture & Assumptions
- **Frontend**: React + Vite + TypeScript (strict mode). Editorial quiet-luxury design system.
- **Backend**: FastAPI (Python 3.13), async architecture, strict type annotations, Pydantic schemas.
- **Database**: MongoDB (via `motor` async driver) with explicit schema validation, indexes, and user-scoped collections.
- **PayPal Integration**: Official PayPal REST APIs exclusively in Sandbox (`api-m.sandbox.paypal.com`), OAuth client-credentials token caching, webhook signature verification.
- **AI Integration**: AI agent with validated tool calling for intent extraction, customer matching, and reminder drafting. The AI proposes actions but cannot bypass human approval or server-side authorization.
- **Financial Calculations**: Strict `Decimal` handling for all currency calculations. No floating-point math for money. Explicit ISO 4217 currency tracking.

## 3. Visual Design System — Editorial Quiet Luxury
| Token | Hex Value | Application |
| :--- | :--- | :--- |
| **Canvas / Background** | `#FAF7F2` | Main page canvas |
| **Sand** | `#D9CFBA` | Primary surface / layout bands |
| **Cream** | `#EDE6D6` | Secondary surface / tables |
| **Ink** | `#0B0B0B` | Primary buttons / feature cards |
| **Muted** | `#4A4036` | Body text / subtle detail |
| **Hairline** | `#3A342C` | 1px borders and dividers |
| **Paid** | `#7A7F5A` | Muted olive status |
| **Pending** | `#B5835A` | Muted clay status |
| **Overdue** | `#8C4A3F` | Muted brick status |

- **Typography**: Uppercase elegant serif headings (Playfair Display / Cormorant Garamond / serif fallback); Inter or clean sans-serif UI body with wide letter-spacing on uppercase labels.
- **Geometry**: Square corners (max 2px radius). No pills, glassmorphism, bright gradients, or heavy shadows.
- **Tables**: Cream backgrounds with fine hairline row dividers.

## 4. Proposed Repository Layout
```
payflow-ai/
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── docs/
│   ├── build-contract.md
│   ├── milestones.md
│   ├── paypal-integration.md
│   └── security.md
├── public/
│   └── logo.png
├── backend/
│   ├── .env.example
│   ├── pyproject.toml
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── agents/
│   │   ├── jobs/
│   │   └── webhooks/
│   └── tests/
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── index.html
    └── src/
        ├── app/
        ├── components/
        ├── features/
        │   ├── dashboard/
        │   ├── assistant/
        │   ├── invoices/
        │   ├── customers/
        │   ├── approvals/
        │   └── analytics/
        ├── lib/
        └── styles/
```

## 5. Non-Negotiable Engineering Rules
1. **Never commit secrets**: All keys stored in `.env` (ignored by git). `.env.example` provides placeholders.
2. **Never expose PayPal or AI secrets to the frontend**: All external API communications occur exclusively server-side.
3. **Multi-tenant User Scoping**: Every query and mutation is filtered by authenticated `user_id`.
4. **Authoritative Server Calculations**: All subtotal, tax, and total amounts are calculated on the backend using Python `Decimal`.
5. **Human-in-the-Loop**: Actions that alter external state (such as sending a PayPal invoice or sending customer reminders) require explicit user approval.
6. **Verified Status Only**: Payment status transitions only occur upon official PayPal webhook verification or direct PayPal API status sync.
