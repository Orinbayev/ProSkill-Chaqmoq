#!/usr/bin/env python3
"""
Playwright headless screenshot capture for ChaqmoqApp dashboards.
Saves to: marketing/static/marketing/img/dashboards/

Usage:
    python3 scripts/capture_dashboards.py

Credentials: phone +998901112112, center: test-markaz
"""
import asyncio
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

BASE_URL = "http://127.0.0.1:8888"
LOGIN_URL = f"{BASE_URL}/login/"
TENANT_SLUG = "test-markaz"
PHONE = "+998901112112"
# We'll use Django set_password approach — provide password below
PASSWORD = os.environ.get("CAPTURE_PASSWORD", "admin1234")

OUTPUT_DIR = os.path.join(PROJECT_ROOT, "marketing", "static", "marketing", "img", "dashboards")

SHOTS = [
    {
        "name": "director",
        "url": f"{BASE_URL}/{TENANT_SLUG}/boshqaruv/",
        "label": "Director asosiy panel",
        "wait_for": ".director-dash, .stat-card, .boshqaruv, main",
    },
    {
        "name": "financial",
        "url": f"{BASE_URL}/{TENANT_SLUG}/dashboards/financial/",
        "label": "Moliyaviy dashboard",
        "wait_for": "main",
    },
    {
        "name": "attendance",
        "url": f"{BASE_URL}/{TENANT_SLUG}/dashboards/overview/",
        "label": "Davomat dashboard",
        "wait_for": "main",
    },
    {
        "name": "students",
        "url": f"{BASE_URL}/{TENANT_SLUG}/stat/students/",
        "label": "O'quvchilar",
        "wait_for": "main",
    },
    {
        "name": "billing",
        "url": f"{BASE_URL}/{TENANT_SLUG}/dashboards/billing/",
        "label": "To'lovlar dashboard",
        "wait_for": "main",
    },
    {
        "name": "groups",
        "url": f"{BASE_URL}/{TENANT_SLUG}/dashboards/groups/",
        "label": "Guruhlar dashboard",
        "wait_for": "main",
    },
]


async def capture():
    from playwright.async_api import async_playwright

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=1.5,
        )
        page = await context.new_page()

        # -- Login --
        print(f"Logging in at {LOGIN_URL}...")
        await page.goto(LOGIN_URL, wait_until="networkidle", timeout=20000)

        # Fill login form
        await page.fill('input[name="username"]', PHONE)
        await page.fill('input[name="password"]', PASSWORD)
        await page.click('button[type="submit"]')

        # Wait for redirect after login
        await page.wait_for_load_state("networkidle", timeout=15000)
        current = page.url
        print(f"After login: {current}")

        if "login" in current.lower() or "hisob/login" in current.lower():
            print("ERROR: Login failed. Check credentials.")
            print("Page content:", await page.content()[:400])
            await browser.close()
            sys.exit(1)

        print("Login successful.")

        # -- Capture each dashboard --
        for shot in SHOTS:
            print(f"Capturing: {shot['name']} -> {shot['url']}")
            try:
                await page.goto(shot["url"], wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(2500)  # let charts render

                # Try to wait for a specific element
                try:
                    await page.wait_for_selector(shot["wait_for"], timeout=5000)
                except Exception:
                    pass  # continue anyway

                # Hide any modals/toasts
                await page.evaluate("""
                    () => {
                        document.querySelectorAll('.modal, .toast, .alert-dismissible').forEach(el => {
                            el.style.display = 'none';
                        });
                    }
                """)

                out_path = os.path.join(OUTPUT_DIR, f"{shot['name']}.jpg")
                await page.screenshot(
                    path=out_path,
                    full_page=False,
                    type="jpeg",
                    quality=85,
                )
                print(f"  Saved: {out_path}")

            except Exception as exc:
                print(f"  ERROR capturing {shot['name']}: {exc}")

        await browser.close()
        print("Done.")


if __name__ == "__main__":
    asyncio.run(capture())
