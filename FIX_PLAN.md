# Market Dashboard — UX Fix Plan

## Execution Strategy

This plan is designed for Claude Code to execute using **3 parallel agents + 1 QA agent**.
Each agent works in an isolated worktree so there are no merge conflicts during development.
After all agents finish, merge sequentially and run a final integration QA pass.

```
Agent 1: Fix mutation reload + sidebar staleness     (main.py)
Agent 2: Fix forecast scroll jump                    (src/nicegui_forecast.py, src/theme.py)
Agent 3: Fix comparison "Since" toggle collision     (main.py)
   ↓ merge all into working branch
Agent 4: QA — run full Playwright test suite         (read-only, validates all fixes)
```

---

## Agent 1 — Mutation Reload + Sidebar Staleness

**Files:** `main.py` only

This is the highest-impact fix. Currently every portfolio mutation (add, remove, load sample,
clear) triggers `ui.navigate.to()` which does a full browser reload. This destroys all tab
caches, kills any in-flight notifications (including the undo toast), and forces 15-30s of
data re-fetching. The fix converts mutations to in-place tab rebuilds.

### Step 1: Make `_build_tab` accessible to the sidebar

The `on_mutation` callback currently holds a reference to `_refresh_after_mutation` (line 452).
Change it to hold a reference to `_build_tab` directly, plus a way to invalidate tabs and
recompute sidebar values.

**Replace lines 447-452** (`_refresh_after_mutation` and the wiring):

```python
# ── Mutation callback — rebuild current tab in-place ──
async def _on_portfolio_mutation():
    """Called after any portfolio change (add/remove/load/clear).
    Rebuilds sidebar values and the active tab without a full page reload."""
    nonlocal portfolio_color_map, ticker_values

    # Recompute shared state from the mutated portfolio
    portfolio_color_map = _build_color_map(portfolio)
    if portfolio:
        ticker_values = await run.io_bound(_compute_ticker_values)
    else:
        ticker_values = {}

    # Invalidate all tab caches so they rebuild on next visit
    for name in _TAB_NAMES:
        _tab_built[name] = False

    # Rebuild the currently visible tab
    await _build_tab(_active_tab["name"])

_mutation_ref["fn"] = _on_portfolio_mutation
```

**Important:** This requires making `portfolio_color_map` and `ticker_values` mutable from
this scope. They are already local variables in `index()`, so adding `nonlocal` works.
However, `_compute_ticker_values` is currently an inline `def` at line 370-377 — it needs
to remain accessible. It already is (it's in the same scope).

### Step 2: Make sidebar values reactive

The sidebar's `positions_list()` reads `ticker_values`, `portfolio_color_map`, and
`currency_symbol` from its closure. Since Agent 1 Step 1 now recomputes these before
calling `positions_list.refresh()`, they will be up-to-date — **but only if the sidebar
function reads them from a mutable container rather than captured locals.**

The problem: `_build_sidebar` receives `ticker_values` and `portfolio_color_map` as
**parameters** (line 467-471). These are separate references from the ones in `index()`.
When `index()` reassigns `portfolio_color_map = _build_color_map(...)`, the sidebar's
parameter copy doesn't update.

**Fix:** Change `_build_sidebar` to accept a **shared state dict** instead of individual values:

At line 366-368, before calling `_build_sidebar`, create a shared state container:

```python
# Shared mutable state that sidebar and tabs can both read/write
_shared = {
    "portfolio_color_map": portfolio_color_map,
    "ticker_values": ticker_values,
    "currency": currency,
    "currency_symbol": CURRENCY_SYMBOLS.get(currency, "$"),
}
```

Change `_build_sidebar` signature (line 467) to accept `_shared` instead of individual
`ticker_values`, `portfolio_color_map`, `currency` params. Inside `_build_sidebar`,
replace all reads of `ticker_values` with `_shared["ticker_values"]`, etc.

Inside `positions_list()` (the `@ui.refreshable` function, line 680+):
- Replace `currency_symbol` → `_shared["currency_symbol"]`
- Replace `ticker_values` → `_shared["ticker_values"]`
- Replace `portfolio_color_map` → `_shared["portfolio_color_map"]`

Inside `_on_portfolio_mutation()`:
- After recomputing, update the shared dict:
  ```python
  _shared["portfolio_color_map"] = portfolio_color_map
  _shared["ticker_values"] = ticker_values
  ```

Inside `_on_currency_change()` (line 455):
- Add: `_shared["currency"] = new_currency`
- Add: `_shared["currency_symbol"] = CURRENCY_SYMBOLS.get(new_currency, "$")`
- Add: `positions_list.refresh()` after updating shared state

### Step 3: Make mutation callbacks async-safe

The sidebar mutation calls (`on_mutation["fn"]()`) are called from sync button handlers
and async button handlers. Since `_on_portfolio_mutation` is now `async`, all callers
must `await` it.

**Affected locations in `_build_sidebar`:**

1. **`on_add_position`** (line 564) — already `async`. Change line 661-662:
   ```python
   if on_mutation and on_mutation.get("fn"):
       await on_mutation["fn"]()
   ```

2. **`do_remove`** (line 738) — already `async def`. Change line 746-747:
   ```python
   if on_mutation and on_mutation.get("fn"):
       await on_mutation["fn"]()
   ```
   Also the undo callback `_undo` (line 751) — already `async def`. Change line 760-761:
   ```python
   if on_mutation and on_mutation.get("fn"):
       await on_mutation["fn"]()
   ```

3. **`do_load_sample`** (line 844) — already `async def`. Change line 855-856:
   ```python
   if on_mutation and on_mutation.get("fn"):
       await on_mutation["fn"]()
   ```

4. **`do_clear`** (line 874) — already `async def`. Change line 883-884:
   ```python
   if on_mutation and on_mutation.get("fn"):
       await on_mutation["fn"]()
   ```

5. **`on_import_upload`** (line 772) — already `async def`. Change line 804-805:
   ```python
   if on_mutation and on_mutation.get("fn"):
       await on_mutation["fn"]()
   ```

### Step 4: Remove the old navigate-based refresh

Delete the `_refresh_after_mutation` function (replaced by `_on_portfolio_mutation` in Step 1).

### Verification checklist for Agent 1:

- [ ] `ui.navigate.to` no longer appears anywhere in mutation flow
- [ ] Adding a position does NOT reload the page (no URL change, no spinner on all tabs)
- [ ] Removing a position shows the undo toast for 5 seconds (not destroyed by reload)
- [ ] Load Sample rebuilds Overview in-place
- [ ] Sidebar shows updated dollar values after adding a position
- [ ] Sidebar shows correct currency symbol after changing currency
- [ ] No `NameError` or `AttributeError` from closure references
- [ ] All existing functionality still works (no regressions)

---

## Agent 2 — Fix Forecast Scroll Jump

**Files:** `src/nicegui_forecast.py`, `src/theme.py`

When the user changes the ticker in the Position Outlook dropdown (Forecast tab), the page
jumps to scrollY ~1226px. This happens because `chart_container.clear()` removes the Plotly
chart (which has significant height), causing the page to shrink, then the new chart is
inserted and the page grows again — but the browser has already adjusted scroll position.

### Step 1: Add min-height to position outlook chart card

In `src/nicegui_forecast.py`, line 337-340, the chart containers are created:

```python
with ui.column().classes("chart-card w-full") as pos_chart_card:
    chart_container = ui.column().classes("w-full")
metrics_container = ui.column().classes("w-full")
info_container = ui.column().classes("w-full")
```

**Fix:** Add a min-height to the outer card so it doesn't collapse when content is cleared:

```python
with ui.column().classes("chart-card w-full").style("min-height:400px;") as pos_chart_card:
    chart_container = ui.column().classes("w-full")
metrics_container = ui.column().classes("w-full")
info_container = ui.column().classes("w-full")
```

### Step 2: Show spinner during chart rebuild instead of empty space

In `_update_position_outlook()` (line 342), after clearing containers, show a loading
spinner to maintain visual height and signal progress:

Replace lines 355-357:
```python
chart_container.clear()
metrics_container.clear()
info_container.clear()
```

With:
```python
chart_container.clear()
metrics_container.clear()
info_container.clear()

with chart_container:
    ui.spinner("dots", size="lg").classes("self-center").style("padding:40px 0;")
```

The spinner gets replaced when the actual chart content is added (the subsequent
`chart_container.clear()` at line ~415 before adding the Plotly chart will remove it —
wait, actually there is no second `.clear()`. The code does `with chart_container:` which
**appends** to the container. So we need to clear the spinner before adding chart content.

**Better approach:** Use a single clear + rebuild pattern. After the data fetch and chart
build, clear the spinner and add the chart:

```python
chart_container.clear()
metrics_container.clear()
info_container.clear()

# Show spinner while computing
with chart_container:
    _spinner = ui.spinner("dots", size="lg").classes("self-center").style("padding:40px 0;")

# ... existing data fetch and chart build code ...

# Replace spinner with actual chart
chart_container.clear()
with chart_container:
    ui.plotly(fig).classes("w-full")
```

Wait — the existing code already does this pattern correctly. The `chart_container.clear()`
at line 355 clears everything, then content is added. The issue is that `_update_position_outlook`
is **synchronous** (not async), so the `.clear()` and the chart creation happen in the same
synchronous block. The browser doesn't get a chance to reflow between clear and rebuild
within a single NiceGUI update cycle... **unless** the Plotly chart renders asynchronously
on the client side.

**Root cause confirmed:** The Plotly chart's JavaScript rendering is async. The DOM receives
a placeholder element, then Plotly.js renders the chart asynchronously. During this gap,
the container has near-zero height, causing scroll jump.

**The correct fix is the min-height approach from Step 1.** This ensures the container
never collapses below 400px, preventing scroll position loss.

### Step 3: Apply same fix to Portfolio Outlook containers

In `_render_portfolio_outlook()` (line 168):

```python
with ui.column().classes("chart-card w-full") as chart_card:
    chart_container = ui.column().classes("w-full")
```

Add min-height:
```python
with ui.column().classes("chart-card w-full").style("min-height:400px;") as chart_card:
    chart_container = ui.column().classes("w-full")
```

And the histogram card (line 171):
```python
with ui.column().classes("chart-card w-full").style("min-height:350px;") as hist_card:
    hist_container = ui.column().classes("w-full")
```

### Verification checklist for Agent 2:

- [ ] Changing position ticker on Forecast tab does NOT cause page scroll jump
- [ ] Changing horizon toggle does NOT cause page scroll jump
- [ ] Changing lookback toggle does NOT cause page scroll jump
- [ ] Charts still render correctly after the fix
- [ ] No visual glitch from the min-height (no excess whitespace when chart is smaller)

---

## Agent 3 — Fix "Since" Toggle Collision

**Files:** `main.py`

The "Since" button in the Portfolio Comparison toggle row can't be clicked because
Playwright (and potentially users) match it against the "Since 2022-07-01" text in the
KPI card. This is a text-collision issue. While users won't have this exact problem
(they click visually), the underlying issue is that the "Since" toggle label is ambiguous
and potentially confusing UX-wise.

### Step 1: Rename "Since" to "All" or "Max"

In `_build_comparison()` (line 1138), change:

```python
range_options = {"3M": "3mo", "6M": "6mo", "1Y": "1y", "Since": "since"}
```

To:
```python
range_options = {"3M": "3mo", "6M": "6mo", "1Y": "1y", "Max": "since"}
```

This is clearer UX ("Max" is the standard label used by TradingView, Yahoo Finance,
Bloomberg terminal, etc.) and avoids the text collision.

### Step 2: Also rename in the Positions tab price history

In `src/nicegui_positions.py`, line 316:

```python
range_options = {"3M": 3, "6M": 6, "1Y": 12, "2Y": 24, "Since": None}
```

Change to:
```python
range_options = {"3M": 3, "6M": 6, "1Y": 12, "2Y": 24, "Max": None}
```

### Verification checklist for Agent 3:

- [ ] "Max" button appears in Portfolio Comparison toggles
- [ ] "Max" button is clickable and shows data from earliest purchase date
- [ ] "Max" button appears in Positions price history toggles
- [ ] No other text contains "Since" that could cause confusion (check KPI cards still say "Since YYYY-MM-DD")

---

## Agent 4 — QA Integration Test

**Files:** Read-only. Runs `_ux_test.py` (with updated assertions) against the merged branch.

### Pre-test: Update test assertions

Before running the QA, update `_ux_test.py` to match the fixes:

1. Change the "Since" toggle test to look for "Max" instead
2. Add explicit assertions for:
   - No `ui.navigate.to` calls during mutation (check URL doesn't change)
   - Undo toast visible for 5s after remove
   - Sidebar values update after add position
   - No scroll jump on Forecast position change (scrollY < 200 after change)

### Test execution

Run the full `_ux_test.py` test suite. The expected results:

**Previously failing, should now PASS:**
- Comparison toggle "Since" → now "Max" — should click successfully
- PAGE JUMP after position selector change — min-height prevents it
- Undo toast appears after remove — no page reload kills it

**Previously failing due to test-locator issues (not real bugs):**
- "Positions table NOT rendered" — was a test issue (tab was already built, test re-navigated and checked wrong content). If this still fails, fix the test locator, not the app.
- "Correlation Matrix section present" / "Performance Attribution present" / "Portfolio Outlook section present" / "VaR metrics present" / "Position Outlook section present" / "Monte Carlo Backtest present" / "Hit Rate metrics present" / "Model Reliability table present" — These failed because the test checked `body.inner_text()` **while the tab was still the cached version from a prior visit** or checked immediately after tab switch before content loaded. The spinner wait logic needs to be more robust.

### QA test update strategy

Fix the test to:
1. After switching to a tab, wait for the spinner to disappear OR wait for specific content text
2. After content loads, re-read `body.inner_text()` instead of using stale text
3. Use more specific locators (e.g., `.q-toggle` for toggle buttons instead of `text=Since`)

### Full QA pass/fail criteria

| Test | Must Pass? | Notes |
|------|-----------|-------|
| Page loads | YES | |
| All tabs present | YES | |
| Empty state | YES | |
| Load Sample < 15s | YES | Was 31s with reload; should be <10s with in-place rebuild |
| Tab switching | YES | Each tab < 10s on first visit |
| No page jumps on any interaction | YES | All scrollY checks < 200 |
| Add position < 5s | YES | Was 15s with reload |
| Undo toast after remove | YES | Was broken by reload |
| Currency change updates sidebar | YES | New fix |
| Mobile layout | YES | Already passing |
| No console errors | YES | Already passing |
| Excel export | YES | Already passing |

---

## Execution Command

Paste this into Claude Code to execute the full plan:

```
Run the fix plan in FIX_PLAN.md. Execute Agents 1, 2, and 3 in parallel using
isolated worktrees. Each agent should:
1. Read FIX_PLAN.md for their specific section
2. Implement the changes described
3. Verify the changes compile (python3 -c "import main")

After all 3 agents complete, merge their changes into the working branch, resolve
any conflicts (Agent 1 touches main.py, Agent 3 also touches main.py — merge carefully),
then run Agent 4 as the QA pass using _ux_test.py. Report all results.
```

---

## Architecture Notes

### Why `ui.navigate.to` is wrong for mutations

NiceGUI's `ui.navigate.to()` sends a browser-level navigation event. This:
1. Tears down the entire WebSocket connection
2. Browser requests a fresh page from the server
3. Server runs `index()` from scratch — re-reads storage, rebuilds all UI
4. All cached tab content is destroyed
5. All in-flight notifications are destroyed
6. User sees a flash of blank screen

The correct NiceGUI pattern for updating content is:
1. Mutate the data
2. Call `container.clear()` on the affected containers
3. Rebuild content inside those containers using `with container:`
4. NiceGUI's WebSocket sends incremental DOM updates — no page reload

### Why shared mutable state via dict

Python closures capture **variables by reference**, but reassignment creates a new local.
If `index()` does `portfolio_color_map = new_map`, the sidebar's captured reference still
points to the old dict. By using `_shared["portfolio_color_map"] = new_map`, we mutate
the dict that both scopes reference — the sidebar sees the update immediately.

### Why min-height for scroll stability

Professional trading dashboards (Bloomberg Terminal, TradingView, Refinitiv Eikon) use
fixed-height panels for chart areas. When chart content refreshes, the container height
stays constant, preventing layout shift. The `min-height: 400px` approach is the simplest
version of this pattern — it prevents the container from collapsing to 0 during async
Plotly rendering, which is what causes the scroll jump.

---
---

# PART 2 — Visual Design Consistency & Readability Fixes

The audit below covers every UI element that breaks the dark trading dashboard aesthetic:
default-styled framework widgets, Plotly tooltip/modebar issues, contrast failures,
truncation without recovery, and hardcoded colors that bypass the theme system.

## Updated Execution Strategy

Add two more agents to the parallel execution. These are independent of Agents 1-3
and can run simultaneously.

```
Agent 1: Fix mutation reload + sidebar staleness       (main.py)
Agent 2: Fix forecast scroll jump                      (src/nicegui_forecast.py)
Agent 3: Fix "Since" toggle collision                  (main.py, src/nicegui_positions.py)
Agent 5: Plotly chart theme + hover tooltips            (src/charts.py)
Agent 6: Quasar dark theme CSS + readability            (src/theme.py, main.py — inline styles only)
   ↓ merge all into working branch
Agent 4: QA — run full Playwright test suite + visual spot checks
```

Agent 5 and Agent 6 touch completely different files from each other and from Agents 1-3,
so all 5 can run in parallel. Agent 1 and Agent 3 both touch `main.py` — merge Agent 1
first, then rebase Agent 3 on top (Agent 3's changes are two-line edits, easy to reapply).

---

## Agent 5 — Plotly Chart Theme Consistency

**Files:** `src/charts.py` only

Every Plotly chart must match the dashboard's dark theme. The current code has default
white hover tooltips, an unstyled modebar, missing legend backgrounds, and inconsistent
color token usage.

### Step 1: Add hover tooltip styling to the shared layout function

In `src/charts.py`, find `_apply_default_layout()` (the function that all charts call
for shared layout settings). Add `hoverlabel` to the `fig.update_layout()` call:

```python
hoverlabel=dict(
    bgcolor="#1C1D26",
    bordercolor="#1E293B",
    font=dict(color="#F1F5F9", size=11, family="Inter, sans-serif"),
),
```

This single change fixes hover tooltips on ALL charts — fan charts, comparison chart,
price history, QQ plot, histogram, correlation heatmap.

### Step 2: Hide the Plotly modebar

The modebar (zoom/pan/save icons) uses default light styling and looks out of place.
Professional dashboards either hide it or show it only on hover.

**Option A (hide completely):** Add to `_apply_default_layout()`:
```python
fig.update_layout(modebar=dict(bgcolor="rgba(0,0,0,0)", color="#64748B", activecolor="#94A3B8"))
```

This makes the modebar transparent with dim icons that only show on hover — matching
what TradingView does.

**Option B (CSS fallback):** If NiceGUI doesn't pass config properly, add to `src/theme.py`
in the GLOBAL_CSS:
```css
.js-plotly-plot .modebar {
    background: transparent !important;
}
.js-plotly-plot .modebar .modebar-btn path {
    fill: #64748B !important;
}
.js-plotly-plot .modebar .modebar-btn:hover path {
    fill: #94A3B8 !important;
}
```

### Step 3: Fix legend styling on all charts

Add `bgcolor` and `bordercolor` to every chart function that has a legend.
Find each `legend=dict(...)` call and ensure it includes:

```python
legend=dict(
    ...,  # existing positioning
    bgcolor="rgba(0,0,0,0)",
    bordercolor="rgba(255,255,255,0.06)",
    font=dict(size=10, color="#94A3B8"),
)
```

**Affected functions:**
- `build_comparison_chart` — legend at bottom of chart
- `build_fan_chart` — legend above chart
- `build_qq_plot` — legend above chart
- `build_price_history_chart` — legend if multiple traces

### Step 4: Fix correlation heatmap colorbar text

In `build_correlation_heatmap()`, the colorbar title and tick labels need explicit
color styling:

```python
coloraxis_colorbar=dict(
    title="Correlation",
    title_font=dict(color="#94A3B8", size=10),
    tickfont=dict(color="#94A3B8", size=9),
    tickvals=[0, 0.25, 0.5, 0.75, 1],
)
```

### Step 5: Replace hardcoded hex colors with theme constants

Audit every raw hex string in `charts.py` and replace with the matching constant
where one exists:

| Current hardcoded | Should be | Locations |
|-------------------|-----------|-----------|
| `"#9CA3AF"` | `TEXT_MUTED` (#94A3B8) — close but wrong shade | Lines ~194, ~490 |
| `"#DC2626"` | `C_NEGATIVE` (already defined) | Histogram annotations |
| `"#16A34A"` | `C_POSITIVE` (already defined) | Histogram annotations |
| `"rgba(59,130,246,0.3)"` | Use `ACCENT` with opacity | Fan chart today line |

### Verification checklist for Agent 5:

- [ ] Hover over any chart → tooltip has dark background (#1C1D26), light text, dark border
- [ ] Modebar is transparent/hidden or styled with dim icons
- [ ] All chart legends have transparent background, no white box
- [ ] Heatmap colorbar labels are light text on dark background
- [ ] No raw `#9CA3AF` or other off-theme hex values remain in charts.py

---

## Agent 6 — Quasar Dark Theme CSS + Readability

**Files:** `src/theme.py` (GLOBAL_CSS), `main.py` (inline styles only — replacing
hardcoded hex with theme constants)

This agent adds CSS rules for every unstyled Quasar component and fixes readability
issues found in the audit.

### Step 1: Style dropdown menus (CRITICAL — currently white)

Add to GLOBAL_CSS in `src/theme.py`, after the existing Quasar overrides:

```css
/* ── Dropdown menus (select, date picker, context menus) ── */
.q-menu {
    background: %(BG_CARD)s !important;
    border: 1px solid %(BORDER)s !important;
    border-radius: 8px !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4) !important;
}
.q-item {
    color: %(TEXT_SECONDARY)s !important;
    font-size: 12px !important;
    min-height: 36px !important;
}
.q-item:hover, .q-item--active {
    background: rgba(59,130,246,0.1) !important;
    color: %(TEXT_PRIMARY)s !important;
}
.q-item__label {
    color: inherit !important;
}
```

This fixes: currency dropdown, market dropdown, ticker dropdown, position selector
on Forecast tab, QQ plot ticker selector on Diagnostics tab.

### Step 2: Style date picker

```css
/* ── Date picker ── */
.q-date {
    background: %(BG_CARD)s !important;
    color: %(TEXT_PRIMARY)s !important;
    border: 1px solid %(BORDER)s !important;
}
.q-date__header {
    background: rgba(59,130,246,0.15) !important;
    color: %(TEXT_PRIMARY)s !important;
}
.q-date__calendar-item .q-btn {
    color: %(TEXT_SECONDARY)s !important;
}
.q-date__calendar-item .q-btn--unelevated {
    background: %(ACCENT)s !important;
    color: #fff !important;
}
.q-date__navigation .q-btn {
    color: %(TEXT_MUTED)s !important;
}
```

### Step 3: Style switch and checkbox

```css
/* ── Switch ── */
.q-toggle__inner {
    color: %(TEXT_DIM)s !important;
}
.q-toggle__inner--truthy {
    color: %(ACCENT)s !important;
}

/* ── Checkbox ── */
.q-checkbox__inner {
    color: %(TEXT_DIM)s !important;
}
.q-checkbox__inner--truthy {
    color: %(ACCENT)s !important;
}
```

### Step 4: Style scrollbars

```css
/* ── Scrollbars ── */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: transparent;
}
::-webkit-scrollbar-thumb {
    background: rgba(255,255,255,0.12);
    border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(255,255,255,0.2);
}
/* Firefox */
* {
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.12) transparent;
}
```

### Step 5: Style text selection

```css
/* ── Text selection ── */
::selection {
    background: rgba(59,130,246,0.3);
    color: %(TEXT_PRIMARY)s;
}
```

### Step 6: Style spinner color

```css
/* ── Spinner ── */
.q-spinner {
    color: %(ACCENT)s !important;
}
```

### Step 7: Add toggle button hover/focus states

Extend the existing `.q-btn-toggle` rules:

```css
.q-btn-toggle .q-btn:not(.q-btn--active):hover {
    background: rgba(255,255,255,0.06) !important;
}
.q-btn-toggle .q-btn:focus-visible {
    outline: 1px solid %(ACCENT)s !important;
    outline-offset: -1px;
}
```

### Step 8: Style notification variants

```css
/* ── Notification variants ── */
.q-notification {
    font-family: 'Inter', system-ui, sans-serif !important;
}
.q-notification .q-btn {
    color: %(TEXT_PRIMARY)s !important;
}
```

### Step 9: Fix placeholder contrast (CRITICAL — WCAG failure)

The current `TEXT_GHOST = "#5A6A7A"` gives only 2.98:1 contrast on dark inputs.
Bump it to meet the 4.5:1 threshold.

In `src/theme.py`, change the TEXT_GHOST definition:

```python
TEXT_GHOST = "#7B8BA0"  # was #5A6A7A — bumped for WCAG AA on dark inputs (4.8:1)
```

This matches `TEXT_DIM` and gives ~4.8:1 contrast on `BG_INPUT (#1D1E26)`.

### Step 10: Add table zebra striping

Add to GLOBAL_CSS:

```css
.table-wrap tbody tr:nth-child(even) {
    background: rgba(255,255,255,0.015);
}
```

This is extremely subtle — just enough to aid horizontal tracking without breaking
the clean dark aesthetic.

### Step 11: Increase toggle button padding on desktop

Change the existing `.q-btn-toggle .q-btn` rule:

```css
.q-btn-toggle .q-btn {
    padding: 4px 10px !important;  /* was 3px 8px */
    min-height: 28px !important;    /* add minimum height */
}
```

### Step 12: Add title attributes for truncated text

In `main.py`, the sidebar company name already has a `title` attribute (line 707):
```python
.props(f'title="{company_name}"')
```

But in the allocation chart (line 1079), the ticker label truncates at 64px with no
title. Since this is raw HTML, add a `title` attribute:

```python
f'<div style="width:64px;..." title="{ticker}">{ticker}</div>'
```

### Step 13: Replace hardcoded colors in main.py with theme constants

These are non-functional changes for maintainability. Replace inline hex values
with the f-string theme constants:

| Line | Current | Replace with |
|------|---------|-------------|
| ~320 | `background:#1D1E26` | `background:{BG_INPUT}` (import if needed) |
| ~320 | `rgba(255,255,255,0.1)` | `{BORDER_INPUT}` |
| ~325 | `rgba(255,255,255,0.12)` | `{BORDER_INPUT}` |
| ~330 | `background:#1E293B` | `background:{BG_CARD}` |
| ~667 | `color:#fff` | `color:{TEXT_PRIMARY}` |
| ~997 | `background:#1C1D26` | `background:{BG_CARD}` |
| ~1016 | `color:#F1F5F9` | `color:{TEXT_PRIMARY}` |
| ~1041 | `color:#F1F5F9` | `color:{TEXT_PRIMARY}` |

### Step 14: Add Plotly modebar CSS (backup for Agent 5)

```css
/* ── Plotly modebar ── */
.js-plotly-plot .modebar {
    background: transparent !important;
}
.js-plotly-plot .modebar-btn path {
    fill: %(TEXT_DIM)s !important;
}
.js-plotly-plot .modebar-btn:hover path {
    fill: %(TEXT_MUTED)s !important;
}
```

### Verification checklist for Agent 6:

- [ ] Click any dropdown → dark background menu with light text
- [ ] Open date picker → dark themed calendar
- [ ] Switches and checkboxes show accent color when active
- [ ] Scrollbars are thin and dark-themed
- [ ] Text selection uses blue highlight
- [ ] Spinners are accent-blue, not default Quasar blue
- [ ] Toggle buttons have hover highlight
- [ ] Input placeholders are clearly readable (contrast >= 4.5:1)
- [ ] Tables have subtle zebra striping
- [ ] Toggle buttons are at least 28px tall
- [ ] No hardcoded hex colors remain in main.py inline styles
- [ ] Plotly modebar is transparent with dim icons

---

## Agent 4 (Updated) — QA Integration Test

After merging all 5 agents (1, 2, 3, 5, 6), run the full QA pass.

### Additional visual checks to add to `_ux_test.py`:

```python
# ── Test: Dropdown menu styling ──
# Click a dropdown, take screenshot, verify dark background
page.locator(".q-drawer .q-select").first.click()
page.wait_for_timeout(500)
menu = page.locator(".q-menu")
if menu.count() > 0:
    menu_bg = menu.first.evaluate("el => getComputedStyle(el).backgroundColor")
    # Should be dark (rgb values < 50 each)
    screenshot(page, "qa_dropdown_dark")
page.keyboard.press("Escape")

# ── Test: Plotly hover tooltip styling ──
# Hover over a chart data point, take screenshot
chart = page.locator(".js-plotly-plot").first
if chart.count() > 0:
    box = chart.bounding_box()
    if box:
        page.mouse.move(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.5)
        page.wait_for_timeout(500)
        screenshot(page, "qa_chart_hover")

# ── Test: Scrollbar styling ──
# Scroll the main content and take screenshot
page.evaluate("window.scrollTo(0, 300)")
page.wait_for_timeout(300)
screenshot(page, "qa_scrollbar_visible")

# ── Test: Placeholder contrast ──
# Check sidebar input placeholder visibility
screenshot(page, "qa_sidebar_form")
```

### Updated pass/fail criteria

| Test | Must Pass? | New? |
|------|-----------|------|
| Dropdown menus have dark background | YES | NEW |
| Plotly hover tooltips are dark | YES | NEW |
| No white modebar on charts | YES | NEW |
| Input placeholders are readable | YES | NEW |
| Tables have zebra striping | YES | NEW |
| All previous tests still pass | YES | |

---

## Updated Execution Command

```
Run the fix plan in FIX_PLAN.md. Execute Agents 1, 2, 3, 5, and 6 in parallel
using isolated worktrees. Each agent should:
1. Read FIX_PLAN.md for their specific section
2. Implement ALL changes described in their section
3. Verify the changes compile (python3 -c "import py_compile; py_compile.compile('src/theme.py')")

Merge order:
1. Agent 6 first (theme.py — foundation CSS)
2. Agent 5 next (charts.py — no conflicts)
3. Agent 2 next (nicegui_forecast.py — no conflicts)
4. Agent 1 next (main.py — largest change)
5. Agent 3 last (main.py + nicegui_positions.py — small edits, rebase on Agent 1)

After merging, run Agent 4 as the QA pass using _ux_test.py. Report all results.
```

---

## Complete Issue Inventory

### Plotly Charts (Agent 5)

| # | Issue | File | Severity |
|---|-------|------|----------|
| P1 | Default white hover tooltips on ALL charts | src/charts.py | CRITICAL |
| P2 | Plotly modebar unstyled (light icons on dark bg) | src/charts.py + src/theme.py | HIGH |
| P3 | Legend missing bgcolor/bordercolor (4 chart functions) | src/charts.py | MEDIUM |
| P4 | Heatmap colorbar text unstyled (default dark text) | src/charts.py | MEDIUM |
| P5 | Hardcoded #9CA3AF instead of TEXT_MUTED (#94A3B8) | src/charts.py | LOW |

### Quasar Components (Agent 6)

| # | Issue | File | Severity |
|---|-------|------|----------|
| Q1 | Dropdown menus (.q-menu, .q-item) default white bg | src/theme.py | CRITICAL |
| Q2 | Date picker default white/light theme | src/theme.py | HIGH |
| Q3 | Switch/checkbox default Quasar styling | src/theme.py | HIGH |
| Q4 | Scrollbars browser-default (thick, light) | src/theme.py | MEDIUM |
| Q5 | Text selection default browser blue | src/theme.py | MEDIUM |
| Q6 | Spinner default Quasar blue instead of theme accent | src/theme.py | MEDIUM |
| Q7 | Toggle buttons no hover/focus states | src/theme.py | MEDIUM |
| Q8 | Notification variant colors not overridden | src/theme.py | LOW |

### Readability (Agent 6)

| # | Issue | File | Severity |
|---|-------|------|----------|
| R1 | TEXT_GHOST placeholder contrast 2.98:1 (WCAG AA fail) | src/theme.py | CRITICAL |
| R2 | No table zebra striping (hard to track rows) | src/theme.py | MEDIUM |
| R3 | Toggle buttons too small (3px padding, ~20px tall) | src/theme.py | MEDIUM |
| R4 | Allocation chart ticker truncation, no title attr | main.py | LOW |

### Hardcoded Colors (Agent 6)

| # | Issue | File | Severity |
|---|-------|------|----------|
| H1 | KPI cards use `#1C1D26` instead of BG_CARD constant | main.py | LOW |
| H2 | Currency dropdown uses `#1D1E26` instead of BG_INPUT | main.py | LOW |
| H3 | About dialog uses `#1E293B` not matching any constant | main.py | LOW |
| H4 | Add button `#fff` instead of TEXT_PRIMARY | main.py | LOW |
| H5 | KPI values `#F1F5F9` instead of TEXT_PRIMARY | main.py | LOW |
| H6 | Topbar borders use different rgba values for same visual | main.py | LOW |
