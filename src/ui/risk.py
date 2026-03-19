"""Risk & Analytics tab for the NiceGUI dashboard.

Renders a unified portfolio analytics table with expandable detail rows,
plus a correlation heatmap, using NiceGUI widgets and Plotly charts.
"""

import numpy as np
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
    BG_PILL,
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


# ── Unified Portfolio Analytics Table ────────────────────────────────────────

def _render_unified_table(
    portfolio_df: pd.DataFrame,
    analytics_df: pd.DataFrame,
    fund_rows: list[dict],
    price_data_1y: dict[str, pd.DataFrame],
    currency_symbol: str,
    color_map: dict[str, str] | None = None,
    base_currency: str = "USD",
) -> None:
    """Render a single expandable table combining performance, risk, and fundamentals."""
    with ui.column().classes("chart-card w-full"):
        # Header with subtitle
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{TEXT_MUTED};">Portfolio Analytics</div>'
            f'<div style="font-size:10px;color:{TEXT_DIM};">Click a row for risk &amp; valuation details</div>'
            f'</div>'
        )

        # Combined intro text
        _section_intro(
            "<b>Performance</b> \u2014 weight, 1-year price return, portfolio contribution, "
            "and relative performance vs. the S&P 500 (adjusted for currency).<br>"
            "<b>Risk</b> \u2014 annualised volatility, worst peak-to-trough drop, "
            "return-per-unit-of-risk score, and market sensitivity (beta).<br>"
            "<b>Valuation</b> \u2014 price/earnings ratio, dividend yield, "
            "52-week price range with current position, and latest market price."
        )

        if portfolio_df.empty:
            ui.html(
                f'<p style="color:{TEXT_DIM}; font-size:12px;">'
                f'No data available for portfolio analytics.</p>'
            )
            return

        # ── Compute per-ticker aggregated data (from _render_performance_attribution) ──
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
                        fx_pair = f"USD{base_currency}=X"
                        fx_hist = yf.Ticker(fx_pair).history(period="1y")
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

        # Compute 1-year price return per ticker from price history
        ticker_1y_return: dict[str, float] = {}
        for t in ticker_data["Ticker"]:
            hist = price_data_1y.get(t, pd.DataFrame())
            if not hist.empty and "Close" in hist.columns:
                close = hist["Close"].dropna()
                if len(close) >= 2:
                    ticker_1y_return[t] = round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2)

        # ── Build analytics and fundamentals lookups ──
        analytics_map: dict[str, dict] = {}
        if not analytics_df.empty:
            for _, arow in analytics_df.iterrows():
                analytics_map[arow["Ticker"]] = {
                    "Volatility": arow.get("Volatility"),
                    "Max Drawdown": arow.get("Max Drawdown"),
                    "Sharpe Ratio": arow.get("Sharpe Ratio"),
                    "Beta": arow.get("Beta"),
                }

        fund_map: dict[str, dict] = {}
        for frow in fund_rows:
            fund_map[frow["Ticker"]] = frow

        num_tickers = len(ticker_data)
        auto_expand = num_tickers == 1

        # ── Build table rows ──
        rows_html = ""
        for _, row in ticker_data.iterrows():
            ticker = row["Ticker"]
            safe_id = ticker.replace(".", "_")
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

            chevron = "\u25BC" if auto_expand else "\u25B6"

            rows_html += (
                f'<tr onclick="toggleDetail(\'{safe_id}\')" style="cursor:pointer;">'
                f'<td><div class="td-ticker">{dot_html}'
                f'<span id="chev-{safe_id}" style="font-size:8px;margin-right:5px;color:{TEXT_DIM};">{chevron}</span>'
                f'{ticker}</div></td>'
                f'<td class="right">{weight:.1f}%</td>'
                f'<td class="{ret_cls} right">{_fmt(pos_return, "{:+.1f}%")}</td>'
                f'<td class="{contrib_cls} right">{_fmt(contribution, "{:+.2f}%")}</td>'
                f'<td class="{bench_cls} right">{_fmt(vs_bench, "{:+.1f}%")}</td>'
                f'</tr>'
            )

            # ── Detail sub-row ──
            detail_display = "table-row" if auto_expand else "none"

            # Risk data
            a = analytics_map.get(ticker, {})
            vol = a.get("Volatility")
            dd = a.get("Max Drawdown")
            sharpe = a.get("Sharpe Ratio")
            beta = a.get("Beta")

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

            # Fundamentals data
            f_data = fund_map.get(ticker, {})
            pe = f_data.get("P/E Ratio")
            div_yield = f_data.get("Div Yield (%)")
            low = f_data.get("1-Year Low")
            high = f_data.get("1-Year High")
            position = f_data.get("1-Year Position")
            current = f_data.get("Current Price")

            if position is not None:
                position = min(position, 100.0)

            # Build 52-week range bar
            if low is not None and high is not None and position is not None:
                range_html = (
                    f'<span style="display:inline-flex;align-items:center;gap:4px;min-width:120px;">'
                    f'<span style="font-size:10px;color:{TEXT_DIM};">{currency_symbol}{low:.0f}</span>'
                    f'<span class="range-bar-bg" style="width:80px;display:inline-block;">'
                    f'<span class="range-bar-fill" style="left:0;width:100%;"></span>'
                    f'<span class="range-bar-dot" style="left:{position}%;"></span>'
                    f'</span>'
                    f'<span style="font-size:10px;color:{TEXT_DIM};">{currency_symbol}{high:.0f}</span>'
                    f'</span>'
                )
            else:
                range_html = "\u2014"

            current_html = f'{currency_symbol}{current:.2f}' if current is not None else "\u2014"

            def _kv(label: str, value_str: str, cls: str = "") -> str:
                color_style = ""
                if cls == "td-pos":
                    color_style = f"color:{GREEN};"
                elif cls == "td-neg":
                    color_style = f"color:{RED};"
                elif cls == "td-amb":
                    color_style = f"color:{AMBER};"
                return (
                    f'<span style="margin-right:14px;white-space:nowrap;">'
                    f'<span style="color:{TEXT_DIM};font-size:11px;">{label}</span> '
                    f'<span style="font-size:11px;font-weight:600;{color_style}">{value_str}</span>'
                    f'</span>'
                )

            risk_line = (
                _kv("Vol", _fmt(vol, "{:.1f}%"), vol_cls)
                + _kv("Drop", _fmt(dd, "{:.1f}%"), dd_cls)
                + _kv("R/R", _fmt(sharpe, "{:.2f}"), sharpe_cls)
                + _kv("Beta", _fmt(beta, "{:.2f}"))
            )

            value_line = (
                _kv("P/E", _fmt(pe, "{:.1f}\u00d7"))
                + _kv("Yield", _fmt(div_yield, "{:.2f}%"))
                + f'<span style="margin-right:14px;white-space:nowrap;">'
                f'<span style="color:{TEXT_DIM};font-size:11px;">52-Wk</span> '
                f'{range_html}'
                f'</span>'
                + _kv("Now", current_html)
            )

            rows_html += (
                f'<tr id="detail-{safe_id}" style="display:{detail_display};">'
                f'<td colspan="5" style="background:{BG_PILL};padding:10px 14px;border-top:none;">'
                f'<div style="display:flex;flex-direction:column;gap:6px;">'
                f'<div style="font-size:11px;">Risk: {risk_line}</div>'
                f'<div style="font-size:11px;">Value: {value_line}</div>'
                f'</div>'
                f'</td>'
                f'</tr>'
            )

        # ── JS toggle function ──
        toggle_js = '''
        <script>
        function toggleDetail(id) {
            var detailRow = document.getElementById('detail-' + id);
            var chevron = document.getElementById('chev-' + id);
            if (!detailRow) return;
            if (detailRow.style.display === 'none' || detailRow.style.display === '') {
                detailRow.style.display = 'table-row';
                if (chevron) chevron.textContent = '\u25BC';
            } else {
                detailRow.style.display = 'none';
                if (chevron) chevron.textContent = '\u25B6';
            }
        }
        </script>
        '''

        ui.html(f'''
        {toggle_js}
        <div class="table-wrap">
        <table>
            <thead><tr>
                <th scope="col">Ticker</th>
                <th scope="col" class="right">Weight %</th>
                <th scope="col" class="right">1Y Return</th>
                <th scope="col" class="right">Contribution</th>
                <th scope="col" class="right">vs SPY</th>
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

        if len(corr_df) > 1:
            mask = np.triu(np.ones(corr_df.shape, dtype=bool), k=1)
            stacked = corr_df.where(mask).stack()
            if not stacked.empty:
                max_pair = stacked.idxmax()
                max_val = stacked.max()
                if len(stacked) == 1:
                    ui.html(
                        f'<div style="font-size:11px;color:{TEXT_DIM};margin-top:8px;">'
                        f'Correlation: {max_pair[0]} & {max_pair[1]} ({max_val:.2f})</div>'
                    )
                else:
                    min_pair = stacked.idxmin()
                    min_val = stacked.min()
                    ui.html(
                        f'<div style="font-size:11px;color:{TEXT_DIM};margin-top:8px;">'
                        f'Most correlated: {max_pair[0]} & {max_pair[1]} ({max_val:.2f}). '
                        f'Least correlated: {min_pair[0]} & {min_pair[1]} ({min_val:.2f}) '
                        f'— good for diversification.</div>'
                    )


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
        "Portfolio risk, performance, and valuation metrics based on 12 months of daily price data."
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

    # ── Unified table (replaces Attribution + Risk + Fundamentals) ──
    _render_unified_table(
        portfolio_df, analytics_df, fund_rows, price_data_1y,
        currency_symbol, portfolio_color_map, base_currency=currency,
    )

    if has_corr:
        _render_correlation_heatmap(price_data_1y, tickers)
