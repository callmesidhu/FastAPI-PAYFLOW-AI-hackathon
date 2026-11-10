"""Automated screenshot capture pipeline for PAYFLOW AI Submission Gallery (Prompt 32).

Uses Chrome DevTools Protocol (CDP) to render and capture all primary views
at both desktop (1280x800) and mobile (390x844) viewports with zero fake data.
"""

import asyncio
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request
import websockets

SCREENSHOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots"))
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


async def send_cdp(ws, method, params=None, msg_id=1):
    payload = {"id": msg_id, "method": method}
    if params:
        payload["params"] = params
    await ws.send(json.dumps(payload))
    while True:
        res = await ws.recv()
        data = json.loads(res)
        if data.get("id") == msg_id:
            return data


async def get_page_ws_url():
    req = urllib.request.urlopen("http://127.0.0.1:9222/json/list", timeout=2)
    targets = json.loads(req.read().decode("utf-8"))
    for t in targets:
        if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
            return t["webSocketDebuggerUrl"]
    return None


async def capture_view(url, output_filename, token=None, width=1280, height=800, wait_seconds=2.0):
    ws_url = await get_page_ws_url()
    if not ws_url:
        print(f"  ✗ Could not find CDP page target for {output_filename}")
        return

    async with websockets.connect(ws_url, ping_interval=None, ping_timeout=None, max_size=25 * 1024 * 1024) as ws:
        # 1. Enable Page
        await send_cdp(ws, "Page.enable", msg_id=1)

        # 2. Emulate screen dimensions
        await send_cdp(
            ws,
            "Emulation.setDeviceMetricsOverride",
            {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": width < 768,
            },
            msg_id=2,
        )

        # 3. Inject token if authenticated view
        if token:
            await send_cdp(ws, "Page.navigate", {"url": "http://127.0.0.1:4173/login"}, msg_id=3)
            await asyncio.sleep(0.6)
            await send_cdp(
                ws,
                "Runtime.evaluate",
                {
                    "expression": f"sessionStorage.setItem('payflow_session_token', '{token}');"
                },
                msg_id=4,
            )

        # 4. Navigate to target URL
        await send_cdp(ws, "Page.navigate", {"url": url}, msg_id=5)
        await asyncio.sleep(wait_seconds)

        # 5. Capture crisp PNG
        res = await send_cdp(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=6)
        img_b64 = res["result"]["data"]
        img_bytes = base64.b64decode(img_b64)

        out_path = os.path.join(SCREENSHOT_DIR, output_filename)
        with open(out_path, "wb") as f:
            f.write(img_bytes)
        print(f"  ✓ Saved: {output_filename} ({len(img_bytes):,} bytes)")


async def main():
    print("=" * 60)
    print("PAYFLOW AI — Visual Quality Review & Screenshot Capture")
    print("=" * 60)

    # 1. Start Demo Backend Server on Port 8000
    print("[1/4] Launching Demo Backend Server (port 8000)...")
    backend_env = os.environ.copy()
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    backend_env["PYTHONPATH"] = backend_dir

    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "app.demo_runner"],
        cwd=backend_dir,
        env=backend_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for backend to be ready
    token = None
    last_err = None
    for _ in range(30):
        try:
            req = urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
            if req.status == 200:
                # Login to get token
                login_payload = json.dumps({"email": "demo@payflowai.com", "password": "DemoPassword2026!"}).encode("utf-8")
                l_req = urllib.request.Request(
                    "http://127.0.0.1:8000/api/auth/login",
                    data=login_payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(l_req) as l_res:
                    l_data = json.loads(l_res.read().decode("utf-8"))
                    token = l_data["access_token"]
                break
        except Exception as e:
            last_err = e
            await asyncio.sleep(0.5)

    if not token:
        print(f"Backend failed to start or login failed. Last error: {last_err}")
        backend_proc.kill()
        return

    print(f"  ✓ Backend live with Demo Token: {token[:15]}...")

    # 2. Start Frontend Preview on Port 4173
    print("[2/4] Launching Frontend Preview Server (port 4173)...")
    frontend_proc = subprocess.Popen(
        ["npx", "vite", "preview", "--port", "4173", "--host", "127.0.0.1"],
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend")),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(20):
        try:
            req = urllib.request.urlopen("http://127.0.0.1:4173/", timeout=1)
            if req.status == 200:
                break
        except Exception:
            await asyncio.sleep(0.5)

    print("  ✓ Frontend preview server ready.")

    # 3. Launch Headless Chrome with Remote Debugging
    print("[3/4] Launching Headless Chrome with CDP...")
    profile_dir = "/tmp/payflow_cdp_profile"
    chrome_proc = subprocess.Popen(
        [
            CHROME_PATH,
            "--headless=new",
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile_dir}",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1280,800",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    ws_url = None
    for _ in range(25):
        try:
            ws_url = await get_page_ws_url()
            if ws_url:
                break
        except Exception:
            pass
        await asyncio.sleep(0.5)

    if not ws_url:
        print("Could not connect to Chrome DevTools Protocol.")
        chrome_proc.kill()
        frontend_proc.kill()
        backend_proc.kill()
        return

    print("  ✓ Connected to Chrome DevTools Protocol.")

    # 4. Capture Views
    print("[4/4] Capturing Quiet-Luxury Views...")
    try:
        views = [
            ("http://127.0.0.1:4173/login", "01_login_desktop.png", None, 1280, 800, 1.5),
            ("http://127.0.0.1:4173/login", "01_login_mobile.png", None, 390, 844, 1.5),
            ("http://127.0.0.1:4173/register", "02_register_desktop.png", None, 1280, 800, 1.5),
            ("http://127.0.0.1:4173/dashboard", "03_dashboard_receivables_desktop.png", token, 1280, 900, 2.5),
            ("http://127.0.0.1:4173/dashboard", "03_dashboard_receivables_mobile.png", token, 390, 844, 2.0),
            ("http://127.0.0.1:4173/invoices", "04_ag_grid_invoices_desktop.png", token, 1280, 850, 2.5),
            ("http://127.0.0.1:4173/invoices", "04_ag_grid_invoices_mobile.png", token, 390, 844, 2.0),
            ("http://127.0.0.1:4173/invoices/inv_001_settled", "05_invoice_detail_timeline_desktop.png", token, 1280, 900, 2.0),
            ("http://127.0.0.1:4173/approvals", "06_approvals_center_desktop.png", token, 1280, 900, 2.5),
            ("http://127.0.0.1:4173/assistant", "07_ai_assistant_desktop.png", token, 1280, 850, 2.0),
            ("http://127.0.0.1:4173/customers", "08_customers_directory_desktop.png", token, 1280, 850, 2.0),
            ("http://127.0.0.1:4173/analytics", "09_analytics_aging_aggrid_desktop.png", token, 1280, 900, 2.5),
            ("http://127.0.0.1:4173/settings", "10_settings_paypal_diagnostics_desktop.png", token, 1280, 850, 2.0),
        ]

        for url, filename, auth_token, w, h, wait_sec in views:
            try:
                await capture_view(url, filename, token=auth_token, width=w, height=h, wait_seconds=wait_sec)
            except Exception as e:
                print(f"  ✗ Error capturing {filename}: {e}")

    finally:
        print("Cleaning up background processes...")
        chrome_proc.kill()
        frontend_proc.kill()
        backend_proc.kill()
        print("All processes terminated cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
