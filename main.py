"""Market Dashboard — NiceGUI entry point.

Replaces the Streamlit app.py with a reactive, WebSocket-driven UI that
matches the approved design_proposal.html visual concept.
"""

import asyncio
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
from src.ui.forecast import build_forecast_tab
from src.ui.income import build_income_tab
from src.ui.positions import build_positions_tab
from src.ui.health import build_health_tab
from src.ui.research import build_research_tab
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
    BORDER, BORDER_INPUT, BORDER_SUBTLE, GLOBAL_CSS,
    GREEN, RED, TEXT_FAINT,
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


_EXCHANGE_MAP = {
    "USD": ("NYSE", "America/New_York", (9, 30), (16, 0)),
    "CHF": ("SIX", "Europe/Zurich", (9, 0), (17, 30)),
    "EUR": ("XETRA", "Europe/Berlin", (9, 0), (17, 30)),
    "GBP": ("LSE", "Europe/London", (8, 0), (16, 30)),
    "SEK": ("OMX", "Europe/Stockholm", (9, 0), (17, 30)),
}


def _get_market_status(currency: str = "USD") -> tuple[str, str, str]:
    """Return (exchange_name, label, color) for the local market.

    Uses timezone-based business hours check. Does not track per-exchange
    holidays — shows 'Open' on national holidays if they fall on a weekday.
    """
    from zoneinfo import ZoneInfo

    exchange, tz_name, (open_h, open_m), (close_h, close_m) = _EXCHANGE_MAP.get(
        currency, _EXCHANGE_MAP["USD"]
    )
    now = datetime.datetime.now(ZoneInfo(tz_name))
    weekday = now.weekday()
    t = now.hour * 60 + now.minute

    if weekday >= 5:
        return exchange, "Closed", RED

    open_t = open_h * 60 + open_m
    close_t = close_h * 60 + close_m

    if open_t <= t < close_t:
        return exchange, "Open", GREEN
    return exchange, "Closed", RED


_TAB_NAMES = ["Overview", "Positions", "Portfolio Health", "Income", "Forecast", "Research", "Guide"]


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

    # On mobile, Forecast and Income are hidden — fall back to Overview.
    # (Actual hiding is CSS-only; this handles direct URL access.)
    _MOBILE_HIDDEN_TABS = {"Forecast", "Income"}

    # ── Head: CSS + PWA ────────────────────────────────────
    ui.add_head_html(GLOBAL_CSS)
    ui.add_head_html("""<script>
function switchMobileTab(el, tabName) {
  // Update active state
  document.querySelectorAll('.mobile-tab-bar .tab-item').forEach(
    t => t.classList.remove('active')
  );
  el.classList.add('active');
  // Click the hidden top tab
  const tabs = document.querySelectorAll('.q-tab');
  for (const tab of tabs) {
    if (tab.textContent.trim() === tabName) {
      tab.click();
      break;
    }
  }
}
</script>""")
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
            # Market status indicator (refreshable so it updates on currency change)
            @ui.refreshable
            def market_status_indicator():
                ex_name, label, color = _get_market_status(currency)
                ui.html(
                    f'<div style="display:flex;align-items:center;gap:5px;margin-left:8px;">'
                    f'<div style="width:7px;height:7px;border-radius:50%;background:{color};"></div>'
                    f'<span style="font-size:10px;color:{TEXT_FAINT};font-weight:500;">{ex_name} {label}</span>'
                    f'</div>'
                )
            market_status_indicator()

        # Right: currency pill + export dropdown + info
        with ui.row().classes("items-center gap-2").style("height:32px;"):

            # ── Currency segmented pill ────────────────────────
            currencies = list(CURRENCY_SYMBOLS.keys())
            pill_container = ui.element("div").style(
                f"display:flex; border:1px solid rgba(59,130,246,0.3); border-radius:8px; overflow:hidden;"
            )
            currency_buttons: dict[str, ui.button] = {}

            _pill_active = (
                "background:#3B82F6; color:white !important; border:none; padding:6px 12px;"
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

            with ui.dialog() as about_dlg, ui.card().style(
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
                    ui.button("Close", on_click=about_dlg.close).props("flat no-caps").style(
                        f"border:1px solid {BORDER_SUBTLE};border-radius:6px;color:{TEXT_MUTED};"
                        f"font-size:11px;padding:6px 16px;text-transform:none;"
                    )

            ui.button(icon="info", on_click=about_dlg.open).props(
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
                        await build_overview_tab(portfolio, currency, portfolio_color_map)
                    elif name == "Positions":
                        await build_positions_tab(portfolio, currency)
                    elif name == "Portfolio Health":
                        await build_health_tab(portfolio, currency)
                    elif name == "Income":
                        await build_income_tab(portfolio, currency, portfolio_color_map)
                    elif name == "Forecast":
                        await build_forecast_tab(portfolio, currency)
                    elif name == "Research":
                        await build_research_tab(portfolio, currency, stock_options)
                    elif name == "Guide":
                        build_guide_tab()
            finally:
                try:
                    spinner.delete()
                except (ValueError, RuntimeError):
                    pass
            _tab_built[name] = True

        # Build the initial tab
        await _build_tab(initial_tab_name)

        # Pre-build remaining tabs in the background (left to right)
        async def _prebuild_tabs():
            for name in _TAB_NAMES:
                if not _tab_built.get(name):
                    await _build_tab(name)
        asyncio.create_task(_prebuild_tabs())

        # Update browser URL when switching tabs; build tab if not yet built
        async def _on_tab_change(e):
            _active_tab["name"] = e.value
            tab_url = _tab_url(e.value)
            ui.run_javascript(f'history.replaceState(null, "", "{tab_url}")')
            if not _tab_built.get(e.value):
                await _build_tab(e.value)
        tabs.on_value_change(_on_tab_change)

        # ── Mobile bottom tab bar ──────────────────────────────────
        _MOBILE_TABS = [
            ("Overview", "Overview", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>'),
            ("Positions", "Positions", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>'),
            ("Health", "Portfolio Health", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>'),
            ("Research", "Research", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>'),
            ("Guide", "Guide", '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'),
        ]
        active_label = {
            "Overview": "Overview",
            "Positions": "Positions",
            "Portfolio Health": "Health",
            "Research": "Research",
            "Guide": "Guide",
        }.get(initial_tab_name, "Overview")

        tab_items_html = ""
        for label, tab_name, icon in _MOBILE_TABS:
            active_cls = " active" if label == active_label else ""
            tab_items_html += (
                f'<div class="tab-item{active_cls}" data-tab="{tab_name}" '
                f'onclick="switchMobileTab(this, \'{tab_name}\')">'
                f'{icon}'
                f'<span class="tab-label">{label}</span>'
                f'</div>'
            )

        ui.html(
            f'<div class="mobile-tab-bar" id="mobile-tab-bar">'
            f'{tab_items_html}'
            f'</div>'
        )

        # ── Persistent disclaimer footer ──────────────────────────
        ui.html(
            f'<div style="text-align:center;padding:12px 20px;margin-top:24px;'
            f'border-top:1px solid {BORDER};font-size:10px;color:{TEXT_FAINT};line-height:1.6;">'
            'For informational purposes only — not financial advice. '
            'Past performance does not guarantee future results. '
            'All figures are before taxes and fees. '
            'Prices may be delayed up to 15 minutes. '
            'Simulated probabilities are model outputs, not predictions.'
            '</div>'
        )

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
        # Refresh market status and sidebar
        market_status_indicator.refresh()
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
