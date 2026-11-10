# PAYFLOW AI — Submission Assets

> Visual assets for Devpost submission. All screenshots captured from the **live running application**
> using Chrome DevTools Protocol (CDP). No fake data, mockups, or generated images.
>
> Demo data is **fictional** (Acme Global Solutions, Globex Corporation, Stark Advisory Group, Cyberdyne Analytics).
> All PayPal interactions target the **Sandbox environment** only.

---

## Asset Inventory

| File | Devpost Usage | Dimensions | Notes |
|------|--------------|------------|-------|
| `00_devpost_thumbnail.png` | **Thumbnail / Cover Image** | 1200×800 (3:2) | PAYFLOW AI wordmark + dashboard preview. ≤5 MB ✓ |
| `01_dashboard.png` | Gallery image 1 | 1280×900 | Live AR dashboard — fictional data |
| `02_ai_assistant_extraction.png` | Gallery image 2 | 1280×850 | AI invoice extraction chat view |
| `03_invoice_approval_preview.png` | Gallery image 3 | 1280×900 | Approval Center — SHA-256 hash visible |
| `04_invoice_list_aggrid.png` | Gallery image 4 | 1280×850 | AG Grid invoice list — sorting/filtering |
| `05_invoice_detail_paypal_status.png` | Gallery image 5 | 1280×900 | Invoice detail + PayPal sandbox status |
| `06_analytics_aging.png` | Gallery image 6 | 1280×900 | Aging analytics AG Grid + charts |
| `07_mobile_dashboard.png` | Mobile layout | 390×844 | Dashboard at iPhone viewport |
| `08_mobile_invoices.png` | Mobile layout | 390×844 | Invoice list at iPhone viewport |
| `09_paypal_sandbox_diagnostics.png` | PayPal integration | 1280×850 | Sandbox connection diagnostics |
| `10_login_page.png` | App overview | 1280×800 | Quiet-luxury login screen |

---

## Capture Method

Screenshots were captured using the CDP (Chrome DevTools Protocol) pipeline in
[`scripts/capture_gallery_screenshots.py`](../../scripts/capture_gallery_screenshots.py):

1. Demo backend (`app.demo_runner`) started on port 8000 — seeds fictional data in-memory
2. Frontend Vite preview server started on port 4173
3. Chrome headless launched with `--remote-debugging-port=9222`
4. Auth token injected via `sessionStorage` before navigating each authenticated view
5. Screenshots taken with `Page.captureScreenshot` at 1x device scale factor
6. Each view rendered in a separate `websockets.connect()` context (prevents connection drops)

---

## Devpost Thumbnail Spec

- **File:** `00_devpost_thumbnail.png`
- **Dimensions:** 1200×800 px (3:2 ratio — Devpost recommended)
- **File size:** ~83 KB (well within 5 MB limit)
- **Content:** Split-panel design — black feature panel (left) + dashboard UI preview (right)
- **Wordmark:** "PAYFLOW AI" legible at thumbnail scale
- **Font:** Georgia serif (wordmark) + Helvetica Neue (labels)
- **Color palette:** Quiet-luxury spec — Canvas `#FAF7F2`, Sand `#D9CFBA`, Ink `#0B0B0B`

---

## Truthfulness Attestation

- ✅ All screenshots are from the actual running application
- ✅ No Figma mockups, Canva designs, or generated imagery
- ✅ Dashboard numbers match seeded fictional demo records
- ✅ AG Grid is the actual `ag-grid-community` v36 library (not a fake table)
- ✅ PayPal status shown as "Sandbox / Not Connected" because no live credentials were configured during capture — this is accurate
- ✅ All company names (Acme Global, Globex, Stark Advisory, Cyberdyne) are fictional

---

## Regenerating Screenshots

```bash
# From project root:
python scripts/capture_gallery_screenshots.py
# Saves to docs/screenshots/ then copy relevant ones here
```

The script starts its own backend and frontend servers, so no manual startup is needed.

