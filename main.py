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
# contexts (see json.dumps in src/ui/positions.py). The HTML content itself
# is hardcoded application markup, not user-supplied.
_original_html_init = ui.html.__init__
def _unsanitized_html_init(self, content='', **kwargs):
    kwargs.setdefault('sanitize', False)
    _original_html_init(self, content, **kwargs)
ui.html.__init__ = _unsanitized_html_init

from src.charts import CHART_COLORS
from src.ui.forecast import build_diagnostics_tab, build_forecast_tab
from src.ui.income import build_income_tab
from src.ui.positions import build_positions_tab
from src.ui.risk import build_risk_tab
from src.data_fetch import fetch_company_name, load_stock_options
from src.fx import CURRENCY_SYMBOLS
from src.portfolio import build_portfolio_df
from src.stocks import TICKER_COLORS
from src.ui.guide import build_guide_tab
from src.ui.overview import build_overview_tab, export_excel
from src.ui.shared import load_portfolio, save_portfolio, get_storage_secret
from src.ui.sidebar import build_sidebar
from src.theme import (
    ACCENT, BG_CARD, BG_INPUT, BG_MAIN, BG_SIDEBAR, BG_TOPBAR,
    BORDER, BORDER_INPUT, GLOBAL_CSS,
    GREEN, AMBER, RED, TEXT_FAINT,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY,
)

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
<meta name="theme-color" content="#0F1117">
"""


def _get_market_status() -> tuple[str, str]:
    """Return (label, color) for current NYSE market status.

    Uses pure timezone calculation with rule-based US holidays.
    """
    from zoneinfo import ZoneInfo

    et = datetime.datetime.now(ZoneInfo("America/New_York"))
    weekday = et.weekday()  # 0=Mon, 6=Sun
    hour, minute = et.hour, et.minute
    t = hour * 60 + minute  # minutes since midnight

    # Rule-based US market holidays
    year = et.year
    holidays: set[tuple[int, int]] = set()

    # New Year's Day — Jan 1 (if Sunday, observed Monday)
    d = datetime.date(year, 1, 1)
    if d.weekday() == 6:
        holidays.add((1, 2))
    else:
        holidays.add((1, 1))

    # MLK Day — 3rd Monday of January
    jan1 = datetime.date(year, 1, 1)
    first_mon = jan1 + datetime.timedelta(days=(7 - jan1.weekday()) % 7)
    mlk = first_mon + datetime.timedelta(weeks=2)
    holidays.add((mlk.month, mlk.day))

    # Presidents' Day — 3rd Monday of February
    feb1 = datetime.date(year, 2, 1)
    first_mon = feb1 + datetime.timedelta(days=(7 - feb1.weekday()) % 7)
    pres = first_mon + datetime.timedelta(weeks=2)
    holidays.add((pres.month, pres.day))

    # Good Friday — 2 days before Easter (anonymous algorithm)
    a = year % 19
    b, c = divmod(year, 100)
    d_v, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d_v - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month_e = (h + l - 7 * m + 114) // 31
    day_e = ((h + l - 7 * m + 114) % 31) + 1
    easter = datetime.date(year, month_e, day_e)
    good_friday = easter - datetime.timedelta(days=2)
    holidays.add((good_friday.month, good_friday.day))

    # Memorial Day — last Monday of May
    may31 = datetime.date(year, 5, 31)
    memorial = may31 - datetime.timedelta(days=(may31.weekday()) % 7)
    holidays.add((memorial.month, memorial.day))

    # Juneteenth — June 19 (observed)
    d = datetime.date(year, 6, 19)
    if d.weekday() == 5:
        holidays.add((6, 18))
    elif d.weekday() == 6:
        holidays.add((6, 20))
    else:
        holidays.add((6, 19))

    # Independence Day — July 4 (observed)
    d = datetime.date(year, 7, 4)
    if d.weekday() == 5:
        holidays.add((7, 3))
    elif d.weekday() == 6:
        holidays.add((7, 5))
    else:
        holidays.add((7, 4))

    # Labor Day — 1st Monday of September
    sep1 = datetime.date(year, 9, 1)
    labor = sep1 + datetime.timedelta(days=(7 - sep1.weekday()) % 7)
    holidays.add((labor.month, labor.day))

    # Thanksgiving — 4th Thursday of November
    nov1 = datetime.date(year, 11, 1)
    first_thu = nov1 + datetime.timedelta(days=(3 - nov1.weekday()) % 7)
    thanks = first_thu + datetime.timedelta(weeks=3)
    holidays.add((thanks.month, thanks.day))

    # Christmas — Dec 25 (observed)
    d = datetime.date(year, 12, 25)
    if d.weekday() == 5:
        holidays.add((12, 24))
    elif d.weekday() == 6:
        holidays.add((12, 26))
    else:
        holidays.add((12, 25))

    is_holiday = (et.month, et.day) in holidays

    if weekday >= 5 or is_holiday:
        return "Closed", RED

    # Pre-market: 4:00-9:30 ET
    if 240 <= t < 570:
        return "Pre-market", AMBER
    # Regular hours: 9:30-16:00 ET
    if 570 <= t < 960:
        return "Open", GREEN
    # After hours: 16:00-20:00 ET
    if 960 <= t < 1200:
        return "After hours", AMBER
    return "Closed", RED


_TAB_NAMES = ["Overview", "Positions", "Risk & Analytics", "Income", "Forecast", "Diagnostics", "Guide"]


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
        # Left: title with accent dot + market status
        with ui.row().classes("items-center gap-2"):
            ui.html(
                f'<div style="width:8px;height:8px;border-radius:50%;background:{ACCENT};"></div>'
            )
            ui.label("Market Dashboard").style(
                f"font-size:14px; font-weight:700; color:{TEXT_PRIMARY}; letter-spacing:0.02em;"
            )
            # Market status indicator
            status_label, status_color = _get_market_status()
            ui.html(
                f'<div style="display:flex;align-items:center;gap:5px;margin-left:8px;">'
                f'<div style="width:7px;height:7px;border-radius:50%;background:{status_color};"></div>'
                f'<span style="font-size:10px;color:{TEXT_FAINT};font-weight:500;">{status_label}</span>'
                f'</div>'
            )

        # Right: currency pill + export dropdown + info
        with ui.row().classes("items-center gap-2").style("height:32px;"):

            # ── Currency segmented pill ────────────────────────
            currencies = list(CURRENCY_SYMBOLS.keys())
            pill_container = ui.element("div").style(
                f"display:flex; border:1px solid rgba(59,130,246,0.3); border-radius:8px; overflow:hidden;"
            )
            currency_buttons: dict[str, ui.button] = {}

            _pill_active = (
                "background:#3B82F6; color:white; border:none; padding:6px 12px;"
                " font-size:12px; font-weight:600; cursor:pointer; min-width:0;"
            )
            _pill_inactive = (
                f"background:transparent; color:{TEXT_MUTED}; border:none;"
                " border-left:1px solid rgba(59,130,246,0.2); padding:6px 10px;"
                " font-size:12px; cursor:pointer; min-width:0;"
            )

            async def _on_pill_click(selected_currency: str):
                for ccy, btn in currency_buttons.items():
                    btn.style(_pill_active if ccy == selected_currency else _pill_inactive)
                await _on_currency_change(selected_currency)

            with pill_container:
                for i, ccy in enumerate(currencies):
                    style = _pill_active if ccy == currency else _pill_inactive
                    # First button has no left border
                    if i == 0:
                        style = style.replace("border-left:1px solid rgba(59,130,246,0.2); ", "")
                    btn = ui.button(
                        ccy,
                        on_click=lambda c=ccy: _on_pill_click(c),
                    ).props("flat dense no-caps size=sm unelevated").style(style)
                    currency_buttons[ccy] = btn

            # ── Export dropdown ────────────────────────────────
            import json as _json

            def _export_json():
                if not portfolio:
                    ui.notify("No positions to export.", type="warning")
                    return
                ui.download(_json.dumps(portfolio, indent=2).encode(), "portfolio.json")
                ui.notify("Portfolio backup downloaded.", type="positive")

            with ui.button("Export", icon="expand_more").props(
                'flat dense no-caps size=sm color=none'
            ).style(
                f"border:1px solid {BORDER_INPUT}; border-radius:6px; padding:0 12px;"
                f" height:32px; color:{TEXT_MUTED} !important; font-size:12px;"
            ):
                with ui.menu().style(
                    f"background:{BG_CARD}; border:1px solid rgba(255,255,255,0.12);"
                    f" border-radius:10px; min-width:260px;"
                ):
                    with ui.menu_item(on_click=lambda: export_excel(portfolio, currency)).style("padding:10px 14px;"):
                        with ui.row().classes("items-center gap-3 no-wrap"):
                            ui.html('<span style="font-size:16px;">📊</span>')
                            with ui.column().style("gap:1px;"):
                                ui.label("Excel Report").style(f"font-size:13px; color:{TEXT_PRIMARY}; font-weight:500;")
                                ui.label("Full workbook with charts and analytics").style(f"font-size:11px; color:{TEXT_DIM};")
                    ui.separator().style("margin:4px 14px; opacity:0.15;")
                    with ui.menu_item(on_click=_export_json).style("padding:10px 14px;"):
                        with ui.row().classes("items-center gap-3 no-wrap"):
                            ui.html('<span style="font-size:16px;">💾</span>')
                            with ui.column().style("gap:1px;"):
                                ui.label("Portfolio Backup").style(f"font-size:13px; color:{TEXT_PRIMARY}; font-weight:500;")
                                ui.label("Save positions as JSON for re-import").style(f"font-size:11px; color:{TEXT_DIM};")

            def _open_about():
                with ui.dialog() as dlg, ui.card().style(
                    f"min-width:380px; max-width:480px; background:{BG_CARD}; border:1px solid rgba(255,255,255,0.12);"
                    f" border-radius:10px; padding:20px;"
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
                    with ui.row().classes("w-full justify-end").style("margin-top:12px;"):
                        ui.button("Close", on_click=dlg.close).props("flat no-caps").style(
                            f"border:1px solid {BORDER_SUBTLE};border-radius:6px;color:{TEXT_MUTED};"
                            f"font-size:11px;padding:6px 16px;text-transform:none;"
                        )
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
        with ui.element("div").classes("tab-bar-wrapper w-full"):
            with ui.tabs().props("align=center").classes("w-full") as tabs:
                for name in _TAB_NAMES:
                    tab_map[name] = ui.tab(name)

        initial_tab = tab_map.get(initial_tab_name, tab_map["Overview"])

        # Lazy tab rendering — only the active tab is built on load.
        # Other tabs are built on first select and cached until invalidated.
        _tab_containers: dict[str, ui.column] = {}
        _tab_built: dict[str, bool] = {}

        with ui.tab_panels(tabs, value=initial_tab).classes("w-full flex-grow"):
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
                        await build_overview_tab(portfolio, currency, portfolio_color_map, tabs, tab_map)
                    elif name == "Positions":
                        await build_positions_tab(portfolio, currency)
                    elif name == "Risk & Analytics":
                        await build_risk_tab(portfolio, currency)
                    elif name == "Income":
                        await build_income_tab(portfolio, currency, portfolio_color_map)
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
        nonlocal currency, ticker_values
        stored = load_portfolio()
        stored["currency"] = new_currency
        save_portfolio(stored)
        currency = new_currency
        _shared["currency"] = new_currency
        _shared["currency_symbol"] = CURRENCY_SYMBOLS.get(new_currency, "$")
        # Recompute ticker values in the new currency
        if portfolio:
            ticker_values = await run.io_bound(_compute_ticker_values)
            _shared["ticker_values"] = ticker_values
        # Invalidate all tabs and rebuild current
        for name in _TAB_NAMES:
            _tab_built[name] = False
        await _build_tab(_active_tab["name"])
        # Refresh sidebar to show updated currency symbols and values
        if _mutation_ref.get("sidebar_refresh"):
            _mutation_ref["sidebar_refresh"]()


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
