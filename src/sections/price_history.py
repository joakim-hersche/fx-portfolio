"""Price History section — single-ticker price chart with buy markers."""

import pandas as pd
import streamlit as st

from src.charts import CHART_COLORS, build_price_history_chart
from src.data_fetch import fetch_price_history_long
from src.fx import get_ticker_currency, get_fx_rate


def render_price_history(
    portfolio: dict,
    name_map: dict,
    portfolio_color_map: dict,
    base_currency: str,
    currency_symbol: str,
) -> None:
    """Render a single price history chart for a selected portfolio position."""
    tickers = list(portfolio.keys())
    if not tickers:
        return

    # ── Controls row ─────────────────────────
    col_ticker, col_range_hist = st.columns([2, 5])

    with col_ticker:
        selected_ticker = st.selectbox(
            "Stock",
            options=tickers,
            format_func=lambda t: f"{name_map.get(t, t)} ({t})",
            key="price_history_ticker",
        )

    with col_range_hist:
        hist_range_options = ["3 months", "6 months", "1 year", "2 years", "Since purchase", "Custom"]
        hist_range_label = st.radio(
            "Time range", hist_range_options, index=4, horizontal=True, key="hist_range"
        )

    # Date range row — only show when needed
    date_from = None
    if hist_range_label == "Custom":
        col_from, col_to, col_fx = st.columns([2, 2, 1])
        with col_from:
            date_from = st.date_input(
                "From",
                value=None,
                min_value=pd.Timestamp("1980-01-01").date(),
                key="hist_custom_from",
            )
        with col_to:
            date_to = st.date_input("To", value=pd.Timestamp.today())
        with col_fx:
            fx_adjust = st.toggle("FX-adjusted", key="fx_toggle_history")
    else:
        col_to_only, col_fx_only = st.columns([2, 1])
        with col_to_only:
            date_to = st.date_input("To", value=pd.Timestamp.today())
        with col_fx_only:
            fx_adjust = st.toggle("Currency-adjusted", key="fx_toggle_history")

    _hist_range_months = {"3 months": 3, "6 months": 6, "1 year": 12, "2 years": 24}

    # GBX notice (only for selected ticker)
    t = selected_ticker
    ticker_currency = get_ticker_currency(t)
    if ticker_currency == "GBX" and not fx_adjust:
        st.caption(
            f"Prices for {t} are shown in GBX (British pence). "
            "100 GBX = 1 GBP. Enable Currency-adjusted above to convert to your base currency."
        )

    # ── Fetch & convert ──────────────────────
    lots = portfolio[t]
    hist = fetch_price_history_long(t)
    if hist.empty:
        st.warning(f"No price history available for {t}.")
        return

    idx = tickers.index(t)
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

    dates = [lot["purchase_date"] for lot in lots if lot["purchase_date"]]
    auto_from = (
        min(pd.Timestamp(d) for d in dates) - pd.DateOffset(months=2)
        if dates else pd.Timestamp.today() - pd.DateOffset(months=6)
    )
    if hist_range_label == "Since purchase":
        effective_from = auto_from
    elif hist_range_label == "Custom":
        effective_from = pd.Timestamp(date_from) if date_from else auto_from
    else:
        effective_from = pd.Timestamp.today() - pd.DateOffset(months=_hist_range_months[hist_range_label])

    line_color = portfolio_color_map.get(t, CHART_COLORS[idx % len(CHART_COLORS)])
    fx_rate = get_fx_rate(ticker_currency, base_currency) if fx_adjust else 1.0

    fig = build_price_history_chart(
        hist_converted, y_label, line_color, lots, currency_symbol,
        fx_adjust, fx_rate, effective_from, date_to,
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
