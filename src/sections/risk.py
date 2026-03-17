"""Risk & Analytics section — risk metrics, correlation heatmap, fundamentals."""

import pandas as pd
import streamlit as st

from src.charts import C_POSITIVE, C_NEGATIVE, C_AMBER, build_correlation_heatmap
from src.ui import section_header, render_styled_table


def _build_attribution(positions_df: pd.DataFrame) -> pd.DataFrame:
    """Compute per-ticker performance attribution from the positions DataFrame.

    Returns a DataFrame with Ticker, Weight (%), Return (%), Contribution (%)
    sorted by contribution descending.
    """
    if positions_df.empty:
        return pd.DataFrame()

    # Aggregate to ticker level
    grouped = positions_df.groupby("Ticker", sort=False).agg(
        total_value=("Total Value", "sum"),
        cost_basis_sum=pd.NamedAgg(column="Buy Price", aggfunc=lambda x: (x * positions_df.loc[x.index, "Shares"]).sum()),
        dividends=("Dividends", "sum"),
    )
    total_portfolio = grouped["total_value"].sum()
    if total_portfolio == 0:
        return pd.DataFrame()

    grouped["weight"] = grouped["total_value"] / total_portfolio * 100
    grouped["return_pct"] = (
        (grouped["total_value"] + grouped["dividends"] - grouped["cost_basis_sum"])
        / grouped["cost_basis_sum"] * 100
    )
    grouped["contribution"] = grouped["weight"] / 100 * grouped["return_pct"]

    result = pd.DataFrame({
        "Ticker": grouped.index,
        "Weight (%)": grouped["weight"].round(2).values,
        "Return (%)": grouped["return_pct"].round(2).values,
        "Contribution (%)": grouped["contribution"].round(2).values,
    })
    return result.sort_values("Contribution (%)", ascending=False).reset_index(drop=True)


def render_risk_analytics(
    analytics_df: pd.DataFrame,
    price_data_1y: dict,
    tickers: list,
    fund_rows: list,
    base_currency: str,
    positions_df: pd.DataFrame | None = None,
) -> None:
    """Render the Risk & Analytics tab content — metrics, correlation, and fundamentals."""
    st.markdown(
        '<p class="section-intro">A deeper look at how risky your positions are and how efficiently they\'ve rewarded that risk. '
        'All figures are based on the past 12 months of daily price data. '
        'This section uses financial industry-standard metrics — each one is explained below its table.</p>',
        unsafe_allow_html=True
    )

    # ── Performance Attribution (full-width) ──
    if positions_df is not None and not positions_df.empty:
        attr_df = _build_attribution(positions_df)
        if not attr_df.empty:
            section_header("Performance Attribution")
            st.markdown(
                '<p class="section-intro">'
                'Shows how much each position contributed to your total portfolio return. '
                '<b>Contribution</b> = weight &times; return — a large position with a small return '
                'can contribute more than a small position with a large return.'
                '</p>',
                unsafe_allow_html=True
            )

            def _color_contribution(val):
                if not isinstance(val, (int, float)):
                    return ""
                if val > 0:
                    return f"color: {C_POSITIVE}"
                if val < 0:
                    return f"color: {C_NEGATIVE}"
                return ""

            def _color_return(val):
                if not isinstance(val, (int, float)):
                    return ""
                if val > 0:
                    return f"color: {C_POSITIVE}"
                if val < 0:
                    return f"color: {C_NEGATIVE}"
                return ""

            styled_attr = (
                attr_df.set_index("Ticker").style
                .format({
                    "Weight (%)": "{:.1f}%",
                    "Return (%)": "{:+.1f}%",
                    "Contribution (%)": "{:+.2f}%",
                })
                .map(_color_return, subset=["Return (%)"])
                .map(_color_contribution, subset=["Contribution (%)"])
            )
            render_styled_table(styled_attr)

    if not analytics_df.empty:
        # ── Risk Metrics + Heatmap side-by-side ──
        _has_corr = len(tickers) >= 2
        if _has_corr:
            col_risk, col_heat = st.columns([1, 1])
        else:
            col_risk = st.container()

        with col_risk:
            section_header("Risk Metrics")
            st.markdown(
                '<p class="section-intro">'
                '• <b>Volatility</b> — how much the price typically swings in a year. 25% means it moves roughly ±25% over 12 months. Higher = more unpredictable.<br>'
                '• <b>Worst Drop</b> — the biggest fall from a peak in the past year. −35% means it dropped 35% from its highest point before recovering.<br>'
                '• <b>Return/Risk Score</b> — how much return you earned per unit of risk. Above 1 is good; above 2 is excellent; below 0 means the risk was not rewarded.<br>'
                '• <b>Market Sensitivity</b> — how much this stock moves when the S&P 500 moves. 1.0 = moves exactly with the market; 1.5 = moves 50% more; 0.5 = half as much.'
                '</p>',
                unsafe_allow_html=True
            )

            def _color_sharpe(val):
                if not isinstance(val, (int, float)): return ""
                if val >= 1:   return f"color: {C_POSITIVE}"
                if val >= 0:   return f"color: {C_AMBER}"
                return f"color: {C_NEGATIVE}"

            def _color_volatility(val):
                if not isinstance(val, (int, float)): return ""
                if val <= 20:  return f"color: {C_POSITIVE}"
                if val <= 35:  return f"color: {C_AMBER}"
                return f"color: {C_NEGATIVE}"

            def _color_drawdown(val):
                if not isinstance(val, (int, float)): return ""
                if val >= -20: return f"color: {C_POSITIVE}"
                if val >= -40: return f"color: {C_AMBER}"
                return f"color: {C_NEGATIVE}"

            risk_display = analytics_df.set_index("Ticker").rename(columns={
                "Volatility":   "Volatility (%)",
                "Max Drawdown": "Worst Drop (%)",
                "Sharpe Ratio": "Return/Risk Score",
                "Beta":         "Beta (vs S&P)",
            })

            styled_risk = (
                risk_display.style
                .format({
                    "Volatility (%)":               "{:.1f}%",
                    "Worst Drop (%)":               "{:.1f}%",
                    "Return/Risk Score":            "{:.2f}",
                    "Beta (vs S&P)": "{:.2f}",
                }, na_rep="—")
                .map(_color_volatility, subset=["Volatility (%)"])
                .map(_color_drawdown,   subset=["Worst Drop (%)"])
                .map(_color_sharpe,     subset=["Return/Risk Score"])
            )
            render_styled_table(styled_risk)

        # ── Correlation Heatmap (side-by-side with risk metrics) ──
        if _has_corr:
            with col_heat:
                section_header("How Your Stocks Move Together")
                st.markdown(
                    '<p class="section-intro">'
                    'Shows how closely your positions move in sync. '
                    '<b>1.0</b> = always move in the same direction at the same time. '
                    '<b>−1.0</b> = always move in opposite directions. '
                    '<b>0</b> = no relationship at all. '
                    'Holding stocks that don\'t all move together reduces your overall risk — if one falls, the others may not. '
                    '<i>Note: uses 1-year daily returns; the Excel export uses a 6-month window.</i>'
                    '</p>',
                    unsafe_allow_html=True
                )
                _returns = {
                    t: price_data_1y[t]["Close"].pct_change().dropna()
                    for t in tickers
                    if not price_data_1y.get(t, pd.DataFrame()).empty
                }
                if len(_returns) >= 2:
                    corr_df = pd.DataFrame(_returns).dropna().corr()
                    fig = build_correlation_heatmap(corr_df)
                    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        # ── Fundamentals ──
        section_header("Valuation & Price Range")
        st.markdown(
            '<p class="section-intro">'
            '• <b>P/E Ratio</b> — how much investors pay relative to what the company earns. A P/E of 20 means you pay 20× the company\'s annual earnings per share. Lower can mean better value, but varies widely by industry.<br>'
            '• <b>Dividend Yield</b> — the annual cash payment as a % of the current price. 3% means every $100 invested pays $3/year directly to you, regardless of whether the stock price moves.<br>'
            '• <b>1-Year Low / High</b> — the cheapest and most expensive the stock has been over the past 12 months.<br>'
            '• <b>1-Year Position</b> — where the current price sits in that range. 100% = at the yearly high; 0% = at the yearly low.'
            '</p>',
            unsafe_allow_html=True
        )

        if fund_rows:
            fund_df = pd.DataFrame(fund_rows).set_index("Ticker")
            fund_df["1-Year Position"] = fund_df["1-Year Position"].clip(upper=100)
            st.dataframe(
                fund_df,
                width="stretch",
                column_config={
                    "P/E Ratio":       st.column_config.NumberColumn("P/E Ratio",      format="%.1f"),
                    "Div Yield (%)":   st.column_config.NumberColumn("Div Yield (%)",  format="%.2f"),
                    "1-Year Low":      st.column_config.NumberColumn("1-Year Low",     format="%.2f"),
                    "1-Year High":     st.column_config.NumberColumn("1-Year High",    format="%.2f"),
                    "1-Year Position": st.column_config.ProgressColumn(
                        "1-Year Position",
                        min_value=0,
                        max_value=100,
                        format="%.0f%%",
                        help="Where the current price sits in its 52-week range. Clamped to 100%.",
                    ),
                },
            )
