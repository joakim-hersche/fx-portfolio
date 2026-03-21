# Mobile Touch Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 33 mobile touch UI issues (7 critical, 14 major, 12 minor) identified in the iPhone audit.

**Architecture:** Pure CSS fixes in theme.py for layout/sizing issues; targeted Python edits in tab files for control-row overflow and missing mobile logic. No new files, no new dependencies.

**Tech Stack:** NiceGUI, Quasar CSS, Plotly, Python

**Important notes:**
- Line numbers are approximate — search for the code patterns, not exact lines (earlier tasks shift later line numbers).
- Task 7 (income.py KPI grid) depends on Task 1 (kpi-row grid fix). Task 1 MUST be completed first.
- Tasks 2 and 11 are coupled: Task 2 changes `.table-wrap table` to `.table-wrap table.wide-table`, Task 11 adds that class to tables that need it.

---

## File Map

| File | Changes |
|------|---------|
| `src/theme.py` | CSS specificity fix, grid/flex fix, tab bar icon color, PWA safe-area, touch targets, table min-width, breakpoint consistency |
| `main.py` | Add Income+Forecast to mobile tab bar, pin search bar, remove user-scalable=no, bump market status font |
| `src/ui/positions.py` | Wrap price history controls in responsive container |
| `src/ui/forecast.py` | Wrap position outlook controls, fix QQ select width, add is_mobile() chart sizing |
| `src/ui/overview.py` | Wrap comparison controls, enlarge ticker pills and All/None buttons |
| `src/ui/income.py` | Remove inline grid-template-columns, add mobile chart height |
| `src/ui/sidebar.py` | Bump form labels to 11px, enlarge checkbox touch target, bump add button to 44px |
| `src/ui/research.py` | Show price chart on mobile (simplified) or add "view on desktop" note, enlarge recent search buttons |
| `src/ui/health.py` | Add "available on desktop" messages for hidden sections |
| `src/ui/alerts.py` | Wrap settings row for mobile |
| `src/ui/guide.py` | Add overflow wrapper for markdown tables |

---

### Task 1: Theme CSS — Critical specificity and layout fixes

Fixes: C2 (sidebar search specificity), C7 (kpi-row flex on grid)

**Files:**
- Modify: `src/theme.py` — phone search override (search for `.sidebar-search .q-field__control` in phone breakpoint)
- Modify: `src/theme.py` — kpi-row phone rule (search for `flex-direction: column` in phone breakpoint)

- [ ] **Step 1: Fix C2 — sidebar search CSS specificity**

The base rule at line 955 (`.sidebar-search .q-field__control { min-height: 36px }`) overrides the phone rule at line 477 because it appears later with equal specificity. Fix by adding a phone-scoped qualifier to increase specificity:

In the phone breakpoint block (`@media (pointer: coarse) and (max-width: 767px)`), change:
```css
.sidebar-search .q-field__control {
    min-height: 44px !important;
    height: 44px !important;
```
to:
```css
.q-drawer .sidebar-search .q-field__control {
    min-height: 44px !important;
    height: 44px !important;
```

This adds specificity so it beats the base rule regardless of source order.

- [ ] **Step 2: Fix C7 — kpi-row phone layout**

At line 519, replace:
```css
.kpi-row { flex-direction: column !important; gap: 8px !important; }
```
with:
```css
.kpi-row { grid-template-columns: 1fr !important; gap: 8px !important; }
```

This is a grid container — `flex-direction` is meaningless on it. `grid-template-columns: 1fr` forces single-column.

- [ ] **Step 3: Fix C1 — add three-zone flex layout to tablet tier**

The three-zone sidebar layout only exists in the phone breakpoint, but `.touch-only` elements (zone-top, zone-bottom) are visible on ALL touch devices. Fix by adding the same three-zone flex layout rules to the tablet tier (`@media (pointer: coarse) and (min-width: 768px)`).

In the tablet tier, add after the existing sidebar rules:
```css
/* Three-zone sidebar layout for tablets too */
.q-drawer__content {
    display: flex !important;
    flex-direction: column !important;
    overflow: hidden !important;
}
.q-drawer .sidebar {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 !important;
    overflow: hidden !important;
    min-height: 0 !important;
}
.sidebar-zone-top { flex-shrink: 0; }
.sidebar-zone-positions { flex: 1; overflow-y: auto; -webkit-overflow-scrolling: touch; min-height: 0; }
.sidebar-zone-bottom { flex-shrink: 0; }
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "from src.theme import GLOBAL_CSS; print('OK')" `
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/theme.py
git commit -m "fix: CSS specificity, grid layout, iPad zone scoping for mobile"
```

---

### Task 2: Theme CSS — Touch targets, sizing, and polish

Fixes: M1 (tab icon color), M2 (PWA double safe-area), m1 (tab label size), m4 (currency pills), m5 (breakpoint consistency), m8 (table min-width)

**Files:**
- Modify: `src/theme.py` — search for tab-item rules, PWA standalone block, currency pills min-height, 479px breakpoint, table min-width

- [ ] **Step 1: Fix M1 — tab bar active icon color**

At lines 415-418, the tab icons use SVG stroke for color. But Material Icons are font-based, not SVGs. Add explicit `color` rules:

Change:
```css
.mobile-tab-bar .tab-item svg { stroke: #64748B; }
.mobile-tab-bar .tab-item .tab-label { font-size: 9px; color: #64748B; }
.mobile-tab-bar .tab-item.active svg { stroke: #3B82F6; }
.mobile-tab-bar .tab-item.active .tab-label { color: #3B82F6; font-weight: 600; }
```
to:
```css
.mobile-tab-bar .tab-item svg { stroke: #64748B; }
.mobile-tab-bar .tab-item .q-icon { color: #64748B; }
.mobile-tab-bar .tab-item .tab-label { font-size: 10px; color: #64748B; }
.mobile-tab-bar .tab-item.active svg { stroke: #3B82F6; }
.mobile-tab-bar .tab-item.active .q-icon { color: #3B82F6; }
.mobile-tab-bar .tab-item.active .tab-label { color: #3B82F6; font-weight: 600; }
```

This also bumps tab label from 9px to 10px (m1).

- [ ] **Step 2: Fix M2 — PWA standalone double safe-area**

At lines 917-920, replace:
```css
@media (display-mode: standalone) {
  body { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }
  .q-header { padding-top: env(safe-area-inset-top); }
}
```
with:
```css
@media (display-mode: standalone) {
  body { padding-bottom: env(safe-area-inset-bottom); }
}
```

The header already gets `padding-top: env(safe-area-inset-top)` in the shared touch tier (line 668). The body padding was doubling it.

- [ ] **Step 3: Fix m5 — add pointer:coarse to 479px breakpoint**

At line 606, change:
```css
@media (max-width: 479px) {
```
to:
```css
@media (pointer: coarse) and (max-width: 479px) {
```

- [ ] **Step 5: Fix m4 — currency pills touch target**

At line 736, change:
```css
min-height: 36px !important;
```
to:
```css
min-height: 44px !important;
```

- [ ] **Step 6: Fix m8 — remove blanket table min-width on phones**

At line 532 (inside phone breakpoint), change:
```css
.table-wrap table { min-width: 600px; }
```
to:
```css
.table-wrap table.wide-table { min-width: 600px; }
```

Then in the tablet tier, also update line 778:
```css
.table-wrap table { min-width: 600px; }
```
to:
```css
.table-wrap table.wide-table { min-width: 600px; }
```

Tables that actually need forced width will get the `wide-table` class added in their respective tab files.

- [ ] **Step 7: Verify syntax**

Run: `python3 -c "from src.theme import GLOBAL_CSS; print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add src/theme.py
git commit -m "fix: touch targets, PWA safe-area, tab icon color, table min-width"
```

---

### Task 3: Main.py — Mobile navigation

Fixes: M3 (search bar pinned), M13 (viewport zoom), m2 (market status font), add Income+Forecast to mobile tab bar

**Files:**
- Modify: `main.py` — search for `_MOBILE_TABS`, viewport meta tag, market status font-size
- Modify: `src/theme.py` — phone breakpoint (add sticky search rule)

- [ ] **Step 1: Add Income and Forecast tabs to mobile tab bar**

At line 678, change:
```python
_MOBILE_TABS = [
    ("Overview", "Overview", "grid_view"),
    ("Positions", "Positions", "list"),
    ("Health", "Portfolio Health", "monitor_heart"),
    ("Research", "Research", "search"),
    ("Guide", "Guide", "menu_book"),
]
```
to:
```python
_MOBILE_TABS = [
    ("Overview", "Overview", "grid_view"),
    ("Positions", "Positions", "list"),
    ("Health", "Portfolio Health", "monitor_heart"),
    ("Income", "Income", "payments"),
    ("Forecast", "Forecast", "trending_up"),
    ("Research", "Research", "search"),
    ("Guide", "Guide", "menu_book"),
]
```

7 tabs at 390px = ~55px each. The tab items have `min-width: 48px` and icon+label stacked vertically — this fits. Labels are short.

- [ ] **Step 2: Fix M13 — allow zoom for accessibility**

At the viewport meta tag (line 737 area, search for `user-scalable=no`), change:
```
maximum-scale=1, user-scalable=no,
```
to just remove those two properties. Keep `viewport-fit=cover`.

The resulting viewport should be:
```
width=device-width, initial-scale=1, viewport-fit=cover
```

- [ ] **Step 3: Fix M3 — move search bar into zone-top**

This requires restructuring the sidebar zone layout in main.py. Currently:
- `sidebar-zone-top` contains title + close button (lines ~509-519)
- `build_sidebar()` renders search + detail fields + positions list outside zone-top (line ~521)
- `sidebar-zone-bottom` contains action buttons + currency (line ~524)

The search bar is built inside `build_sidebar()` in `src/ui/sidebar.py`. The simplest fix is to split `build_sidebar()` into two parts: search (which goes in zone-top) and positions (which goes in zone-positions). However, since the search has a detail container that shows/hides, it's cleaner to just move the search rendering to zone-top by adding a CSS class.

The sidebar on phones has `padding: 0 !important` (theme.py line 438). Use sticky positioning without negative margins:

Add to the phone breakpoint in theme.py:
```css
/* Pin search bar at top of sidebar scroll area */
.q-drawer .sidebar-search {
    position: sticky;
    top: 0;
    z-index: 5;
    background: #161719;
    padding: 8px 12px;
}
```

This keeps the search pinned at the top when the positions list scrolls, without restructuring Python code.

- [ ] **Step 4: Fix m2 — market status font size**

In main.py, search for the market status indicator (the `font-size:10px` span). Change `font-size:10px` to `font-size:11px` in the market status label.

- [ ] **Step 5: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add main.py src/theme.py
git commit -m "fix: add Income+Forecast to mobile tab bar, enable zoom, pin search"
```

---

### Task 4: Positions tab — Responsive controls

Fixes: C3 (price history controls overflow — ticker select + 6-option toggle + FX switch on one row)

**Files:**
- Modify: `src/ui/positions.py:439-456`

- [ ] **Step 1: Wrap controls in a column that stacks on mobile**

At line 439, the controls row uses `ui.row().classes("w-full items-center justify-between")`. Replace this entire controls section to use a wrapper that stacks on small screens:

Change:
```python
with ui.row().classes("w-full items-center justify-between").style("margin-bottom:12px;"):
    ui.html(f'<div class="chart-title">Price History</div>')
    with ui.row().classes("items-center gap-3"):
        ticker_select = ui.select(
            {t: f"{name_map.get(t, t)} ({t})" for t in tickers},
            value=tickers[0],
            label="Stock",
        ).props("dense outlined").style("min-width:180px;font-size:12px;")

        range_options = {"Since Purchase": -1, "3M": 3, "6M": 6, "1Y": 12, "2Y": 24, "Max": None}
        range_toggle = ui.toggle(
            list(range_options.keys()),
            value="Since Purchase",
        ).props("dense size=sm no-caps").style("font-size:11px;")

        fx_switch = ui.switch("Currency-adjusted", value=False).style(
            f"font-size:12px;color:{TEXT_MUTED};"
        )
```

to:
```python
ui.html(f'<div class="chart-title">Price History</div>')
with ui.row().classes("w-full items-center gap-3 flex-wrap"):
    ticker_select = ui.select(
        {t: f"{name_map.get(t, t)} ({t})" for t in tickers},
        value=tickers[0],
        label="Stock",
    ).props("dense outlined").style("min-width:140px;max-width:200px;font-size:12px;flex:1 1 140px;")

    range_options = {"Since Purchase": -1, "3M": 3, "6M": 6, "1Y": 12, "2Y": 24, "Max": None}
    range_toggle = ui.toggle(
        list(range_options.keys()),
        value="Since Purchase",
    ).props("dense size=sm no-caps").style("font-size:11px;")

    fx_switch = ui.switch("Currency-adjusted", value=False).style(
        f"font-size:12px;color:{TEXT_MUTED};"
    )
```

Key changes: `flex-wrap` allows row to wrap, `flex:1 1 140px` on select makes it shrink, removed `justify-between` to let items flow naturally.

- [ ] **Step 2: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('src/ui/positions.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/ui/positions.py
git commit -m "fix: positions price history controls wrap on mobile"
```

---

### Task 5: Forecast tab — Responsive controls and chart sizing

Fixes: C5 (position outlook controls overflow), C6 (QQ select width), M14 (no is_mobile chart sizing)

**Files:**
- Modify: `src/ui/forecast.py:328-339` (position outlook controls)
- Modify: `src/ui/forecast.py:640-644` (QQ select)
- Modify: `src/ui/forecast.py` (add is_mobile import and chart height adjustments)

- [ ] **Step 1: Fix C5 — position outlook controls wrap**

At line 324-339, change:
```python
with ui.row().classes("w-full items-center justify-between"):
    with ui.column().style("gap:2px;"):
        _section_header("Position Outlook")
        ui.html(f'<div style="font-size:12px;color:{TEXT_DIM};">Per-ticker Monte Carlo simulation</div>')
    with ui.row().classes("items-center").style("gap:10px;"):
        ticker_select = ui.select(
            options=ticker_names,
            value=tickers[0],
            label="Position",
        ).style("min-width:200px;")
        horizon_toggle = ui.toggle(
            list(horizon_options.keys()), value="6 months"
        ).props("dense size=sm no-caps")
        lookback_toggle = ui.toggle(
            list(lookback_options.keys()), value="2 years"
        ).props("dense size=sm no-caps")
```

to:
```python
with ui.column().classes("w-full").style("gap:8px;"):
    with ui.row().classes("w-full items-center justify-between"):
        _section_header("Position Outlook")
        ui.html(f'<div style="font-size:12px;color:{TEXT_DIM};">Per-ticker Monte Carlo simulation</div>')
    with ui.row().classes("w-full items-center gap-3 flex-wrap"):
        ticker_select = ui.select(
            options=ticker_names,
            value=tickers[0],
            label="Position",
        ).style("min-width:140px;max-width:220px;flex:1 1 140px;")
        horizon_toggle = ui.toggle(
            list(horizon_options.keys()), value="6 months"
        ).props("dense size=sm no-caps")
        lookback_toggle = ui.toggle(
            list(lookback_options.keys()), value="2 years"
        ).props("dense size=sm no-caps")
```

- [ ] **Step 2: Fix C6 — QQ select width**

At line 640-644, change:
```python
).style("min-width:300px;")
```
to:
```python
).style("min-width:140px;max-width:300px;width:100%;")
```

- [ ] **Step 3: Fix M14 — add is_mobile import and chart height adjustments**

Add `is_mobile` to the imports from `src.charts`:
```python
from src.charts import (
    C_POSITIVE,
    C_NEGATIVE,
    C_AMBER,
    build_fan_chart,
    build_portfolio_histogram,
    build_qq_plot,
    is_mobile,
)
```

Then find calls to `build_fan_chart` and `build_portfolio_histogram` and pass mobile-aware heights. Search for `height=` in the chart builder calls and reduce for mobile. Add at the top of `build_forecast_tab`:
```python
mobile = is_mobile()
chart_h = 280 if mobile else 400
```

Use `chart_h` wherever chart heights are set in the forecast tab.

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('src/ui/forecast.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ui/forecast.py
git commit -m "fix: forecast controls wrap, QQ select width, mobile chart heights"
```

---

### Task 6: Overview tab — Controls wrapping and touch targets

Fixes: M7 (comparison controls overflow), M8 (ticker pills too small), m7 (All/None buttons)

**Files:**
- Modify: `src/ui/overview.py:509-517` (comparison controls)
- Modify: `src/ui/overview.py:538-544` (ticker pill styling)
- Modify: `src/ui/overview.py:557-563` (All/None buttons)

- [ ] **Step 1: Fix M7 — wrap comparison controls**

At line 509, change:
```python
with ui.row().classes("w-full items-start justify-between").style("margin:0;"):
```
to:
```python
with ui.row().classes("w-full items-start justify-between flex-wrap").style("margin:0;gap:8px;"):
```

And at line 512, change:
```python
with ui.row().classes("items-center gap-2"):
```
to:
```python
with ui.row().classes("items-center gap-2 flex-wrap"):
```

- [ ] **Step 2: Fix M8 — enlarge ticker pills for touch**

At lines 538-544, change the pill button styling. Replace:
```python
f"padding:2px 10px;font-size:11px;color:#F1F5F9;"
```
with:
```python
f"padding:6px 12px;font-size:11px;color:#F1F5F9;"
```

And replace:
```python
f"transition:all 0.2s ease;min-height:0;line-height:1.4;"
```
with:
```python
f"transition:all 0.2s ease;min-height:32px;line-height:1.4;"
```

- [ ] **Step 3: Fix m7 — enlarge All/None buttons**

At lines 557-563, change both buttons from:
```python
).style("font-size:10px;color:#94A3B8;min-height:0;padding:0 4px;")
```
to:
```python
).style("font-size:10px;color:#94A3B8;min-height:28px;padding:4px 8px;")
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('src/ui/overview.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ui/overview.py
git commit -m "fix: overview comparison controls wrap, ticker pills touch targets"
```

---

### Task 7: Income tab — KPI grid and chart mobile fixes

Fixes: C4 (inline grid overrides mobile CSS), M9 (income chart no mobile sizing), M10 (dividend calendar)

**Files:**
- Modify: `src/ui/income.py:149-168` (KPI grid)
- Modify: `src/ui/income.py:269-277` (income chart height)
- Modify: `src/ui/income.py` (calendar table class)

- [ ] **Step 1: Fix C4 — remove inline grid-template-columns**

At line 150, change:
```python
<div class="kpi-row" style="grid-template-columns:1fr 1fr 1fr;">
```
to:
```python
<div class="kpi-row">
```

The `.kpi-row` class defaults to 4-col, the 1100px breakpoint makes it 2-col, and the phone breakpoint (after Task 1's fix) makes it 1-col. Three cards will lay out correctly in all tiers without the inline override.

- [ ] **Step 2: Fix M9 — add mobile chart height**

Add `is_mobile` import at top of file:
```python
from src.charts import _apply_default_layout, is_mobile
```

At line 270, change:
```python
_apply_default_layout(
    fig,
    height=380,
```
to:
```python
_apply_default_layout(
    fig,
    height=280 if is_mobile() else 380,
```

- [ ] **Step 3: Add wide-table class to calendar table**

Find the dividend calendar table HTML generation (search for the `<table` tag in the calendar section). Add `class="wide-table"` to the `<table>` element so it gets the `min-width: 600px` rule from Task 2's change. The 13-column calendar genuinely needs forced width.

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('src/ui/income.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ui/income.py
git commit -m "fix: income KPI grid mobile layout, chart height, calendar table class"
```

---

### Task 8: Sidebar — Labels and touch targets

Fixes: M4 (9px form labels), M6 (checkbox touch target), m3 (add button 40→44px)

**Files:**
- Modify: `src/ui/sidebar.py:131-132` (shares label)
- Modify: `src/ui/sidebar.py:138-139` (date label)
- Modify: `src/ui/sidebar.py:155-156` (buy price label)
- Modify: `src/ui/sidebar.py:163-164` (auto-price note)
- Modify: `src/ui/sidebar.py:167-168` (checkbox)
- Modify: `src/ui/sidebar.py:369-371` (edit dialog labels)
- Modify: `src/theme.py:699-701` (sidebar button min-height)

- [ ] **Step 1: Fix M4 — bump form labels from 9px to 11px**

In sidebar.py, find all `font-size:9px` in form labels and change to `font-size:11px`. These appear at lines ~131, ~138, ~155, ~163, ~370, ~378. Use find-and-replace:

Replace all occurrences of:
```
font-size:9px;font-weight:600;color:{TEXT_DIM}
```
with:
```
font-size:11px;font-weight:600;color:{TEXT_DIM}
```

Also change the auto-price note at line 164:
```python
f'<div style="font-size:9px;color:{TEXT_DIM};margin:-2px 0 2px 0;">'
```
to:
```python
f'<div style="font-size:11px;color:{TEXT_DIM};margin:-2px 0 2px 0;">'
```

- [ ] **Step 2: Fix M6 — checkbox touch target**

At line 167, add min-height style:
```python
manual_checkbox = ui.checkbox("Enter price manually", value=False).style(
    f"font-size:10px;color:{TEXT_DIM};"
)
```
to:
```python
manual_checkbox = ui.checkbox("Enter price manually", value=False).style(
    f"font-size:11px;color:{TEXT_DIM};min-height:44px;"
)
```

- [ ] **Step 3: Fix m3 — sidebar button min-height**

In theme.py, at lines 699-701, change:
```css
.sidebar .q-btn, .sidebar .sidebar-btn {
    min-height: 40px !important;
```
to:
```css
.sidebar .q-btn, .sidebar .sidebar-btn {
    min-height: 44px !important;
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('src/ui/sidebar.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ui/sidebar.py src/theme.py
git commit -m "fix: sidebar form labels 11px, checkbox touch target, button 44px"
```

---

### Task 9: Research and Health — Hidden features messaging

Fixes: M11 (research price chart hidden), M12 (health hidden sections), m12 (recent search buttons)

**Files:**
- Modify: `src/ui/research.py:736` (price chart area)
- Modify: `src/ui/research.py:768-771` (recent search buttons)
- Modify: `src/ui/health.py` (after rebalancer/detailed metrics sections)
- Modify: `src/theme.py:558-561` (hidden sections)

- [ ] **Step 1: Fix M11 — show simplified price chart on mobile**

Instead of hiding the price chart entirely on mobile, remove `.price-chart-section` from the hidden list in theme.py. At line 561, delete:
```css
.price-chart-section { display: none !important; }
```

The chart will render on mobile using existing responsive CSS (chart-card stacks full-width). The chart is already inside `.charts-row` which becomes `1fr` on phones.

- [ ] **Step 2: Fix M12 — add desktop-only messages for hidden health sections**

In `src/ui/health.py`, find where `.rebalancer-section` and `.detailed-metrics-section` are rendered. After each section's closing `with` block, add a mobile-visible message:

```python
ui.html(
    '<div class="touch-only" style="padding:12px 16px;font-size:12px;'
    f'color:{TEXT_DIM};background:{BG_PILL};border-radius:8px;'
    f'border:1px solid {BORDER_SUBTLE};text-align:center;">'
    'Rebalancing calculator is available on desktop.'
    '</div>'
)
```

And similarly for detailed metrics:
```python
ui.html(
    '<div class="touch-only" style="padding:12px 16px;font-size:12px;'
    f'color:{TEXT_DIM};background:{BG_PILL};border-radius:8px;'
    f'border:1px solid {BORDER_SUBTLE};text-align:center;">'
    'Detailed analytics table is available on desktop.'
    '</div>'
)
```

- [ ] **Step 3: Fix m12 — recent search button touch targets**

At line 768-771 in research.py, change:
```python
f"padding:2px 8px;min-height:0;"
```
to:
```python
f"padding:6px 10px;min-height:28px;"
```

- [ ] **Step 4: Verify syntax**

Run: `python3 -c "import ast; ast.parse(open('src/ui/research.py').read()); print('OK')"`
Run: `python3 -c "import ast; ast.parse(open('src/ui/health.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ui/research.py src/ui/health.py src/theme.py
git commit -m "fix: show price chart on mobile, desktop-only messages, search buttons"
```

---

### Task 10: Minor fixes — Alerts, Guide, Dialogs

Fixes: m10 (guide markdown table overflow), m11 (alert settings row), m13 (edit dialog min-width)

**Files:**
- Modify: `src/ui/guide.py:21-28` (table overflow)
- Modify: `src/ui/alerts.py:116` (settings row)
- Modify: `src/ui/sidebar.py:365` (edit dialog min-width)

- [ ] **Step 1: Fix m10 — guide markdown table overflow**

In guide.py, wrap the markdown table sections. At line 21, change:
```python
with ui.element("div").classes("chart-card w-full"):
```
to add a style for the markdown table overflow. After the `ui.markdown(...)` call at line 23, the table is rendered inside a markdown widget. Add overflow CSS to the card:
```python
with ui.element("div").classes("chart-card w-full").style("overflow-x:auto;"):
```

- [ ] **Step 2: Fix m11 — alert settings row wrapping**

At line 116 in alerts.py, change:
```python
with ui.row().classes("gap-4 items-center").style("margin-top:4px;"):
```
to:
```python
with ui.row().classes("gap-4 items-center flex-wrap").style("margin-top:4px;"):
```

And change the fixed widths on the number inputs (lines 120, 124) from `width:140px` to `min-width:100px;flex:1 1 120px;max-width:160px;`.

- [ ] **Step 3: Fix m13 — edit dialog responsive min-width**

At line 365 in sidebar.py, change:
```python
with ui.dialog() as dialog, ui.card().style(f"min-width:300px;background:{BG_CARD};"):
```
to:
```python
with ui.dialog() as dialog, ui.card().style(f"min-width:min(300px, 90vw);background:{BG_CARD};"):
```

- [ ] **Step 4: Verify syntax for all changed files**

Run:
```bash
python3 -c "
import ast
for f in ['src/ui/guide.py', 'src/ui/alerts.py', 'src/ui/sidebar.py']:
    ast.parse(open(f).read())
print('OK')
"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add src/ui/guide.py src/ui/alerts.py src/ui/sidebar.py
git commit -m "fix: guide table overflow, alert settings wrap, dialog responsive width"
```

---

### Task 11: Add wide-table class to tables that need it

After Task 2 changed `min-width:600px` to only apply to `.wide-table`, any table that genuinely needs forced width must get the class.

**Files:**
- Modify: `src/ui/positions.py` (positions table)
- Modify: `src/ui/income.py` (dividend calendar, per-position table)
- Modify: `src/ui/health.py` (detailed analytics table)

- [ ] **Step 1: Find all `<table` tags and add wide-table class where needed**

Tables with 6+ columns that genuinely need horizontal scroll should get `class="wide-table"`:
- Positions table (9 columns) — needs it
- Income dividend calendar (13 columns) — needs it
- Health detailed analytics table (13 columns) — needs it

Tables with fewer columns should NOT get it:
- Income per-position table (5 columns) — skip
- Research peer comparison (5 columns) — skip
- Guide markdown tables — skip

Search each file for `<table` and add the class.

- [ ] **Step 2: Verify syntax**

Run:
```bash
python3 -c "
import ast
for f in ['src/ui/positions.py', 'src/ui/income.py', 'src/ui/health.py']:
    ast.parse(open(f).read())
print('OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add src/ui/positions.py src/ui/income.py src/ui/health.py
git commit -m "fix: add wide-table class to tables needing forced min-width"
```

---

### Task 12: Smoke test — Start server and verify on mobile viewport

- [ ] **Step 1: Start the server if not running**

Run: `curl -s http://localhost:8080/healthz` — if it returns 200, skip. Otherwise:
Run: `cd "/Users/joakimhersche/Documents/Python Project/market-dashboard" && python3 main.py &`

- [ ] **Step 2: Run Playwright smoke test at iPhone viewport**

Write and run a quick Playwright script that:
1. Opens http://localhost:8080 at 390x844 viewport with `is_mobile=True, has_touch=True`
2. Loads sample portfolio
3. Screenshots each tab
4. Verifies no horizontal overflow via JS: `document.documentElement.scrollWidth <= document.documentElement.clientWidth`

Save screenshots to `audit_screenshots/mobile-after/`

- [ ] **Step 3: Compare before/after screenshots visually**

Read the new screenshots and compare with the `audit_screenshots/mobile/` originals.

- [ ] **Step 4: Fix any regressions found**

If any fix introduced new issues, address them before the final commit.
