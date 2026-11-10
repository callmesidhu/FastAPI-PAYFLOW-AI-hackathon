# PAYFLOW AI — Environment Configuration & Secrets Management Guide

This guide details how to configure environment variables safely for local development (Windows PowerShell) and production deployment (Render Dashboard).

---

## 1. Environment Variables Reference

| Variable | Required in Prod? | Default (Sandbox/Dev) | Description |
| :--- | :---: | :--- | :--- |
| `APP_ENV` | Yes | `development` | Runtime environment (`development`, `test`, `production`). |
| `APP_SECRET_KEY` | Yes | `dev-insecure-...` | Salt & signature secret for JWT tokens (must be >= 32 chars in prod). |
| `PORT` | No | `8000` | Port for the backend service. |
| `FRONTEND_ORIGIN` | Yes | `http://localhost:5173` | Comma-separated list of allowed origins for CORS. Wildcards (`*`) are rejected in production. |
| `MONGODB_URI` | Yes | `mongodb://localhost:27017` | MongoDB connection string (Atlas SRV or local). Credentials are automatically masked in logs. |
| `MONGODB_DATABASE` | No | `payflow_ai` | Target MongoDB database name. |
| `PAYPAL_BASE_URL` | No | `https://api-m.sandbox.paypal.com` | Official PayPal Sandbox REST API host. Live endpoints (`api.paypal.com`) are rejected. |
| `PAYPAL_CLIENT_ID` | Yes | *Empty / Mock* | PayPal Developer Sandbox App Client ID. |
| `PAYPAL_CLIENT_SECRET` | Yes | *Empty / Mock* | PayPal Developer Sandbox App Client Secret. |
| `PAYPAL_WEBHOOK_ID` | Yes | *Empty / Mock* | Webhook ID created in the PayPal Developer Dashboard for signature verification. |
| `AI_PROVIDER` | No | `gemini` | Supported providers: `gemini`, `openai`, `mock`. |
| `AI_API_KEY` | Yes | *Empty / Mock* | API Key for the chosen AI provider. |
| `AI_MODEL` | No | `gemini-2.5-flash` | Model identifier for tool calling and reasoning. |
| `EMAIL_PROVIDER` | No | *None* | Optional transactional email provider. |
| `ZAPIER_WEBHOOK_URL`| No | *None* | Optional Zapier Catch Hook URL for approved reminders. |

---

## 2. Windows PowerShell Setup (Local Development)

### Method A: Using a `.env` File (Recommended)
Copy the template to `backend/.env`:
```powershell
Copy-Item backend\.env.example backend\.env
```
Edit `backend/.env` with your sandbox keys. The file is listed in `.gitignore` and will never be committed.

### Method B: Setting Session Environment Variables in PowerShell
To set variables for your current PowerShell terminal session:
```powershell
$env:APP_ENV="development"
$env:APP_SECRET_KEY="temporary-local-dev-secret-key-32chars"
$env:MONGODB_URI="mongodb://localhost:27017"
$env:PAYPAL_BASE_URL="https://api-m.sandbox.paypal.com"
$env:PAYPAL_CLIENT_ID="your_sandbox_client_id"
$env:PAYPAL_CLIENT_SECRET="your_sandbox_client_secret"
$env:AI_PROVIDER="gemini"
$env:AI_API_KEY="your_gemini_api_key"

# Verify a variable (without displaying full secrets)
Write-Host "PayPal Sandbox Base URL:" $env:PAYPAL_BASE_URL
```

### Method C: Development Fallback Mode
If external credentials (`PAYPAL_CLIENT_ID`, `AI_API_KEY`) are not provided, the server starts safely in **development mode**:
- The `/health` endpoint remains accessible with HTTP 200.
- Clear, actionable notices are printed to the console explaining which integrations are operating in local/mock mode.
- Unit and contract tests pass without requiring live external network access.

---

## 3. Render Dashboard Setup (Production Deployment)

When deploying to [Render](https://render.com) (Prompt 30):

1. **Navigate to your Web Service** in the Render Dashboard.
2. Click on **Environment** in the left sidebar menu.
3. Click **Add Environment Variable** for each of the following:

```
APP_ENV = production
APP_SECRET_KEY = <generate a 64-char random hex string>
FRONTEND_ORIGIN = https://payflow-ai-frontend.onrender.com
MONGODB_URI = mongodb+srv://<username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority
MONGODB_DATABASE = payflow_ai
PAYPAL_BASE_URL = https://api-m.sandbox.paypal.com
PAYPAL_CLIENT_ID = <your_paypal_sandbox_client_id>
PAYPAL_CLIENT_SECRET = <your_paypal_sandbox_client_secret>
PAYPAL_WEBHOOK_ID = <your_paypal_sandbox_webhook_id>
AI_PROVIDER = gemini
AI_API_KEY = <your_gemini_api_key>
AI_MODEL = gemini-2.5-flash
```

> [!IMPORTANT]
> - Never set `PAYPAL_BASE_URL` to `https://api.paypal.com` on Render during the hackathon. The system will reject startup if an accidental live PayPal host is detected.
> - Never set `FRONTEND_ORIGIN` to `*` in production. Wildcards in production mode cause an explicit startup rejection.
> - Use Render's **Secret Files** or dashboard environment variables. Do **not** commit `.env` into git.

---

## 4. Secret Masking & Security Invariants

- **Endpoint Isolation**: The public `/health` and `/` endpoints return only high-level status (`status`, `app`, `version`, `environment`). They never serialize configuration values or credentials.
- **Log Protection**: Application loggers and `Settings.__repr__` automatically redact credentials and passwords embedded within connection strings (e.g. `mongodb://admin:***@...`).
