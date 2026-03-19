# Launch Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix async bugs, add error surfacing, decompose main.py into modules, clean up dead artifacts, and produce a monetization analysis — making the dashboard ready for free testing with banking coworkers.

**Architecture:** Surgical bug fixes first (Section 1), then performance polish (Section 2), then mechanical extraction of main.py into `src/ui/` modules (Section 3), dead file cleanup (Section 4), and a parallel market analysis (Section 5). Each section produces independently testable changes.

**Tech Stack:** NiceGUI 3.8.0, Python 3.12, asyncio, yfinance, Plotly 6.6, Quasar (via NiceGUI)

**Spec:** `docs/superpowers/specs/2026-03-19-launch-readiness-design.md`

**Important notes:**
- All line numbers reference the **original** main.py (1458 lines) before any changes. After each task removes code, line numbers shift. Implementers should locate code by **function name**, not line number.
- **Descoped from spec:** Section 2c (multi-user resilience — session isolation verification, yfinance rate limiting, global error boundary). NiceGUI already creates isolated page instances per connection. Rate limiting and error boundaries are follow-up work after tester feedback confirms they're needed.
- `diagnostics` stays inside `src/ui/forecast.py` (not a separate module) since `build_diagnostics_tab` and `build_forecast_tab` share simulation data loading logic.

---

## Pre-work

- [ ] **Step 1: Tag current state as rollback point**

```bash
git tag pre-launch-readiness
```

---

## Task 1: Fix Currency Change Async Bug

**Files:**
- Modify: `main.py:367-373` (currency select `on_change`)

**Context:** `_on_currency_change` (defined at line 547) is async. The lambda at line 370 creates a coroutine object but never awaits it. NiceGUI's `on_change` can handle async callables directly if they accept the event argument.

- [ ] **Step 1: Fix the currency select callback**

Replace the lambda with an async wrapper that NiceGUI will properly await:

```python
# main.py:367-373 — replace the ui.select block
async def _handle_currency_select(e):
    await _on_currency_change(e.value)

ui.select(
    list(CURRENCY_SYMBOLS.keys()),
    value=currency,
    on_change=_handle_currency_select,
).props('dense borderless').style(
    f"background:{BG_INPUT}; border:1px solid {BORDER_INPUT}; border-radius:6px; color:{TEXT_MUTED}; font-size:12px; min-width:70px; height:32px; max-height:32px;"
)
```

The `# noqa: async handled` comment is removed as part of this change.

- [ ] **Step 2: Manual test**

```bash
cd /Users/joakimhersche/Documents/Python\ Project/market-dashboard
python main.py
```

Open browser, load sample portfolio, change currency dropdown from USD to EUR. Verify:
- No page reload occurs
- KPI values update to EUR
- Console shows no "coroutine was never awaited" warning

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "fix: await async currency change callback"
```

---

## Task 2: Fix Blocking Company Name Fetch in Sidebar

**Files:**
- Modify: `main.py:430-451` (`_shared` dict initialization)
- Modify: `main.py:520-543` (`_on_portfolio_mutation`)
- Modify: `main.py:774-788` (`positions_list` refreshable)
- Reference: `src/data_fetch.py:101-107` (`fetch_company_name`)

**Context:** `fetch_company_name(ticker)` at line 788 calls `yf.Ticker(ticker).info` synchronously on the UI thread, once per position, every time the sidebar refreshes. With 8 positions that's 8 serial network calls blocking the UI.

- [ ] **Step 1: Pre-fetch names on initial load**

Add a batch fetch to the initial portfolio load block. Insert after `ticker_values` computation (after line 443):

```python
# Pre-fetch company names off the UI thread
def _fetch_all_names():
    from concurrent.futures import ThreadPoolExecutor
    tickers = list(portfolio.keys())
    if not tickers:
        return {}
    with ThreadPoolExecutor(max_workers=min(10, len(tickers))) as ex:
        return dict(zip(tickers, ex.map(fetch_company_name, tickers)))

name_map: dict[str, str] = {}
if portfolio:
    name_map = await run.io_bound(_fetch_all_names)
```

Add `name_map` to the `_shared` dict (line 446-451):

```python
_shared = {
    "portfolio_color_map": portfolio_color_map,
    "ticker_values": ticker_values,
    "name_map": name_map,
    "currency": currency,
    "currency_symbol": CURRENCY_SYMBOLS.get(currency, "$"),
}
```

- [ ] **Step 2: Update mutation callback to refresh names**

In `_on_portfolio_mutation` (line 521), add name refresh after ticker_values:

```python
async def _on_portfolio_mutation():
    nonlocal portfolio_color_map, ticker_values

    portfolio_color_map = _build_color_map(portfolio)
    if portfolio:
        ticker_values = await run.io_bound(_compute_ticker_values)
        new_names = await run.io_bound(_fetch_all_names)
    else:
        ticker_values = {}
        new_names = {}

    _shared["portfolio_color_map"] = portfolio_color_map
    _shared["ticker_values"] = ticker_values
    _shared["name_map"] = new_names

    for name in _TAB_NAMES:
        _tab_built[name] = False
    await _build_tab(_active_tab["name"])
```

- [ ] **Step 3: Replace blocking call in sidebar**

In `positions_list()` at line 788, replace:

```python
company_name = fetch_company_name(ticker)
```

with:

```python
company_name = _shared.get("name_map", {}).get(ticker, ticker)
```

- [ ] **Step 4: Manual test**

Run the app, load sample portfolio. Verify:
- Sidebar positions list renders without delay
- Company names appear correctly
- Adding a new position shows the correct company name after mutation

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "fix: pre-fetch company names off UI thread"
```

---

## Task 3: Chart Container Min-Heights

**Files:**
- Modify: `src/theme.py` (add CSS class for chart containers with min-height)

**Context:** When Plotly charts render asynchronously, the page jumps as containers expand from 0 to their final height. Adding min-height to chart containers reserves space.

- [ ] **Step 1: Add chart-placeholder class to GLOBAL_CSS**

In `src/theme.py`, add to the GLOBAL_CSS string (before the closing `</style>` or at the end of the CSS block):

```css
/* Reserve space for Plotly charts to prevent scroll jumps */
.chart-card .js-plotly-plot,
.chart-card .plotly {
    min-height: 380px;
}
```

This targets only Plotly charts inside `.chart-card` containers, not Guide tab or empty states.

- [ ] **Step 2: Manual test**

Load the app with sample portfolio. Switch between tabs. Verify:
- No visible scroll jump when charts render
- Guide tab has no unnecessary empty space

- [ ] **Step 3: Commit**

```bash
git add src/theme.py
git commit -m "fix: add min-height to chart containers to prevent scroll jumps"
```

---

## Task 4: Error Surfacing — Distinguish Network Failures

**Files:**
- Modify: `src/fx.py:32-51` (`get_fx_rate`)
- Modify: `src/data_fetch.py:101-107` (`fetch_company_name`)
- Modify: `src/data_fetch.py:26-44` (`fetch_price_history_short`, `fetch_price_history_long`)
- Modify: `main.py:700-706` (add position — price fetch error message)

**Context:** All yfinance errors return empty data silently. Users can't tell if their ticker is wrong or if yfinance is down. FX failures silently return 1.0, producing incorrect values.

- [ ] **Step 1: Make FX failures return a warning flag**

In `src/fx.py`, the `get_fx_rate` function already returns `(rate, is_live)`. Change the except block (line 43-48) to log more clearly:

```python
except Exception as exc:
    _log.warning("FX rate fetch failed for %s→%s: %s — using 1.0 fallback", from_currency, to_currency, exc)
    return 1.0, False
```

No structural change — just better logging. The `is_live=False` return already signals the fallback; callers that care can check it.

- [ ] **Step 2: Add timeout to yfinance Ticker calls via requests session**

The codebase uses `yf.Ticker(ticker).history()`, not `yf.download()`. The `.history()` method doesn't accept a `timeout` parameter directly. Instead, configure a `requests.Session` with a timeout adapter:

In `src/data_fetch.py`, add a module-level session near the top (after imports):

```python
import requests
from requests.adapters import HTTPAdapter

# Shared session with 15s timeout for all yfinance calls
_yf_session = requests.Session()
_yf_session.request = lambda *args, timeout=15, **kwargs: requests.Session.request(_yf_session.__class__.__new__(_yf_session.__class__), *args, timeout=timeout, **kwargs)
```

Actually, the cleaner approach — yfinance `Ticker` accepts a `session` parameter since v0.2.18. Create a session with a default timeout:

```python
import requests

class _TimeoutSession(requests.Session):
    """Session that enforces a default timeout on all requests."""
    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", 15)
        return super().request(*args, **kwargs)

_session = _TimeoutSession()
```

Then update each fetch function to pass `session=_session`:

```python
@cached(short_cache)
def fetch_price_history_short(ticker: str) -> pd.DataFrame:
    try:
        hist = yf.Ticker(ticker, session=_session).history(period="6mo")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()
```

Apply the same `session=_session` to all `yf.Ticker()` calls in:
- `fetch_price_history_long` (line 37)
- `fetch_fundamentals` (line 48)
- `fetch_company_name` (line 101)
- `fetch_simulation_history` (line 111)
- `fetch_analytics_history` (line 122)
- `fetch_price_history_range` (line 133)

Also update `src/fx.py` and `src/portfolio.py` where `yf.Ticker()` or `yf.download()` are called — import and use the same session. To avoid circular imports, define `_TimeoutSession` and `_session` in `src/cache.py` (which is already imported by all data modules).

- [ ] **Step 3: Improve add-position error messaging**

In `main.py`, around line 700-706, replace the generic error:

```python
if result is None:
    ui.notify("No price data found for that date. Try a different date.", type="negative")
    return
```

with:

```python
if result is None:
    ui.notify(
        f"Could not fetch price for {ticker} on {purchase_date}. "
        "Check the ticker symbol and date, or try again if Yahoo Finance is slow.",
        type="negative",
    )
    return
```

- [ ] **Step 4: Manual test**

Test with a garbage ticker (e.g. "ZZZZZ") — should show clear error. Test with valid ticker — should work normally. Check console for FX warning logs.

- [ ] **Step 5: Commit**

```bash
git add src/fx.py src/data_fetch.py main.py
git commit -m "fix: add timeouts to yfinance calls and improve error messages"
```

---

## Task 5: Decompose main.py — Create src/ui/ Package

**Files:**
- Create: `src/ui/__init__.py`
- Create: `src/ui/shared.py`

**Context:** Before extracting tab modules, create the package and the shared utilities they'll all need.

- [ ] **Step 1: Create src/ui/__init__.py**

```python
"""UI modules for the Market Dashboard."""
```

- [ ] **Step 2: Create src/ui/shared.py**

Extract the shared types and helpers that all tab modules will use:

```python
"""Shared UI utilities used across tab modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from typing import Any

# Type alias for the shared state dict passed to all tab builders
SharedState = dict[str, Any]
```

- [ ] **Step 3: Commit**

```bash
git add src/ui/__init__.py src/ui/shared.py
git commit -m "refactor: create src/ui/ package skeleton"
```

---

## Task 6: Extract Guide Tab

**Files:**
- Create: `src/ui/guide.py`
- Modify: `main.py` (remove `_build_guide_tab`, import from `src.ui.guide`)

**Context:** The simplest extraction — `_build_guide_tab` (lines 162-245) is a pure function with no dependencies on page-level state.

- [ ] **Step 1: Create src/ui/guide.py**

Move `_build_guide_tab` from main.py lines 162-245 into `src/ui/guide.py`:

```python
"""Guide tab — plain-language explanations of dashboard features."""

from nicegui import ui

from src.theme import TEXT_PRIMARY, TEXT_SECONDARY


def build_guide_tab() -> None:
    """Plain-language explanations of every dashboard feature."""
    # ... (exact content from main.py lines 164-245, unchanged)
```

Copy the full function body verbatim from main.py. Only changes:
- Rename from `_build_guide_tab` to `build_guide_tab` (public API)
- Add the two theme imports at the top

- [ ] **Step 2: Update main.py imports and usage**

Remove lines 162-245 from main.py. Add import:

```python
from src.ui.guide import build_guide_tab
```

In `_build_tab` (line 502-503), change:

```python
elif name == "Guide":
    _build_guide_tab()
```

to:

```python
elif name == "Guide":
    build_guide_tab()
```

- [ ] **Step 3: Manual test**

Run the app. Click the Guide tab. Verify all content renders identically.

- [ ] **Step 4: Commit**

```bash
git add src/ui/guide.py main.py
git commit -m "refactor: extract guide tab to src/ui/guide.py"
```

---

## Task 7: Extract Sidebar

**Files:**
- Create: `src/ui/sidebar.py`
- Modify: `main.py` (remove `_build_sidebar`, import from `src.ui.sidebar`)

**Context:** `_build_sidebar` (lines 561-986) is the largest single function. It has the most callback complexity but is self-contained — it takes `portfolio`, `stock_options`, `_shared`, `_active_tab`, and `on_mutation` as arguments. It also needs several module-level constants and imports from main.py.

- [ ] **Step 1: Create src/ui/sidebar.py**

Move `_build_sidebar` (lines 561-986) into `src/ui/sidebar.py`. The function needs these items from main.py:

Constants to move/import:
- `_MARKETS` (line 92-97)
- `_ALT_ASSETS` (line 99)
- `_VALID_TICKER_RE` and `_is_valid_ticker` (lines 102-107)
- `_LS_KEY` (line 72)
- `_SAMPLE_PATH` (line 89)
- `_load_portfolio` and `_save_portfolio` (lines 118-144)

Decision: `_load_portfolio`, `_save_portfolio`, `_LS_KEY`, and the encryption setup (lines 72-86) are used by both sidebar and main page. Move `_load_portfolio`/`_save_portfolio` to `src/ui/shared.py` since they're used across modules.

```python
"""Sidebar — add/remove positions, import/export, sample portfolio."""

from __future__ import annotations

import json
import os
import re

import pandas as pd
from nicegui import run, ui

from src.charts import CHART_COLORS
from src.data_fetch import fetch_company_name
from src.fx import CURRENCY_SYMBOLS, get_fx_rate, get_historical_fx_rate, get_ticker_currency
from src.portfolio import fetch_buy_price
from src.theme import (
    ACCENT_DARK, BG_CARD, BORDER, BORDER_INPUT,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY,
)
from src.ui.shared import load_portfolio, save_portfolio

_SAMPLE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sample_portfolio.json")

_MARKETS = [
    "US — S&P 500", "UK — FTSE 100", "Germany — DAX", "France — CAC 40",
    "Switzerland — SMI", "Netherlands — AEX", "Spain — IBEX 35",
    "Sweden — OMX 30",
    "ETFs", "REITs", "Bonds", "Emerging Markets", "Crypto", "Commodities",
]

_ALT_ASSETS = {"Crypto", "Commodities"}

_VALID_TICKER_RE = re.compile(r'^[A-Za-z0-9.\-=^]{1,15}$')


def _is_valid_ticker(ticker: str) -> bool:
    return isinstance(ticker, str) and bool(_VALID_TICKER_RE.match(ticker))


def build_sidebar(
    portfolio: dict, stock_options: dict, shared: dict,
    active_tab: dict, on_mutation=None,
) -> None:
    # ... (exact content from main.py _build_sidebar lines 567-986)
    # Replace all references to _shared -> shared, _active_tab -> active_tab
    # Replace _load_portfolio -> load_portfolio, _save_portfolio -> save_portfolio
    # Replace _is_valid_ticker (already defined in this module)
```

- [ ] **Step 2: Move persistence functions to shared.py**

Add to `src/ui/shared.py`:

```python
import base64
import json
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from nicegui import app

import logging as _logging
_log = _logging.getLogger(__name__)

_LS_KEY = "market_dashboard_portfolio"

_STORAGE_SECRET = os.environ.get("STORAGE_SECRET", "market-dashboard-dev-fallback")
if _STORAGE_SECRET == "market-dashboard-dev-fallback":
    _log.warning("Using deterministic fallback encryption secret. Set STORAGE_SECRET env var for production.")
    if os.environ.get("HOST", "127.0.0.1") == "0.0.0.0":
        raise RuntimeError("STORAGE_SECRET must be set in production")
_kdf = PBKDF2HMAC(
    algorithm=hashes.SHA256(),
    length=32,
    salt=b"market-dashboard-portfolio-salt",
    iterations=480_000,
)
_fernet = Fernet(base64.urlsafe_b64encode(_kdf.derive(_STORAGE_SECRET.encode())))


def load_portfolio() -> dict:
    """Load and decrypt portfolio from user storage."""
    raw = app.storage.user.get(_LS_KEY, {})
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            decrypted = _fernet.decrypt(raw.encode())
            parsed = json.loads(decrypted)
            return parsed if isinstance(parsed, dict) else {}
        except InvalidToken:
            pass
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def save_portfolio(data: dict) -> None:
    """Encrypt and persist portfolio to user storage."""
    plaintext = json.dumps(data, default=str).encode()
    app.storage.user[_LS_KEY] = _fernet.encrypt(plaintext).decode()


def get_storage_secret() -> str:
    """Return the storage secret for NiceGUI's storage_secret parameter."""
    return _STORAGE_SECRET
```

- [ ] **Step 3: Update main.py**

Remove:
- `_build_sidebar` function (lines 561-986)
- `_load_portfolio`, `_save_portfolio` functions (lines 118-144)
- `_LS_KEY` (line 72)
- Encryption imports and setup (lines 15-16, 74-86)
- `_MARKETS`, `_ALT_ASSETS` (lines 92-99)
- `_VALID_TICKER_RE`, `_is_valid_ticker` (lines 102-107)

**Keep `_SAMPLE_PATH` (line 89) in main.py** — it's still used by `_prewarm_caches` (line 270).

Add imports:

```python
from src.ui.sidebar import build_sidebar
from src.ui.shared import load_portfolio, save_portfolio, get_storage_secret
```

Update all `_load_portfolio` → `load_portfolio`, `_save_portfolio` → `save_portfolio` calls in remaining main.py code.

Update `_build_sidebar(...)` call at line 460 → `build_sidebar(...)`.

Update `storage_secret=_STORAGE_SECRET` at line 1456 → `storage_secret=get_storage_secret()`.

- [ ] **Step 4: Manual test**

Run the app. Test:
- Add a position
- Remove a position (with undo)
- Import/export portfolio JSON
- Load sample portfolio
- Clear all

All should work identically.

- [ ] **Step 5: Commit**

```bash
git add src/ui/shared.py src/ui/sidebar.py main.py
git commit -m "refactor: extract sidebar and persistence to src/ui/"
```

---

## Task 8: Extract Overview Tab

**Files:**
- Create: `src/ui/overview.py`
- Modify: `main.py` (remove `_build_overview`, `_build_comparison`, `_export_excel`)

**Context:** `_build_overview` (lines 989-1228), `_build_comparison` (lines 1231-1327), and `_export_excel` (lines 1330-1435) form a cohesive unit. They share `portfolio_color_map`, `name_map`, `currency`.

- [ ] **Step 1: Create src/ui/overview.py**

Move these three functions into `src/ui/overview.py`:

```python
"""Overview tab — KPI cards, allocation chart, comparison chart, Excel export."""

from __future__ import annotations

import datetime
import json
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from nicegui import run, ui

from src.charts import (
    CHART_COLORS, C_CARD_BRD, C_NEGATIVE, C_POSITIVE,
    build_comparison_chart,
)
from src.data_fetch import (
    fetch_company_name, fetch_price_history_range,
)
from src.fx import CURRENCY_SYMBOLS, get_fx_rate, get_ticker_currency
from src.portfolio import build_portfolio_df
from src.theme import (
    BG_CARD, BORDER, BORDER_SUBTLE,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)


async def build_overview_tab(
    portfolio: dict, currency: str, portfolio_color_map: dict[str, str],
    tabs=None, tab_map: dict | None = None,
) -> None:
    # ... (exact content from _build_overview, lines 993-1228)


async def build_comparison(
    portfolio: dict, name_map: dict, portfolio_color_map: dict, base_currency: str,
) -> None:
    # ... (exact content from _build_comparison, lines 1233-1327)


async def export_excel(portfolio: dict, currency: str) -> None:
    # ... (exact content from _export_excel, lines 1331-1435)
```

- [ ] **Step 2: Update main.py**

Remove `_build_overview`, `_build_comparison`, `_export_excel` functions.

Add import:

```python
from src.ui.overview import build_overview_tab, export_excel
```

Update `_build_tab` to call `build_overview_tab` instead of `_build_overview`.

Update export button callback (line 374) to reference `export_excel`.

- [ ] **Step 3: Manual test**

Run the app with sample portfolio. Verify:
- Overview tab renders KPIs, allocation, comparison chart
- Time range toggle and FX switch work on comparison chart
- Export button downloads Excel file
- Empty portfolio shows getting-started card

- [ ] **Step 4: Commit**

```bash
git add src/ui/overview.py main.py
git commit -m "refactor: extract overview tab and excel export to src/ui/overview.py"
```

---

## Task 9: Move Existing Tab Modules into src/ui/

**Files:**
- Move: `src/nicegui_positions.py` → `src/ui/positions.py`
- Move: `src/nicegui_risk.py` → `src/ui/risk.py`
- Move: `src/nicegui_forecast.py` → `src/ui/forecast.py`
- Modify: `main.py` (update imports)

**Context:** These files are already self-contained modules. This is a pure rename/move — no code changes inside the files themselves.

- [ ] **Step 1: Move files**

```bash
cd /Users/joakimhersche/Documents/Python\ Project/market-dashboard
mv src/nicegui_positions.py src/ui/positions.py
mv src/nicegui_risk.py src/ui/risk.py
mv src/nicegui_forecast.py src/ui/forecast.py
```

- [ ] **Step 2: Update imports in main.py**

Replace:

```python
from src.nicegui_forecast import build_diagnostics_tab, build_forecast_tab
from src.nicegui_positions import build_positions_tab
from src.nicegui_risk import build_risk_tab
```

with:

```python
from src.ui.forecast import build_diagnostics_tab, build_forecast_tab
from src.ui.positions import build_positions_tab
from src.ui.risk import build_risk_tab
```

- [ ] **Step 3: Update internal cross-references**

Check if any of the moved files import from each other using the old `src.nicegui_*` paths. Search:

```bash
grep -r "from src.nicegui_" src/ui/
```

If any found, update to `from src.ui.xxx`.

- [ ] **Step 4: Manual test**

Run the app. Click through all tabs: Overview, Positions, Risk & Analytics, Forecast, Diagnostics, Guide. All should render normally.

- [ ] **Step 5: Commit**

```bash
git add -A src/ui/ src/nicegui_positions.py src/nicegui_risk.py src/nicegui_forecast.py main.py
git commit -m "refactor: move tab modules to src/ui/"
```

---

## Task 10: Final main.py Cleanup

**Files:**
- Modify: `main.py`

**Context:** After Tasks 6-9, main.py should be significantly smaller. This task cleans up anything remaining: verify line count, remove orphaned imports, ensure no dead code.

- [ ] **Step 1: Audit remaining main.py**

Check what's left in main.py. It should contain only:
- App init (static files, PWA head, JSON serializer patch, HTML sanitization patch)
- `_preload` and `_prewarm_caches`
- `index()` page handler (tab shell, shared state init, tab routing)
- `_on_currency_change`
- `_build_color_map`
- `_tab_url`
- `_SecurityHeadersMiddleware`
- `ui.run()`

- [ ] **Step 2: Remove unused imports**

After extractions, main.py no longer needs many of the original imports. Remove any that are no longer referenced:
- `base64`, `os` related to encryption (moved to shared.py)
- `re` (moved to sidebar.py)
- Any `from src.*` imports that were only used by extracted functions

- [ ] **Step 3: Verify line count**

```bash
wc -l main.py
```

Target: under 300 lines. After extracting guide (~84 lines), sidebar (~426 lines), and overview+comparison+export (~447 lines), main.py should land at ~250-300 lines. The remaining code is: app init, patches, preload/prewarm, top bar, about dialog, tab shell, lazy loading, mutation callback, currency change, middleware, and `ui.run()`.

- [ ] **Step 4: Run full test**

```bash
python main.py
```

Walk through every feature: load sample, add position, remove position, switch currencies, switch tabs, export Excel, import JSON.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "refactor: clean up main.py after module extraction"
```

---

## Task 11: Delete Dead Artifacts

**Files:**
- Delete: `FIX_PLAN.md`, `FIX_INSTRUCTIONS.md`, `UI_UX_AUDIT.md`
- Delete: `_audit_test.py`, `_ux_test.py`, `_test_launcher.py`
- Delete: `_test_screenshot.png`, `_test_after_load.png`
- Delete: `_ux_screenshots/`
- Delete: `explainer_day_02_data_layer.md`, `explainer_day_03_portfolio_core.md`
- Delete: `test_integration.py`
- Delete: `demo_raw/` — already git-deleted, commit the staged deletion
- Modify: `src/cache.py:1-8` (remove Streamlit docstring references)
- Modify: `src/monte_carlo.py:7-13` (remove Streamlit docstring references)

- [ ] **Step 1: Delete files**

```bash
cd /Users/joakimhersche/Documents/Python\ Project/market-dashboard
rm -f FIX_PLAN.md FIX_INSTRUCTIONS.md UI_UX_AUDIT.md
rm -f _audit_test.py _ux_test.py _test_launcher.py
rm -f _test_screenshot.png _test_after_load.png
rm -rf _ux_screenshots/
rm -f explainer_day_02_data_layer.md explainer_day_03_portfolio_core.md
rm -f test_integration.py
rm -rf demo_raw/
```

- [ ] **Step 2: Ensure .nicegui/ is gitignored**

Check `.gitignore` contains `.nicegui/`. If not, add it.

- [ ] **Step 3: Clean up Streamlit references in docstrings**

In `src/cache.py`, replace the module docstring (lines 1-8) that references `@st.cache_data`:

```python
"""TTL caches for data-fetch functions.

Three separate caches prevent key collisions between
history, fundamentals, and name lookups.
"""
```

In `src/monte_carlo.py`, remove/update the docstring referencing Streamlit at lines 7-13. Replace with:

```python
"""Monte Carlo simulation engine for portfolio projection and backtesting."""
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove dead planning docs, test artifacts, and Streamlit references"
```

---

## Task 12: Market Analysis for Monetization

**Files:**
- Create: `docs/market-analysis.md`

**Context:** This is pure research — no code changes. Can run in parallel with all other tasks.

- [ ] **Step 1: Research and write analysis**

Create `docs/market-analysis.md` covering:

1. **Target customer segments:**
   - Retail self-directed investors (people who outgrew spreadsheets)
   - Semi-pro traders and finance professionals tracking personal portfolios
   - Small RIAs / independent advisors wanting a lightweight tool
   - Finance students and academics

2. **Competitive landscape:**
   Research and compare: Sharesight, Portfolio Performance (open source), Stock Events, SimplePortfolio, Ziggma, Delta, Kubera. For each: pricing, key features, limitations.

3. **This dashboard's competitive wedge:**
   - Monte Carlo simulation with diagnostics (most competitors don't offer this)
   - Multi-market support (S&P 500, FTSE, DAX, CAC, etc. in one tool)
   - FX-adjusted comparison across markets
   - Excel export with full analytics
   - Self-hostable (privacy-conscious users)
   - No ads, no data selling

4. **Recommended free/paid split:**
   Based on competitor analysis, propose what stays free vs what goes behind subscription.

5. **Pricing benchmarks:**
   What competitors charge, where this product fits.

- [ ] **Step 2: Commit**

```bash
git add docs/market-analysis.md
git commit -m "docs: add market analysis for monetization strategy"
```

---

## Task 13: QA Validation

**Files:** Read-only — verify all changes work together.

**Context:** Run after all code tasks (1-11) are merged. Validates end-to-end.

- [ ] **Step 1: Start the app**

```bash
cd /Users/joakimhersche/Documents/Python\ Project/market-dashboard
python main.py
```

- [ ] **Step 2: Test critical paths**

Walk through each scenario and verify:

| # | Scenario | Expected |
|---|----------|----------|
| 1 | Load app with empty portfolio | Overview shows "Add positions" empty state, Guide card visible |
| 2 | Load Sample Portfolio | All positions appear in sidebar with company names, Overview tab rebuilds |
| 3 | Switch to each tab | Each tab loads with spinner, no scroll jumps, no errors |
| 4 | Change currency to EUR | KPIs update in-place, no page reload, no console warnings |
| 5 | Change currency to GBP | Same as above, GBP symbol shows correctly |
| 6 | Add a position (AAPL, 10 shares, 2024-01-15) | Notification shows, sidebar updates, tab rebuilds |
| 7 | Add a position with manual price | Price field appears, saves correctly |
| 8 | Remove a position | Confirmation dialog, undo toast, sidebar updates |
| 9 | Undo a removal within 5s | Position restored, sidebar and tab update |
| 10 | Export to Excel | File downloads, contains all sheets |
| 11 | Export portfolio JSON | JSON file downloads |
| 12 | Import portfolio JSON | Positions load, tab rebuilds |
| 13 | Clear all | Confirmation dialog, portfolio empties |
| 14 | Comparison chart: toggle time range | Chart updates with debounce, no jumps |
| 15 | Comparison chart: toggle FX-adjusted | Chart recalculates |
| 16 | Positions tab: click different ticker | Price chart updates |
| 17 | Forecast tab: switch position outlook | Fan chart updates for selected ticker |
| 18 | Open app in 2 browser tabs simultaneously | Each session independent, no state bleed |

- [ ] **Step 3: Check console for warnings**

```bash
# In the terminal running main.py, check for:
# - "coroutine was never awaited" warnings (should be zero)
# - Python tracebacks (should be zero during normal operation)
# - FX fallback warnings (acceptable but should be logged, not silent)
```

- [ ] **Step 4: Verify file structure**

```bash
wc -l main.py  # Should be under 300 lines (target ~250-300 after all extractions)
ls src/ui/      # Should contain: __init__.py, shared.py, sidebar.py, overview.py, guide.py, positions.py, risk.py, forecast.py
                # Note: diagnostics stays inside forecast.py (build_diagnostics_tab is exported from there)
ls src/nicegui_*.py 2>/dev/null  # Should return nothing (all moved)
ls FIX_PLAN.md UI_UX_AUDIT.md FIX_INSTRUCTIONS.md 2>/dev/null  # Should return nothing (all deleted)
```

- [ ] **Step 5: Sign off or file issues**

If all checks pass, the app is ready to share with testers. If any fail, file the issue as a follow-up task.