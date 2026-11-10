# PAYFLOW AI — Authentication, Ownership & Demo Credentials

This guide outlines user authentication, data isolation guarantees, and demo user provisioning.

---

## 1. Authentication Architecture

PAYFLOW AI implements a modern, secure authentication scheme:
- **Password Hashing**: Modern **Argon2id** (`time_cost=2`, `memory_cost=100 MiB`, `parallelism=8`) via `argon2-cffi`. Raw passwords are never stored or logged.
- **Access Tokens**: Short-lived JSON Web Tokens (JWT) signed via HMAC-SHA256 using the environment variable `APP_SECRET_KEY`.
- **Enumeration Protection**: Login failures return generic 401 Unauthorized messages ("Invalid email or password") without disclosing whether an email address is registered.

---

## 2. User Ownership & Multi-Tenant Data Isolation

### Invariant: Authenticated Context is Authoritative
Every database query and mutation across customers, invoices, approvals, reminders, transactions, and audit records **must** be scoped to `current_user.id`.

```python
# SECURE (enforced in PAYFLOW AI):
@router.get("/api/invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db)
):
    # Strictly filtered by both internal_id AND authenticated user_id
    invoice = await db.invoices.find_one({"internal_id": invoice_id, "user_id": current_user.id})
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice
```

- A caller cannot supply a different `user_id` to read or mutate another user's business records.
- Cross-user queries always return `404 Not Found` (or `403 Forbidden`), completely isolating multi-tenant data.

---

## 3. Demo User Seed Script

For local evaluation and hackathon testing, a demo account can be seeded:

### Execution (Windows PowerShell)
```powershell
cd backend
python scripts/seed_demo_user.py --confirm
```

### Safety Guardrails
- **Disabled by Default**: Running without `--confirm` or `ALLOW_DEMO_SEED=true` exits immediately with an error.
- **Idempotent**: If the demo user already exists, the script does not duplicate or alter existing data.

### Vital Sandbox Distinction
> [!IMPORTANT]
> **PAYFLOW AI Demo Credentials $\neq$ PayPal Sandbox Credentials**
> - The demo credentials (`demo@payflow.local` / `DemoPassword2026!`) grant login access **only** to the PAYFLOW AI application web interface.
> - When testing invoice payments via PayPal Sandbox, judges must use a separate **PayPal Sandbox Personal/Buyer account** created via the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/accounts). Never use your PAYFLOW AI password on PayPal.
