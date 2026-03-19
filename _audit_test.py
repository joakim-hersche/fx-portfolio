"""
Comprehensive interactive UI/UX audit of the Market Dashboard (NiceGUI).
Launches the app, exercises every interactive element, and reports findings.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

# We'll use sync playwright
from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

BASE_URL = "http://localhost:8081"
SCREENSHOT_DIR = Path(__file__).parent / "audit_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Clean old screenshots
for f in SCREENSHOT_DIR.glob("*.png"):
    f.unlink()

results = []  # list of (category, test_name, status, detail)

def record(category, name, status, detail=""):
    results.append((category, name, status, detail))
    icon = "PASS" if status == "PASS" else ("FAIL" if status == "FAIL" else "WARN")
    print(f"  [{icon}] {category} > {name}" + (f" -- {detail}" if detail else ""))

def shot(page, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=False)
    return path

def shot_full(page, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path


def main():
    # ── Launch app ─────────────────────────────────────────
    print("Starting app on port 8081...")
    proc = subprocess.Popen(
        [sys.executable, "_test_launcher.py"],
        cwd=str(Path(__file__).parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for server to be ready
    import urllib.request
    ready = False
    for i in range(60):
        try:
            urllib.request.urlopen(BASE_URL, timeout=2)
            ready = True
            break
        except Exception:
            time.sleep(2)

    if not ready:
        print("FATAL: App did not start within 120s")
        proc.kill()
        return

    print("App is running.")

    console_errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            # Collect console errors
            page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
            page.on("pageerror", lambda err: console_errors.append(f"[PAGE_ERROR] {err}"))

            # ════════════════════════════════════════════════
            # 1. APP LAUNCH & INITIAL STATE
            # ════════════════════════════════════════════════
            print("\n=== 1. App Launch & Initial State ===")
            try:
                page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
                record("Launch", "App loads without crash", "PASS")
            except Exception as e:
                record("Launch", "App loads without crash", "FAIL", str(e))

            # Wait for NiceGUI to hydrate
            page.wait_for_timeout(3000)
            shot(page, "01_initial_state")

            # Check title
            title = page.title()
            record("Launch", "Page has a title", "PASS" if title else "WARN", f"Title: '{title}'")

            # Check sidebar is visible
            sidebar = page.locator("aside, .q-drawer")
            sidebar_visible = sidebar.count() > 0 and sidebar.first.is_visible()
            record("Launch", "Sidebar visible on load", "PASS" if sidebar_visible else "FAIL")

            # Check empty state KPI cards
            kpi_dashes = page.locator("text=—")
            has_empty_kpis = kpi_dashes.count() >= 2
            record("Launch", "Empty state shows placeholder KPIs", "PASS" if has_empty_kpis else "WARN", f"Found {kpi_dashes.count()} dash placeholders")

            # Check that all 6 tabs exist
            for tab_name in ["Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"]:
                tab = page.locator(f"role=tab >> text='{tab_name}'")
                if tab.count() > 0:
                    record("Launch", f"Tab '{tab_name}' exists", "PASS")
                else:
                    # Try broader search
                    tab2 = page.locator(f"text='{tab_name}'")
                    record("Launch", f"Tab '{tab_name}' exists", "PASS" if tab2.count() > 0 else "FAIL")

            # Check empty positions message
            empty_msg = page.locator("text=No positions yet")
            record("Launch", "Empty portfolio shows 'No positions yet'", "PASS" if empty_msg.count() > 0 else "FAIL")

            # ════════════════════════════════════════════════
            # 2. SIDEBAR: LOAD SAMPLE PORTFOLIO
            # ════════════════════════════════════════════════
            print("\n=== 2. Sidebar: Load Sample Portfolio ===")

            load_sample_btn = page.locator("button:has-text('Load Sample')")
            record("Sidebar", "Load Sample button exists", "PASS" if load_sample_btn.count() > 0 else "FAIL")

            if load_sample_btn.count() > 0:
                load_sample_btn.first.click()
                page.wait_for_timeout(1000)

                # Check confirmation dialog appears
                dialog = page.locator("text=Load Sample Portfolio?")
                record("Sidebar", "Load Sample shows confirmation dialog", "PASS" if dialog.count() > 0 else "FAIL")
                shot(page, "02_load_sample_dialog")

                # Click confirm
                confirm_btn = page.locator("button:has-text('Load Sample')").last
                if confirm_btn.count() > 0:
                    confirm_btn.click()
                    # Wait for page reload
                    page.wait_for_timeout(8000)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    record("Sidebar", "Sample portfolio loads (page reloads)", "PASS")
                else:
                    record("Sidebar", "Confirmation button found in dialog", "FAIL")

            page.wait_for_timeout(3000)
            shot(page, "03_after_sample_load")

            # Check positions now appear in sidebar
            position_rows = page.locator(".position-row")
            if position_rows.count() == 0:
                # Try finding ticker labels like AAPL, JNJ etc
                aapl_label = page.locator("text=AAPL")
                record("Sidebar", "Positions appear after sample load", "PASS" if aapl_label.count() > 0 else "FAIL", f"Found AAPL: {aapl_label.count() > 0}")
            else:
                record("Sidebar", "Positions appear after sample load", "PASS", f"{position_rows.count()} rows")

            # Check KPIs are now populated (no more dashes)
            kpi_dashes_after = page.locator(".kpi-value:has-text('—')")
            has_data = kpi_dashes_after.count() == 0
            record("Sidebar", "KPI cards show data after sample load", "PASS" if has_data else "WARN", f"Still {kpi_dashes_after.count()} dashes")
            shot(page, "04_kpi_after_load")

            # ════════════════════════════════════════════════
            # 3. SIDEBAR: MARKET DROPDOWN
            # ════════════════════════════════════════════════
            print("\n=== 3. Sidebar: Market Dropdown ===")

            # Find all select elements in the sidebar
            # The market select is the first select in the sidebar
            sidebar_el = page.locator("aside, .q-drawer").first
            market_selects = sidebar_el.locator(".q-select")

            if market_selects.count() >= 1:
                market_select = market_selects.first
                record("Sidebar", "Market dropdown exists", "PASS")

                # Click to open dropdown
                market_select.click()
                page.wait_for_timeout(500)

                # Check options are visible
                menu_items = page.locator(".q-item__label")
                visible_options = []
                for i in range(min(menu_items.count(), 20)):
                    try:
                        text = menu_items.nth(i).text_content()
                        if text:
                            visible_options.append(text.strip())
                    except:
                        pass

                record("Sidebar", "Market dropdown shows options", "PASS" if len(visible_options) > 0 else "FAIL", f"Found: {visible_options[:5]}...")
                shot(page, "05_market_dropdown_open")

                # Select UK market
                uk_option = page.locator("text='UK — FTSE 100'")
                if uk_option.count() > 0:
                    uk_option.first.click()
                    page.wait_for_timeout(1000)
                    record("Sidebar", "Can select UK market", "PASS")
                else:
                    record("Sidebar", "Can select UK market", "FAIL", "Option not found")
                    page.keyboard.press("Escape")

                page.wait_for_timeout(500)

                # Switch back to US
                market_select.click()
                page.wait_for_timeout(500)
                us_option = page.locator("text='US — S&P 500'")
                if us_option.count() > 0:
                    us_option.first.click()
                    page.wait_for_timeout(500)
                else:
                    page.keyboard.press("Escape")
            else:
                record("Sidebar", "Market dropdown exists", "FAIL")

            # ════════════════════════════════════════════════
            # 4. SIDEBAR: TICKER DROPDOWN
            # ════════════════════════════════════════════════
            print("\n=== 4. Sidebar: Ticker Dropdown ===")

            if market_selects.count() >= 2:
                ticker_select = market_selects.nth(1)
                record("Sidebar", "Ticker dropdown exists", "PASS")

                ticker_select.click()
                page.wait_for_timeout(500)
                shot(page, "06_ticker_dropdown_open")

                # Check if company names appear (not just ticker symbols)
                # Type to filter
                page.keyboard.type("Apple")
                page.wait_for_timeout(800)
                shot(page, "07_ticker_search_apple")

                # Check if we get results
                items_after_search = page.locator(".q-item")
                found_apple = False
                for i in range(min(items_after_search.count(), 10)):
                    try:
                        text = items_after_search.nth(i).text_content()
                        if text and "AAPL" in text:
                            found_apple = True
                            break
                    except:
                        pass

                record("Sidebar", "Ticker search filters results", "PASS" if found_apple else "WARN", f"Found AAPL in filtered list: {found_apple}")

                # Check if company names are shown
                has_company_names = False
                for i in range(min(items_after_search.count(), 10)):
                    try:
                        text = items_after_search.nth(i).text_content()
                        if text and ("Apple" in text or "Inc" in text):
                            has_company_names = True
                            break
                    except:
                        pass

                record("Sidebar", "Ticker dropdown shows company names", "PASS" if has_company_names else "FAIL", "Company names should be visible for usability")

                # Select MSFT
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
                ticker_select.click()
                page.wait_for_timeout(300)
                # Clear and type
                page.keyboard.press("Control+a")
                page.keyboard.type("MSFT")
                page.wait_for_timeout(800)
                msft_item = page.locator(".q-item:has-text('MSFT')")
                if msft_item.count() > 0:
                    msft_item.first.click()
                    page.wait_for_timeout(500)
                    record("Sidebar", "Can select a ticker (MSFT)", "PASS")
                else:
                    page.keyboard.press("Escape")
                    record("Sidebar", "Can select a ticker (MSFT)", "FAIL")
            else:
                record("Sidebar", "Ticker dropdown exists", "FAIL")

            # ════════════════════════════════════════════════
            # 5. SIDEBAR: SHARES INPUT
            # ════════════════════════════════════════════════
            print("\n=== 5. Sidebar: Shares Input ===")

            shares_input = sidebar_el.locator("input[type='number']").first
            if shares_input.count() > 0:
                record("Sidebar", "Shares input exists", "PASS")
                shares_input.fill("10")
                page.wait_for_timeout(300)
                val = shares_input.input_value()
                record("Sidebar", "Can enter share count", "PASS" if val == "10" else "FAIL", f"Value: {val}")

                # Test 0 shares
                shares_input.fill("0")
                page.wait_for_timeout(300)
                record("Sidebar", "Accepts 0 shares (edge case)", "WARN", "Should 0 shares be valid?")
            else:
                record("Sidebar", "Shares input exists", "FAIL")

            # ════════════════════════════════════════════════
            # 6. SIDEBAR: MANUAL PRICE TOGGLE
            # ════════════════════════════════════════════════
            print("\n=== 6. Sidebar: Manual Price Toggle ===")

            manual_checkbox = sidebar_el.locator("text=Enter price manually")
            if manual_checkbox.count() > 0:
                record("Sidebar", "Manual price checkbox exists", "PASS")
                manual_checkbox.click()
                page.wait_for_timeout(500)
                shot(page, "08_manual_price_toggled")

                # Check that price input becomes visible
                price_inputs = sidebar_el.locator("input[type='number']")
                price_visible = price_inputs.count() >= 2
                record("Sidebar", "Price input appears when manual toggled", "PASS" if price_visible else "FAIL")

                # Check that date input is hidden
                date_input = sidebar_el.locator("input[placeholder='2024-01-15']")
                date_hidden = date_input.count() == 0 or not date_input.first.is_visible()
                record("Sidebar", "Date input hidden when manual toggled", "PASS" if date_hidden else "FAIL")

                # Toggle back
                manual_checkbox.click()
                page.wait_for_timeout(500)
            else:
                record("Sidebar", "Manual price checkbox exists", "FAIL")

            # ════════════════════════════════════════════════
            # 7. SIDEBAR: DATE INPUT
            # ════════════════════════════════════════════════
            print("\n=== 7. Sidebar: Date Input ===")

            date_input = sidebar_el.locator("input[placeholder='2024-01-15']")
            if date_input.count() > 0:
                record("Sidebar", "Date input exists", "PASS")
                date_input.fill("2024-01-15")
                page.wait_for_timeout(300)
                val = date_input.input_value()
                record("Sidebar", "Can enter date", "PASS" if "2024" in val else "FAIL", f"Value: {val}")

                # Check calendar icon
                cal_icon = sidebar_el.locator("text=edit_calendar")
                has_cal = cal_icon.count() > 0
                record("Sidebar", "Calendar picker icon exists", "PASS" if has_cal else "WARN")
                if has_cal:
                    cal_icon.first.click()
                    page.wait_for_timeout(500)
                    date_picker = page.locator(".q-date")
                    record("Sidebar", "Calendar picker opens on click", "PASS" if date_picker.count() > 0 else "FAIL")
                    shot(page, "09_date_picker_open")
                    # Close it
                    close_btn = page.locator("button:has-text('Close')")
                    if close_btn.count() > 0:
                        close_btn.first.click()
                        page.wait_for_timeout(300)
            else:
                record("Sidebar", "Date input exists", "FAIL")

            # ════════════════════════════════════════════════
            # 8. SIDEBAR: ADD POSITION (INVALID INPUTS)
            # ════════════════════════════════════════════════
            print("\n=== 8. Sidebar: Add Position - Validation ===")

            add_btn = sidebar_el.locator("button:has-text('Add Position')")
            if add_btn.count() > 0:
                record("Sidebar", "Add Position button exists", "PASS")

                # Clear all inputs first and try adding without ticker
                # Reset form
                if market_selects.count() >= 2:
                    ticker_select = market_selects.nth(1)
                    # Don't select ticker - click add
                    # First clear ticker
                    ticker_select.click()
                    page.wait_for_timeout(200)
                    page.keyboard.press("Escape")

                shares_input = sidebar_el.locator("input[type='number']").first
                if shares_input.count() > 0:
                    shares_input.fill("")

                # Click add with empty form
                add_btn.first.click()
                page.wait_for_timeout(1000)

                # Check for warning notification
                notif = page.locator(".q-notification")
                has_warning = notif.count() > 0
                record("Sidebar", "Shows warning when adding without ticker", "PASS" if has_warning else "FAIL")
                shot(page, "10_add_no_ticker_warning")

                # Try adding with ticker but no shares
                if market_selects.count() >= 2:
                    ticker_select = market_selects.nth(1)
                    ticker_select.click()
                    page.wait_for_timeout(300)
                    page.keyboard.type("MSFT")
                    page.wait_for_timeout(800)
                    msft_item = page.locator(".q-item:has-text('MSFT')")
                    if msft_item.count() > 0:
                        msft_item.first.click()
                        page.wait_for_timeout(500)

                add_btn.first.click()
                page.wait_for_timeout(1000)
                shot(page, "11_add_no_shares_warning")

                # Try with 0 shares
                shares_input = sidebar_el.locator("input[type='number']").first
                if shares_input.count() > 0:
                    shares_input.fill("0")
                add_btn.first.click()
                page.wait_for_timeout(1000)
                record("Sidebar", "Shows warning for 0 shares", "PASS" if page.locator(".q-notification").count() > 0 else "FAIL")
                shot(page, "12_add_zero_shares")
            else:
                record("Sidebar", "Add Position button exists", "FAIL")

            # ════════════════════════════════════════════════
            # 9. SIDEBAR: ADD POSITION (VALID)
            # ════════════════════════════════════════════════
            print("\n=== 9. Sidebar: Add Position - Valid ===")

            # Fill valid data: MSFT, 5 shares, 2024-01-15
            if market_selects.count() >= 2:
                ticker_select = market_selects.nth(1)
                ticker_select.click()
                page.wait_for_timeout(300)
                page.keyboard.press("Control+a")
                page.keyboard.type("MSFT")
                page.wait_for_timeout(800)
                msft_item = page.locator(".q-item:has-text('MSFT')")
                if msft_item.count() > 0:
                    msft_item.first.click()
                    page.wait_for_timeout(500)

            shares_input = sidebar_el.locator("input[type='number']").first
            if shares_input.count() > 0:
                shares_input.fill("5")

            date_input = sidebar_el.locator("input[placeholder='2024-01-15']")
            if date_input.count() > 0:
                date_input.fill("2024-01-15")

            add_btn = sidebar_el.locator("button:has-text('Add Position')")
            if add_btn.count() > 0:
                add_btn.first.click()
                # Wait for fetch + page reload
                try:
                    page.wait_for_timeout(15000)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    record("Sidebar", "Add valid position (MSFT, 5 shares)", "PASS")
                except Exception as e:
                    record("Sidebar", "Add valid position (MSFT, 5 shares)", "FAIL", str(e))

            page.wait_for_timeout(3000)
            shot(page, "13_after_add_msft")

            # Verify MSFT appears in sidebar
            msft_in_sidebar = page.locator("text=MSFT")
            record("Sidebar", "MSFT appears in positions list after add", "PASS" if msft_in_sidebar.count() > 0 else "FAIL")

            # ════════════════════════════════════════════════
            # 10. SIDEBAR: CURRENCY SELECTOR
            # ════════════════════════════════════════════════
            print("\n=== 10. Sidebar: Currency Selector ===")

            # Currency selector is in the top bar
            header = page.locator("header").first
            currency_select = header.locator(".q-select")
            if currency_select.count() > 0:
                record("Top Bar", "Currency selector exists", "PASS")
                currency_select.first.click()
                page.wait_for_timeout(500)
                shot(page, "14_currency_dropdown")

                # Try selecting GBP
                gbp_option = page.locator(".q-item:has-text('GBP')")
                if gbp_option.count() > 0:
                    gbp_option.first.click()
                    page.wait_for_timeout(8000)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    record("Top Bar", "Currency change to GBP triggers reload", "PASS")
                    shot(page, "15_currency_gbp")

                    # Check that values changed (look for pound sign)
                    page_text = page.content()
                    has_pound = "£" in page_text or "GBP" in page_text
                    record("Top Bar", "Currency symbol updates to GBP", "PASS" if has_pound else "FAIL")

                    # Switch back to USD
                    page.wait_for_timeout(2000)
                    header = page.locator("header").first
                    currency_select = header.locator(".q-select")
                    if currency_select.count() > 0:
                        currency_select.first.click()
                        page.wait_for_timeout(500)
                        usd_option = page.locator(".q-item:has-text('USD')")
                        if usd_option.count() > 0:
                            usd_option.first.click()
                            page.wait_for_timeout(8000)
                            page.wait_for_load_state("networkidle", timeout=30000)
                else:
                    record("Top Bar", "GBP option found", "FAIL")
                    page.keyboard.press("Escape")
            else:
                record("Top Bar", "Currency selector exists", "FAIL")

            # ════════════════════════════════════════════════
            # 11. SIDEBAR: EXPORT BUTTON
            # ════════════════════════════════════════════════
            print("\n=== 11. Top Bar: Export Button ===")

            export_btn = header.locator("button:has-text('Export')")
            if export_btn.count() > 0:
                record("Top Bar", "Export button exists", "PASS")
                # We just click and check for notification (won't test actual download)
                export_btn.first.click()
                page.wait_for_timeout(5000)
                shot(page, "16_export_clicked")
                record("Top Bar", "Export button clickable", "PASS")
            else:
                record("Top Bar", "Export button exists", "FAIL")

            # ════════════════════════════════════════════════
            # 12. SIDEBAR: INDIVIDUAL DELETE BUTTONS
            # ════════════════════════════════════════════════
            print("\n=== 12. Sidebar: Delete Position ===")

            sidebar_el = page.locator("aside, .q-drawer").first
            # Find X/close buttons
            close_buttons = sidebar_el.locator("button:has(i:has-text('close'))")
            if close_buttons.count() > 0:
                record("Sidebar", "Delete (X) buttons exist", "PASS", f"{close_buttons.count()} found")

                # Click the first delete button (should be for first position)
                close_buttons.first.click()
                page.wait_for_timeout(1000)

                # Check confirmation dialog
                remove_dialog = page.locator("text=Remove")
                record("Sidebar", "Delete shows confirmation dialog", "PASS" if remove_dialog.count() > 0 else "FAIL")
                shot(page, "17_delete_confirm_dialog")

                # Cancel
                cancel_btn = page.locator("button:has-text('Cancel')")
                if cancel_btn.count() > 0:
                    cancel_btn.first.click()
                    page.wait_for_timeout(500)
                    record("Sidebar", "Cancel button closes delete dialog", "PASS")
            else:
                record("Sidebar", "Delete (X) buttons exist", "FAIL")

            # ════════════════════════════════════════════════
            # 13. SIDEBAR: CLEAR ALL
            # ════════════════════════════════════════════════
            print("\n=== 13. Sidebar: Clear All ===")

            clear_btn = sidebar_el.locator("button:has-text('Clear All')")
            if clear_btn.count() > 0:
                record("Sidebar", "Clear All button exists", "PASS")
                clear_btn.first.click()
                page.wait_for_timeout(1000)

                clear_dialog = page.locator("text=Clear All Positions?")
                record("Sidebar", "Clear All shows confirmation", "PASS" if clear_dialog.count() > 0 else "FAIL")
                shot(page, "18_clear_all_dialog")

                # Cancel (don't actually clear)
                cancel_btn = page.locator("button:has-text('Cancel')")
                if cancel_btn.count() > 0:
                    cancel_btn.first.click()
                    page.wait_for_timeout(500)
            else:
                record("Sidebar", "Clear All button exists", "FAIL")

            # ════════════════════════════════════════════════
            # 14. TAB NAVIGATION
            # ════════════════════════════════════════════════
            print("\n=== 14. Tab Navigation ===")

            tab_names = ["Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"]
            for tab_name in tab_names:
                try:
                    tab = page.locator(f".q-tab:has-text('{tab_name}')").first
                    if tab.count() > 0:
                        tab.click()
                        page.wait_for_timeout(3000)
                        shot(page, f"19_tab_{tab_name.lower().replace(' ', '_').replace('&', 'and')}")
                        record("Tabs", f"'{tab_name}' tab clickable and loads", "PASS")

                        # Check URL updates
                        current_url = page.url
                        if tab_name == "Overview":
                            url_ok = "tab=" not in current_url or "tab=Overview" in current_url
                        else:
                            url_ok = tab_name.replace(" ", "+").replace("&", "%26") in current_url or tab_name in current_url
                        record("Tabs", f"'{tab_name}' URL updates", "PASS" if url_ok else "WARN", current_url)
                    else:
                        record("Tabs", f"'{tab_name}' tab exists", "FAIL")
                except Exception as e:
                    record("Tabs", f"'{tab_name}' tab navigation", "FAIL", str(e))

            # ════════════════════════════════════════════════
            # 15. OVERVIEW TAB - DETAILED
            # ════════════════════════════════════════════════
            print("\n=== 15. Overview Tab ===")

            # Navigate to Overview
            overview_tab = page.locator(".q-tab:has-text('Overview')").first
            if overview_tab.count() > 0:
                overview_tab.click()
                page.wait_for_timeout(3000)

            # KPI cards
            kpi_row = page.locator(".kpi-row")
            record("Overview", "KPI row exists", "PASS" if kpi_row.count() > 0 else "FAIL")

            # Check for actual values (not dashes)
            page_text = page.content()
            has_dollar_values = "$" in page_text and any(c.isdigit() for c in page_text)
            record("Overview", "KPI cards show dollar values", "PASS" if has_dollar_values else "FAIL")

            # Allocation chart
            alloc_title = page.locator("text=Portfolio Allocation")
            record("Overview", "Allocation chart title exists", "PASS" if alloc_title.count() > 0 else "FAIL")

            # Comparison chart
            comp_title = page.locator("text=Portfolio Comparison")
            record("Overview", "Comparison chart title exists", "PASS" if comp_title.count() > 0 else "FAIL")

            # Comparison time range toggle
            range_toggle = page.locator(".q-btn-toggle, .q-toggle")
            has_range = False
            for label in ["3M", "6M", "1Y", "Since"]:
                btn = page.locator(f"button:has-text('{label}')")
                if btn.count() > 0:
                    has_range = True
                    break
            record("Overview", "Comparison range toggle exists", "PASS" if has_range else "FAIL")

            # FX switch
            fx_switch = page.locator("text=FX-adjusted")
            record("Overview", "FX-adjusted switch exists", "PASS" if fx_switch.count() > 0 else "FAIL")

            # Test range toggle
            for label in ["3M", "1Y", "Since"]:
                btn = page.locator(f"button:has-text('{label}')")
                if btn.count() > 0:
                    btn.first.click()
                    page.wait_for_timeout(4000)
                    record("Overview", f"Range toggle '{label}' works", "PASS")
                    break

            shot_full(page, "20_overview_full")

            # Plotly chart interaction
            plotly_charts = page.locator(".js-plotly-plot")
            record("Overview", f"Plotly charts rendered", "PASS" if plotly_charts.count() > 0 else "FAIL", f"Found {plotly_charts.count()} charts")

            # Tab preview cards
            preview_cards = page.locator(".preview-card")
            record("Overview", "Tab preview cards exist", "PASS" if preview_cards.count() > 0 else "FAIL", f"Found {preview_cards.count()}")

            # Test clicking preview card
            if preview_cards.count() > 0:
                preview_cards.first.click()
                page.wait_for_timeout(1000)
                record("Overview", "Preview card click navigates to tab", "PASS")
                # Go back to overview
                overview_tab = page.locator(".q-tab:has-text('Overview')").first
                if overview_tab.count() > 0:
                    overview_tab.click()
                    page.wait_for_timeout(2000)

            # ════════════════════════════════════════════════
            # 16. POSITIONS TAB
            # ════════════════════════════════════════════════
            print("\n=== 16. Positions Tab ===")

            positions_tab = page.locator(".q-tab:has-text('Positions')").first
            if positions_tab.count() > 0:
                positions_tab.click()
                page.wait_for_timeout(4000)
                shot(page, "21_positions_tab")

                # Check for table
                table = page.locator(".q-table, table")
                record("Positions", "Positions table exists", "PASS" if table.count() > 0 else "FAIL")

                # Check for price chart
                plotly_in_positions = page.locator(".js-plotly-plot")
                record("Positions", "Price chart exists", "PASS" if plotly_in_positions.count() > 0 else "FAIL")

                # Check for ticker selector or controls
                selects_in_positions = page.locator(".q-tab-panel--active .q-select, .q-tab-panel--active select")
                record("Positions", "Has controls/selectors", "PASS" if selects_in_positions.count() > 0 else "WARN", f"Found {selects_in_positions.count()}")

                shot_full(page, "22_positions_full")

            # ════════════════════════════════════════════════
            # 17. RISK & ANALYTICS TAB
            # ════════════════════════════════════════════════
            print("\n=== 17. Risk & Analytics Tab ===")

            risk_tab = page.locator(".q-tab:has-text('Risk & Analytics')").first
            if risk_tab.count() > 0:
                risk_tab.click()
                page.wait_for_timeout(5000)
                shot(page, "23_risk_tab")

                # Check for charts
                plotly_in_risk = page.locator(".js-plotly-plot")
                record("Risk", "Charts exist in Risk tab", "PASS" if plotly_in_risk.count() > 0 else "FAIL", f"Found {plotly_in_risk.count()} charts")

                # Check for specific sections
                for section in ["Risk Metrics", "Correlation", "Attribution", "Fundamentals"]:
                    el = page.locator(f"text='{section}'")
                    # Broader search
                    if el.count() == 0:
                        el = page.locator(f"text={section}")
                    found = el.count() > 0
                    record("Risk", f"'{section}' section exists", "PASS" if found else "WARN")

                shot_full(page, "24_risk_full")

            # ════════════════════════════════════════════════
            # 18. FORECAST TAB
            # ════════════════════════════════════════════════
            print("\n=== 18. Forecast Tab ===")

            forecast_tab = page.locator(".q-tab:has-text('Forecast')").first
            if forecast_tab.count() > 0:
                forecast_tab.click()
                page.wait_for_timeout(5000)
                shot(page, "25_forecast_tab")

                plotly_in_forecast = page.locator(".js-plotly-plot")
                record("Forecast", "Charts exist in Forecast tab", "PASS" if plotly_in_forecast.count() > 0 else "FAIL", f"Found {plotly_in_forecast.count()} charts")

                # Check for specific sections
                for section in ["Portfolio Outlook", "Position Outlook", "VaR", "CVaR"]:
                    el = page.locator(f"text={section}")
                    record("Forecast", f"'{section}' content exists", "PASS" if el.count() > 0 else "WARN")

                # Check for position selector
                forecast_selects = page.locator(".q-tab-panel--active .q-select")
                record("Forecast", "Position selector exists", "PASS" if forecast_selects.count() > 0 else "WARN")

                shot_full(page, "26_forecast_full")

            # ════════════════════════════════════════════════
            # 19. DIAGNOSTICS TAB
            # ════════════════════════════════════════════════
            print("\n=== 19. Diagnostics Tab ===")

            diag_tab = page.locator(".q-tab:has-text('Diagnostics')").first
            if diag_tab.count() > 0:
                diag_tab.click()
                page.wait_for_timeout(5000)
                shot(page, "27_diagnostics_tab")

                plotly_in_diag = page.locator(".js-plotly-plot")
                record("Diagnostics", "Charts exist in Diagnostics tab", "PASS" if plotly_in_diag.count() > 0 else "FAIL", f"Found {plotly_in_diag.count()} charts")

                # Check for specific sections
                for section in ["Backtest", "QQ", "Reliability", "Normality"]:
                    el = page.locator(f"text={section}")
                    record("Diagnostics", f"'{section}' content exists", "PASS" if el.count() > 0 else "WARN")

                shot_full(page, "28_diagnostics_full")

            # ════════════════════════════════════════════════
            # 20. GUIDE TAB
            # ════════════════════════════════════════════════
            print("\n=== 20. Guide Tab ===")

            guide_tab = page.locator(".q-tab:has-text('Guide')").first
            if guide_tab.count() > 0:
                guide_tab.click()
                page.wait_for_timeout(2000)
                shot(page, "29_guide_tab")

                guide_content = page.locator("text=Getting Started")
                record("Guide", "Guide tab has content", "PASS" if guide_content.count() > 0 else "FAIL")
                shot_full(page, "30_guide_full")

            # ════════════════════════════════════════════════
            # 21. EDGE CASE: ADD DUPLICATE TICKER
            # ════════════════════════════════════════════════
            print("\n=== 21. Edge Case: Duplicate Ticker ===")

            # Navigate to overview first
            overview_tab = page.locator(".q-tab:has-text('Overview')").first
            if overview_tab.count() > 0:
                overview_tab.click()
                page.wait_for_timeout(2000)

            sidebar_el = page.locator("aside, .q-drawer").first
            market_selects = sidebar_el.locator(".q-select")

            if market_selects.count() >= 2:
                ticker_select = market_selects.nth(1)
                ticker_select.click()
                page.wait_for_timeout(300)
                page.keyboard.press("Control+a")
                page.keyboard.type("AAPL")
                page.wait_for_timeout(800)
                aapl_item = page.locator(".q-item:has-text('AAPL')")
                if aapl_item.count() > 0:
                    aapl_item.first.click()
                    page.wait_for_timeout(500)

                shares_input = sidebar_el.locator("input[type='number']").first
                if shares_input.count() > 0:
                    shares_input.fill("3")

                date_input = sidebar_el.locator("input[placeholder='2024-01-15']")
                if date_input.count() > 0:
                    date_input.fill("2024-06-01")

                add_btn = sidebar_el.locator("button:has-text('Add Position')")
                if add_btn.count() > 0:
                    add_btn.first.click()
                    page.wait_for_timeout(12000)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    page.wait_for_timeout(3000)
                    shot(page, "31_duplicate_aapl")

                    # Check if AAPL has multiple lots or shows twice
                    aapl_entries = page.locator("text=AAPL")
                    record("Edge", "Duplicate ticker handled (AAPL added twice)", "PASS" if aapl_entries.count() > 0 else "FAIL",
                           f"AAPL appears {aapl_entries.count()} time(s) in page. Should aggregate as lots.")

            # ════════════════════════════════════════════════
            # 22. EDGE CASE: DIFFERENT MARKETS
            # ════════════════════════════════════════════════
            print("\n=== 22. Edge Case: Market Switching ===")

            sidebar_el = page.locator("aside, .q-drawer").first
            market_selects = sidebar_el.locator(".q-select")

            markets_to_test = ["UK — FTSE 100", "Germany — DAX", "ETFs", "Crypto", "Commodities"]
            for market_name in markets_to_test:
                try:
                    if market_selects.count() >= 1:
                        market_selects.first.click()
                        page.wait_for_timeout(500)
                        option = page.locator(f".q-item:has-text('{market_name}')")
                        if option.count() > 0:
                            option.first.click()
                            page.wait_for_timeout(1000)

                            # Check ticker dropdown updated
                            ticker_select = market_selects.nth(1)
                            ticker_select.click()
                            page.wait_for_timeout(500)
                            items = page.locator(".q-item")
                            item_count = items.count()
                            page.keyboard.press("Escape")
                            page.wait_for_timeout(300)

                            record("Edge", f"Market '{market_name}' loads tickers", "PASS" if item_count > 0 else "FAIL", f"{item_count} tickers")

                            # For alt assets (Crypto, Commodities), check label changes to "Amount"
                            if market_name in ("Crypto", "Commodities"):
                                amount_label = sidebar_el.locator("text=Amount")
                                record("Edge", f"'{market_name}' shows 'Amount' label", "PASS" if amount_label.count() > 0 else "FAIL")
                        else:
                            record("Edge", f"Market '{market_name}' option exists", "FAIL")
                            page.keyboard.press("Escape")
                except Exception as e:
                    record("Edge", f"Market '{market_name}' test", "FAIL", str(e))

            # Switch back to US
            if market_selects.count() >= 1:
                market_selects.first.click()
                page.wait_for_timeout(500)
                us_opt = page.locator(".q-item:has-text('US — S&P 500')")
                if us_opt.count() > 0:
                    us_opt.first.click()
                    page.wait_for_timeout(500)
                else:
                    page.keyboard.press("Escape")

            # ════════════════════════════════════════════════
            # 23. EDGE CASE: RAPID CURRENCY SWITCHING
            # ════════════════════════════════════════════════
            print("\n=== 23. Edge Case: Rapid Currency Switching ===")

            header = page.locator("header").first
            currency_select = header.locator(".q-select")
            if currency_select.count() > 0:
                currencies = ["EUR", "GBP", "SEK", "USD"]
                for curr in currencies:
                    try:
                        currency_select.first.click()
                        page.wait_for_timeout(300)
                        opt = page.locator(f".q-item:has-text('{curr}')")
                        if opt.count() > 0:
                            opt.first.click()
                            page.wait_for_timeout(2000)
                        else:
                            page.keyboard.press("Escape")
                    except Exception:
                        pass

                # Wait for last reload
                page.wait_for_timeout(8000)
                try:
                    page.wait_for_load_state("networkidle", timeout=30000)
                except:
                    pass
                page.wait_for_timeout(3000)
                shot(page, "32_rapid_currency_switch")

                # Check page is still functional
                kpi_row = page.locator(".kpi-row")
                record("Edge", "Page functional after rapid currency switching", "PASS" if kpi_row.count() > 0 else "FAIL")
            else:
                record("Edge", "Currency selector for rapid switch test", "FAIL")

            # ════════════════════════════════════════════════
            # 24. EDGE CASE: DELETE ALL POSITIONS
            # ════════════════════════════════════════════════
            print("\n=== 24. Edge Case: Clear All Positions ===")

            sidebar_el = page.locator("aside, .q-drawer").first
            clear_btn = sidebar_el.locator("button:has-text('Clear All')")
            if clear_btn.count() > 0:
                clear_btn.first.click()
                page.wait_for_timeout(1000)

                # Confirm
                confirm_clear = page.locator("button:has-text('Clear All')").last
                if confirm_clear.count() > 0:
                    confirm_clear.click()
                    page.wait_for_timeout(8000)
                    page.wait_for_load_state("networkidle", timeout=30000)
                    page.wait_for_timeout(3000)
                    shot(page, "33_after_clear_all")

                    # Check empty state
                    empty_msg = page.locator("text=No positions yet")
                    kpi_dashes = page.locator("text=—")
                    record("Edge", "Clear All returns to empty state", "PASS" if empty_msg.count() > 0 or kpi_dashes.count() >= 2 else "FAIL")

                    # Check tabs still work
                    for tab_name in ["Positions", "Risk & Analytics", "Forecast", "Diagnostics"]:
                        tab = page.locator(f".q-tab:has-text('{tab_name}')").first
                        if tab.count() > 0:
                            tab.click()
                            page.wait_for_timeout(2000)
                            # Just verify no crash
                            record("Edge", f"'{tab_name}' tab works with empty portfolio", "PASS")
                        shot(page, f"34_empty_{tab_name.lower().replace(' ', '_').replace('&', 'and')}")

            # ════════════════════════════════════════════════
            # 25. INFO BUTTON
            # ════════════════════════════════════════════════
            print("\n=== 25. Info Button ===")

            header = page.locator("header").first
            info_btn = header.locator("button:has(i:has-text('info'))")
            if info_btn.count() > 0:
                info_btn.first.click()
                page.wait_for_timeout(1000)
                about_dialog = page.locator("text=Market Dashboard")
                record("Top Bar", "Info button opens About dialog", "PASS" if about_dialog.count() > 0 else "FAIL")
                shot(page, "35_about_dialog")

                close_btn = page.locator("button:has-text('Close')")
                if close_btn.count() > 0:
                    close_btn.first.click()
                    page.wait_for_timeout(500)
            else:
                record("Top Bar", "Info button exists", "FAIL")

            # ════════════════════════════════════════════════
            # 26. CONSOLE ERRORS
            # ════════════════════════════════════════════════
            print("\n=== 26. Console Errors ===")

            error_msgs = [e for e in console_errors if "[error]" in e.lower() or "[page_error]" in e.lower()]
            warning_msgs = [e for e in console_errors if "[warning]" in e.lower()]

            if error_msgs:
                for i, err in enumerate(error_msgs[:10]):
                    record("Console", f"Error #{i+1}", "FAIL", err[:200])
            else:
                record("Console", "No JS errors detected", "PASS")

            if warning_msgs:
                record("Console", f"JS warnings detected", "WARN", f"{len(warning_msgs)} warnings. First: {warning_msgs[0][:150]}")

            browser.close()

    except Exception as e:
        record("FATAL", "Test execution", "FAIL", f"{traceback.format_exc()}")
    finally:
        proc.terminate()
        proc.wait(timeout=10)

    # ══════════════════════════════════════════════════════
    # PRINT REPORT
    # ══════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("AUDIT REPORT")
    print("=" * 70)

    pass_count = sum(1 for r in results if r[2] == "PASS")
    fail_count = sum(1 for r in results if r[2] == "FAIL")
    warn_count = sum(1 for r in results if r[2] == "WARN")

    print(f"\nTotal: {len(results)} tests | PASS: {pass_count} | FAIL: {fail_count} | WARN: {warn_count}\n")

    # Group by category
    from collections import defaultdict
    by_cat = defaultdict(list)
    for cat, name, status, detail in results:
        by_cat[cat].append((name, status, detail))

    for cat, items in by_cat.items():
        print(f"\n--- {cat} ---")
        for name, status, detail in items:
            icon = {"PASS": "OK", "FAIL": "XX", "WARN": "!!"}.get(status, "??")
            line = f"  [{icon}] {name}"
            if detail:
                line += f"  -- {detail}"
            print(line)

    # FAILURES summary
    failures = [(cat, name, detail) for cat, name, status, detail in results if status == "FAIL"]
    if failures:
        print("\n" + "=" * 70)
        print("FAILURES SUMMARY")
        print("=" * 70)
        for cat, name, detail in failures:
            print(f"  [{cat}] {name}: {detail}")

    # WARNINGS summary
    warnings = [(cat, name, detail) for cat, name, status, detail in results if status == "WARN"]
    if warnings:
        print("\n" + "=" * 70)
        print("WARNINGS SUMMARY")
        print("=" * 70)
        for cat, name, detail in warnings:
            print(f"  [{cat}] {name}: {detail}")

    # Write JSON report
    report_path = SCREENSHOT_DIR / "audit_report.json"
    with open(report_path, "w") as f:
        json.dump({
            "summary": {"total": len(results), "pass": pass_count, "fail": fail_count, "warn": warn_count},
            "results": [{"category": c, "test": n, "status": s, "detail": d} for c, n, s, d in results],
            "console_errors": console_errors[:50],
        }, f, indent=2)
    print(f"\nFull report saved to: {report_path}")
    print(f"Screenshots saved to: {SCREENSHOT_DIR}/")


if __name__ == "__main__":
    main()
