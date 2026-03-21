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

from src.charts import FALLBACK_COLORS
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
from src import db
from src.ui.auth import show_auth_ui, build_reset_complete_form
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
        t: TICKER_COLORS.get(t, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
        for i, t in enumerate(portfolio.keys())
    }

# ── PWA meta tags ──────────────────────────────────────────
_PWA_HEAD = """
<link rel="manifest" href="/static/manifest.json">
<link rel="apple-touch-icon" sizes="180x180" href="/static/icon-180.png">
<link rel="apple-touch-icon" sizes="192x192" href="/static/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Market-Dashboard">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
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
    db._init_connection()
    db.init_schema()
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
    ui.add_head_html("""<script>
// Add-to-homescreen prompt for mobile Safari/Chrome
(function() {
  var isStandalone = window.navigator.standalone || window.matchMedia('(display-mode: standalone)').matches;
  var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  var dismissed = localStorage.getItem('a2hs_dismissed');
  if (isMobile && !isStandalone && !dismissed) {
    setTimeout(function() {
      var isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent);
      var instruction = isIOS
        ? 'Tap <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="2" style="vertical-align:middle;margin:0 2px;"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg> then <b>Add to Home Screen</b>'
        : 'Tap <b>⋮</b> then <b>Add to Home Screen</b>';
      var banner = document.createElement('div');
      banner.className = 'a2hs-banner';
      var closeBtn = document.createElement('button');
      closeBtn.className = 'a2hs-close';
      closeBtn.innerHTML = '&times;';
      closeBtn.addEventListener('click', function() {
        banner.remove();
        localStorage.setItem('a2hs_dismissed', '1');
      });
      var iconDiv = document.createElement('div');
      iconDiv.style.cssText = 'width:40px;height:40px;border-radius:10px;background:#111318;border:1px solid rgba(255,255,255,0.1);display:flex;align-items:center;justify-content:center;flex-shrink:0;';
      iconDiv.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B82F6" stroke-width="1.8"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>';
      var textDiv = document.createElement('div');
      textDiv.innerHTML = '<div style="font-size:13px;font-weight:600;color:#F1F5F9;">Install Market Dashboard</div>' +
        '<div style="font-size:11px;color:#94A3B8;margin-top:2px;">' + instruction + '</div>';
      banner.appendChild(closeBtn);
      banner.appendChild(iconDiv);
      banner.appendChild(textDiv);
      document.body.appendChild(banner);
    }, 3000);
  }
})();

// Swipe hint: peek first position row on first sidebar open
function triggerSwipeHint() {
  if (localStorage.getItem('sidebar_swipe_hint')) return;
  localStorage.setItem('sidebar_swipe_hint', '1');
  setTimeout(function() {
    var firstSlide = document.querySelector('.touch-only .q-slide-item .q-slide-item__content');
    if (!firstSlide) return;
    firstSlide.style.transition = 'transform 0.4s ease-out';
    firstSlide.style.transform = 'translateX(-40px)';
    setTimeout(function() {
      firstSlide.style.transition = 'transform 0.6s ease-in-out';
      firstSlide.style.transform = 'translateX(0)';
    }, 1500);
  }, 500);
}

// Watch for sidebar open to trigger hint
(function() {
  var hintObserver = new MutationObserver(function(muts) {
    for (var i = 0; i < muts.length; i++) {
      var target = muts[i].target;
      if (target.classList && target.classList.contains('q-layout__drawer--left')
          && !target.classList.contains('q-layout__drawer--mini')) {
        // Check if drawer just became visible
        var drawer = document.querySelector('.q-drawer--left');
        if (drawer && getComputedStyle(drawer).visibility === 'visible') {
          triggerSwipeHint();
          break;
        }
      }
    }
  });
  // Start observing after a delay to let the page render
  setTimeout(function() {
    var layout = document.querySelector('.q-layout');
    if (layout) {
      hintObserver.observe(layout, {attributes: true, subtree: true, attributeFilter: ['class']});
    }
  }, 2000);
})();
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

    # Show verification banner for unverified logged-in users
    user_id = app.storage.user.get("user_id")
    if user_id:
        user_row = await run.io_bound(db.get_user_by_id, user_id)
        if user_row and not user_row["email_verified"]:
            ui.html(
                f'<div style="background:rgba(234,179,8,0.15); border:1px solid rgba(234,179,8,0.3);'
                f' border-radius:8px; padding:8px 16px; margin:8px 16px; font-size:12px;'
                f' color:#EAB308;">Verify your email to enable cross-device sync.</div>'
            )

    # Mutable ref so sidebar callbacks can read the active tab
    _active_tab = {"name": initial_tab_name}

    # Forward ref for sidebar drawer (assigned after drawer creation)
    _drawer_ref: dict = {"drawer": None}

    # ── Top bar ────────────────────────────────────────────
    with ui.header().classes("items-center justify-between px-5").style(
        f"height: 48px; background: {BG_TOPBAR}; border-bottom: 1px solid {BORDER};"
    ):
        # Left: hamburger (mobile) + title with accent dot + market status
        with ui.row().classes("items-center gap-2"):
            # Hamburger icon (visible only on mobile via CSS)
            ui.button(
                icon="menu", on_click=lambda: _drawer_ref["drawer"].toggle() if _drawer_ref["drawer"] else None
            ).props("flat dense round size=sm color=none").classes("hamburger-btn").style(
                f"color:{TEXT_MUTED} !important;min-width:0;width:36px;height:36px;"
            )
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
                    f'<span style="font-size:11px;color:{TEXT_FAINT};font-weight:500;">{ex_name} {label}</span>'
                    f'</div>'
                )
            market_status_indicator()

        # Right: currency pill + export dropdown + info
        with ui.row().classes("items-center gap-2").style("height:32px;"):

            # ── Currency segmented pill ────────────────────────
            currencies = list(CURRENCY_SYMBOLS.keys())
            pill_container = ui.element("div").classes("header-currency-pills").style(
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

            with ui.button("Export", icon="expand_more").classes("header-export-btn").props(
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

            ui.button(icon="info", on_click=about_dlg.open).classes("header-info-btn").props(
                "flat dense round size=sm color=none"
            ).style(
                f"color:{TEXT_MUTED} !important; min-width:0; width:32px; height:32px;"
            )

            # ── Auth button ───────────────────────────────
            auth_user_id = app.storage.user.get("user_id")
            auth_email = app.storage.user.get("auth_email")

            if auth_user_id:
                ui.label(auth_email or "").style(
                    f"font-size:11px; color:{TEXT_DIM}; max-width:120px;"
                    f" overflow:hidden; text-overflow:ellipsis; white-space:nowrap;"
                )
                def _logout():
                    app.storage.user.pop("user_id", None)
                    app.storage.user.pop("encryption_key", None)
                    app.storage.user.pop("auth_email", None)
                    ui.navigate.to("/")

                ui.button("Sign out", on_click=_logout).props(
                    "flat dense no-caps size=sm color=none"
                ).style(
                    f"border:1px solid {BORDER_INPUT}; border-radius:6px; padding:0 10px;"
                    f" height:28px; color:{TEXT_MUTED} !important; font-size:11px;"
                )
            else:
                async def _show_sign_in():
                    async def _on_login_success(result):
                        import base64 as _b64
                        app.storage.user["user_id"] = result["user_id"]
                        # Store as base64 string (JSON-serialisable)
                        app.storage.user["encryption_key"] = _b64.urlsafe_b64encode(
                            result["encryption_key"]
                        ).decode()
                        app.storage.user["auth_email"] = result["email"]
                        # Migrate local portfolio if needed
                        await _maybe_migrate_local_portfolio(result)
                        ui.navigate.to("/")

                    # Render auth UI in the main content area
                    for name in _TAB_NAMES:
                        _tab_built[name] = False
                    _content_container.clear()
                    with _content_container:
                        await show_auth_ui(_content_container, _on_login_success)

                ui.button("Sign in", on_click=_show_sign_in).props(
                    "flat dense no-caps size=sm color=none"
                ).style(
                    f"border:1px solid {BORDER_INPUT}; border-radius:6px; padding:0 10px;"
                    f" height:28px; color:{TEXT_MUTED} !important; font-size:11px;"
                )

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
    ).props('width=220 :breakpoint="768"') as sidebar_drawer:
        _drawer_ref["drawer"] = sidebar_drawer

        # ── Zone 1: Fixed top (mobile) — title + close ──
        with ui.element("div").classes("sidebar-zone-top touch-only"):
            with ui.row().classes("w-full items-center justify-between").style("margin-bottom:10px;"):
                ui.label("Portfolio").style(
                    f"font-size:15px;font-weight:700;color:{TEXT_PRIMARY};"
                )
                ui.button(
                    icon="close", on_click=lambda: sidebar_drawer.hide()
                ).props("flat dense round size=md color=none").style(
                    f"color:{TEXT_MUTED};min-width:44px;min-height:44px;"
                )

        # ── Zone 2: sidebar content (search + positions scroll on mobile) ──
        build_sidebar(portfolio, stock_options, _shared, _active_tab, on_mutation=_mutation_ref)

        # ── Zone 3: Pinned bottom (mobile) — actions + currency ──
        with ui.element("div").classes("sidebar-zone-bottom touch-only"):
            ui.html(
                f'<div style="font-size:10px;font-weight:700;color:{TEXT_MUTED};'
                f'letter-spacing:0.04em;text-transform:uppercase;margin-bottom:6px;">Currency</div>'
            )
            sidebar_pill = ui.element("div").classes("sidebar-currency-pills").style(
                f"display:flex;width:100%;border:1px solid rgba(59,130,246,0.3);border-radius:8px;overflow:hidden;"
            )
            with sidebar_pill:
                for i, ccy in enumerate(currencies):
                    style = _pill_active if ccy == currency else _pill_inactive
                    if i == 0:
                        style = style.replace("border-left:1px solid rgba(59,130,246,0.2); ", "")
                    ui.button(
                        ccy,
                        on_click=lambda c=ccy: _on_pill_click(c),
                    ).props("flat dense no-caps size=sm unelevated").style(style)

    # Close sidebar on mobile (it starts open for desktop, but covers everything on mobile)
    ui.run_javascript("""
        if (window.innerWidth <= 767) {
            setTimeout(function() {
                var backdrop = document.querySelector('.q-drawer__backdrop');
                if (backdrop) backdrop.click();
            }, 200);
        }
    """)

    # ── Main content area ──────────────────────────────────
    _content_container = ui.column().classes("w-full").style(f"background:{BG_MAIN}; min-height:100vh;")
    with _content_container:

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

        # ── Mobile bottom tab bar (pure NiceGUI elements) ────
        _MOBILE_TABS = [
            ("Overview", "Overview", "grid_view"),
            ("Positions", "Positions", "list"),
            ("Health", "Portfolio Health", "monitor_heart"),
            ("Income", "Income", "payments"),
            ("Forecast", "Forecast", "trending_up"),
            ("Research", "Research", "search"),
            ("Guide", "Guide", "menu_book"),
        ]
        _mobile_tab_els: dict[str, ui.element] = {}

        def _switch_mobile_tab(tab_name: str):
            tabs.set_value(tab_map[tab_name])
            for name, el in _mobile_tab_els.items():
                if name == tab_name:
                    el.classes(add="active")
                else:
                    el.classes(remove="active")
            # Close sidebar if open
            if _drawer_ref["drawer"]:
                _drawer_ref["drawer"].hide()

        with ui.element("div").classes("mobile-tab-bar"):
            for label, tab_name, icon_name in _MOBILE_TABS:
                is_active = tab_map.get(initial_tab_name) == tab_map.get(tab_name)
                with ui.element("div").classes(
                    f"tab-item{'  active' if is_active else ''}"
                ).on("click", lambda _, tn=tab_name: _switch_mobile_tab(tn)) as tab_el:
                    ui.icon(icon_name).style("font-size:20px;")
                    ui.label(label).classes("tab-label")
                    _mobile_tab_els[tab_name] = tab_el

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

    # ── Local → server portfolio migration ────────────────
    async def _maybe_migrate_local_portfolio(login_result: dict):
        """On first login, migrate local portfolio to server if server is empty."""
        from src.ui.shared import _server_load, _server_save, _load_local
        user_id = login_result["user_id"]
        enc_key = login_result["encryption_key"]

        server_data = await run.io_bound(_server_load, enc_key, user_id)
        # Read local data directly (bypass routing, which would hit server now)
        local_data = _load_local()

        has_local = bool(local_data.get("portfolio"))
        has_server = bool(server_data.get("portfolio"))

        if has_local and not has_server:
            # No conflict — migrate local → server
            await run.io_bound(_server_save, local_data, enc_key, user_id)
        elif has_local and has_server:
            # Conflict — let user choose
            with ui.dialog() as dlg, ui.card().style(
                f"min-width:360px; max-width:440px; background:{BG_CARD};"
                f" border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:20px;"
            ):
                ui.label("Portfolio conflict").style(
                    f"font-size:15px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
                )
                ui.label(
                    "This browser has a local portfolio, but your account already "
                    "has one on the server. Which do you want to keep?"
                ).style(f"font-size:12px; color:{TEXT_MUTED}; margin-bottom:16px;")
                with ui.row().classes("w-full justify-end gap-2"):
                    async def _keep_server():
                        dlg.close()
                    async def _use_local():
                        await run.io_bound(_server_save, local_data, enc_key, user_id)
                        dlg.close()
                    ui.button("Keep server", on_click=_keep_server).props(
                        "flat no-caps"
                    ).style(f"color:{TEXT_MUTED}; font-size:12px;")
                    ui.button("Use this browser's data", on_click=_use_local).props(
                        "no-caps unelevated"
                    ).style(f"background:{ACCENT}; border-radius:6px; font-size:12px;")
            dlg.open()

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

@ui.page("/reset")
async def reset_page(token: str = ""):
    """Password reset landing page — linked from reset emails."""
    if not token:
        ui.label("Invalid reset link.").style(f"color:{TEXT_MUTED}; padding:40px;")
        return
    build_reset_complete_form(token)

# ── Run ────────────────────────────────────────────────────
ui.run(
    title="Market Dashboard",
    host=os.environ.get("HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8080")),
    dark=True,
    storage_secret=get_storage_secret(),
    viewport="width=device-width, initial-scale=1, viewport-fit=cover",
)
