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


from src.charts import build_price_history_chart


def _sample_hist():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    return pd.DataFrame({"Close": range(100, 200)}, index=dates)


def _sample_lots():
    return [
        {"buy_price": 120, "shares": 10, "purchase_date": "2024-02-01"},
        {"buy_price": 150, "shares": 5, "purchase_date": "2024-03-15"},
    ]


def test_price_history_mobile_no_hlines():
    hist = _sample_hist()
    fig = build_price_history_chart(
        hist, "Price (USD)", "#1D4ED8", _sample_lots(), "$",
        False, 1.0, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-04-10"),
        mobile=True,
    )
    hlines = [s for s in fig.layout.shapes if hasattr(s, 'type') and s.type == 'line' and s.y0 == s.y1]
    assert len(hlines) == 0


def test_price_history_mobile_no_vlines():
    hist = _sample_hist()
    fig = build_price_history_chart(
        hist, "Price (USD)", "#1D4ED8", _sample_lots(), "$",
        False, 1.0, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-04-10"),
        mobile=True,
    )
    vlines = [s for s in fig.layout.shapes if hasattr(s, 'type') and s.type == 'line' and s.x0 == s.x1]
    assert len(vlines) == 0


def test_price_history_mobile_has_buy_markers():
    hist = _sample_hist()
    fig = build_price_history_chart(
        hist, "Price (USD)", "#1D4ED8", _sample_lots(), "$",
        False, 1.0, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-04-10"),
        mobile=True,
    )
    scatter_traces = [t for t in fig.data if t.mode == "markers"]
    assert len(scatter_traces) == 1
    assert len(scatter_traces[0].x) == 2


def test_price_history_mobile_compact_ticks():
    hist = _sample_hist()
    fig = build_price_history_chart(
        hist, "Price (USD)", "#1D4ED8", _sample_lots(), "$",
        False, 1.0, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-04-10"),
        mobile=True,
    )
    assert fig.layout.xaxis.nticks == 5
    assert fig.layout.dragmode is False


def test_price_history_desktop_still_has_hlines():
    hist = _sample_hist()
    fig = build_price_history_chart(
        hist, "Price (USD)", "#1D4ED8", _sample_lots(), "$",
        False, 1.0, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-04-10"),
    )
    shapes = fig.layout.shapes or []
    hlines = [s for s in shapes if hasattr(s, 'type') and s.type == 'line' and s.y0 == s.y1]
    assert len(hlines) >= 1


def test_mobile_overrides_applied_to_inline_figure():
    """Verify _mobile_overrides works on an inline-built figure (like contribution chart)."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[1, 2, 3], y=[100, 200, 300], name="Value"))
    fig.update_layout(
        xaxis=dict(title="Date"),
        yaxis=dict(title="Value (USD)"),
    )
    _mobile_overrides(fig)
    assert fig.layout.dragmode is False
    assert fig.layout.xaxis.title.text is None
    assert fig.layout.yaxis.tickfont.size == 9
