import json
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from src.localstorage_component import ls_get, ls_set

from src.stocks import (
    get_sp500_stocks, get_ftse100_stocks, get_dax_stocks,
    get_cac40_stocks, get_smi_stocks, get_aex_stocks,
    get_ibex_stocks, get_etfs, get_crypto, get_commodities,
    get_reits, get_bonds, get_emerging_markets, TICKER_COLORS
)
from src.fx import get_ticker_currency, get_fx_rate, get_historical_fx_rate, CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df, fetch_buy_price, compute_analytics
from src.monte_carlo import (
    run_monte_carlo_backtest, run_monte_carlo_portfolio,
    run_monte_carlo_ticker, compute_var_cvar,
)
from src.excel_export import build_excel_report

@st.cache_data(ttl=900)   # 15 minutes — current price data
def fetch_price_history_short(ticker: str) -> pd.DataFrame:
    """Fetch 6-month price history. Cached for 15 minutes."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400)  # 24 hours — historical chart data
def fetch_price_history_long(ticker: str) -> pd.DataFrame:
    """Fetch full price history. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="max")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400)  # 24 hours — fundamental data
def fetch_fundamentals(ticker: str) -> dict:
    """Fetch P/E, dividend yield, and 1-year range. Cached for 24 hours."""
    try:
        info = yf.Ticker(ticker).info
        current  = info.get("currentPrice") or info.get("regularMarketPrice")
        low_1y   = info.get("fiftyTwoWeekLow")
        high_1y  = info.get("fiftyTwoWeekHigh")
        pe       = info.get("trailingPE")
        div_rate = info.get("dividendRate")  # annual dividend per share, native currency

        # Prefer computing yield from dividendRate/price — more reliable than dividendYield
        # which yfinance returns inconsistently (sometimes decimal fraction, sometimes percent).
        if div_rate and current and current > 0:
            candidate = round(div_rate / current * 100, 4)
            # Guard: yields above 20% almost certainly indicate a unit mismatch
            # (e.g. dividendRate returned in cents instead of dollars). Fall through
            # to the dividendYield fallback in that case.
            div_pct = candidate if candidate <= 20.0 else None
        else:
            div_pct = None

        if div_pct is None:
            div = info.get("dividendYield")
            if div is not None:
                # dividendYield is normally a decimal fraction (0.0042 = 0.42%).
                # If result > 20% after multiplying it was already in percent form.
                candidate = div * 100
                div_pct = candidate if candidate <= 20.0 else div

        # For London-listed tickers yfinance returns fiftyTwoWeekLow/High in GBX
        # (pence) but currentPrice in GBP, so divide by 100 to make units consistent.
        ticker_ccy = get_ticker_currency(ticker)
        if ticker_ccy == "GBX":
            low_1y  = low_1y  / 100 if low_1y  else None
            high_1y = high_1y / 100 if high_1y else None

        position = None
        if current and low_1y and high_1y and high_1y > low_1y:
            position = round((current - low_1y) / (high_1y - low_1y) * 100, 1)

        return {
            "P/E Ratio":      round(pe, 1)        if pe      else None,
            "Div Yield (%)":  round(div_pct, 2)   if div_pct else None,
            "1-Year Low":     round(low_1y, 2)     if low_1y  else None,
            "1-Year High":    round(high_1y, 2)    if high_1y else None,
            "1-Year Position": position,
        }
    except Exception:
        return {}


@st.cache_data(ttl=86400)  # 24 hours — company name
def fetch_company_name(ticker: str) -> str:
    """Fetch short company name. Falls back to ticker on failure."""
    try:
        info = yf.Ticker(ticker).info
        return info.get("shortName") or info.get("longName") or ticker
    except Exception:
        return ticker


@st.cache_data(ttl=86400)  # 24 hours — 5-year history for Monte Carlo
def fetch_simulation_history(ticker: str) -> pd.DataFrame:
    """Fetch up to 5-year price history for Monte Carlo simulation. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="5y")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400)  # 24 hours — analytics price data
def fetch_analytics_history(ticker: str) -> pd.DataFrame:
    """Fetch 1-year price history for analytics. Cached for 24 hours."""
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        hist.index = hist.index.tz_localize(None)
        return hist
    except Exception:
        return pd.DataFrame()


# ── Color tokens ──────────────────────────────────────────────────────────────
CHART_COLORS = ["#1D4ED8", "#0EA5E9", "#6366F1", "#10B981", "#F59E0B",
                "#EC4899", "#8B5CF6", "#06B6D4", "#22C55E", "#F97316"]

_C_POSITIVE    = "#16A34A"
_C_NEGATIVE    = "#DC2626"
_C_NEUTRAL     = "#94A3B8"
_C_AMBER       = "#D97706"
_PLOT_TMPL     = "plotly"
_C_METRIC_BRD  = "rgba(29,78,216,0.25)"
_C_CARD_BRD    = "rgba(29,78,216,0.3)"

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(page_title="Market Dashboard", layout="wide")

# ──────────────────────────────────────────────
# Global CSS
# ──────────────────────────────────────────────
st.markdown(f"""
<style>
h3 {{
    margin-top: 1.8rem !important;
    margin-bottom: 0.8rem !important;
}}
[data-testid="metric-container"] {{
    background-color: var(--secondary-background-color);
    border: 1px solid {_C_METRIC_BRD};
    border-radius: 8px;
    padding: 16px 20px;
}}
.kpi-card {{
    background-color: var(--secondary-background-color);
    border-radius: 8px;
    padding: 18px 24px;
    text-align: center;
}}
.kpi-label {{
    font-size: 12px;
    color: #475569;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 500;
}}
.kpi-value {{
    font-size: 26px;
    font-weight: 600;
    line-height: 1.2;
    color: var(--text-color);
}}
.section-intro {{
    color: #64748B;
    font-size: 14px;
    margin-bottom: 12px;
    line-height: 1.6;
}}
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Session State  (must run before any widgets)
# ──────────────────────────────────────────────
_LS_KEY = "market_dashboard_portfolio"

if "ls_loaded" not in st.session_state:
    _ls_data = ls_get(_LS_KEY)
    if _ls_data is not None:
        st.session_state.ls_loaded = True
        if _ls_data:
            try:
                _parsed = json.loads(_ls_data)
                if isinstance(_parsed, dict):
                    if "portfolio" in _parsed:
                        st.session_state.portfolio = _parsed["portfolio"]
                    if "currency" in _parsed:
                        st.session_state.currency = _parsed["currency"]
            except Exception:
                pass

if "portfolio" not in st.session_state:
    st.session_state.portfolio = {}

if "currency" not in st.session_state:
    st.session_state.currency = list(CURRENCY_SYMBOLS.keys())[0]

if "imported" not in st.session_state:
    st.session_state.imported = False

if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

if "pending_remove" not in st.session_state:
    st.session_state.pending_remove = False

if st.session_state.get("ls_loaded"):
    ls_set(_LS_KEY, json.dumps({
        "portfolio": st.session_state.portfolio,
        "currency": st.session_state.currency,
    }))

# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
col_title, col_currency = st.columns([4, 1])

with col_title:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
        <div style="width:4px; height:40px; background:#1D4ED8; border-radius:2px; flex-shrink:0;"></div>
        <h1 style="margin:0; padding:0;">Market Dashboard</h1>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("Track your stock portfolio in real time.")

with col_currency:
    base_currency = st.selectbox(
        "Currency",
        options=list(CURRENCY_SYMBOLS.keys()),
        key="currency",
    )

currency_symbol = CURRENCY_SYMBOLS[base_currency]

if st.session_state.get("portfolio") and any(
    lot.get("buy_fx_rate") for lots in st.session_state.portfolio.values() for lot in lots
):
    st.caption("Changing currency does not update historical buy FX rates stored with each lot.")

# ──────────────────────────────────────────────
# Stock List
# ──────────────────────────────────────────────
@st.cache_data(ttl=86400)
def load_stock_options() -> dict:
    return {
        "S&P 500":     get_sp500_stocks(),
        "FTSE 100":    get_ftse100_stocks(),
        "DAX":         get_dax_stocks(),
        "CAC 40":      get_cac40_stocks(),
        "SMI":         get_smi_stocks(),
        "AEX":         get_aex_stocks(),
        "IBEX 35":     get_ibex_stocks(),
        "ETFs":             get_etfs(),
        "Crypto":           get_crypto(),
        "Commodities":      get_commodities(),
        "REITs":            get_reits(),
        "Bonds":            get_bonds(),
        "Emerging Markets": get_emerging_markets(),
    }

all_stock_options = load_stock_options()

# ──────────────────────────────────────────────
# Add / Manage Positions
# ──────────────────────────────────────────────
is_new_user = not bool(st.session_state.portfolio)

with st.expander("Add / Manage Positions", expanded=is_new_user):
    if is_new_user:
        st.markdown(
            '<p class="section-intro">'
            'Welcome! Start by adding your first stock below. '
            'Select which market it\'s listed on, search for it by name, enter how many shares you bought and when — '
            'the app looks up the price automatically. '
            'Already have a saved portfolio? Import it or load the sample to explore.</p>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<p class="section-intro">'
            'Add a new position or remove an existing one. '
            'Each time you bought the same stock counts as a separate purchase.</p>',
            unsafe_allow_html=True
        )

    # Import / Load Sample
    col_import, col_sample = st.columns([3, 1], vertical_alignment="bottom")
    uploaded_file = col_import.file_uploader("Import saved portfolio (.json file)", type="json")
    st.caption("Use the file you previously exported with the 'Export Portfolio' button.")
    if col_sample.button("Load Sample Portfolio", use_container_width=True):
        import os
        sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_portfolio.json")
        with open(sample_path) as f:
            st.session_state.portfolio = json.load(f)
        st.session_state.imported = False
        st.rerun()

    if uploaded_file is not None and not st.session_state.imported:
        try:
            data = pd.read_json(uploaded_file, typ="series").to_dict()
            valid = (
                isinstance(data, dict)
                and all(
                    isinstance(ticker, str)
                    and isinstance(lots, list)
                    and all(
                        isinstance(lot, dict) and {"shares", "buy_price", "purchase_date"}.issubset(lot.keys())
                        for lot in lots
                    )
                    for ticker, lots in data.items()
                )
            )
            if not valid:
                st.error("Invalid portfolio file. Expected format: {ticker: [{shares, buy_price, purchase_date, ...}]}.")
            else:
                st.session_state.portfolio = data
                st.session_state.imported = True
                st.success("Portfolio imported successfully.")
                st.rerun()
        except Exception:
            st.error("Could not read the file. Make sure it is a valid portfolio JSON export.")

    if uploaded_file is None:
        st.session_state.imported = False

    st.markdown("---")

    # Add Position form
    manual_price = st.session_state.get("manual_price_toggle", False)
    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])

    with col1:
        index_choice = st.selectbox(
            "Stock Market",
            options=list(all_stock_options.keys()),
            index=0,
        )
        st.caption("US → S&P 500 · UK → FTSE 100 · Switzerland → SMI · Germany → DAX")
        stock_options = all_stock_options[index_choice]
        selected = st.selectbox(
            "Stock",
            options=list(stock_options.keys()),
            index=None,
            placeholder="Search by name or ticker…"
        )

    alt_asset = index_choice in ("Crypto", "Commodities")

    with col2:
        if alt_asset:
            amount_input = st.number_input(
                f"Amount ({base_currency})",
                min_value=0.0, value=None, step=1.0,
                placeholder="e.g. 5000"
            )
            shares_input = None
        else:
            shares_input = st.number_input(
                "Number of Shares",
                min_value=0.0, value=None, step=1.0,
                placeholder="e.g. 5"
            )
            amount_input = None

    with col3:
        if not alt_asset and manual_price:
            buy_price_input = st.number_input(
                f"Average Buy Price ({base_currency})",
                min_value=0.0, value=None, step=0.01,
                placeholder="e.g. 180.00"
            )
            purchase_date = None
        else:
            purchase_date = st.date_input(
                "Purchase Date" + (" (optional)" if alt_asset else ""),
                value=None,
                min_value=pd.Timestamp("1980-01-01").date(),
                max_value=pd.Timestamp.today().date()
            )
            buy_price_input = None

    with col4:
        if not alt_asset:
            st.markdown("<div style='margin-top: 36px;'>", unsafe_allow_html=True)
            manual_price = st.checkbox("Enter price manually", key="manual_price_toggle")
            st.caption("Leave unchecked to use the actual market price on that date (recommended).")
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Add to Portfolio"):
        if selected is None:
            st.warning("Please select a stock.")
        elif not alt_asset and (shares_input is None or shares_input == 0):
            st.warning("Please enter the number of shares.")
        elif alt_asset and (amount_input is None or amount_input == 0):
            st.warning("Please enter the amount.")
        elif not alt_asset and not manual_price and purchase_date is None:
            st.warning("Please select a purchase date or enter a price manually.")
        elif not alt_asset and manual_price and (buy_price_input is None or buy_price_input == 0):
            st.warning("Please enter a valid buy price.")
        else:
            ticker = stock_options[selected]
            ticker_currency = get_ticker_currency(ticker)
            if not alt_asset and manual_price:
                buy_price = buy_price_input
                # Manual price is entered in base currency — store fx_rate=1 so
                # build_portfolio_df does not double-convert.
                buy_fx_rate = 1.0
            elif purchase_date is not None:
                result = fetch_buy_price(ticker, str(purchase_date))
                if result is None:
                    st.error("No price data found for that date. Try a different date.")
                    buy_price = None
                else:
                    buy_price, actual_date = result
                    if actual_date != str(purchase_date):
                        st.info(
                            f"{purchase_date} was not a trading day. "
                            f"Using the closing price from {actual_date} instead."
                        )
                buy_fx_rate = get_historical_fx_rate(ticker_currency, base_currency, str(purchase_date))
            else:
                purchase_date = pd.Timestamp.today().date()
                result = fetch_buy_price(ticker, str(purchase_date))
                buy_price = result[0] if result else None
                buy_fx_rate = get_fx_rate(ticker_currency, base_currency)

            if buy_price is not None:
                shares = round(amount_input / buy_price, 6) if alt_asset else shares_input
                lot = {
                    "shares": shares,
                    "buy_price": buy_price,
                    "buy_fx_rate": buy_fx_rate,
                    "purchase_date": str(purchase_date) if purchase_date else None,
                    "manual_price": manual_price
                }
                st.session_state.portfolio.setdefault(ticker, []).append(lot)
                st.success(f"Added {shares:g} units of {ticker} at {currency_symbol}{buy_price:,.2f}")

    # Manage existing positions
    if st.session_state.portfolio:
        st.markdown("---")
        col_manage_title, col_clear, col_spacer = st.columns([3, 1, 6], vertical_alignment="bottom")
        col_manage_title.markdown("**Your purchases**")
        if col_clear.button("Clear All", key="clear_portfolio"):
            st.session_state.confirm_clear = True

        if st.session_state.confirm_clear:
            st.warning("This will delete all your positions. Are you sure?")
            col_yes, col_no, _ = st.columns([1, 1, 8])
            if col_yes.button("Yes, clear all", key="confirm_clear_yes"):
                st.session_state.portfolio = {}
                st.session_state.confirm_clear = False
                st.rerun()
            if col_no.button("Cancel", key="confirm_clear_no"):
                st.session_state.confirm_clear = False
                st.rerun()

        for t, lots in list(st.session_state.portfolio.items()):
            for i, lot in enumerate(lots):
                col_name, col_detail, col_date, col_btn, col_spacer = st.columns([2, 3, 2, 1, 3])
                col_name.write(f"{t} — Buy {i + 1}")
                tc = get_ticker_currency(t)
                display_tc = "GBP" if tc == "GBX" else tc
                col_detail.caption(f"{lot['shares']:g} shares · {display_tc} {lot['buy_price']:,.2f}")
                col_date.write(lot["purchase_date"] or "Manual")
                if col_btn.button("×", key=f"remove_{t}_{i}"):
                    st.session_state.pending_remove = (t, i)
                    st.rerun()

        if st.session_state.pending_remove:
            pt, pi = st.session_state.pending_remove
            st.warning(f"Remove {pt} (Buy {pi + 1})? This cannot be undone.")
            col_yes, col_no, _ = st.columns([1, 1, 8])
            if col_yes.button("Remove", key="confirm_remove_yes"):
                st.session_state.portfolio[pt].pop(pi)
                if not st.session_state.portfolio[pt]:
                    del st.session_state.portfolio[pt]
                st.session_state.pending_remove = None
                st.rerun()
            if col_no.button("Cancel", key="confirm_remove_no"):
                st.session_state.pending_remove = None
                st.rerun()

# ──────────────────────────────────────────────
# Portfolio Display
# ──────────────────────────────────────────────
if not st.session_state.portfolio:
    st.stop()

st.divider()

df = build_portfolio_df(st.session_state.portfolio, base_currency)

if df.empty:
    st.warning("Could not retrieve price data for any positions.")
    st.stop()

# ── Shared display helpers ─────────────────
# Single color map keyed by portfolio insertion order — used consistently across all charts.
portfolio_color_map = {
    t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
    for i, t in enumerate(st.session_state.portfolio.keys())
}
# Company names — falls back to ticker if fetch fails.
name_map = {t: fetch_company_name(t) for t in st.session_state.portfolio}

# ── Pre-compute analytics (cached 24h) ───────
# Done here (outside expanders) so the export button always has data,
# regardless of which sections the user has opened.
_tickers       = list(st.session_state.portfolio.keys())
_price_data_1y = {t: fetch_analytics_history(t) for t in _tickers}
_spy_data      = fetch_analytics_history("SPY")
analytics_df   = compute_analytics(st.session_state.portfolio, _price_data_1y, _spy_data)

# ── Pre-compute Monte Carlo (cached 24h via fetch_simulation_history) ────────
# 5y fetches are cached; the simulations themselves are fast (~100ms for 1,000 paths).
_price_data_5y = {t: fetch_simulation_history(t) for t in _tickers}
_bt            = run_monte_carlo_backtest(st.session_state.portfolio, _price_data_5y)

_start_prices_base = {}
_ticker_mc_results = {}
for _t in _tickers:
    _hist_5y = _price_data_5y.get(_t, pd.DataFrame())
    _fx_mc   = get_fx_rate(get_ticker_currency(_t), base_currency)
    _close_mc = _hist_5y["Close"].dropna() if not _hist_5y.empty and "Close" in _hist_5y.columns else pd.Series(dtype=float)
    if not _close_mc.empty:
        _cur_mc = float(_close_mc.iloc[-1]) * _fx_mc
        _start_prices_base[_t] = _cur_mc
        _ticker_mc_results[_t] = run_monte_carlo_ticker(
            hist=_hist_5y, current_price=_cur_mc, n_sims=1000, horizon_days=252
        )

_portfolio_mc = run_monte_carlo_portfolio(
    portfolio=st.session_state.portfolio,
    price_data=_price_data_5y,
    start_prices_base=_start_prices_base,
    n_sims=1000,
    horizon_days=252,
)
fund_rows      = []
for _t in _tickers:
    _f = fetch_fundamentals(_t)
    if _f:
        # Convert 1-year range to base currency so Fundamentals matches Positions pricing.
        _tc = get_ticker_currency(_t)
        _fx_ccy = "GBP" if _tc == "GBX" else _tc
        if _fx_ccy != base_currency:
            _fx = get_fx_rate(_fx_ccy, base_currency)
            if _f.get("1-Year Low"):  _f["1-Year Low"]  = round(_f["1-Year Low"]  * _fx, 2)
            if _f.get("1-Year High"): _f["1-Year High"] = round(_f["1-Year High"] * _fx, 2)
        fund_rows.append({"Ticker": _t, **_f})

# ── KPI Cards ────────────────────────────────
total_value   = df["Total Value"].sum()
daily_pnl     = df["Daily P&L"].sum()
n_positions   = len(st.session_state.portfolio)
cost_basis    = (df["Buy Price"] * df["Shares"]).sum()
total_divs    = df["Dividends"].sum()
total_return  = total_value + total_divs - cost_basis
total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

pnl_color  = _C_POSITIVE if daily_pnl    >= 0 else _C_NEGATIVE
ret_color  = _C_POSITIVE if total_return >= 0 else _C_NEGATIVE

n_purchases = sum(len(lots) for lots in st.session_state.portfolio.values())
positions_sub = f'<div style="color: var(--text-color); opacity: 0.55; font-size:12px; margin-top:4px;">{n_purchases} purchases</div>' if n_purchases != n_positions else ""

_all_dates = [lot["purchase_date"] for lots in st.session_state.portfolio.values() for lot in lots if lot.get("purchase_date")]
_first_purchase = min(_all_dates) if _all_dates else None
return_sub = f'<div style="color: var(--text-color); opacity: 0.55; font-size:12px; margin-top:4px;">Since {_first_purchase}</div>' if _first_purchase else ""

col_m1, col_m2, col_m3, col_m4 = st.columns(4)

_spacer_line_md  = '<div style="font-size:14px; margin-top:4px; visibility:hidden;">.</div>'
_spacer_line_sm  = '<div style="font-size:12px; margin-top:4px; visibility:hidden;">.</div>'

with col_m1:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {_C_CARD_BRD};">
        <div class="kpi-label">Total Portfolio Value</div>
        <div class="kpi-value" style="color: var(--text-color);">{currency_symbol}{total_value:,.2f}</div>
        {_spacer_line_md}
        {_spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

with col_m2:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {pnl_color};">
        <div class="kpi-label">Today's Change</div>
        <div class="kpi-value" style="color: {pnl_color};">
            {"+" if daily_pnl >= 0 else ""}{currency_symbol}{daily_pnl:,.2f}
        </div>
        <div style="color: var(--text-color); opacity: 0.55; font-size:14px; margin-top:4px;">Since yesterday's close</div>
        {_spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

with col_m3:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {ret_color};">
        <div class="kpi-label">Total Return</div>
        <div class="kpi-value" style="color: {ret_color};">
            {"+" if total_return >= 0 else ""}{currency_symbol}{total_return:,.2f}
        </div>
        <div style="color: {ret_color}; font-size: 14px; margin-top: 4px;">
            {"+" if total_ret_pct >= 0 else ""}{total_ret_pct:,.2f}%
        </div>
        {return_sub if return_sub else _spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

with col_m4:
    st.markdown(f"""
    <div class="kpi-card" style="border: 1px solid {_C_CARD_BRD};">
        <div class="kpi-label">Positions</div>
        <div class="kpi-value" style="color: var(--text-color);">{n_positions}</div>
        {positions_sub if positions_sub else _spacer_line_md}
        {_spacer_line_sm}
    </div>
    """, unsafe_allow_html=True)

from datetime import datetime
_last_updated = datetime.now().strftime("%H:%M")
st.markdown(
    f'<p style="text-align:right; color: var(--text-color); opacity: 0.55; font-size:12px; margin-top:4px;">Prices last fetched at {_last_updated} (cached up to 15 min)</p>',
    unsafe_allow_html=True
)
st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

# ── Download Report ───────────────────────────
_, _col_dl = st.columns([5, 1])
with _col_dl:
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
    st.download_button(
        label="Download Excel Report",
        data=_excel_bytes,
        file_name=f"portfolio_{pd.Timestamp.today().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ──────────────────────────────────────────────
# Positions Table
# ──────────────────────────────────────────────
st.divider()
with st.expander("Your Positions", expanded=True):
    st.markdown(
        '<p class="section-intro">Every stock you own, how much you paid, what it\'s worth now, '
        'and how much you\'ve gained or lost. <b>Today\'s Change</b> is how much your value moved since yesterday\'s market close. '
        '<b>Total Return</b> includes any dividends received. <b>Portfolio Share</b> is what percentage of your total investment this position represents.</p>',
        unsafe_allow_html=True
    )

    styled_df = df.copy().rename(columns={
        "Return (%)": "Total Return (%)",
        "Weight (%)": "Portfolio Share (%)",
        "Daily P&L":  "Today's Change",
        "Purchase":   "Buy #",
    })
    styled_df.insert(1, "Company", styled_df["Ticker"].map(name_map))

    def _color_pnl(val):
        if val > 0:   return f"color: {_C_POSITIVE}; font-weight: 500"
        elif val < 0: return f"color: {_C_NEGATIVE}; font-weight: 500"
        return f"color: {_C_NEUTRAL}"

    def _fmt_shares(x):
        return f"{int(x):,}" if x == int(x) else f"{x:g}"

    styled = (
        styled_df.set_index(["Ticker", "Company", "Buy #"])
        .style
        .format({
            "Shares":           _fmt_shares,
            "Buy Price":        lambda x: f"{currency_symbol}{x:,.2f}",
            "Current Price":    lambda x: f"{currency_symbol}{x:,.2f}",
            "Total Value":      lambda x: f"{currency_symbol}{x:,.2f}",
            "Dividends":        lambda x: f"{currency_symbol}{x:,.2f}",
            "Today's Change":   lambda x: f"{currency_symbol}{x:,.2f}",
            "Total Return (%)": "{:,.2f}%",
            "Portfolio Share (%)": "{:,.2f}%",
        })
        .map(_color_pnl, subset=["Today's Change", "Total Return (%)"])
    )

    st.dataframe(styled, use_container_width=True, column_config={
        "Shares":    st.column_config.TextColumn("Shares", width="small"),
        "Dividends": st.column_config.NumberColumn("Dividends", help="Total dividends received since purchase. Already included in Total Return."),
    })

    st.download_button(
        label="Export Portfolio",
        data=pd.Series(st.session_state.portfolio).to_json(),
        file_name="portfolio.json",
        mime="application/json"
    )

# ──────────────────────────────────────────────
# Portfolio Allocation
# ──────────────────────────────────────────────
st.divider()
with st.expander("Portfolio Allocation", expanded=True):
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
    alloc_df["Company"] = alloc_df["Ticker"].map(name_map)
    alloc_color_map = {name_map[t]: portfolio_color_map[t] for t in alloc_df["Ticker"]}
    fig_alloc = px.bar(
        alloc_df,
        x="Portfolio Share (%)",
        y="Company",
        orientation="h",
        color="Company",
        color_discrete_map=alloc_color_map,
        text=alloc_df["Portfolio Share (%)"].map(lambda v: f"{v:.1f}%"),
    )
    fig_alloc.update_traces(textposition="outside")
    fig_alloc.update_layout(
        xaxis_title="Portfolio Share (%)",
        yaxis_title=None,
        showlegend=False,
        template=_PLOT_TMPL,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[0, alloc_df["Portfolio Share (%)"].max() * 1.15]),
    )
    st.plotly_chart(fig_alloc, use_container_width=True)

# ──────────────────────────────────────────────
# Side-by-Side Comparison
# ──────────────────────────────────────────────
st.divider()
with st.expander("How My Stocks Compare", expanded=True):
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
        range_options = {"3 months": "3mo", "6 months": "6mo", "1 year": "1y", "All time": "max"}
        range_label = st.radio("Time range", list(range_options.keys()), index=1, horizontal=True)
        selected_range = range_options[range_label]
    with col_fx_comp:
        fx_adjust_comparison = st.toggle("Currency-adjusted", key="fx_toggle_comparison")

    @st.cache_data(ttl=900)
    def fetch_price_history_range(ticker: str, period: str) -> pd.DataFrame:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            hist.index = hist.index.tz_localize(None)
            return hist
        except Exception:
            return pd.DataFrame()

    comparison_data = {}
    for t in st.session_state.portfolio:
        hist = fetch_price_history_range(t, selected_range)
        if hist.empty:
            st.warning(f"Could not load data for {t} — skipping.")
            continue
        ticker_currency = get_ticker_currency(t)
        if fx_adjust_comparison and ticker_currency != base_currency:
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

    comp_name_map = {t: name_map.get(t, t) for t in comparison_df.columns}
    comp_color_map = {comp_name_map[t]: portfolio_color_map[t] for t in comparison_df.columns if t in portfolio_color_map}
    comparison_df_display = comparison_df.rename(columns=comp_name_map)
    title_suffix = f"({base_currency}-adjusted)" if fx_adjust_comparison else "(native currencies)"
    fig_comp = px.line(
        comparison_df_display,
        x=comparison_df_display.index,
        y=comparison_df_display.columns,
        color_discrete_map=comp_color_map,
    )
    fig_comp.update_layout(
        xaxis_title="Date",
        yaxis_title=f"Indexed growth (100 = start)  —  {range_label}  {title_suffix}",
        legend_title="Stock",
        template=_PLOT_TMPL,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig_comp.add_hline(y=100, line_dash="dash", line_color="gray")
    st.plotly_chart(fig_comp, use_container_width=True)

# ──────────────────────────────────────────────
# Price History
# ──────────────────────────────────────────────
st.divider()
st.markdown("### Price History")
st.markdown(
    '<p class="section-intro">The full price history for each stock you own. '
    'The dashed line shows what you paid. The grey line marks when you bought it. '
    'Prices are shown in each stock\'s native trading currency — enable <b>Currency-adjusted</b> to convert to your base currency. '
    'Click any stock below to expand its chart.</p>',
    unsafe_allow_html=True
)

col_range_hist, col_to, col_fx, _ = st.columns([4, 2, 2, 3])
with col_range_hist:
    hist_range_options = ["3 months", "6 months", "1 year", "2 years", "Since purchase", "Custom"]
    hist_range_label = st.radio("Time range", hist_range_options, index=4, horizontal=True, key="hist_range")
with col_to:
    date_to = st.date_input("To", value=pd.Timestamp.today())
with col_fx:
    st.write(" ")
    st.write(" ")
    fx_adjust_history = st.toggle("Currency-adjusted", key="fx_toggle_history")

date_from = None
if hist_range_label == "Custom":
    date_from = st.date_input("From date", value=None, min_value=pd.Timestamp("1980-01-01").date(), key="hist_custom_from")

_hist_range_months = {"3 months": 3, "6 months": 6, "1 year": 12, "2 years": 24}

for idx, (t, lots) in enumerate(st.session_state.portfolio.items()):
    hist = fetch_price_history_long(t)
    if hist.empty:
        st.warning(f"No price history available for {t}.")
        continue

    ticker_currency = get_ticker_currency(t)

    if fx_adjust_history and ticker_currency != base_currency:
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
    title_suffix = f"({base_currency}-adjusted)" if fx_adjust_history else f"({ticker_currency})"
    company = name_map.get(t, t)
    with st.expander(f"{company} ({t}) — Price History {title_suffix}", expanded=False):
        if ticker_currency == "GBX" and not fx_adjust_history:
            st.caption("Prices shown in GBX (British pence). 100 GBX = 1 GBP. Enable Currency-adjusted above to convert to your base currency.")
        fig_hist = px.line(
            hist_converted,
            x=hist_converted.index,
            y="Close",
            color_discrete_sequence=[line_color],
        )
        fig_hist.update_layout(
            xaxis_title="Date",
            yaxis_title=y_label,
            xaxis_range=[str(pd.Timestamp(effective_from).date()), str(date_to)],
            showlegend=False,
            template=_PLOT_TMPL,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
        )

        for i, lot in enumerate(lots):
            if fx_adjust_history:
                fx_rate = get_fx_rate(ticker_currency, base_currency)
                buy_price_display = round(lot["buy_price"] * fx_rate, 2)
                buy_label = f"Buy {i + 1}  {currency_symbol}{buy_price_display}"
            else:
                buy_price_display = lot["buy_price"]
                buy_label = f"Buy {i + 1}  {buy_price_display}"

            fig_hist.add_hline(
                y=buy_price_display,
                line_dash="dash",
                line_color=_C_AMBER,
                annotation_text=buy_label,
                annotation_position="top left"
            )
            if lot["purchase_date"]:
                fig_hist.add_vline(
                    x=str(pd.Timestamp(lot["purchase_date"]).date()),
                    line_dash="dash",
                    line_color="gray"
                )

        st.plotly_chart(fig_hist, use_container_width=True)

# ──────────────────────────────────────────────
# Risk & Analytics
# ──────────────────────────────────────────────
st.divider()
with st.expander("Risk & Analytics", expanded=False):
    st.markdown(
        '<p class="section-intro">A deeper look at how risky your positions are and how efficiently they\'ve rewarded that risk. '
        'All figures are based on the past 12 months of daily price data. '
        'This section uses financial industry-standard metrics — each one is explained below its table.</p>',
        unsafe_allow_html=True
    )

    if not analytics_df.empty:
        # ── Risk Metrics ──
        st.markdown("##### Risk Metrics")
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
            if val >= 1:   return f"color: {_C_POSITIVE}"
            if val >= 0:   return f"color: {_C_AMBER}"
            return f"color: {_C_NEGATIVE}"

        def _color_volatility(val):
            if not isinstance(val, (int, float)): return ""
            if val <= 20:  return f"color: {_C_POSITIVE}"
            if val <= 35:  return f"color: {_C_AMBER}"
            return f"color: {_C_NEGATIVE}"

        def _color_drawdown(val):
            if not isinstance(val, (int, float)): return ""
            if val >= -20: return f"color: {_C_POSITIVE}"
            if val >= -40: return f"color: {_C_AMBER}"
            return f"color: {_C_NEGATIVE}"

        risk_display = analytics_df.set_index("Ticker").rename(columns={
            "Volatility":   "Volatility (%)",
            "Max Drawdown": "Worst Drop (%)",
            "Sharpe Ratio": "Return/Risk Score",
            "Beta":         "Market Sensitivity",
        })

        styled_risk = (
            risk_display.style
            .format({
                "Volatility (%)":     "{:.1f}%",
                "Worst Drop (%)":     "{:.1f}%",
                "Return/Risk Score":  "{:.2f}",
                "Market Sensitivity": "{:.2f}",
            }, na_rep="—")
            .map(_color_volatility, subset=["Volatility (%)"])
            .map(_color_drawdown,   subset=["Worst Drop (%)"])
            .map(_color_sharpe,     subset=["Return/Risk Score"])
        )
        st.dataframe(styled_risk, use_container_width=True)

        # ── Correlation Matrix ──
        if len(_tickers) >= 2:
            st.markdown("##### How Your Stocks Move Together")
            st.markdown(
                '<p class="section-intro">'
                'Shows how closely your positions move in sync. '
                '<b>1.0</b> = always move in the same direction at the same time. '
                '<b>−1.0</b> = always move in opposite directions. '
                '<b>0</b> = no relationship at all. '
                'Holding stocks that don\'t all move together reduces your overall risk — if one falls, the others may not. '
                'If you see no blue cells, it means none of your stocks tend to move in opposite directions — this is normal for a typical portfolio.'
                ' <i>Note: this uses 1-year daily returns; the Excel export uses a 6-month window.</i>'
                '</p>',
                unsafe_allow_html=True
            )
            _returns = {
                t: _price_data_1y[t]["Close"].pct_change().dropna()
                for t in _tickers
                if not _price_data_1y.get(t, pd.DataFrame()).empty
            }
            if len(_returns) >= 2:
                corr_df = pd.DataFrame(_returns).dropna().corr()
                fig_corr = px.imshow(
                    corr_df,
                    color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1,
                    text_auto=".2f",
                )
                fig_corr.update_layout(
                    template=_PLOT_TMPL,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=20),
                    coloraxis_colorbar=dict(title="Correlation"),
                )
                st.plotly_chart(fig_corr, use_container_width=True)

        # ── Fundamentals ──
        st.markdown("##### Valuation & Price Range")
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
            st.dataframe(
                fund_df,
                use_container_width=True,
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
                    ),
                },
            )

# ──────────────────────────────────────────────
# Monte Carlo Backtest
# ──────────────────────────────────────────────
st.divider()
with st.expander("Monte Carlo Backtest", expanded=False):
    st.markdown(
        '<p class="section-intro">'
        '<b>What is a Monte Carlo simulation?</b> It runs thousands of possible futures by randomly sampling from the asset\'s historical daily return distribution. '
        'Each simulated day draws a return that is plausible given how the stock has behaved in the past. '
        'Run 1,000 times, this produces a fan of outcomes — wide when the asset is volatile, narrow when it is stable. '
        'The edges of the fan are not predictions; they are a range of outcomes consistent with past behaviour.'
        '<br><br>'
        '<b>What the backtest does.</b> Rather than only showing a forward projection (which cannot be verified), this section first tests the model against history. '
        'It takes data from up to 4 years ago, runs the simulation forward for one year using only that older data, '
        'then compares the simulated fan to what your portfolio actually did. '
        'If the model is well-calibrated, the actual value should fall inside the 80% band roughly 80% of the time. '
        'A hit rate far below that means the model was overconfident — the real moves were more extreme than history suggested.'
        '</p>',
        unsafe_allow_html=True
    )

    if not st.session_state.portfolio:
        st.info("Add positions to run the backtest.")
    else:
        if not _bt:
            st.warning(
                "Not enough price history to run the backtest. "
                "Each position needs at least 2 years of trading data. "
                f"Tickers excluded due to short history: "
                f"{', '.join(t for t in _tickers if t not in _bt.get('tickers_used', []))}"
                if _bt else
                "Not enough price history to run the backtest. "
                "Each position needs at least 2 years of trading data."
            )
        else:
            # ── KPI row ──────────────────────────────────────────────────
            _col1, _col2, _col3 = st.columns(3)
            _col1.metric(
                "Hit Rate — 80% band",
                f"{_bt['hit_rate_80']}%",
                help="Percentage of trading days over the past year where the actual portfolio value fell within the simulated 80% confidence interval (p10–p90).",
            )
            _col2.metric(
                "Hit Rate — 50% band",
                f"{_bt['hit_rate_50']}%",
                help="Same check for the tighter 50% band (p25–p75). A well-calibrated model should be close to 50%.",
            )
            _col3.metric(
                "Training window",
                f"{_bt['train_days']} days",
                help=f"Number of trading days used to calibrate the model (data before {_bt['split_date']}).",
            )

            # ── Fan chart ────────────────────────────────────────────────
            st.markdown(
                '<p class="section-intro">'
                '• <b>Dark band</b> — 50% of simulated portfolios ended up in this range. Think of it as the most likely zone.<br>'
                '• <b>Light band</b> — 80% of simulations fell here. Outcomes outside this band were the rare, extreme scenarios.<br>'
                '• <b>Dashed line</b> — the median simulation path (exactly half above, half below).<br>'
                '• <b>Black line</b> — what your portfolio actually did. If it stayed mostly inside the fan, the model was a good fit for your holdings.'
                '</p>',
                unsafe_allow_html=True
            )
            _dates  = list(_bt["sim_dates"])
            _pct    = _bt["percentiles"]
            _actual = _bt["actual"]
            _sym    = currency_symbol

            _fig_bt = go.Figure()

            # 80% band (p10–p90)
            _fig_bt.add_trace(go.Scatter(
                x=_dates + list(reversed(_dates)),
                y=list(_pct["p90"]) + list(reversed(_pct["p10"])),
                fill="toself",
                fillcolor="rgba(99,110,250,0.12)",
                line=dict(width=0),
                name="80% of simulations",
                hoverinfo="skip",
            ))

            # 50% band (p25–p75)
            _fig_bt.add_trace(go.Scatter(
                x=_dates + list(reversed(_dates)),
                y=list(_pct["p75"]) + list(reversed(_pct["p25"])),
                fill="toself",
                fillcolor="rgba(99,110,250,0.25)",
                line=dict(width=0),
                name="50% of simulations",
                hoverinfo="skip",
            ))

            # Median simulation
            _fig_bt.add_trace(go.Scatter(
                x=_dates,
                y=_pct["p50"],
                line=dict(color="rgba(99,110,250,0.7)", width=1.5, dash="dash"),
                name="Median simulation",
            ))

            # Actual portfolio value
            _fig_bt.add_trace(go.Scatter(
                x=list(_actual.index),
                y=list(_actual.values),
                line=dict(color="#222222", width=2),
                name="Actual portfolio value",
            ))

            _fig_bt.update_layout(
                template=_PLOT_TMPL,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=40),
                yaxis=dict(tickprefix=_sym, title=f"Portfolio Value ({base_currency})"),
                xaxis=dict(title="Date"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                hovermode="x unified",
            )

            st.plotly_chart(_fig_bt, use_container_width=True)

            # ── Per-ticker reliability table ─────────────────────────────
            st.markdown("##### Model Reliability by Position")
            st.markdown(
                '<p class="section-intro">'
                'Shows how well the model performed for each position individually over the past year. '
                'The same simulation is run per stock and compared to its actual price path.'
                '<br><br>'
                '• <b>Hit Rate 80% CI</b> — the percentage of trading days over the past year where the actual price stayed inside the simulated 80% band. '
                'A well-calibrated model scores close to 80%. Much lower means the real moves were more extreme than the model expected.<br>'
                '• <b>Hit Rate 50% CI</b> — the same check for the tighter middle band. Should be close to 50% for a well-calibrated model.<br>'
                '• <b>Kurtosis</b> — measures how "fat" the tails of the return distribution are compared to a normal distribution (which scores 0). '
                'A score above 3 means unusually large moves happen more often than the model assumes — the model will understate risk for that stock. '
                'Crypto, small caps, and individual growth stocks typically score high here.<br>'
                '• <b>Skewness</b> — measures whether big moves tend to be up or down. Positive means the distribution has a longer right tail (large gains are more common than large losses). '
                'Negative means the opposite — losses tend to be more extreme than gains.<br>'
                '• <b>Fat-tailed</b> — a flag that fires when kurtosis exceeds 3. Treat confidence bands for these positions with extra scepticism.'
                '</p>',
                unsafe_allow_html=True
            )

            def _reliability_label(hit_rate_80: float) -> str:
                if hit_rate_80 >= 80:  return "Good"
                if hit_rate_80 >= 65:  return "Moderate"
                return "Low"

            def _color_reliability(val: str) -> str:
                if val == "Good":     return f"color: {_C_POSITIVE}; font-weight: 500"
                if val == "Moderate": return f"color: {_C_AMBER}; font-weight: 500"
                return f"color: {_C_NEGATIVE}; font-weight: 500"

            def _color_kurtosis(val) -> str:
                if not isinstance(val, (int, float)): return ""
                if val <= 1:  return f"color: {_C_POSITIVE}"
                if val <= 3:  return f"color: {_C_AMBER}"
                return f"color: {_C_NEGATIVE}"

            _rel_rows = []
            for _t in _bt["tickers_used"]:
                _hr   = _bt["ticker_hit_rates"].get(_t, {})
                _flag = _bt["ticker_flags"].get(_t, {})
                _rel_rows.append({
                    "Ticker":          _t,
                    "Hit Rate 80% CI": _hr.get("hit_rate_80"),
                    "Hit Rate 50% CI": _hr.get("hit_rate_50"),
                    "Kurtosis":        _flag.get("kurtosis"),
                    "Skewness":        _flag.get("skewness"),
                    "Fat-tailed":      "Yes" if _flag.get("fat_tailed") else "No",
                    "Reliability":     _reliability_label(_hr.get("hit_rate_80", 0)),
                })

            _rel_df = pd.DataFrame(_rel_rows).set_index("Ticker")

            _styled_rel = (
                _rel_df.style
                .format({
                    "Hit Rate 80% CI": "{:.1f}%",
                    "Hit Rate 50% CI": "{:.1f}%",
                    "Kurtosis":        "{:.2f}",
                    "Skewness":        "{:.2f}",
                }, na_rep="—")
                .map(_color_reliability, subset=["Reliability"])
                .map(_color_kurtosis,    subset=["Kurtosis"])
            )
            st.dataframe(_styled_rel, use_container_width=True)

            # ── Caveat ───────────────────────────────────────────────────
            st.caption(
                f"Simulated using up to {_bt['train_days']} days of historical log-returns calibrated before "
                f"{_bt['split_date']}. The model assumes returns are normally distributed and that historical "
                f"correlations are stable — both simplifications. Positions flagged as fat-tailed violate the "
                f"normality assumption; their confidence bands will understate tail risk. "
                f"This is a statistical model, not financial advice."
            )

# ──────────────────────────────────────────────
# Portfolio Outlook
# ──────────────────────────────────────────────
st.divider()
with st.expander("Portfolio Outlook", expanded=False):
    st.markdown(
        '<p class="section-intro">'
        'Projects your full portfolio value forward using correlated Monte Carlo simulation — '
        'accounting for how your positions move together, not just individually. '
        'The fan shows the range of outcomes; the metrics below it quantify the downside in standard risk terms.'
        '<br><br>'
        '• <b>Fan chart</b> — 1,000 simulated portfolio paths. The dark band covers the middle 50% of outcomes; '
        'the light band covers 80%. The further out you look, the wider the fan grows.'
        '<br>'
        '• <b>Value at Risk (VaR 95%)</b> — the minimum loss you would face in the worst 5% of scenarios. '
        'If VaR is 18%, there is a 5% chance your portfolio loses at least that much over the period.'
        '<br>'
        '• <b>Expected Shortfall (CVaR 95%)</b> — given that you are in the worst 5% of scenarios, '
        'the average loss. Always worse than VaR; this is what tail risk actually costs on average.'
        '<br>'
        '• <b>Diversification effect</b> — compares two versions of the simulation: one using the historical '
        'correlation between your positions (realistic), and one assuming they move completely independently. '
        'The difference in the 10th-percentile outcome shows whether your portfolio is well-diversified '
        'or whether your positions amplify each other\'s downside.'
        '</p>',
        unsafe_allow_html=True
    )

    if not st.session_state.portfolio:
        st.info("Add positions to run the portfolio outlook.")
    elif not _portfolio_mc:
        st.warning(
            "Not enough price history to run the portfolio outlook. "
            "Each position needs at least 1 year of data."
        )
    else:
        _po_horizon_label = st.radio(
            "Horizon", ["3 months", "6 months", "1 year"],
            index=2, horizontal=True, key="portfolio_outlook_horizon"
        )
        _po_day_idx = {"3 months": 62, "6 months": 125, "1 year": 251}[_po_horizon_label]

        _po_pct        = _portfolio_mc["percentiles"]
        _po_paths      = _portfolio_mc["portfolio_paths"]
        _po_paths_i    = _portfolio_mc["portfolio_paths_i"]
        _po_start      = _portfolio_mc["start_value"]
        _po_dates_full = list(_portfolio_mc["dates"])
        _po_dates      = _po_dates_full[:_po_day_idx + 1]

        # Slice percentile bands to chosen horizon
        _po_p10  = list(_po_pct["p10"].iloc[:_po_day_idx + 1])
        _po_p25  = list(_po_pct["p25"].iloc[:_po_day_idx + 1])
        _po_p50  = list(_po_pct["p50"].iloc[:_po_day_idx + 1])
        _po_p75  = list(_po_pct["p75"].iloc[:_po_day_idx + 1])
        _po_p90  = list(_po_pct["p90"].iloc[:_po_day_idx + 1])

        # ── Fan chart ────────────────────────────────────────────────────────
        _fig_po = go.Figure()

        _fig_po.add_trace(go.Scatter(
            x=_po_dates + list(reversed(_po_dates)),
            y=_po_p90 + list(reversed(_po_p10)),
            fill="toself", fillcolor="rgba(99,110,250,0.12)",
            line=dict(width=0), name="80% of simulations", hoverinfo="skip",
        ))
        _fig_po.add_trace(go.Scatter(
            x=_po_dates + list(reversed(_po_dates)),
            y=_po_p75 + list(reversed(_po_p25)),
            fill="toself", fillcolor="rgba(99,110,250,0.25)",
            line=dict(width=0), name="50% of simulations", hoverinfo="skip",
        ))
        _fig_po.add_trace(go.Scatter(
            x=_po_dates, y=_po_p50,
            line=dict(color="rgba(99,110,250,0.7)", width=1.5, dash="dash"),
            name="Median simulation",
        ))

        # Current value as starting reference line
        _fig_po.add_hline(
            y=_po_start,
            line=dict(color="#9CA3AF", width=1, dash="dot"),
            annotation_text=f"Current  {currency_symbol}{_po_start:,.0f}",
            annotation_position="top left",
            annotation_font_color="#9CA3AF",
        )

        _fig_po.update_layout(
            template=_PLOT_TMPL,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=40),
            yaxis=dict(tickprefix=currency_symbol, title=f"Portfolio Value ({base_currency})"),
            xaxis=dict(title="Date"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            hovermode="x unified",
        )
        st.plotly_chart(_fig_po, use_container_width=True)

        # ── Risk metrics ─────────────────────────────────────────────────────
        _po_end   = _po_paths[:, _po_day_idx]
        _po_end_i = _po_paths_i[:, _po_day_idx]
        _po_vc    = compute_var_cvar(_po_end, _po_start)

        _corr_p10  = float(sorted(_po_end)[int(len(_po_end) * 0.10)])
        _indep_p10 = float(sorted(_po_end_i)[int(len(_po_end_i) * 0.10)])
        _div_diff  = _indep_p10 - _corr_p10   # positive = correlation widens downside

        _rm1, _rm2, _rm3, _rm4 = st.columns(4)
        _rm1.metric(
            f"VaR 95% ({_po_horizon_label})",
            f"{_po_vc['var'] * 100:.1f}%",
            delta=f"{currency_symbol}{_po_vc['var_abs']:,.0f}",
            delta_color="inverse",
            help=f"In the worst 5% of simulations, the portfolio loses at least "
                 f"{_po_vc['var'] * 100:.1f}% ({currency_symbol}{_po_vc['var_abs']:,.0f}) "
                 f"over {_po_horizon_label}.",
        )
        _rm2.metric(
            f"CVaR 95% ({_po_horizon_label})",
            f"{_po_vc['cvar'] * 100:.1f}%",
            delta=f"{currency_symbol}{_po_vc['cvar_abs']:,.0f}",
            delta_color="inverse",
            help=f"Given that you are in the worst 5% of scenarios, the average loss is "
                 f"{_po_vc['cvar'] * 100:.1f}% ({currency_symbol}{_po_vc['cvar_abs']:,.0f}). "
                 f"This is always at least as bad as VaR.",
        )
        _rm3.metric(
            "p10 outcome",
            f"{currency_symbol}{_corr_p10:,.0f}",
            delta=f"{(_corr_p10 - _po_start) / _po_start * 100:+.1f}%",
            delta_color="normal",
            help="The 10th-percentile portfolio value at the chosen horizon — "
                 "9 out of 10 simulations end above this level.",
        )
        _div_label = "narrows" if _div_diff < 0 else "widens"
        _rm4.metric(
            "Diversification effect",
            f"{currency_symbol}{abs(_div_diff):,.0f}",
            delta=f"Correlation {_div_label} p10",
            delta_color="normal" if _div_diff < 0 else "inverse",
            help=(
                f"Correlated p10: {currency_symbol}{_corr_p10:,.0f}  |  "
                f"Independent p10: {currency_symbol}{_indep_p10:,.0f}. "
                + (
                    f"Your positions tend to move together, which widens the downside tail by "
                    f"{currency_symbol}{_div_diff:,.0f} compared to uncorrelated positions."
                    if _div_diff > 0 else
                    f"Your positions partially offset each other, tightening the downside tail by "
                    f"{currency_symbol}{abs(_div_diff):,.0f} compared to uncorrelated positions."
                )
            ),
        )

        # ── Outcome distribution histogram ───────────────────────────────────
        st.markdown("##### Distribution of Simulated Outcomes")
        st.markdown(
            '<p class="section-intro">'
            'Each bar represents the number of simulated portfolios that ended within that value range. '
            'A tall central peak means outcomes are tightly clustered; a wide spread means high uncertainty. '
            'The dashed lines mark the 10th percentile (left tail), median, and 90th percentile.'
            '</p>',
            unsafe_allow_html=True
        )

        _fig_hist = go.Figure()
        _fig_hist.add_trace(go.Histogram(
            x=list(_po_end),
            nbinsx=60,
            marker_color="rgba(99,110,250,0.6)",
            marker_line=dict(color="rgba(99,110,250,0.9)", width=0.5),
            name="Simulated end values",
            hovertemplate=f"{currency_symbol}%{{x:,.0f}}<br>Count: %{{y}}<extra></extra>",
        ))

        for _vline_val, _vline_label, _vline_color in [
            (_corr_p10,                           "p10",    "#DC2626"),
            (float(_po_pct["p50"].iloc[_po_day_idx]), "Median", "#2255A4"),
            (float(_po_pct["p90"].iloc[_po_day_idx]), "p90",    "#16A34A"),
            (_po_start,                           "Current", "#9CA3AF"),
        ]:
            _fig_hist.add_vline(
                x=_vline_val,
                line=dict(color=_vline_color, width=1.5, dash="dash"),
                annotation_text=_vline_label,
                annotation_position="top",
                annotation_font_color=_vline_color,
            )

        _fig_hist.update_layout(
            template=_PLOT_TMPL,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=40),
            xaxis=dict(tickprefix=currency_symbol, title=f"Portfolio Value ({base_currency})"),
            yaxis=dict(title="Number of simulations"),
            showlegend=False,
            bargap=0.02,
        )
        st.plotly_chart(_fig_hist, use_container_width=True)

        st.caption(
            f"Based on {_portfolio_mc['train_days']} trading days of calibration data. "
            f"Positions included: {', '.join(_portfolio_mc['tickers_used'])}. "
            + (
                f"Excluded (insufficient history): "
                f"{', '.join(t for t in _tickers if t not in _portfolio_mc['tickers_used'])}. "
                if any(t not in _portfolio_mc["tickers_used"] for t in _tickers) else ""
            )
            + "This is a statistical model, not financial advice."
        )

# ──────────────────────────────────────────────
# Position Outlook
# ──────────────────────────────────────────────
st.divider()
with st.expander("Position Outlook", expanded=False):
    st.markdown(
        '<p class="section-intro">'
        'Projects a single position forward using Monte Carlo simulation — useful for thinking through whether to hold or sell. '
        'Pick a position, set a time horizon, and the model generates 1,000 possible price paths based on that stock\'s historical return distribution. '
        'The fan shows the range of simulated outcomes; the dashed lines mark your purchase price(s).'
        '<br><br>'
        '• <b>Calibration window</b> — how far back the model looks to estimate the stock\'s typical daily return and volatility. '
        'A shorter window (1 year) reflects recent behaviour only — useful if the stock has changed character recently (e.g. after a major product launch or market re-rating). '
        'A longer window (5 years) smooths out short-term noise and captures multiple market regimes, including downturns. '
        'If the two windows produce very different fans, the stock\'s behaviour has changed meaningfully and either estimate carries more uncertainty.'
        '<br><br>'
        '<b>Not financial advice.</b> The probabilities shown are model outputs based on historical patterns. '
        'They do not account for news, earnings, macroeconomic changes, or any information not reflected in past prices. '
        'Use this as one input among many, not as a decision rule.'
        '</p>',
        unsafe_allow_html=True
    )

    if not st.session_state.portfolio:
        st.info("Add positions to run the outlook.")
    else:
        _ol_col1, _ol_col2, _ol_col3 = st.columns([2, 1, 1])

        with _ol_col1:
            _ol_ticker = st.selectbox(
                "Position",
                options=_tickers,
                format_func=lambda t: f"{t} — {fetch_company_name(t)}",
                key="outlook_ticker",
            )
        with _ol_col2:
            _ol_horizon_label = st.radio(
                "Horizon", ["3 months", "6 months", "1 year"], index=2, key="outlook_horizon"
            )
        with _ol_col3:
            _ol_lookback_label = st.radio(
                "Calibration window", ["1 year", "2 years", "5 years"], index=2, key="outlook_lookback"
            )

        _ol_horizon_days  = {"3 months": 63, "6 months": 126, "1 year": 252}[_ol_horizon_label]
        _ol_lookback_days = {"1 year": 252, "2 years": 504, "5 years": None}[_ol_lookback_label]

        _ol_hist = _price_data_5y.get(_ol_ticker, pd.DataFrame())
        _ol_fx   = get_fx_rate(get_ticker_currency(_ol_ticker), base_currency)

        # Current price in base currency (last available close, FX-adjusted)
        _ol_current_price = None
        _ol_close = _ol_hist["Close"].dropna() if not _ol_hist.empty and "Close" in _ol_hist.columns else pd.Series(dtype=float)
        if not _ol_close.empty:
            _ol_raw_price     = float(_ol_close.iloc[-1])
            _ol_current_price = _ol_raw_price * _ol_fx

        if _ol_current_price is None or _ol_current_price <= 0:
            st.warning(f"Could not fetch a current price for {_ol_ticker}.")
        else:
            with st.spinner(f"Simulating {_ol_ticker}…"):
                _ol_result = run_monte_carlo_ticker(
                    hist=_ol_hist,
                    current_price=_ol_current_price,
                    n_sims=1000,
                    horizon_days=_ol_horizon_days,
                    lookback_days=_ol_lookback_days,
                )

            if not _ol_result:
                st.warning(
                    f"{_ol_ticker} does not have enough price history for the selected calibration window. "
                    f"Try a shorter calibration window."
                )
            else:
                # ── Buy price lines for this ticker (base currency) ──────
                _ol_lots = df[df["Ticker"] == _ol_ticker][["Purchase", "Buy Price", "Shares"]].copy()
                _ol_wavg = None
                if not _ol_lots.empty:
                    _ol_wavg = float(
                        (_ol_lots["Buy Price"] * _ol_lots["Shares"]).sum()
                        / _ol_lots["Shares"].sum()
                    )

                # ── Fan chart ────────────────────────────────────────────
                _ol_dates = list(_ol_result["dates"])
                _ol_pct   = _ol_result["percentiles"]

                _fig_ol = go.Figure()

                # 80% band
                _fig_ol.add_trace(go.Scatter(
                    x=_ol_dates + list(reversed(_ol_dates)),
                    y=list(_ol_pct["p90"]) + list(reversed(_ol_pct["p10"])),
                    fill="toself",
                    fillcolor="rgba(99,110,250,0.12)",
                    line=dict(width=0),
                    name="80% of simulations",
                    hoverinfo="skip",
                ))

                # 50% band
                _fig_ol.add_trace(go.Scatter(
                    x=_ol_dates + list(reversed(_ol_dates)),
                    y=list(_ol_pct["p75"]) + list(reversed(_ol_pct["p25"])),
                    fill="toself",
                    fillcolor="rgba(99,110,250,0.25)",
                    line=dict(width=0),
                    name="50% of simulations",
                    hoverinfo="skip",
                ))

                # Median
                _fig_ol.add_trace(go.Scatter(
                    x=_ol_dates,
                    y=_ol_pct["p50"],
                    line=dict(color="rgba(99,110,250,0.7)", width=1.5, dash="dash"),
                    name="Median simulation",
                ))

                # Weighted average buy price line
                if _ol_wavg is not None:
                    _fig_ol.add_hline(
                        y=_ol_wavg,
                        line=dict(color="#D97706", width=1.5, dash="dot"),
                        annotation_text=f"Avg buy {currency_symbol}{_ol_wavg:,.2f}",
                        annotation_position="top left",
                        annotation_font_color="#D97706",
                    )

                # Individual lot lines (only if multiple lots)
                if len(_ol_lots) > 1:
                    for _, _lot_row in _ol_lots.iterrows():
                        _fig_ol.add_hline(
                            y=_lot_row["Buy Price"],
                            line=dict(color="#9CA3AF", width=1, dash="dot"),
                            annotation_text=f"Lot {int(_lot_row['Purchase'])}  {currency_symbol}{_lot_row['Buy Price']:,.2f}",
                            annotation_position="top right",
                            annotation_font_color="#9CA3AF",
                        )

                _fig_ol.update_layout(
                    template=_PLOT_TMPL,
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=20, b=40),
                    yaxis=dict(tickprefix=currency_symbol, title=f"Price ({base_currency})"),
                    xaxis=dict(title="Date"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                    hovermode="x unified",
                )
                st.plotly_chart(_fig_ol, use_container_width=True)

                # ── Probability metrics ──────────────────────────────────
                _ol_end = _ol_result["end_paths"]
                _m1, _m2, _m3 = st.columns(3)

                if _ol_wavg is not None:
                    _prob_above = float((_ol_end >= _ol_wavg).mean() * 100)
                    _m1.metric(
                        f"Prob. above avg buy price",
                        f"{_prob_above:.0f}%",
                        help=f"Fraction of simulations ending above your average buy price of "
                             f"{currency_symbol}{_ol_wavg:,.2f} after {_ol_horizon_label}.",
                    )

                _prob_above_current = float((_ol_end >= _ol_current_price).mean() * 100)
                _m2.metric(
                    "Prob. above today's price",
                    f"{_prob_above_current:.0f}%",
                    help=f"Fraction of simulations ending above the current price of "
                         f"{currency_symbol}{_ol_current_price:,.2f} — i.e. probability of a positive return.",
                )

                _m3.metric(
                    "Annualised volatility",
                    f"{_ol_result['sigma_annual']:.1f}%",
                    help="Annualised standard deviation of daily log-returns, used to calibrate the simulation width.",
                )

                st.markdown(
                    '<p class="section-intro">'
                    'A probability above 50% means the model\'s calibrated return rate is positive — based on historical patterns, '
                    'the stock has tended to go up over the chosen horizon. Below 50% means the opposite: '
                    'the historical drift was negative, and more simulated paths end lower than they started. '
                    'The width of the fan matters as much as the median: a highly volatile stock may show 55% probability of being above breakeven, '
                    'but the downside tail could be severe. Check the volatility figure alongside the probability.'
                    '</p>',
                    unsafe_allow_html=True
                )

                # ── Distribution flag ────────────────────────────────────
                _ol_flag = _ol_result["flag"]
                if _ol_flag.get("fat_tailed"):
                    st.warning(
                        f"**{_ol_ticker} has fat-tailed returns** (excess kurtosis: {_ol_flag['kurtosis']:.1f}). "
                        f"Extreme price moves occur more often than a normal distribution predicts. "
                        f"The confidence bands above will understate the real tail risk for this position."
                    )

                st.caption(
                    f"Calibrated on {_ol_result['train_days']} trading days of {_ol_ticker} history "
                    f"({_ol_lookback_label} window). Assumes log-normally distributed daily returns with "
                    f"μ = {_ol_result['mu_annual']:+.1f}%/yr, σ = {_ol_result['sigma_annual']:.1f}%/yr. "
                    f"This is a statistical model, not financial advice."
                )
