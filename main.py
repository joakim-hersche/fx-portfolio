"""Market Dashboard — NiceGUI entry point.

Replaces the Streamlit app.py with a reactive, WebSocket-driven UI that
matches the approved design_proposal.html visual concept.
"""

import datetime
import json
import os
from urllib.parse import quote

import pandas as pd
from nicegui import app, run, ui
from nicegui.json import orjson_wrapper
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Patch NiceGUI's JSON serializer to handle pd.Timestamp (used in Plotly chart data)
_original_converter = orjson_wrapper._orjson_converter
def _patched_converter(obj):
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return _original_converter(obj)
orjson_wrapper._orjson_converter = _patched_converter

# Disable HTML sanitization globally — our ui.html() calls contain trusted
# HTML with CSS classes (kpi-row, chart-card, etc.) that must render unsanitized.
# This is safe because user-controlled input (ticker names, company names) is
# validated at the input boundary (see _is_valid_ticker) and escaped in JS
# contexts (see json.dumps in nicegui_positions.py). The HTML content itself
# is hardcoded application markup, not user-supplied.
_original_html_init = ui.html.__init__
def _unsanitized_html_init(self, content='', **kwargs):
    kwargs.setdefault('sanitize', False)
    _original_html_init(self, content, **kwargs)
ui.html.__init__ = _unsanitized_html_init

from src.charts import (
    CHART_COLORS, C_CARD_BRD, C_NEGATIVE, C_POSITIVE,
    build_comparison_chart,
)
from src.nicegui_forecast import build_diagnostics_tab, build_forecast_tab
from src.nicegui_positions import build_positions_tab
from src.nicegui_risk import build_risk_tab
from src.data_fetch import (
    fetch_company_name, fetch_price_history_range, load_stock_options,
)
from src.fx import (
    CURRENCY_SYMBOLS, get_fx_rate, get_historical_fx_rate, get_ticker_currency,
)
from src.portfolio import build_portfolio_df, fetch_buy_price
from src.stocks import TICKER_COLORS
from src.ui.guide import build_guide_tab
from src.ui.shared import load_portfolio, save_portfolio, get_storage_secret
from src.ui.sidebar import build_sidebar
from src.theme import (
    ACCENT, ACCENT_DARK, BG_CARD, BG_INPUT, BG_MAIN, BG_SIDEBAR, BG_TOPBAR,
    BORDER, BORDER_INPUT, BORDER_SUBTLE, GLOBAL_CSS,
    TEXT_DIM, TEXT_FAINT, TEXT_GHOST, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)

import logging as _logging
_log = _logging.getLogger(__name__)

# ── Static files (PWA assets) ─────────────────────────────
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.add_static_files("/static", _STATIC_DIR)

# ── Sample portfolio path ──
_SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_portfolio.json")


def _build_color_map(portfolio: dict) -> dict[str, str]:
    """Build a consistent ticker -> color mapping used across all tabs and sidebar."""
    return {
        t: TICKER_COLORS.get(t, CHART_COLORS[i % len(CHART_COLORS)])
        for i, t in enumerate(portfolio.keys())
    }



# ── PWA meta tags ──────────────────────────────────────────
_PWA_HEAD = """
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" sizes="180x180" href="/static/icon-180.png">
<link rel="apple-touch-icon" sizes="192x192" href="/static/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Market-Dashboard">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#3B82F6">
"""


_TAB_NAMES = ["Overview", "Positions", "Risk & Analytics", "Forecast", "Diagnostics", "Guide"]


def _tab_url(tab_name: str | None = None) -> str:
    """Build a navigation URL that preserves the active tab."""
    if tab_name and tab_name != "Overview":
        return f"/?tab={quote(tab_name)}"
    return "/"


@app.on_startup
async def _preload():
    app.state.stock_options = await run.io_bound(load_stock_options)
    # Pre-warm 24h caches for sample portfolio tickers so first load is fast
    await run.io_bound(_prewarm_caches)


def _prewarm_caches():
    """Pre-fetch long-cached data for sample portfolio tickers in parallel."""
    from concurrent.futures import ThreadPoolExecutor
    from src.data_fetch import (
        fetch_analytics_history, fetch_fundamentals,
        fetch_company_name, fetch_simulation_history,
    )
    try:
        with open(_SAMPLE_PATH) as f:
            sample_tickers = list(json.load(f).keys())
    except Exception:
        return
    all_tickers = sample_tickers + ["SPY"]

    def _warm(ticker):
        fetch_company_name(ticker)
        fetch_analytics_history(ticker)
        fetch_fundamentals(ticker)
        fetch_simulation_history(ticker)

    with ThreadPoolExecutor(max_workers=min(10, len(all_tickers))) as ex:
        list(ex.map(_warm, all_tickers))


@app.get('/healthz')
async def healthz():
    return {'status': 'ok'}


# TODO: Re-enable authentication before production launch.
# Set APP_PASSWORD env var to the subscription password.
#
# @ui.page("/login")
# def login_page():
#     """Simple password gate for the dashboard."""
#     ui.add_head_html(GLOBAL_CSS)
#     ui.dark_mode(True)
#
#     def try_login():
#         if password.value == os.environ.get("APP_PASSWORD", "demo"):
#             app.storage.user["authenticated"] = True
#             ui.navigate.to("/")
#         else:
#             ui.notify("Wrong password", type="negative")
#
#     with ui.card().classes("absolute-center").style(
#         f"background:{BG_CARD}; border:1px solid {BORDER}; padding:32px; min-width:320px;"
#     ):
#         with ui.row().classes("items-center gap-2").style("margin-bottom:16px;"):
#             ui.html(
#                 f'<div style="width:8px;height:8px;border-radius:50%;background:{ACCENT};"></div>'
#             )
#             ui.label("Market Dashboard").style(
#                 f"font-size:16px; font-weight:700; color:{TEXT_PRIMARY};"
#             )
#         password = ui.input(
#             "Password", password=True, password_toggle_button=True,
#         ).on("keydown.enter", try_login).classes("w-full")
#         ui.button("Login", on_click=try_login).classes("w-full").style("margin-top:8px;")


@ui.page("/")
async def index(request: Request):
    # TODO: Re-enable auth gate before production launch.
    # if not app.storage.user.get("authenticated"):
    #     return ui.navigate.to("/login")

    # ── Read query params for tab restoration ─────────────
    initial_tab_name = request.query_params.get("tab", "Overview")
    if initial_tab_name not in _TAB_NAMES:
        initial_tab_name = "Overview"

    # ── Head: CSS + PWA ────────────────────────────────────
    ui.add_head_html(GLOBAL_CSS)
    ui.add_head_html(_PWA_HEAD)

    # Force dark mode to match design concept
    ui.dark_mode(True)

    # ── Load persisted state ───────────────────────────────
    stored = load_portfolio()
    portfolio = stored.get("portfolio", {})
    currency = stored.get("currency", list(CURRENCY_SYMBOLS.keys())[0])

    # ── Load stock options (preloaded at startup, fallback to empty) ──
    stock_options = getattr(app.state, 'stock_options', None) or {}

    # Mutable ref so sidebar callbacks can read the active tab
    _active_tab = {"name": initial_tab_name}

    # ── Top bar ────────────────────────────────────────────
    with ui.header().classes("items-center justify-between px-5").style(
        f"height: 48px; background: {BG_TOPBAR}; border-bottom: 1px solid {BORDER};"
    ):
        # Left: title with accent dot
        with ui.row().classes("items-center gap-2"):
            ui.html(
                f'<div style="width:8px;height:8px;border-radius:50%;background:{ACCENT};"></div>'
            )
            ui.label("Market Dashboard").style(
                f"font-size:14px; font-weight:700; color:{TEXT_PRIMARY}; letter-spacing:0.02em;"
            )

        # Right: currency selector + export button
        with ui.row().classes("items-center gap-2").style("height:32px;"):
            async def _handle_currency_select(e):
                await _on_currency_change(e.value)

            ui.select(
                list(CURRENCY_SYMBOLS.keys()),
                value=currency,
                on_change=_handle_currency_select,
            ).props('dense borderless').style(
                f"background:{BG_INPUT}; border:1px solid {BORDER_INPUT}; border-radius:6px; color:{TEXT_MUTED}; font-size:12px; min-width:70px; height:32px; max-height:32px;"
            )
            ui.button("Export", icon="download", on_click=lambda: _export_excel(portfolio, currency)).props(
                'flat dense size=sm no-caps color=none aria-label="Export portfolio to Excel"'
            ).style(
                f"border:1px solid {BORDER_INPUT}; border-radius:6px; padding:0 12px; height:32px; color:{TEXT_MUTED} !important; font-size:12px;"
            )

            def _open_about():
                with ui.dialog() as dlg, ui.card().style(
                    f"min-width:380px; max-width:480px; background:{BG_CARD}; border:1px solid {BORDER};"
                ):
                    ui.label("Market Dashboard").style(
                        f"font-size:16px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:4px;"
                    )
                    ui.label("v2.0 — NiceGUI Edition").style(
                        f"font-size:11px; color:{TEXT_DIM}; margin-bottom:12px;"
                    )
                    ui.html(
                        f'<div style="font-size:12px; color:{TEXT_MUTED}; line-height:1.7;">'
                        '<p style="margin-bottom:10px;">A real-time stock portfolio tracker. '
                        'Add positions across major global exchanges, monitor performance in '
                        'your home currency, and run Monte Carlo simulations to project future outcomes.</p>'
                        '<p style="margin-bottom:6px;"><b style="color:#CBD5E1;">Data sources</b></p>'
                        '<ul style="margin:0 0 10px 16px; padding:0;">'
                        '<li>Stock prices, FX rates, dividends, fundamentals — <b>Yahoo Finance</b> via yfinance</li>'
                        '<li>Stock index constituents — <b>Wikipedia</b> (scraped at startup, cached 24h)</li>'
                        '</ul>'
                        '<p style="margin-bottom:6px;"><b style="color:#CBD5E1;">Disclaimer</b></p>'
                        f'<p style="font-size:12px; color:{TEXT_DIM};">All data is provided as-is for informational '
                        'purposes only. Prices may be delayed up to 15 minutes. Monte Carlo simulations '
                        'are statistical projections based on historical returns and do not constitute '
                        'financial advice. Positions flagged as fat-tailed violate the model\'s normality '
                        'assumption — confidence bands for those assets will understate real tail risk.</p>'
                        '</div>'
                    )
                    with ui.row().classes("w-full justify-end"):
                        ui.button("Close", on_click=dlg.close).props("flat")
                dlg.open()

            ui.button(icon="info", on_click=_open_about).props(
                "flat dense round size=sm color=none"
            ).style(
                f"color:{TEXT_MUTED} !important; min-width:0; width:32px; height:32px;"
            )

            # TODO: Re-enable logout button when auth is active.
            # def _logout():
            #     app.storage.user["authenticated"] = False
            #     ui.navigate.to("/login")
            #
            # ui.button(icon="logout", on_click=_logout).props(
            #     'flat dense round size=sm color=none aria-label="Logout"'
            # ).style(
            #     f"color:{TEXT_MUTED} !important; min-width:0; width:32px; height:32px;"
            # )

    # ── Precompute shared maps ────────────────────────────
    portfolio_color_map = _build_color_map(portfolio)
    ticker_values: dict[str, float] = {}

    def _compute_ticker_values():
        try:
            _sv_df = build_portfolio_df(portfolio, currency)
            if not _sv_df.empty:
                return _sv_df.groupby("Ticker")["Total Value"].sum().to_dict()
        except Exception:
            pass
        return {}

    if portfolio:
        ticker_values = await run.io_bound(_compute_ticker_values)

    # Pre-fetch company names off the UI thread
    def _fetch_all_names():
        from concurrent.futures import ThreadPoolExecutor
        tickers = list(portfolio.keys())
        if not tickers:
            return {}
        with ThreadPoolExecutor(max_workers=min(10, len(tickers))) as ex:
            return dict(zip(tickers, ex.map(fetch_company_name, tickers)))

    name_map: dict[str, str] = {}
    if portfolio:
        name_map = await run.io_bound(_fetch_all_names)

    # Shared mutable state that sidebar and tabs can both read/write
    _shared = {
        "portfolio_color_map": portfolio_color_map,
        "ticker_values": ticker_values,
        "name_map": name_map,
        "currency": currency,
        "currency_symbol": CURRENCY_SYMBOLS.get(currency, "$"),
    }

    # Forward reference for mutation callback (defined after tab panels)
    _mutation_ref = {"fn": None}

    # ── Sidebar (left drawer) ──────────────────────────────
    with ui.left_drawer(value=True, fixed=True).classes("sidebar").style(
        f"width:220px; background:{BG_SIDEBAR}; border-right:1px solid {BORDER}; padding:16px 12px;"
    ).props('width=220 :breakpoint="768"'):
        build_sidebar(portfolio, stock_options, _shared, _active_tab, on_mutation=_mutation_ref)

    # ── Main content area ──────────────────────────────────
    with ui.column().classes("w-full").style(f"background:{BG_MAIN}; min-height:100vh;"):

        # Tab bar
        tab_map: dict[str, ui.tab] = {}
        with ui.tabs().classes("w-full") as tabs:
            for name in _TAB_NAMES:
                tab_map[name] = ui.tab(name)

        initial_tab = tab_map.get(initial_tab_name, tab_map["Overview"])

        # Lazy tab rendering — only the active tab is built on load.
        # Other tabs are built on first select and cached until invalidated.
        _tab_containers: dict[str, ui.column] = {}
        _tab_built: dict[str, bool] = {}

        with ui.tab_panels(tabs, value=initial_tab).classes("w-full flex-grow") as tab_panels:
            for name in _TAB_NAMES:
                with ui.tab_panel(tab_map[name]):
                    _tab_containers[name] = ui.column().classes("w-full")
                    _tab_built[name] = False

        async def _build_tab(name: str) -> None:
            """Build (or rebuild) a single tab's content."""
            container = _tab_containers[name]
            container.clear()
            with container:
                spinner = ui.spinner('dots', size='xl').classes('self-center')
            try:
                with container:
                    if name == "Overview":
                        await _build_overview(portfolio, currency, portfolio_color_map, tabs, tab_map)
                    elif name == "Positions":
                        await build_positions_tab(portfolio, currency)
                    elif name == "Risk & Analytics":
                        await build_risk_tab(portfolio, currency)
                    elif name == "Forecast":
                        await build_forecast_tab(portfolio, currency)
                    elif name == "Diagnostics":
                        await build_diagnostics_tab(portfolio, currency)
                    elif name == "Guide":
                        build_guide_tab()
            finally:
                spinner.delete()
            _tab_built[name] = True

        # Build the initial tab
        await _build_tab(initial_tab_name)

        # Update browser URL when switching tabs; build tab if not yet built
        async def _on_tab_change(e):
            _active_tab["name"] = e.value
            tab_url = _tab_url(e.value)
            ui.run_javascript(f'history.replaceState(null, "", "{tab_url}")')
            if not _tab_built.get(e.value):
                await _build_tab(e.value)
        tabs.on_value_change(_on_tab_change)

    # ── Mutation callback — rebuild current tab in-place ──
    async def _on_portfolio_mutation():
        """Called after any portfolio change (add/remove/load/clear).
        Rebuilds sidebar values and the active tab without a full page reload."""
        nonlocal portfolio_color_map, ticker_values

        # Recompute shared state from the mutated portfolio
        portfolio_color_map = _build_color_map(portfolio)
        if portfolio:
            ticker_values = await run.io_bound(_compute_ticker_values)
            new_names = await run.io_bound(_fetch_all_names)
        else:
            ticker_values = {}
            new_names = {}

        # Update the shared dict so the sidebar sees the new values
        _shared["portfolio_color_map"] = portfolio_color_map
        _shared["ticker_values"] = ticker_values
        _shared["name_map"] = new_names

        # Invalidate all tab caches so they rebuild on next visit
        for name in _TAB_NAMES:
            _tab_built[name] = False

        # Rebuild the currently visible tab
        await _build_tab(_active_tab["name"])

    _mutation_ref["fn"] = _on_portfolio_mutation

    # ── Callbacks ──────────────────────────────────────────
    async def _on_currency_change(new_currency: str):
        nonlocal currency
        stored = load_portfolio()
        stored["currency"] = new_currency
        save_portfolio(stored)
        currency = new_currency
        _shared["currency"] = new_currency
        _shared["currency_symbol"] = CURRENCY_SYMBOLS.get(new_currency, "$")
        # Invalidate all tabs and rebuild current
        for name in _TAB_NAMES:
            _tab_built[name] = False
        await _build_tab(_active_tab["name"])


async def _build_overview(
    portfolio: dict, currency: str, portfolio_color_map: dict[str, str],
    tabs=None, tab_map: dict | None = None,
) -> None:
    """Overview tab — KPI cards + allocation chart + comparison chart."""
    currency_symbol = CURRENCY_SYMBOLS.get(currency, "$")

    if not portfolio:
        ui.html("""
            <div class="kpi-row">
                <div class="kpi-card hero">
                    <div class="kpi-label">Portfolio Value</div>
                    <div class="kpi-value">\u2014</div>
                    <div class="kpi-sub">Add positions to get started</div>
                </div>
                <div class="kpi-card hero">
                    <div class="kpi-label">Total Return</div>
                    <div class="kpi-value">\u2014</div>
                    <div class="kpi-sub">vs. total cost basis</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Today's Change</div>
                    <div class="kpi-value" style="font-size:20px;">\u2014</div>
                    <div class="kpi-sub">Since market open</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Positions</div>
                    <div class="kpi-value" style="font-size:28px;">0</div>
                    <div class="kpi-sub">Add positions in the sidebar</div>
                </div>
            </div>
        """).classes("w-full")

        # Getting Started card pointing to the Guide tab (#25)
        with ui.element("div").classes("chart-card").style("margin-top:16px;cursor:pointer;") as guide_card:
            ui.html(f'<div class="chart-title">Getting Started</div>')
            ui.html(
                f'<p style="font-size:12px;color:{TEXT_MUTED};line-height:1.6;margin-top:8px;">'
                "New here? Check the <b>Guide</b> tab for a plain-language walkthrough of every "
                "feature, or add your first position using the sidebar.</p>"
            )
        if tabs is not None and tab_map is not None:
            guide_card.on("click", lambda: tabs.set_value(tab_map["Guide"]))

        return

    # ── Build portfolio DataFrame (cached 15 min) ─────────
    notification = ui.notification("Loading overview data...", spinner=True, timeout=None)
    try:
        df = await run.io_bound(build_portfolio_df, portfolio, currency)
    except Exception:
        df = None
    finally:
        notification.dismiss()
    if df is None or df.empty:
        ui.html(
            '<div style="color:#94A3B8;font-size:13px;padding:24px;">'
            'Could not retrieve price data for any positions.</div>'
        )
        return

    # ── Shared helpers ─────────────────────────────────────
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(10, len(portfolio))) as _ex:
        _names = list(_ex.map(lambda t: (t, fetch_company_name(t)), portfolio))
    name_map = dict(_names)

    # ── KPI values ─────────────────────────────────────────
    total_value = df["Total Value"].sum()
    daily_pnl = df["Daily P&L"].sum()
    n_positions = len(portfolio)
    cost_basis = (df["Buy Price"] * df["Shares"]).sum()
    total_divs = df["Dividends"].sum()
    total_return = total_value + total_divs - cost_basis
    total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

    pnl_color = C_POSITIVE if daily_pnl >= 0 else C_NEGATIVE
    ret_color = C_POSITIVE if total_return >= 0 else C_NEGATIVE

    n_purchases = sum(len(lots) for lots in portfolio.values())
    purchases_sub = (
        f'<div class="kpi-sub sm" style="color:{TEXT_MUTED};">{n_purchases} purchases</div>'
        if n_purchases != n_positions else ""
    )

    all_dates = [
        lot["purchase_date"]
        for lots in portfolio.values() for lot in lots
        if lot.get("purchase_date")
    ]
    first_purchase = min(all_dates) if all_dates else None
    return_sub = (
        f'<div class="kpi-sub sm" style="color:{TEXT_MUTED};">Since {first_purchase}</div>'
        if first_purchase else ""
    )

    spacer_md = '<div class="kpi-sub" style="visibility:hidden;">.</div>'
    spacer_sm = '<div class="kpi-sub sm" style="visibility:hidden;">.</div>'

    def _kpi_card(label, value, border_color, line1="", line2="", hero=False, font_size=None):
        is_neutral = border_color == C_CARD_BRD
        value_color = TEXT_PRIMARY if is_neutral else border_color
        font = font_size or ("26px" if hero else "22px")
        return (
            f'<div style="background:{BG_CARD};border-radius:10px;'
            f'padding:16px 18px;border:1px solid {BORDER};'
            f'display:flex;flex-direction:column;">'
            f'<div class="kpi-label">{label}</div>'
            f'<div style="font-size:{font};font-weight:700;line-height:1.2;color:{value_color};white-space:nowrap;">{value}</div>'
            f'{line1 or spacer_md}'
            f'{line2 or spacer_sm}'
            f'</div>'
        )

    sign_ret = "+" if total_return >= 0 else ""
    sign_pnl = "+" if daily_pnl >= 0 else ""

    cache_time = datetime.datetime.now().strftime("%H:%M")

    val_int = f"{currency_symbol}{int(total_value):,}"
    val_dec = f"{total_value:.2f}".split('.')[-1]
    card_1 = _kpi_card(
        "Total Portfolio Value", val_int, C_CARD_BRD,
        line1=f'<div style="font-size:16px;font-weight:700;color:{TEXT_PRIMARY};margin-top:1px;">.{val_dec}</div>',
        line2=f'<div class="kpi-sub" style="color:{TEXT_DIM};">Updated {cache_time} \u00b7 15 min cache</div>',
        hero=True,
    )
    card_2 = _kpi_card(
        "Total Return",
        f"{sign_ret}{currency_symbol}{total_return:,.2f}",
        ret_color,
        line1=f'<span class="kpi-badge {"badge-green" if total_return >= 0 else "badge-red"}" style="margin-top:6px;">{"\u25b2" if total_return >= 0 else "\u25bc"} {sign_ret}{total_ret_pct:,.2f}%</span>',
        line2=return_sub or spacer_sm,
        hero=True,
    )
    daily_pnl_pct = (daily_pnl / (total_value - daily_pnl) * 100) if (total_value - daily_pnl) else 0.0
    card_3 = _kpi_card(
        "Today's Change",
        f"{sign_pnl}{currency_symbol}{daily_pnl:,.2f}",
        pnl_color,
        line1=f'<span class="kpi-badge {"badge-green" if daily_pnl >= 0 else "badge-red"}" style="margin-top:5px; font-size:11px;">{"\u25b2" if daily_pnl >= 0 else "\u25bc"} {sign_pnl}{daily_pnl_pct:,.2f}%</span>',
        line2=f'<div class="kpi-sub">Since yesterday\'s close</div>',
        font_size="20px",
    )
    card_4 = (
        f'<div style="background:{BG_CARD};border-radius:10px;padding:16px 18px;'
        f'border:1px solid {BORDER};">'
        f'<div class="kpi-label">Positions</div>'
        f'<div style="font-size:28px;font-weight:700;color:{TEXT_PRIMARY};line-height:1.1;">{n_positions}</div>'
        f'<div style="font-size:12px;color:{TEXT_DIM};margin-top:4px;">'
        f'{n_positions} stocks &middot; {n_purchases} lots</div>'
        f'</div>'
    )

    ui.html(f'<div class="kpi-row">{card_1}{card_2}{card_3}{card_4}</div>').classes("w-full")

    ui.html('<hr class="content-divider">').classes("w-full")

    # ── Allocation + Comparison side by side ───────────────
    with ui.element("div").classes("charts-row w-full").style("width:100%;"):
        # Allocation chart
        with ui.column().classes("chart-card").style("min-width:0;"):
            with ui.row().classes("w-full items-center justify-between").style("margin:0;"):
                ui.html('<div class="chart-title">Portfolio Allocation</div>')
                ui.html(f'<div style="font-size:10px;color:{TEXT_DIM};">by market value</div>')
            alloc_df = (
                df.groupby("Ticker")["Total Value"]
                .sum()
                .reset_index()
                .assign(**{"Portfolio Share (%)": lambda x: (x["Total Value"] / x["Total Value"].sum() * 100).round(2)})
                .sort_values("Portfolio Share (%)", ascending=False)
            )

            # Build HTML bars — scale bar height + gap dynamically based on stock count
            max_pct = alloc_df["Portfolio Share (%)"].max() if not alloc_df.empty else 100
            n_bars = len(alloc_df)
            bar_h = max(18, min(40, int(280 / max(n_bars, 1))))
            bar_gap = max(4, min(14, int(100 / max(n_bars, 1))))

            bar_rows = ""
            for _, row in alloc_df.iterrows():
                ticker = row["Ticker"]
                pct = row["Portfolio Share (%)"]
                bar_width = (pct / max_pct * 100) if max_pct > 0 else 0
                color = portfolio_color_map.get(ticker, "#3B82F6")
                bar_rows += (
                    f'<div style="display:flex;align-items:center;gap:8px;line-height:1.4;">'
                    f'<div style="width:64px;font-size:11px;font-weight:600;color:{TEXT_SECONDARY};flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{ticker}">{ticker}</div>'
                    f'<div style="flex:1;height:{bar_h}px;background:rgba(255,255,255,0.04);border-radius:4px;overflow:hidden;">'
                    f'<div style="width:{bar_width:.1f}%;height:100%;background:{color};border-radius:4px;"></div>'
                    f'</div>'
                    f'<div style="width:36px;font-size:11px;color:{TEXT_DIM};text-align:right;flex-shrink:0;">{pct:.0f}%</div>'
                    f'</div>'
                )

            # Legend
            legend_items = ""
            for _, row in alloc_df.iterrows():
                ticker = row["Ticker"]
                color = portfolio_color_map.get(ticker, "#3B82F6")
                legend_items += (
                    f'<div style="display:flex;align-items:center;gap:4px;font-size:10px;color:{TEXT_DIM};">'
                    f'<div style="width:8px;height:8px;border-radius:2px;background:{color};"></div>{ticker}</div>'
                )

            alloc_html = (
                f'<div style="display:flex;flex-direction:column;flex:1;">'
                f'<div style="display:flex;flex-direction:column;gap:{bar_gap}px;flex:1;justify-content:center;">'
                f'{bar_rows}'
                f'</div>'
                f'<div style="display:flex;flex-wrap:wrap;gap:8px;padding-top:16px;margin-top:20px;'
                f'border-top:1px solid rgba(255,255,255,0.05);">{legend_items}</div>'
                f'</div>'
            )

            ui.html(alloc_html).classes("w-full").style("flex:1;display:flex;")

        # Comparison chart
        with ui.column().classes("chart-card").style("min-width:0;"):
            await _build_comparison(portfolio, name_map, portfolio_color_map, currency)

    # Other tabs preview — clickable cards that navigate to each tab
    with ui.element("div").classes("w-full").style(
        f"margin-top:18px;padding-top:16px;border-top:1px solid {BORDER_SUBTLE};width:100%;"
    ):
        ui.html(f'<div style="font-size:10px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:{TEXT_DIM};margin-bottom:8px;">Other tabs</div>')
        with ui.element("div").classes("preview-grid w-full").style("width:100%;"):
            for _tab_name, _tab_desc in [
                ("Positions", "Positions table &middot; Price history per ticker"),
                ("Risk & Analytics", "Attribution &middot; Risk metrics &middot; Heatmap &middot; Fundamentals"),
                ("Forecast", "Portfolio outlook &middot; Position outlook &middot; Fan charts &middot; VaR/CVaR"),
                ("Diagnostics", "Monte Carlo backtest &middot; Model diagnostics &middot; QQ plots"),
                ("Guide", "Getting started &middot; Metric explanations &middot; How to read charts"),
            ]:
                card = ui.element("div").classes("preview-card").style("cursor:pointer;")
                with card:
                    ui.html(f'<div class="preview-card-label">{_tab_name}</div>')
                    ui.html(f'<div class="preview-card-text">{_tab_desc}</div>')
                if tabs is not None and tab_map is not None:
                    card.on("click", lambda _, t=_tab_name: tabs.set_value(tab_map[t]))


async def _build_comparison(
    portfolio: dict, name_map: dict, portfolio_color_map: dict, base_currency: str,
) -> None:
    """Comparison chart with time-range toggle and FX adjustment."""
    range_options = {"3M": "3mo", "6M": "6mo", "1Y": "1y", "Max": "since"}

    # Compute earliest purchase date for "Max" option
    all_dates = [
        lot["purchase_date"]
        for lots in portfolio.values() for lot in lots
        if lot.get("purchase_date")
    ]
    earliest_date = min(all_dates) if all_dates else None

    with ui.row().classes("w-full items-start justify-between").style("margin:0;"):
        ui.html('<div class="chart-title" style="margin-top:2px;">Portfolio Comparison</div>')
        with ui.row().classes("items-center gap-2"):
            range_toggle = ui.toggle(
                list(range_options.keys()), value="6M",
            ).props("dense size=sm no-caps").style("font-size:10px;")
            fx_switch = ui.switch("FX-adjusted", value=False).style(f"font-size:12px;color:{TEXT_MUTED};")

    chart_container = ui.column().classes("w-full")

    async def update_chart():
        chart_container.clear()
        range_label = range_toggle.value
        selected_range = range_options[range_label]
        fx_adjust = fx_switch.value

        def _fetch_comparison_data():
            from concurrent.futures import ThreadPoolExecutor
            from src.data_fetch import fetch_price_history_long

            def _fetch_one(t):
                try:
                    if selected_range == "since" and earliest_date:
                        hist = fetch_price_history_long(t)
                        if not hist.empty:
                            hist = hist[hist.index >= pd.Timestamp(earliest_date)]
                    else:
                        hist = fetch_price_history_range(t, selected_range if selected_range != "since" else "max")
                except Exception:
                    return t, None
                if hist.empty:
                    return t, None
                ticker_currency = get_ticker_currency(t)
                if fx_adjust and ticker_currency != base_currency:
                    fx_pair = "GBP" if ticker_currency == "GBX" else ticker_currency
                    try:
                        if selected_range == "since" and earliest_date:
                            fx_hist = fetch_price_history_long(f"{fx_pair}{base_currency}=X")
                            if not fx_hist.empty:
                                fx_hist = fx_hist[fx_hist.index >= pd.Timestamp(earliest_date)]
                        else:
                            fx_hist = fetch_price_history_range(f"{fx_pair}{base_currency}=X", selected_range if selected_range != "since" else "max")
                    except Exception:
                        return t, hist["Close"]
                    if fx_hist.empty:
                        return t, hist["Close"]
                    fx_series = fx_hist["Close"].reindex(hist.index, method="ffill")
                    if ticker_currency == "GBX":
                        fx_series = fx_series / 100
                    return t, hist["Close"] * fx_series
                else:
                    return t, hist["Close"]

            with ThreadPoolExecutor(max_workers=min(10, len(portfolio))) as ex:
                results = list(ex.map(_fetch_one, portfolio))
            return {t: series for t, series in results if series is not None}

        comparison_data = await run.io_bound(_fetch_comparison_data)

        comparison_df = pd.DataFrame(comparison_data).dropna()
        if not comparison_df.empty:
            comparison_df = comparison_df / comparison_df.iloc[0] * 100

        fig = build_comparison_chart(
            comparison_df, name_map, portfolio_color_map,
            range_label, fx_adjust, base_currency,
        )
        with chart_container:
            ui.plotly(fig).classes("w-full")

    # Debounce rapid toggles (#27)
    _debounce_timer = {"handle": None}
    async def _debounced_update(_=None):
        import asyncio
        if _debounce_timer["handle"]:
            _debounce_timer["handle"].cancel()
        loop = asyncio.get_event_loop()
        _debounce_timer["handle"] = loop.call_later(0.3, lambda: asyncio.ensure_future(update_chart()))
    range_toggle.on_value_change(_debounced_update)
    fx_switch.on_value_change(_debounced_update)

    # Initial render
    await update_chart()


async def _export_excel(portfolio: dict, currency: str) -> None:
    """Build and download the Excel report."""
    if not portfolio:
        ui.notify("No positions to export.", type="warning")
        return

    from src.data_fetch import (
        fetch_analytics_history, fetch_fundamentals, fetch_price_history_short,
        cached_run_monte_carlo_backtest, cached_run_monte_carlo_portfolio,
        cached_run_monte_carlo_ticker, fetch_simulation_history,
    )
    from src.excel_export import build_excel_report
    from src.portfolio import compute_analytics

    notification = ui.notification("Building Excel report...", spinner=True, timeout=None)

    def _build():
        base_currency = currency
        df = build_portfolio_df(portfolio, base_currency)
        if df.empty:
            return None

        name_map = {t: fetch_company_name(t) for t in portfolio}
        tickers = list(portfolio.keys())

        # Analytics
        price_data_1y = {t: fetch_analytics_history(t) for t in tickers}
        spy_data = fetch_analytics_history("SPY")
        analytics_df = compute_analytics(portfolio, price_data_1y, spy_data)

        # Monte Carlo
        price_data_5y = {t: fetch_simulation_history(t) for t in tickers}
        bt = cached_run_monte_carlo_backtest(portfolio, price_data_5y)

        start_prices_base = {}
        ticker_mc_results = {}
        for t in tickers:
            hist_5y = price_data_5y.get(t, pd.DataFrame())
            fx_mc, _ = get_fx_rate(get_ticker_currency(t), base_currency)
            close_mc = hist_5y["Close"].dropna() if not hist_5y.empty and "Close" in hist_5y.columns else pd.Series(dtype=float)
            if not close_mc.empty:
                cur_mc = float(close_mc.iloc[-1]) * fx_mc
                start_prices_base[t] = cur_mc
                ticker_mc_results[t] = cached_run_monte_carlo_ticker(
                    ticker=t, hist=hist_5y, current_price=cur_mc, horizon_days=252,
                )

        portfolio_mc = cached_run_monte_carlo_portfolio(
            portfolio=portfolio, price_data=price_data_5y,
            start_prices_base=start_prices_base, horizon_days=252,
        )

        # Fundamentals
        fund_rows = []
        for t in tickers:
            f = fetch_fundamentals(t)
            if f:
                tc = get_ticker_currency(t)
                fx_ccy = "GBP" if tc == "GBX" else tc
                if fx_ccy != base_currency:
                    fx, _ = get_fx_rate(fx_ccy, base_currency)
                    if f.get("1-Year Low"):
                        f["1-Year Low"] = round(f["1-Year Low"] * fx, 2)
                    if f.get("1-Year High"):
                        f["1-Year High"] = round(f["1-Year High"] * fx, 2)
                fund_rows.append({"Ticker": t, **f})

        # KPIs
        total_value = df["Total Value"].sum()
        daily_pnl = df["Daily P&L"].sum()
        cost_basis = (df["Buy Price"] * df["Shares"]).sum()
        total_divs = df["Dividends"].sum()
        total_return = total_value + total_divs - cost_basis
        total_ret_pct = (total_return / cost_basis * 100) if cost_basis else 0.0

        return build_excel_report(
            positions_df=df,
            analytics_df=analytics_df,
            fund_rows=fund_rows,
            price_histories={t: fetch_price_history_short(t) for t in portfolio},
            name_map=name_map,
            currency=base_currency,
            summary_kpis={
                "total_value": total_value,
                "daily_pnl": daily_pnl,
                "cost_basis": cost_basis,
                "total_divs": total_divs,
                "total_return": total_return,
                "total_ret_pct": total_ret_pct,
                "n_positions": len(portfolio),
            },
            bt_result=bt,
            ticker_mc_results=ticker_mc_results,
            portfolio_mc=portfolio_mc,
        )

    excel_bytes = await run.io_bound(_build)
    notification.dismiss()

    if excel_bytes is None:
        ui.notify("Could not build report — no price data.", type="negative")
        return

    filename = f"portfolio_{pd.Timestamp.today().strftime('%Y%m%d')}.xlsx"
    ui.download(excel_bytes, filename)
    ui.notify("Report downloaded", type="positive")


# ── Security headers middleware ────────────────────────────
class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(_SecurityHeadersMiddleware)

# ── Run ────────────────────────────────────────────────────
ui.run(
    title="Market Dashboard",
    host=os.environ.get("HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8080")),
    dark=True,
    storage_secret=get_storage_secret(),
)
