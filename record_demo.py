"""
Record a demo GIF of the market dashboard.

Flow:
  1. Sidebar: add Apple (AAPL) — USD stock
  2. Sidebar: add Nestlé (NESN.SW) — CHF stock
  3. Overview tab: KPI cards + allocation + comparison charts
  4. Positions tab: price history chart
  5. Risk & Analytics tab: risk metrics
  6. Sidebar: switch Display Currency to CHF

Output: demo.gif (≈5 seconds, sped-up from raw recording)

Usage:
  python3 record_demo.py
"""

import subprocess
import sys
import time
import os
import asyncio

# ── dependencies ──────────────────────────────────────────────────────────────
def ensure(pkg, import_name=None):
    try:
        __import__(import_name or pkg.split("[")[0])
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

ensure("imageio[ffmpeg]", "imageio")
ensure("pillow", "PIL")
ensure("numpy", "numpy")

import imageio
from PIL import Image
import numpy as np

# ── kill stale process on port, then start Streamlit ─────────────────────────
PORT = 8502
APP_URL = f"http://localhost:{PORT}"

subprocess.run(
    f"lsof -ti tcp:{PORT} | xargs kill -9",
    shell=True, stderr=subprocess.DEVNULL
)
time.sleep(1)

print(f"Starting Streamlit on port {PORT}...")
proc = subprocess.Popen(
    [sys.executable, "-m", "streamlit", "run", "app.py",
     "--server.port", str(PORT),
     "--server.headless", "true",
     "--server.runOnSave", "false",
     "--logger.level", "error"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    cwd=os.path.dirname(os.path.abspath(__file__)),
)

import urllib.request, urllib.error
for _ in range(30):
    try:
        urllib.request.urlopen(APP_URL, timeout=2)
        break
    except Exception:
        time.sleep(1)
else:
    proc.terminate()
    raise RuntimeError("Streamlit did not start in time")

print("Streamlit ready.")

# ── Playwright recording ───────────────────────────────────────────────────────
async def run():
    from playwright.async_api import async_playwright

    VIDEO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_raw")
    os.makedirs(VIDEO_DIR, exist_ok=True)

    # Selectbox positions (stable across page states):
    # nth(0) = Display Currency, nth(1) = Stock Market, nth(2) = Stock
    # Analytics selectboxes append at higher indices.
    SEL_CURRENCY     = 0
    SEL_STOCK_MARKET = 1
    SEL_STOCK        = 2

    async def pick_selectbox(page, nth_index, value_text, search_text=None):
        """Click a selectbox by its nth position, optionally type to filter, pick option."""
        combobox = page.locator("[data-testid='stSelectbox']").nth(nth_index).locator(
            "input[role='combobox']"
        ).first
        await combobox.click(force=True)
        await page.wait_for_timeout(500)
        if search_text:
            await page.keyboard.type(search_text, delay=60)
            await page.wait_for_timeout(700)
        option = page.locator("li[role='option']").filter(has_text=value_text).first
        await option.wait_for(state="visible", timeout=15000)
        await option.click()
        await page.wait_for_timeout(400)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            record_video_dir=VIDEO_DIR,
            record_video_size={"width": 1400, "height": 900},
            color_scheme="dark",
        )
        page = await ctx.new_page()

        # ── navigate & reset state ────────────────────────────────────────────
        await page.goto(APP_URL, wait_until="networkidle")
        await page.wait_for_timeout(1500)
        await page.evaluate("localStorage.clear()")
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # ── ADD STOCK 1: Apple (USD) ──────────────────────────────────────────
        await pick_selectbox(page, SEL_STOCK, "Apple Inc. (AAPL)", search_text="Apple")

        shares = page.locator("[data-testid='stNumberInput'] input").first
        await shares.click()
        await shares.fill("10")
        await page.wait_for_timeout(200)

        date_inp = page.locator("[data-testid='stDateInput'] input").first
        await date_inp.click()
        await date_inp.fill("2024/01/15")
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(300)

        await page.get_by_role("button", name="Add to Portfolio").click()
        print("Adding Apple... waiting for full render")
        await page.wait_for_timeout(18000)

        # ── ADD STOCK 2: Nestlé (CHF) ─────────────────────────────────────────
        await pick_selectbox(page, SEL_STOCK_MARKET, "Switzerland — SMI")
        await page.wait_for_timeout(12000)   # wait for full rerender with AAPL data

        await pick_selectbox(page, SEL_STOCK, "Nestlé SA (NESN.SW)", search_text="Nestle")

        shares2 = page.locator("[data-testid='stNumberInput'] input").first
        await shares2.click()
        await shares2.fill("5")
        await page.wait_for_timeout(200)

        date_inp2 = page.locator("[data-testid='stDateInput'] input").first
        await date_inp2.click()
        await date_inp2.fill("2024/03/01")
        await page.keyboard.press("Tab")
        await page.wait_for_timeout(300)

        await page.get_by_role("button", name="Add to Portfolio").click()
        print("Adding Nestlé... waiting for full render")
        await page.wait_for_timeout(18000)

        # ── NAVIGATE TABS to show charts ──────────────────────────────────────
        # Overview tab: KPI cards — pause, then scroll to show allocation + comparison charts
        await page.get_by_role("tab", name="Overview").click()
        await page.wait_for_timeout(2000)
        await page.evaluate("window.scrollTo({top: 420, behavior: 'smooth'})")
        await page.wait_for_timeout(2500)   # hold on the charts

        # Positions tab: wait for price history chart to render, then show it
        await page.get_by_role("tab", name="Positions").click()
        await page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        await page.wait_for_timeout(3000)   # let the chart render
        await page.evaluate("window.scrollTo({top: 600, behavior: 'smooth'})")
        await page.wait_for_timeout(2000)   # hold on the chart

        # Risk & Analytics tab
        await page.get_by_role("tab", name="Risk & Analytics").click()
        await page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        await page.wait_for_timeout(2500)

        # ── TOGGLE CURRENCY in sidebar ────────────────────────────────────────
        await page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
        await page.wait_for_timeout(400)
        await pick_selectbox(page, SEL_CURRENCY, "CHF")
        print("Switched currency to CHF, waiting for refresh")
        await page.wait_for_timeout(4000)

        # Back to Overview — scroll to show CHF numbers + allocation chart
        await page.get_by_role("tab", name="Overview").click()
        await page.wait_for_timeout(1500)
        await page.evaluate("window.scrollTo({top: 420, behavior: 'smooth'})")
        await page.wait_for_timeout(2000)

        # ── done ─────────────────────────────────────────────────────────────
        video = page.video
        await ctx.close()
        await browser.close()
        raw_path = await video.path()
        print(f"Raw video saved: {raw_path}")
        return raw_path


raw_video = asyncio.run(run())
proc.terminate()

# ── Convert webm → GIF (5 second target) ─────────────────────────────────────
print("Converting to GIF...")

OUTPUT_GIF = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.gif")
TARGET_DURATION = 5.0
TARGET_FPS = 15
SCALE = 0.55   # 1400 * 0.55 ≈ 770px wide

try:
    reader = imageio.get_reader(raw_video, "ffmpeg")
    meta = reader.get_meta_data()
    source_fps = meta.get("fps", 25)
    source_duration = meta.get("duration", None)
    frames_raw = []
    for frame in reader:
        frames_raw.append(frame.copy())
    reader.close()
    total_frames = len(frames_raw)
    dur = source_duration if source_duration else total_frames / source_fps
    print(f"Source: {total_frames} frames @ {source_fps:.1f}fps = {dur:.1f}s")

    # Non-uniform sampling: loading waits get few frames, chart sections get many.
    # Timeline (approx): 0-25s form fill, 25-60s waits, 60s+ charts/tabs/currency
    t_form_end  = min(int(total_frames * 25  / dur), total_frames - 1)
    t_wait_end  = min(int(total_frames * 60  / dur), total_frames - 1)
    t_total_end = total_frames - 1

    segments = [
        (0,           t_form_end,  8),   # form interactions — 8 frames
        (t_form_end,  t_wait_end,  4),   # loading waits     — 4 frames
        (t_wait_end,  t_total_end, 48),  # charts + currency — 48 frames
    ]
    indices = []
    for start, end, n in segments:
        if end > start and n > 0:
            indices.extend(np.linspace(start, end - 1, n, dtype=int).tolist())

    frame_ms = int(1000 / TARGET_FPS)
    print(f"Output: {len(indices)} frames @ {TARGET_FPS}fps = {len(indices)/TARGET_FPS:.1f}s")

    frames_out = []
    for idx in indices:
        img = Image.fromarray(frames_raw[idx])
        new_w = int(img.width * SCALE)
        new_h = int(img.height * SCALE)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        img = img.convert("P", palette=Image.ADAPTIVE, colors=256)
        frames_out.append(img)

    frames_out[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=frames_out[1:],
        duration=frame_ms,
        loop=0,
        optimize=True,
    )
    size_mb = os.path.getsize(OUTPUT_GIF) / 1_000_000
    print(f"Saved: {OUTPUT_GIF}  ({size_mb:.1f} MB)")

except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"Raw webm available at: {raw_video}")
