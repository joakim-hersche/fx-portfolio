"""Portfolio Health tab for the NiceGUI dashboard.

Replaces the Risk & Analytics tab with a health-score-first layout:
disclaimer, score circle, findings cards, sector exposure,
collapsible detailed metrics, and rebalancing calculator.
"""

import time as _time

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
from src.health import compute_health_score, generate_findings, ticker_to_region
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


# ── Disclaimer ───────────────────────────────────────────────────────────────

def _render_disclaimer() -> None:
    """Amber disclaimer banner."""
    ui.html(
        '<div style="background:rgba(217,119,6,0.06);border:1px solid rgba(217,119,6,0.15);'
        'border-radius:6px;padding:10px 14px;margin-bottom:16px;">'
        '<div style="color:#D97706;font-size:11px;line-height:1.5;">'
        '<strong>For informational purposes only.</strong> '
        'This tool provides data and calculations to support your own research. '
        'It does not constitute financial advice, investment recommendations, or '
        'solicitation to buy or sell securities. Past performance does not predict '
        'future results. Always consult a qualified financial advisor before making '
        'investment decisions.'
        '</div></div>'
    )


# ── Health Score ─────────────────────────────────────────────────────────────

def _score_color(score: float, max_score: float) -> str:
    """Green >= 70%, amber 40-70%, red < 40%."""
    pct = score / max_score if max_score > 0 else 0
    if pct >= 0.7:
        return "#16A34A"
    if pct >= 0.4:
        return "#D97706"
    return "#DC2626"


def _render_health_score(score_result: dict) -> None:
    """Render circular health score badge + expandable methodology."""
    total = score_result["total"]
    components = score_result["components"]
    color = _score_color(total, 100)

    # Score circle
    ui.html(
        f'<div class="health-score-container" style="display:flex;align-items:center;gap:20px;padding:16px;'
        f'background:rgba(59,130,246,0.05);border:1px solid rgba(59,130,246,0.15);'
        f'border-radius:12px;margin-bottom:16px;">'
        f'<div style="width:80px;height:80px;border-radius:50%;border:4px solid {color};'
        f'display:flex;align-items:center;justify-content:center;flex-shrink:0;'
        f'font-size:2rem;font-weight:700;color:#F1F5F9;">{total:.0f}</div>'
        f'<div>'
        f'<div style="font-size:14px;font-weight:600;color:#F1F5F9;">Portfolio Health Score</div>'
        f'<div style="color:#94A3B8;font-size:12px;margin-top:4px;">'
        f'Based on diversification, concentration, volatility, and correlation</div>'
        f'</div></div>'
    )

    # Expandable methodology
    with ui.expansion("How is this calculated?").classes("w-full").style(
        "margin-bottom:16px;"
    ):
        descriptions = {
            "Diversification": {
                "what": "How many distinct sectors and geographies your portfolio spans.",
                "why": "Portfolios spread across more sectors and countries are less exposed to any single downturn.",
            },
            "Concentration": {
                "what": "How evenly your capital is distributed across holdings.",
                "why": "High concentration means a large drop in one or two stocks can significantly impact your total portfolio.",
            },
            "Correlation": {
                "what": "How independently your holdings move from each other.",
                "why": "If all your stocks rise and fall together, diversification is an illusion.",
            },
            "Stability": {
                "what": "How much your portfolio value swings day-to-day.",
                "why": "Lower volatility means fewer large swings — easier to hold through downturns.",
            },
        }

        cards_html = ""
        for comp in components:
            name = comp["name"]
            score = comp["score"]
            max_s = comp["max_score"]
            c = _score_color(score, max_s)
            pct = score / max_s * 100 if max_s > 0 else 0
            desc = descriptions.get(name, {"what": "", "why": ""})

            cards_html += (
                f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
                f'border-radius:8px;padding:12px;display:flex;flex-direction:column;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
                f'<div><span style="font-weight:600;color:#F1F5F9;">{name}</span>'
                f'<span style="color:#64748B;font-size:12px;margin-left:8px;">{max_s}% of score</span></div>'
                f'<div style="font-size:14px;font-weight:700;color:{c};">{score:.0f}'
                f'<span style="font-size:11px;font-weight:400;color:#64748B;"> / {max_s}</span></div></div>'
                f'<div style="height:6px;background:rgba(255,255,255,0.05);border-radius:3px;margin-bottom:8px;">'
                f'<div style="height:100%;width:{pct:.0f}%;background:{c};border-radius:3px;"></div></div>'
                f'<div style="color:#94A3B8;font-size:12px;line-height:1.5;flex:1;">'
                f'<strong style="color:#F1F5F9;">What it measures:</strong> {desc["what"]}<br>'
                f'<strong style="color:#F1F5F9;">Why it matters:</strong> {desc["why"]}'
                f'</div></div>'
            )

        ui.html(
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">'
            f'{cards_html}</div>'
        )


# ── Findings ─────────────────────────────────────────────────────────────────

def _render_findings(findings: list[dict]) -> None:
    """Render diagnostic finding cards in a horizontal row."""
    if not findings:
        return

    _section_header("Key Findings")

    severity_colors = {"red": "#DC2626", "amber": "#D97706", "green": "#16A34A"}
    severity_bgs = {
        "red": "rgba(220,38,38,0.06)",
        "amber": "rgba(217,119,6,0.06)",
        "green": "rgba(22,163,74,0.06)",
    }

    cards_html = ""
    for finding in findings:
        color = severity_colors.get(finding["severity"], "#94A3B8")
        bg = severity_bgs.get(finding["severity"], "transparent")
        cards_html += (
            f'<div style="flex:1;min-width:0;background:{bg};border-left:3px solid {color};'
            f'padding:10px 14px;border-radius:0 6px 6px 0;">'
            f'<div style="font-weight:600;color:#F1F5F9;font-size:13px;">{finding["headline"]}</div>'
            f'<div style="color:#94A3B8;font-size:12px;margin-top:3px;">{finding["body"]}</div>'
            f'</div>'
        )

    ui.html(
        f'<div class="findings-row" style="display:flex;gap:8px;flex-wrap:wrap;">'
        f'{cards_html}</div>'
    )


# ── Weighted correlation & portfolio volatility helpers ──────────────────────

def _compute_weighted_corr(
    price_data_1y: dict[str, pd.DataFrame],
    tickers: list[str],
    weights: dict[str, float],
) -> float | None:
    """Compute weight-adjusted average pairwise Pearson correlation.
    Returns None if < 2 tickers have sufficient data.

    1. Daily returns for each ticker from price_data_1y
    2. Pairwise correlation matrix
    3. For each pair (i,j): pair_weight = weights[i] * weights[j]
    4. weighted_avg = sum(corr * pair_weight) / sum(pair_weight)
    """
    returns = {}
    for t in tickers:
        hist = price_data_1y.get(t)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            r = hist["Close"].pct_change().dropna()
            if len(r) >= 60:
                returns[t] = r
    if len(returns) < 2:
        return None

    corr_df = pd.DataFrame(returns).dropna().corr()
    labels = list(corr_df.columns)
    total_weight = 0.0
    weighted_sum = 0.0
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            w = weights.get(labels[i], 0) * weights.get(labels[j], 0)
            weighted_sum += corr_df.iloc[i, j] * w
            total_weight += w
    if total_weight <= 0:
        return None
    return weighted_sum / total_weight


def _compute_portfolio_vol(
    price_data_1y: dict[str, pd.DataFrame],
    tickers: list[str],
    weights: dict[str, float],
) -> float:
    """Compute portfolio-level annualized volatility.

    1. Build aligned daily returns DataFrame
    2. Portfolio daily return = sum(weight_i * return_i)
    3. Annualized vol = std(portfolio_returns) * sqrt(252)
    """
    returns = {}
    for t in tickers:
        hist = price_data_1y.get(t)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            r = hist["Close"].pct_change().dropna()
            if len(r) >= 30:
                returns[t] = r
    if not returns:
        return 0.0

    df = pd.DataFrame(returns).dropna()
    if df.empty:
        return 0.0

    # Portfolio daily return (weight-adjusted)
    portfolio_returns = sum(
        df[t] * weights.get(t, 0) for t in df.columns
    )
    return float(portfolio_returns.std() * (252 ** 0.5))


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
                total_cost = group["Cost Basis"].sum()
                total_value = group["Total Value"].sum()
                total_divs = group["Dividends"].sum()
                if total_cost > 0:
                    ticker_data.at[idx, "Return (%)"] = round(
                        (total_value + total_divs - total_cost) / total_cost * 100, 2
                    )

        # Benchmark 1-year return (already in base currency)
        bench_hist = price_data_1y.get("__bench__", pd.DataFrame())
        spy_return = None
        if not bench_hist.empty and "Close" in bench_hist.columns:
            bench_close = bench_hist["Close"].dropna()
            if len(bench_close) >= 2:
                spy_return = (bench_close.iloc[-1] / bench_close.iloc[0] - 1) * 100

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
                    "Sortino Ratio": arow.get("Sortino Ratio"),
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
            sortino = a.get("Sortino Ratio")
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
            sortino_cls = _color_class(sortino, [
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
                f'<td class="{sortino_cls} right">{_fmt(sortino, "{:.1f}")}</td>'
                f'<td class="right">{_fmt(beta, "{:.1f}")}</td>'
                f'<td class="right">{_fmt(pe, "{:.0f}\u00d7")}</td>'
                f'<td class="right">{_fmt(div_yield, "{:.1f}%")}</td>'
                f'<td>{range_html}</td>'
                f'<td class="right">{current_html}</td>'
                f'</tr>'
            )

        ui.html(f'''
        <div class="table-wrap" style="overflow-x:auto;">
        <table class="wide-table" style="min-width:1200px;border-collapse:separate;border-spacing:0;">
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


# ── Sector Breakdown ────────────────────────────────────────────────────────

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
    portfolio_color_map: dict[str, str] | None = None,
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
                ticker_color = (portfolio_color_map or {}).get(ticker, color)  # fallback to sector color
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
        top_sector = sector_order[0] if sector_order else "\u2014"
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
    with ui.column().classes("chart-card w-full"):
        _section_header("Rebalancing Calculator")
        ui.html(
            f'<p style="font-size:12px;color:{TEXT_DIM};line-height:1.6;margin:0 0 12px 0;">'
            f'Set target weights and enter a deposit amount to see buy-only suggestions. '
            f'<span style="color:{AMBER};">Not a recommendation.</span></p>'
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

                diff = tgt - cur
                if abs(diff) < 0.5:
                    bar_fill_color = ACCENT
                elif diff > 0:
                    bar_fill_color = GREEN
                else:
                    bar_fill_color = AMBER

                buy_html = ""
                if shares > 0:
                    s_label = "share" if shares == 1 else "shares"
                    buy_html = (
                        f'<div style="display:flex;align-items:center;gap:5px;margin-top:4px;">'
                        f'<div style="width:5px;height:5px;border-radius:50%;background:{GREEN};"></div>'
                        f'<span style="font-size:10px;font-weight:600;color:{GREEN};">Buy {shares} {s_label}</span>'
                        f'<span style="font-size:10px;color:{TEXT_DIM};">({currency_symbol}{amount:,.0f})</span>'
                        f'</div>'
                    )

                # Target marker: thin line at target position
                tgt_marker = ""
                if abs(diff) >= 0.5:
                    tgt_marker = (
                        f'<div style="position:absolute;left:{min(tgt, 100):.1f}%;top:-1px;'
                        f'width:2px;height:calc(100% + 2px);background:{bar_fill_color};'
                        f'border-radius:1px;"></div>'
                    )

                bar_containers[t].clear()
                with bar_containers[t]:
                    ui.html(
                        f'<div style="height:8px;background:rgba(255,255,255,0.08);'
                        f'border-radius:4px;position:relative;overflow:visible;">'
                        f'<div style="position:absolute;left:0;width:{min(cur, 100):.1f}%;'
                        f'height:100%;background:{bar_fill_color};border-radius:4px;'
                        f'opacity:0.7;"></div>'
                        f'{tgt_marker}'
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
                    tgt_color = AMBER if total_tgt < 99.5 or total_tgt > 100.5 else GREEN
                    parts.append(
                        f'<span style="font-size:11px;font-weight:600;color:{tgt_color};">'
                        f'Total target: {total_tgt:.1f}%</span>'
                    )
                    if deposit > 0 and remaining > 0.01:
                        parts.append(
                            f'<span style="font-size:11px;color:{TEXT_DIM};">'
                            f'{currency_symbol}{remaining:.2f} unallocated</span>'
                        )
                    ui.html(
                        f'<div style="display:flex;justify-content:space-between;'
                        f'padding-top:8px;margin-top:4px;'
                        f'border-top:1px solid {BORDER_SUBTLE};">'
                        f'{"".join(parts)}</div>'
                    )

        # ── Deposit + Reset row ──
        input_style = (
            f"background:{BG_PILL};border:1px solid {BORDER_INPUT};"
            f"border-radius:4px;padding:0 6px;"
        )

        initial_weights: dict[str, float] = dict(target_weights)
        target_inputs: dict[str, ui.number] = {}

        with ui.row().classes("w-full items-center justify-between").style(
            f"margin-bottom:14px;padding:10px 12px;"
            f"background:rgba(255,255,255,0.02);border-radius:8px;"
            f"border:1px solid {BORDER_SUBTLE};"
        ):
            with ui.row().classes("items-center").style("gap:10px;"):
                ui.html(
                    f'<span style="font-size:11px;font-weight:600;color:{TEXT_MUTED};">'
                    f'Deposit amount</span>'
                )
                deposit_input = ui.number(
                    value=0, min=0, format="%.0f", prefix=currency_symbol,
                ).props("dense borderless").style(f"width:140px;{input_style}")

                def _on_deposit(e):
                    deposit_ref["value"] = e.value or 0.0
                    _recalculate()
                deposit_input.on_value_change(_on_deposit)

            def _reset_targets():
                for t, w in initial_weights.items():
                    target_weights[t] = w
                    if t in target_inputs:
                        target_inputs[t].value = round(w)
                deposit_ref["value"] = 0.0
                deposit_input.value = 0
                _recalculate()

            ui.button("Reset", on_click=_reset_targets).props(
                "flat dense no-caps size=sm"
            ).style(
                f"font-size:11px;color:{TEXT_DIM};border:1px solid {BORDER_SUBTLE};"
                f"border-radius:4px;padding:4px 12px;"
            )

        # ── Column headers ──
        # ── Column headers (widths match the single-block ticker row) ──
        _hdr = (
            f"font-size:9px;font-weight:600;text-transform:uppercase;"
            f"letter-spacing:0.08em;color:{TEXT_MUTED};"
        )
        ui.html(
            f'<div style="display:flex;align-items:center;padding:0 0 6px 16px;gap:4px;'
            f'border-bottom:1px solid {BORDER_SUBTLE};">'
            f'<div style="display:flex;width:130px;flex-shrink:0;">'
            f'<span style="flex:1;{_hdr}">Ticker</span>'
            f'<span style="width:36px;flex-shrink:0;{_hdr}text-align:right;">Now</span>'
            f'<span style="width:20px;flex-shrink:0;"></span>'
            f'</div>'
            f'<span style="width:64px;flex-shrink:0;{_hdr}">Target</span>'
            f'<span style="flex:1;{_hdr}">Drift</span>'
            f'</div>'
        ).classes("w-full")

        # ── Sector-grouped rows ──
        for sector in sector_order:
            color = sector_color_map[sector]
            total = sector_totals.get(sector, 0)

            # Sector header
            ui.html(
                f'<div style="display:flex;align-items:center;gap:8px;'
                f'padding:10px 0 4px 0;margin-top:4px;">'
                f'<div style="width:6px;height:6px;border-radius:2px;'
                f'background:{color};flex-shrink:0;"></div>'
                f'<span style="font-size:11px;font-weight:700;color:{TEXT_MUTED};'
                f'text-transform:uppercase;letter-spacing:0.06em;">{sector}</span>'
                f'<span style="font-size:11px;font-weight:700;color:{TEXT_SECONDARY};">'
                f'{total:.1f}%</span>'
                f'</div>'
            ).classes("w-full")

            # Ticker rows
            for ticker in sector_tickers_grouped.get(sector, []):
                td_row = ticker_data[ticker_data["Ticker"] == ticker]
                if td_row.empty:
                    continue
                current_w = td_row.iloc[0]["Weight (%)"]

                with ui.row().classes("w-full items-center no-wrap").style(
                    "padding:3px 0 3px 16px;gap:4px;"
                ):
                    # Single HTML block for ticker + now% + arrow = fixed 130px
                    ui.html(
                        f'<div style="display:flex;align-items:center;width:130px;flex-shrink:0;">'
                        f'<span style="flex:1;font-size:11px;color:{TEXT_DIM};'
                        f'overflow:hidden;text-overflow:ellipsis;'
                        f'white-space:nowrap;">{ticker}</span>'
                        f'<span style="width:36px;flex-shrink:0;font-size:11px;color:{TEXT_DIM};'
                        f'text-align:right;">{current_w:.0f}%</span>'
                        f'<span style="width:20px;flex-shrink:0;font-size:10px;color:{TEXT_DIM};'
                        f'text-align:center;">&rarr;</span>'
                        f'</div>'
                    )
                    inp = ui.number(
                        value=round(current_w),
                        min=0, max=100, step=1, format="%.0f",
                        suffix="%",
                    ).props("dense outlined").style(
                        "font-size:11px;width:64px;flex-shrink:0;"
                    )
                    target_inputs[ticker] = inp

                    def _make_handler(t):
                        def handler(e):
                            target_weights[t] = e.value if e.value is not None else 0.0
                            _recalculate()
                        return handler
                    inp.on_value_change(_make_handler(ticker))

                    with ui.element("div").style(
                        "flex:1 1 auto;padding:0 0 0 4px;min-width:80px;"
                    ):
                        bar_containers[ticker] = ui.element("div").classes("w-full")

        footer_ref["ref"] = ui.column().classes("w-full").style("margin-top:4px;")
        _recalculate()


# ── Public entry point ───────────────────────────────────────────────────────

def _format_time_ago(unix_timestamp: int) -> str:
    if not unix_timestamp:
        return ""
    diff = int(_time.time()) - unix_timestamp
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    days = diff // 86400
    return f"{days}d ago"


async def _render_portfolio_news(tickers, color_map):
    from src.data_fetch import fetch_ticker_news

    def _fetch_all_news():
        all_news = []
        for ticker in tickers:
            for item in fetch_ticker_news(ticker):
                item["ticker"] = ticker
                all_news.append(item)
        all_news.sort(key=lambda x: x.get("providerPublishTime", 0), reverse=True)
        return all_news[:20]

    news_items = await run.io_bound(_fetch_all_news)

    with ui.column().classes("chart-card w-full"):
        if not news_items:
            ui.html(f'<p style="color:{TEXT_DIM};font-size:12px;">No recent news for your holdings.</p>')
            return

        for item in news_items:
            ticker = item.get("ticker", "")
            dot_color = color_map.get(ticker, TEXT_DIM)
            time_ago = _format_time_ago(item.get("providerPublishTime", 0))

            ui.html(
                f'<div style="display:flex;gap:8px;align-items:baseline;'
                f'padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);">'
                f'<span style="font-size:11px;font-weight:600;color:{dot_color};'
                f'white-space:nowrap;min-width:50px;">{ticker}</span>'
                f'<div style="flex:1;">'
                f'<a href="{item.get("link", "#")}" target="_blank" rel="noopener" '
                f'style="color:{TEXT_PRIMARY};font-size:12px;text-decoration:none;">'
                f'{item.get("title", "")}</a>'
                f'<div style="font-size:10px;color:{TEXT_DIM};">'
                f'{item.get("publisher", "")} &middot; {time_ago}</div>'
                f'</div></div>'
            )


async def build_health_tab(portfolio: dict, currency: str) -> None:
    """Render the full Portfolio Health tab content.

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
            '<p style="color:#7B8BA0;font-size:13px;padding:20px 0;">'
            'Add positions to see portfolio health.</p>'
        )
        return

    _render_disclaimer()

    # ── Fetch data (off the event loop) ──────────────────────────────────
    def _fetch_health_data():
        from concurrent.futures import ThreadPoolExecutor

        # Fetch all analytics histories + benchmark in parallel
        _BENCH_MAP = {
            "USD": "SPY",
            "CHF": "^SSMI",
            "EUR": "^STOXX50E",
            "GBP": "^FTSE",
            "SEK": "^OMX",
        }
        bench_ticker = _BENCH_MAP.get(currency, "SPY")
        all_tickers = tickers + [bench_ticker]
        with ThreadPoolExecutor(max_workers=min(10, len(all_tickers))) as ex:
            hist_results = dict(ex.map(lambda t: (t, fetch_analytics_history(t)), all_tickers))

        price_data_1y: dict[str, pd.DataFrame] = {}
        for t in tickers:
            hist = hist_results.get(t, pd.DataFrame())
            if not hist.empty:
                price_data_1y[t] = hist
        bench_data = hist_results.get(bench_ticker, pd.DataFrame())
        if not bench_data.empty:
            price_data_1y["__bench__"] = bench_data
        analytics_df = compute_analytics(portfolio, price_data_1y, bench_data, currency)
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

    result = await run.io_bound(_fetch_health_data)
    if result is None:
        ui.html('<div style="color:#7B8BA0;font-size:13px;padding:24px;">'
                'Could not load health data. Please try reloading.</div>')
        return
    price_data_1y, analytics_df, fund_rows, portfolio_df = result

    # Color map
    portfolio_color_map: dict[str, str] = {
        t: TICKER_COLORS.get(t, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
        for i, t in enumerate(portfolio.keys())
    }

    # Compute health score inputs
    ticker_weights_decimal = (
        portfolio_df.groupby("Ticker")["Weight (%)"].sum() / 100
    ).to_dict()

    sectors = set()
    regions = set()
    for fr in fund_rows:
        sector = fr.get("Sector", "Unknown")
        if sector and sector != "Unknown":
            sectors.add(sector)
        regions.add(ticker_to_region(fr["Ticker"]))

    sector_weights = {}
    for fr in fund_rows:
        sector = fr.get("Sector", "Unknown")
        w = ticker_weights_decimal.get(fr["Ticker"], 0) * 100
        sector_weights[sector] = sector_weights.get(sector, 0) + w

    weighted_avg_corr = _compute_weighted_corr(price_data_1y, tickers, ticker_weights_decimal)
    annualized_vol = _compute_portfolio_vol(price_data_1y, tickers, ticker_weights_decimal)

    top_holdings = sorted(
        [(t, w * 100) for t, w in ticker_weights_decimal.items()],
        key=lambda x: x[1], reverse=True,
    )

    # Health score
    score_result = compute_health_score(
        ticker_weights_decimal, sectors, regions,
        weighted_avg_corr, annualized_vol,
    )
    _render_health_score(score_result)

    # Findings
    findings = generate_findings(
        ticker_weights_decimal, sectors, regions, sector_weights,
        weighted_avg_corr, annualized_vol, top_holdings,
    )
    _render_findings(findings)

    # Sections
    with ui.element("div").classes("risk-sections w-full"):
        _render_sector_breakdown(fund_rows, portfolio_df, portfolio_color_map)

        # Collapsible detailed metrics (hidden on mobile)
        with ui.element("div").classes("detailed-metrics-section"):
            with ui.expansion("Detailed Metrics").classes("w-full"):
                _render_flat_table(
                    portfolio_df, analytics_df, fund_rows, price_data_1y,
                    currency_symbol, portfolio_color_map, base_currency=currency,
                )
                if len(tickers) >= 2:
                    _render_correlation_heatmap(price_data_1y, tickers)
        ui.html(
            '<div class="touch-only" style="padding:12px 16px;font-size:12px;'
            f'color:{TEXT_DIM};background:{BG_PILL};border-radius:8px;'
            f'border:1px solid {BORDER_SUBTLE};text-align:center;">'
            'Detailed analytics table is available on desktop.'
            '</div>'
        )

        with ui.element("div").classes("rebalancer-section"):
            _render_rebalancing_calculator(fund_rows, portfolio_df, currency_symbol)
        ui.html(
            '<div class="touch-only" style="padding:12px 16px;font-size:12px;'
            f'color:{TEXT_DIM};background:{BG_PILL};border-radius:8px;'
            f'border:1px solid {BORDER_SUBTLE};text-align:center;">'
            'Rebalancing calculator is available on desktop.'
            '</div>'
        )

    _section_header("Portfolio News")
    await _render_portfolio_news(tickers, portfolio_color_map)
