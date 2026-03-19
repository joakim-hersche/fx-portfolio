"""Risk & Analytics tab for the NiceGUI dashboard.

Renders risk metrics, correlation heatmap, and fundamentals tables
using NiceGUI widgets and Plotly charts.
"""

import pandas as pd
from nicegui import run, ui

from src.charts import (
    CHART_COLORS,
    C_POSITIVE,
    C_NEGATIVE,
    C_AMBER,
    build_correlation_heatmap,
)
from src.stocks import TICKER_COLORS
from src.data_fetch import fetch_analytics_history, fetch_fundamentals
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df, compute_analytics
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

def _render_risk_table(analytics_df: pd.DataFrame, color_map: dict[str, str] | None = None) -> None:
    """Render the per-ticker risk metrics as a styled HTML table."""
    with ui.column().classes("chart-card w-full"):
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

            dot_color = (color_map or {}).get(ticker, "")
            dot_html = (
                f'<div style="width:8px;height:8px;border-radius:50%;background:{dot_color};flex-shrink:0;display:inline-block;margin-right:6px;vertical-align:middle;"></div>'
                if dot_color else ""
            )

            rows_html += (
                f'<tr>'
                f'<td><div class="td-ticker">{dot_html}{ticker}</div></td>'
                f'<td class="{vol_cls} right">{_fmt(vol, "{:.1f}%")}</td>'
                f'<td class="{dd_cls} right">{_fmt(dd, "{:.1f}%")}</td>'
                f'<td class="{sharpe_cls} right">{_fmt(sharpe, "{:.2f}")}</td>'
                f'<td class="right">{_fmt(beta, "{:.2f}")}</td>'
                f'</tr>'
            )

        ui.html(f'''
        <div class="table-wrap">
        <table>
            <thead><tr>
                <th scope="col">Ticker</th>
                <th scope="col" class="right">Volatility (%)</th>
                <th scope="col" class="right">Worst Drop (%)</th>
                <th scope="col" class="right">Return / Risk Score</th>
                <th scope="col" class="right">Beta (vs S&amp;P)</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        ''')


# ── Correlation Heatmap ─────────────────────────────────────────────────────

def _render_correlation_heatmap(price_data: dict, tickers: list) -> None:
    """Render the pairwise correlation matrix as a Plotly heatmap."""
    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{TEXT_MUTED};">Correlation Matrix</div>'
            f'<div style="font-size:10px;color:{TEXT_DIM};">12-month rolling</div>'
            f'</div>'
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

def _render_fundamentals_table(fund_rows: list, currency_symbol: str, color_map: dict[str, str] | None = None) -> None:
    """Render the fundamentals (P/E, Div Yield, 52-week range) as a styled HTML table."""
    with ui.column().classes("chart-card w-full"):
        _section_header("Valuation & Price Range")
        _section_intro(
            "\u2022 <b>P/E Ratio</b> \u2014 how much investors pay relative to what the company earns. "
            "A P/E of 20 means you pay 20\u00d7 the company\u2019s annual earnings per share. "
            "Lower can mean better value, but varies widely by industry.<br>"
            "\u2022 <b>Div. Yield</b> \u2014 the annual cash payment as a % of the current price. "
            "3% means every $100 invested pays $3/year directly to you, regardless of whether "
            "the stock price moves.<br>"
            "\u2022 <b>52-Week Range</b> \u2014 the cheapest and most expensive the stock has been "
            "over the past 12 months, shown as a visual bar with the current price marked.<br>"
            "\u2022 <b>Current</b> \u2014 the latest market price for each position."
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
            current = row.get("Current Price")

            # Clamp position to 100%
            if position is not None:
                position = min(position, 100.0)

            # Build 52-Week Range cell with visual bar
            if low is not None and high is not None and position is not None:
                range_cell = (
                    f'<td style="min-width:180px;padding-right:14px;">'
                    f'<div style="display:flex;align-items:center;gap:4px;">'
                    f'<span style="font-size:10px;color:{TEXT_DIM};">{currency_symbol}{low:.0f}</span>'
                    f'<div class="range-bar-bg" style="flex:1;">'
                    f'<div class="range-bar-fill" style="left:0;width:100%;"></div>'
                    f'<div class="range-bar-dot" style="left:{position}%;"></div>'
                    f'</div>'
                    f'<span style="font-size:10px;color:{TEXT_DIM};">{currency_symbol}{high:.0f}</span>'
                    f'</div></td>'
                )
            else:
                range_cell = '<td>\u2014</td>'

            # Current price cell
            if current is not None:
                current_cell = f'<td class="right" style="font-weight:600;">{currency_symbol}{current:.2f}</td>'
            else:
                current_cell = '<td class="right">\u2014</td>'

            dot_color = (color_map or {}).get(ticker, "")
            dot_html = (
                f'<div style="width:8px;height:8px;border-radius:50%;background:{dot_color};flex-shrink:0;display:inline-block;margin-right:6px;vertical-align:middle;"></div>'
                if dot_color else ""
            )

            rows_html += (
                f'<tr>'
                f'<td><div class="td-ticker">{dot_html}{ticker}</div></td>'
                f'<td class="right">{_fmt(pe, "{:.1f}\u00d7")}</td>'
                f'<td class="right">{_fmt(div_yield, "{:.2f}%")}</td>'
                f'{range_cell}'
                f'{current_cell}'
                f'</tr>'
            )

        ui.html(f'''
        <div class="table-wrap">
        <table>
            <thead><tr>
                <th scope="col">Ticker</th>
                <th scope="col" class="right">P/E Ratio</th>
                <th scope="col" class="right">Div. Yield</th>
                <th scope="col">52-Week Range</th>
                <th scope="col" class="right">Current</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        ''')


# ── Performance Attribution ────────────────────────────────────────────────

def _render_performance_attribution(
    portfolio_df: pd.DataFrame,
    price_data_1y: dict[str, pd.DataFrame],
    color_map: dict[str, str] | None = None,
    base_currency: str = "USD",
) -> None:
    """Render the Performance Attribution table matching the design proposal."""
    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{TEXT_MUTED};">Performance Attribution</div>'
            f'<div style="font-size:10px;color:{TEXT_DIM};">Period: 1 Year</div>'
            f'</div>'
        )

        if portfolio_df.empty:
            ui.html(
                f'<p style="color:{TEXT_DIM}; font-size:12px;">'
                f'No data available for performance attribution.</p>'
            )
            return

        # Compute per-ticker aggregated data
        ticker_data = (
            portfolio_df.groupby("Ticker")
            .agg({"Total Value": "sum", "Weight (%)": "sum", "Return (%)": "first"})
            .reset_index()
        )

        # For multi-lot tickers, compute a weighted return
        for idx, row in ticker_data.iterrows():
            ticker = row["Ticker"]
            group = portfolio_df[portfolio_df["Ticker"] == ticker]
            if len(group) > 1:
                total_cost = (group["Buy Price"] * group["Shares"]).sum()
                total_value = group["Total Value"].sum()
                total_divs = group["Dividends"].sum()
                if total_cost > 0:
                    ticker_data.at[idx, "Return (%)"] = round(
                        (total_value + total_divs - total_cost) / total_cost * 100, 2
                    )

        # Compute SPY 1-year return from price data, adjusted for FX
        spy_hist = price_data_1y.get("__spy__", pd.DataFrame())
        spy_return = None
        if not spy_hist.empty and "Close" in spy_hist.columns:
            spy_close = spy_hist["Close"].dropna()
            if len(spy_close) >= 2:
                spy_return_usd = (spy_close.iloc[-1] / spy_close.iloc[0] - 1) * 100
                if base_currency != "USD":
                    # Adjust for USD->base_currency FX change over the same period
                    try:
                        import yfinance as yf
                        from src.cache import yf_session
                        fx_pair = f"USD{base_currency}=X"
                        fx_hist = yf.Ticker(fx_pair, session=yf_session).history(period="1y")
                        if not fx_hist.empty and "Close" in fx_hist.columns:
                            fx_close = fx_hist["Close"].dropna()
                            if len(fx_close) >= 2:
                                fx_change = (fx_close.iloc[-1] / fx_close.iloc[0] - 1) * 100
                                spy_return = ((1 + spy_return_usd / 100) * (1 + fx_change / 100) - 1) * 100
                            else:
                                spy_return = spy_return_usd
                        else:
                            spy_return = spy_return_usd
                    except Exception:
                        spy_return = spy_return_usd
                else:
                    spy_return = spy_return_usd

        # Compute 1-year price return per ticker from price history (more accurate than portfolio return)
        ticker_1y_return: dict[str, float] = {}
        for t in ticker_data["Ticker"]:
            hist = price_data_1y.get(t, pd.DataFrame())
            if not hist.empty and "Close" in hist.columns:
                close = hist["Close"].dropna()
                if len(close) >= 2:
                    ticker_1y_return[t] = round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2)

        rows_html = ""
        for _, row in ticker_data.iterrows():
            ticker = row["Ticker"]
            weight = row["Weight (%)"]
            pos_return = ticker_1y_return.get(ticker, row["Return (%)"])
            contribution = round(weight * pos_return / 100, 2) if pd.notna(pos_return) else None

            vs_bench = None
            if pos_return is not None and spy_return is not None:
                vs_bench = round(pos_return - spy_return, 2)

            dot_color = (color_map or {}).get(ticker, "")
            dot_html = (
                f'<div style="width:8px;height:8px;border-radius:50%;background:{dot_color};flex-shrink:0;display:inline-block;margin-right:6px;vertical-align:middle;"></div>'
                if dot_color else ""
            )

            ret_cls = "td-pos" if pos_return and pos_return > 0 else "td-neg" if pos_return and pos_return < 0 else ""
            contrib_cls = "td-pos" if contribution and contribution > 0 else "td-neg" if contribution and contribution < 0 else ""
            bench_cls = "td-pos" if vs_bench and vs_bench > 0 else "td-neg" if vs_bench and vs_bench < 0 else ""

            rows_html += (
                f'<tr>'
                f'<td><div class="td-ticker">{dot_html}{ticker}</div></td>'
                f'<td class="right">{weight:.1f}%</td>'
                f'<td class="{ret_cls} right">{_fmt(pos_return, "{:+.1f}%")}</td>'
                f'<td class="{contrib_cls} right">{_fmt(contribution, "{:+.2f}%")}</td>'
                f'<td class="{bench_cls} right">{_fmt(vs_bench, "{:+.1f}%")}</td>'
                f'</tr>'
            )

        ui.html(f'''
        <div class="table-wrap">
        <table>
            <thead><tr>
                <th scope="col">Ticker</th>
                <th scope="col" class="right">Weight %</th>
                <th scope="col" class="right">Position Return %</th>
                <th scope="col" class="right">Contribution %</th>
                <th scope="col" class="right">vs. SPY</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        ''')


# ── Public entry point ───────────────────────────────────────────────────────

async def build_risk_tab(portfolio: dict, currency: str) -> None:
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

    # ── Fetch data (off the event loop) ──────────────────────────────────
    def _fetch_risk_data():
        from concurrent.futures import ThreadPoolExecutor

        # Fetch all analytics histories + SPY in parallel
        all_tickers = tickers + ["SPY"]
        with ThreadPoolExecutor(max_workers=min(10, len(all_tickers))) as ex:
            hist_results = dict(ex.map(lambda t: (t, fetch_analytics_history(t)), all_tickers))

        price_data_1y: dict[str, pd.DataFrame] = {}
        for t in tickers:
            hist = hist_results.get(t, pd.DataFrame())
            if not hist.empty:
                price_data_1y[t] = hist
        spy_data = hist_results.get("SPY", pd.DataFrame())
        if not spy_data.empty:
            price_data_1y["__spy__"] = spy_data
        analytics_df = compute_analytics(portfolio, price_data_1y, spy_data)
        portfolio_df = build_portfolio_df(portfolio, currency)

        # Fetch fundamentals in parallel
        with ThreadPoolExecutor(max_workers=min(10, len(tickers))) as ex:
            fund_results = dict(ex.map(lambda t: (t, fetch_fundamentals(t)), tickers))

        fund_rows: list[dict] = []
        for t in tickers:
            info = fund_results.get(t)
            if info:
                fx_rate, _ = get_fx_rate(get_ticker_currency(t), currency)
                row = {"Ticker": t}
                row["P/E Ratio"] = info.get("P/E Ratio")
                row["Div Yield (%)"] = info.get("Div Yield (%)")
                low = info.get("1-Year Low")
                high = info.get("1-Year High")
                row["1-Year Low"] = round(low * fx_rate, 2) if low is not None else None
                row["1-Year High"] = round(high * fx_rate, 2) if high is not None else None
                row["1-Year Position"] = info.get("1-Year Position")
                cur_price = info.get("Current Price")
                row["Current Price"] = round(cur_price * fx_rate, 2) if cur_price is not None else None
                fund_rows.append(row)
        return price_data_1y, analytics_df, fund_rows, portfolio_df

    result = await run.io_bound(_fetch_risk_data)
    if result is None:
        ui.html(f'<div style="color:{TEXT_DIM};font-size:13px;padding:24px;">'
                'Could not load risk data. Please try reloading the page.</div>')
        return
    price_data_1y, analytics_df, fund_rows, portfolio_df = result

    # Build color map for dot indicators
    portfolio_color_map: dict[str, str] = {
        t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
        for i, t in enumerate(portfolio.keys())
    }

    has_corr = len(tickers) >= 2

    # ── Row 1: Attribution + Risk Metrics side by side ──────────────
    with ui.element("div").classes("risk-grid"):
        with ui.column().classes("w-full"):
            _render_performance_attribution(portfolio_df, price_data_1y, portfolio_color_map, base_currency=currency)
        with ui.column().classes("w-full"):
            if not analytics_df.empty:
                _render_risk_table(analytics_df, portfolio_color_map)

    # ── Row 2: Correlation + Fundamentals side by side ──────────────
    with ui.element("div").classes("risk-grid"):
        with ui.column().classes("w-full"):
            if has_corr:
                _render_correlation_heatmap(price_data_1y, tickers)
        with ui.column().classes("w-full"):
            _render_fundamentals_table(fund_rows, currency_symbol, portfolio_color_map)
