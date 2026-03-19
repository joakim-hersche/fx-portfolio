# Agent-Org Instructions: Fix All UI/UX Audit Issues

Use the agent-org skill to fix every issue documented in `UI_UX_AUDIT.md`. Below is the team structure, file ownership, phasing, and QA plan.

---

## Team Structure (3 teams)

### Team A: Core Architecture (Performance & State)
**Owns:** `main.py`
**Read-only:** all `src/` files
**Fixes:** #1, #2, #3, #5, #6, #8, #9, #11, #14, #15, #20, #21, #22, #23, #25, #26, #30, #31, #39

### Team B: Theme & Visual Design
**Owns:** `src/theme.py`, `src/charts.py`
**Read-only:** `main.py`, other `src/` files
**Fixes:** #4, #10, #12, #13, #17, #18, #19, #32, #33, #34, #35, #36, #37, #38

### Team C: Tab Modules & Data Layer
**Owns:** `src/nicegui_positions.py`, `src/nicegui_risk.py`, `src/nicegui_forecast.py`, `src/fx.py`
**Read-only:** `main.py`, `src/theme.py`, `src/charts.py`
**Fixes:** #5, #7, #16, #24, #27, #28, #29

---

## Phasing

### Phase 1: Critical fixes (blockers & performance)

**Team A — Phase 1:**
1. **#1 Calendar dialog trap** — Fix the date picker so its backdrop doesn't persist. Either use a different Quasar date input approach (inline calendar, or `with_popup=False`), or add JS to dismiss the backdrop on close. This is the #1 priority — the app is unusable after opening the date picker.
2. **#3 Lazy tab rendering** — Refactor `main.py:348-367` so only the active tab renders on page load. Use `@ui.refreshable` or a guard flag per tab. When a tab is first selected, build its content then. Previously rendered tabs should cache their content until invalidated.
3. **#2 Incremental updates** — Replace `ui.navigate.to()` calls in add/remove/import/load/clear handlers with `@ui.refreshable` refresh calls. The sidebar position list, KPI cards, and active tab should refresh independently without a full page reload.

**Team B — Phase 1:**
1. **#4 Text contrast** — Update `src/theme.py`:
   - `TEXT_FAINT`: change from `#475569` to `#8494A7` (achieves ~4.5:1 on #1C1D26)
   - `TEXT_GHOST`: change from `#374151` to `#5A6A7A` (achieves ~3.5:1, acceptable for placeholder text)
   - `TEXT_DIM`: change from `#64748B` to `#7B8BA0` (achieves ~5:1)
   - Verify all `TEXT_FAINT`, `TEXT_GHOST`, `TEXT_DIM` usages still look intentionally dim/subtle but are now readable.
2. **#10 Unify color palettes** — Make `CHART_COLORS` in `src/charts.py` import from `TICKER_PALETTE` in `src/theme.py` (or vice versa). One source of truth.
3. **#13 Chart text contrast** — In `src/charts.py`, change chart font color from `#64748B` to `TEXT_MUTED` (#94A3B8). Increase tick font size from 8.5px to 10px.

**Team C — Phase 1:**
1. **#5 Async positions tab** — Make `build_positions_tab` in `src/nicegui_positions.py` async. Wrap `build_portfolio_df()` and `fetch_company_name()` calls in `await run.io_bound(...)`. Follow the pattern in `build_risk_tab` and `build_forecast_tab`.
2. **#7 FX failure visibility** — In `src/fx.py`, when `get_fx_rate` falls back to 1.0, log a warning and return a flag. The calling code should show `ui.notify("FX rate unavailable for {pair}, showing unconverted values", type="warning")`.
3. **#16 Price chart loading state** — In `src/nicegui_positions.py:_update_chart()`, show a spinner inside the chart container while fetching, then replace with the chart.

### Phase 1 QA:
- `python3 -c "import py_compile; py_compile.compile('main.py', doraise=True)"` on all modified files
- Start the app on port 8081 and verify:
  - App loads without crash
  - Date picker opens and closes without trapping UI
  - Only the active tab renders on load (check timing — should be <5s for Overview)
  - Adding a position does NOT cause full page reload
  - Text labels are visibly readable on dark backgrounds
  - Positions tab doesn't freeze the UI

---

### Phase 2: Major UX fixes

**Team A — Phase 2:**
1. **#6 Loading indicators** — Add spinner notifications to Overview tab data fetching (around `build_portfolio_df` call at line 808 and comparison chart fetch). Match the pattern used in Forecast/Diagnostics.
2. **#8 Mobile sidebar** — Change `breakpoint="0"` to `breakpoint="768"` at `main.py:332-334` so the sidebar collapses to a hamburger on mobile. Verify the mobile CSS in theme.py is no longer dead code.
3. **#9 Dialog consistency** — Apply consistent dark backgrounds to all dialog cards. Use `style=f"background:{BG_CARD};"` on all `ui.card()` elements inside dialogs (About, Remove, Load Sample, Clear All).
4. **#11 Zero shares validation** — Add `if shares <= 0` check in the add-position handler with a warning notification.
5. **#14 Manual price date** — Keep the date field visible when "Enter price manually" is checked. Make it optional (don't require it) but show a small hint: "Optional — helps track dividends and purchase-relative returns."
6. **#15 Import type validation** — Add type checks: `isinstance(lot["shares"], (int, float))`, `lot["shares"] > 0`, same for `buy_price`. Return specific error messages.

**Team B — Phase 2:**
1. **#12 Spacing scale** — Define a spacing scale in theme.py (4/8/12/16/20/24px as CSS custom properties). Replace all hardcoded gap/margin values with the nearest scale value. Remove dead CSS (position-row gap:7px overridden by inline 6px).
2. **#17 Self-host font** — Download Inter font files (woff2 for weights 400, 500, 600, 700 — drop 300 since it's unused) into `static/fonts/`. Update `src/theme.py:50` to use `@font-face` with local files, keeping Google Fonts as fallback.
3. **#18 Legend font sizes** — Standardize all chart legend `font.size` to 10px in `src/charts.py`.
4. **#19 KPI grid breakpoint** — Add `@media (max-width: 1100px)` breakpoint in theme.py that drops `.kpi-row` to 2 columns.
5. **#33 Hardcoded colors** — Replace all inline color literals in theme.py and charts.py with the named tokens. For #E2E8F0 (used for ticker labels), define a new token `TEXT_BRIGHT` or use `TEXT_PRIMARY`.

**Team C — Phase 2:**
1. **#24 ARIA labels** — Add `aria-label` attributes to delete buttons (e.g., "Remove AAPL"), export button, and add position button. Add `scope="col"` to table header cells in positions table HTML.
2. **#27 Debounce chart toggles** — Add a 300ms debounce to comparison chart range/FX toggle handlers in `main.py` (Team A owns main.py, so Team C should report the exact code change needed and Team A applies it). For positions price chart in `src/nicegui_positions.py`, Team C can add debounce directly.
3. **#29 Cache "Since" range** — In the comparison chart handler, use `fetch_price_history_long(ticker, period="max")` and slice the result to the desired start date, instead of calling `yf.Ticker(t).history(start=...)` directly.

### Phase 2 QA:
- Compile-check all modified files
- Start app, load sample portfolio, verify:
  - Loading spinners appear during Overview data fetch
  - Sidebar collapses at <768px viewport
  - All dialogs have dark backgrounds
  - Cannot add position with 0 shares
  - Date field visible in manual price mode
  - Import with `"shares": "banana"` shows error, not crash
  - Spacing is consistent (no visual jumps between sections)
  - Font loads from local files (disable network to Google Fonts to verify)

---

### Phase 3: Minor polish

**Team A — Phase 3:**
1. **#20** — Add Enter-key handler to shares input
2. **#22** — Add "Load Sample Portfolio" button inline in empty state on Overview and Positions tabs
3. **#23** — Add `title` attribute to truncated company names in sidebar
4. **#25** — Add a "Getting Started" card to Overview empty state pointing to the Guide tab
5. **#26** — Make currency change use `@ui.refreshable` instead of page reload (same pattern as #2)
6. **#30** — Hide or grey out preview cards when portfolio is empty
7. **#31** — Add `ui.notify("Report downloaded", type="positive")` after `ui.download()` in Excel export
8. **#39** — Log a warning when using the fallback encryption secret
9. **#21** — Add undo toast for position removal (soft delete with 5-second undo window)

**Team B — Phase 3:**
1. **#32** — Reduce font sizes to a consistent scale: 10/12/14/16/20/24px. Eliminate 9px, 9.5px, 11px, 13px sizes.
2. **#34** — Replace `ui.separator()` in Guide tab with the `content-divider` class
3. **#35** — Standardize all `ui.switch` font size to 11px with `color: TEXT_MUTED`
4. **#36** — Standardize all `ui.select` to use `dense outlined` props with consistent min-width
5. **#37** — Define standard chart margins in charts.py and apply to all charts
6. **#38** — Add Quasar notification CSS overrides to theme.py for dark theme consistency

**Team C — Phase 3:**
1. **#28** — Document that cache is in-memory only (add a comment in `src/cache.py`). Consider adding a startup log message noting cache cold start.

### Phase 3 QA:
- Full smoke test: load sample, click every tab, add position, remove position, change currency, export Excel
- Verify all minor issues are resolved
- Run the existing `test_integration.py` to confirm nothing is broken

---

## Cross-Team Coordination Rules

1. **main.py is owned by Team A only.** If Team B or Team C needs a change in main.py, they report the exact change needed (with line numbers and code) and Team A applies it.
2. **After each phase, ALL teams must stop and wait for QA.** No team starts Phase N+1 until Phase N passes QA for all teams.
3. **No new dependencies.** Do not add packages to requirements.txt. Work with what's installed.
4. **No scope creep.** Fix exactly what's listed. Don't refactor surrounding code, add features, or "improve" things not in the audit.
5. **Test with real data.** After loading the sample portfolio (9 positions), verify the fix works with actual API data, not just empty state.
