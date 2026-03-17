"""Portfolio Comparison section."""

import pandas as pd
import streamlit as st

from src.charts import build_comparison_chart
from src.data_fetch import fetch_price_history_range
from src.fx import get_ticker_currency


def render_comparison(
    portfolio: dict,
    name_map: dict,
    portfolio_color_map: dict,
    base_currency: str,
) -> None:
    """Render the indexed side-by-side comparison chart."""
    st.markdown(
        '<p class="section-intro">All your stocks shown on the same scale. '
        'Every stock starts at 100 on the left so you can fairly compare their growth — '
        'a stock at 120 has grown 20%, a stock at 85 has fallen 15%. '
        'Click a ticker in the legend to hide or show it. '
        'Enable <b>Currency-adjusted</b> to account for exchange rate changes if you hold stocks in different currencies.</p>',
        unsafe_allow_html=True
    )

    col_range, col_fx_comp = st.columns([3, 2], vertical_alignment="bottom")
    with col_range:
        range_options = {"3 months": "3mo", "6 months": "6mo", "1 year": "1y", "Since first purchase": "max"}
        range_label = st.radio("Time range", list(range_options.keys()), index=1, horizontal=True)
        selected_range = range_options[range_label]
    with col_fx_comp:
        fx_adjust = st.toggle("Currency-adjusted", key="fx_toggle_comparison")

    comparison_data = {}
    for t in portfolio:
        hist = fetch_price_history_range(t, selected_range)
        if hist.empty:
            st.warning(f"Could not load data for {t} — skipping.")
            continue
        ticker_currency = get_ticker_currency(t)
        if fx_adjust and ticker_currency != base_currency:
            fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
            fx_hist = fetch_price_history_range(f"{fx_pair}{base_currency}=X", selected_range)
            if fx_hist.empty:
                comparison_data[t] = hist["Close"]
                continue
            fx_series = fx_hist["Close"].reindex(hist.index, method="ffill")
            if ticker_currency == "GBX":
                fx_series = fx_series / 100
            comparison_data[t] = hist["Close"] * fx_series
        else:
            comparison_data[t] = hist["Close"]

    comparison_df = pd.DataFrame(comparison_data).dropna()
    if not comparison_df.empty:
        comparison_df = comparison_df / comparison_df.iloc[0] * 100

    fig = build_comparison_chart(comparison_df, name_map, portfolio_color_map, range_label, fx_adjust, base_currency)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
