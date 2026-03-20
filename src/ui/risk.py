"""Risk & Analytics tab for the NiceGUI dashboard.

Renders a unified portfolio analytics table with expandable detail rows,
plus a correlation heatmap, using NiceGUI widgets and Plotly charts.
"""

import numpy as np
import pandas as pd
from nicegui import run, ui

from src.charts import (
    FALLBACK_COLORS,
    C_POSITIVE,
    C_NEGATIVE,
    C_AMBER,
)
from src.stocks import (
    TICKER_COLORS,
    get_bonds,
    get_commodities,
    get_crypto,
    get_emerging_markets,
    get_etfs,
    get_reits,
)
from src.data_fetch import fetch_analytics_history, fetch_fundamentals
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df, compute_analytics
from src.theme import (
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_DIM,
    TEXT_FAINT,
    TEXT_SECONDARY,
    BG_PILL,
    BORDER,
    BORDER_INPUT,
    BORDER_SUBTLE,
    BG_TOPBAR,
    GREEN,
    RED,
    AMBER,
    ACCENT,
)


_ASSET_CLASS_SECTORS: dict[str, str] = {}
for _label, _fn in [
    ("Commodities", get_commodities),
    ("Equity ETFs", get_etfs),
    ("Bonds", get_bonds),
    ("Real Estate", get_reits),
    ("Emerging Markets", get_emerging_markets),
    ("Crypto", get_crypto),
]:
    for _t in _fn():
        _ASSET_CLASS_SECTORS[_t] = _label

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
        ui.html('<div class="section-label">Correlation Matrix</div>')
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
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


def _build_sector_data(
    fund_rows: list[dict],
    portfolio_df: pd.DataFrame,
) -> tuple[dict[str, str], dict[str, float], list[str], dict[str, float], dict[str, str]]:
    """Build sector grouping data shared by sector breakdown and rebalancing cards.

    Returns (ticker_sector, ticker_weights, sector_order, sector_totals, sector_color_map).
    """
    ticker_sector: dict[str, str] = {
        r["Ticker"]: r.get("Sector", "Unknown") for r in fund_rows
    }
    ticker_weights = portfolio_df.groupby("Ticker")["Weight (%)"].sum().to_dict()

    sector_order: list[str] = []
    for ticker, _w in sorted(ticker_weights.items(), key=lambda x: x[1], reverse=True):
        sector = ticker_sector.get(ticker, "Unknown")
        if sector not in sector_order:
            sector_order.append(sector)

    sector_totals: dict[str, float] = {}
    for ticker, weight in ticker_weights.items():
        sector = ticker_sector.get(ticker, "Unknown")
        sector_totals[sector] = sector_totals.get(sector, 0) + weight

    sector_order.sort(key=lambda s: sector_totals.get(s, 0), reverse=True)
    sector_color_map = {
        s: _SECTOR_COLORS[i % len(_SECTOR_COLORS)]
        for i, s in enumerate(sector_order)
    }
    return ticker_sector, ticker_weights, sector_order, sector_totals, sector_color_map


def _render_sector_breakdown(
    fund_rows: list[dict],
    portfolio_df: pd.DataFrame,
    color_map: dict[str, str] | None = None,
) -> None:
    """Sector exposure as grouped horizontal bars."""
    with ui.column().classes("chart-card w-full"):
        ui.html('<div class="section-label">Sector Exposure</div>')
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;color:{TEXT_DIM};">by portfolio weight</div>'
            f'</div>'
        )

        _section_intro(
            "Shows which industries your money is spread across. "
            "If one sector dominates, a downturn in that industry affects your whole portfolio."
        )

        if not fund_rows or portfolio_df.empty:
            ui.html(f'<p style="color:{TEXT_DIM};font-size:12px;">No sector data available.</p>')
            return

        ticker_sector, ticker_weights, sector_order, sector_totals, sector_color_map = (
            _build_sector_data(fund_rows, portfolio_df)
        )

        # Build per-sector ticker lists for display
        sector_tickers: dict[str, list[tuple[str, float]]] = {}
        for ticker, weight in ticker_weights.items():
            sector = ticker_sector.get(ticker, "Unknown")
            sector_tickers.setdefault(sector, []).append((ticker, round(weight, 2)))
        for sector in sector_tickers:
            sector_tickers[sector].sort(key=lambda x: x[1], reverse=True)

        max_sector = max(sector_totals.values()) if sector_totals else 1
        max_ticker = max(ticker_weights.values()) if ticker_weights else 1

        # Build HTML
        rows_html = ""
        for sector in sector_order:
            color = sector_color_map[sector]
            total = sector_totals.get(sector, 0)
            sector_bar_w = (total / max_sector * 100) if max_sector > 0 else 0
            rows_html += (
                f'<div style="display:flex;align-items:center;gap:8px;padding:7px 0 3px 0;'
                f'margin-top:4px;">'
                f'<div style="width:6px;height:6px;border-radius:2px;background:{color};flex-shrink:0;"></div>'
                f'<span style="width:90px;font-size:10px;font-weight:700;color:{TEXT_MUTED};text-transform:uppercase;'
                f'letter-spacing:0.08em;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;'
                f'white-space:nowrap;">{sector}</span>'
                f'<div style="flex:1;height:10px;background:rgba(255,255,255,0.04);border-radius:4px;overflow:hidden;">'
                f'<div style="width:{sector_bar_w:.1f}%;height:100%;background:{color};opacity:0.85;'
                f'border-radius:4px;"></div>'
                f'</div>'
                f'<span style="width:40px;font-size:11px;font-weight:700;color:{TEXT_SECONDARY};'
                f'text-align:right;flex-shrink:0;">{total:.1f}%</span>'
                f'</div>'
            )
            for ticker, weight in sector_tickers.get(sector, []):
                bar_width = (weight / max_ticker * 100) if max_ticker > 0 else 0
                ticker_color = (color_map or {}).get(ticker, color)  # fallback to sector color
                rows_html += (
                    f'<div class="alloc-bar" style="display:flex;align-items:center;gap:8px;'
                    f'padding:1px 0 1px 20px;position:relative;">'
                    f'<div style="width:48px;font-size:10px;color:{TEXT_DIM};'
                    f'flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{ticker}</div>'
                    f'<div style="flex:1;height:4px;background:rgba(255,255,255,0.03);border-radius:3px;overflow:hidden;">'
                    f'<div style="width:{bar_width:.1f}%;height:100%;background:{ticker_color};opacity:0.45;border-radius:3px;"></div>'
                    f'</div>'
                    f'<div style="width:40px;font-size:10px;color:{TEXT_DIM};text-align:right;flex-shrink:0;">{weight:.1f}%</div>'
                    f'<div class="alloc-tip">'
                    f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
                    f'<div style="width:8px;height:8px;border-radius:2px;background:{ticker_color};flex-shrink:0;"></div>'
                    f'<span style="font-weight:600;color:{TEXT_PRIMARY};font-size:11px;">{ticker}</span>'
                    f'<span style="color:{TEXT_DIM};font-size:10px;">{sector}</span>'
                    f'</div>'
                    f'<div style="font-size:11px;">'
                    f'<span style="color:{TEXT_PRIMARY};font-weight:600;">{weight:.1f}%</span>'
                    f'<span style="color:{TEXT_MUTED};"> of portfolio</span>'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                )

        # Footer summary
        top_sector = sector_order[0] if sector_order else "—"
        top_pct = sector_totals.get(top_sector, 0)
        n_sectors = len(sector_order)
        rows_html += (
            f'<div style="font-size:11px;color:{TEXT_DIM};margin-top:8px;">'
            f'Top sector: {top_sector} ({top_pct:.1f}%) &middot; {n_sectors} sector{"s" if n_sectors != 1 else ""} total'
            f'</div>'
        )

        ui.html(
            f'<div style="display:flex;flex-direction:column;gap:2px;">{rows_html}</div>'
        ).classes("w-full")


# ── Rebalancing Calculator (drift bars) ──────────────────────────────────────

def _render_rebalancing_calculator(
    fund_rows: list[dict],
    portfolio_df: pd.DataFrame,
    currency_symbol: str,
) -> None:
    """Buy-only rebalancing calculator with sector-grouped drift-bar layout."""
    with ui.column().classes("chart-card card-tertiary w-full").style("gap:0;"):
        ui.html('<div class="section-label">Rebalancing Calculator</div>')
        ui.html(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">'
            f'<div style="font-size:10px;color:{TEXT_DIM};">buy-only</div>'
            f'</div>'
        )

        _section_intro(
            "Set target weights and a deposit amount. "
            "<span style=\"color:" + AMBER + ";\">Not a recommendation.</span>"
        )

        if not fund_rows or portfolio_df.empty:
            ui.html(f'<p style="color:{TEXT_DIM};font-size:12px;">No positions to rebalance.</p>')
            return

        ticker_data = (
            portfolio_df.groupby("Ticker")
            .agg({"Weight (%)": "sum", "Total Value": "sum", "Current Price": "first"})
            .reset_index()
        )

        # ── Sector grouping (shared helper ensures colors match sector breakdown) ──
        ticker_sector, ticker_weights_map, sector_order, sector_totals, sector_color_map = (
            _build_sector_data(fund_rows, portfolio_df)
        )
        sector_tickers_grouped: dict[str, list[str]] = {}
        for ticker in ticker_weights_map:
            sector = ticker_sector.get(ticker, "Unknown")
            sector_tickers_grouped.setdefault(sector, []).append(ticker)
        for sector in sector_tickers_grouped:
            sector_tickers_grouped[sector].sort(
                key=lambda t: ticker_weights_map.get(t, 0), reverse=True,
            )

        target_weights: dict[str, float] = {
            row["Ticker"]: round(row["Weight (%)"], 2)
            for _, row in ticker_data.iterrows()
        }
        deposit_ref = {"value": 0.0}
        bar_containers: dict[str, ui.column] = {}
        footer_ref = {"ref": None}

        def _recalculate():
            deposit = deposit_ref["value"] or 0.0

            # Compute buy suggestions
            action_map: dict[str, dict] = {}
            remaining = 0.0
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
                    for s in suggestions:
                        if remaining <= 0:
                            break
                        t = s["Ticker"]
                        if s["Deficit"] <= 0 or s["Price"] is None or s["Price"] <= 0:
                            continue
                        a = action_map[t]
                        still_needed = s["Deficit"] - a["Amount"]
                        if still_needed <= 0:
                            continue
                        price = s["Price"]
                        if remaining >= price:
                            extra = min(int(remaining / price), int(still_needed / price) or 1)
                            if extra > 0:
                                a["Shares"] += extra
                                a["Amount"] += extra * price
                                remaining -= extra * price

            # Update each ticker's drift bar
            for _, row in ticker_data.iterrows():
                t = row["Ticker"]
                if t not in bar_containers:
                    continue
                cur = row["Weight (%)"]
                tgt = target_weights.get(t, cur)
                a = action_map.get(t, {})
                shares = a.get("Shares", 0)
                amount = a.get("Amount", 0.0)

                if abs(tgt - cur) < 0.5:
                    border_color = ACCENT
                elif tgt > cur:
                    border_color = GREEN
                else:
                    border_color = AMBER

                buy_html = ""
                if shares > 0:
                    s_label = "share" if shares == 1 else "shares"
                    buy_html = (
                        f'<div style="display:flex;align-items:center;gap:4px;margin-top:2px;">'
                        f'<div style="width:4px;height:4px;border-radius:50%;background:{GREEN};flex-shrink:0;"></div>'
                        f'<span style="font-size:9px;font-weight:600;color:{GREEN};">Buy {shares} {s_label}</span>'
                        f'<span style="font-size:9px;color:{TEXT_DIM};">({currency_symbol}{amount:,.0f})</span>'
                        f'</div>'
                    )

                bar_containers[t].clear()
                with bar_containers[t]:
                    ui.html(
                        f'<div style="height:6px;background:rgba(255,255,255,0.04);'
                        f'border-radius:3px;position:relative;">'
                        f'<div style="position:absolute;left:0;width:{min(cur, 100):.1f}%;'
                        f'height:100%;background:{TEXT_DIM};border-radius:3px;opacity:0.5;"></div>'
                        f'<div style="position:absolute;left:0;width:{min(tgt, 100):.1f}%;'
                        f'height:100%;border:1.5px solid {border_color};border-radius:3px;'
                        f'box-sizing:border-box;"></div>'
                        f'</div>'
                        f'{buy_html}'
                    )

            # Footer
            total_tgt = sum(target_weights.values())
            fc = footer_ref["ref"]
            if fc is not None:
                fc.clear()
                with fc:
                    parts: list[str] = []
                    tgt_color = AMBER if total_tgt < 99.5 or total_tgt > 100.5 else TEXT_DIM
                    parts.append(
                        f'<span style="font-size:10px;color:{tgt_color};">'
                        f'Target: {total_tgt:.1f}%</span>'
                    )
                    if deposit > 0 and remaining > 0.01:
                        parts.append(
                            f'<span style="font-size:10px;color:{TEXT_DIM};">'
                            f'{currency_symbol}{remaining:.2f} unallocated</span>'
                        )
                    ui.html(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'border-top:1px solid {BORDER_SUBTLE};padding-top:6px;">'
                        f'{"".join(parts)}</div>'
                    )

        # ── Deposit input ──
        input_style = (
            f"background:{BG_PILL};border:1px solid {BORDER_INPUT};"
            f"border-radius:4px;padding:0 4px;"
        )
        with ui.row().classes("w-full items-center no-wrap").style("gap:8px;margin:0 0 10px 0;min-height:0;"):
            ui.html(
                f'<span style="font-size:9px;font-weight:600;color:{TEXT_DIM};'
                f'text-transform:uppercase;letter-spacing:0.06em;">Deposit</span>'
            )
            deposit_input = ui.number(
                value=0, min=0, format="%.0f", prefix=currency_symbol,
            ).props("dense borderless input-class=text-center").style(f"width:120px;{input_style}")

            def _on_deposit(e):
                deposit_ref["value"] = e.value or 0.0
                _recalculate()
            deposit_input.on_value_change(_on_deposit)

        # ── Column headers ──
        ui.html(
            f'<div style="display:flex;align-items:center;gap:6px;padding:0 0 4px 0;'
            f'margin-bottom:2px;border-bottom:1px solid {BORDER_SUBTLE};">'
            f'<span style="width:52px;font-size:8px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:{TEXT_MUTED};flex-shrink:0;">Ticker</span>'
            f'<span style="width:32px;font-size:8px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:{TEXT_MUTED};text-align:right;flex-shrink:0;">Now</span>'
            f'<span style="width:8px;flex-shrink:0;"></span>'
            f'<span style="width:44px;font-size:8px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:{TEXT_MUTED};flex-shrink:0;">Target</span>'
            f'<span style="flex:1;font-size:8px;font-weight:600;text-transform:uppercase;'
            f'letter-spacing:0.08em;color:{TEXT_MUTED};">Drift</span>'
            f'</div>'
        ).classes("w-full")

        # ── Sector-grouped rows ──
        max_sector_total = max(sector_totals.values()) if sector_totals else 1
        for sector in sector_order:
            color = sector_color_map[sector]
            total = sector_totals.get(sector, 0)
            bar_w = (total / max_sector_total * 100) if max_sector_total > 0 else 0

            # Sector header
            ui.html(
                f'<div style="display:flex;align-items:center;gap:6px;padding:7px 0 3px 0;'
                f'margin-top:4px;">'
                f'<div style="width:6px;height:6px;border-radius:2px;background:{color};flex-shrink:0;"></div>'
                f'<span style="width:90px;font-size:10px;font-weight:700;color:{TEXT_MUTED};'
                f'text-transform:uppercase;letter-spacing:0.08em;flex-shrink:0;overflow:hidden;'
                f'text-overflow:ellipsis;white-space:nowrap;">{sector}</span>'
                f'<div style="flex:1;height:10px;background:rgba(255,255,255,0.04);border-radius:4px;'
                f'overflow:hidden;">'
                f'<div style="width:{bar_w:.1f}%;height:100%;background:{color};opacity:0.85;'
                f'border-radius:4px;"></div>'
                f'</div>'
                f'<span style="width:40px;font-size:11px;font-weight:700;color:{TEXT_SECONDARY};'
                f'text-align:right;flex-shrink:0;">{total:.1f}%</span>'
                f'</div>'
            ).classes("w-full")

            # Ticker rows within sector
            for ticker in sector_tickers_grouped.get(sector, []):
                td_row = ticker_data[ticker_data["Ticker"] == ticker]
                if td_row.empty:
                    continue
                current_w = td_row.iloc[0]["Weight (%)"]

                with ui.row().classes("w-full items-center no-wrap").style(
                    "gap:6px;margin:0;padding:0 0 0 14px;min-height:0;"
                ):
                    ui.html(
                        f'<span style="width:52px;font-size:10px;color:{TEXT_DIM};'
                        f'flex-shrink:0;overflow:hidden;text-overflow:ellipsis;'
                        f'white-space:nowrap;">{ticker}</span>'
                    )
                    ui.html(
                        f'<span style="width:32px;font-size:10px;color:{TEXT_DIM};'
                        f'text-align:right;flex-shrink:0;">{current_w:.0f}%</span>'
                    )
                    ui.html(
                        f'<span style="width:8px;font-size:9px;color:{TEXT_DIM};'
                        f'text-align:center;flex-shrink:0;">&rarr;</span>'
                    )
                    inp = ui.number(
                        value=round(current_w),
                        min=0, max=100, step=1, format="%.0f",
                        suffix="%",
                    ).props("dense borderless input-class=text-center").style(
                        f"width:56px;max-height:28px;{input_style}"
                    )

                    def _make_handler(t):
                        def handler(e):
                            target_weights[t] = e.value if e.value is not None else 0.0
                            _recalculate()
                        return handler
                    inp.on_value_change(_make_handler(ticker))

                    bar_containers[ticker] = ui.element("div").style(
                        "flex:1;min-width:40px;display:flex;flex-direction:column;"
                        "justify-content:center;gap:0;"
                    )

        footer_ref["ref"] = ui.column().classes("w-full").style("margin-top:2px;")
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
                sector = info.get("Sector", "Unknown")
                if sector == "Unknown" and t in _ASSET_CLASS_SECTORS:
                    sector = _ASSET_CLASS_SECTORS[t]
                row["Sector"] = sector
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
        t: TICKER_COLORS.get(t, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
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
            '<div class="kpi-row risk-hero" style="grid-template-columns:1fr 1fr 1fr 1fr;">'
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

    # ── Sections with vertical spacing ─────────────────────
    with ui.element("div").classes("risk-sections w-full"):
        # Analytics table (full width)
        _render_flat_table(
            portfolio_df, analytics_df, fund_rows, price_data_1y,
            currency_symbol, portfolio_color_map, base_currency=currency,
        )

        # Correlation + Sector + Rebalancing — three wide
        with ui.element("div").classes("risk-triple w-full"):
            if has_corr:
                _render_correlation_heatmap(price_data_1y, tickers)
            else:
                ui.element("div")
            _render_sector_breakdown(fund_rows, portfolio_df, portfolio_color_map)
            _render_rebalancing_calculator(fund_rows, portfolio_df, currency_symbol)
