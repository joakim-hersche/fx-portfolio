"""
Automated screenshot capture for the Market Dashboard.

Launches the Streamlit app, loads the sample portfolio, and captures
full-tab screenshots of every section in both dark and light mode.
Saves PNGs to Screenshots/dark/ and Screenshots/light/.

Usage:
    python3 take_screenshots.py

Requirements:
    pip install playwright && playwright install chromium
"""

import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

APP_URL  = "http://localhost:8501"
ROOT     = Path(__file__).parent
SCDIR    = ROOT / "Screenshots"
CONFIG   = ROOT / ".streamlit" / "config.toml"

# MacBook 13" equivalent viewport (1440×900 logical → ×2 HiDPI)
WIDTH  = 1440
HEIGHT = 900


# ── helpers ────────────────────────────────────────────────────────────────

def wait_for_app_ready(page, timeout=120):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page.locator('[data-testid="stStatusWidget"]').count() == 0:
            return
        time.sleep(1)
    raise TimeoutError("Streamlit app did not finish loading")


def click_tab(page, label):
    page.get_by_role("tab", name=label).click()
    time.sleep(0.5)
    wait_for_app_ready(page)
    time.sleep(1)


def load_sample_portfolio(page):
    print("  Loading sample portfolio...")
    page.get_by_role("button", name="Load Sample Portfolio").click()
    wait_for_app_ready(page)
    time.sleep(1)
    page.get_by_role("button", name="Yes, load sample").click()
    time.sleep(3)
    wait_for_app_ready(page)
    print("  Waiting for data to settle...")
    time.sleep(10)
    wait_for_app_ready(page)


def shoot(page, path: Path, full_page=False):
    page.evaluate("window.scrollTo(0, 0)")
    time.sleep(0.5)
    page.screenshot(path=str(path), full_page=full_page)
    print(f"    {path.name}")


# ── per-theme pass ──────────────────────────────────────────────────────────

def run_pass(pw, theme: str):
    out = SCDIR / theme
    out.mkdir(parents=True, exist_ok=True)
    print(f"\n── {theme.upper()} ──────────────────────────────────────────")

    # Swap Streamlit theme config
    CONFIG.write_text(f'[theme]\nbase = "{theme}"\nprimaryColor = "#3B82F6"\n')

    # Start server
    server = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.headless=true", "--server.port=8501",
         "--browser.gatherUsageStats=false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        cwd=str(ROOT),
    )
    time.sleep(3)

    try:
        browser = pw.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": WIDTH, "height": HEIGHT},
            device_scale_factor=2,
        )
        page = ctx.new_page()

        # Connect
        for _ in range(30):
            try:
                page.goto(APP_URL, timeout=5000)
                break
            except Exception:
                time.sleep(2)
        else:
            raise RuntimeError("Could not connect to Streamlit")

        wait_for_app_ready(page)
        load_sample_portfolio(page)
        print("  Capturing screenshots...")

        # 01 Overview — above fold
        click_tab(page, "Overview")
        shoot(page, out / "01_overview_hero.png")

        # 02 Overview — full page
        page.screenshot(path=str(out / "02_overview_full.png"), full_page=True)
        print(f"    02_overview_full.png")

        # 03 Positions — viewport + full
        click_tab(page, "Positions")
        shoot(page, out / "03_positions_hero.png")
        page.screenshot(path=str(out / "03_positions_full.png"), full_page=True)
        print(f"    03_positions_full.png")

        # 04 Risk & Analytics — viewport + full
        click_tab(page, "Risk & Analytics")
        shoot(page, out / "04_risk_hero.png")
        page.screenshot(path=str(out / "04_risk_full.png"), full_page=True)
        print(f"    04_risk_full.png")

        # 05 Forecast — viewport + full
        click_tab(page, "Forecast")
        time.sleep(2)
        shoot(page, out / "05_forecast_hero.png")
        page.screenshot(path=str(out / "05_forecast_full.png"), full_page=True)
        print(f"    05_forecast_full.png")

        # 06 Diagnostics — viewport + full
        click_tab(page, "Diagnostics")
        time.sleep(2)
        shoot(page, out / "06_diagnostics_hero.png")
        page.screenshot(path=str(out / "06_diagnostics_full.png"), full_page=True)
        print(f"    06_diagnostics_full.png")

        # 07 Sidebar close-up
        click_tab(page, "Overview")
        time.sleep(0.5)
        sidebar = page.locator('[data-testid="stSidebar"]')
        if sidebar.count():
            sidebar.screenshot(path=str(out / "07_sidebar.png"))
            print(f"    07_sidebar.png")

        browser.close()
        print(f"  Done → {out}")

    finally:
        server.terminate()
        server.wait()
        time.sleep(1)


def main():
    with sync_playwright() as pw:
        run_pass(pw, "dark")
        run_pass(pw, "light")
    # Restore dark as default
    CONFIG.write_text('[theme]\nbase = "dark"\nprimaryColor = "#3B82F6"\n')
    print("\nAll done. Config restored to dark.")


if __name__ == "__main__":
    main()
