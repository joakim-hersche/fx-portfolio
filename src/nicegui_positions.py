"""Positions tab — positions table + price history chart (NiceGUI version).

Exports a single function `build_positions_tab` that renders:
1. A styled HTML positions table with conditional formatting
2. A per-ticker price history chart with buy-price overlay and purchase markers
"""

from __future__ import annotations

import pandas as pd
from nicegui import ui

from src.charts import (
    CHART_COLORS,
    C_NEGATIVE,
    C_NEUTRAL,
    C_POSITIVE,
    build_price_history_chart,
)
from src.data_fetch import fetch_company_name, fetch_price_history_long
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
) -> None:
    """Render the positions table as a styled HTML table via ui.html()."""

    ui.html(
        f'<p style="font-size:12px;color:{TEXT_MUTED};line-height:1.6;margin-bottom:12px;">'
        "Every stock you own, how much you paid, what it's worth now, "
        "and how much you've gained or lost. <b>Today's Change</b> is how much "
        "your value moved since yesterday's market close. "
        "<b>Total Return</b> includes any dividends received. "
        "<b>Portfolio Share</b> is what percentage of your total investment "
        "this position represents.</p>"
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

        # Build HTML table
        columns = [
            "Ticker",
            "Company",
            "Buy #",
            "Shares",
            "Buy Price",
            "Purchase Date",
            "Current Price",
            "Total Value",
            "Dividends",
            "Today",
            "Return (%)",
            "Weight (%)",
        ]

        header_cells = "".join(f"<th>{c}</th>" for c in columns)
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

            cells = [
                f"<td style=\"{row_style}\">{ticker_raw}</td>",
                f"<td style=\"{row_style}\">{company}</td>",
                f"<td style=\"{row_style}\">{row['Purchase']}</td>",
                f"<td style=\"{row_style}\">{_fmt_shares(row['Shares'])}</td>",
                f"<td style=\"{row_style}\">{_fmt_currency(row['Buy Price'], currency_symbol)}</td>",
                f"<td style=\"{row_style}\">{row['Purchase Date']}</td>",
                f"<td style=\"{row_style}\">{_fmt_currency(row['Current Price'], currency_symbol)}</td>",
                f"<td style=\"{row_style}\">{_fmt_currency(row['Total Value'], currency_symbol)}</td>",
                f"<td style=\"{row_style}\">{_fmt_currency(row['Dividends'], currency_symbol)}</td>",
                f"<td style=\"{row_style}\" class=\"{daily_cls}\">{_fmt_currency(daily_pnl, currency_symbol)}</td>",
                f"<td style=\"{row_style}\" class=\"{ret_cls}\">{_fmt_return(ret_pct)}</td>",
                f"<td style=\"{row_style}\">{row['Weight (%)']:.2f}%</td>",
            ]

            body_rows.append(f"<tr>{''.join(cells)}</tr>")

        tbody = f"<tbody>{''.join(body_rows)}</tbody>"
        html = f'<div class="table-wrap"><table>{header}{tbody}</table></div>'

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
        ).style(f"font-size:12px;color:{TEXT_MUTED};")

    _render_table()


# ---------------------------------------------------------------------------
# Price history section
# ---------------------------------------------------------------------------

def _build_price_history(
    portfolio: dict,
    name_map: dict[str, str],
    portfolio_color_map: dict[str, str],
    base_currency: str,
    currency_symbol: str,
) -> None:
    """Render the price-history chart with ticker selector and time-range toggle."""

    tickers = list(portfolio.keys())
    if not tickers:
        return

    ui.html(
        f'<div style="font-size:10px;font-weight:700;letter-spacing:0.12em;'
        f'text-transform:uppercase;color:{TEXT_MUTED};margin-bottom:10px;">'
        "Price History</div>"
    )

    # ── Controls row ──────────────────────────────────────
    with ui.row().classes("w-full items-center gap-3"):
        ticker_select = ui.select(
            {t: f"{name_map.get(t, t)} ({t})" for t in tickers},
            value=tickers[0],
            label="Stock",
        ).props("dense outlined").style("min-width:200px;font-size:12px;")

        range_options = {"3M": 3, "6M": 6, "1Y": 12}
        range_toggle = ui.toggle(
            list(range_options.keys()),
            value="6M",
        ).props("dense size=sm no-caps").style("font-size:11px;")

        fx_switch = ui.switch("Currency-adjusted", value=False).style(
            "font-size:11px;"
        )

    # ── Chart container ───────────────────────────────────
    chart_container = ui.column().classes("w-full")

    def _update_chart():
        chart_container.clear()

        t = ticker_select.value
        if not t:
            return

        ticker_currency = get_ticker_currency(t)
        fx_adjust = fx_switch.value
        range_months = range_options.get(range_toggle.value, 6)

        lots = portfolio[t]
        hist = fetch_price_history_long(t)
        if hist.empty:
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
        effective_from = pd.Timestamp.today() - pd.DateOffset(months=range_months)

        idx = tickers.index(t)
        line_color = portfolio_color_map.get(
            t, CHART_COLORS[idx % len(CHART_COLORS)]
        )
        fx_rate = get_fx_rate(ticker_currency, base_currency) if fx_adjust else 1.0
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
        )

        with chart_container:
            ui.plotly(fig).classes("w-full")

    # Wire up reactive updates
    ticker_select.on_value_change(lambda _: _update_chart())
    range_toggle.on_value_change(lambda _: _update_chart())
    fx_switch.on_value_change(lambda _: _update_chart())

    # Initial render
    _update_chart()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_positions_tab(portfolio: dict, currency: str) -> None:
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
        ui.html(
            f'<div style="color:{TEXT_DIM};font-size:13px;padding:24px;">'
            "No positions yet. Add stocks in the sidebar to see your holdings here."
            "</div>"
        )
        return

    # Build the portfolio DataFrame (cached 15 min)
    df = build_portfolio_df(portfolio, currency)
    if df.empty:
        ui.html(
            f'<div style="color:{TEXT_DIM};font-size:13px;padding:24px;">'
            "Could not retrieve price data for any positions.</div>"
        )
        return

    # Shared maps
    name_map: dict[str, str] = {t: fetch_company_name(t) for t in portfolio}
    portfolio_color_map: dict[str, str] = {
        t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
        for i, t in enumerate(portfolio.keys())
    }

    # ── Section 1: Positions table ────────────────────────
    _build_positions_table(df, name_map, currency_symbol)

    # ── Divider ───────────────────────────────────────────
    ui.html('<hr class="content-divider">')

    # ── Section 2: Price history chart ────────────────────
    _build_price_history(
        portfolio,
        name_map,
        portfolio_color_map,
        currency,
        currency_symbol,
    )
