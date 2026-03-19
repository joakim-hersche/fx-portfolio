"""Income tab — dividend KPIs, income growth chart, calendar, per-position table."""

import calendar as cal
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
from nicegui import run, ui

from src.data_fetch import fetch_fundamentals
from src.fx import CURRENCY_SYMBOLS, get_fx_rate, get_ticker_currency
from src.portfolio import build_dividend_timeline, build_portfolio_df
from src.theme import (
    ACCENT,
    BG_CARD,
    BG_PILL,
    BORDER,
    BORDER_SUBTLE,
    GREEN,
    RED,
    TEXT_DIM,
    TEXT_FAINT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _fmt_currency(value: float, symbol: str) -> str:
    """Format a currency value with thousands separator."""
    if abs(value) >= 1000:
        return f"{symbol}{value:,.0f}"
    return f"{symbol}{value:,.2f}"


def _month_add(year: int, month: int, delta: int) -> tuple[int, int]:
    """Add *delta* months to (year, month), returning (new_year, new_month)."""
    m = year * 12 + (month - 1) + delta
    return divmod(m, 12)[0], divmod(m, 12)[1] + 1


def _infer_frequency(payment_months: list[int]) -> int | None:
    """Infer dividend frequency from a list of payment month numbers.

    Returns the gap in months (1=monthly, 3=quarterly, 6=semi, 12=annual)
    or None if no pattern can be determined.
    """
    if len(payment_months) < 2:
        return None
    unique = sorted(set(payment_months))
    if len(unique) < 2:
        return None
    gaps = [unique[i + 1] - unique[i] for i in range(len(unique) - 1)]
    # Also handle wrap-around (Dec -> next year's month)
    gaps.append(12 - unique[-1] + unique[0])
    # Most common gap
    from collections import Counter
    counter = Counter(gaps)
    most_common_gap = counter.most_common(1)[0][0]
    if most_common_gap in (1, 2, 3, 4, 6, 12):
        return most_common_gap
    return None


# ── Main builder ─────────────────────────────────────────────────────────────


async def build_income_tab(
    portfolio: dict,
    currency: str,
    portfolio_color_map: dict[str, str],
) -> None:
    """Build the full Income tab content."""
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")

    if not portfolio:
        ui.html("""
            <div class="kpi-row" style="grid-template-columns:1fr 1fr 1fr;">
                <div class="kpi-card">
                    <div class="kpi-label">Trailing 12M Income</div>
                    <div class="kpi-value">&mdash;</div>
                    <div class="kpi-sub">Add positions to get started</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Projected Annual Income</div>
                    <div class="kpi-value">&mdash;</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Portfolio Yield</div>
                    <div class="kpi-value">&mdash;</div>
                </div>
            </div>
        """).classes("w-full")
        return

    notification = ui.notification("Loading income data...", spinner=True, timeout=None)

    try:
        # Fetch data off the UI thread
        df, timeline, fund_map = await run.io_bound(
            _fetch_income_data, portfolio, currency,
        )
    except Exception:
        df, timeline, fund_map = pd.DataFrame(), [], {}
    finally:
        notification.dismiss()

    if df is None or df.empty:
        ui.label("Unable to load portfolio data.").style(f"color:{TEXT_MUTED};")
        return

    # ── Compute KPI values ────────────────────────────────
    today = pd.Timestamp.today()
    twelve_months_ago = (today - pd.DateOffset(months=12)).strftime("%Y-%m")

    trailing_12m = sum(
        r["amount"] for r in timeline if r["month"] >= twelve_months_ago
    )

    # Projected annual income from Dividend Rate * shares * FX
    # dividendRate is in financialCurrency (not necessarily the trading currency)
    projected_annual = 0.0
    for ticker, lots in portfolio.items():
        total_shares = sum(lot["shares"] for lot in lots)
        fund = fund_map.get(ticker, {})
        div_rate = fund.get("Dividend Rate")
        if not div_rate or div_rate <= 0:
            continue
        div_ccy = fund.get("Financial Currency") or get_ticker_currency(ticker)
        fx_rate, _ = get_fx_rate(div_ccy, currency)
        projected_annual += div_rate * total_shares * fx_rate

    total_value = df.groupby("Ticker")["Total Value"].sum().sum()
    portfolio_yield = (projected_annual / total_value * 100) if total_value > 0 else 0.0

    # ── KPI Cards ─────────────────────────────────────────
    ui.html(f"""
        <div class="kpi-row" style="grid-template-columns:1fr 1fr 1fr;">
            <div class="kpi-card">
                <div class="kpi-label">Trailing 12M Income</div>
                <div class="kpi-value">{_fmt_currency(trailing_12m, currency_symbol)}</div>
                <div class="kpi-sub">Dividends received last 12 months</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Projected Annual Income*</div>
                <div class="kpi-value">{_fmt_currency(projected_annual, currency_symbol)}</div>
                <div class="kpi-sub">Assumes current rates continue</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Forward Dividend Yield</div>
                <div class="kpi-value">{portfolio_yield:.2f}%</div>
                <div class="kpi-sub">Projected income / portfolio value</div>
            </div>
        </div>
    """).classes("w-full")

    ui.html(
        f'<p style="font-size:10px;color:{TEXT_FAINT};margin:4px 0 0 0;">'
        '*Projected figures assume current dividend rates continue. '
        'Companies may cut, suspend, or increase dividends at any time.</p>'
    ).classes("w-full")

    # ── Income Growth Chart ───────────────────────────────
    _build_income_chart(timeline, portfolio_color_map, currency_symbol)

    # ── Dividend Calendar ─────────────────────────────────
    _build_dividend_calendar(timeline, portfolio, portfolio_color_map, currency_symbol)

    # ── Per-Position Income Table ─────────────────────────
    _build_income_table(portfolio, df, fund_map, currency, currency_symbol, portfolio_color_map)


def _fetch_income_data(
    portfolio: dict, currency: str,
) -> tuple[pd.DataFrame, list[dict], dict]:
    """Fetch all income-related data (runs in a thread)."""
    df = build_portfolio_df(portfolio, currency)
    timeline = build_dividend_timeline(portfolio, currency, months_back=24)

    # Fetch fundamentals in parallel
    tickers = list(portfolio.keys())

    def _fetch_fund(t):
        return t, fetch_fundamentals(t)

    fund_map = {}
    with ThreadPoolExecutor(max_workers=min(10, len(tickers))) as ex:
        for ticker, fund in ex.map(lambda t: _fetch_fund(t), tickers):
            fund_map[ticker] = fund

    return df, timeline, fund_map


def _build_income_chart(
    timeline: list[dict],
    color_map: dict[str, str],
    currency_symbol: str,
) -> None:
    """Stacked monthly bar chart with a 3-month rolling average trend line."""
    if not timeline:
        with ui.column().classes("chart-card w-full"):
            ui.html('<div class="chart-title">Income Growth</div>')
            ui.html(f'<p style="font-size:12px;color:{TEXT_MUTED};padding:20px 0;">No dividend history available.</p>')
        return

    # Aggregate by month + ticker
    month_ticker: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for r in timeline:
        month_ticker[r["month"]][r["ticker"]] += r["amount"]

    months = sorted(month_ticker.keys())
    tickers = sorted({r["ticker"] for r in timeline})

    # Build Plotly traces
    traces = []
    for ticker in tickers:
        values = [month_ticker[m].get(ticker, 0) for m in months]
        traces.append({
            "x": months,
            "y": values,
            "name": ticker,
            "type": "bar",
            "marker": {"color": color_map.get(ticker, "#3B82F6")},
            "hovertemplate": f"<b>{ticker}</b><br>%{{x}}<br>{currency_symbol}%{{y:,.2f}}<extra></extra>",
        })

    # 3-month rolling average
    monthly_totals = [sum(month_ticker[m].values()) for m in months]
    if len(monthly_totals) >= 3:
        rolling = []
        for i in range(len(monthly_totals)):
            if i < 2:
                rolling.append(None)
            else:
                rolling.append(round(sum(monthly_totals[i - 2 : i + 1]) / 3, 2))
        traces.append({
            "x": months,
            "y": rolling,
            "name": "3M Avg",
            "type": "scatter",
            "mode": "lines",
            "line": {"color": TEXT_PRIMARY, "width": 2, "dash": "dot"},
            "yaxis": "y",
            "hovertemplate": f"<b>3M Avg</b><br>%{{x}}<br>{currency_symbol}%{{y:,.2f}}<extra></extra>",
        })

    layout = {
        "barmode": "stack",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Inter, sans-serif", "size": 11, "color": TEXT_MUTED},
        "margin": {"l": 50, "r": 20, "t": 10, "b": 40},
        "xaxis": {
            "gridcolor": "rgba(255,255,255,0.04)",
            "tickfont": {"size": 10, "color": "#CBD5E1"},
        },
        "yaxis": {
            "gridcolor": "rgba(255,255,255,0.04)",
            "tickfont": {"size": 10, "color": "#CBD5E1"},
            "tickprefix": currency_symbol,
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom", "y": 1.02,
            "xanchor": "left", "x": 0,
            "font": {"size": 10, "color": "#94A3B8"},
            "bgcolor": "rgba(0,0,0,0)",
        },
        "hoverlabel": {
            "bgcolor": "#1C1D26",
            "bordercolor": "#1E293B",
            "font": {"family": "Inter, sans-serif", "size": 11, "color": "#F1F5F9"},
            "namelength": -1,
        },
        "modebar": {
            "bgcolor": "rgba(0,0,0,0)",
            "color": "#64748B",
            "activecolor": "#94A3B8",
        },
    }

    with ui.column().classes("chart-card w-full"):
        ui.html('<div class="chart-title">Income Growth</div>')
        ui.plotly({"data": traces, "layout": layout}).classes("w-full")


def _build_dividend_calendar(
    timeline: list[dict],
    portfolio: dict,
    color_map: dict[str, str],
    currency_symbol: str,
) -> None:
    """12-month forward calendar based on historical payment patterns."""
    today = pd.Timestamp.today()
    tickers = sorted(portfolio.keys())

    # Analyse historical payment months per ticker
    ticker_months: dict[str, list[int]] = defaultdict(list)
    ticker_last_amount: dict[str, tuple[str, float]] = {}  # ticker -> (month_key, amount)
    for r in timeline:
        month_num = int(r["month"][5:7])
        ticker_months[r["ticker"]].append(month_num)
        # Track latest payment per ticker (by month key)
        prev = ticker_last_amount.get(r["ticker"])
        if prev is None or r["month"] > prev[0]:
            ticker_last_amount[r["ticker"]] = (r["month"], r["amount"])

    # Build next 12 months
    future_months = []
    for i in range(1, 13):
        y, m = _month_add(today.year, today.month, i)
        future_months.append((y, m))

    # For each ticker, infer which future months will have payments
    calendar_data: dict[str, dict[str, str]] = {}  # ticker -> {month_key: amount_str}
    calendar_amounts: dict[str, dict[str, float]] = {}  # ticker -> {month_key: numeric amount}
    has_any_data = False

    for ticker in tickers:
        payments = ticker_months.get(ticker, [])
        if len(payments) < 2:
            calendar_data[ticker] = None
            continue

        freq = _infer_frequency(payments)
        if freq is None:
            calendar_data[ticker] = None
            continue

        # Which months does this ticker typically pay in?
        typical_months = sorted(set(payments))
        last_entry = ticker_last_amount.get(ticker)
        per_payment = round(last_entry[1], 2) if last_entry else 0

        projected: dict[str, str] = {}
        amounts: dict[str, float] = {}
        for y, m in future_months:
            key = f"{y}-{m:02d}"
            if m in typical_months and per_payment > 0:
                projected[key] = _fmt_currency(per_payment, currency_symbol)
                amounts[key] = per_payment
                has_any_data = True
            else:
                projected[key] = ""
                amounts[key] = 0.0
        calendar_data[ticker] = projected
        calendar_amounts[ticker] = amounts

    # Render as HTML table
    with ui.column().classes("chart-card w-full"):
        ui.html('<div class="chart-title">Dividend Calendar (12-Month Forward)</div>')
        ui.html(
            f'<p style="font-size:11px;color:{TEXT_DIM};margin:0 0 8px 0;">'
            'Estimated from historical payment patterns. Companies may change '
            'dividend dates and amounts at any time. Not a confirmed schedule.</p>'
        )

        if not has_any_data and all(v is None for v in calendar_data.values()):
            ui.html(
                f'<p style="font-size:12px;color:{TEXT_MUTED};padding:20px 0;">'
                "Insufficient dividend history to project a calendar. "
                "At least 2 historical payments per ticker are needed.</p>"
            )
            return

        month_headers = []
        for y, m in future_months:
            month_headers.append(f"{cal.month_abbr[m]}<br>{y}")

        header_cells = "".join(
            f'<th class="right" style="min-width:70px;">{mh}</th>' for mh in month_headers
        )

        rows_html = []
        for ticker in tickers:
            projected = calendar_data.get(ticker)
            dot_color = color_map.get(ticker, "#3B82F6")
            ticker_cell = (
                f'<td class="td-ticker">'
                f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
                f'background:{dot_color};margin-right:6px;"></span>{ticker}</td>'
            )
            if projected is None:
                cells = f'<td colspan="{len(future_months)}" class="right" style="color:{TEXT_FAINT};font-size:11px;">Insufficient history</td>'
            else:
                cells = ""
                for y, m in future_months:
                    key = f"{y}-{m:02d}"
                    val = projected.get(key, "")
                    style = f"color:{GREEN};font-weight:600;" if val and val != "--" else f"color:{TEXT_FAINT};"
                    cells += f'<td class="right" style="{style}">{val}</td>'
            rows_html.append(f"<tr>{ticker_cell}{cells}</tr>")

        # Totals row
        total_cells = ""
        for y, m in future_months:
            key = f"{y}-{m:02d}"
            month_total = sum(
                calendar_amounts.get(t, {}).get(key, 0.0) for t in tickers
            )
            if month_total > 0:
                total_cells += f'<td class="right" style="color:{TEXT_PRIMARY};font-weight:700;">{_fmt_currency(month_total, currency_symbol)}</td>'
            else:
                total_cells += f'<td class="right" style="color:{TEXT_FAINT};">\u2014</td>'
        rows_html.append(
            f'<tr style="border-top:2px solid {BORDER};">'
            f'<td style="color:{TEXT_PRIMARY};font-weight:700;">Total</td>'
            f'{total_cells}</tr>'
        )

        table_html = f"""
        <div class="table-wrap" style="margin-top:10px;">
            <table>
                <thead><tr><th>Ticker</th>{header_cells}</tr></thead>
                <tbody>{''.join(rows_html)}</tbody>
            </table>
        </div>
        """
        ui.html(table_html).classes("w-full")


def _build_income_table(
    portfolio: dict,
    df: pd.DataFrame,
    fund_map: dict,
    currency: str,
    currency_symbol: str,
    color_map: dict[str, str],
) -> None:
    """Per-position income table: annual income, yield, yield-on-cost."""
    with ui.column().classes("chart-card w-full"):
        ui.html('<div class="chart-title">Per-Position Income</div>')

        rows_html = []
        for ticker in sorted(portfolio.keys()):
            fund = fund_map.get(ticker, {})
            div_rate = fund.get("Dividend Rate")
            div_yield = fund.get("Div Yield (%)")

            ticker_df = df[df["Ticker"] == ticker]
            if ticker_df.empty:
                continue

            total_shares = ticker_df["Shares"].sum()
            total_value = ticker_df["Total Value"].sum()
            cost_basis = (ticker_df["Buy Price"] * ticker_df["Shares"]).sum()

            div_ccy = fund.get("Financial Currency") or get_ticker_currency(ticker)
            fx_rate, _ = get_fx_rate(div_ccy, currency)

            if div_rate and div_rate > 0:
                annual_income = div_rate * total_shares * fx_rate
                yield_on_cost = (annual_income / cost_basis * 100) if cost_basis > 0 else 0.0
            else:
                annual_income = 0.0
                yield_on_cost = 0.0

            dot_color = color_map.get(ticker, "#3B82F6")
            income_str = _fmt_currency(annual_income, currency_symbol)
            yield_str = f"{div_yield:.2f}%" if div_yield else "--"
            yoc_str = f"{yield_on_cost:.2f}%" if yield_on_cost > 0 else "--"
            yield_color = TEXT_SECONDARY
            yoc_color = TEXT_SECONDARY

            rows_html.append(f"""
                <tr>
                    <td class="td-ticker">
                        <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                        background:{dot_color};margin-right:6px;"></span>{ticker}
                    </td>
                    <td class="right">{total_shares:,.0f}</td>
                    <td class="right">{income_str}</td>
                    <td class="right" style="color:{yield_color};">{yield_str}</td>
                    <td class="right" style="color:{yoc_color};">{yoc_str}</td>
                </tr>
            """)

        if not rows_html:
            ui.html(f'<p style="font-size:12px;color:{TEXT_MUTED};padding:10px 0;">No dividend-paying positions.</p>')
            return

        # Totals row
        total_annual = 0.0
        total_cost = 0.0
        total_val = 0.0
        for ticker in portfolio:
            fund = fund_map.get(ticker, {})
            div_rate = fund.get("Dividend Rate")
            ticker_df = df[df["Ticker"] == ticker]
            if ticker_df.empty:
                continue
            total_shares = ticker_df["Shares"].sum()
            cost_basis = (ticker_df["Buy Price"] * ticker_df["Shares"]).sum()
            total_cost += cost_basis
            total_val += ticker_df["Total Value"].sum()
            if div_rate and div_rate > 0:
                div_ccy = fund.get("Financial Currency") or get_ticker_currency(ticker)
                fx_rate, _ = get_fx_rate(div_ccy, currency)
                total_annual += div_rate * total_shares * fx_rate

        total_yield = (total_annual / total_val * 100) if total_val > 0 else 0
        total_yoc = (total_annual / total_cost * 100) if total_cost > 0 else 0

        table_html = f"""
        <div class="table-wrap" style="margin-top:10px;">
            <table>
                <thead>
                    <tr>
                        <th>Ticker</th>
                        <th class="right">Shares</th>
                        <th class="right">Annual Income</th>
                        <th class="right">Yield</th>
                        <th class="right">Yield on Cost</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(rows_html)}
                    <tr style="border-top:2px solid {BORDER};font-weight:700;">
                        <td style="color:{TEXT_PRIMARY};">Total</td>
                        <td></td>
                        <td class="right" style="color:{TEXT_PRIMARY};">{_fmt_currency(total_annual, currency_symbol)}</td>
                        <td class="right" style="color:{TEXT_PRIMARY};">{total_yield:.2f}%</td>
                        <td class="right" style="color:{TEXT_PRIMARY};">{total_yoc:.2f}%</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """
        ui.html(table_html).classes("w-full")
