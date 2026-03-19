# Market Dashboard — Feature Expansion & Infrastructure Spec

**Date:** 2026-03-19
**Goal:** Ship all remaining backlog items (P1–P3) plus two new features (Income tab, Contribution tracking), then prepare the codebase for deployment.

---

## Context

Four investor personas (beginner, active trader, dividend/retirement, European passive) stress-tested the dashboard. Cross-referencing their feedback against the existing Obsidian backlog and commercialisation plan produced a clear priority list. This spec covers everything needed to reach a launchable product.

**Existing specs to complete first:**
- `2026-03-19-risk-tab-redesign.md` — unified expandable table + HTML correlation matrix (includes Performance Attribution)

---

## 1. Income Tab (new — 7th tab)

### Purpose

Answer "how much income does my portfolio generate, and is it growing?" — the single biggest gap identified by 3 of 4 investor personas.

### File

New: `src/ui/income.py`

### Wiring

1. Add `"Income"` to `_TAB_NAMES` in `main.py` (after "Risk & Analytics", before "Forecast")
2. Add import: `from src.ui.income import build_income_tab`
3. Add case to `_build_tab()`:
   ```python
   elif name == "Income":
       await build_income_tab(portfolio, currency, portfolio_color_map)
   ```

### Layout (top to bottom)

#### 1.1 Income KPI Row (3 cards)

| Card | Value | Calculation |
|---|---|---|
| Trailing 12-Month Income | Sum of all dividends received in last 365 days, base currency | Reuse `_dividends_in_base_currency()` with `start=today-365d` per lot |
| Projected Annual Income | Forward estimate: current shares × most recent annual dividend per share | `yf.Ticker(t).info["dividendRate"]` (annual, native currency) × shares × current FX rate |
| Portfolio Yield | Projected annual income / total portfolio value × 100 | Derived from the two values above |

Use existing `kpi-card` CSS class. Green/red trend arrows not applicable here (no prior-period comparison on first load).

#### 1.2 Income Growth Chart (centrepiece)

- **Type:** Monthly bar chart (Plotly) with trend line overlay
- **X-axis:** Months, from earliest purchase date to current month
- **Y-axis:** Dividend income received in base currency
- **Bars:** Stacked by ticker, using `portfolio_color_map` colors
- **Trend line:** Rolling 3-month average, dashed grey line
- **Data source:** `yf.Ticker(t).history(start=purchase_date)["Dividends"]` — already fetched by `_dividends_in_base_currency()`. New logic buckets dividend payments by calendar month and converts at historical FX rates.
- **Empty months:** Show as zero-height bars (no gaps)
- **Plotly config:** Match existing chart styling (transparent background, dark tooltips, grey text axes)

**New helper function** in `src/portfolio.py`:
```python
def build_dividend_timeline(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """Return a DataFrame with columns: month (YYYY-MM), ticker, amount (base currency).
    One row per ticker per month where a dividend was paid."""
```

This function iterates all lots, fetches dividend history from yfinance (cached), buckets by month, converts via historical FX rates. Returns a tidy DataFrame suitable for Plotly stacked bar.

#### 1.3 Dividend Calendar (12-month forward view)

- **Type:** Pure HTML table (matching dashboard design language)
- **Rows:** Next 12 months
- **Columns:** Month | Expected Payers (color dots) | Estimated Amount
- **Logic:** For each ticker, look at which months dividends were paid in the last 12 months. Assume the same months repeat. Estimated amount = most recent dividend per share × shares × FX rate.
- **Disclaimer text** below table: "Based on historical payment patterns. Dividends are not guaranteed."
- **Edge cases:**
  - Ticker with no dividend history: omit from calendar
  - Ticker held < 12 months: need at least 2 dividend payments in history to infer a quarterly/monthly pattern. If only 1 payment exists, show "Insufficient history" for that ticker.
  - Monthly payers (e.g., REITs like O): show in all 12 months

#### 1.4 Per-Position Income Table

- **Type:** HTML table (matching positions table style)
- **Columns:** Ticker (color dot) | Annual Div/Share | Shares | Annual Income | Current Yield | Yield-on-Cost
- **Yield-on-Cost:** annual dividend per share / weighted average buy price × 100
- **Sort:** By annual income descending
- **Tickers with no dividend:** Show row with "--" in all dividend columns
- **Data:** `dividendRate` from `yf.Ticker(t).info` (already in `fetch_fundamentals()` — add if not present), shares from portfolio, buy price from portfolio

### Excel Export

Add new sheet **"Income"** to `excel_export.py`:
- Income KPIs at top (Trailing 12M, Projected Annual, Yield)
- Monthly income table (month × ticker matrix with totals)
- Per-position income summary table

Add after the existing Monte Carlo sheet. Follow existing JP Morgan palette and formatting patterns.

---

## 2. Contribution Tracking (Overview tab addition)

### Purpose

Answer "is my portfolio growth real, or did I just deposit more money?" — requested by 3 of 4 personas.

### Location

`src/ui/overview.py` — additive changes only.

### Components

#### 2.1 New KPI Card — "Total Contributed"

- **Value:** Sum of `buy_price × shares × buy_fx_rate` across all lots — this is the cost basis in base currency
- **Computation:** `build_portfolio_df()` does not expose a `Cost Basis` column directly. Compute as `sum(buy_price * shares * buy_fx_rate)` from the raw portfolio lot data, or add `Cost Basis` as an explicit column to the DataFrame.
- **Position:** 5th card in the existing KPI row (after Positions count)
- **Subtitle:** "Cost basis in {currency}"

#### 2.2 Contributions vs. Value Chart

- **Type:** Plotly area chart
- **Location:** Below the portfolio comparison chart, in its own `chart-card`
- **Title:** "Contributions vs. Portfolio Value"
- **Two lines:**
  1. **Contributed (step line):** Cumulative cost basis over time. Steps up on each purchase date. Flat between purchases. Solid blue line with light fill below.
  2. **Portfolio Value (smooth line):** Daily portfolio value from earliest purchase date to today. Solid green line.
- **Gap shading:** The area between the two lines could be shaded green (gain) or red (loss), but keep it simple for v1 — just two lines, let the visual gap speak for itself.
- **Data construction:**
  - Sort all lots by purchase_date ascending
  - For each date, cumulative_cost += lot cost basis
  - For portfolio value: sum of (shares_held_on_date × closing_price_on_date) for each historical date. Use `fetch_price_history_long()` per ticker. Fetch in parallel via `ThreadPoolExecutor` (same pattern as `_fetch_risk_data` in `risk.py`) to avoid sequential latency with 10+ tickers.
  - Resample to daily frequency, forward-fill the step line
  - If FX rate lookup fails for a historical date, fall back to the nearest available rate (same behavior as `_dividends_in_base_currency`)
- **Time range:** Earliest purchase date to today (no toggle needed — this chart only makes sense over the full period)
- **Plotly config:** Match existing chart styling

**New helper function** in `src/portfolio.py`:
```python
def build_contribution_timeline(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """Return a DataFrame with columns: date, contributed (cumulative cost basis), value (portfolio value).
    Daily frequency from earliest purchase date to today."""
```

### Excel Export

Add "Total Contributed" / "Cost Basis" to the Summary sheet KPIs (may already be there — verify and ensure it's labeled clearly).

---

## 3. Sector Breakdown Chart

### Location

`src/ui/risk.py` — new section below the correlation matrix. This extends the risk tab redesign layout (intro → unified table → correlation matrix) to: intro → unified table → correlation matrix → sector breakdown → rebalancing helper.

### Implementation

- **Type:** Horizontal bar chart (HTML, matching the allocation chart style on Overview)
- **Data:** `yf.Ticker(t).info["sector"]` — add `"sector"` to the dict returned by `fetch_fundamentals()` in `data_fetch.py`
- **Fallback labels:** ETFs → "ETF", bonds → "Fixed Income", crypto → "Crypto", commodities → "Commodities". Determine from the market category in `stocks.py` (which market list the ticker came from) or from `info.get("quoteType")`.
- **Aggregation:** Sum portfolio weight by sector
- **Sort:** By weight descending
- **Colors:** Use a neutral palette (blues/purples/teals) — not the ticker colors, since multiple tickers share a sector
- **Section header:** "Sector Exposure"

### Excel Export

Add sector column to the Fundamentals sheet.

---

## 4. Analyst Target Price

### Location

`src/ui/positions.py` — new column in the positions table.

### Data

- `yf.Ticker(t).info["targetMeanPrice"]` — add to `fetch_fundamentals()` return dict
- Already available in the `.info` call, no additional API request

### Display

- New column "Target" in positions table, after Current Price
- Shows consensus target price in native currency (converted to base currency for display). Apply GBX/100 conversion for London-listed stocks, same as 52-week range values.
- Small inline badge: upside/downside % vs current price
  - Green (`td-pos`): upside > 10%
  - Amber (`td-amb`): upside 0–10%
  - Red (`td-neg`): downside
- ETFs, crypto, bonds, commodities: show "--" (no analyst coverage)

### Excel Export

Add "Target Price" and "Upside/Downside %" columns to the Positions sheet.

---

## 5. Rebalancing Calculator

### Location

`src/ui/risk.py` — new section below the sector breakdown chart.

### Implementation

1. **Target weight inputs:** One editable number input per ticker, pre-filled with current weight. Constrained to 0–100. A "Total" row shows sum (should equal 100%).
2. **Deposit field:** Single number input labeled "Next deposit ({currency})" defaulting to 0.
3. **Output table** (read-only, updates reactively):
   - Columns: Ticker | Current % | Target % | Drift | Action
   - Drift = Current % − Target %
   - Action: "Buy {n} shares (~{amount})" for underweight tickers, "Overweight by {x}%" for overweight tickers
   - Allocation algorithm: distribute the deposit amount to the most underweight positions first, buying whole shares at current prices
4. **Buy-only:** Never suggests sells. If a position is overweight, it just flags it — the user decides.
5. **No persistence:** Target weights are session-only. Cleared on page reload.

### Section Header

"Rebalancing Helper" with subtitle "Buy-only — does not suggest sells"

### Excel Export

No Excel export for this feature (it's interactive/session-only).

---

## 6. Portfolio Benchmark Comparison (SPY Overlay)

### Location

`src/ui/overview.py` — modification to existing comparison chart.

### Implementation

- Add SPY as a permanent reference line on the portfolio comparison chart
- Rebased to 100 at the same start date as other tickers
- **Style:** Dashed grey line, thinner than portfolio lines, labeled "S&P 500" in legend
- **Toggle:** New "Show benchmark" checkbox next to the existing "FX-adjusted" toggle. Default: on.
- **Data:** SPY price history. Use `fetch_price_history_range("SPY", period)` matching the selected time range. Period mapping: "3M" → `"3mo"`, "6M" → `"6mo"`, "1Y" → `"1y"`, "Max" → `"max"`. This is the same mapping the existing comparison chart already uses internally.

---

## 7. Editable Positions

### Location

`src/ui/sidebar.py` — modification to position pills.

### Implementation

- Click a position pill (or an edit icon on the pill) to open an edit dialog
- Dialog uses the same form layout as the add-position form: shares, buy price, purchase date, manual toggle
- Pre-filled with the lot's current values
- **Save:** Overwrites the lot in `portfolio[ticker]`, calls `save_portfolio()`, triggers `on_mutation()`
- **Delete:** "Remove this lot" button in the dialog — removes the lot, triggers mutation. If this is the last lot for a ticker, remove the ticker from the portfolio entirely.
- **Multi-lot:** If a ticker has multiple lots, clicking the pill shows a lot picker first, then the edit dialog for the selected lot
- **Validation:** Same rules as add-position (shares > 0, price > 0 if manual, etc.)

---

## 8. Market Status Indicator

### Location

`main.py` — top bar, next to the currency selector.

### Implementation

- Small colored dot + text label
- **States:**
  - Green dot + "Open" — NYSE regular hours (9:30–16:00 ET, Mon–Fri)
  - Amber dot + "Pre-market" — 4:00–9:30 ET
  - Amber dot + "After hours" — 16:00–20:00 ET
  - Red dot + "Closed" — outside all above, weekends, holidays
- **Timezone:** Use `zoneinfo.ZoneInfo("America/New_York")` (stdlib, no new dependency)
- **Holidays:** Use rule-based patterns (e.g., "third Monday of January", "last Monday of May") rather than hardcoded dates, so no annual maintenance is needed. Cover: New Year's, MLK Day, Presidents' Day, Good Friday, Memorial Day, Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas. ~9–10 holidays per year.
- **No live refresh:** Shows status at page load time. Accurate enough — users reload the page when they want updated data anyway.

---

## 9. Infrastructure

### 9A. Update README

- Replace Streamlit screenshots with NiceGUI UI screenshots
- Update setup instructions (`main.py` entry point, NiceGUI-specific env vars)
- Remove all Streamlit references
- Add feature list matching current state (6 tabs → 7 with Income)
- Add "Self-hosting" section with Docker instructions (if Docker is set up by then)

### 9B. Unit Tests

**Framework:** `pytest` + `unittest.mock`

**Scope — test pure functions, mock yfinance:**

| Module | What to test |
|---|---|
| `src/portfolio.py` | `build_portfolio_df()` with mocked price/dividend data; FX conversion accuracy; cost basis calculation; dividend bucketing (new) |
| `src/fx.py` | Currency detection from ticker suffix; GBX→GBP division; FX rate lookup with mock |
| `src/monte_carlo.py` | Output shape (n_simulations × n_days); VaR/CVaR calculation; Cholesky fallback to independent simulation |
| `src/stocks.py` | Ticker color assignment; stock list parsing from mock HTML |
| `src/ui/shared.py` | Encryption round-trip (encrypt → decrypt = original) |
| New: `src/portfolio.py` | `build_dividend_timeline()` monthly bucketing; `build_contribution_timeline()` step-line construction |

**Test file:** `tests/test_portfolio.py`, `tests/test_fx.py`, etc. One test file per source module.

**No integration tests** against live yfinance API — too flaky for CI.

### 9C. Mobile Responsiveness Fix

- Verify sidebar collapse behavior below 768px
- Ensure all HTML tables have `overflow-x: auto` wrapper
- Test at 375px width (iPhone SE) — tab bar, KPI cards, charts
- Plotly charts: ensure `responsive: true` in config
- Income tab: calendar and income table must scroll horizontally on mobile

### 9D. CSV Export

- New "Export CSV" button on Overview tab, next to Excel export button
- Single flat CSV: one row per lot
- Columns: Ticker, Company, Shares, Buy Price, Purchase Date, Current Price, Total Value, Dividends, Day P&L, Return %, Weight %
- Use `csv.writer` with `io.StringIO` → download via NiceGUI's `ui.download()`
- No styling, no multi-sheet — that's what Excel export is for

### 9E. Loading Spinners

Extend existing spinner pattern to:
- Sidebar "Add position" button: show spinner during price fetch + FX lookup
- Excel export button: show spinner during workbook generation
- Any async data fetch that takes >500ms: wrap in spinner context
- Use existing `ui.spinner("dots")` style for consistency

### 9F. Error State for Delisted Stocks

- When `fetch_fundamentals()` or `fetch_price_history_short()` returns empty/error for a ticker:
  - Sidebar: show amber warning icon on the position pill
  - Positions tab: show row with available data + amber "Data unavailable" badge
  - Risk/Income tabs: exclude ticker from calculations, show footnote "N tickers excluded due to missing data"
- Don't crash the tab — graceful degradation per ticker
- Log the error for debugging

### 9G. README GIF

Animated screen recording showing: add a position → Overview KPIs update → switch tabs → expand a risk row → run Monte Carlo. Replace static PNG screenshots.

### 9H. LinkedIn Post

Not engineering. Write after deployment. Mention: open-source, multi-currency, Monte Carlo, self-hostable. Link to GitHub repo.

---

## 10. Agent Architecture

### Orchestration Model

One Opus orchestrator agent holds the full plan and manages five parallel implementation teams (Sonnet agents in isolated worktrees), plus review agents that validate each team's output.

### Teams

| Team | Scope | Files touched | Dependencies |
|---|---|---|---|
| **Team 1: Income** | Income tab, dividend timeline, dividend calendar, per-position income table, Excel income sheet | New: `src/ui/income.py`. Modify: `src/portfolio.py` (add `build_dividend_timeline`), `main.py` (tab wiring), `src/data_fetch.py` (add `dividendRate` to fundamentals), `src/excel_export.py` (add Income sheet) | None — mostly new files |
| **Team 2: Overview** | Contribution tracking (KPI + chart), SPY benchmark overlay, market status indicator, CSV export | Modify: `src/ui/overview.py`, `src/portfolio.py` (add `build_contribution_timeline`), `main.py` (market status in top bar) | None — additive |
| **Team 3: Risk** | Sector breakdown chart, rebalancing calculator | Modify: `src/ui/risk.py`, `src/data_fetch.py` (add `sector` + `targetMeanPrice` to fundamentals) | `fetch_fundamentals()` changes shared with Team 4 |
| **Team 4: Positions** | Analyst target price column, editable positions dialog, error state for delisted tickers | Modify: `src/ui/positions.py`, `src/ui/sidebar.py` (edit dialog), `src/data_fetch.py` (shared with Team 3) | `fetch_fundamentals()` changes shared with Team 3 |
| **Team 5: Infra** | Unit tests, mobile fix, loading spinners, README update | New: `tests/`. Modify: `src/ui/sidebar.py` (spinners), various UI files (mobile CSS) | Runs after Teams 1–4 merge |

### Shared Data Conflict: `fetch_fundamentals()`

Teams 1, 3, and 4 all add fields to `fetch_fundamentals()` in `data_fetch.py`. Resolution:
- **Team 3 owns `data_fetch.py` changes** — adds `sector`, `targetMeanPrice`, and `dividendRate` to the return dict in one commit. Note: `dividendRate` is already fetched from `yf.Ticker(t).info` inside `fetch_fundamentals()` but only used to derive `Div Yield (%)`; it is not currently included in the return dict. Team 3 simply adds the raw value to the returned dict alongside the existing derived yield.
- Teams 1 and 4 consume these fields but don't modify `data_fetch.py`
- Orchestrator ensures Team 3's `data_fetch.py` change lands first

### Sequencing

```
Phase 0:  Team 3 lands data_fetch.py changes (sector, targetMeanPrice, dividendRate)
          │
Phase 1:  Teams 1, 2, 3, 4 run in parallel (isolated worktrees)
          │         │         │         │
          ▼         ▼         ▼         ▼
        Income   Overview    Risk    Positions
          │         │         │         │
          └─────────┴─────────┴─────────┘
                        │
Phase 2:  Review agents validate each team's output against this spec
          │
Phase 3:  Merge all teams to main (resolve any conflicts)
          │
Phase 4:  Team 5 (Infra) — tests, mobile, spinners, README
          │
Phase 5:  Final review + README GIF + LinkedIn post
```

### Review Protocol

After each team completes:
1. **Code reviewer agent** checks output against the relevant spec section
2. **Test runner agent** runs `pytest` (after Team 5 adds tests) or manual smoke test
3. Orchestrator reviews both reports and decides: merge, request fixes, or escalate to human

### Orchestrator Responsibilities

- Track progress across all 5 teams
- Resolve merge conflicts between teams (especially `data_fetch.py`, `main.py`)
- Ensure no team drifts from the spec
- Surface blockers to the human immediately rather than attempting workarounds
- Final integration test after all teams merge

---

## 11. What Must Not Change

- All existing data calculations remain identical
- The `build_*_tab()` public interfaces stay the same (new params are additive)
- Color dot assignment logic stays the same
- Metric threshold colors (green/amber/red) stay the same
- Existing Excel export sheets continue to work (new sheets are additive)
- Portfolio storage format stays backward-compatible (no migration needed)
- Encryption/decryption logic untouched

---

## 12. Edge Cases

| Scenario | Handling |
|---|---|
| 0 positions | Income tab shows "Add positions to see income data". Contribution chart not rendered. |
| No dividend-paying stocks | Income KPIs show $0. Growth chart shows flat zero line. Calendar shows "No dividends expected." |
| Ticker with no sector info | Sector breakdown uses fallback label (ETF/Fixed Income/Crypto/Commodities/Unknown) |
| Ticker with no analyst target | Target column shows "--" |
| All positions bought on same date | Contribution step line shows single step. Chart still renders correctly. |
| 15+ tickers | All features must handle gracefully. Sector chart aggregates. Income table scrolls. Rebalancing table scrolls. |
| Delisted ticker | Error state applies. Excluded from income/risk calculations. Flagged in UI. |
| Manual-price lots (no purchase date) | Excluded from dividend calculations. Contribution chart uses "today" as purchase date. |
| GBX dividends | Divide by 100 before FX conversion (existing logic in `_dividends_in_base_currency`) |
| Rebalancing with deposit = 0 | Show drift column only. Action column shows "Enter a deposit amount to see buy suggestions." |
| `dividendRate` is None/0 from yfinance | Treat as 0 in income calculations (growth stocks). Show "--" in income table dividend columns. |
| FX rate lookup failure on historical date | Fall back to nearest available rate. Same behavior as existing `_dividends_in_base_currency`. |
| Ticker with only 1 dividend payment | Dividend calendar shows "Insufficient history" for that ticker. Income table still shows the single payment in trailing 12M. |
