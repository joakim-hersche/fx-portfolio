"""Portfolio Allocation section."""

import pandas as pd
import streamlit as st

from src.charts import build_allocation_chart


def render_allocation(df: pd.DataFrame, name_map: dict, portfolio_color_map: dict) -> None:
    """Render the Portfolio Allocation bar chart."""
    st.markdown(
        '<p class="section-intro">How your money is spread across your positions. '
        'Larger bars mean a bigger share of your total investment in that stock.</p>',
        unsafe_allow_html=True
    )

    alloc_df = (
        df.groupby("Ticker")["Total Value"]
        .sum()
        .reset_index()
        .assign(**{"Portfolio Share (%)": lambda x: (x["Total Value"] / x["Total Value"].sum() * 100).round(2)})
        .sort_values("Portfolio Share (%)", ascending=True)
    )

    fig = build_allocation_chart(alloc_df, name_map, portfolio_color_map)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
