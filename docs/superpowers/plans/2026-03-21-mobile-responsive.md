# Mobile-Responsive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Market Dashboard mobile-friendly with a purpose-built touch experience for iPhone and iPad, hiding desktop-only features and adding a native-feeling bottom tab bar.

**Architecture:** CSS-first approach using existing `@media (max-width: 767px)` breakpoint. Structurally different mobile layouts (bottom tab bar, position cards, overview hero card) use dual-render with `mobile-only` / `desktop-only` CSS classes. Tab switching wired via `ui.run_javascript` to programmatically click hidden top tabs.

**Tech Stack:** NiceGUI 3.8.0, Quasar/Vue 3, CSS media queries, inline SVG icons

**Spec:** `docs/superpowers/specs/2026-03-21-mobile-responsive-design.md`

---

## File Structure

| File | Changes |
|------|---------|
| `src/theme.py` | Add mobile CSS: bottom tab bar, mobile-only/desktop-only utilities, position cards, hide classes, Plotly modebar hide, body bottom padding |
| `main.py` | Render bottom tab bar HTML (hidden on desktop), mobile tab-restore redirect for hidden tabs |
| `src/ui/overview.py` | Add mobile hero card (desktop-only wrapper on KPI grid) |
| `src/ui/positions.py` | Add card-based position renderer (desktop-only wrapper on table) |
| `src/ui/health.py` | Wrap rebalancer + detailed metrics in hideable containers |
| `src/ui/research.py` | Add class to fundamentals grid, wrap price chart in hideable container, mobile class on charts-row |

---

### Task 1: Mobile CSS Foundation in theme.py

**Files:**
- Modify: `src/theme.py` (inside GLOBAL_CSS string, before closing `</style>` tag)

- [ ] **Step 1.1: Read the current mobile CSS block**

Read `src/theme.py` lines 360-440 to see existing mobile breakpoints.

- [ ] **Step 1.2: Add mobile utility classes and bottom tab bar CSS**

Add the following CSS inside the existing `@media (max-width: 767px)` block in `src/theme.py`, and add new rules outside the block for the bottom tab bar base styles:

```css
/* ── Mobile utility classes ── */
.mobile-only { display: none !important; }
.desktop-only { display: block !important; }

/* ── Bottom tab bar (base — hidden on desktop) ── */
.mobile-tab-bar {
  display: none;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 2000;
  background: #161719;
  border-top: 1px solid rgba(255,255,255,0.07);
  justify-content: space-around;
  padding: 8px 0 env(safe-area-inset-bottom, 20px) 0;
}
.mobile-tab-bar .tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 48px;
  gap: 3px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.mobile-tab-bar .tab-item svg { stroke: #64748B; }
.mobile-tab-bar .tab-item .tab-label { font-size: 9px; color: #64748B; }
.mobile-tab-bar .tab-item.active svg { stroke: #3B82F6; }
.mobile-tab-bar .tab-item.active .tab-label { color: #3B82F6; font-weight: 600; }
```

Then inside the existing `@media (max-width: 767px)` block, add:

```css
  /* Show mobile, hide desktop */
  .mobile-only { display: block !important; }
  .desktop-only { display: none !important; }

  /* Bottom tab bar visible */
  .mobile-tab-bar { display: flex !important; }

  /* Hide top tab bar */
  .tab-bar-wrapper { display: none !important; }

  /* Body padding for fixed bottom bar */
  .q-page, .nicegui-content { padding-bottom: 72px !important; }

  /* Hide sections on mobile */
  .rebalancer-section { display: none !important; }
  .detailed-metrics-section { display: none !important; }
  .price-chart-section { display: none !important; }

  /* Positions card list */
  .position-cards { display: flex !important; flex-direction: column; gap: 6px; }
  .table-wrap { display: none !important; }

  /* Research fundamentals 2-col */
  .fundamentals-grid { grid-template-columns: 1fr 1fr !important; }

  /* Research charts-row stack on mobile */
  .charts-row { grid-template-columns: 1fr !important; }

  /* Plotly modebar hidden on touch */
  .modebar-container { display: none !important; }
```

- [ ] **Step 1.3: Verify theme.py is syntactically valid**

Run: `python -c "from src.theme import GLOBAL_CSS; print('OK', len(GLOBAL_CSS))"`
Expected: `OK` followed by a number (no syntax errors).

- [ ] **Step 1.4: Commit**

```bash
git add src/theme.py
git commit -m "style: add mobile CSS foundation — tab bar, utilities, hide classes"
```

---

### Task 2: Bottom Tab Bar in main.py

**Files:**
- Modify: `main.py` (lines ~206-209 for tab redirect, lines ~427-431 for tab bar insertion, after line ~491 for bottom bar HTML)

- [ ] **Step 2.1: Add mobile tab redirect for hidden tabs**

In `main.py`, after line 209, modify the tab restoration logic:

```python
# ── Read query params for tab restoration ─────────────
initial_tab_name = request.query_params.get("tab", "Overview")
if initial_tab_name not in _TAB_NAMES:
    initial_tab_name = "Overview"
# On mobile, Forecast and Income are hidden — fall back to Overview.
# (Actual hiding is CSS-only; this handles direct URL access.)
_MOBILE_HIDDEN_TABS = {"Forecast", "Income"}
```

No Python-side redirect needed — CSS handles hiding. But we store the set for the bottom bar builder.

- [ ] **Step 2.2: Render bottom tab bar HTML after the tab panels**

After the `tabs.on_value_change(_on_tab_change)` line (~491), and before the disclaimer footer (~493), insert the bottom tab bar:

```python
# ── Mobile bottom tab bar ──────────────────────────────
_MOBILE_TABS = [
    ("Overview", "Overview", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>'),
    ("Positions", "Positions", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>'),
    ("Health", "Portfolio Health", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>'),
    ("Research", "Research", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>'),
    ("Guide", "Guide", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'),
]
active_label = {
    "Overview": "Overview",
    "Positions": "Positions",
    "Portfolio Health": "Health",
    "Research": "Research",
    "Guide": "Guide",
}.get(initial_tab_name, "Overview")

tab_items_html = ""
for label, tab_name, icon in _MOBILE_TABS:
    active_cls = " active" if label == active_label else ""
    tab_items_html += (
        f'<div class="tab-item{active_cls}" data-tab="{tab_name}" '
        f'onclick="switchMobileTab(this, \'{tab_name}\')">'
        f'{icon}'
        f'<span class="tab-label">{label}</span>'
        f'</div>'
    )

ui.html(
    f'<div class="mobile-tab-bar" id="mobile-tab-bar">'
    f'{tab_items_html}'
    f'</div>'
)
```

- [ ] **Step 2.3: Add JavaScript for tab switching**

Add a `ui.add_head_html` call (near the existing `ui.add_head_html(GLOBAL_CSS)` line) with the tab-switching JS:

```python
ui.add_head_html("""<script>
function switchMobileTab(el, tabName) {
  // Update active state
  document.querySelectorAll('.mobile-tab-bar .tab-item').forEach(
    t => t.classList.remove('active')
  );
  el.classList.add('active');
  // Click the hidden top tab
  const tabs = document.querySelectorAll('.q-tab');
  for (const tab of tabs) {
    if (tab.textContent.trim() === tabName) {
      tab.click();
      break;
    }
  }
}
</script>""")
```

- [ ] **Step 2.4: Verify app starts without errors**

Run: `python -c "import main; print('imports OK')"`
Expected: `imports OK` (no syntax errors). Full app test requires `python main.py` and visiting localhost:8080.

- [ ] **Step 2.5: Commit**

```bash
git add main.py
git commit -m "feat: add mobile bottom tab bar with JS-based tab switching"
```

---

### Task 3: Overview Mobile Hero Card

**Files:**
- Modify: `src/ui/overview.py` (lines ~243-246, KPI grid section)

- [ ] **Step 3.1: Read overview.py lines 195-255**

Understand the KPI card variables (`card_1` through `card_5`) and the grid injection.

- [ ] **Step 3.2: Wrap existing KPI grid in desktop-only and add mobile hero card**

Replace the KPI grid `ui.html(...)` call at lines 243-246 with:

```python
# Desktop: 5-column KPI grid
ui.html(
    f'<div class="kpi-row desktop-only" style="grid-template-columns:1fr 1fr 1fr 1fr 1fr;">'
    f'{card_1}{card_2}{card_3}{card_4}{card_5}</div>'
).classes("w-full")

# Mobile: consolidated hero card
sign_pnl_m = "+" if daily_pnl >= 0 else ""
sign_ret_m = "+" if total_return >= 0 else ""
pnl_color_m = "#16A34A" if daily_pnl >= 0 else "#DC2626"
ret_color_m = "#16A34A" if total_return >= 0 else "#DC2626"
ret_bg_m = "rgba(22,163,74,0.15)" if total_return >= 0 else "rgba(220,38,38,0.15)"
pnl_bg_m = "rgba(22,163,74,0.15)" if daily_pnl >= 0 else "rgba(220,38,38,0.15)"
arrow_ret = "\u25b2" if total_return >= 0 else "\u25bc"

ui.html(f'''<div class="mobile-only" style="margin-bottom:16px;">
  <div style="background:{BG_CARD};border-radius:10px;padding:16px;
    border:1px solid {BORDER};">
    <div style="font-size:10px;color:{TEXT_MUTED};text-transform:uppercase;
      letter-spacing:0.08em;">Portfolio Value</div>
    <div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY};margin-top:4px;">
      {val_int}<span style="font-size:16px;color:{TEXT_DIM};">.{val_dec}</span></div>
    <div style="display:flex;align-items:center;gap:8px;margin-top:6px;">
      <span style="font-size:12px;color:{pnl_color_m};font-weight:600;">
        {sign_pnl_m}{currency_symbol}{daily_pnl:,.2f}</span>
      <span style="font-size:10px;background:{pnl_bg_m};color:{pnl_color_m};
        padding:2px 6px;border-radius:4px;font-weight:600;">
        {sign_pnl_m}{daily_pnl_pct:,.2f}%</span>
      <span style="font-size:10px;color:{TEXT_DIM};">today</span>
    </div>
    <div style="border-top:1px solid {BORDER_SUBTLE};margin:12px 0;"></div>
    <div style="display:flex;justify-content:space-between;">
      <div>
        <div style="font-size:9px;color:{TEXT_DIM};text-transform:uppercase;
          letter-spacing:0.06em;">Total Return</div>
        <div style="font-size:14px;font-weight:600;color:{ret_color_m};margin-top:2px;">
          {sign_ret_m}{currency_symbol}{total_return:,.2f}
          <span style="font-size:10px;opacity:0.7;">
            {sign_ret_m}{total_ret_pct:,.2f}%</span></div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:9px;color:{TEXT_DIM};text-transform:uppercase;
          letter-spacing:0.06em;">Positions</div>
        <div style="font-size:14px;font-weight:600;color:{TEXT_PRIMARY};margin-top:2px;">
          {n_positions} <span style="font-size:10px;color:{TEXT_DIM};">stocks</span></div>
      </div>
    </div>
  </div>
  <div style="display:flex;justify-content:space-between;padding:0 4px;margin-top:8px;">
    <div style="font-size:10px;color:{TEXT_DIM};">Contributed:
      <span style="color:{TEXT_MUTED};font-weight:500;">{currency_symbol}{total_contributed:,.2f}</span></div>
  </div>
</div>''')

# Note: the health score is shown on the Health tab itself — no need to
# duplicate it here since the data isn't available in overview.py without
# adding a cross-tab dependency. The spec's inline "Health: 72/100" was
# aspirational but not worth the coupling..classes("w-full")
```

- [ ] **Step 3.3: Add BORDER_SUBTLE import if not already imported**

Check if `BORDER_SUBTLE` is imported in `overview.py`. If not, add it to the import from `src.theme`.

- [ ] **Step 3.4: Verify no syntax errors**

Run: `python -c "from src.ui.overview import build_overview_tab; print('OK')"`

- [ ] **Step 3.5: Commit**

```bash
git add src/ui/overview.py
git commit -m "feat: add mobile hero card for overview, desktop KPI grid unchanged"
```

---

### Task 4: Positions Mobile Cards

**Files:**
- Modify: `src/ui/positions.py` (lines ~64-325, the `_build_positions_table` function area)

- [ ] **Step 4.1: Read positions.py fully to understand the table builder**

Read `src/ui/positions.py` lines 64-330 to understand the table rendering flow, display_df construction, and the variables available.

- [ ] **Step 4.2: Add mobile card renderer function**

Add a new function `_build_mobile_position_cards` after the existing `_build_positions_table` function. This renders the card-based layout wrapped in `position-cards mobile-only`:

```python
def _build_mobile_position_cards(
    df: pd.DataFrame,
    name_map: dict[str, str],
    currency_symbol: str,
    portfolio_color_map: dict[str, str] | None = None,
) -> None:
    """Render positions as mobile-friendly cards (hidden on desktop via CSS)."""
    # Aggregate multi-lot positions
    agg_rows = []
    for ticker, group in df.groupby("Ticker", sort=False):
        total_val = group["Total Value"].sum()
        total_cost = (group["Buy Price"] * group["Shares"]).sum()
        total_shares = group["Shares"].sum()
        total_divs = group["Dividends"].sum()
        daily = group["Daily P&L"].sum()
        ret_pct = (
            (total_val + total_divs - total_cost) / total_cost * 100
            if total_cost else 0.0
        )
        weight = group["Weight (%)"].sum()
        agg_rows.append({
            "Ticker": ticker,
            "Company": name_map.get(ticker, ticker),
            "Shares": total_shares,
            "Total Value": total_val,
            "Daily P&L": daily,
            "Return (%)": ret_pct,
            "Weight (%)": weight,
        })
    agg_rows.sort(key=lambda r: r["Weight (%)"], reverse=True)

    cards_html = f'<div style="font-size:11px;color:#94A3B8;margin-bottom:12px;">{len(agg_rows)} positions</div>'

    for r in agg_rows:
        ticker = r["Ticker"]
        dot_color = (portfolio_color_map or {}).get(ticker, "#64748B")
        val_str = f"{currency_symbol}{r['Total Value']:,.0f}"
        ret = r["Return (%)"]
        ret_color = "#16A34A" if ret >= 0 else "#DC2626"
        ret_str = f"{'+' if ret >= 0 else ''}{ret:.1f}%"
        daily = r["Daily P&L"]
        daily_color = "#16A34A" if daily >= 0 else "#DC2626"
        daily_str = f"{'+' if daily >= 0 else ''}{currency_symbol}{daily:,.0f} today"
        shares = r["Shares"]
        shares_str = f"{int(shares):,}" if shares == int(shares) else f"{shares:g}"
        weight_str = f"{r['Weight (%)']:.1f}%"

        cards_html += f'''<div style="background:#1C1D26;border-radius:8px;padding:12px;
          margin-bottom:6px;border:1px solid rgba(255,255,255,0.06);">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div style="display:flex;align-items:center;gap:8px;">
              <div style="width:6px;height:6px;border-radius:50%;background:{dot_color};
                flex-shrink:0;margin-top:2px;"></div>
              <div>
                <div style="font-size:13px;font-weight:700;color:#F1F5F9;">{ticker}</div>
                <div style="font-size:10px;color:#64748B;overflow:hidden;text-overflow:ellipsis;
                  white-space:nowrap;max-width:160px;">{r["Company"]}</div>
              </div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:13px;font-weight:600;color:#F1F5F9;">{val_str}</div>
              <div style="font-size:10px;color:{ret_color};font-weight:500;">{ret_str}</div>
            </div>
          </div>
          <div style="display:flex;justify-content:space-between;margin-top:8px;padding-top:8px;
            border-top:1px solid rgba(255,255,255,0.04);">
            <div style="font-size:10px;color:#64748B;">{shares_str} shares \u00b7 {weight_str}</div>
            <div style="font-size:10px;color:{daily_color};">{daily_str}</div>
          </div>
        </div>'''

    ui.html(f'<div class="position-cards mobile-only">{cards_html}</div>').classes("w-full")
```

- [ ] **Step 4.3: Add desktop-only class to the table wrapper**

In `_build_positions_table`, find the HTML table injection at line ~322:

```python
html = f'<div style="overflow-x:auto;"><div class="table-wrap"><table>{header}{tbody}</table></div></div>'
```

Change to:

```python
html = f'<div class="desktop-only" style="overflow-x:auto;"><div class="table-wrap"><table>{header}{tbody}</table></div></div>'
```

- [ ] **Step 4.4: Call the mobile card renderer from build_positions_tab**

In `build_positions_tab`, after the `_build_positions_table(...)` call at line ~587, add:

```python
_build_mobile_position_cards(
    df, name_map, currency_symbol,
    portfolio_color_map=portfolio_color_map,
)
```

Note: the DataFrame variable is `df` (line 536/546), not `portfolio_df`.

- [ ] **Step 4.5: Verify no syntax errors**

Run: `python -c "from src.ui.positions import build_positions_tab; print('OK')"`

- [ ] **Step 4.6: Commit**

```bash
git add src/ui/positions.py
git commit -m "feat: add mobile position cards, hide table on small screens"
```

---

### Task 5: Health Tab Mobile Lite

**Files:**
- Modify: `src/ui/health.py` (lines ~1280-1289)

- [ ] **Step 5.1: Read health.py lines 1275-1293**

Understand the section ordering: findings → sector breakdown → detailed metrics → rebalancer → news.

- [ ] **Step 5.2: Wrap detailed metrics in hideable container**

At line ~1280, change:

```python
        # Collapsible detailed metrics
        with ui.expansion("Detailed Metrics").classes("w-full"):
```

To:

```python
        # Collapsible detailed metrics (hidden on mobile)
        with ui.element("div").classes("detailed-metrics-section"):
            with ui.expansion("Detailed Metrics").classes("w-full"):
```

Make sure the indentation of the contents (lines 1282-1287) is adjusted to be inside both `with` blocks.

- [ ] **Step 5.3: Wrap rebalancer in hideable container**

At line ~1289, change:

```python
        _render_rebalancing_calculator(fund_rows, portfolio_df, currency_symbol)
```

To:

```python
        with ui.element("div").classes("rebalancer-section"):
            _render_rebalancing_calculator(fund_rows, portfolio_df, currency_symbol)
```

- [ ] **Step 5.4: Verify no syntax errors**

Run: `python -c "from src.ui.health import build_health_tab; print('OK')"`

- [ ] **Step 5.5: Commit**

```bash
git add src/ui/health.py
git commit -m "feat: wrap rebalancer and metrics in mobile-hideable containers"
```

---

### Task 6: Research Tab Mobile Adaptations

**Files:**
- Modify: `src/ui/research.py` (lines ~191-192 for fundamentals grid, ~736 for price chart)

- [ ] **Step 6.1: Read research.py lines 191-192 and 720-742**

Understand the fundamentals grid element and the price chart call.

- [ ] **Step 6.2: Add class to fundamentals grid**

At line ~191, change:

```python
    with ui.element("div").style(
        "display:grid;grid-template-columns:repeat(3,1fr);gap:var(--grid-gap);width:100%;"
    ):
```

To:

```python
    with ui.element("div").classes("fundamentals-grid").style(
        "display:grid;grid-template-columns:repeat(3,1fr);gap:var(--grid-gap);width:100%;"
    ):
```

The CSS in theme.py will override `grid-template-columns` to `1fr 1fr` on mobile.

- [ ] **Step 6.3: Wrap price chart in hideable container**

At line ~736, change:

```python
            # Price chart
            _render_price_chart(ticker, hist)
```

To:

```python
            # Price chart (hidden on mobile)
            with ui.element("div").classes("price-chart-section"):
                _render_price_chart(ticker, hist)
```

- [ ] **Step 6.4: Verify no syntax errors**

Run: `python -c "from src.ui.research import build_research_tab; print('OK')"`

- [ ] **Step 6.5: Commit**

```bash
git add src/ui/research.py
git commit -m "feat: research tab mobile — 2-col fundamentals, hidden price chart"
```

---

### Task 7: Manual Visual Testing

**Files:** None (testing only)

- [ ] **Step 7.1: Start the app**

Run: `python main.py`

Open in browser at `http://localhost:8080`

- [ ] **Step 7.2: Test desktop — no regressions**

Verify at full desktop width (1200px+):
- All 7 tabs visible in top tab bar
- KPI grid shows 5 columns
- Positions table renders normally
- Health tab shows rebalancer and detailed metrics
- Research tab shows 3-column fundamentals and price chart
- Bottom tab bar is NOT visible

- [ ] **Step 7.3: Test mobile — Chrome DevTools device mode**

Open Chrome DevTools → Toggle Device Toolbar → Select iPhone 14 (390x844):
- Bottom tab bar visible with 5 icons
- Top tab bar hidden
- Overview: hero card visible, KPI grid hidden
- Positions: card list visible, table hidden
- Health: score + findings + sectors + news visible; rebalancer + detailed metrics hidden
- Research: 2-column fundamentals grid; price chart hidden; peer table scrolls horizontally
- Forecast/Income tabs: not accessible from bottom bar

- [ ] **Step 7.4: Test iPad — tablet breakpoint**

Switch to iPad (810x1080) in DevTools:
- If width > 767px: desktop layout (top tabs, full table, etc.)
- If width <= 767px (portrait narrow iPads): mobile layout

- [ ] **Step 7.5: Test tab switching**

Click each bottom tab bar icon. Verify:
- Content switches correctly
- Active icon turns blue, others gray
- URL updates in address bar

- [ ] **Step 7.6: Test URL with hidden tab**

Navigate to `http://localhost:8080/?tab=Forecast` with device mode on:
- Tab should still load (it's in the DOM), but bottom bar shows Overview as active
- Forecast panel content is hidden via CSS

- [ ] **Step 7.7: Final commit**

If any fixups were needed during testing, commit them:

```bash
git add src/theme.py main.py src/ui/overview.py src/ui/positions.py src/ui/health.py src/ui/research.py
git commit -m "fix: mobile testing adjustments"
```
