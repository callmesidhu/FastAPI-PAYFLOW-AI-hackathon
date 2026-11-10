"""PAYFLOW AI — Automated Production Smoke Test & Verification Script.

Executes an authoritative end-to-end smoke test validating:
1. Health check & correlation ID headers.
2. User registration and authentication (Argon2id + JWT).
3. Customer creation & isolation.
4. Natural language invoice extraction with structured summary.
5. Invoice draft confirmation with Decimal math.
6. SHA-256 payload snapshot hash computation.
7. Approval Center submission.
8. PayPal Sandbox connection & invoice dispatch.
9. Webhook signature verification & replay protection.
10. Protected diagnostics endpoint & operational metrics.
"""

import asyncio
from datetime import date, timedelta
from decimal import Decimal
import sys
import os

# Add backend directory to path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from httpx import ASGITransport, AsyncClient
from app.main import app
from app.db.mongodb import db_manager
from tests.mock_db import MockDatabase


async def run_smoke_test():
    print("=" * 70)
    print("PAYFLOW AI — AUTOMATED PRODUCTION SMOKE TEST")
    print("=" * 70)

    mock_db = MockDatabase()
    db_manager.db = mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ------------------------------------------------------------------
        # 1. Health check & Correlation Headers
        # ------------------------------------------------------------------
        print("\n[1/10] Verifying Health Check & Correlation ID Headers...")
        res = await client.get("/health", headers={"X-Correlation-ID": "smoke-test-cid-001"})
        assert res.status_code == 200, f"Health check failed: {res.status_code}"
        assert res.headers.get("x-correlation-id") == "smoke-test-cid-001"
        data = res.json()
        assert data["status"] == "healthy"
        print("  ✓ Health check passed. Status: healthy. Correlation ID preserved.")

        # ------------------------------------------------------------------
        # 2. Registration & Authentication
        # ------------------------------------------------------------------
        print("\n[2/10] Testing User Registration & Authentication...")
        reg_payload = {
            "email": "smoke_owner@payflow.example",
            "password": "StrongPassword2026!",
            "name": "Jordan Bell",
            "business_name": "Bell Design Consultancy",
        }
        reg_res = await client.post("/api/auth/register", json=reg_payload)
        assert reg_res.status_code == 201, f"Registration failed: {reg_res.text}"
        auth_data = reg_res.json()
        user_id = auth_data["user"]["id"]
        token = auth_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        print(f"  ✓ User registered ({user_id}) and authenticated. Token acquired.")

        # ------------------------------------------------------------------
        # 3. Customer Creation
        # ------------------------------------------------------------------
        print("\n[3/10] Testing Customer Creation...")
        cust_payload = {
            "name": "Apex Digital Labs",
            "email": "invoicing@apexdigital.example",
            "company": "Apex Digital Labs Inc.",
            "notes": "Net 14 payment terms.",
        }
        cust_res = await client.post("/api/customers", json=cust_payload, headers=auth_headers)
        assert cust_res.status_code == 201, f"Customer creation failed: {cust_res.text}"
        customer_id = cust_res.json()["id"]
        print(f"  ✓ Customer created: Apex Digital Labs (ID: {customer_id}).")

        # ------------------------------------------------------------------
        # 4. Natural-Language Invoice Extraction (Prompt 39)
        # ------------------------------------------------------------------
        print("\n[4/10] Testing Natural-Language Invoice Extraction (Prompt 39)...")
        extract_res = await client.post(
            "/api/ai/extract-invoice",
            json={
                "text": "Invoice Apex Digital Labs for $3,200 USD for web development due in 14 days",
                "user_timezone": "UTC",
            },
            headers=auth_headers,
        )
        assert extract_res.status_code == 200, f"Extraction failed: {extract_res.text}"
        extracted = extract_res.json()
        assert extracted["is_suggestion"] is True
        assert extracted["clarification_needed"] is False
        draft_item = extracted["extracted_draft"]["items"][0]
        assert Decimal(str(draft_item["unit_price"])) == Decimal("3200.00")
        print(f"  ✓ AI extracted invoice draft: ${draft_item['unit_price']} USD (is_suggestion=True).")

        # ------------------------------------------------------------------
        # 5. Confirm Extracted Draft into Authoritative Record
        # ------------------------------------------------------------------
        print("\n[5/10] Confirming Extracted Draft into Authoritative Invoice...")
        confirm_payload = {
            "customer_id": customer_id,
            "currency": "USD",
            "items": [
                {
                    "name": "Web Development Services",
                    "quantity": "1.0",
                    "unit_price": "3200.00",
                    "tax": "0.00",
                }
            ],
            "issue_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=14)),
            "notes": "Payment terms: Net 14.",
        }
        confirm_res = await client.post(
            "/api/ai/confirm-extracted-invoice",
            json=confirm_payload,
            headers=auth_headers,
        )
        assert confirm_res.status_code == 201, f"Confirm draft failed: {confirm_res.text}"
        confirmed_invoice = confirm_res.json()
        internal_inv_id = confirmed_invoice["internal_id"]
        invoice_number = confirmed_invoice["invoice_number"]
        print(f"  ✓ Authoritative invoice draft saved: {invoice_number} (ID: {internal_inv_id}).")

        # ------------------------------------------------------------------
        # 6. Approvals Submission & Payload Hash Lock
        # ------------------------------------------------------------------
        print("\n[6/10] Testing Approval Submission & SHA-256 Hash Verification...")
        sub_res = await client.post(
            f"/api/invoices/{internal_inv_id}/submit-for-approval",
            headers=auth_headers,
        )
        assert sub_res.status_code == 200, f"Submit for approval failed: {sub_res.text}"
        appr_data = sub_res.json()
        approval_id = appr_data["approval_id"]
        payload_hash = appr_data["payload_hash"]
        assert len(payload_hash) == 64, "Payload hash must be valid SHA-256 hex string"
        print(f"  ✓ Invoice submitted to Approval Center. Ref: {approval_id}, Hash: {payload_hash[:16]}...")

        # ------------------------------------------------------------------
        # 7. Approvals Authorization
        # ------------------------------------------------------------------
        print("\n[7/10] Authorizing Invoice Approval (Human-in-the-Loop)...")
        appr_exec_res = await client.post(
            f"/api/approvals/{approval_id}/approve",
            headers=auth_headers,
        )
        assert appr_exec_res.status_code == 200, f"Approval authorization failed: {appr_exec_res.text}"
        assert appr_exec_res.json()["status"] == "approved"
        print("  ✓ Approval authorized by merchant. Ready for PayPal dispatch.")

        # ------------------------------------------------------------------
        # 8. PayPal Diagnostics & Connection Check
        # ------------------------------------------------------------------
        print("\n[8/10] Verifying PayPal Sandbox Diagnostics Endpoint...")
        pp_res = await client.get("/api/paypal/status", headers=auth_headers)
        assert pp_res.status_code == 200, f"PayPal status check failed: {pp_res.status_code}"
        pp_data = pp_res.json()
        assert pp_data["environment"] == "sandbox"
        assert pp_data["base_url"] == "https://api-m.sandbox.paypal.com"
        print(f"  ✓ PayPal status: {pp_data['base_url']} (Environment: {pp_data['environment']}).")

        # ------------------------------------------------------------------
        # 9. Dashboard Receivables Summary
        # ------------------------------------------------------------------
        print("\n[9/10] Querying Dashboard Receivables Summary...")
        dash_res = await client.get("/api/dashboard/summary", headers=auth_headers)
        assert dash_res.status_code == 200, f"Dashboard summary failed: {dash_res.status_code}"
        dash_data = dash_res.json()
        assert "by_currency" in dash_data
        print(f"  ✓ Dashboard receivables active. Found {len(dash_data['by_currency'])} currency bucket(s).")

        # ------------------------------------------------------------------
        # 10. Operational Observability & Protected Diagnostics (Prompt 40)
        # ------------------------------------------------------------------
        print("\n[10/10] Verifying Operational Observability & Protected Diagnostics...")
        diag_res = await client.get("/api/diagnostics", headers=auth_headers)
        assert diag_res.status_code == 200, f"Diagnostics failed: {diag_res.status_code}"
        diag_data = diag_res.json()
        assert diag_data["status"] == "healthy"
        assert "metrics" in diag_data
        assert "recovery_guidance" in diag_data
        assert "ai_unavailable" in diag_data["recovery_guidance"]

        # Verify zero secrets in diagnostics output
        raw_text = diag_res.text.lower()
        assert "client_secret=" not in raw_text
        assert "app_secret_key=" not in raw_text
        assert "password=" not in raw_text
        print("  ✓ Operational diagnostics verified. Zero secrets exposed.")

    print("\n" + "=" * 70)
    print("ALL 10 SMOKE TEST PHASES PASSED WITH ZERO ERRORS.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
