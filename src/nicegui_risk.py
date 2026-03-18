"""Risk & Analytics tab for the NiceGUI dashboard.

Renders risk metrics, correlation heatmap, and fundamentals tables
using NiceGUI widgets and Plotly charts.
"""

import pandas as pd
from nicegui import ui

from src.charts import (
    C_POSITIVE,
    C_NEGATIVE,
    C_AMBER,
    build_correlation_heatmap,
)
from src.data_fetch import fetch_analytics_history, fetch_fundamentals
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import compute_analytics
from src.theme import (
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_DIM,
    TEXT_FAINT,
    TEXT_SECONDARY,
    BG_CARD,
    BORDER,
    BORDER_SUBTLE,
    BG_TOPBAR,
    GREEN,
    RED,
    AMBER,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_header(title: str) -> None:
    """Render a styled section header matching the dashboard aesthetic."""
    ui.html(
        f'<div style="font-size:10px; font-weight:700; letter-spacing:0.12em; '
        f'text-transform:uppercase; color:{TEXT_MUTED}; margin:18px 0 8px 0;">'
        f'{title}</div>'
    )


def _section_intro(text: str) -> None:
    """Render explanatory text below a section header."""
    ui.html(
        f'<p style="font-size:12px; color:{TEXT_DIM}; line-height:1.6; '
        f'margin:0 0 12px 0;">{text}</p>'
    )


def _fmt(value, fmt_str: str, na: str = "\u2014") -> str:
    """Format a numeric value, returning a dash for None/NaN."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return na
    return fmt_str.format(value)


def _color_class(value, thresholds: list[tuple]) -> str:
    """Return a CSS class name based on threshold rules.

    thresholds: list of (test_fn, class_name) evaluated in order.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    for test_fn, cls in thresholds:
        if test_fn(value):
            return cls
    return ""


# ── Risk Metrics Table ───────────────────────────────────────────────────────

def _render_risk_table(analytics_df: pd.DataFrame) -> None:
    """Render the per-ticker risk metrics as a styled HTML table."""
    _section_header("Risk Metrics")
    _section_intro(
        "\u2022 <b>Volatility</b> \u2014 how much the price typically swings in a year. "
        "25% means it moves roughly \u00b125% over 12 months. Higher = more unpredictable.<br>"
        "\u2022 <b>Worst Drop</b> \u2014 the biggest fall from a peak in the past year. "
        "\u221235% means it dropped 35% from its highest point before recovering.<br>"
        "\u2022 <b>Return/Risk Score</b> \u2014 how much return you earned per unit of risk. "
        "Above 1 is good; above 2 is excellent; below 0 means the risk was not rewarded.<br>"
        "\u2022 <b>Market Sensitivity</b> \u2014 how much this stock moves when the S&P 500 moves. "
        "1.0 = moves exactly with the market; 1.5 = moves 50% more; 0.5 = half as much."
    )

    rows_html = ""
    for _, row in analytics_df.iterrows():
        ticker = row["Ticker"]
        vol = row.get("Volatility")
        dd = row.get("Max Drawdown")
        sharpe = row.get("Sharpe Ratio")
        beta = row.get("Beta")

        vol_cls = _color_class(vol, [
            (lambda v: v <= 20, "td-pos"),
            (lambda v: v <= 35, "td-amb"),
            (lambda v: True, "td-neg"),
        ])
        dd_cls = _color_class(dd, [
            (lambda v: v >= -20, "td-pos"),
            (lambda v: v >= -40, "td-amb"),
            (lambda v: True, "td-neg"),
        ])
        sharpe_cls = _color_class(sharpe, [
            (lambda v: v >= 1, "td-pos"),
            (lambda v: v >= 0, "td-amb"),
            (lambda v: True, "td-neg"),
        ])

        rows_html += (
            f'<tr>'
            f'<td style="font-weight:600;">{ticker}</td>'
            f'<td class="{vol_cls}">{_fmt(vol, "{:.1f}%")}</td>'
            f'<td class="{dd_cls}">{_fmt(dd, "{:.1f}%")}</td>'
            f'<td class="{sharpe_cls}">{_fmt(sharpe, "{:.2f}")}</td>'
            f'<td>{_fmt(beta, "{:.2f}")}</td>'
            f'</tr>'
        )

    ui.html(f'''
    <style>
        .td-pos {{ color: {GREEN}; font-weight: 600; }}
        .td-neg {{ color: {RED}; font-weight: 600; }}
        .td-amb {{ color: {AMBER}; font-weight: 600; }}
    </style>
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Ticker</th>
            <th>Volatility (%)</th>
            <th>Worst Drop (%)</th>
            <th>Return / Risk Score</th>
            <th>Beta (vs S&amp;P)</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    ''')


# ── Correlation Heatmap ─────────────────────────────────────────────────────

def _render_correlation_heatmap(price_data: dict, tickers: list) -> None:
    """Render the pairwise correlation matrix as a Plotly heatmap."""
    _section_header("How Your Stocks Move Together")
    _section_intro(
        "Shows how closely your positions move in sync. "
        "<b>1.0</b> = always move in the same direction at the same time. "
        "<b>\u22121.0</b> = always move in opposite directions. "
        "<b>0</b> = no relationship at all. "
        "Holding stocks that don\u2019t all move together reduces your overall risk \u2014 "
        "if one falls, the others may not. "
        "<i>Note: uses 1-year daily returns; the Excel export uses a 6-month window.</i>"
    )

    returns = {
        t: price_data[t]["Close"].pct_change().dropna()
        for t in tickers
        if not price_data.get(t, pd.DataFrame()).empty
    }
    if len(returns) < 2:
        ui.html(
            f'<p style="color:{TEXT_DIM}; font-size:12px;">'
            f'Need at least 2 tickers with price data to show correlations.</p>'
        )
        return

    corr_df = pd.DataFrame(returns).dropna().corr()
    fig = build_correlation_heatmap(corr_df)
    ui.plotly(fig).classes("w-full")


# ── Fundamentals Table ───────────────────────────────────────────────────────

def _render_fundamentals_table(fund_rows: list, currency_symbol: str) -> None:
    """Render the fundamentals (P/E, Div Yield, 52-week range) as a styled HTML table."""
    _section_header("Valuation & Price Range")
    _section_intro(
        "\u2022 <b>P/E Ratio</b> \u2014 how much investors pay relative to what the company earns. "
        "A P/E of 20 means you pay 20\u00d7 the company\u2019s annual earnings per share. "
        "Lower can mean better value, but varies widely by industry.<br>"
        "\u2022 <b>Dividend Yield</b> \u2014 the annual cash payment as a % of the current price. "
        "3% means every $100 invested pays $3/year directly to you, regardless of whether "
        "the stock price moves.<br>"
        "\u2022 <b>1-Year Low / High</b> \u2014 the cheapest and most expensive the stock has been "
        "over the past 12 months.<br>"
        "\u2022 <b>1-Year Position</b> \u2014 where the current price sits in that range. "
        "100% = at the yearly high; 0% = at the yearly low."
    )

    if not fund_rows:
        ui.html(
            f'<p style="color:{TEXT_DIM}; font-size:12px;">'
            f'No fundamentals data available.</p>'
        )
        return

    rows_html = ""
    for row in fund_rows:
        ticker = row.get("Ticker", "")
        pe = row.get("P/E Ratio")
        div_yield = row.get("Div Yield (%)")
        low = row.get("1-Year Low")
        high = row.get("1-Year High")
        position = row.get("1-Year Position")

        # Clamp position to 100%
        if position is not None:
            position = min(position, 100.0)

        # Build a mini progress bar for 1-Year Position
        if position is not None:
            bar_color = GREEN if position >= 50 else AMBER if position >= 25 else RED
            pos_cell = (
                f'<div style="display:flex; align-items:center; gap:8px;">'
                f'<div style="flex:1; height:6px; background:rgba(255,255,255,0.08); '
                f'border-radius:3px; overflow:hidden;">'
                f'<div style="width:{position:.0f}%; height:100%; background:{bar_color}; '
                f'border-radius:3px;"></div></div>'
                f'<span style="font-size:11px; min-width:36px; text-align:right;">'
                f'{position:.0f}%</span></div>'
            )
        else:
            pos_cell = "\u2014"

        rows_html += (
            f'<tr>'
            f'<td style="font-weight:600;">{ticker}</td>'
            f'<td>{_fmt(pe, "{:.1f}")}</td>'
            f'<td>{_fmt(div_yield, "{:.2f}%")}</td>'
            f'<td>{_fmt(low, "{currency_symbol}{:.2f}")}</td>'
            f'<td>{_fmt(high, "{currency_symbol}{:.2f}")}</td>'
            f'<td style="min-width:120px;">{pos_cell}</td>'
            f'</tr>'
        )

    ui.html(f'''
    <div class="table-wrap">
    <table>
        <thead><tr>
            <th>Ticker</th>
            <th>P/E Ratio</th>
            <th>Div Yield (%)</th>
            <th>1-Year Low</th>
            <th>1-Year High</th>
            <th>1-Year Position</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    ''')


# ── Public entry point ───────────────────────────────────────────────────────

def build_risk_tab(portfolio: dict, currency: str) -> None:
    """Render the full Risk & Analytics tab content using NiceGUI widgets.

    Parameters
    ----------
    portfolio : dict
        Mapping of ticker -> list of lot dicts (the session portfolio).
    currency : str
        Base display currency code, e.g. "USD", "GBP", "EUR".
    """
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")
    tickers = list(portfolio.keys())

    if not tickers:
        ui.html(
            f'<p style="color:{TEXT_DIM}; font-size:13px; padding:20px 0;">'
            f'Add positions to your portfolio to see risk analytics.</p>'
        )
        return

    _section_intro(
        "A deeper look at how risky your positions are and how efficiently "
        "they\u2019ve rewarded that risk. All figures are based on the past 12 months "
        "of daily price data. This section uses financial industry-standard "
        "metrics \u2014 each one is explained below its table."
    )

    # ── Fetch data ───────────────────────────────────────────────────────
    price_data_1y: dict[str, pd.DataFrame] = {}
    for t in tickers:
        hist = fetch_analytics_history(t)
        if not hist.empty:
            price_data_1y[t] = hist

    # SPY benchmark for beta calculation
    spy_data = fetch_analytics_history("SPY")

    # Compute analytics (volatility, drawdown, sharpe, beta)
    analytics_df = compute_analytics(portfolio, price_data_1y, spy_data)

    # Fetch fundamentals per ticker
    fund_rows: list[dict] = []
    for t in tickers:
        info = fetch_fundamentals(t)
        if info:
            fx_rate = get_fx_rate(get_ticker_currency(t), currency)
            row = {"Ticker": t}
            row["P/E Ratio"] = info.get("P/E Ratio")
            row["Div Yield (%)"] = info.get("Div Yield (%)")
            low = info.get("1-Year Low")
            high = info.get("1-Year High")
            row["1-Year Low"] = round(low * fx_rate, 2) if low is not None else None
            row["1-Year High"] = round(high * fx_rate, 2) if high is not None else None
            row["1-Year Position"] = info.get("1-Year Position")
            fund_rows.append(row)

    # ── Layout: risk metrics + correlation heatmap side by side ───────
    has_corr = len(tickers) >= 2

    if not analytics_df.empty:
        if has_corr:
            with ui.row().classes("w-full").style("gap:14px; align-items:flex-start;"):
                with ui.column().classes("w-full").style("flex:1; min-width:0;"):
                    _render_risk_table(analytics_df)
                with ui.column().classes("w-full").style("flex:1; min-width:0;"):
                    _render_correlation_heatmap(price_data_1y, tickers)
        else:
            _render_risk_table(analytics_df)

    # ── Fundamentals table (full width) ──────────────────────────────
    _render_fundamentals_table(fund_rows, currency_symbol)
