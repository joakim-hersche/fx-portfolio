"""Plotly chart builders. All functions return go.Figure — no st.* calls."""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── Color tokens (shared across all charts) ──────────────────────────────────
CHART_COLORS = ["#1D4ED8", "#0EA5E9", "#6366F1", "#10B981", "#F59E0B",
                "#EC4899", "#8B5CF6", "#06B6D4", "#22C55E", "#F97316"]

C_POSITIVE   = "#16A34A"
C_NEGATIVE   = "#DC2626"
C_NEUTRAL    = "#94A3B8"
C_AMBER      = "#D97706"
C_METRIC_BRD = "rgba(29,78,216,0.25)"
C_CARD_BRD   = "rgba(29,78,216,0.3)"

_PLOT_TMPL = "plotly"


def _apply_default_layout(fig: go.Figure, **overrides) -> go.Figure:
    """Apply standard transparent background and template to any chart."""
    defaults = dict(
        template=_PLOT_TMPL,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hoverlabel=dict(
            bgcolor="#1C1D26",
            bordercolor="#1E293B",
            font=dict(color="#F1F5F9", size=11, family="Inter, sans-serif"),
        ),
        modebar=dict(
            bgcolor="rgba(0,0,0,0)",
            color="#64748B",
            activecolor=C_NEUTRAL,
        ),
    )
    defaults.update(overrides)
    fig.update_layout(**defaults)
    _axis_style = dict(
        gridcolor="rgba(255,255,255,0.04)",
        tickfont=dict(color="#CBD5E1", size=10),
        title_font=dict(color="#CBD5E1", size=11),
    )
    fig.update_xaxes(**_axis_style)
    fig.update_yaxes(**_axis_style)
    return fig


# ── QQ plot ──────────────────────────────────────────────────────────────────

def build_qq_plot(
    theoretical: np.ndarray,
    observed: np.ndarray,
    ticker: str,
) -> go.Figure:
    """Build a QQ plot comparing observed return quantiles against a normal distribution.

    Points falling on the diagonal mean the distribution is normal.
    Deviation at the tails reveals fat tails (above the line = heavier tails than expected).
    """
    fig = go.Figure()

    # Data points
    fig.add_trace(go.Scatter(
        x=theoretical,
        y=observed,
        mode="markers",
        marker=dict(color="rgba(99,110,250,0.7)", size=5),
        name="Returns",
        hovertemplate="Theoretical: %{x:.3f}<br>Observed: %{y:.3f}<extra></extra>",
    ))

    # 45-degree reference line
    lo = min(theoretical.min(), observed.min())
    hi = max(theoretical.max(), observed.max())
    fig.add_trace(go.Scatter(
        x=[lo, hi],
        y=[lo, hi],
        mode="lines",
        line=dict(color=C_NEGATIVE, width=1, dash="dash"),
        name="Normal distribution",
        hoverinfo="skip",
    ))

    _apply_default_layout(
        fig,
        margin=dict(t=30, b=40),
        xaxis_title="Theoretical quantiles (normal)",
        yaxis_title="Sample quantiles (actual returns)",
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.06)",
            font=dict(size=10, color=C_NEUTRAL),
        ),
    )
    return fig


# ── Fan chart (shared by backtest, portfolio outlook, position outlook) ──────

def build_fan_chart(
    dates: list,
    percentiles: dict,
    *,
    actual: pd.Series | None = None,
    hlines: list[dict] | None = None,
    currency_symbol: str = "$",
    y_title: str = "Value",
    show_legend: bool = True,
) -> go.Figure:
    """Build a Monte Carlo fan chart with 80%/50% bands, median, and optional actual line.

    percentiles: dict with keys p10, p25, p50, p75, p90 (each a list/array).
    actual: optional pd.Series of actual values to overlay.
    hlines: optional list of dicts with keys y, text, color for horizontal reference lines.
    """
    fig = go.Figure()

    # 80% band (p10–p90)
    fig.add_trace(go.Scatter(
        x=dates + list(reversed(dates)),
        y=list(percentiles["p90"]) + list(reversed(list(percentiles["p10"]))),
        fill="toself",
        fillcolor="rgba(99,110,250,0.12)",
        line=dict(width=0),
        name="80% of simulations",
        hoverinfo="skip",
    ))

    # 50% band (p25–p75)
    fig.add_trace(go.Scatter(
        x=dates + list(reversed(dates)),
        y=list(percentiles["p75"]) + list(reversed(list(percentiles["p25"]))),
        fill="toself",
        fillcolor="rgba(99,110,250,0.35)",
        line=dict(width=0),
        name="50% of simulations",
        hoverinfo="skip",
    ))

    # Median simulation
    fig.add_trace(go.Scatter(
        x=dates,
        y=percentiles["p50"],
        line=dict(color="rgba(99,110,250,0.7)", width=1.5, dash="dash"),
        name="Median simulation",
    ))

    # Actual portfolio value (backtest only)
    if actual is not None:
        fig.add_trace(go.Scatter(
            x=list(actual.index),
            y=list(actual.values),
            line=dict(color="#334155", width=2),
            name="Actual portfolio value",
        ))

    # Horizontal reference lines (buy prices, current value, etc.)
    for hl in (hlines or []):
        fig.add_hline(
            y=hl["y"],
            line=dict(color=hl.get("color", C_NEUTRAL), width=hl.get("width", 1.5), dash=hl.get("dash", "dot")),
            annotation_text=hl.get("text", ""),
            annotation_position=hl.get("position", "top left"),
            annotation_font_color=hl.get("color", C_NEUTRAL),
        )

    _apply_default_layout(
        fig,
        margin=dict(t=20, b=40),
        yaxis=dict(tickprefix=currency_symbol, title=y_title),
        xaxis=dict(title="Date"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=10, color=C_NEUTRAL),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.06)",
        ) if show_legend else dict(visible=False),
        hovermode="x unified",
    )
    return fig


# ── Individual chart builders ────────────────────────────────────────────────

def build_allocation_chart(
    alloc_df: pd.DataFrame,
    name_map: dict,
    portfolio_color_map: dict,
) -> go.Figure:
    alloc_df = alloc_df.copy()
    alloc_df["Company"] = alloc_df["Ticker"].map(name_map)
    alloc_df["Company"] = alloc_df["Company"].str[:20]
    color_map = {name_map[t]: portfolio_color_map[t] for t in alloc_df["Ticker"]}
    fig = px.bar(
        alloc_df,
        x="Portfolio Share (%)",
        y="Company",
        orientation="h",
        color="Company",
        color_discrete_map=color_map,
        text=alloc_df["Portfolio Share (%)"].map(lambda v: f"{v:.1f}%"),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    _apply_default_layout(
        fig,
        xaxis_title="Portfolio Share (%)",
        yaxis_title=None,
        showlegend=False,
        xaxis=dict(range=[0, alloc_df["Portfolio Share (%)"].max() * 1.25]),
        margin=dict(l=10, r=60, t=10, b=40),
    )
    return fig


def build_comparison_chart(
    comparison_df: pd.DataFrame,
    name_map: dict,
    portfolio_color_map: dict,
    range_label: str,
    fx_adjusted: bool,
    base_currency: str,
) -> go.Figure:
    # Use "TICKER — Short Name" labels that fit in the legend without overflow
    def _legend_label(t: str) -> str:
        name = name_map.get(t, t)
        if name == t:
            return t
        short = name[:15] + "…" if len(name) > 15 else name
        return f"{t} — {short}"

    comp_label_map = {t: _legend_label(t) for t in comparison_df.columns}
    color_map = {comp_label_map[t]: portfolio_color_map[t] for t in comparison_df.columns if t in portfolio_color_map}
    display = comparison_df.rename(columns=comp_label_map)
    fx_note = " (FX-adjusted)" if fx_adjusted else ""
    reset = display.reset_index()
    idx_col = reset.columns[0]
    melted = reset.melt(id_vars=idx_col, var_name="Ticker", value_name="Value")
    fig = px.line(melted, x=idx_col, y="Value", color="Ticker", color_discrete_map=color_map)
    _apply_default_layout(
        fig,
        xaxis_title="Date",
        yaxis_title=f"Indexed (100 = start){fx_note}",
        legend_title="",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="left", x=0,
            font=dict(size=10, color=C_NEUTRAL),
            bgcolor="rgba(0,0,0,0)",
            bordercolor="rgba(255,255,255,0.06)",
        ),
    )
    fig.add_hline(y=100, line_dash="dash", line_color="gray")
    return fig


def build_price_history_chart(
    hist: pd.DataFrame,
    y_label: str,
    line_color: str,
    lots: list[dict],
    currency_symbol: str,
    fx_adjusted: bool,
    fx_rate: float,
    effective_from: pd.Timestamp,
    date_to,
) -> go.Figure:
    fig = px.line(x=hist.index, y=hist["Close"], color_discrete_sequence=[line_color])
    _apply_default_layout(
        fig,
        xaxis_title="Date",
        yaxis_title=y_label,
        xaxis_range=[str(pd.Timestamp(effective_from).date()), str(date_to)],
        showlegend=False,
    )
    for i, lot in enumerate(lots):
        if fx_adjusted:
            buy_price_display = round(lot["buy_price"] * fx_rate, 2)
            buy_label = f"Buy {i + 1}  {currency_symbol}{buy_price_display}"
        else:
            buy_price_display = lot["buy_price"]
            buy_label = f"Buy {i + 1}  {buy_price_display}"
        fig.add_hline(
            y=buy_price_display,
            line_dash="dash", line_color=C_AMBER,
            annotation_text=buy_label, annotation_position="top left",
        )
        if lot["purchase_date"]:
            fig.add_vline(
                x=str(pd.Timestamp(lot["purchase_date"]).date()),
                line_dash="dash", line_color="gray",
            )
    return fig


def build_correlation_heatmap(corr_df: pd.DataFrame) -> go.Figure:
    # Red → light-red → neutral-gray → light-green → green
    # Matches the dashboard's existing C_NEGATIVE / C_POSITIVE color language.
    # Gray center avoids the harsh white midpoint that breaks dark-mode readability.
    _scale = [
        [0.00, "#DC2626"],  # -1.0  strong negative
        [0.25, "#FCA5A5"],  # -0.5  weak negative
        [0.50, C_NEUTRAL],  #  0.0  no correlation
        [0.75, "#86EFAC"],  # +0.5  weak positive
        [1.00, "#16A34A"],  # +1.0  strong positive
    ]
    fig = px.imshow(corr_df, color_continuous_scale=_scale, zmin=-1, zmax=1, text_auto=".2f")
    fig.update_traces(textfont=dict(color="#1E293B"))
    _apply_default_layout(
        fig,
        margin=dict(t=20),
        coloraxis_colorbar=dict(
            title="Correlation",
            title_font=dict(color=C_NEUTRAL, size=10),
            tickfont=dict(color=C_NEUTRAL, size=9),
            tickvals=[-1, -0.5, 0, 0.5, 1],
        ),
    )
    return fig


def build_portfolio_histogram(
    end_values,
    start_value: float,
    p10: float,
    p50: float,
    p90: float,
    currency_symbol: str,
    base_currency: str,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=list(end_values),
        nbinsx=60,
        marker_color="rgba(99,110,250,0.6)",
        marker_line=dict(color="rgba(99,110,250,0.9)", width=0.5),
        name="Simulated end values",
        hovertemplate=f"{currency_symbol}%{{x:,.0f}}<br>Count: %{{y}}<extra></extra>",
    ))
    for val, label, color, pos in [
        (p10,         "p10",     C_NEGATIVE, "top left"),
        (p50,         "Median",  "#6366F1",  "top right"),
        (p90,         "p90",     C_POSITIVE, "top right"),
        (start_value, "Current", C_NEUTRAL, "bottom right"),
    ]:
        fig.add_vline(
            x=val,
            line=dict(color=color, width=1.5, dash="dash"),
            annotation_text=label,
            annotation_position=pos,
            annotation_font_color=color,
        )
    _apply_default_layout(
        fig,
        margin=dict(t=20, b=40),
        xaxis=dict(tickprefix=currency_symbol, title=f"Portfolio Value ({base_currency})"),
        yaxis=dict(title="Number of simulations"),
        showlegend=False,
        bargap=0.02,
    )
    return fig
