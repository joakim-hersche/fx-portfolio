# Launch Readiness: Free Testing Phase

**Date:** 2026-03-19
**Status:** Approved design
**Goal:** Get the NiceGUI market dashboard to a state where it can be shared with coworkers in banking and university friends for free testing, then use feedback to inform a subscription launch.

## Context

The Streamlit-to-NiceGUI migration is functionally complete (all 6 tabs work, data layer is solid, deployment is containerized, URL is public). But the app has bugs and UX issues that would cause a banker to close the tab within 30 seconds.

Lazy tab loading, spinners, and in-place mutation rebuilds are **already implemented** (main.py:473-539). The remaining work is smaller and more targeted than initially scoped.

**Strategy:** Fix what would embarrass you, ship, collect feedback, then build subscription infrastructure informed by real usage.

## Approach

Approach A (performance-first) was selected over feature-first (B) and full-rewrite (C). Auth and multi-user can wait — localStorage is sufficient for the validation phase. NiceGUI creates a new page instance per connection, so concurrent testers get isolated server-side state.

---

## Section 1: Fix Async Bugs

Two confirmed silent failures.

### 1a. Currency change callback
- **File:** `main.py:370`
- **Bug:** `on_change=lambda e: _on_currency_change(e.value)` — `_on_currency_change` is async, coroutine created but never awaited. The `# noqa: async handled` comment is misleading and must be removed.
- **Fix:** Replace lambda with direct async handler, e.g. `on_change=lambda e: asyncio.create_task(_on_currency_change(e.value))`, or restructure to pass the async function directly.

### 1b. Blocking company name fetch in sidebar
- **File:** `main.py:788`
- **Bug:** `fetch_company_name(ticker)` called synchronously inside `@ui.refreshable` `positions_list()`. This runs on the UI thread and makes a `yf.Ticker(ticker).info` network call for every position, blocking the entire UI.
- **Fix:** Pre-fetch all company names into `_shared["name_map"]` once during `_on_portfolio_mutation` and on initial portfolio load (using `run.io_bound()` with a batch fetch). The sidebar then reads from the dict — zero network calls during render.
- **Note:** Other call sites (e.g. `main.py:1053` in Overview) already use ThreadPoolExecutor and are fine.

**Scope:** Surgical fixes, small diffs, no architectural changes.

---

## Section 2: Performance Polish

Lazy loading and mutation rebuilds are already in place. What remains:

### 2a. Chart container min-heights
- Add `min-height: 400px` to Plotly chart wrapper containers only (not Guide tab or empty states)
- Prevents scroll jumps when charts render asynchronously
- Remove the min-height after chart renders (via removing the style class after async build completes)

### 2b. Error surfacing
- Replace broad silent `except Exception` catches with user-visible notifications for network failures
- Distinguish between bad ticker, bad date, and yfinance being down (currently `main.py:639` shows same message for all)
- Surface FX rate fallback (currently `fx.py:49-51` silently returns 1.0) as a warning notification
- Add timeout handling for yfinance calls that hang indefinitely

### 2c. Multi-user resilience
- Verify session isolation under concurrent load (NiceGUI page instances should be independent)
- Add basic rate-limit awareness for yfinance when multiple users trigger data fetches simultaneously
- Add global error boundary / logging so crashes from one session don't affect others

**Scope:** Targeted improvements to existing infrastructure.

---

## Section 3: Decompose main.py

Extract the 1377-line monolith into focused modules to enable fast iteration on tester feedback.

### Target structure
```
main.py              (~150 lines) — app init, routing, top bar, tab shell
src/ui/
  __init__.py
  sidebar.py         — add/remove form, positions list, import/export/clear
  overview.py        — KPI cards, allocation chart, comparison chart
  positions.py       — positions table, price history (absorbs nicegui_positions.py)
  risk.py            — correlation, fundamentals, heatmap (absorbs nicegui_risk.py)
  forecast.py        — Monte Carlo, fan charts (absorbs nicegui_forecast.py)
  diagnostics.py     — backtest, QQ, reliability (split from forecast if combined)
  guide.py           — static content
  shared.py          — loading spinner helper, tab caching logic, state dict type
```

### Rules
- `src/ui/` is the target directory (alongside existing `src/` modules)
- Each tab module exports: `async def build_xxx_tab(container, portfolio, currency, shared)` — matches current calling convention with explicit `shared` dict added
- Current tab builders already take `(portfolio, currency)` — adding `shared` is the only signature change
- Existing `src/nicegui_*.py` files are absorbed into corresponding `src/ui/` modules, then deleted
- Sidebar gets its own module (most callback complexity)
- App should behave identically before and after

**Scope:** Refactor only. Zero user-facing changes.

---

## Section 4: Cleanup Dead Artifacts

Remove files that no longer serve a purpose.

### Delete
- `FIX_PLAN.md` — already implemented
- `FIX_INSTRUCTIONS.md` — already implemented
- `UI_UX_AUDIT.md` — findings fixed or captured here
- `_audit_test.py`, `_ux_test.py`, `_test_launcher.py` — throwaway test scripts
- `_test_screenshot.png`, `_test_after_load.png` — test artifacts
- `_ux_screenshots/` — audit artifacts
- `explainer_day_02_data_layer.md`, `explainer_day_03_portfolio_core.md` — dev notes
- `demo_raw/` — already git-deleted, commit the deletion
- `test_integration.py` — orphaned test file

### Keep (intentional)
- `DEPLOY.md` — deployment guide, still needed
- `static/fonts/` — self-hosted fonts for firewall environments
- `.nicegui/` — must be in `.gitignore`, not committed

### Clean up
- Remove Streamlit references in `cache.py:1-8` docstring
- Remove Streamlit references in `monte_carlo.py:7-13` docstring
- Remove misleading `# noqa: async handled` comment at `main.py:370`

**Scope:** Deletion pass, no code changes beyond docstring cleanup.

---

## Section 5: Market Analysis for Monetization

Runs in parallel with technical work, doesn't block shipping.

### Deliverable
A concise analysis document covering:
- Target customer segments (retail investors, semi-pro traders, small RIAs, fintech teams)
- Competitive landscape (Portfolio Performance, Sharesight, Stock Events, SimplePortfolio, etc.)
- Free vs paid feature gating in existing products
- This dashboard's competitive wedge
- Recommended free/paid tier split for current feature set
- Pricing benchmarks

### Purpose
Inform post-feedback decisions about what to gate behind a subscription. Not a business plan.

---

## Execution Order

Section 1 is small and surgical. Section 2 builds on the same area. Run them sequentially to avoid conflicts on the currency/mutation code paths.

```
Timeline:
  [1: async bugs] ──▶ [2: perf polish] ──▶ [3: decompose main.py] ──▶ [QA]
  [4: cleanup] ────────────────────────────────────────────────────────┘
  [5: market analysis] ────────────────────────────────────────────────▶ [doc]
```

- **Sections 1 → 2:** Sequential (touch overlapping code paths around currency change and mutation callbacks)
- **Section 3:** After 1+2 merge (restructures the files they modified)
- **Section 4:** Parallel with everything (independent file deletions)
- **Section 5:** Parallel with everything (pure research, no code)
- **QA:** After all code changes merge

### Pre-work
Tag current working state (`git tag pre-launch-readiness`) before any changes, as a rollback point.

## Success Criteria

- Currency change works without page reload
- Sidebar renders without blocking the UI (no synchronous network calls)
- Errors surface as user-visible notifications, not silent swallows
- main.py is under 300 lines
- All existing `src/nicegui_*.py` files absorbed into `src/ui/`
- No dead planning docs or test artifacts in repo root
- Coworkers in banking don't close the tab in the first 30 seconds