# UI/UX Audit Report — Market Dashboard

## CRITICAL Issues (5)

### 1. Calendar picker dialog traps the UI
**File:** `main.py` (date input around line 441-450)
The Quasar date picker opens a dialog with a backdrop overlay (`q-dialog__backdrop`). After the calendar closes, the backdrop remains in the DOM and intercepts all pointer events on the sidebar. The user cannot click any sidebar element after opening the calendar. The only recovery is a page refresh.

### 2. Full page reload on every portfolio mutation
**Files:** `main.py:576`, `main.py:656`, `main.py:690`, `main.py:739`, `main.py:764`
Every add/remove/import/load/clear calls `ui.navigate.to()`, triggering a full server-side page rebuild. With 8 positions, this means 30+ sequential yfinance API calls and 10-30 seconds of waiting after adding a single stock.

**Fix:** Use `@ui.refreshable` on individual tab content builders. On mutation, only refresh the visible tab and lazily invalidate others.

### 3. All tabs eagerly rendered on page load
**File:** `main.py:348-367`
Overview, Positions, Risk, Forecast, and Diagnostics all build sequentially with `await` on every page load. Risk fetches 1-year history for every ticker + SPY + fundamentals. Forecast runs Monte Carlo simulations. Initial load with 8 positions takes 30-60+ seconds.

**Fix:** Only render the active tab on initial load. Use lazy tab panels that build content when first selected.

### 4. Text contrast failures (WCAG AA)
**File:** `src/theme.py`
- `TEXT_FAINT` (#475569) on `BG_CARD` (#1C1D26) = ~2.6:1 ratio (needs 4.5:1). Used for: KPI labels (line 145), chart titles (line 171), sidebar section headers (line 72), table headers (line 192), metric labels (line 232).
- `TEXT_GHOST` (#374151) on dark backgrounds = ~1.7:1. Used for input placeholders (line 84). Essentially invisible.
- `TEXT_DIM` (#64748B) on `BG_CARD` = ~3.9:1. Fails for 10-12px body text. Used for form labels (line 105), KPI sub-text (line 150), metric sub-text (line 236), pill text (line 264).

**Fix:** Raise `TEXT_FAINT` to at least `#8494A7` (~4.5:1 on #1C1D26). Raise `TEXT_GHOST` to at least `#5A6A7A`. Raise `TEXT_DIM` to at least `#7B8BA0`.

### 5. Synchronous blocking calls freeze the event loop
**File:** `src/nicegui_positions.py:447`, `src/nicegui_positions.py:341`
`build_positions_tab` is sync (not async) and calls `build_portfolio_df()` + `fetch_company_name()` for every ticker, blocking NiceGUI's event loop. This freezes the UI for all connected clients.

**Fix:** Make `build_positions_tab` async and wrap blocking calls in `await run.io_bound(...)`, matching the pattern already used in `build_risk_tab` and `build_forecast_tab`.

---

## MAJOR Issues (14)

### 6. No loading indicators on Overview or Positions tabs
**Files:** `main.py:773-964` (overview), `src/nicegui_positions.py:426-491` (positions)
Risk and Forecast show spinner notifications during data loading. Overview and Positions show nothing.

**Fix:** Add spinner notifications around all data-fetching operations, matching the Forecast/Diagnostics pattern.

### 7. Silent FX rate failure defaults to 1.0
**File:** `src/fx.py:44-46`
When FX lookup fails, `get_fx_rate` silently returns 1.0. A GBP portfolio viewing USD stocks shows prices as if 1 GBP = 1 USD with no indication.

**Fix:** Return a tuple `(rate, success)` or surface a warning via `ui.notify()` when fallback is used.

### 8. Sidebar never collapses on mobile
**File:** `main.py:332-334`
`breakpoint="0"` means the 220px sidebar is always visible. On a 320px phone, content gets 100px. The mobile CSS override in `src/theme.py:299` is dead code because the drawer never enters collapsible mode.

**Fix:** Set a reasonable breakpoint (e.g., 768) so the sidebar collapses into a hamburger menu on small screens.

### 9. Dialog backgrounds inconsistent
**File:** `main.py:281` (About uses #1E293B), `main.py:641, 724, 752` (others use Quasar defaults)
The About dialog manually sets a dark background while the other three rely on Quasar's dark mode propagation, creating visual inconsistency.

**Fix:** Apply a consistent dark background class or inline style to all dialog cards using `BG_CARD` token.

### 10. Duplicate/divergent color palettes
**Files:** `src/charts.py:9` (`CHART_COLORS` starts #1D4ED8) vs `src/theme.py:40` (`TICKER_PALETTE` starts #3B82F6)
Same ticker can have different colors in sidebar dots vs chart lines.

**Fix:** Use a single source of truth. Either import `TICKER_PALETTE` from theme in charts.py, or vice versa.

### 11. Zero shares accepted as valid input
**File:** `main.py:490`
The shares input accepts 0, creating a $0 position.

**Fix:** Add validation `if shares <= 0: ui.notify("Shares must be greater than 0", type="warning"); return`.

### 12. Inconsistent spacing scale
**Files:** `src/theme.py` throughout
Gaps: 6px, 7px, 8px, 10px, 12px, 14px with no system. Position row CSS defines `gap:7px` but inline style overrides to `6px` at `main.py:607`, making the CSS dead code.

**Fix:** Define a spacing scale (e.g., 4/8/12/16/20/24px) and apply consistently. Remove dead CSS.

### 13. Chart text contrast too low
**Files:** `src/charts.py:28` (8.5px tick labels), `src/charts.py:34` (#64748B font color)
Chart axis labels use TEXT_DIM at 8.5px -- barely readable even with good contrast.

**Fix:** Increase chart tick font to 10px minimum. Use `TEXT_MUTED` (#94A3B8) instead of TEXT_DIM for chart text.

### 14. Manual price mode silently drops purchase date
**File:** `main.py:516-518`
When using manual price, the date field is hidden, so `purchase_date` is null. This breaks dividend calculations, "Since purchase" range, and Position Outlook fan charts.

**Fix:** Keep date field visible in manual mode (optional but encouraged), or show a warning before submit.

### 15. Import validation accepts garbage types
**File:** `main.py:664-692`
Validates key existence but not types. `"shares": "banana"` passes validation and crashes later.

**Fix:** Validate types: shares is numeric & positive, buy_price is numeric & positive, purchase_date is string or None.

### 16. No loading state on price chart ticker/range change
**File:** `src/nicegui_positions.py:329-417`
Chart area is blank or stale during fetch with no spinner.

**Fix:** Show inline spinner in chart container while fetching.

### 17. Font loaded via CDN with no fallback
**File:** `src/theme.py:50`
Inter loaded from Google Fonts via `@import`. Behind corporate firewalls, the app blocks rendering.

**Fix:** Self-host the Inter font files in `static/` and load from there, keeping the CDN as fallback.

### 18. Chart legend font size mismatch
**Files:** `src/charts.py:211` (12px) vs `src/charts.py:278` (9px)
Legend readability varies between charts for no reason.

**Fix:** Standardize all chart legend font sizes to 10px or 11px.

### 19. KPI grid breaks at medium widths
**File:** `src/theme.py:138`
4-column grid with 220px sidebar leaves ~780px between 1024-1100px viewports. No breakpoint for this range.

**Fix:** Add a breakpoint at ~1100px that drops to 2 columns.

---

## MINOR Issues (20)

### 20. No Enter-key handler on shares input
Only the date input has `keydown.enter`. Pressing Enter in shares does nothing.

### 21. No undo for position removal
Destructive with no recovery. Consider a "soft delete" with undo toast.

### 22. Empty state doesn't offer "Load Sample" inline
User must find the sidebar button. Add an inline CTA in the empty state.

### 23. Company names truncated at 100px with no tooltip
**File:** `main.py:617`
Add a `title` attribute or NiceGUI tooltip for the full name on hover.

### 24. No ARIA labels on interactive elements
Raw `ui.html()` everywhere with no semantic markup. Add `aria-label` to buttons, `scope="col"` to table headers.

### 25. Guide tab last in order
New users won't find help. Show Guide content in empty state, or reorder tabs.

### 26. Currency change triggers full page reload
**File:** `main.py:377-381`
Same full-rebuild issue as #2.

### 27. No debouncing on comparison chart range toggles
Rapid clicks queue multiple API calls with no cancellation.

### 28. Cache is process-local, non-persistent
Server restart = cold start for all users. TTLCache only.

### 29. "Since" comparison range bypasses cache
**File:** `main.py:1022-1024`
Calls `yf.Ticker(t).history(start=...)` directly instead of using cached fetch.

### 30. Preview cards shown when portfolio is empty
Clicking them is a dead end. Disable or hide when empty.

### 31. No feedback after Excel export completes
Add `ui.notify()` confirmation after `ui.download()`.

### 32. 13 distinct font sizes with no type scale
Ranges from 9px to 28px. Define a consistent scale.

### 33. Hardcoded color literals scattered throughout
`#E2E8F0`, `#64748B` inline instead of theme tokens. Refactor to use tokens.

### 34. `ui.separator()` in Guide tab uses Quasar defaults
Inconsistent with `content-divider` class used everywhere else.

### 35. Switch/toggle components styled inconsistently
Different font sizes, some set color, some don't across tabs.

### 36. Select dropdowns styled inconsistently across tabs
Some `outlined`, some not, different min-widths.

### 37. Chart margins not standardized
Left margins range from 0 to 50px across charts.

### 38. Quasar notification styling not overridden for dark theme
May clash with dark theme palette.

### 39. Encryption key deterministic from static salt
**File:** `main.py:58-65`
Fallback secret provides no real protection. Log a warning when using it.
