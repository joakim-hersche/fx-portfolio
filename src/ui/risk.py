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
    ACCENT,
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

        _section_intro(
            "Performance, risk, and valuation metrics based on 12 months of daily price data. "
            "Colour coding uses common industry thresholds for context. "
            "Hover over any column header for a plain-language explanation."
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

            # Build 52-week range bar (single-line)
            if low is not None and high is not None and position is not None:
                range_html = (
                    f'<span style="display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">'
                    f'<span style="font-size:10px;color:{TEXT_DIM};min-width:32px;text-align:right;">{currency_symbol}{low:.0f}</span>'
                    f'<span class="range-bar-bg" style="width:60px;display:inline-block;flex-shrink:0;">'
                    f'<span class="range-bar-fill" style="left:0;width:100%;"></span>'
                    f'<span class="range-bar-dot" style="left:{position}%;"></span>'
                    f'</span>'
                    f'<span style="font-size:10px;color:{TEXT_DIM};min-width:32px;">{currency_symbol}{high:.0f}</span>'
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

            def _kv_tip(label: str, tip: str, value_str: str, cls: str = "") -> str:
                color_style = ""
                if cls == "td-pos":
                    color_style = f"color:{GREEN};"
                elif cls == "td-neg":
                    color_style = f"color:{RED};"
                elif cls == "td-amb":
                    color_style = f"color:{AMBER};"
                return (
                    f'<span style="margin-right:14px;white-space:nowrap;">'
                    f'<span class="th-tip" title="{tip}" style="color:{TEXT_DIM};font-size:11px;">{label}</span> '
                    f'<span style="font-size:11px;font-weight:600;{color_style}">{value_str}</span>'
                    f'</span>'
                )

            risk_line = (
                _kv_tip("Vol", "Annualised volatility — how much the price swings.", _fmt(vol, "{:.1f}%"), vol_cls)
                + _kv_tip("Drop", "Max drawdown — biggest peak-to-trough fall.", _fmt(dd, "{:.1f}%"), dd_cls)
                + _kv_tip("R/R", "Sharpe Ratio — return per unit of risk. Above 1 is good.", _fmt(sharpe, "{:.2f}"), sharpe_cls)
                + _kv_tip("Beta", "Market sensitivity vs S&amp;P 500. 1.0 = same swings.", _fmt(beta, "{:.2f}"))
            )

            value_line = (
                _kv_tip("P/E", "Price-to-Earnings — years of profits you pay for the stock.", _fmt(pe, "{:.1f}\u00d7"))
                + _kv_tip("Yield", "Annual dividend as % of stock price.", _fmt(div_yield, "{:.2f}%"))
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
        ui.add_body_html('''
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
        ''')

        ui.html(f'''
        <div style="overflow-x:auto;">
        <div class="table-wrap">
        <table>
            <thead><tr>
                <th scope="col">Ticker</th>
                <th scope="col" class="right th-tip" title="What percentage of your total portfolio value this position represents.">Weight %</th>
                <th scope="col" class="right th-tip" title="How much this stock's price changed over the past 12 months.">1Y Return</th>
                <th scope="col" class="right th-tip" title="How much this position contributed to your overall portfolio return, based on its weight.">Contribution</th>
                <th scope="col" class="right th-tip" title="Performance compared to the S&amp;P 500 index over the same period. Positive = beat the market.">vs SPY</th>
            </tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        </div>
        ''')


# ── Flat (non-expandable) Portfolio Analytics Table ─────────────────────────

def _render_flat_table(
    portfolio_df: pd.DataFrame,
    analytics_df: pd.DataFrame,
    fund_rows: list[dict],
    price_data_1y: dict[str, pd.DataFrame],
    currency_symbol: str,
    color_map: dict[str, str] | None = None,
    base_currency: str = "USD",
) -> None:
    """Render a single wide table with all performance, risk, and valuation columns."""
    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{TEXT_MUTED};">Portfolio Analytics</div>'
            f'</div>'
        )

        _section_intro(
            "Performance, risk, and valuation metrics based on 12 months of daily price data. "
            "Colour coding uses common industry thresholds for context. "
            "Hover over any column header for a plain-language explanation."
        )

        if portfolio_df.empty:
            ui.html(
                f'<p style="color:{TEXT_DIM}; font-size:12px;">'
                f'No data available for portfolio analytics.</p>'
            )
            return

        # ── Compute per-ticker aggregated data ──
        ticker_data = (
            portfolio_df.groupby("Ticker")
            .agg({"Total Value": "sum", "Weight (%)": "sum", "Return (%)": "first"})
            .reset_index()
        )

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

        # SPY 1-year return
        spy_hist = price_data_1y.get("__spy__", pd.DataFrame())
        spy_return = None
        if not spy_hist.empty and "Close" in spy_hist.columns:
            spy_close = spy_hist["Close"].dropna()
            if len(spy_close) >= 2:
                spy_return_usd = (spy_close.iloc[-1] / spy_close.iloc[0] - 1) * 100
                if base_currency != "USD":
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

        # 1-year price returns per ticker
        ticker_1y_return: dict[str, float] = {}
        for t in ticker_data["Ticker"]:
            hist = price_data_1y.get(t, pd.DataFrame())
            if not hist.empty and "Close" in hist.columns:
                close = hist["Close"].dropna()
                if len(close) >= 2:
                    ticker_1y_return[t] = round((close.iloc[-1] / close.iloc[0] - 1) * 100, 2)

        # Analytics and fundamentals lookups
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

        # ── Build table rows ──
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
                position = max(5.0, min(position, 95.0))

            # 52-week range bar (compact, single-line)
            if low is not None and high is not None and position is not None:
                range_html = (
                    f'<div style="display:inline-flex;align-items:center;gap:4px;white-space:nowrap;">'
                    f'<span style="font-size:9px;color:{TEXT_DIM};min-width:32px;text-align:right;">{currency_symbol}{low:.0f}</span>'
                    f'<div class="range-bar-bg" style="width:60px;flex-shrink:0;">'
                    f'<div class="range-bar-fill" style="left:0;width:100%;"></div>'
                    f'<div class="range-bar-dot" style="left:{position}%;"></div>'
                    f'</div>'
                    f'<span style="font-size:9px;color:{TEXT_DIM};min-width:32px;">{currency_symbol}{high:.0f}</span>'
                    f'</div>'
                )
            else:
                range_html = "\u2014"

            current_html = f'{currency_symbol}{current:.0f}' if current is not None else "\u2014"

            rows_html += (
                f'<tr>'
                f'<td><div class="td-ticker">{dot_html}{ticker}</div></td>'
                f'<td class="right">{weight:.0f}%</td>'
                f'<td class="{ret_cls} right">{_fmt(pos_return, "{:+.1f}%")}</td>'
                f'<td class="{contrib_cls} right">{_fmt(contribution, "{:+.1f}%")}</td>'
                f'<td class="{bench_cls} right">{_fmt(vs_bench, "{:+.1f}%")}</td>'
                f'<td class="{vol_cls} right">{_fmt(vol, "{:.0f}%")}</td>'
                f'<td class="{dd_cls} right">{_fmt(dd, "{:.0f}%")}</td>'
                f'<td class="{sharpe_cls} right">{_fmt(sharpe, "{:.1f}")}</td>'
                f'<td class="right">{_fmt(beta, "{:.1f}")}</td>'
                f'<td class="right">{_fmt(pe, "{:.0f}\u00d7")}</td>'
                f'<td class="right">{_fmt(div_yield, "{:.1f}%")}</td>'
                f'<td>{range_html}</td>'
                f'<td class="right">{current_html}</td>'
                f'</tr>'
            )

        ui.html(f'''
        <div class="table-wrap" style="overflow-x:auto;">
        <table style="min-width:1200px;border-collapse:separate;border-spacing:0;">
            <thead>
              <tr>
                <th rowspan="2">Ticker</th>
                <th colspan="4" style="text-align:center;border-bottom:1px solid rgba(255,255,255,0.07);">Performance</th>
                <th colspan="4" style="text-align:center;border-bottom:1px solid rgba(255,255,255,0.07);border-left:1px solid rgba(255,255,255,0.07);">Risk</th>
                <th colspan="4" style="text-align:center;border-bottom:1px solid rgba(255,255,255,0.07);border-left:1px solid rgba(255,255,255,0.07);">Valuation</th>
              </tr>
              <tr>
                <th class="right">Weight %</th>
                <th class="right">1Y Return</th>
                <th class="right">Contribution</th>
                <th class="right">vs S&amp;P</th>
                <th class="right th-tip" style="border-left:1px solid rgba(255,255,255,0.07);" title="How much the price swings day to day, as a yearly %. Higher = more unpredictable.">Volatility</th>
                <th class="right th-tip" title="Biggest peak-to-trough fall in the past year. Shows the worst losing streak.">Worst Drop</th>
                <th class="right th-tip" title="Return per unit of risk (Sharpe Ratio). Above 1 is good, above 2 is excellent, below 0 means you lost money.">Return/Risk</th>
                <th class="right th-tip" title="How much this stock moves relative to the S&amp;P 500. 1.0 = same swings, above 1 = more volatile, below 1 = calmer.">Beta</th>
                <th class="right th-tip" style="border-left:1px solid rgba(255,255,255,0.07);" title="Price-to-Earnings ratio. How many years of current profits you pay for the stock. Lower can mean cheaper, higher can mean expected growth.">P/E Ratio</th>
                <th class="right th-tip" title="Annual dividend payment as a % of the stock price. Higher = more cash income from holding.">Div Yield</th>
                <th class="th-tip" title="The lowest and highest price in the past 52 weeks. The dot shows where the current price sits.">52-Week Range</th>
                <th class="right">Current</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
        </table>
        </div>
        ''')


# ── Correlation Heatmap ─────────────────────────────────────────────────────

def _corr_color(val: float) -> str:
    """Map correlation to a continuous blue-to-red gradient."""
    # Clamp to [-1, 1]
    val = max(-1.0, min(1.0, val))

    if val < 0:
        # Negative: teal (#14B8A6) to dark (#1C1D26), scaled by magnitude
        t = abs(val)  # 0 to 1
        r = int(0x1C + (0x14 - 0x1C) * t)
        g = int(0x1D + (0xB8 - 0x1D) * t)
        b = int(0x26 + (0xA6 - 0x26) * t)
        return f"#{r:02x}{g:02x}{b:02x}"

    # Positive: interpolate through blue -> indigo -> purple -> amber -> red
    stops = [
        (0.0, (0x3B, 0x82, 0xF6)),  # blue
        (0.33, (0x63, 0x66, 0xF1)),  # indigo
        (0.66, (0x8B, 0x5C, 0xF6)),  # purple
        (0.85, (0xD9, 0x77, 0x06)),  # amber
        (1.0, (0xDC, 0x26, 0x26)),   # red
    ]

    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if val <= t1:
            t = (val - t0) / (t1 - t0) if t1 > t0 else 0
            r = int(c0[0] + (c1[0] - c0[0]) * t)
            g = int(c0[1] + (c1[1] - c0[1]) * t)
            b = int(c0[2] + (c1[2] - c0[2]) * t)
            return f"#{r:02x}{g:02x}{b:02x}"

    return "#DC2626"


def _render_correlation_heatmap(price_data: dict, tickers: list) -> None:
    """Render the pairwise correlation matrix as an HTML CSS grid."""
    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:{TEXT_MUTED};">Correlation Matrix</div>'
            f'<div style="font-size:10px;color:{TEXT_DIM};">12-month rolling</div>'
            f'</div>'
        )

        _section_intro(
            "Shows whether your stocks tend to move together or independently. "
            "Values near 1.0 (warm colours) mean two stocks rise and fall in sync — "
            "less diversification benefit. Values near 0 (cool colours) mean they move "
            "independently, which helps cushion your portfolio when one stock drops."
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
        labels = list(corr_df.columns)
        n = len(labels)

        # Build HTML grid
        cell_style = (
            "border-radius:6px;aspect-ratio:1;display:flex;"
            "align-items:center;justify-content:center;"
        )
        font_style = "font-size:10px;font-weight:600;color:rgba(255,255,255,0.85);"
        label_style = f"font-size:10px;font-weight:700;color:{TEXT_FAINT};display:flex;align-items:center;justify-content:center;"

        cells = f'<div style="{label_style}"></div>'  # empty corner
        for lbl in labels:
            cells += f'<div style="{label_style}">{lbl}</div>'

        for i, row_lbl in enumerate(labels):
            cells += f'<div style="{label_style}">{row_lbl}</div>'
            for j, col_lbl in enumerate(labels):
                val = corr_df.iloc[i, j]
                if i == j:
                    cells += (
                        f'<div style="{cell_style}background:{BG_PILL};'
                        f'font-size:9px;color:{TEXT_DIM};">1.0</div>'
                    )
                else:
                    bg = _corr_color(val)
                    cells += (
                        f'<div style="{cell_style}background:{bg};{font_style}">'
                        f'{val:.2f}</div>'
                    )

        ui.html(
            f'<div style="display:grid;grid-template-columns:repeat({n + 1},1fr);gap:4px;">'
            f'{cells}</div>'
        )

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
                        f'— returns moved most independently.</div>'
                    )


# ── Sector Treemap ────────────────────────────────────────────────────────────

_SECTOR_COLORS = [
    "#3B82F6", "#0EA5E9", "#6366F1", "#10B981", "#F59E0B",
    "#EC4899", "#8B5CF6", "#14B8A6", "#0E7490", "#D97706",
]


def _render_sector_breakdown(
    fund_rows: list[dict],
    portfolio_df: pd.DataFrame,
) -> None:
    """Sector concentration as a CSS-grid treemap."""
    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;'
            f'text-transform:uppercase;color:{TEXT_MUTED};">Sector Exposure</div>'
            f'<div style="font-size:10px;color:{TEXT_DIM};">by portfolio weight</div>'
            f'</div>'
        )

        if not fund_rows or portfolio_df.empty:
            ui.html(f'<p style="color:{TEXT_DIM};font-size:12px;">No sector data available.</p>')
            return

        ticker_sector: dict[str, str] = {
            r["Ticker"]: r.get("Sector", "Unknown") for r in fund_rows
        }
        ticker_weights = portfolio_df.groupby("Ticker")["Weight (%)"].sum().to_dict()

        sector_data: dict[str, dict] = {}
        for ticker, weight in ticker_weights.items():
            sector = ticker_sector.get(ticker, "Unknown")
            if sector not in sector_data:
                sector_data[sector] = {"weight": 0.0, "tickers": []}
            sector_data[sector]["weight"] += weight
            sector_data[sector]["tickers"].append((ticker, weight))

        sorted_sectors = sorted(sector_data.items(), key=lambda x: x[1]["weight"], reverse=True)
        if not sorted_sectors:
            ui.html(f'<p style="color:{TEXT_DIM};font-size:12px;">No sector data available.</p>')
            return

        sector_colors = {s: _SECTOR_COLORS[i % len(_SECTOR_COLORS)] for i, (s, _) in enumerate(sorted_sectors)}
        n = len(sorted_sectors)

        # ── Build treemap cell HTML ──
        def _cell(sector: str, data: dict, color: str) -> str:
            w = data["weight"]
            tickers_sorted = sorted(data["tickers"], key=lambda x: x[1], reverse=True)
            # Show ticker pills only if cell is large enough (>= 8%)
            if w >= 8:
                pills = "".join(
                    f'<span style="font-size:9px;background:rgba(255,255,255,0.2);'
                    f'padding:2px 5px;border-radius:2px;color:white;">{t}</span>'
                    for t, _ in tickers_sorted
                )
                pills_html = f'<div style="display:flex;gap:3px;flex-wrap:wrap;margin-top:4px;justify-content:center;">{pills}</div>'
            else:
                pills_html = ""
            # Show sector name only if large enough
            name_html = (
                f'<span style="font-size:10px;color:rgba(255,255,255,0.8);margin-top:2px;">{sector}</span>'
                if w >= 12 else ""
            )
            tickers_str = ", ".join(t for t, _ in tickers_sorted)
            return (
                f'<div title="{sector}: {w:.1f}% ({tickers_str})" '
                f'style="background:{color};border-radius:6px;display:flex;flex-direction:column;'
                f'align-items:center;justify-content:center;padding:6px;overflow:hidden;min-width:0;">'
                f'<span style="font-size:16px;font-weight:700;color:white;">{w:.0f}%</span>'
                f'{name_html}{pills_html}'
                f'</div>'
            )

        # ── Layout strategy: biggest sector on left full-height, rest stack right ──
        if n == 1:
            s, d = sorted_sectors[0]
            grid_html = (
                f'<div style="height:100%;">'
                f'{_cell(s, d, sector_colors[s])}'
                f'</div>'
            )
        elif n == 2:
            s0, d0 = sorted_sectors[0]
            s1, d1 = sorted_sectors[1]
            w0 = max(30, min(70, round(d0["weight"] / (d0["weight"] + d1["weight"]) * 100)))
            grid_html = (
                f'<div style="display:grid;grid-template-columns:{w0}fr {100-w0}fr;gap:3px;height:100%;">'
                f'{_cell(s0, d0, sector_colors[s0])}'
                f'{_cell(s1, d1, sector_colors[s1])}'
                f'</div>'
            )
        else:
            # First sector takes left column, rest stack on the right
            s0, d0 = sorted_sectors[0]
            rest = sorted_sectors[1:]
            # Left column width proportional to first sector weight, clamped
            left_w = max(30, min(60, round(d0["weight"])))
            right_w = 100 - left_w
            # Right side: split into rows; pair small sectors together
            right_cells = ""
            rest_total = sum(d["weight"] for _, d in rest)
            i = 0
            while i < len(rest):
                s, d = rest[i]
                w_frac = d["weight"] / rest_total if rest_total > 0 else 1.0 / len(rest)
                # If next sector is also small, put them side by side
                if i + 1 < len(rest) and d["weight"] < 20 and rest[i + 1][1]["weight"] < 20:
                    s2, d2 = rest[i + 1]
                    pair_total = d["weight"] + d2["weight"]
                    w1 = max(30, round(d["weight"] / pair_total * 100)) if pair_total > 0 else 50
                    pair_frac = pair_total / rest_total if rest_total > 0 else 0.5
                    right_cells += (
                        f'<div style="display:grid;grid-template-columns:{w1}fr {100-w1}fr;gap:3px;'
                        f'flex:{pair_frac:.2f};">'
                        f'{_cell(s, d, sector_colors[s])}'
                        f'{_cell(s2, d2, sector_colors[s2])}'
                        f'</div>'
                    )
                    i += 2
                else:
                    right_cells += (
                        f'<div style="flex:{w_frac:.2f};">'
                        f'{_cell(s, d, sector_colors[s])}'
                        f'</div>'
                    )
                    i += 1

            grid_html = (
                f'<div style="display:grid;grid-template-columns:{left_w}fr {right_w}fr;gap:3px;height:100%;">'
                f'{_cell(s0, d0, sector_colors[s0])}'
                f'<div style="display:flex;flex-direction:column;gap:3px;">'
                f'{right_cells}'
                f'</div>'
                f'</div>'
            )

        ui.html(grid_html).classes("w-full").style("aspect-ratio:1;width:100%;")


# ── Rebalancing Calculator (drift bars) ──────────────────────────────────────

def _render_rebalancing_calculator(portfolio_df: pd.DataFrame, currency_symbol: str) -> None:
    """Buy-only rebalancing calculator with drift-bar visualisation."""
    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">'
            f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;'
            f'text-transform:uppercase;color:{TEXT_MUTED};">Rebalancing Calculator</div>'
            f'<div style="font-size:10px;color:{TEXT_DIM};">buy-only</div>'
            f'</div>'
        )
        ui.html(
            f'<div style="font-size:11px;color:{TEXT_DIM};margin-bottom:10px;">'
            f'Set targets and a deposit amount to see what to buy. '
            f'<span style="color:{AMBER};">Not a recommendation.</span></div>'
        )

        if portfolio_df.empty:
            ui.html(f'<p style="color:{TEXT_DIM};font-size:12px;">No positions to rebalance.</p>')
            return

        ticker_data = (
            portfolio_df.groupby("Ticker")
            .agg({"Weight (%)": "sum", "Total Value": "sum", "Current Price": "first"})
            .reset_index()
        )

        target_weights: dict[str, float] = {
            row["Ticker"]: round(row["Weight (%)"], 2)
            for _, row in ticker_data.iterrows()
        }
        deposit_ref = {"value": 0.0}
        result_container = {"ref": None}

        def _recalculate():
            container = result_container["ref"]
            if container is None:
                return
            container.clear()
            with container:
                deposit = deposit_ref["value"] or 0.0

                # ── Drift bars (always shown) ──
                action_map: dict[str, dict] = {}
                if deposit > 0:
                    total_value = ticker_data["Total Value"].sum()
                    new_total = total_value + deposit
                    suggestions = []
                    for _, row in ticker_data.iterrows():
                        t = row["Ticker"]
                        cur_pct = row["Weight (%)"]
                        tgt_pct = target_weights.get(t, cur_pct)
                        cur_val = row["Total Value"]
                        price = row["Current Price"]
                        tgt_val = new_total * tgt_pct / 100
                        deficit = tgt_val - cur_val
                        suggestions.append({
                            "Ticker": t, "Deficit": max(deficit, 0), "Price": price,
                        })
                    suggestions.sort(key=lambda s: s["Deficit"], reverse=True)

                    remaining = deposit
                    for s in suggestions:
                        if remaining <= 0 or s["Price"] is None or s["Price"] <= 0 or s["Deficit"] <= 0:
                            action_map[s["Ticker"]] = {"Shares": 0, "Amount": 0.0}
                            continue
                        max_spend = min(s["Deficit"], remaining)
                        shares = int(max_spend / s["Price"])
                        amount = shares * s["Price"]
                        remaining -= amount
                        action_map[s["Ticker"]] = {"Shares": shares, "Amount": amount}

                    if remaining > 0:
                        for t, a in action_map.items():
                            if remaining <= 0:
                                break
                            price = next(
                                (r["Current Price"] for _, r in ticker_data.iterrows() if r["Ticker"] == t),
                                None,
                            )
                            if price and price > 0 and remaining >= price:
                                extra = int(remaining / price)
                                if extra > 0:
                                    a["Shares"] += extra
                                    a["Amount"] += extra * price
                                    remaining -= extra * price

                # Render drift bar rows
                bars_html = ""
                for _, row in ticker_data.iterrows():
                    t = row["Ticker"]
                    cur = row["Weight (%)"]
                    tgt = target_weights.get(t, cur)
                    a = action_map.get(t, {})
                    shares = a.get("Shares", 0)
                    amount = a.get("Amount", 0.0)

                    if abs(tgt - cur) < 0.5:
                        border_color = ACCENT
                        opacity = "0.7"
                    elif tgt > cur:
                        border_color = GREEN
                        opacity = "0.5"
                    else:
                        border_color = AMBER
                        opacity = "0.5"

                    buy_html = ""
                    if shares > 0:
                        buy_html = (
                            f'<span style="font-size:10px;font-weight:700;color:{GREEN};'
                            f'flex-shrink:0;white-space:nowrap;">'
                            f'+{shares} ({currency_symbol}{amount:,.0f})</span>'
                        )

                    bars_html += (
                        f'<div style="margin-bottom:6px;">'
                        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">'
                        f'<span style="font-size:10px;font-weight:600;color:{TEXT_SECONDARY};'
                        f'width:48px;flex-shrink:0;">{t}</span>'
                        f'<span style="font-size:9px;color:{TEXT_DIM};">'
                        f'{cur:.0f}% \u2192 {tgt:.0f}%</span>'
                        f'<span style="flex:1;"></span>'
                        f'{buy_html}'
                        f'</div>'
                        f'<div style="height:10px;background:rgba(255,255,255,0.06);border-radius:4px;'
                        f'overflow:visible;position:relative;">'
                        f'<div style="position:absolute;left:0;width:{min(cur, 100):.1f}%;height:100%;'
                        f'background:{TEXT_DIM};border-radius:4px;opacity:{opacity};"></div>'
                        f'<div style="position:absolute;left:0;width:{min(tgt, 100):.1f}%;height:100%;'
                        f'border:1.5px solid {border_color};border-radius:4px;box-sizing:border-box;"></div>'
                        f'</div>'
                        f'</div>'
                    )

                ui.html(bars_html)

                if deposit > 0 and remaining > 0.01:
                    ui.html(
                        f'<div style="font-size:10px;color:{TEXT_DIM};margin-top:4px;">'
                        f'{currency_symbol}{remaining:.2f} unallocated</div>'
                    )

        # ── Deposit input ──
        with ui.row().classes("w-full items-end").style("gap:12px;margin-bottom:10px;"):
            with ui.column().style("gap:2px;"):
                ui.html(
                    f'<span style="font-size:10px;font-weight:600;color:{TEXT_DIM};">'
                    f'Deposit ({currency_symbol})</span>'
                )
                deposit_input = ui.number(
                    value=0, min=0, format="%.0f",
                ).style("width:120px;")

                def _on_deposit(e):
                    deposit_ref["value"] = e.value or 0.0
                    _recalculate()
                deposit_input.on_value_change( _on_deposit)

        # ── Per-ticker target inputs ──
        for _, row in ticker_data.iterrows():
            ticker = row["Ticker"]
            current_w = row["Weight (%)"]
            with ui.row().classes("w-full items-center").style("gap:6px;margin-bottom:2px;"):
                ui.html(
                    f'<span style="width:48px;font-size:11px;font-weight:700;'
                    f'color:{TEXT_PRIMARY};flex-shrink:0;">{ticker}</span>'
                )
                ui.html(
                    f'<span style="font-size:9px;color:{TEXT_DIM};flex-shrink:0;">'
                    f'{current_w:.0f}% \u2192</span>'
                )
                inp = ui.number(
                    value=round(current_w, 1),
                    min=0, max=100, step=0.5, format="%.1f",
                    suffix="%",
                ).props("dense").style("width:70px;flex-shrink:0;")

                def _make_handler(t):
                    def handler(e):
                        target_weights[t] = e.value if e.value is not None else 0.0
                        _recalculate()
                    return handler
                inp.on_value_change( _make_handler(ticker))

        # ── Result area (drift bars + buy suggestions) ──
        result_container["ref"] = ui.column().classes("w-full").style("margin-top:8px;")
        _recalculate()



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
                row["Sector"] = info.get("Sector", "Unknown")
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

    # ── Portfolio-level risk KPIs ──────────────────────────
    if not analytics_df.empty and not portfolio_df.empty:
        ticker_weights = (
            portfolio_df.groupby("Ticker")["Weight (%)"].sum() / 100
        ).to_dict()

        total_vol = total_dd = total_sharpe = total_beta = 0.0
        w_sum_vol = w_sum_dd = w_sum_sharpe = w_sum_beta = 0.0
        for _, arow in analytics_df.iterrows():
            w = ticker_weights.get(arow["Ticker"], 0.0)
            if w <= 0:
                continue
            v, d, s, b = (arow.get("Volatility"), arow.get("Max Drawdown"),
                          arow.get("Sharpe Ratio"), arow.get("Beta"))
            if v is not None and not pd.isna(v):
                total_vol += w * v; w_sum_vol += w
            if d is not None and not pd.isna(d):
                total_dd += w * d; w_sum_dd += w
            if s is not None and not pd.isna(s):
                total_sharpe += w * s; w_sum_sharpe += w
            if b is not None and not pd.isna(b):
                total_beta += w * b; w_sum_beta += w

        p_vol = (total_vol / w_sum_vol) if w_sum_vol > 0 else None
        p_dd = (total_dd / w_sum_dd) if w_sum_dd > 0 else None
        p_sharpe = (total_sharpe / w_sum_sharpe) if w_sum_sharpe > 0 else None
        p_beta = (total_beta / w_sum_beta) if w_sum_beta > 0 else None

        def _risk_kpi(label, value_str, sub_text):
            return (
                f'<div class="kpi-card">'
                f'<div class="kpi-label">{label}</div>'
                f'<div class="kpi-value">{value_str}</div>'
                f'<div class="kpi-sub">{sub_text}</div>'
                f'</div>'
            )

        ui.html(
            '<div class="kpi-row" style="grid-template-columns:1fr 1fr 1fr 1fr;">'
            + _risk_kpi("Portfolio Volatility",
                        f"{p_vol:.1f}%" if p_vol is not None else "\u2014",
                        "How much your portfolio swings in a typical year")
            + _risk_kpi("Worst Drawdown",
                        f"{p_dd:.1f}%" if p_dd is not None else "\u2014",
                        "Biggest drop from peak in the past year")
            + _risk_kpi("Return / Risk",
                        f"{p_sharpe:.2f}" if p_sharpe is not None else "\u2014",
                        "Return per unit of risk — above 1 is good")
            + _risk_kpi("Market Beta",
                        f"{p_beta:.2f}" if p_beta is not None else "\u2014",
                        "How closely your portfolio follows the market")
            + '</div>'
        ).classes("w-full")

    # ── Analytics table (full width) ───────────────────────
    _render_flat_table(
        portfolio_df, analytics_df, fund_rows, price_data_1y,
        currency_symbol, portfolio_color_map, base_currency=currency,
    )

    # ── Correlation + Sector + Rebalancing — three wide ─────
    with ui.element("div").classes("risk-triple w-full"):
        if has_corr:
            _render_correlation_heatmap(price_data_1y, tickers)
        else:
            ui.element("div")  # placeholder to keep 3-col grid
        _render_sector_breakdown(fund_rows, portfolio_df)
        _render_rebalancing_calculator(portfolio_df, currency_symbol)
