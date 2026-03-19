# Team 2: Overview Additions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contribution tracking (KPI card + Contributions vs. Value chart), SPY benchmark overlay on comparison chart, market status indicator in top bar, and CSV export button.

**Architecture:** Additive changes to `src/ui/overview.py` (contribution tracking, SPY overlay, CSV export) and `main.py` (market status indicator). New helper in `src/portfolio.py` for contribution timeline. All changes are additive — no existing functions are modified, only extended.

**Tech Stack:** NiceGUI, Plotly, pandas, csv, zoneinfo

**Spec:** `docs/superpowers/specs/2026-03-19-feature-expansion-design.md` — Sections 2, 6, 8, 9D

---

## File Map

- **Modify:** `src/portfolio.py` — Add `build_contribution_timeline()` helper
- **Modify:** `src/ui/overview.py:141-198` — Add 5th KPI card
- **Modify:** `src/ui/overview.py:290-389` — Add SPY overlay + benchmark toggle to comparison chart
- **Modify:** `src/ui/overview.py:389+` — Add contributions vs. value chart
- **Modify:** `src/ui/overview.py` — Add CSV export button
- **Modify:** `main.py:202-218` — Add market status indicator to top bar
- **Test:** `tests/test_portfolio_contrib.py` — Tests for contribution timeline logic
- **Test:** `tests/test_market_status.py` — Tests for market status calculation

---

### Task 1: Build `build_contribution_timeline()` in portfolio.py

**Files:**
- Modify: `src/portfolio.py`
- Create: `tests/test_portfolio_contrib.py`

- [ ] **Step 1: Write failing test**

```python
"""Tests for contribution timeline construction."""
import pandas as pd
from unittest.mock import patch, MagicMock
from src.portfolio import build_contribution_timeline


@patch("src.portfolio.yf.Ticker")
@patch("src.portfolio.get_fx_rate", return_value=(1.0, True))
def test_contribution_timeline_shape(mock_fx, mock_ticker):
    # Mock price history
    dates = pd.date_range("2025-01-01", "2025-03-01", freq="B")
    mock_hist = pd.DataFrame({"Close": [100.0] * len(dates)}, index=dates)
    mock_ticker.return_value.history.return_value = mock_hist

    portfolio = {
        "AAPL": [{"shares": 10, "buy_price": 95.0, "buy_fx_rate": 1.0, "purchase_date": "2025-01-15", "manual_price": False}]
    }
    result = build_contribution_timeline(portfolio, "USD")
    assert isinstance(result, pd.DataFrame)
    assert "date" in result.columns
    assert "contributed" in result.columns
    assert "value" in result.columns
    assert len(result) > 0


def test_contribution_timeline_empty():
    result = build_contribution_timeline({}, "USD")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_portfolio_contrib.py -v`
Expected: FAIL — `build_contribution_timeline` not defined

- [ ] **Step 3: Implement `build_contribution_timeline()`**

Append to `src/portfolio.py`:

```python
def build_contribution_timeline(portfolio: dict, base_currency: str) -> pd.DataFrame:
    """Build daily timeline of cumulative contributions vs. portfolio value.

    Returns DataFrame with columns: date, contributed (cumulative cost basis), value (portfolio value).
    Daily frequency from earliest purchase date to today.
    """
    if not portfolio:
        return pd.DataFrame(columns=["date", "contributed", "value"])

    # Collect all lots with dates
    lots_with_dates = []
    for ticker, lots in portfolio.items():
        for lot in lots:
            pd_date = lot.get("purchase_date")
            # Manual-price lots without a date use today (per spec edge case)
            if not pd_date or pd_date == "Manual":
                pd_date = pd.Timestamp.now().strftime("%Y-%m-%d")
            cost_basis = lot["shares"] * lot.get("buy_price", 0) * lot.get("buy_fx_rate", 1.0)
            lots_with_dates.append({
                "ticker": ticker,
                "shares": lot["shares"],
                "cost_basis": cost_basis,
                "purchase_date": pd.Timestamp(pd_date),
            })

    if not lots_with_dates:
        return pd.DataFrame(columns=["date", "contributed", "value"])

    lots_with_dates.sort(key=lambda x: x["purchase_date"])
    start_date = lots_with_dates[0]["purchase_date"]
    today = pd.Timestamp.now().normalize()
    date_range = pd.date_range(start_date, today, freq="B")  # business days

    if date_range.empty:
        return pd.DataFrame(columns=["date", "contributed", "value"])

    # Fetch price histories in parallel
    from concurrent.futures import ThreadPoolExecutor
    from src.data_fetch import fetch_price_history_long

    tickers = list(set(lot["ticker"] for lot in lots_with_dates))
    price_data = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {t: pool.submit(fetch_price_history_long, t) for t in tickers}
        for t, f in futures.items():
            try:
                price_data[t] = f.result()
            except Exception:
                price_data[t] = pd.DataFrame()

    # Build daily series
    contributed = []
    values = []
    for date in date_range:
        # Cumulative cost basis: sum of all lots purchased on or before this date
        cum_cost = sum(
            lot["cost_basis"] for lot in lots_with_dates
            if lot["purchase_date"] <= date
        )

        # Portfolio value: sum of shares × price for lots held on this date
        port_val = 0.0
        for lot in lots_with_dates:
            if lot["purchase_date"] > date:
                continue
            hist = price_data.get(lot["ticker"], pd.DataFrame())
            if hist.empty or "Close" not in hist.columns:
                continue
            # Get closest price on or before date
            valid = hist[hist.index <= date]
            if valid.empty:
                continue
            price = valid["Close"].iloc[-1]
            from_ccy = get_ticker_currency(lot["ticker"])
            if from_ccy == "GBX":
                price /= 100
                from_ccy = "GBP"
            if from_ccy != base_currency:
                fx, _ = get_fx_rate(from_ccy, base_currency)
                price *= fx
            port_val += lot["shares"] * price

        contributed.append(cum_cost)
        values.append(port_val)

    return pd.DataFrame({
        "date": date_range,
        "contributed": contributed,
        "value": values,
    })
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_portfolio_contrib.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/portfolio.py tests/test_portfolio_contrib.py
git commit -m "feat: add build_contribution_timeline helper"
```

---

### Task 2: Add "Total Contributed" KPI Card

**Files:**
- Modify: `src/ui/overview.py:141-198`

- [ ] **Step 1: Read the current KPI card rendering section**

Read `src/ui/overview.py` lines 141-198 to understand the existing 4-card layout.

- [ ] **Step 2: Add 5th KPI card after the Positions card**

After the 4th card (Positions count, around line 196), add:

```python
# Card 5: Total Contributed
total_contributed = sum(
    lot["shares"] * lot.get("buy_price", 0) * lot.get("buy_fx_rate", 1.0)
    for lots in portfolio.values()
    for lot in lots
)
_kpi_card(
    "Total Contributed",
    f"{currency} {total_contributed:,.2f}",
    subtitle=f"Cost basis in {currency}",
)
```

- [ ] **Step 3: Run app to verify**

Run: `python main.py`
Expected: Overview tab shows 5 KPI cards. 5th card shows "Total Contributed" with the cost basis sum.

- [ ] **Step 4: Commit**

```bash
git add src/ui/overview.py
git commit -m "feat: add total contributed KPI card to overview"
```

---

### Task 3: Contributions vs. Value Chart

**Files:**
- Modify: `src/ui/overview.py`

- [ ] **Step 1: Add the chart below the comparison chart section**

After the comparison chart section (around line 389), add a new chart-card section:

```python
# --- Contributions vs. Portfolio Value ---
from src.portfolio import build_contribution_timeline

contrib_df = await ui.run_cpu_bound(build_contribution_timeline, portfolio, currency)
if not contrib_df.empty:
    with ui.column().classes("chart-card w-full"):
        ui.label("Contributions vs. Portfolio Value").classes("chart-title")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=contrib_df["date"],
            y=contrib_df["contributed"],
            name="Contributed",
            mode="lines",
            line=dict(color=ACCENT, width=2, shape="hv"),  # step line
            fill="tozeroy",
            fillcolor="rgba(59, 130, 246, 0.1)",
            hovertemplate="Contributed: %{y:,.2f} " + currency + "<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=contrib_df["date"],
            y=contrib_df["value"],
            name="Portfolio Value",
            mode="lines",
            line=dict(color=GREEN, width=2),
            hovertemplate="Value: %{y:,.2f} " + currency + "<extra></extra>",
        ))

        fig.update_layout(
            template="plotly",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=20, t=10, b=40),
            legend=dict(orientation="h", y=-0.15, font=dict(size=10, color=TEXT_FAINT)),
            xaxis=dict(tickfont=dict(size=10, color=TEXT_FAINT), gridcolor="rgba(255,255,255,0.06)"),
            yaxis=dict(title=currency, tickfont=dict(size=10, color=TEXT_FAINT), gridcolor="rgba(255,255,255,0.06)"),
            hoverlabel=dict(bgcolor="#1C1D26", font_color="#CBD5E1"),
        )
        ui.plotly(fig).classes("w-full").style("height: 300px;")
```

- [ ] **Step 2: Run app to verify**

Expected: Overview tab shows Contributions vs. Value chart below the comparison chart. Blue step line (contributions) and green line (portfolio value) with visible gap.

- [ ] **Step 3: Commit**

```bash
git add src/ui/overview.py
git commit -m "feat: add contributions vs portfolio value chart"
```

---

### Task 4: SPY Benchmark Overlay

**Files:**
- Modify: `src/ui/overview.py:290-389`

- [ ] **Step 1: Read the comparison chart section**

Read `src/ui/overview.py` lines 290-389 to understand the current chart build and toggle logic.

- [ ] **Step 2: Add benchmark toggle**

After the FX-adjusted toggle (around line 311), add:

```python
benchmark_switch = ui.switch("Show benchmark", value=True).classes("ml-4")
```

- [ ] **Step 3: Add SPY trace to the comparison chart**

Inside the chart update function (wherever traces are added), add SPY as a reference line when the benchmark toggle is on:

```python
if benchmark_switch.value:
    from src.data_fetch import fetch_price_history_range
    spy_hist = fetch_price_history_range("SPY", period)
    if spy_hist is not None and not spy_hist.empty and "Close" in spy_hist.columns:
        spy_close = spy_hist["Close"]
        spy_rebased = spy_close / spy_close.iloc[0] * 100
        fig.add_trace(go.Scatter(
            x=spy_rebased.index,
            y=spy_rebased.values,
            name="S&P 500",
            mode="lines",
            line=dict(color="#64748B", width=1.5, dash="dash"),
            hovertemplate="S&P 500: %{y:.1f}<extra></extra>",
        ))
```

- [ ] **Step 4: Wire the toggle to trigger chart rebuild**

Ensure the benchmark toggle triggers the same debounced update as the FX toggle. Add it to the same `on_value_change` handler.

- [ ] **Step 5: Run app to verify**

Expected: Comparison chart shows dashed grey "S&P 500" line. Toggling "Show benchmark" off removes it.

- [ ] **Step 6: Commit**

```bash
git add src/ui/overview.py
git commit -m "feat: add SPY benchmark overlay on comparison chart"
```

---

### Task 5: Market Status Indicator

**Files:**
- Modify: `main.py:202-218`
- Create: `tests/test_market_status.py`

- [ ] **Step 1: Write tests for market status logic**

```python
"""Tests for market status calculation."""
from datetime import datetime
from zoneinfo import ZoneInfo


def _market_status(dt: datetime) -> tuple[str, str]:
    """Determine NYSE market status. Returns (status, color)."""
    et = dt.astimezone(ZoneInfo("America/New_York"))

    # Weekend check
    if et.weekday() >= 5:
        return ("Closed", "#DC2626")

    # Holiday check (rule-based)
    # ... tested via specific dates below

    hour_min = et.hour * 60 + et.minute
    if 570 <= hour_min < 960:  # 9:30-16:00
        return ("Open", "#16A34A")
    elif 240 <= hour_min < 570:  # 4:00-9:30
        return ("Pre-market", "#D97706")
    elif 960 <= hour_min < 1200:  # 16:00-20:00
        return ("After hours", "#D97706")
    else:
        return ("Closed", "#DC2626")


def test_market_open():
    dt = datetime(2026, 3, 18, 10, 30, tzinfo=ZoneInfo("America/New_York"))  # Wednesday 10:30 ET
    status, color = _market_status(dt)
    assert status == "Open"


def test_market_premarket():
    dt = datetime(2026, 3, 18, 7, 0, tzinfo=ZoneInfo("America/New_York"))  # Wednesday 7:00 ET
    status, color = _market_status(dt)
    assert status == "Pre-market"


def test_market_after_hours():
    dt = datetime(2026, 3, 18, 17, 0, tzinfo=ZoneInfo("America/New_York"))  # Wednesday 17:00 ET
    status, color = _market_status(dt)
    assert status == "After hours"


def test_market_closed_weekend():
    dt = datetime(2026, 3, 21, 12, 0, tzinfo=ZoneInfo("America/New_York"))  # Saturday
    status, color = _market_status(dt)
    assert status == "Closed"
```

- [ ] **Step 2: Implement market status function in main.py**

Add a helper function in `main.py` (before the `index()` route):

```python
from zoneinfo import ZoneInfo
from datetime import datetime

def _market_status() -> tuple[str, str]:
    """Return (status_text, dot_color) for NYSE market status."""
    et = datetime.now(ZoneInfo("America/New_York"))

    if et.weekday() >= 5:
        return ("Closed", RED)

    # Rule-based US market holidays
    if _is_nyse_holiday(et):
        return ("Closed", RED)

    hour_min = et.hour * 60 + et.minute
    if 570 <= hour_min < 960:  # 9:30-16:00
        return ("Open", GREEN)
    elif 240 <= hour_min < 570:  # 4:00-9:30
        return ("Pre-market", AMBER)
    elif 960 <= hour_min < 1200:  # 16:00-20:00
        return ("After hours", AMBER)
    else:
        return ("Closed", RED)


def _is_nyse_holiday(dt: datetime) -> bool:
    """Check if date is a NYSE holiday using rule-based patterns."""
    m, d, dow = dt.month, dt.day, dt.weekday()  # dow: 0=Mon

    # New Year's Day (Jan 1, or nearest weekday)
    if m == 1 and d <= 2 and dow == 0:
        return True
    if m == 1 and d == 1 and dow < 5:
        return True
    # MLK Day (3rd Monday of January)
    if m == 1 and dow == 0 and 15 <= d <= 21:
        return True
    # Presidents' Day (3rd Monday of February)
    if m == 2 and dow == 0 and 15 <= d <= 21:
        return True
    # Good Friday — skip (date varies, complex to compute without a library)
    # Memorial Day (last Monday of May)
    if m == 5 and dow == 0 and d >= 25:
        return True
    # Juneteenth (June 19, or nearest weekday)
    if m == 6 and d == 19 and dow < 5:
        return True
    if m == 6 and d == 20 and dow == 0:
        return True
    if m == 6 and d == 18 and dow == 4:
        return True
    # Independence Day (July 4, or nearest weekday)
    if m == 7 and d == 4 and dow < 5:
        return True
    if m == 7 and d == 5 and dow == 0:
        return True
    if m == 7 and d == 3 and dow == 4:
        return True
    # Labor Day (1st Monday of September)
    if m == 9 and dow == 0 and d <= 7:
        return True
    # Thanksgiving (4th Thursday of November)
    if m == 11 and dow == 3 and 22 <= d <= 28:
        return True
    # Christmas (Dec 25, or nearest weekday)
    if m == 12 and d == 25 and dow < 5:
        return True
    if m == 12 and d == 26 and dow == 0:
        return True
    if m == 12 and d == 24 and dow == 4:
        return True

    return False
```

- [ ] **Step 3: Add the indicator to the top bar**

In `main.py`, inside the top bar right-side section (around lines 202-218), add before the currency selector:

```python
status_text, status_color = _market_status()
with ui.row().classes("items-center gap-1 mr-4"):
    ui.element("span").style(
        f"width:8px;height:8px;border-radius:50%;background:{status_color};display:inline-block;"
    )
    ui.label(status_text).style(f"color:{TEXT_FAINT};font-size:12px;")
```

- [ ] **Step 4: Run app and tests**

Run: `python main.py`
Expected: Top bar shows market status dot + text next to currency selector.

Run: `pytest tests/test_market_status.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add main.py tests/test_market_status.py
git commit -m "feat: add market status indicator to top bar"
```

---

### Task 6: CSV Export

**Files:**
- Modify: `src/ui/overview.py`

- [ ] **Step 1: Add CSV export button next to Excel export**

Find the Excel export button in `src/ui/overview.py` and add a CSV export button next to it:

```python
async def _export_csv():
    """Export positions as flat CSV."""
    import csv
    import io

    df = build_portfolio_df(portfolio, currency)
    if df.empty:
        ui.notify("No positions to export", type="warning")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticker", "Company", "Shares", "Buy Price", "Purchase Date",
                      "Current Price", "Total Value", "Dividends", "Day P&L",
                      "Return (%)", "Weight (%)"])
    for _, row in df.iterrows():
        writer.writerow([
            row.get("Ticker", ""),
            row.get("Company", ""),
            row.get("Shares", ""),
            row.get("Buy Price", ""),
            row.get("Purchase Date", ""),
            row.get("Current Price", ""),
            row.get("Total Value", ""),
            row.get("Dividends", ""),
            row.get("Day P&L", ""),
            row.get("Return (%)", ""),
            row.get("Weight (%)", ""),
        ])

    ui.download(output.getvalue().encode(), "portfolio.csv")

ui.button("Export CSV", on_click=_export_csv).props("flat dense").style(
    f"color: {TEXT_FAINT}; font-size: 12px;"
)
```

- [ ] **Step 2: Run app to verify**

Expected: "Export CSV" button appears next to Excel export. Clicking it downloads a CSV file.

- [ ] **Step 3: Commit**

```bash
git add src/ui/overview.py
git commit -m "feat: add CSV export button to overview"
```
