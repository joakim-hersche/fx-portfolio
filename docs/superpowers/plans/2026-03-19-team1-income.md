# Team 1: Income Tab — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new "Income" tab (7th tab) showing dividend income growth over time, a forward-looking dividend calendar, and per-position income metrics with yield-on-cost.

**Architecture:** New `src/ui/income.py` module following the existing tab pattern. Two new helper functions in `src/portfolio.py` for dividend timeline bucketing. Wired into `main.py` via `_TAB_NAMES` and `_build_tab()`. New Excel sheet in `excel_export.py`.

**Tech Stack:** NiceGUI, Plotly, pandas, yfinance (via existing cached helpers)

**Spec:** `docs/superpowers/specs/2026-03-19-feature-expansion-design.md` — Section 1

**Prerequisite:** Team 0 (data_fetch changes) must be complete — this plan consumes `Dividend Rate` from `fetch_fundamentals()`.

---

## File Map

- **Create:** `src/ui/income.py` — Income tab UI (KPI cards, income growth chart, dividend calendar, per-position table)
- **Modify:** `src/portfolio.py:204+` — Add `build_dividend_timeline()` helper
- **Modify:** `main.py:82` — Add "Income" to `_TAB_NAMES`
- **Modify:** `main.py:37-48` — Add import
- **Modify:** `main.py:343-365` — Add case to `_build_tab()`
- **Modify:** `src/excel_export.py:1619-1633` — Add Income sheet builder
- **Test:** `tests/test_portfolio_income.py` — Tests for dividend timeline logic

---

### Task 1: Build `build_dividend_timeline()` in portfolio.py

**Files:**
- Modify: `src/portfolio.py` (append after `build_portfolio_df`)
- Create: `tests/test_portfolio_income.py`

- [ ] **Step 1: Write failing tests for dividend timeline**

```python
"""Tests for dividend timeline bucketing."""
import pandas as pd
from unittest.mock import patch, MagicMock
from datetime import date


def _make_dividend_series(dates_and_amounts):
    """Create a mock yfinance dividend Series."""
    idx = pd.DatetimeIndex(dates_and_amounts.keys())
    return pd.Series(dates_and_amounts.values(), index=idx, name="Dividends")


@patch("src.portfolio.yf.Ticker")
@patch("src.portfolio.get_fx_rate", return_value=(1.0, True))
@patch("src.portfolio.get_historical_fx_rate", return_value=(1.0, True))
def test_dividend_timeline_monthly_bucketing(mock_hist_fx, mock_fx, mock_ticker):
    from src.portfolio import build_dividend_timeline

    hist = pd.DataFrame({
        "Dividends": [0.0, 0.24, 0.0, 0.0, 0.24, 0.0],
    }, index=pd.date_range("2025-01-01", periods=6, freq="ME"))
    mock_ticker.return_value.history.return_value = hist

    portfolio = {"AAPL": [{"shares": 10, "purchase_date": "2025-01-01", "manual_price": False}]}
    result = build_dividend_timeline(portfolio, "USD")

    assert isinstance(result, pd.DataFrame)
    assert "month" in result.columns
    assert "ticker" in result.columns
    assert "amount" in result.columns
    # Should have 2 rows (2 months with dividends > 0)
    dividend_rows = result[result["amount"] > 0]
    assert len(dividend_rows) == 2


@patch("src.portfolio.yf.Ticker")
@patch("src.portfolio.get_fx_rate", return_value=(1.0, True))
@patch("src.portfolio.get_historical_fx_rate", return_value=(1.0, True))
def test_dividend_timeline_empty_portfolio(mock_hist_fx, mock_fx, mock_ticker):
    from src.portfolio import build_dividend_timeline
    result = build_dividend_timeline({}, "USD")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_portfolio_income.py -v`
Expected: FAIL — `build_dividend_timeline` not defined

- [ ] **Step 3: Implement `build_dividend_timeline()`**

First, update the import line in `src/portfolio.py` (line 8) from:
```python
from src.fx import get_ticker_currency, get_fx_rate
```
to:
```python
from src.fx import get_ticker_currency, get_fx_rate, get_historical_fx_rate
```

Then append to `src/portfolio.py` after the `build_portfolio_df()` function:

```python
def build_dividend_timeline(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """Return a DataFrame with columns: month (YYYY-MM), ticker, amount (base currency).

    One row per ticker per month where a dividend was paid.
    Used for the Income tab's income growth chart.
    """
    if not portfolio:
        return pd.DataFrame(columns=["month", "ticker", "amount"])

    rows = []
    for ticker, lots in portfolio.items():
        from_currency = get_ticker_currency(ticker)  # returns e.g. "USD", "GBX", "EUR"
        for lot in lots:
            pd_date = lot.get("purchase_date")
            if not pd_date or pd_date == "Manual":
                continue
            try:
                ticker_obj = yf.Ticker(ticker)
                hist = ticker_obj.history(start=pd_date)
                if hist.empty or "Dividends" not in hist.columns:
                    continue
                dividends = hist["Dividends"]
                dividends = dividends[dividends > 0]
                if dividends.empty:
                    continue

                shares = lot["shares"]
                for div_date, div_per_share in dividends.items():
                    amount_native = div_per_share * shares
                    # GBX to GBP conversion
                    if from_currency == "GBX":
                        amount_native /= 100
                        fx_from = "GBP"
                    else:
                        fx_from = from_currency
                    # Convert to base currency at historical rate
                    if fx_from == base_currency:
                        amount_base = amount_native
                    else:
                        fx_rate = get_historical_fx_rate(fx_from, base_currency, div_date.strftime("%Y-%m-%d"))  # returns float directly
                        amount_base = amount_native * fx_rate

                    month_str = div_date.strftime("%Y-%m")
                    rows.append({"month": month_str, "ticker": ticker, "amount": amount_base})
            except Exception:
                continue

    if not rows:
        return pd.DataFrame(columns=["month", "ticker", "amount"])

    df = pd.DataFrame(rows)
    # Aggregate: sum amounts per ticker per month (in case multiple lots)
    df = df.groupby(["month", "ticker"], as_index=False)["amount"].sum()
    return df.sort_values("month")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_portfolio_income.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/portfolio.py tests/test_portfolio_income.py
git commit -m "feat: add build_dividend_timeline helper for income tab"
```

---

### Task 2: Create the Income tab UI module

**Files:**
- Create: `src/ui/income.py`

- [ ] **Step 1: Create the income tab module with KPI cards**

Create `src/ui/income.py`:

```python
"""Income tab — dividend income tracking and projections."""
from __future__ import annotations

import calendar
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import plotly.graph_objects as go
from nicegui import ui

from src.data_fetch import fetch_fundamentals, fetch_company_name
from src.fx import get_ticker_currency, get_fx_rate, get_historical_fx_rate
from src.portfolio import build_dividend_timeline, build_portfolio_df
from src.theme import (
    BG_CARD, BG_PILL, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_FAINT,
    ACCENT, GREEN, RED, AMBER, BORDER_SUBTLE,
)


async def build_income_tab(
    portfolio: dict,
    currency: str,
    portfolio_color_map: dict,
) -> None:
    """Build the Income tab content."""
    if not portfolio:
        ui.label("Add positions to see income data.").classes("text-center w-full py-8").style(f"color: {TEXT_FAINT}")
        return

    # Fetch data in parallel
    tickers = list(portfolio.keys())
    fundamentals = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {t: pool.submit(fetch_fundamentals, t) for t in tickers}
        name_futures = {t: pool.submit(fetch_company_name, t) for t in tickers}
        for t, f in futures.items():
            try:
                fundamentals[t] = f.result()
            except Exception:
                fundamentals[t] = {}
        name_map = {}
        for t, f in name_futures.items():
            try:
                name_map[t] = f.result()
            except Exception:
                name_map[t] = t

    # Build dividend timeline
    div_timeline = await ui.run_cpu_bound(build_dividend_timeline, portfolio, currency)

    # Compute KPIs
    trailing_12m = _compute_trailing_12m(div_timeline)
    projected_annual = _compute_projected_annual(portfolio, fundamentals, currency)
    portfolio_df = build_portfolio_df(portfolio, currency)
    total_value = portfolio_df["Total Value"].sum() if not portfolio_df.empty else 0
    portfolio_yield = (projected_annual / total_value * 100) if total_value > 0 else 0

    # --- KPI Row ---
    with ui.row().classes("kpi-row w-full gap-4 justify-center"):
        _income_kpi_card("Trailing 12M Income", f"{currency} {trailing_12m:,.2f}", "Dividends received last 12 months")
        _income_kpi_card("Projected Annual Income", f"{currency} {projected_annual:,.2f}", "Based on current holdings")
        _income_kpi_card("Portfolio Yield", f"{portfolio_yield:.2f}%", "Projected income / portfolio value")

    # --- Income Growth Chart ---
    _render_income_growth_chart(div_timeline, portfolio_color_map, currency)

    # --- Dividend Calendar ---
    _render_dividend_calendar(portfolio, fundamentals, portfolio_color_map, currency)

    # --- Per-Position Income Table ---
    _render_income_table(portfolio, fundamentals, portfolio_color_map, name_map, currency)
```

- [ ] **Step 2: Add the KPI card helper**

Append to `src/ui/income.py`:

```python
def _income_kpi_card(title: str, value: str, subtitle: str) -> None:
    """Render a single income KPI card."""
    with ui.column().classes("kpi-card"):
        ui.label(title).style(f"color: {TEXT_FAINT}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em;")
        ui.label(value).style(f"color: {TEXT_PRIMARY}; font-size: 24px; font-weight: 700;")
        ui.label(subtitle).style(f"color: {TEXT_FAINT}; font-size: 11px;")
```

- [ ] **Step 3: Add trailing 12M and projected annual income computations**

Append to `src/ui/income.py`:

```python
def _compute_trailing_12m(div_timeline) -> float:
    """Sum dividend income from the last 12 months."""
    if div_timeline.empty:
        return 0.0
    cutoff = (datetime.now() - timedelta(days=365)).strftime("%Y-%m")
    recent = div_timeline[div_timeline["month"] >= cutoff]
    return recent["amount"].sum()


def _compute_projected_annual(portfolio: dict, fundamentals: dict, base_currency: str) -> float:
    """Estimate annual income from current holdings × dividend rate."""
    total = 0.0
    for ticker, lots in portfolio.items():
        fund = fundamentals.get(ticker, {})
        div_rate = fund.get("Dividend Rate")
        if not div_rate:
            continue
        shares = sum(lot["shares"] for lot in lots)
        amount_native = div_rate * shares

        from_currency = get_ticker_currency(ticker)  # returns e.g. "USD", "GBX", "EUR"
        if from_currency == "GBX":
            amount_native /= 100
            from_currency = "GBP"

        if from_currency == base_currency:
            total += amount_native
        else:
            fx = get_fx_rate(from_currency, base_currency)
            total += amount_native * fx
    return total
```

- [ ] **Step 4: Commit skeleton**

```bash
git add src/ui/income.py
git commit -m "feat: add income tab skeleton with KPI cards"
```

---

### Task 3: Income Growth Chart

**Files:**
- Modify: `src/ui/income.py`

- [ ] **Step 1: Implement the income growth chart renderer**

Append to `src/ui/income.py`:

```python
def _render_income_growth_chart(div_timeline, color_map: dict, currency: str) -> None:
    """Render stacked monthly bar chart with rolling 3-month average trend line."""
    with ui.column().classes("chart-card w-full"):
        ui.label("Income Growth").classes("chart-title")
        ui.label("Monthly dividend income received").style(f"color: {TEXT_FAINT}; font-size: 12px; margin-bottom: 8px;")

        if div_timeline.empty:
            ui.label("No dividend income recorded yet.").style(f"color: {TEXT_FAINT};")
            return

        fig = go.Figure()

        # Pivot: columns = tickers, index = months, values = amounts
        pivot = div_timeline.pivot_table(index="month", columns="ticker", values="amount", aggfunc="sum", fill_value=0)
        pivot = pivot.sort_index()

        # Stacked bars per ticker
        for ticker in pivot.columns:
            color = color_map.get(ticker, ACCENT)
            fig.add_trace(go.Bar(
                x=pivot.index,
                y=pivot[ticker],
                name=ticker,
                marker_color=color,
                hovertemplate=f"{ticker}: %{{y:,.2f}} {currency}<extra></extra>",
            ))

        # Rolling 3-month average trend line
        monthly_total = pivot.sum(axis=1)
        rolling_avg = monthly_total.rolling(3, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=pivot.index,
            y=rolling_avg,
            name="3-month avg",
            mode="lines",
            line=dict(color="#94A3B8", width=2, dash="dash"),
            hovertemplate="Avg: %{y:,.2f} " + currency + "<extra></extra>",
        ))

        fig.update_layout(
            barmode="stack",
            template="plotly",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=20, t=10, b=40),
            legend=dict(orientation="h", y=-0.15, font=dict(size=10, color=TEXT_FAINT)),
            xaxis=dict(
                tickfont=dict(size=10, color=TEXT_FAINT),
                gridcolor="rgba(255,255,255,0.06)",
            ),
            yaxis=dict(
                title=currency,
                tickfont=dict(size=10, color=TEXT_FAINT),
                gridcolor="rgba(255,255,255,0.06)",
            ),
            hoverlabel=dict(bgcolor="#1C1D26", font_color="#CBD5E1"),
        )

        ui.plotly(fig).classes("w-full").style("height: 350px;")
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/income.py
git commit -m "feat: add income growth chart with stacked bars and trend line"
```

---

### Task 4: Dividend Calendar

**Files:**
- Modify: `src/ui/income.py`

- [ ] **Step 1: Implement the dividend calendar renderer**

Append to `src/ui/income.py`:

```python
def _render_dividend_calendar(portfolio: dict, fundamentals: dict, color_map: dict, currency: str) -> None:
    """Render 12-month forward dividend calendar based on historical payment patterns."""
    with ui.column().classes("chart-card w-full"):
        ui.label("Dividend Calendar").classes("chart-title")
        ui.label("Expected payments based on historical patterns").style(f"color: {TEXT_FAINT}; font-size: 12px; margin-bottom: 8px;")

        # Infer payment months per ticker from yfinance history
        import yfinance as yf
        payment_schedule = {}  # ticker -> {month_number: estimated_amount}

        for ticker, lots in portfolio.items():
            total_shares = sum(lot["shares"] for lot in lots)
            try:
                hist = yf.Ticker(ticker).history(period="1y")
                if hist.empty or "Dividends" not in hist.columns:
                    continue
                divs = hist["Dividends"]
                divs = divs[divs > 0]
                if len(divs) < 2:
                    continue  # Need at least 2 payments to infer pattern

                # Get payment months and most recent dividend per share
                months = [d.month for d in divs.index]
                latest_div = divs.iloc[-1]
                est_amount = latest_div * total_shares

                # FX conversion
                from_ccy = get_ticker_currency(ticker)
                if from_ccy == "GBX":
                    est_amount /= 100
                    from_ccy = "GBP"
                if from_ccy != currency:
                    fx_rate, _ = get_fx_rate(from_ccy, currency)
                    est_amount *= fx_rate

                payment_schedule[ticker] = {m: est_amount for m in set(months)}
            except Exception:
                continue

        if not payment_schedule:
            ui.label("No dividends expected.").style(f"color: {TEXT_FAINT};")
            ui.label("Based on historical payment patterns. Dividends are not guaranteed.").style(f"color: {TEXT_FAINT}; font-size: 11px; margin-top: 8px;")
            return

        # Build calendar rows for next 12 months
        now = datetime.now()
        rows_html = []
        for i in range(12):
            month_date = now + timedelta(days=30 * i)
            m = month_date.month
            month_label = month_date.strftime("%b %Y")

            payers = []
            total = 0.0
            for ticker, schedule in payment_schedule.items():
                if m in schedule:
                    color = color_map.get(ticker, ACCENT)
                    payers.append(f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:4px;" title="{ticker}"></span>')
                    total += schedule[m]

            dots = "".join(payers) if payers else f'<span style="color:{TEXT_FAINT};">—</span>'
            amount = f"{currency} {total:,.2f}" if total > 0 else "—"

            rows_html.append(
                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.06);">'
                f'<td style="padding:8px 12px;color:{TEXT_SECONDARY};font-size:13px;">{month_label}</td>'
                f'<td style="padding:8px 12px;">{dots}</td>'
                f'<td style="padding:8px 12px;color:{TEXT_SECONDARY};font-size:13px;text-align:right;">{amount}</td>'
                f'</tr>'
            )

        html = f'''
        <table style="width:100%;border-collapse:collapse;">
            <thead><tr style="border-bottom:1px solid rgba(255,255,255,0.12);">
                <th style="text-align:left;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Month</th>
                <th style="text-align:left;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Expected Payers</th>
                <th style="text-align:right;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Est. Amount</th>
            </tr></thead>
            <tbody>{"".join(rows_html)}</tbody>
        </table>
        '''
        ui.html(html)
        ui.label("Based on historical payment patterns. Dividends are not guaranteed.").style(f"color: {TEXT_FAINT}; font-size: 11px; margin-top: 8px;")
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/income.py
git commit -m "feat: add dividend calendar with forward projections"
```

---

### Task 5: Per-Position Income Table

**Files:**
- Modify: `src/ui/income.py`

- [ ] **Step 1: Implement the per-position income table**

Append to `src/ui/income.py`:

```python
def _render_income_table(portfolio: dict, fundamentals: dict, color_map: dict, name_map: dict, currency: str) -> None:
    """Render per-position income table with yield-on-cost."""
    with ui.column().classes("chart-card w-full"):
        ui.label("Income by Position").classes("chart-title")

        rows_data = []
        for ticker, lots in portfolio.items():
            fund = fundamentals.get(ticker, {})
            div_rate = fund.get("Dividend Rate")
            total_shares = sum(lot["shares"] for lot in lots)

            # Weighted average buy price
            total_cost = sum(lot["shares"] * lot.get("buy_price", 0) for lot in lots)
            avg_buy = total_cost / total_shares if total_shares > 0 else 0

            # Current yield from fundamentals
            current_yield = fund.get("Div Yield (%)", 0) or 0

            if div_rate and div_rate > 0:
                annual_income_native = div_rate * total_shares
                from_ccy = get_ticker_currency(ticker)
                if from_ccy == "GBX":
                    annual_income_native /= 100
                    from_ccy = "GBP"
                if from_ccy != currency:
                    fx_rate, _ = get_fx_rate(from_ccy, currency)
                    annual_income_native *= fx_rate

                yield_on_cost = (div_rate / avg_buy * 100) if avg_buy > 0 else 0
                rows_data.append({
                    "ticker": ticker,
                    "div_rate": div_rate,
                    "shares": total_shares,
                    "annual_income": annual_income_native,
                    "current_yield": current_yield,
                    "yield_on_cost": yield_on_cost,
                })
            else:
                rows_data.append({
                    "ticker": ticker,
                    "div_rate": None,
                    "shares": total_shares,
                    "annual_income": 0,
                    "current_yield": 0,
                    "yield_on_cost": 0,
                })

        # Sort by annual income descending
        rows_data.sort(key=lambda r: r["annual_income"], reverse=True)

        # Render HTML table
        rows_html = []
        for r in rows_data:
            color = color_map.get(r["ticker"], ACCENT)
            dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{color};margin-right:6px;"></span>'
            company = name_map.get(r["ticker"], r["ticker"])

            if r["div_rate"] is not None:
                div_rate_str = f'{r["div_rate"]:.2f}'
                income_str = f'{currency} {r["annual_income"]:,.2f}'
                yield_str = f'{r["current_yield"]:.2f}%'
                yoc_str = f'{r["yield_on_cost"]:.2f}%'
            else:
                div_rate_str = income_str = yield_str = yoc_str = "—"

            rows_html.append(
                f'<tr style="border-bottom:1px solid rgba(255,255,255,0.06);">'
                f'<td style="padding:8px 12px;color:{TEXT_SECONDARY};font-size:13px;">{dot}{r["ticker"]}</td>'
                f'<td style="padding:8px 12px;color:{TEXT_FAINT};font-size:12px;">{company}</td>'
                f'<td style="padding:8px 12px;color:{TEXT_SECONDARY};font-size:13px;text-align:right;">{div_rate_str}</td>'
                f'<td style="padding:8px 12px;color:{TEXT_SECONDARY};font-size:13px;text-align:right;">{r["shares"]:.2f}</td>'
                f'<td style="padding:8px 12px;color:{TEXT_PRIMARY};font-size:13px;text-align:right;font-weight:600;">{income_str}</td>'
                f'<td style="padding:8px 12px;color:{TEXT_SECONDARY};font-size:13px;text-align:right;">{yield_str}</td>'
                f'<td style="padding:8px 12px;color:{TEXT_SECONDARY};font-size:13px;text-align:right;">{yoc_str}</td>'
                f'</tr>'
            )

        html = f'''
        <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;">
            <thead><tr style="border-bottom:1px solid rgba(255,255,255,0.12);">
                <th style="text-align:left;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Ticker</th>
                <th style="text-align:left;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Company</th>
                <th style="text-align:right;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Ann. Div/Share</th>
                <th style="text-align:right;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Shares</th>
                <th style="text-align:right;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Annual Income</th>
                <th style="text-align:right;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Yield</th>
                <th style="text-align:right;padding:8px 12px;color:{TEXT_FAINT};font-size:11px;text-transform:uppercase;">Yield on Cost</th>
            </tr></thead>
            <tbody>{"".join(rows_html)}</tbody>
        </table>
        </div>
        '''
        ui.html(html)
```

- [ ] **Step 2: Commit**

```bash
git add src/ui/income.py
git commit -m "feat: add per-position income table with yield-on-cost"
```

---

### Task 6: Wire Income tab into main.py

**Files:**
- Modify: `main.py:82` — `_TAB_NAMES`
- Modify: `main.py:37-48` — imports
- Modify: `main.py:343-365` — `_build_tab()`

- [ ] **Step 1: Add import**

In `main.py`, add after the existing UI imports (around line 48):

```python
from src.ui.income import build_income_tab
```

- [ ] **Step 2: Add "Income" to `_TAB_NAMES`**

Change line 82 from:
```python
_TAB_NAMES = ["Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"]
```
to:
```python
_TAB_NAMES = ["Overview", "Positions", "Risk & Analytics", "Income", "Forecast", "Diagnostics", "Guide"]
```

- [ ] **Step 3: Add case to `_build_tab()`**

In the `_build_tab()` function (around line 343-365), add a new `elif` case:

```python
elif name == "Income":
    await build_income_tab(portfolio, currency, portfolio_color_map)
```

Place it after the "Risk & Analytics" case and before the "Forecast" case.

- [ ] **Step 4: Test by running the app**

Run: `python main.py`
Expected: App starts. Tab bar shows "Income" between "Risk & Analytics" and "Forecast". Clicking Income tab renders KPI cards, chart, calendar, and table.

- [ ] **Step 5: Commit**

```bash
git add main.py
git commit -m "feat: wire income tab into main app"
```

---

### Task 7: Excel Income Sheet

**Files:**
- Modify: `src/excel_export.py`

- [ ] **Step 1: Add income sheet builder function**

Add a new function `_sheet_income()` to `src/excel_export.py` (before the `builders` list at line 1619). Follow the existing sheet patterns (JP Morgan palette, borders, headers).

The function should create a sheet with:
- Income KPIs at top (Trailing 12M, Projected Annual, Yield)
- Per-position income table (ticker, annual div/share, shares, annual income, yield, yield-on-cost)

- [ ] **Step 2: Add to builders list**

In the `builders` list (line 1619-1633), add after the Monte Carlo entry:

```python
("Income", lambda: _sheet_income(wb, positions_df, fund_rows, name_map, currency)),
```

- [ ] **Step 3: Update `build_excel_report()` signature if needed**

Ensure `fund_rows` (which now contains `Dividend Rate`) is passed through. It already is — no signature change needed.

- [ ] **Step 4: Commit**

```bash
git add src/excel_export.py
git commit -m "feat: add income sheet to excel export"
```
