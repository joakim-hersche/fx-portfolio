"""Positions tab — positions table + price history chart (NiceGUI version).

Exports a single function `build_positions_tab` that renders:
1. A styled HTML positions table with conditional formatting
2. A per-ticker price history chart with buy-price overlay and purchase markers
"""

from __future__ import annotations

import json

import pandas as pd
from nicegui import run, ui

from src.charts import (
    CHART_COLORS,
    C_NEGATIVE,
    C_NEUTRAL,
    C_POSITIVE,
    build_price_history_chart,
)
from src.data_fetch import fetch_company_name, fetch_fundamentals, fetch_price_history_long
from src.fx import CURRENCY_SYMBOLS, get_fx_rate, get_ticker_currency
from src.portfolio import build_portfolio_df
from src.stocks import TICKER_COLORS
from src.theme import (
    BG_CARD,
    BORDER,
    TEXT_DIM,
    TEXT_FAINT,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


# ---------------------------------------------------------------------------
# Positions table
# ---------------------------------------------------------------------------

def _color_class(val: float) -> str:
    """Return the CSS class for a positive / negative / neutral value."""
    if val > 0:
        return "td-pos"
    elif val < 0:
        return "td-neg"
    return ""


def _fmt_shares(x: float) -> str:
    return f"{int(x):,}" if x == int(x) else f"{x:g}"


def _fmt_currency(x: float, sym: str) -> str:
    return f"{sym}{x:,.2f}"


def _fmt_return(x) -> str:
    if isinstance(x, (int, float)):
        return f"{x:+,.2f}%"
    return str(x)


def _build_positions_table(
    df: pd.DataFrame,
    name_map: dict[str, str],
    currency_symbol: str,
    portfolio_color_map: dict[str, str] | None = None,
    on_click_bridge_id: int | None = None,
    target_prices: dict[str, float | None] | None = None,
    unavailable_tickers: set[str] | None = None,
) -> None:
    """Render the positions table as a styled HTML table via ui.html().

    If *on_click_bridge_id* is set, each data row emits a ``row_click``
    event (carrying the clean ticker string) when clicked.
    """

    ui.html(
        f'<p style="font-size:12px;color:{TEXT_MUTED};line-height:1.6;margin-bottom:12px;">'
        "Every stock you own, how much you paid, what it's worth now, "
        "and how much you've gained or lost. <b>Target</b> shows the analyst "
        "consensus price target with upside/downside percentage. "
        "<b>Today's Change</b> is how much "
        "your value moved since yesterday's market close. "
        "<b>Total Return</b> includes any dividends received. "
        "<b>Share</b> is what percentage of your total investment "
        "this position represents."
        + (" Click a row to view its price chart below." if on_click_bridge_id else "")
        + "</p>"
    )

    # Hover highlight for clickable rows
    if on_click_bridge_id is not None:
        ui.html(
            "<style>"
            ".table-wrap tbody tr[onclick]:hover {"
            "  background: rgba(59, 130, 246, 0.08) !important;"
            "}"
            "</style>"
        )

    # Detect multi-lot tickers
    multi_tickers = {t for t, g in df.groupby("Ticker", sort=False) if len(g) > 1}

    # Toggle for individual purchases (only shown when multi-lot positions exist)
    show_individual = {"value": False}

    # Container that holds the table so we can refresh it
    table_container = ui.column().classes("w-full")

    def _render_table():
        """Build and inject the HTML table into *table_container*."""
        table_container.clear()

        display_rows: list[pd.DataFrame] = []
        for ticker, group in df.groupby("Ticker", sort=False):
            if len(group) > 1:
                if show_individual["value"]:
                    display_rows.append(group)
                else:
                    total_value_t = group["Total Value"].sum()
                    total_cost_t = (group["Buy Price"] * group["Shares"]).sum()
                    total_divs_t = group["Dividends"].sum()
                    summary = {
                        "Ticker": f"\u25ba {ticker}",
                        "Purchase": "Total",
                        "Shares": group["Shares"].sum(),
                        "Buy Price": round(total_cost_t / group["Shares"].sum(), 2),
                        "Purchase Date": "",
                        "Current Price": group["Current Price"].iloc[0],
                        "Total Value": round(total_value_t, 2),
                        "Dividends": round(total_divs_t, 2),
                        "Daily P&L": round(group["Daily P&L"].sum(), 2),
                        "Return (%)": round(
                            (total_value_t + total_divs_t - total_cost_t)
                            / total_cost_t
                            * 100,
                            2,
                        )
                        if total_cost_t
                        else None,
                        "Weight (%)": round(group["Weight (%)"].sum(), 2),
                    }
                    display_rows.append(pd.DataFrame([summary]))
            else:
                display_rows.append(group)

        display_df = (
            pd.concat(display_rows, ignore_index=True) if display_rows else df.copy()
        )
        display_df["Purchase"] = display_df["Purchase"].astype(str)

        _target_prices = target_prices or {}
        _unavailable = unavailable_tickers or set()

        # Build HTML table
        columns = [
            "Ticker",
            "Company",
            "Lot",
            "Shares",
            "Buy Price",
            "Purchase Date",
            "Current Price",
            "Target",
            "Total Value",
            "Dividends",
            "Day P&L",
            "Return (%)",
            "Share (%)",
        ]

        right_cols = {"Shares", "Buy Price", "Purchase Date", "Current Price",
                      "Target", "Total Value", "Dividends", "Today", "Return (%)", "Weight (%)"}
        _col_tips = {
            "Target": "Analyst consensus price target — the average price Wall Street analysts expect this stock to reach.",
            "Dividends": "Cash dividends received since you bought this position, in your base currency.",
            "Day P&L": "How much this position's value changed since yesterday's market close.",
            "Return (%)": "Total return including dividends — how much you gained or lost as a % of what you paid.",
            "Share (%)": "What percentage of your total portfolio this position represents by value.",
        }
        header_cells = "".join(
            f'<th scope="col" class="right th-tip" title="{_col_tips[c]}">{c}</th>'
            if c in _col_tips and c in right_cols
            else f'<th scope="col" class="th-tip" title="{_col_tips[c]}">{c}</th>'
            if c in _col_tips
            else f'<th scope="col" class="right">{c}</th>'
            if c in right_cols
            else f'<th scope="col">{c}</th>'
            for c in columns
        )
        header = f"<thead><tr>{header_cells}</tr></thead>"

        body_rows: list[str] = []
        for _, row in display_df.iterrows():
            ticker_raw = row["Ticker"]
            is_summary = str(ticker_raw).startswith("\u25ba ")
            clean_ticker = str(ticker_raw).replace("\u25ba ", "")
            company = name_map.get(clean_ticker, clean_ticker)

            daily_pnl = row["Daily P&L"]
            ret_pct = row["Return (%)"]

            daily_cls = _color_class(daily_pnl) if pd.notna(daily_pnl) else ""
            ret_cls = _color_class(ret_pct) if pd.notna(ret_pct) else ""

            row_style = (
                f"font-weight:700;background:rgba(29,78,216,0.08);"
                if is_summary and not show_individual["value"]
                else ""
            )

            # Colored dot for the ticker cell
            dot_color = (portfolio_color_map or {}).get(clean_ticker, "")
            dot_html = (
                f'<div style="width:8px;height:8px;border-radius:50%;background:{dot_color};flex-shrink:0;"></div>'
                if dot_color else ""
            )
            ticker_cell = (
                f'<td style="{row_style}">'
                f'<div style="display:flex;align-items:center;gap:6px;font-weight:700;color:{TEXT_PRIMARY};">'
                f'{dot_html}{ticker_raw}</div></td>'
            )

            # Target price + upside badge
            tp = _target_prices.get(clean_ticker)
            cur_price = row['Current Price']
            if tp and cur_price and cur_price > 0:
                upside_pct = (tp - cur_price) / cur_price * 100
                if upside_pct > 10:
                    badge_cls = "badge-green"
                elif upside_pct >= 0:
                    badge_cls = "badge-amber"
                else:
                    badge_cls = "badge-red"
                arrow = "\u25b2" if upside_pct >= 0 else "\u25bc"
                target_cell = (
                    f'<td style="{row_style}" class="right">'
                    f'{_fmt_currency(tp, currency_symbol)} '
                    f'<span class="kpi-badge {badge_cls}" style="font-size:10px;">'
                    f'{arrow} {upside_pct:+.1f}%</span></td>'
                )
            else:
                target_cell = f'<td style="{row_style}" class="right">\u2014</td>'

            # Unavailable ticker badge
            is_unavailable = clean_ticker in _unavailable
            if is_unavailable:
                company_cell = (
                    f'<td style="{row_style}">{company} '
                    f'<span class="kpi-badge badge-amber" style="font-size:10px;">'
                    f'\u26a0 Data unavailable</span></td>'
                )
            else:
                company_cell = f'<td style="{row_style}">{company}</td>'

            cells = [
                ticker_cell,
                company_cell,
                f"<td style=\"{row_style}\">{row['Purchase']}</td>",
                f"<td style=\"{row_style}\" class=\"right\">{_fmt_shares(row['Shares'])}</td>",
                f"<td style=\"{row_style}\" class=\"right\">{_fmt_currency(row['Buy Price'], currency_symbol)}</td>",
                f"<td style=\"{row_style}\" class=\"right\">{row['Purchase Date']}</td>",
                f"<td style=\"{row_style}\" class=\"right\">{_fmt_currency(row['Current Price'], currency_symbol)}</td>",
                target_cell,
                f"<td style=\"{row_style}\" class=\"right\">{_fmt_currency(row['Total Value'], currency_symbol)}</td>",
                f"<td style=\"{row_style}\" class=\"right\">{_fmt_currency(row['Dividends'], currency_symbol)}</td>",
                f"<td style=\"{row_style}\" class=\"{daily_cls} right\">{'+' if pd.notna(daily_pnl) and daily_pnl > 0 else ''}{_fmt_currency(daily_pnl, currency_symbol) if pd.notna(daily_pnl) else '\u2014'}</td>",
                f"<td style=\"{row_style}\" class=\"{ret_cls} right\">{_fmt_return(ret_pct) if pd.notna(ret_pct) else '\u2014'}</td>",
                f"<td style=\"{row_style}\" class=\"right\">{row['Weight (%)']:.2f}%</td>",
            ]

            # Clickable row — dispatches a DOM event to the bridge element
            if on_click_bridge_id is not None:
                safe_ticker = json.dumps(clean_ticker)
                onclick = (
                    f"document.getElementById('c{on_click_bridge_id}')"
                    f".dispatchEvent(new CustomEvent('row_click', {{detail: {safe_ticker}}}))"
                )
                body_rows.append(
                    f'<tr style="cursor:pointer;" onclick="{onclick}">'
                    f"{''.join(cells)}</tr>"
                )
            else:
                body_rows.append(f"<tr>{''.join(cells)}</tr>")

        # ── TOTAL summary row ─────────────────────────────────
        total_value = df["Total Value"].sum()
        total_cost = (df["Buy Price"] * df["Shares"]).sum()
        total_divs = df["Dividends"].sum()
        total_daily = df["Daily P&L"].sum()
        total_ret_pct = (
            round((total_value + total_divs - total_cost) / total_cost * 100, 2)
            if total_cost else 0.0
        )
        n_positions = df["Ticker"].nunique()
        total_ret_cls = _color_class(total_ret_pct)
        total_daily_cls = _color_class(total_daily)

        ts = f"font-size:10px;color:{TEXT_DIM};"
        total_row = (
            f'<tr style="background:rgba(22,163,74,0.04);">'
            f'<td><div style="display:flex;align-items:center;gap:6px;{ts}font-weight:700;">TOTAL</div></td>'
            f'<td style="{ts}">{n_positions} positions</td>'
            f'<td style="{ts}">\u2014</td>'
            f'<td style="{ts}" class="right">\u2014</td>'
            f'<td style="{ts}" class="right">\u2014</td>'
            f'<td style="{ts}" class="right">\u2014</td>'
            f'<td style="{ts}" class="right">\u2014</td>'
            f'<td style="{ts}" class="right">\u2014</td>'
            f'<td style="font-weight:700;color:{TEXT_PRIMARY};" class="right">{_fmt_currency(total_value, currency_symbol)}</td>'
            f'<td style="{ts}" class="right">{_fmt_currency(total_divs, currency_symbol)}</td>'
            f'<td class="{total_daily_cls} right">{"+" if total_daily > 0 else ""}{_fmt_currency(total_daily, currency_symbol)}</td>'
            f'<td class="right"><span class="kpi-badge {"badge-green" if total_ret_pct >= 0 else "badge-red"}" style="font-size:11px;">{"\u25b2" if total_ret_pct >= 0 else "\u25bc"} {_fmt_return(total_ret_pct)}</span></td>'
            f'<td style="{ts}" class="right">100.00%</td>'
            f'</tr>'
        )
        body_rows.append(total_row)

        tbody = f"<tbody>{''.join(body_rows)}</tbody>"
        html = f'<div class="desktop-only" style="overflow-x:auto;"><div class="table-wrap"><table>{header}{tbody}</table></div></div>'

        with table_container:
            ui.html(html)

    # Show toggle only when multi-lot positions exist
    if multi_tickers:
        def _on_toggle(e):
            show_individual["value"] = e.value
            _render_table()

        ui.switch(
            "Show individual purchases",
            value=False,
            on_change=_on_toggle,
        ).style(f"font-size:12px;color:{TEXT_MUTED};").props("dense")

    _render_table()


def _build_mobile_position_cards(
    df: pd.DataFrame,
    name_map: dict[str, str],
    currency_symbol: str,
    portfolio_color_map: dict[str, str] | None = None,
) -> None:
    """Render positions as mobile-friendly cards (hidden on desktop via CSS)."""
    agg_rows = []
    for ticker, group in df.groupby("Ticker", sort=False):
        total_val = group["Total Value"].sum()
        total_cost = (group["Buy Price"] * group["Shares"]).sum()
        total_shares = group["Shares"].sum()
        total_divs = group["Dividends"].sum()
        daily = group["Daily P&L"].sum()
        ret_pct = (
            (total_val + total_divs - total_cost) / total_cost * 100
            if total_cost else 0.0
        )
        weight = group["Weight (%)"].sum()
        agg_rows.append({
            "Ticker": ticker,
            "Company": name_map.get(ticker, ticker),
            "Shares": total_shares,
            "Total Value": total_val,
            "Daily P&L": daily,
            "Return (%)": ret_pct,
            "Weight (%)": weight,
        })
    agg_rows.sort(key=lambda r: r["Weight (%)"], reverse=True)

    cards_html = f'<div style="font-size:11px;color:#94A3B8;margin-bottom:12px;">{len(agg_rows)} positions</div>'

    for r in agg_rows:
        ticker = r["Ticker"]
        dot_color = (portfolio_color_map or {}).get(ticker, "#64748B")
        val_str = f"{currency_symbol}{r['Total Value']:,.0f}"
        ret = r["Return (%)"]
        ret_color = "#16A34A" if ret >= 0 else "#DC2626"
        ret_str = f"{'+' if ret >= 0 else ''}{ret:.1f}%"
        daily = r["Daily P&L"]
        daily_color = "#16A34A" if daily >= 0 else "#DC2626"
        daily_str = f"{'+' if daily >= 0 else ''}{currency_symbol}{daily:,.0f} today"
        shares = r["Shares"]
        shares_str = f"{int(shares):,}" if shares == int(shares) else f"{shares:g}"
        weight_str = f"{r['Weight (%)']:.1f}%"

        cards_html += (
            f'<div style="background:#1C1D26;border-radius:8px;padding:12px;'
            f'margin-bottom:6px;border:1px solid rgba(255,255,255,0.06);">'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
            f'<div style="display:flex;align-items:center;gap:8px;">'
            f'<div style="width:6px;height:6px;border-radius:50%;background:{dot_color};'
            f'flex-shrink:0;margin-top:2px;"></div>'
            f'<div>'
            f'<div style="font-size:13px;font-weight:700;color:#F1F5F9;">{ticker}</div>'
            f'<div style="font-size:10px;color:#64748B;overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap;max-width:160px;">{r["Company"]}</div>'
            f'</div></div>'
            f'<div style="text-align:right;">'
            f'<div style="font-size:13px;font-weight:600;color:#F1F5F9;">{val_str}</div>'
            f'<div style="font-size:10px;color:{ret_color};font-weight:500;">{ret_str}</div>'
            f'</div></div>'
            f'<div style="display:flex;justify-content:space-between;margin-top:8px;padding-top:8px;'
            f'border-top:1px solid rgba(255,255,255,0.04);">'
            f'<div style="font-size:10px;color:#64748B;">{shares_str} shares \u00b7 {weight_str}</div>'
            f'<div style="font-size:10px;color:{daily_color};">{daily_str}</div>'
            f'</div></div>'
        )

    ui.html(f'<div class="position-cards mobile-only">{cards_html}</div>').classes("w-full")


# ---------------------------------------------------------------------------
# Price history section
# ---------------------------------------------------------------------------

def _build_price_history(
    portfolio: dict,
    name_map: dict[str, str],
    portfolio_color_map: dict[str, str],
    base_currency: str,
    currency_symbol: str,
) -> ui.select | None:
    """Render the price-history chart with ticker selector and time-range toggle.

    Returns the ``ticker_select`` widget so callers can change the
    selected ticker programmatically (e.g. from a table row click).
    """

    tickers = list(portfolio.keys())
    if not tickers:
        return None

    with ui.column().classes("chart-card w-full"):
        # ── Title + Controls on same row ──────────────────────
        with ui.row().classes("w-full items-center justify-between").style("margin-bottom:12px;"):
            ui.html(f'<div class="chart-title">Price History</div>')
            with ui.row().classes("items-center gap-3"):
                ticker_select = ui.select(
                    {t: f"{name_map.get(t, t)} ({t})" for t in tickers},
                    value=tickers[0],
                    label="Stock",
                ).props("dense outlined").style("min-width:180px;font-size:12px;")

                range_options = {"Since Purchase": -1, "3M": 3, "6M": 6, "1Y": 12, "2Y": 24, "Max": None}
                range_toggle = ui.toggle(
                    list(range_options.keys()),
                    value="Since Purchase",
                ).props("dense size=sm no-caps").style("font-size:11px;")

                fx_switch = ui.switch("Currency-adjusted", value=False).style(
                    f"font-size:12px;color:{TEXT_MUTED};"
                )

        # ── Chart container ───────────────────────────────────
        chart_container = ui.column().classes("w-full")

    def _update_chart():
        chart_container.clear()

        t = ticker_select.value
        if not t:
            return

        # Show spinner while loading
        with chart_container:
            spinner = ui.spinner("dots", size="lg").classes("self-center")

        ticker_currency = get_ticker_currency(t)
        fx_adjust = fx_switch.value
        range_months = range_options.get(range_toggle.value, 6)  # None = Since purchase

        lots = portfolio[t]
        hist = fetch_price_history_long(t)
        if not hasattr(hist, 'empty') or hist.empty:
            chart_container.clear()
            with chart_container:
                ui.label(f"No price history available for {t}.").style(
                    f"color:{TEXT_DIM};font-size:12px;"
                )
            return

        # FX conversion
        if fx_adjust and ticker_currency != base_currency:
            fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
            fx_hist = fetch_price_history_long(f"{fx_pair}{base_currency}=X")
            if fx_hist.empty:
                hist_converted = hist.copy()
                y_label = f"Price ({ticker_currency})"
            else:
                fx_series = fx_hist["Close"].reindex(hist.index, method="ffill")
                if ticker_currency == "GBX":
                    fx_series = fx_series / 100
                hist_converted = hist.copy()
                hist_converted["Close"] = hist["Close"] * fx_series
                y_label = f"Price ({base_currency})"
        else:
            hist_converted = hist.copy()
            y_label = f"Price ({ticker_currency})"

        # Clear spinner now that data is fetched
        chart_container.clear()

        # GBX notice
        if ticker_currency == "GBX" and not fx_adjust:
            with chart_container:
                ui.html(
                    f'<p style="font-size:11px;color:{TEXT_DIM};margin:4px 0;">'
                    f"Prices for {t} are shown in GBX (British pence). "
                    "100 GBX = 1 GBP. Enable Currency-adjusted to convert "
                    "to your base currency.</p>"
                )

        # Determine the start date
        if range_months is None:
            # "Max" — show full history
            effective_from = hist_converted.index[0]
        elif range_months == -1:
            # "Since purchase" — start 2 months before earliest purchase
            purchase_dates = [
                pd.Timestamp(lot["purchase_date"])
                for lot in lots
                if lot.get("purchase_date")
            ]
            if purchase_dates:
                effective_from = min(purchase_dates) - pd.DateOffset(months=2)
            else:
                effective_from = hist_converted.index[0]
        else:
            effective_from = pd.Timestamp.today() - pd.DateOffset(months=range_months)

        idx = tickers.index(t)
        line_color = portfolio_color_map.get(
            t, CHART_COLORS[idx % len(CHART_COLORS)]
        )
        if fx_adjust:
            fx_rate, fx_ok = get_fx_rate(ticker_currency, base_currency)
            if not fx_ok:
                ui.notify(f"FX rate unavailable for {ticker_currency}\u2192{base_currency}, showing unconverted values", type="warning")
        else:
            fx_rate = 1.0
        date_to = pd.Timestamp.today()

        fig = build_price_history_chart(
            hist_converted,
            y_label,
            line_color,
            lots,
            currency_symbol,
            fx_adjust,
            fx_rate,
            effective_from,
            date_to,
            title=t,
        )

        with chart_container:
            ui.plotly(fig).classes("w-full")

    # Wire up reactive updates
    ticker_select.on_value_change(lambda _: _update_chart())
    range_toggle.on_value_change(lambda _: _update_chart())
    fx_switch.on_value_change(lambda _: _update_chart())

    # Initial render
    _update_chart()

    return ticker_select


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def build_positions_tab(portfolio: dict, currency: str) -> None:
    """Render the full Positions tab content using NiceGUI widgets.

    Parameters
    ----------
    portfolio:
        Raw portfolio dict  ``{ticker: [lot, ...]}``.
    currency:
        Base currency code (e.g. ``"USD"``).
    """
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")

    if not portfolio:
        with ui.column().classes("w-full items-center").style("padding:40px 20px;"):
            ui.html(
                f'<div style="color:{TEXT_DIM};font-size:14px;text-align:center;margin-bottom:16px;">'
                "No positions yet. Add stocks in the sidebar, or load sample data to explore."
                "</div>"
            )
            ui.button(
                "Load Sample Portfolio", icon="science",
                on_click=lambda: ui.run_javascript(
                    'document.getElementById("btn-load-sample")?.click()'
                ),
            ).props("unelevated no-caps size=lg").style(
                "background:#3B82F6; color:white; border-radius:8px; padding:12px 32px;"
                " font-size:14px; font-weight:600;"
            )
        return

    # Build the portfolio DataFrame (cached 15 min) — off the event loop
    def _fetch_positions_data():
        df = build_portfolio_df(portfolio, currency)
        name_map: dict[str, str] = {t: fetch_company_name(t) for t in portfolio}
        # Fetch fundamentals for target prices and error detection
        fund_map: dict[str, dict] = {}
        for t in portfolio:
            fund_map[t] = fetch_fundamentals(t)
        return df, name_map, fund_map

    notification = ui.notification("Loading positions...", spinner=True, timeout=None)
    try:
        df, name_map, fund_map = await run.io_bound(_fetch_positions_data)
    finally:
        notification.dismiss()

    if df.empty:
        ui.html(
            f'<div style="color:{TEXT_DIM};font-size:13px;padding:24px;">'
            "Could not retrieve price data for any positions.</div>"
        )
        return

    # Shared maps
    portfolio_color_map: dict[str, str] = {
        t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
        for i, t in enumerate(portfolio.keys())
    }

    # Build target price map and detect unavailable tickers
    from src.fx import get_fx_rate as _get_fx_rate, get_ticker_currency as _get_ticker_ccy
    target_prices: dict[str, float | None] = {}
    unavailable_tickers: set[str] = set()
    for t in portfolio:
        f = fund_map.get(t, {})
        if not f or f.get("Current Price") is None:
            unavailable_tickers.add(t)
            continue
        tp = f.get("Target Price")
        if tp is not None:
            # Convert target price to base currency (GBX /100 handled by get_fx_rate)
            tc = _get_ticker_ccy(t)
            if tc != currency:
                fx, _ = _get_fx_rate(tc, currency)
                tp = round(tp * fx, 2)
            target_prices[t] = tp
        else:
            target_prices[t] = None

    # Hidden bridge element — table rows emit 'row_click' events on it
    bridge = ui.element("div").style("display:none")

    # ── Section 1: Positions table ────────────────────────
    _build_positions_table(
        df, name_map, currency_symbol, portfolio_color_map,
        on_click_bridge_id=bridge.id,
        target_prices=target_prices,
        unavailable_tickers=unavailable_tickers,
    )

    _build_mobile_position_cards(
        df, name_map, currency_symbol,
        portfolio_color_map=portfolio_color_map,
    )

    # ── Divider ───────────────────────────────────────────
    ui.html('<hr class="content-divider">')

    # ── Section 2: Price history chart ────────────────────
    ticker_select = _build_price_history(
        portfolio,
        name_map,
        portfolio_color_map,
        currency,
        currency_symbol,
    )

    # Connect table row clicks → price history ticker selector
    if ticker_select is not None:
        def _on_row_click(e):
            ticker = e.args
            if ticker and ticker in portfolio:
                ticker_select.set_value(ticker)

        bridge.on("row_click", _on_row_click, ["event.detail"])
