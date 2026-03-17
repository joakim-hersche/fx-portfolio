"""Market Dashboard — Streamlit entry point.

Thin orchestrator that delegates to focused modules under src/.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from src.charts import C_CARD_BRD, C_METRIC_BRD, C_POSITIVE, C_NEGATIVE, CHART_COLORS
from src.data_fetch import (
    cached_run_monte_carlo_backtest, cached_run_monte_carlo_portfolio,
    cached_run_monte_carlo_ticker, fetch_analytics_history, fetch_company_name,
    fetch_fundamentals, fetch_price_history_short, fetch_simulation_history,
    load_stock_options,
)
from src.excel_export import build_excel_report
from src.fx import CURRENCY_SYMBOLS, get_ticker_currency, get_fx_rate
from src.portfolio import build_portfolio_df, compute_analytics
from src.sections.allocation import render_allocation
from src.sections.comparison import render_comparison
from src.sections.monte_carlo import render_backtest, render_model_diagnostics, render_portfolio_outlook, render_position_outlook
from src.sections.positions import render_add_manage, render_positions_table
from src.sections.price_history import render_price_history
from src.sections.risk import render_risk_analytics
from src.state import init_session_state, sync_localstorage
from src.stocks import TICKER_COLORS
from src.ui import section_header

# ──────────────────────────────────────────────
# Page Config  (must be first Streamlit call)
# ──────────────────────────────────────────────
st.set_page_config(page_title="Market Dashboard", layout="wide")

# ──────────────────────────────────────────────
# PWA — manifest, icons, service worker
# ──────────────────────────────────────────────
st.markdown("""
<link rel="manifest" href="app/static/manifest.json">
<link rel="apple-touch-icon" href="app/static/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#3B82F6">
<script>
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('app/static/sw.js');
}
</script>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# CSS — design-token variables, dark + light
# ──────────────────────────────────────────────
st.markdown(f"""
<style>
/* ── Design tokens ───────────────────────── */
/* Derived from Streamlit's own --text-color so these automatically adapt
   to both dark and light themes without needing [data-theme] selectors
   (which Streamlit 1.x does not set on any DOM element). */
:root {{
    --accent:               #3B82F6;
    --text-muted:           color-mix(in srgb, var(--text-color) 65%, transparent);
    --section-header-color: color-mix(in srgb, var(--text-color) 80%, transparent);
    --border-subtle:        color-mix(in srgb, var(--text-color) 10%, transparent);
    --border-card:          color-mix(in srgb, var(--text-color) 28%, transparent);
    --gridline:             color-mix(in srgb, var(--text-color) 12%, transparent);
}}

/* ── Section headers ─────────────────────── */
.section-header {{
    font-size: 12px;
    font-variant: small-caps;
    letter-spacing: 0.1em;
    font-weight: 600;
    color: var(--section-header-color);
    border-bottom: 1px solid var(--border-subtle);
    padding-bottom: 6px;
    margin-top: 1.6rem;
    margin-bottom: 0.6rem;
    text-transform: uppercase;
}}
.section-subtitle {{
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 4px;
    margin-bottom: 12px;
    line-height: 1.5;
}}

/* ── Metric containers ───────────────────── */
[data-testid="metric-container"] {{
    background-color: var(--secondary-background-color);
    border: 1px solid {C_METRIC_BRD};
    border-radius: 8px;
    padding: 16px 20px;
}}

/* ── KPI cards ───────────────────────────── */
.kpi-card {{
    background-color: var(--secondary-background-color);
    border-radius: 10px;
    padding: 20px 26px;
    text-align: center;
    border: 1px solid color-mix(in srgb, var(--text-color) 22%, transparent);
    min-height: 110px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 4px color-mix(in srgb, var(--text-color) 8%, transparent);
}}
.kpi-card.hero {{
    padding: 26px 30px;
    min-height: 130px;
}}
.kpi-label {{
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
}}
.kpi-value {{
    font-size: 26px;
    font-weight: 600;
    line-height: 1.2;
    color: var(--text-color);
}}
.kpi-card.hero .kpi-value {{
    font-size: 32px;
}}

/* ── Misc layout helpers ─────────────────── */
.section-intro {{
    color: var(--text-muted);
    font-size: 14px;
    margin-bottom: 12px;
    line-height: 1.6;
}}
.kpi-sub {{
    font-size: 14px;
    margin-top: 4px;
}}
.kpi-sub.sm {{
    font-size: 12px;
}}

/* ── HTML styled tables (replaces st.dataframe for small tables) ── */
.styled-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    color: var(--text-color);
}}
.styled-table th {{
    text-align: left;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 12px;
    color: var(--text-muted);
    border-bottom: 1px solid var(--border-subtle);
}}
.styled-table td {{
    padding: 8px 12px;
    border-bottom: 1px solid var(--border-subtle);
}}
.styled-table th.blank,
.styled-table th.index_name {{
    border-bottom: 1px solid var(--border-subtle);
}}
.styled-table tbody tr:hover {{
    background-color: color-mix(in srgb, var(--text-color) 5%, transparent);
}}

/* ── KPI grid ───────────────────────────── */
.kpi-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    grid-auto-rows: 1fr;
    gap: 12px;
}}

/* ── Responsive: Tablet portrait (≤ 1024px) ── */
@media (max-width: 1024px) {{
    /* Stack all column layouts */
    [data-testid="stHorizontalBlock"] {{
        flex-wrap: wrap !important;
    }}
    [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {{
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }}

    .kpi-card {{
        padding: 16px 20px;
        min-height: 96px;
    }}
    .kpi-card.hero {{
        padding: 20px 24px;
        min-height: 110px;
    }}
    .kpi-card.hero .kpi-value {{ font-size: 28px; }}
    .kpi-value {{ font-size: 22px; }}

    .kpi-grid {{
        grid-template-columns: 1fr;
    }}

    [data-testid="metric-container"] {{
        padding: 12px 14px;
    }}

    /* Wrap horizontal radio groups */
    [data-testid="stRadio"] > div[role="radiogroup"] {{
        flex-wrap: wrap !important;
        gap: 4px 12px !important;
    }}
}}

/* ── Responsive: Large phone / iPad mini (≤ 768px) ── */
@media (max-width: 768px) {{
    .kpi-card {{
        padding: 14px 16px;
        min-height: 80px;
    }}
    .kpi-card.hero {{
        padding: 16px 20px;
        min-height: 90px;
    }}
    .kpi-card.hero .kpi-value {{ font-size: 24px; }}
    .kpi-value {{ font-size: 20px; }}
    .kpi-label {{ font-size: 11px; }}

    [data-testid="metric-container"] {{
        padding: 10px 12px;
    }}

    /* Compact tab labels */
    button[data-baseweb="tab"] {{
        font-size: 13px !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
    }}

    .section-intro {{ font-size: 13px; }}
}}

/* ── Responsive: Small phone (≤ 480px) ────── */
@media (max-width: 480px) {{
    .kpi-card {{
        padding: 12px 14px;
        min-height: 70px;
    }}
    .kpi-card.hero {{
        padding: 14px 16px;
        min-height: 76px;
    }}
    .kpi-card.hero .kpi-value {{ font-size: 22px; }}
    .kpi-value {{ font-size: 18px; }}
    .kpi-label {{ font-size: 10px; letter-spacing: 0.04em; }}
    .kpi-sub {{ font-size: 12px; }}
    .kpi-sub.sm {{ font-size: 11px; }}

    button[data-baseweb="tab"] {{
        font-size: 12px !important;
        padding-left: 8px !important;
        padding-right: 8px !important;
    }}

    .section-intro {{ font-size: 12px; }}
    .section-header {{ font-size: 11px; margin-top: 1.2rem; }}

    [data-testid="metric-container"] {{
        padding: 8px 10px;
    }}
    [data-testid="metric-container"] [data-testid="stMetricLabel"] {{
        font-size: 12px !important;
    }}
}}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Session State & localStorage
# ──────────────────────────────────────────────
init_session_state()
sync_localstorage()



# ──────────────────────────────────────────────
# Sidebar  (Phase 2)
# ──────────────────────────────────────────────
all_stock_options = load_stock_options()

with st.sidebar:
    st.markdown("## Market Dashboard")

    # Currency selector
    base_currency = st.selectbox(
        "Display Currency",
        options=list(CURRENCY_SYMBOLS.keys()),
        key="currency",
    )
    if st.session_state.get("portfolio") and any(
        lot.get("buy_fx_rate") for lots in st.session_state.portfolio.values() for lot in lots
    ):
        st.caption("Changing currency does not update historical buy FX rates stored with each lot.")

    st.divider()

    # Add / Manage Positions (moved into sidebar)
    render_add_manage(all_stock_options, base_currency, CURRENCY_SYMBOLS[base_currency])

currency_symbol = CURRENCY_SYMBOLS[base_currency]

# ──────────────────────────────────────────────
# Main header
# ──────────────────────────────────────────────
st.markdown("""
<div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
    <div style="width:4px; height:40px; background:var(--accent); border-radius:2px; flex-shrink:0;"></div>
    <div>
        <h1 style="margin:0; padding:0; font-size:clamp(1.6rem, 3vw, 2.2rem); line-height:1.2;">Market Dashboard</h1>
        <p style="margin:4px 0 0; color:var(--text-muted); font-size:14px;">Track your stock portfolio in real time.</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Portfolio Display Guard
# ──────────────────────────────────────────────
if not st.session_state.portfolio:
    st.info("Add your first position using the sidebar on the left.")
    st.stop()

df = build_portfolio_df(st.session_state.portfolio, base_currency)

if df.empty:
    st.warning("Could not retrieve price data for any positions.")
    st.stop()

# ── Shared display helpers ─────────────────
portfolio_color_map = {
    t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
    for i, t in enumerate(st.session_state.portfolio.keys())
}
name_map = {t: fetch_company_name(t) for t in st.session_state.portfolio}

# ── Pre-compute analytics (cached 24h) ───────
_tickers       = list(st.session_state.portfolio.keys())
_price_data_1y = {t: fetch_analytics_history(t) for t in _tickers}
_spy_data      = fetch_analytics_history("SPY")
analytics_df   = compute_analytics(st.session_state.portfolio, _price_data_1y, _spy_data)

# ── Pre-compute Monte Carlo ────────
_price_data_5y = {t: fetch_simulation_history(t) for t in _tickers}
_bt            = cached_run_monte_carlo_backtest(st.session_state.portfolio, _price_data_5y)

_start_prices_base = {}
_ticker_mc_results = {}
for _t in _tickers:
    _hist_5y = _price_data_5y.get(_t, pd.DataFrame())
    _fx_mc   = get_fx_rate(get_ticker_currency(_t), base_currency)
    _close_mc = _hist_5y["Close"].dropna() if not _hist_5y.empty and "Close" in _hist_5y.columns else pd.Series(dtype=float)
    if not _close_mc.empty:
        _cur_mc = float(_close_mc.iloc[-1]) * _fx_mc
        _start_prices_base[_t] = _cur_mc
        _ticker_mc_results[_t] = cached_run_monte_carlo_ticker(
            ticker=_t, hist=_hist_5y, current_price=_cur_mc, horizon_days=252
        )

_portfolio_mc = cached_run_monte_carlo_portfolio(
    portfolio=st.session_state.portfolio,
    price_data=_price_data_5y,
    start_prices_base=_start_prices_base,
    horizon_days=252,
)

fund_rows = []
for _t in _tickers:
    _f = fetch_fundamentals(_t)
    if _f:
        _tc = get_ticker_currency(_t)
        _fx_ccy = "GBP" if _tc == "GBX" else _tc
        if _fx_ccy != base_currency:
            _fx = get_fx_rate(_fx_ccy, base_currency)
            if _f.get("1-Year Low"):  _f["1-Year Low"]  = round(_f["1-Year Low"]  * _fx, 2)
            if _f.get("1-Year High"): _f["1-Year High"] = round(_f["1-Year High"] * _fx, 2)
        fund_rows.append({"Ticker": _t, **_f})

# ── KPI values ───────────────────────────────
total_value   = df["Total Value"].sum()
daily_pnl     = df["Daily P&L"].sum()
n_positions   = len(st.session_state.portfolio)
cost_basis    = (df["Buy Price"] * df["Shares"]).sum()
total_divs    = df["Dividends"].sum()
total_return  = total_value + total_divs - cost_basis
total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

pnl_color  = C_POSITIVE if daily_pnl    >= 0 else C_NEGATIVE
ret_color  = C_POSITIVE if total_return >= 0 else C_NEGATIVE

n_purchases = sum(len(lots) for lots in st.session_state.portfolio.values())
positions_sub = (
    f'<div class="kpi-sub sm" style="color: var(--text-muted);">{n_purchases} purchases</div>'
    if n_purchases != n_positions else ""
)

_all_dates = [lot["purchase_date"] for lots in st.session_state.portfolio.values() for lot in lots if lot.get("purchase_date")]
_first_purchase = min(_all_dates) if _all_dates else None
return_sub = (
    f'<div class="kpi-sub sm" style="color: var(--text-muted);">Since {_first_purchase}</div>'
    if _first_purchase else ""
)

_spacer_md = '<div class="kpi-sub" style="visibility:hidden;">.</div>'
_spacer_sm = '<div class="kpi-sub sm" style="visibility:hidden;">.</div>'


def _kpi_card(label: str, value: str, border_color: str, line1: str = "", line2: str = "", hero: bool = False) -> str:
    is_neutral = border_color == C_CARD_BRD
    value_color = "var(--text-color)" if is_neutral else border_color
    actual_border = "rgba(148,163,184,0.3)" if is_neutral else border_color
    font = "30px" if hero else "26px"
    return (
        f'<div style="background:var(--secondary-background-color);border-radius:10px;'
        f'padding:22px 26px;text-align:center;border:1px solid {actual_border};'
        f'display:flex;flex-direction:column;justify-content:center;align-items:center;'
        f'box-shadow:0 1px 4px rgba(0,0,0,0.12);">'
        f'<div class="kpi-label">{label}</div>'
        f'<div style="font-size:{font};font-weight:600;line-height:1.2;color:{value_color};">{value}</div>'
        f'{line1 or _spacer_md}'
        f'{line2 or _spacer_sm}'
        f'</div>'
    )


# ──────────────────────────────────────────────
# 5-Tab Layout  (Phase 3)
# ──────────────────────────────────────────────
tab_overview, tab_positions, tab_risk, tab_forecast, tab_diagnostics, tab_guide = st.tabs([
    "Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"
])

# ══════════════════════════════════════════════
# TAB 1 — Overview  (Phases 4)
# ══════════════════════════════════════════════
with tab_overview:
    # ── KPI cards: 2 hero + 2 secondary ──────
    section_header("Portfolio Summary")

    _card_1 = _kpi_card(
        "Total Portfolio Value",
        f"{currency_symbol}{total_value:,.2f}",
        C_CARD_BRD,
        hero=True,
    )
    _card_2 = _kpi_card(
        "Total Return",
        f'{"+" if total_return >= 0 else ""}{currency_symbol}{total_return:,.2f}',
        ret_color,
        line1=f'<div class="kpi-sub" style="color: {ret_color};">{"+" if total_ret_pct >= 0 else ""}{total_ret_pct:,.2f}%</div>',
        line2=return_sub if return_sub else _spacer_sm,
        hero=True,
    )
    _card_3 = _kpi_card(
        "Today's Change",
        f'{"+" if daily_pnl >= 0 else ""}{currency_symbol}{daily_pnl:,.2f}',
        pnl_color,
        line1=f'<div class="kpi-sub sm" style="color: var(--text-muted);">Since yesterday\'s close</div>',
    )
    _card_4 = _kpi_card(
        "Positions",
        str(n_positions),
        C_CARD_BRD,
        line1=positions_sub if positions_sub else _spacer_md,
    )

    st.markdown(f"""
    <div class="kpi-grid">
        {_card_1}{_card_2}{_card_3}{_card_4}
    </div>
    """, unsafe_allow_html=True)

    # ── Download Report ───────────────────────────
    # All inputs are already cached upstream (prices 15 min, everything else 24h),
    # so this is pure openpyxl computation — no network calls — and always matches
    # the numbers shown on the dashboard.
    _excel_bytes = build_excel_report(
        positions_df=df,
        analytics_df=analytics_df,
        fund_rows=fund_rows,
        price_histories={t: fetch_price_history_short(t) for t in st.session_state.portfolio},
        name_map=name_map,
        currency=base_currency,
        summary_kpis={
            "total_value":   total_value,
            "daily_pnl":     daily_pnl,
            "cost_basis":    cost_basis,
            "total_divs":    total_divs,
            "total_return":  total_return,
            "total_ret_pct": total_ret_pct,
            "n_positions":   n_positions,
        },
        bt_result=_bt,
        ticker_mc_results=_ticker_mc_results,
        portfolio_mc=_portfolio_mc,
    )

    st.markdown("")  # spacer

    _dl_left, _dl_center, _dl_right = st.columns([1, 1, 1])
    with _dl_center:
        st.download_button(
            label="Download Excel Report",
            data=_excel_bytes,
            file_name=f"portfolio_{pd.Timestamp.today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    _last_updated = datetime.now().strftime("%H:%M")
    st.markdown(
        f'<p style="color: var(--text-muted); font-size:12px; text-align:center; margin-top:-8px;">'
        f'Prices last fetched at {_last_updated} · cached up to 15 min</p>',
        unsafe_allow_html=True,
    )

    # ── Allocation + Comparison side by side ──
    section_header("Allocation & Performance")

    col_alloc, col_comp = st.columns([1, 1])

    with col_alloc:
        render_allocation(df, name_map, portfolio_color_map)

    with col_comp:
        render_comparison(st.session_state.portfolio, name_map, portfolio_color_map, base_currency)



# ══════════════════════════════════════════════
# TAB 2 — Positions  (Phase 5)
# ══════════════════════════════════════════════
with tab_positions:
    section_header("Your Positions")
    render_positions_table(df, name_map, currency_symbol)

    section_header(
        "Price History",
        "The full price history for each stock. The orange dashed line shows your buy price; "
        "the grey line marks when you bought it.",
    )
    render_price_history(st.session_state.portfolio, name_map, portfolio_color_map, base_currency, currency_symbol)


# ══════════════════════════════════════════════
# TAB 3 — Risk & Analytics  (Phase 6)
# ══════════════════════════════════════════════
with tab_risk:
    render_risk_analytics(analytics_df, _price_data_1y, _tickers, fund_rows, base_currency, positions_df=df)


# ══════════════════════════════════════════════
# TAB 4 — Forecast  (Phase 7)
# ══════════════════════════════════════════════
with tab_forecast:
    render_portfolio_outlook(_portfolio_mc, _tickers, base_currency, currency_symbol)
    st.divider()
    render_position_outlook(df, _price_data_5y, _tickers, base_currency, currency_symbol)


# ══════════════════════════════════════════════
# TAB 5 — Diagnostics  (Phase 8)
# ══════════════════════════════════════════════
with tab_diagnostics:
    render_backtest(_bt, _tickers, base_currency, currency_symbol)
    st.divider()
    render_model_diagnostics(_price_data_5y, _tickers)


# ══════════════════════════════════════════════
# TAB 6 — Guide
# ══════════════════════════════════════════════
with tab_guide:
    section_header("Getting Started")
    st.markdown("""
Pick a stock market from the sidebar, search for a company, enter how many shares you bought and when.
The app looks up prices automatically. You can add the same stock multiple times if you bought at different dates.
""")

    section_header("The Numbers at the Top (KPI Cards)")
    st.markdown("""
| Metric | What it means |
|--------|--------------|
| **Total Portfolio Value** | What all your shares are worth right now, converted to your chosen currency. |
| **Today's Change** | How much the total value moved since the market closed yesterday. Green = up, red = down. |
| **Total Return** | The difference between what your portfolio is worth today (including any dividends received) and what you originally paid. The percentage below it is that same number as a fraction of your total investment. |
| **Positions** | How many different stocks you own. If you bought the same stock twice, that counts as one position but two purchases. |
""")

    section_header("Charts")
    st.markdown("""
- **Portfolio Allocation** — a bar chart showing what percentage of your money is in each stock. If one bar is much longer than the rest, your portfolio is concentrated — a big move in that stock affects everything.
- **Portfolio Comparison** — every stock is set to 100 at the start so you can compare growth fairly. A stock at 130 has grown 30%; a stock at 85 has fallen 15%. Use the time range buttons to zoom in or out.
- **Price History** — the actual price chart for each stock. The orange dashed line is what you paid; the grey dashed line marks the date you bought it. If the price line is above the orange line, you are in profit on that position.
""")

    section_header("Risk & Analytics")
    st.markdown("""
These are standard measures used by professional investors. You do not need to understand all of them, but here is what the key ones mean:

- **Volatility** — how much the price swings day to day, expressed as a yearly percentage. Higher = more unpredictable. A stock with 25% volatility typically swings about 25% up or down in a year.
- **Worst Drop (Max Drawdown)** — the biggest peak-to-trough fall in the past year. If it says -35%, the stock lost 35% from its highest point before recovering.
- **Return/Risk Score (Sharpe Ratio)** — how much return you earn per unit of risk. Above 1 is good, above 2 is excellent, below 0 means the stock lost money.
- **Market Sensitivity (Beta)** — how much the stock moves relative to the overall market (S&P 500). Beta of 1.0 means it moves in lockstep. Above 1.0 means it swings more; below 1.0 means it is calmer.
- **Correlation** — whether two stocks tend to go up and down together (close to 1.0) or move independently (close to 0). Owning stocks with low correlation reduces overall portfolio risk.
- **P/E Ratio** — how many years of current earnings you are paying for. A P/E of 20 means you pay 20× this year's profit. Lower can mean cheaper; higher can mean the market expects fast growth.
- **Dividend Yield** — the annual dividend payment as a percentage of the stock price. A 3% yield means you receive roughly 3% of your investment back as cash each year.
""")

    section_header("Monte Carlo Simulation (the Fan Charts)")
    st.markdown("""
Imagine replaying the stock market 1,000 times. Each replay uses the stock's real historical behaviour — how much it typically moves each day — but shuffles the order of good and bad days randomly. The result is a fan of possible futures:

- The **dark band** is where 50% of the replays ended up — the most likely zone.
- The **light band** covers 80% of replays — a wider range of plausible outcomes.
- The **dashed line** is the median — exactly half of the replays were above, half below.

If the fan is wide, there is a lot of uncertainty. If it is narrow, the stock has been relatively stable historically.

**Portfolio Outlook** adds two extra metrics:
- **VaR (Value at Risk) 95%** — in the worst 5% of replays, the portfolio lost at least this much. Think of it as a "bad month" scenario.
- **CVaR (Expected Shortfall) 95%** — the average loss in those worst 5% of replays. Always worse than VaR; this is what tail risk actually costs on average.

**Position Outlook** does the same thing for a single stock. The probability figure tells you: out of 1,000 replays, how many ended above your buy price?
""")

    section_header("Model Diagnostics — When to Be Sceptical")
    st.markdown("""
The simulation assumes that daily price changes follow a bell curve (normal distribution) and are independent from one day to the next. These assumptions are often wrong for real stocks:

- **Jarque-Bera: Fail** means the stock has fatter tails than a bell curve — extreme days (crashes or rallies) happen more often than the model expects. The fan chart will understate how bad a bad day can really be.
- **Ljung-Box: Fail** means today's return is correlated with recent days — there is momentum or mean-reversion that the model ignores.
- **QQ Plot** — if the dots follow the red line, the bell-curve assumption holds. Where the dots curve away from the line, the real distribution has heavier tails.

Most individual stocks will fail the normality test. That does not make the simulation useless — it means you should treat the edges of the fan as optimistic. Real tail risk is likely larger than shown.
""")
