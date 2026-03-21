"""Tests for mobile chart overrides in src.charts."""
import plotly.graph_objects as go

from src.charts import _mobile_overrides


def test_mobile_overrides_sets_dragmode_false():
    fig = go.Figure()
    _mobile_overrides(fig)
    assert fig.layout.dragmode is False


def test_mobile_overrides_sets_hovermode_closest():
    fig = go.Figure()
    _mobile_overrides(fig)
    assert fig.layout.hovermode == "closest"


def test_mobile_overrides_sets_tick_font_size():
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1, 2], y=[1, 2]))
    _mobile_overrides(fig)
    assert fig.layout.xaxis.tickfont.size == 9
    assert fig.layout.yaxis.tickfont.size == 9


def test_mobile_overrides_sets_hoverlabel_font_size():
    fig = go.Figure()
    _mobile_overrides(fig)
    assert fig.layout.hoverlabel.font.size == 10


def test_mobile_overrides_hides_axis_titles():
    fig = go.Figure()
    fig.update_xaxes(title_text="Date")
    fig.update_yaxes(title_text="Price")
    _mobile_overrides(fig)
    assert fig.layout.xaxis.title.text is None
    assert fig.layout.yaxis.title.text is None


import pandas as pd
from src.charts import build_comparison_chart


def _sample_comparison_df():
    dates = pd.date_range("2024-01-01", periods=5, freq="ME")
    return pd.DataFrame(
        {"AAPL": [100, 105, 110, 108, 112], "MSFT": [100, 102, 98, 103, 107]},
        index=dates,
    )


def test_comparison_mobile_legend_below():
    df = _sample_comparison_df()
    color_map = {"AAPL": "#1D4ED8", "MSFT": "#0EA5E9"}
    fig = build_comparison_chart(df, {"AAPL": "Apple", "MSFT": "Microsoft"}, color_map, "1Y", False, "USD", mobile=True)
    legend = fig.layout.legend
    assert legend.orientation == "h"
    assert legend.yanchor == "top"
    assert legend.y < 0  # below chart


def test_comparison_mobile_ticker_only_legend():
    df = _sample_comparison_df()
    color_map = {"AAPL": "#1D4ED8", "MSFT": "#0EA5E9"}
    fig = build_comparison_chart(df, {"AAPL": "Apple Inc.", "MSFT": "Microsoft Corp"}, color_map, "1Y", False, "USD", mobile=True)
    trace_names = [t.name for t in fig.data]
    for name in trace_names:
        assert " — " not in name  # no company name suffix


def test_comparison_mobile_short_date_format():
    df = _sample_comparison_df()
    color_map = {"AAPL": "#1D4ED8", "MSFT": "#0EA5E9"}
    fig = build_comparison_chart(df, {"AAPL": "Apple", "MSFT": "Microsoft"}, color_map, "1Y", False, "USD", mobile=True)
    assert fig.layout.xaxis.tickformat == "%b"
    assert fig.layout.xaxis.nticks == 5


def test_comparison_mobile_applies_overrides():
    df = _sample_comparison_df()
    color_map = {"AAPL": "#1D4ED8", "MSFT": "#0EA5E9"}
    fig = build_comparison_chart(df, {"AAPL": "Apple", "MSFT": "Microsoft"}, color_map, "1Y", False, "USD", mobile=True)
    assert fig.layout.dragmode is False


def test_comparison_desktop_unchanged():
    df = _sample_comparison_df()
    color_map = {"AAPL": "#1D4ED8", "MSFT": "#0EA5E9"}
    fig = build_comparison_chart(df, {"AAPL": "Apple", "MSFT": "Microsoft"}, color_map, "1Y", False, "USD")
    trace_names = [t.name for t in fig.data]
    assert any(" — " in name for name in trace_names)  # has company name
