"""Stock Research tab — evaluate any ticker with fundamentals, portfolio fit,
peer comparison, price chart, and news."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from nicegui import app, run, ui

from src.data_fetch import (
    fetch_company_name,
    fetch_fundamentals,
    fetch_ticker_news,
    fetch_sector_peers,
    fetch_sector_medians,
    fetch_analytics_history,
    fetch_price_history_range,
)
from src.fx import get_ticker_currency, get_fx_rate, CURRENCY_SYMBOLS
from src.health import compute_health_score, simulate_addition, ticker_to_region
from src.portfolio import build_portfolio_df
from src.theme import (
    TEXT_PRIMARY,
    TEXT_MUTED,
    TEXT_DIM,
    TEXT_FAINT,
    BG_PILL,
    BG_CARD,
    BORDER,
    BORDER_INPUT,
    BORDER_SUBTLE,
    GREEN,
    RED,
    AMBER,
    ACCENT,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_time_ago(unix_timestamp: int | float) -> str:
    """Convert a unix timestamp to a relative time string."""
    if not unix_timestamp:
        return ""
    diff = time.time() - unix_timestamp
    if diff < 0:
        return "just now"
    minutes = diff / 60
    if minutes < 60:
        return f"{int(minutes)}m ago"
    hours = minutes / 60
    if hours < 24:
        return f"{int(hours)}h ago"
    days = hours / 24
    if days < 30:
        return f"{int(days)}d ago"
    months = days / 30
    return f"{int(months)}mo ago"


def _fmt_market_cap(value: float | None) -> str:
    """Format market cap to human-readable string."""
    if value is None:
        return "\u2014"
    if value >= 1e12:
        return f"${value / 1e12:.1f}T"
    if value >= 1e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e6:
        return f"${value / 1e6:.0f}M"
    return f"${value:,.0f}"


def _flat_tickers(stock_options: dict) -> list[str]:
    """Extract a flat list of tickers from stock_options groups."""
    tickers = []
    for group_tickers in stock_options.values():
        if isinstance(group_tickers, dict):
            tickers.extend(group_tickers.keys())
        elif isinstance(group_tickers, list):
            tickers.extend(group_tickers)
    return tickers


# ── Disclaimer ───────────────────────────────────────────────────────────────

def _render_disclaimer() -> None:
    """Amber disclaimer banner (same as health tab)."""
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


# ── Renderers ────────────────────────────────────────────────────────────────

def _render_company_header(
    ticker: str,
    name: str,
    fund: dict,
    extra_info: dict,
    currency_symbol: str,
    currency: str,
) -> None:
    """Company name, sector, country | current price, daily change."""
    sector = fund.get("Sector", "Unknown")
    country = extra_info.get("country", "")
    price = fund.get("Current Price")
    prev_close = extra_info.get("previousClose")

    with ui.row().classes("w-full items-center justify-between").style(
        f"background:{BG_CARD};border:1px solid {BORDER};border-radius:10px;"
        f"padding:10px 16px;"
    ):
        # Left: company info
        with ui.column().style("gap:2px;"):
            ui.label(name).style(
                f"font-size:18px;font-weight:700;color:{TEXT_PRIMARY};"
            )
            parts = [ticker]
            if sector and sector != "Unknown":
                parts.append(sector)
            if country:
                parts.append(country)
            parts.append(currency)
            ui.label(" | ".join(parts)).style(
                f"font-size:11px;color:{TEXT_MUTED};"
            )

        # Right: price + change
        if price:
            with ui.column().style("gap:2px;align-items:flex-end;"):
                ui.label(f"{currency_symbol}{price:,.2f}").style(
                    f"font-size:22px;font-weight:700;color:{TEXT_PRIMARY};"
                )
                if prev_close and prev_close > 0:
                    change = price - prev_close
                    change_pct = (change / prev_close) * 100
                    color = GREEN if change >= 0 else RED
                    arrow = "\u25b2" if change >= 0 else "\u25bc"
                    ui.label(
                        f"{arrow} {currency_symbol}{abs(change):,.2f} ({change_pct:+.2f}%)"
                    ).style(f"font-size:12px;font-weight:600;color:{color};")


def _render_fundamentals(
    fund: dict,
    extra_info: dict,
    currency_symbol: str,
    medians: dict,
) -> None:
    """Grid of fundamental metric cards."""
    pe = fund.get("P/E Ratio")
    div_yield = fund.get("Div Yield (%)")
    market_cap = extra_info.get("marketCap")
    beta = extra_info.get("beta")
    low = fund.get("1-Year Low")
    high = fund.get("1-Year High")
    target = fund.get("Target Price")

    median_pe = medians.get("median_pe")
    median_dy = medians.get("median_div_yield")

    def _metric_card(label: str, value: str, context: str = "") -> None:
        with ui.column().style(
            f"background:{BG_PILL};border:1px solid {BORDER_SUBTLE};"
            f"border-radius:8px;padding:12px 14px;min-height:80px;"
        ):
            ui.label(label).style(
                f"font-size:10px;font-weight:700;letter-spacing:0.1em;"
                f"text-transform:uppercase;color:{TEXT_FAINT};margin-bottom:4px;"
            )
            ui.label(value).style(
                f"font-size:18px;font-weight:700;color:{TEXT_PRIMARY};"
            )
            if context:
                ui.label(context).style(
                    f"font-size:10px;color:{TEXT_DIM};margin-top:2px;"
                )

    with ui.element("div").classes("fundamentals-grid").style(
        "display:grid;grid-template-columns:repeat(3,1fr);gap:var(--grid-gap);width:100%;"
    ):
        # P/E
        pe_ctx = ""
        if pe and median_pe:
            direction = "Above" if pe > median_pe else "Below"
            pe_ctx = f"{direction} sector median ({median_pe})"
        _metric_card("P/E Ratio", f"{pe:.1f}" if pe else "\u2014", pe_ctx)

        # Div Yield
        dy_ctx = ""
        if div_yield and median_dy:
            direction = "Above" if div_yield > median_dy else "Below"
            dy_ctx = f"{direction} sector median ({median_dy}%)"
        _metric_card(
            "Div Yield",
            f"{div_yield:.2f}%" if div_yield else "\u2014",
            dy_ctx,
        )

        # Market Cap
        _metric_card("Market Cap", _fmt_market_cap(market_cap))

        # Beta
        beta_ctx = ""
        if beta is not None:
            if beta > 1.2:
                beta_ctx = "Higher volatility than market"
            elif beta < 0.8:
                beta_ctx = "Lower volatility than market"
            else:
                beta_ctx = "Near market volatility"
        _metric_card(
            "Beta",
            f"{beta:.2f}" if beta is not None else "\u2014",
            beta_ctx,
        )

        # 52-Week Range
        range_str = "\u2014"
        if low and high:
            range_str = f"{currency_symbol}{low:,.2f} - {currency_symbol}{high:,.2f}"
        _metric_card("52-Week Range", range_str)

        # Analyst Target
        target_ctx = ""
        if target and fund.get("Current Price"):
            cur = fund["Current Price"]
            upside = (target - cur) / cur * 100
            target_ctx = f"{'Upside' if upside >= 0 else 'Downside'}: {upside:+.1f}%"
        _metric_card(
            "Analyst Target",
            f"{currency_symbol}{target:,.2f}" if target else "\u2014",
            target_ctx,
        )


async def _render_portfolio_fit(
    ticker: str,
    fund: dict,
    extra_info: dict,
    portfolio: dict,
    currency: str,
) -> None:
    """Show current -> projected health score with impact bullets."""
    if not portfolio:
        ui.html(
            f'<div style="background:{BG_PILL};border:1px solid {BORDER_SUBTLE};'
            f'border-radius:8px;padding:20px;text-align:center;">'
            f'<span style="font-size:12px;color:{TEXT_DIM};">'
            "Add positions to see portfolio fit."
            "</span></div>"
        )
        return

    def _compute_fit():
        # Build current portfolio inputs
        df = build_portfolio_df(portfolio, currency)
        if df.empty:
            return None

        tickers = list(portfolio.keys())
        total_value = df["Total Value"].sum()
        if total_value == 0:
            return None

        weights = {}
        for t in tickers:
            t_val = df[df["Ticker"] == t]["Total Value"].sum()
            weights[t] = t_val / total_value

        sectors = set()
        regions = set()
        for t in tickers:
            f = fetch_fundamentals(t)
            s = f.get("Sector", "Unknown")
            if s and s != "Unknown":
                sectors.add(s)
            regions.add(ticker_to_region(t))

        # Compute correlation and vol from price data
        price_data = {}
        for t in tickers:
            hist = fetch_analytics_history(t)
            if not hist.empty:
                price_data[t] = hist

        weighted_avg_corr = _compute_corr(price_data, tickers, weights)
        ann_vol = _compute_vol(price_data, tickers, weights)

        # New ticker info
        new_sector = fund.get("Sector", "Unknown")
        new_region = ticker_to_region(ticker)

        current_portfolio = {
            "weights": weights,
            "sectors": sectors,
            "regions": regions,
            "weighted_avg_corr": weighted_avg_corr,
            "annualized_vol": ann_vol,
        }

        result = simulate_addition(
            current_portfolio,
            new_sector,
            new_region,
            0.5,  # default correlation assumption
            0.05,  # 5% addition weight
        )
        return result

    result = await run.io_bound(_compute_fit)

    with ui.column().style(
        f"background:{BG_PILL};border:1px solid {BORDER_SUBTLE};"
        f"border-radius:8px;padding:16px 18px;width:100%;flex:1;"
    ):
        ui.label("Portfolio Fit Preview").style(
            f"font-size:10px;font-weight:700;letter-spacing:0.12em;"
            f"text-transform:uppercase;color:{TEXT_FAINT};margin-bottom:8px;"
        )

        if result is None:
            ui.label("Could not compute portfolio fit.").style(
                f"font-size:12px;color:{TEXT_DIM};"
            )
            return

        current = result["current_score"]
        projected = result["projected_score"]
        delta = result["delta"]

        delta_color = GREEN if delta >= 0 else RED
        arrow = "\u25b2" if delta >= 0 else "\u25bc"

        # Score display
        with ui.row().classes("items-center").style("gap:12px;margin-bottom:8px;"):
            ui.label(f"{current:.0f}").style(
                f"font-size:24px;font-weight:700;color:{TEXT_PRIMARY};"
            )
            ui.label("\u2192").style(
                f"font-size:18px;color:{TEXT_DIM};"
            )
            ui.label(f"{projected:.0f}").style(
                f"font-size:24px;font-weight:700;color:{TEXT_PRIMARY};"
            )
            ui.label(f"{arrow} {delta:+.1f}").style(
                f"font-size:14px;font-weight:600;color:{delta_color};"
            )

        ui.label(
            f"Simulated impact of adding {ticker} at 5% weight"
        ).style(f"font-size:11px;color:{TEXT_DIM};margin-bottom:6px;")

        # Impact bullets
        for impact in result.get("impacts", []):
            ui.html(
                f'<div style="font-size:11px;color:{TEXT_MUTED};padding:2px 0;">'
                f'\u2022 {impact}</div>'
            )


def _compute_corr(
    price_data: dict[str, pd.DataFrame],
    tickers: list[str],
    weights: dict[str, float],
) -> float | None:
    """Compute weight-adjusted average pairwise correlation."""
    returns = {}
    for t in tickers:
        hist = price_data.get(t)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            r = hist["Close"].pct_change().dropna()
            if len(r) >= 60:
                returns[t] = r
    if len(returns) < 2:
        return None

    valid = list(returns.keys())
    ret_df = pd.DataFrame(returns).dropna()
    if len(ret_df) < 30:
        return None

    corr_matrix = ret_df.corr()
    total_weight = 0.0
    weighted_sum = 0.0
    for i, t1 in enumerate(valid):
        for j, t2 in enumerate(valid):
            if j <= i:
                continue
            pw = weights.get(t1, 0) * weights.get(t2, 0)
            weighted_sum += corr_matrix.loc[t1, t2] * pw
            total_weight += pw
    if total_weight == 0:
        return None
    return weighted_sum / total_weight


def _compute_vol(
    price_data: dict[str, pd.DataFrame],
    tickers: list[str],
    weights: dict[str, float],
) -> float:
    """Compute portfolio-level annualized volatility."""
    returns = {}
    for t in tickers:
        hist = price_data.get(t)
        if hist is not None and not hist.empty and "Close" in hist.columns:
            r = hist["Close"].pct_change().dropna()
            if len(r) >= 30:
                returns[t] = r
    if not returns:
        return 0.0

    ret_df = pd.DataFrame(returns).dropna()
    if ret_df.empty:
        return 0.0

    valid = [t for t in tickers if t in ret_df.columns]
    w_arr = np.array([weights.get(t, 0) for t in valid])
    w_sum = w_arr.sum()
    if w_sum > 0:
        w_arr = w_arr / w_sum

    port_ret = (ret_df[valid] * w_arr).sum(axis=1)
    return float(port_ret.std() * np.sqrt(252))


def _render_price_chart(ticker: str, hist: pd.DataFrame) -> None:
    """Plotly line chart of closing prices, 1Y."""
    import plotly.graph_objects as go

    if hist.empty or "Close" not in hist.columns:
        ui.label("No price history available.").style(
            f"font-size:12px;color:{TEXT_DIM};"
        )
        return

    close = hist["Close"].dropna()
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    if close.empty:
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=close.index,
        y=close.values,
        mode="lines",
        line=dict(color=ACCENT, width=2),
        name=ticker,
        hovertemplate="%{x|%b %d, %Y}<br>$%{y:,.2f}<extra></extra>",
    ))

    fig.update_layout(
        template="plotly",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
        height=320,
        autosize=True,
        showlegend=False,
        hoverlabel=dict(
            bgcolor="#1C1D26",
            bordercolor="#1E293B",
            font=dict(color="#F1F5F9", size=11, family="Inter, sans-serif"),
        ),
    )
    fig.update_xaxes(
        gridcolor="rgba(255,255,255,0.04)",
        tickfont=dict(color="#CBD5E1", size=10),
    )
    fig.update_yaxes(
        gridcolor="rgba(255,255,255,0.04)",
        tickfont=dict(color="#CBD5E1", size=10),
    )

    with ui.column().style(
        f"width:100%;background:{BG_PILL};border:1px solid {BORDER_SUBTLE};"
        f"border-radius:8px;padding:16px 18px;"
    ):
        ui.html(
            f'<div class="chart-title" style="margin-bottom:8px;">Price History (1Y)</div>'
        )
        ui.plotly(fig).style("width:100%;")


async def _render_peers(
    ticker: str,
    fund: dict,
    stock_options: dict,
    currency_symbol: str,
) -> None:
    """Peer comparison table: same-sector stocks."""
    sector = fund.get("Sector", "Unknown")
    if sector == "Unknown" or not stock_options:
        ui.label("No peer data available.").style(
            f"font-size:12px;color:{TEXT_DIM};"
        )
        return

    candidates = _flat_tickers(stock_options)

    def _fetch():
        return fetch_sector_peers(sector, candidates, ticker, max_peers=4)

    peers = await run.io_bound(_fetch)

    if not peers:
        ui.label("No peers found in this sector.").style(
            f"font-size:12px;color:{TEXT_DIM};"
        )
        return

    # Build the table including the researched stock
    researched = {
        "ticker": ticker,
        "name": fund.get("_name", ticker),
        "pe": fund.get("P/E Ratio"),
        "div_yield": fund.get("Div Yield (%)"),
        "beta": fund.get("_beta"),
        "return_1y": fund.get("_return_1y"),
    }
    all_rows = [researched] + peers

    header = (
        "<thead><tr>"
        '<th>Company</th>'
        '<th class="right">P/E</th>'
        '<th class="right">Yield</th>'
        '<th class="right">Beta</th>'
        '<th class="right">1Y Return</th>'
        "</tr></thead>"
    )

    body_rows = []
    for row in all_rows:
        is_target = row["ticker"] == ticker
        style = f"color:{ACCENT};font-weight:700;" if is_target else ""
        pe_str = f'{row["pe"]:.1f}' if row.get("pe") else "\u2014"
        dy_str = f'{row["div_yield"]:.2f}%' if row.get("div_yield") else "\u2014"
        beta_str = f'{row["beta"]:.2f}' if row.get("beta") else "\u2014"
        ret_str = "\u2014"
        if row.get("return_1y") is not None:
            r = row["return_1y"]
            color = GREEN if r >= 0 else RED
            ret_str = f'<span style="color:{color};font-weight:600;">{r:+.1f}%</span>'

        body_rows.append(
            f'<tr>'
            f'<td style="{style}">{row.get("name", row["ticker"])} ({row["ticker"]})</td>'
            f'<td class="right" style="{style}">{pe_str}</td>'
            f'<td class="right" style="{style}">{dy_str}</td>'
            f'<td class="right" style="{style}">{beta_str}</td>'
            f'<td class="right">{ret_str}</td>'
            f'</tr>'
        )

    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div class="chart-title" style="margin-bottom:8px;">Peer Comparison</div>'
        )
        ui.html(
            f'<div class="table-wrap"><table>{header}<tbody>'
            f"{''.join(body_rows)}"
            f"</tbody></table></div>"
        )


def _render_news(news_items: list[dict]) -> None:
    """Chronological news list with external links."""
    if not news_items:
        ui.label("No recent news available.").style(
            f"font-size:12px;color:{TEXT_DIM};"
        )
        return

    with ui.column().classes("chart-card w-full"):
        ui.html(
            f'<div class="chart-title" style="margin-bottom:8px;">Recent News</div>'
        )
        for item in sorted(
            news_items,
            key=lambda x: x.get("providerPublishTime", 0),
            reverse=True,
        ):
            title = item.get("title", "")
            link = item.get("link", "")
            publisher = item.get("publisher", "")
            ts = item.get("providerPublishTime", 0)
            time_ago = _format_time_ago(ts)

            meta_parts = []
            if publisher:
                meta_parts.append(publisher)
            if time_ago:
                meta_parts.append(time_ago)
            meta = " \u00b7 ".join(meta_parts)

            ui.html(
                f'<div style="padding:6px 0;border-bottom:1px solid {BORDER_SUBTLE};">'
                f'<a href="{link}" target="_blank" rel="noopener" '
                f'style="font-size:12px;color:{TEXT_PRIMARY};text-decoration:none;'
                f'font-weight:500;line-height:1.4;">{title}</a>'
                f'<div style="font-size:10px;color:{TEXT_DIM};margin-top:2px;">{meta}</div>'
                f'</div>'
            )


# ── Main entry point ─────────────────────────────────────────────────────────

async def build_research_tab(
    portfolio: dict,
    currency: str,
    stock_options: dict | None = None,
) -> None:
    """Build the Stock Research tab."""
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")
    stock_options = stock_options or getattr(app.state, "stock_options", None) or {}

    # Build select options from stock_options (dict of group -> {ticker: name} or [tickers])
    select_opts = {}
    for group_tickers in stock_options.values():
        if isinstance(group_tickers, dict):
            for t, name in group_tickers.items():
                select_opts[t] = name if name != t else t
        elif isinstance(group_tickers, list):
            for t in group_tickers:
                select_opts[t] = t

    _render_disclaimer()

    # Results container
    results_container = ui.column().classes("w-full")

    # Recent searches
    recent = app.storage.user.get("recent_searches", [])

    async def _do_search(ticker: str) -> None:
        if not ticker:
            return

        ticker = ticker.strip().upper()

        # Update recent searches
        recent_list = app.storage.user.get("recent_searches", [])
        if ticker in recent_list:
            recent_list.remove(ticker)
        recent_list.insert(0, ticker)
        recent_list = recent_list[:10]
        app.storage.user["recent_searches"] = recent_list
        _refresh_recent.refresh()

        # Show loading
        results_container.clear()
        with results_container:
            spinner = ui.spinner("dots", size="xl").classes("self-center")

        # Fetch all data
        def _fetch_all():
            import yfinance as yf
            name = fetch_company_name(ticker)
            fund = fetch_fundamentals(ticker)

            # Extra info not in fetch_fundamentals
            extra_info = {}
            try:
                info = yf.Ticker(ticker).info
                extra_info["marketCap"] = info.get("marketCap")
                extra_info["beta"] = info.get("beta")
                extra_info["country"] = info.get("country", "")
                extra_info["previousClose"] = info.get("previousClose")
            except Exception:
                pass

            news = fetch_ticker_news(ticker)
            hist = fetch_price_history_range(ticker, "1y")

            sector = fund.get("Sector", "Unknown")
            candidates = _flat_tickers(stock_options)
            medians = {}
            if sector != "Unknown" and candidates:
                medians = fetch_sector_medians(sector, candidates)

            # Compute 1Y return for peer table
            return_1y = None
            if not hist.empty and "Close" in hist.columns:
                close = hist["Close"].dropna()
                if isinstance(close, pd.DataFrame):
                    close = close.iloc[:, 0]
                if len(close) >= 2:
                    return_1y = round(
                        (close.iloc[-1] / close.iloc[0] - 1) * 100, 1
                    )

            return name, fund, extra_info, news, hist, medians, return_1y

        try:
            name, fund, extra_info, news, hist, medians, return_1y = (
                await run.io_bound(_fetch_all)
            )
        except Exception as exc:
            results_container.clear()
            with results_container:
                ui.label(f"Error fetching data for {ticker}: {exc}").style(
                    f"font-size:12px;color:{RED};"
                )
            return

        # Stash extra fields for peer table rendering
        fund["_name"] = name
        fund["_beta"] = extra_info.get("beta")
        fund["_return_1y"] = return_1y

        # Render results
        results_container.clear()
        with results_container:
            # Company header
            _render_company_header(
                ticker, name, fund, extra_info, currency_symbol, currency
            )

            # Fundamentals + portfolio fit (single row of cards)
            _render_fundamentals(fund, extra_info, currency_symbol, medians)
            await _render_portfolio_fit(
                ticker, fund, extra_info, portfolio, currency
            )

            # Price chart
            with ui.element("div").classes("price-chart-section").style("width:100%;"):
                _render_price_chart(ticker, hist)

            # Peer comparison
            await _render_peers(ticker, fund, stock_options, currency_symbol)

            # News
            _render_news(news)

    # Search bar
    with ui.row().classes("w-full items-center").style("gap:8px;margin-bottom:12px;"):
        search_select = ui.select(
            options=select_opts,
            with_input=True,
            label="Search ticker...",
            on_change=lambda e: _do_search(e.value) if e.value else None,
        ).props(
            'dense outlined clearable use-input input-debounce="150" behavior="menu"'
        ).style("flex:1;min-width:200px;max-width:400px;")

        # Auto-highlight first filtered option on each keystroke
        search_select.on(
            "input-value",
            lambda: ui.run_javascript(f'''
                setTimeout(() => {{
                    const el = getElement({search_select.id});
                    if (el && el.$refs && el.$refs.qRef) {{
                        const q = el.$refs.qRef;
                        q.setOptionIndex(-1);
                        q.moveOptionSelection(1, true);
                    }}
                }}, 200);
            '''),
        )

    # Recent searches tags
    @ui.refreshable
    def _refresh_recent():
        recent_list = app.storage.user.get("recent_searches", [])
        display = recent_list[:5]
        if display:
            with ui.row().style("gap:6px;margin-bottom:12px;"):
                ui.label("Recent:").style(
                    f"font-size:11px;color:{TEXT_DIM};align-self:center;"
                )
                for t in display:
                    ui.button(
                        t,
                        on_click=lambda ticker=t: _do_search(ticker),
                    ).props("flat dense no-caps size=sm").style(
                        f"font-size:11px;color:{TEXT_MUTED};background:{BG_PILL};"
                        f"border:1px solid {BORDER_SUBTLE};border-radius:4px;"
                        f"padding:6px 10px;min-height:28px;"
                    )

    _refresh_recent()
