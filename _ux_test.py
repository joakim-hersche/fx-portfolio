"""Comprehensive UX audit test — exercises every button, toggle, tab, and
interaction in the Market Dashboard and reports timing + visual issues.

Run: python3 _ux_test.py
"""

import subprocess
import sys
import time
import signal
import socket
import os
import json

from playwright.sync_api import sync_playwright

PORT = 8082
URL = f"http://localhost:{PORT}"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SCREENSHOT_DIR = os.path.join(APP_DIR, "_ux_screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

results = []


def log(msg, ok=True, timing_ms=None):
    status = "PASS" if ok else "FAIL"
    timing = f" ({timing_ms:.0f}ms)" if timing_ms else ""
    results.append({"status": status, "msg": msg, "timing_ms": timing_ms})
    print(f"[{status}] {msg}{timing}")


def screenshot(page, name):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    page.screenshot(path=path, full_page=True)
    return path


def measure(fn, *args, **kwargs):
    """Run fn and return (result, elapsed_ms)."""
    t0 = time.time()
    result = fn(*args, **kwargs)
    return result, (time.time() - t0) * 1000


def run_tests():
    # Start the app
    launcher = os.path.join(APP_DIR, "_test_launcher.py")
    # Patch launcher to use our port
    env = os.environ.copy()
    env["TEST_PORT"] = str(PORT)

    proc = subprocess.Popen(
        [sys.executable, "-c", f"""
import glob, os, sys
sys.path.insert(0, "{APP_DIR}")
nicegui_dir = os.path.join("{APP_DIR}", ".nicegui")
for f in glob.glob(os.path.join(nicegui_dir, "storage-user-*.json")):
    os.remove(f)
from nicegui import ui
_original_run = ui.run
def _patched_run(**kwargs):
    kwargs["port"] = {PORT}
    kwargs["show"] = False
    kwargs["reload"] = False
    _original_run(**kwargs)
ui.run = _patched_run
import main
"""],
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )

    try:
        print("Waiting for server to start...")
        for i in range(45):
            time.sleep(1)
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode()
                print(f"App crashed:\n{stderr[-3000:]}")
                log("App failed to start", ok=False)
                return
            try:
                s = socket.create_connection(("localhost", PORT), timeout=1)
                s.close()
                print(f"Server ready after {i+1}s")
                break
            except OSError:
                pass
        else:
            log("Server did not start in 45s", ok=False)
            return

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.set_default_timeout(60000)

            # Collect console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

            # ═══════════════════════════════════════════════════
            # PHASE 1: Empty state tests
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 1: Empty State ===")

            _, load_ms = measure(lambda: page.goto(URL, wait_until="domcontentloaded"))
            page.wait_for_timeout(5000)
            log(f"Initial page load (empty portfolio)", timing_ms=load_ms)
            screenshot(page, "01_empty_state")

            # Check sidebar is visible
            try:
                page.locator(".q-drawer").first.wait_for(state="visible", timeout=5000)
                log("Sidebar visible on load")
            except Exception:
                log("Sidebar not visible on load", ok=False)

            # Check all tabs present
            body = page.locator("body").inner_text()
            for tab in ["Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"]:
                if tab in body:
                    log(f"Tab '{tab}' present")
                else:
                    log(f"Tab '{tab}' missing", ok=False)

            # Check empty KPI placeholders
            dash_count = body.count("\u2014")
            log(f"Empty state shows {dash_count} dash placeholders", ok=dash_count >= 2)

            # Check Add Position button
            try:
                page.locator("button:has-text('Add Position')").first.wait_for(state="visible", timeout=5000)
                log("Add Position button visible")
            except Exception:
                log("Add Position button NOT visible", ok=False)

            # ── Test form validation (empty submit) ──
            try:
                page.locator("button:has-text('Add Position')").first.click()
                page.wait_for_timeout(1500)
                notif = page.locator(".q-notification").first
                notif_text = notif.inner_text(timeout=3000)
                log(f"Empty form validation: '{notif_text[:60]}'", ok="select" in notif_text.lower() or "please" in notif_text.lower())
            except Exception as e:
                log(f"Empty form validation check failed: {e}", ok=False)

            # ── Test About dialog ──
            try:
                info_btn = page.locator("button[aria-label]").filter(has=page.locator("i:has-text('info')")).first
                if info_btn.count() == 0:
                    info_btn = page.locator("button").filter(has=page.locator(".q-icon:has-text('info')")).first
                if info_btn.count() == 0:
                    # Try finding by icon content
                    info_btn = page.locator("button i.q-icon").filter(has_text="info").first.locator("..")
                info_btn.click()
                page.wait_for_timeout(1000)
                dialog = page.locator(".q-dialog")
                if dialog.count() > 0:
                    dialog_text = dialog.first.inner_text()
                    has_about = "Market Dashboard" in dialog_text and ("data" in dialog_text.lower() or "version" in dialog_text.lower())
                    log("About dialog opens with content", ok=has_about)
                    screenshot(page, "01b_about_dialog")
                    # Close it
                    page.locator("button:has-text('Close')").first.click()
                    page.wait_for_timeout(500)
                else:
                    log("About dialog did not open", ok=False)
            except Exception as e:
                log(f"About dialog test failed: {e}", ok=False)

            # ── Test Export button (empty portfolio) ──
            try:
                page.locator("button:has-text('Export')").first.click()
                page.wait_for_timeout(1000)
                # Should show warning notification
                log("Export button clickable (empty portfolio)")
            except Exception as e:
                log(f"Export button test failed: {e}", ok=False)

            # ── Test Clear All (empty portfolio) ──
            try:
                page.locator("button:has-text('Clear All')").first.click()
                page.wait_for_timeout(1000)
                log("Clear All button clickable (empty portfolio)")
            except Exception as e:
                log(f"Clear All test failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 2: Load Sample Portfolio
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 2: Load Sample Portfolio ===")

            t0 = time.time()
            page.locator("button:has-text('Load Sample')").first.click()
            page.wait_for_timeout(1500)
            # Confirm in dialog
            all_load_btns = page.locator("button:has-text('Load Sample')")
            if all_load_btns.count() >= 2:
                all_load_btns.last.click()
            else:
                log("Load Sample confirmation dialog did not appear", ok=False)

            # Wait for page navigation/reload
            page.wait_for_load_state("domcontentloaded", timeout=30000)
            page.wait_for_timeout(30000)  # Let data load (9 tickers)
            load_sample_ms = (time.time() - t0) * 1000
            log(f"Load Sample portfolio + Overview render", timing_ms=load_sample_ms,
                ok=load_sample_ms < 120000)

            screenshot(page, "02_overview_loaded")

            # Check sidebar positions populated
            sidebar_text = page.locator(".q-drawer").first.inner_text(timeout=10000)
            tickers_found = [t for t in ["AAPL", "JNJ", "XOM", "KO", "ASML", "HSBA", "SPY", "GLD", "O"]
                            if t in sidebar_text]
            log(f"Sidebar positions: {len(tickers_found)}/9 tickers", ok=len(tickers_found) >= 5)

            # Check KPIs show dollar values
            body = page.locator("body").inner_text()
            has_dollar = "$" in body
            log("KPI cards show dollar values", ok=has_dollar)

            # Check for scroll position — page should be at top
            scroll_y = page.evaluate("window.scrollY")
            log(f"Page scroll position after load: {scroll_y}px", ok=scroll_y < 50)

            # ═══════════════════════════════════════════════════
            # PHASE 3: Overview tab interactions
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 3: Overview Tab Interactions ===")

            # Test comparison chart time range toggles
            for range_label in ["3M", "1Y", "Since"]:
                try:
                    t0 = time.time()
                    page.locator(f"text={range_label}").first.click()
                    page.wait_for_timeout(3000)
                    toggle_ms = (time.time() - t0) * 1000
                    log(f"Comparison toggle '{range_label}'", timing_ms=toggle_ms,
                        ok=toggle_ms < 10000)
                    scroll_after = page.evaluate("window.scrollY")
                    if scroll_after > 200:
                        log(f"PAGE JUMP after comparison toggle '{range_label}': scrollY={scroll_after}", ok=False)
                except Exception as e:
                    log(f"Comparison toggle '{range_label}' failed: {e}", ok=False)

            # Reset to 6M
            try:
                page.locator("text=6M").first.click()
                page.wait_for_timeout(1000)
            except Exception:
                pass

            # Test FX-adjusted switch
            try:
                fx_switch = page.locator("text=FX-adjusted").first
                t0 = time.time()
                fx_switch.click()
                page.wait_for_timeout(3000)
                fx_ms = (time.time() - t0) * 1000
                log(f"FX-adjusted toggle", timing_ms=fx_ms, ok=fx_ms < 10000)
                scroll_after = page.evaluate("window.scrollY")
                if scroll_after > 200:
                    log(f"PAGE JUMP after FX toggle: scrollY={scroll_after}", ok=False)
                # Toggle back
                fx_switch.click()
                page.wait_for_timeout(1000)
            except Exception as e:
                log(f"FX-adjusted toggle failed: {e}", ok=False)

            # Test "Other tabs" preview cards
            try:
                preview_cards = page.locator(".preview-card")
                card_count = preview_cards.count()
                log(f"Other tabs preview: {card_count} cards", ok=card_count == 5)
            except Exception as e:
                log(f"Preview cards check failed: {e}", ok=False)

            screenshot(page, "03_overview_after_interactions")

            # ═══════════════════════════════════════════════════
            # PHASE 4: Tab switching timing
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 4: Tab Switching ===")

            tab_timings = {}
            for tab_name in ["Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"]:
                try:
                    t0 = time.time()
                    page.locator(f"text={tab_name}").first.click()
                    # Wait for spinner to appear and disappear, or content to load
                    page.wait_for_timeout(2000)
                    # Wait for spinners to disappear
                    try:
                        page.wait_for_selector(".q-spinner", state="hidden", timeout=90000)
                    except Exception:
                        pass
                    # Extra wait for charts to render
                    page.wait_for_timeout(3000)
                    tab_ms = (time.time() - t0) * 1000
                    tab_timings[tab_name] = tab_ms

                    # Check scroll position
                    scroll_y = page.evaluate("window.scrollY")
                    if scroll_y > 100:
                        log(f"PAGE JUMP on tab switch to '{tab_name}': scrollY={scroll_y}", ok=False)

                    # Check for error text
                    body = page.locator("body").inner_text()
                    if "500" in body and "internal server error" in body.lower():
                        log(f"Tab '{tab_name}' shows server error", ok=False)
                    else:
                        is_slow = tab_ms > 30000
                        log(f"Tab '{tab_name}' loaded", timing_ms=tab_ms,
                            ok=not is_slow)
                        if is_slow:
                            log(f"  SLOW: '{tab_name}' took {tab_ms/1000:.1f}s — unacceptable for a trading dashboard", ok=False)

                    screenshot(page, f"04_{tab_name.replace(' & ', '_').replace(' ', '_').lower()}")
                except Exception as e:
                    log(f"Tab '{tab_name}' switch failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 5: Positions tab deep-dive
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 5: Positions Tab ===")

            try:
                page.locator("text=Positions").first.click()
                page.wait_for_timeout(3000)

                # Check positions table is rendered
                table = page.locator(".table-wrap table")
                if table.count() > 0:
                    log("Positions table rendered")
                    # Count rows
                    rows = table.first.locator("tbody tr")
                    row_count = rows.count()
                    log(f"Positions table has {row_count} rows", ok=row_count >= 9)
                else:
                    log("Positions table NOT rendered", ok=False)

                # Test "Show individual purchases" switch if present
                switch = page.locator("text=Show individual purchases")
                if switch.count() > 0:
                    t0 = time.time()
                    switch.first.click()
                    page.wait_for_timeout(1500)
                    switch_ms = (time.time() - t0) * 1000
                    log(f"'Show individual purchases' toggle", timing_ms=switch_ms)
                    scroll_y = page.evaluate("window.scrollY")
                    if scroll_y > 200:
                        log(f"PAGE JUMP after individual purchases toggle: scrollY={scroll_y}", ok=False)
                    # Toggle back
                    switch.first.click()
                    page.wait_for_timeout(500)

                # Test table row click → price chart update
                try:
                    first_data_row = page.locator(".table-wrap tbody tr[onclick]").first
                    if first_data_row.count() > 0:
                        t0 = time.time()
                        first_data_row.click()
                        page.wait_for_timeout(2000)
                        click_ms = (time.time() - t0) * 1000
                        log(f"Table row click → price chart", timing_ms=click_ms)
                        scroll_y = page.evaluate("window.scrollY")
                        if scroll_y > 600:
                            log(f"PAGE JUMP after row click: scrollY={scroll_y}", ok=False)
                except Exception as e:
                    log(f"Table row click failed: {e}", ok=False)

                # Test price history time range toggles
                for label in ["3M", "1Y", "2Y"]:
                    try:
                        toggles = page.locator(f"text={label}")
                        if toggles.count() > 0:
                            t0 = time.time()
                            toggles.last.click()
                            page.wait_for_timeout(2000)
                            t_ms = (time.time() - t0) * 1000
                            log(f"Price history toggle '{label}'", timing_ms=t_ms)
                    except Exception as e:
                        log(f"Price history toggle '{label}' failed: {e}", ok=False)

                # Test Currency-adjusted switch
                try:
                    ca_switch = page.locator("text=Currency-adjusted")
                    if ca_switch.count() > 0:
                        t0 = time.time()
                        ca_switch.first.click()
                        page.wait_for_timeout(3000)
                        ca_ms = (time.time() - t0) * 1000
                        log(f"Currency-adjusted toggle", timing_ms=ca_ms)
                        # Toggle back
                        ca_switch.first.click()
                        page.wait_for_timeout(1000)
                except Exception as e:
                    log(f"Currency-adjusted toggle failed: {e}", ok=False)

                screenshot(page, "05_positions_after_interactions")

            except Exception as e:
                log(f"Positions tab tests failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 6: Risk & Analytics tab deep-dive
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 6: Risk & Analytics Tab ===")

            try:
                page.locator("text=Risk & Analytics").first.click()
                page.wait_for_timeout(5000)

                # Check risk table
                tables = page.locator(".table-wrap table")
                table_count = tables.count()
                log(f"Risk tab tables: {table_count}", ok=table_count >= 3)

                # Check correlation heatmap
                body = page.locator("body").inner_text()
                has_corr = "Correlation" in body
                log("Correlation Matrix section present", ok=has_corr)

                # Check fundamentals
                has_fund = "Valuation" in body or "P/E" in body
                log("Fundamentals section present", ok=has_fund)

                # Check performance attribution
                has_perf = "Attribution" in body
                log("Performance Attribution present", ok=has_perf)

                screenshot(page, "06_risk_analytics")

            except Exception as e:
                log(f"Risk & Analytics tab tests failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 7: Forecast tab deep-dive
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 7: Forecast Tab ===")

            try:
                page.locator("text=Forecast").first.click()
                page.wait_for_timeout(5000)
                try:
                    page.wait_for_selector(".q-spinner", state="hidden", timeout=90000)
                except Exception:
                    pass
                page.wait_for_timeout(3000)

                body = page.locator("body").inner_text()

                # Check portfolio outlook
                has_outlook = "Portfolio Outlook" in body
                log("Portfolio Outlook section present", ok=has_outlook)

                # Check VaR/CVaR metrics
                has_var = "VaR" in body
                log("VaR metrics present", ok=has_var)

                # Test horizon toggles
                for label in ["3 months", "6 months"]:
                    try:
                        t0 = time.time()
                        page.locator(f"text={label}").first.click()
                        page.wait_for_timeout(2000)
                        h_ms = (time.time() - t0) * 1000
                        log(f"Forecast horizon toggle '{label}'", timing_ms=h_ms)
                        scroll_y = page.evaluate("window.scrollY")
                        if scroll_y > 200:
                            log(f"PAGE JUMP after forecast horizon toggle: scrollY={scroll_y}", ok=False)
                    except Exception as e:
                        log(f"Forecast horizon toggle '{label}' failed: {e}", ok=False)

                # Reset to 1 year
                try:
                    page.locator("text=1 year").first.click()
                    page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Check position outlook section
                has_pos_outlook = "Position Outlook" in body
                log("Position Outlook section present", ok=has_pos_outlook)

                # Test position selector dropdown
                try:
                    pos_select = page.locator(".q-select").filter(has_text="Position")
                    if pos_select.count() > 0:
                        pos_select.first.click()
                        page.wait_for_timeout(1000)
                        items = page.locator(".q-menu .q-item")
                        if items.count() > 1:
                            t0 = time.time()
                            items.nth(1).click()
                            page.wait_for_timeout(3000)
                            pos_ms = (time.time() - t0) * 1000
                            log(f"Position selector change", timing_ms=pos_ms)
                            scroll_y = page.evaluate("window.scrollY")
                            if scroll_y > 200:
                                log(f"PAGE JUMP after position selector change: scrollY={scroll_y}", ok=False)
                except Exception as e:
                    log(f"Position selector test failed: {e}", ok=False)

                # Test lookback toggles
                for label in ["1 year", "5 years"]:
                    try:
                        lookback_btns = page.locator(f"text={label}")
                        # Find the one in the position outlook section (not portfolio)
                        if lookback_btns.count() > 0:
                            t0 = time.time()
                            lookback_btns.last.click()
                            page.wait_for_timeout(3000)
                            lb_ms = (time.time() - t0) * 1000
                            log(f"Lookback toggle '{label}'", timing_ms=lb_ms)
                    except Exception as e:
                        log(f"Lookback toggle '{label}' failed: {e}", ok=False)

                screenshot(page, "07_forecast_after_interactions")

            except Exception as e:
                log(f"Forecast tab tests failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 8: Diagnostics tab deep-dive
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 8: Diagnostics Tab ===")

            try:
                page.locator("text=Diagnostics").first.click()
                page.wait_for_timeout(5000)
                try:
                    page.wait_for_selector(".q-spinner", state="hidden", timeout=90000)
                except Exception:
                    pass
                page.wait_for_timeout(3000)

                body = page.locator("body").inner_text()

                # Check backtest section
                has_backtest = "Backtest" in body
                log("Monte Carlo Backtest present", ok=has_backtest)

                # Check hit rate metrics
                has_hit = "Hit Rate" in body
                log("Hit Rate metrics present", ok=has_hit)

                # Check reliability table
                has_reliability = "Reliability" in body
                log("Model Reliability table present", ok=has_reliability)

                # Check model diagnostics
                has_diag = "Statistical Tests" in body or "Jarque-Bera" in body or "QQ Plot" in body
                log("Model Diagnostics section present", ok=has_diag)

                # Test QQ ticker selector
                try:
                    qq_select = page.locator(".q-select").filter(has_text="QQ")
                    if qq_select.count() == 0:
                        qq_select = page.locator(".q-select").filter(has_text="ticker")
                    if qq_select.count() > 0:
                        qq_select.first.click()
                        page.wait_for_timeout(1000)
                        items = page.locator(".q-menu .q-item")
                        if items.count() > 1:
                            t0 = time.time()
                            items.nth(1).click()
                            page.wait_for_timeout(2000)
                            qq_ms = (time.time() - t0) * 1000
                            log(f"QQ plot ticker change", timing_ms=qq_ms)
                except Exception as e:
                    log(f"QQ ticker selector test failed: {e}", ok=False)

                screenshot(page, "08_diagnostics")

            except Exception as e:
                log(f"Diagnostics tab tests failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 9: Guide tab
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 9: Guide Tab ===")

            try:
                t0 = time.time()
                page.locator("text=Guide").first.click()
                page.wait_for_timeout(2000)
                guide_ms = (time.time() - t0) * 1000
                log(f"Guide tab render", timing_ms=guide_ms)

                body = page.locator("body").inner_text()
                has_getting_started = "Getting Started" in body
                log("Guide: Getting Started section", ok=has_getting_started)

                screenshot(page, "09_guide")

            except Exception as e:
                log(f"Guide tab tests failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 10: Currency change
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 10: Currency Change ===")

            # Go back to Overview first
            try:
                page.locator("text=Overview").first.click()
                page.wait_for_timeout(3000)
            except Exception:
                pass

            try:
                # Find currency selector in header
                curr_select = page.locator("header .q-select").first
                t0 = time.time()
                curr_select.click()
                page.wait_for_timeout(500)
                # Pick EUR
                eur_item = page.locator(".q-menu .q-item:has-text('EUR')")
                if eur_item.count() > 0:
                    eur_item.first.click()
                    page.wait_for_timeout(10000)  # Wait for full refresh
                    curr_ms = (time.time() - t0) * 1000
                    log(f"Currency change to EUR", timing_ms=curr_ms,
                        ok=curr_ms < 30000)

                    body = page.locator("body").inner_text()
                    has_euro = "\u20ac" in body
                    log("EUR symbol displayed after currency change", ok=has_euro)

                    scroll_y = page.evaluate("window.scrollY")
                    if scroll_y > 100:
                        log(f"PAGE JUMP after currency change: scrollY={scroll_y}", ok=False)

                    screenshot(page, "10_currency_eur")

                    # Change back to USD
                    curr_select.click()
                    page.wait_for_timeout(500)
                    usd_item = page.locator(".q-menu .q-item:has-text('USD')")
                    if usd_item.count() > 0:
                        usd_item.first.click()
                        page.wait_for_timeout(10000)
                else:
                    log("EUR option not found in currency dropdown", ok=False)
            except Exception as e:
                log(f"Currency change test failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 11: Add Position flow
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 11: Add Position ===")

            try:
                # Ensure we're on Overview
                page.locator("text=Overview").first.click()
                page.wait_for_timeout(2000)

                # Fill out the form
                # Market is already US - S&P 500
                # Select ticker
                ticker_input = page.locator(".q-drawer .q-select").nth(1)
                ticker_input.click()
                page.wait_for_timeout(500)
                # Type to search
                ticker_input.locator("input").fill("MSFT")
                page.wait_for_timeout(1500)
                msft_item = page.locator(".q-menu .q-item:has-text('MSFT')")
                if msft_item.count() > 0:
                    msft_item.first.click()
                    page.wait_for_timeout(500)

                    # Enter shares
                    shares_field = page.locator("input[type='number']").first
                    shares_field.fill("5")

                    # Enter date
                    date_field = page.locator("input[placeholder='2024-01-15']")
                    if date_field.count() > 0:
                        date_field.first.fill("2024-06-15")

                    # Click Add Position
                    t0 = time.time()
                    page.locator("button:has-text('Add Position')").first.click()
                    # Wait for price fetch + save + refresh
                    page.wait_for_timeout(15000)
                    add_ms = (time.time() - t0) * 1000
                    log(f"Add Position (MSFT)", timing_ms=add_ms)

                    # Check notification
                    body = page.locator("body").inner_text()
                    added = "MSFT" in page.locator(".q-drawer").first.inner_text()
                    log("MSFT appears in sidebar after add", ok=added)

                    scroll_y = page.evaluate("window.scrollY")
                    if scroll_y > 100:
                        log(f"PAGE JUMP after add position: scrollY={scroll_y}", ok=False)

                    screenshot(page, "11_after_add_position")
                else:
                    log("MSFT ticker option not found", ok=False)
            except Exception as e:
                log(f"Add position test failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 12: Remove Position flow
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 12: Remove Position ===")

            try:
                # Find a remove button (X) in sidebar
                remove_btns = page.locator('.q-drawer button[aria-label^="Remove"]')
                if remove_btns.count() > 0:
                    t0 = time.time()
                    remove_btns.first.click()
                    page.wait_for_timeout(1500)

                    # Confirm remove dialog
                    dialog = page.locator(".q-dialog")
                    if dialog.count() > 0:
                        remove_confirm = dialog.locator("button:has-text('Remove')").first
                        remove_confirm.click()
                        page.wait_for_timeout(3000)
                        remove_ms = (time.time() - t0) * 1000
                        log(f"Remove Position", timing_ms=remove_ms)

                        # Check undo toast
                        undo_btn = page.locator("button:has-text('Undo')")
                        log("Undo toast appears after remove", ok=undo_btn.count() > 0)

                        scroll_y = page.evaluate("window.scrollY")
                        if scroll_y > 100:
                            log(f"PAGE JUMP after remove: scrollY={scroll_y}", ok=False)

                        screenshot(page, "12_after_remove")
                    else:
                        log("Remove confirmation dialog did not appear", ok=False)
                else:
                    log("No remove buttons found in sidebar", ok=False)
            except Exception as e:
                log(f"Remove position test failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 13: Export Portfolio (JSON)
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 13: Export Portfolio ===")

            try:
                export_btn = page.locator("button:has-text('Export Portfolio')")
                if export_btn.count() > 0:
                    t0 = time.time()
                    with page.expect_download(timeout=10000) as download_info:
                        export_btn.first.click()
                    download = download_info.value
                    export_ms = (time.time() - t0) * 1000
                    log(f"Export Portfolio JSON download", timing_ms=export_ms,
                        ok=download.suggested_filename == "portfolio.json")
            except Exception as e:
                log(f"Export portfolio test failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 14: Excel Export
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 14: Excel Export ===")

            try:
                excel_btn = page.locator("header button:has-text('Export')")
                if excel_btn.count() > 0:
                    t0 = time.time()
                    with page.expect_download(timeout=120000) as download_info:
                        excel_btn.first.click()
                    download = download_info.value
                    excel_ms = (time.time() - t0) * 1000
                    log(f"Excel Export download", timing_ms=excel_ms,
                        ok=download.suggested_filename.endswith(".xlsx"))
                    if excel_ms > 30000:
                        log(f"  SLOW: Excel export took {excel_ms/1000:.1f}s", ok=False)
            except Exception as e:
                log(f"Excel export test failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 15: Rapid tab switching (stress test)
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 15: Rapid Tab Switching ===")

            try:
                for tab in ["Positions", "Overview", "Risk & Analytics", "Forecast", "Overview"]:
                    page.locator(f"text={tab}").first.click()
                    page.wait_for_timeout(500)
                page.wait_for_timeout(3000)
                body = page.locator("body").inner_text()
                has_error = "error" in body.lower() and "500" in body
                log("Rapid tab switching — no crash", ok=not has_error)
                screenshot(page, "15_after_rapid_tabs")
            except Exception as e:
                log(f"Rapid tab switching failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 16: Mobile viewport test
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 16: Mobile Viewport ===")

            try:
                page.set_viewport_size({"width": 375, "height": 812})
                page.wait_for_timeout(2000)
                screenshot(page, "16_mobile_view")

                # Check if sidebar is hidden on mobile
                drawer = page.locator(".q-drawer")
                drawer_visible = drawer.first.is_visible()
                log(f"Sidebar hidden on mobile (375px): {not drawer_visible}", ok=not drawer_visible)

                # Check content isn't overflowing
                body_width = page.evaluate("document.body.scrollWidth")
                viewport_width = page.evaluate("window.innerWidth")
                overflow = body_width > viewport_width + 20
                log(f"No horizontal overflow on mobile (body={body_width}, viewport={viewport_width})",
                    ok=not overflow)

                # Reset viewport
                page.set_viewport_size({"width": 1440, "height": 900})
                page.wait_for_timeout(1000)
            except Exception as e:
                log(f"Mobile viewport test failed: {e}", ok=False)

            # ═══════════════════════════════════════════════════
            # PHASE 17: Console Errors Check
            # ═══════════════════════════════════════════════════
            print("\n=== PHASE 17: Console Errors ===")

            if console_errors:
                # Filter out noise
                real_errors = [e for e in console_errors if "favicon" not in e.lower() and "service-worker" not in e.lower()]
                if real_errors:
                    log(f"Console errors detected: {len(real_errors)}", ok=False)
                    for err in real_errors[:5]:
                        print(f"  [ERROR] {err[:120]}")
                else:
                    log("No significant console errors")
            else:
                log("No console errors")

            # Final screenshot
            screenshot(page, "99_final_state")
            browser.close()

    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass

    # ═══════════════════════════════════════════════════
    # SUMMARY
    # ═══════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("UX AUDIT TEST SUMMARY")
    print("=" * 70)
    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    print(f"  {passes} passed, {fails} failed, {len(results)} total")
    print()

    # Timing summary
    print("TIMING REPORT (sorted by slowest):")
    timed = [(r["msg"], r["timing_ms"]) for r in results if r["timing_ms"] is not None]
    timed.sort(key=lambda x: x[1], reverse=True)
    for msg, ms in timed:
        marker = " <<< SLOW" if ms > 15000 else ""
        print(f"  {ms:8.0f}ms  {msg}{marker}")
    print()

    # Failures
    if fails > 0:
        print("FAILURES:")
        for r in results:
            if r["status"] == "FAIL":
                print(f"  [FAIL] {r['msg']}")
    print()

    # Page jump report
    jumps = [r for r in results if "PAGE JUMP" in r["msg"]]
    if jumps:
        print("PAGE JUMP ISSUES:")
        for r in jumps:
            print(f"  {r['msg']}")
    print()

    return fails


if __name__ == "__main__":
    fail_count = run_tests()
    sys.exit(1 if fail_count > 0 else 0)
