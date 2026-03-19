"""Integration test: verify Phase 1+2 fixes with Playwright."""
import subprocess
import sys
import time
import signal
import socket
import os

from playwright.sync_api import sync_playwright

PORT = 8081
URL = f"http://localhost:{PORT}"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

results = []


def log(msg, ok=True):
    status = "PASS" if ok else "FAIL"
    results.append((status, msg))
    print(f"[{status}] {msg}")


def run_tests():
    proc = subprocess.Popen(
        [sys.executable, os.path.join(APP_DIR, "_test_launcher.py")],
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid,
    )

    try:
        # Wait for server port to open
        print("Waiting for server to start...")
        for i in range(30):
            time.sleep(1)
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode()
                print(f"App crashed:\n{stderr[-2000:]}")
                log("App failed to start", ok=False)
                return
            try:
                s = socket.create_connection(("localhost", PORT), timeout=1)
                s.close()
                print(f"Server port open after {i+1}s")
                break
            except OSError:
                pass
        else:
            log("Server did not start in 30s", ok=False)
            return

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_default_timeout(30000)

            # ── TEST 1: Page loads ─────────────────────────────
            try:
                page.goto(URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(8000)  # let NiceGUI render via WebSocket
                log("Page loads without crash")
            except Exception as e:
                log(f"Page load failed: {e}", ok=False)
                browser.close()
                return

            # ── TEST 2: Manifest served ────────────────────────
            try:
                resp = page.request.get(f"http://127.0.0.1:{PORT}/static/manifest.json")
                log("manifest.json served (200)" if resp.status == 200
                    else f"manifest.json returned {resp.status}", ok=(resp.status == 200))
            except Exception as e:
                log(f"manifest.json check failed: {e}", ok=False)

            # ── TEST 3: Sidebar visible ────────────────────────
            try:
                page.locator(".q-drawer").first.wait_for(state="visible", timeout=5000)
                log("Sidebar visible")
            except Exception:
                log("Sidebar not found", ok=False)

            # ── TEST 4: Add Position button visible (BUG 3) ───
            try:
                page.locator("button:has-text('Add Position')").first.wait_for(
                    state="visible", timeout=5000)
                log("Add Position button visible (BUG 3 fix verified)")
            except Exception:
                log("Add Position button NOT visible", ok=False)

            # ── TEST 5: Tabs present ──────────────────────────
            try:
                body_text = page.locator("body").inner_text(timeout=5000)
                tabs_found = all(t in body_text for t in
                                 ["Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics"])
                log("All 5 tabs present" if tabs_found else "Some tabs missing",
                    ok=tabs_found)
            except Exception as e:
                log(f"Tab check failed: {e}", ok=False)

            # ── TEST 6: Empty state shows dashes ───────────────
            try:
                body_text = page.locator("body").inner_text(timeout=5000)
                # Before loading sample, KPIs should show dashes
                if body_text.count("\u2014") >= 3:  # em dashes in KPI placeholders
                    log("Empty portfolio shows dash placeholders")
                else:
                    log("Empty portfolio KPIs unclear", ok=False)
            except Exception as e:
                log(f"Empty state check failed: {e}", ok=False)

            # ── TEST 7: Load Sample Portfolio ──────────────────
            try:
                page.locator("button:has-text('Load Sample')").first.click()
                page.wait_for_timeout(2000)
                # Confirm in dialog -- the confirm button is the LAST "Load Sample" button
                # (first one is the sidebar button that opened the dialog)
                all_load_btns = page.locator("button:has-text('Load Sample')")
                print(f"Found {all_load_btns.count()} 'Load Sample' buttons")
                all_load_btns.last.click()
                # Page will navigate/reload -- wait for it
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                # Wait for page to reload and render (fetching 9 tickers takes time)
                page.wait_for_timeout(60000)
                # Take screenshot after reload
                page.screenshot(path=os.path.join(APP_DIR, "_test_after_load.png"))
                body_text = page.locator("body").inner_text(timeout=5000)
                print(f"After Load Sample body preview: {body_text[:500]}")
                if "500" in body_text and "error" in body_text.lower():
                    log(f"Page 500 after Load Sample: {body_text[:200]}", ok=False)
                else:
                    log("Load Sample portfolio completed")
            except Exception as e:
                log(f"Load Sample failed: {e}", ok=False)

            # ── TEST 8: Positions in sidebar ──────────────────
            try:
                sidebar_text = page.locator(".q-drawer").first.inner_text(timeout=10000)
                found = [t for t in ["AAPL", "JNJ", "XOM", "KO", "ASML", "HSBA", "SPY", "GLD", "O"]
                         if t in sidebar_text]
                if len(found) >= 5:
                    log(f"Positions in sidebar: {', '.join(found)} (BUG 1 storage verified)")
                else:
                    log(f"Only {len(found)} tickers found: {found}", ok=False)
            except Exception as e:
                log(f"Position check failed: {e}", ok=False)

            # ── TEST 9: KPIs show dollar values ───────────────
            try:
                body_text = page.locator("body").inner_text(timeout=5000)
                has_dollar = "$" in body_text
                log("KPI cards show dollar values" if has_dollar
                    else "No dollar signs in KPIs", ok=has_dollar)
            except Exception as e:
                log(f"KPI check failed: {e}", ok=False)

            # ── TEST 10: Click through tabs ───────────────────
            for tab_name in ["Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Overview"]:
                try:
                    page.locator(f"text={tab_name}").first.click()
                    page.wait_for_timeout(3000)
                    log(f"Tab '{tab_name}' clickable")
                except Exception as e:
                    log(f"Tab '{tab_name}' click failed: {e}", ok=False)

            # ── TEST 11: Ticker dropdown labels (BUG 2) ───────
            try:
                # The second .q-select in the drawer is the ticker select
                ticker_select = page.locator(".q-drawer .q-select").nth(1)
                ticker_select.click()
                page.wait_for_timeout(2000)
                items = page.locator(".q-menu .q-item")
                count = items.count()
                if count > 0:
                    first_label = items.first.inner_text()
                    if "(" in first_label and len(first_label) > 5:
                        log(f"Ticker dropdown shows labels: '{first_label[:60]}' (BUG 2 verified)")
                    else:
                        log(f"Ticker dropdown labels may be wrong: '{first_label[:60]}'", ok=False)
                else:
                    log("Ticker dropdown has no items", ok=False)
                page.keyboard.press("Escape")
            except Exception as e:
                log(f"Ticker select check: {e}", ok=False)

            # Take final screenshot
            page.screenshot(path=os.path.join(APP_DIR, "_test_screenshot.png"))
            print("Final screenshot saved")

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

    # Summary
    print("\n" + "=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    passes = sum(1 for s, _ in results if s == "PASS")
    fails = sum(1 for s, _ in results if s == "FAIL")
    print(f"  {passes} passed, {fails} failed, {len(results)} total")
    for status, msg in results:
        print(f"  [{status}] {msg}")

    if fails > 0:
        sys.exit(1)


if __name__ == "__main__":
    run_tests()
