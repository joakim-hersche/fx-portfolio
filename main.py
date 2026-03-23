"""FX Portfolio — NiceGUI entry point.

Replaces the Streamlit app.py with a reactive, WebSocket-driven UI that
matches the approved design_proposal.html visual concept.
"""

from dotenv import load_dotenv
load_dotenv()

import asyncio
import datetime
import json
import logging
import os
from urllib.parse import quote

import pandas as pd
from nicegui import app, run, ui
from nicegui.json import orjson_wrapper
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

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
from src.alert_job import start_alert_scheduler
from src.billing import is_pro, is_tab_locked, create_portal_session, is_admin, FREE_POSITION_LIMIT
from src.security_logger import log_security_event, UNAUTHORIZED_ACCESS, ADMIN_ACTION
from src.ui.paywall import render_locked_overlay, build_pricing_page
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

# Google Search Console verification
from starlette.responses import FileResponse

@app.get("/google3533e9f0fa55eb2b.html")
async def _google_verify():
    return FileResponse(os.path.join(_STATIC_DIR, "google3533e9f0fa55eb2b.html"))

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
<meta name="apple-mobile-web-app-title" content="FX Portfolio">
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
    start_alert_scheduler()


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


_log = logging.getLogger(__name__)


def _send_gift_email(to_email: str, days: int, expires) -> None:
    """Send a gift Pro notification email via Resend."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "noreply@fxportfolio.app")
    if not api_key:
        _log.warning("RESEND_API_KEY not set — skipping gift email to %s", to_email)
        return
    expires_str = expires.strftime("%B %d, %Y")
    html = (
        f"<div style='font-family:system-ui,sans-serif; max-width:480px; margin:0 auto; padding:32px;'>"
        f"<h2 style='color:#e2e8f0; margin-bottom:8px;'>You've been gifted FX Portfolio Pro!</h2>"
        f"<p style='color:#94a3b8; font-size:15px; line-height:1.6;'>"
        f"You now have full access to all Pro features for <strong>{days} days</strong>, "
        f"including Monte Carlo forecasting, dividend income tracking, and unlimited positions.</p>"
        f"<p style='color:#94a3b8; font-size:15px;'>Your Pro access expires on <strong>{expires_str}</strong>.</p>"
        f"<a href='https://fxportfolio.app' style='display:inline-block; margin-top:16px; padding:10px 24px; "
        f"background:#3b82f6; color:white; text-decoration:none; border-radius:8px; font-size:14px;'>"
        f"Open FX Portfolio</a>"
        f"</div>"
    )
    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            "from": from_email,
            "to": to_email,
            "subject": f"You've been gifted {days} days of FX Portfolio Pro",
            "html": html,
        })
    except Exception:
        _log.exception("Failed to send gift email to %s", to_email)


async def _restore_session_from_cookie(request: Request) -> None:
    """If the NiceGUI session is empty but a persistent auth_token cookie exists,
    validate it against the DB and re-establish the session."""
    if app.storage.user.get("user_id"):
        return
    raw_token = request.cookies.get("auth_token")
    if not raw_token:
        return
    try:
        from src.auth import validate_auth_token, _unwrap_key
        import base64 as _b64
        user = await run.io_bound(validate_auth_token, raw_token)
        if not user:
            return
        enc_key = user["encryption_key"]
        if not isinstance(enc_key, bytes):
            enc_key = enc_key.encode()
        encryption_key = await run.io_bound(_unwrap_key, enc_key)
        app.storage.user["user_id"] = user["id"]
        app.storage.user["encryption_key"] = _b64.urlsafe_b64encode(
            encryption_key
        ).decode()
        app.storage.user["auth_email"] = user["email"]
    except Exception:
        _log.exception("Failed to restore session from auth token")


@ui.page("/")
async def index(request: Request):
    await _restore_session_from_cookie(request)

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
      textDiv.innerHTML = '<div style="font-size:13px;font-weight:600;color:#F1F5F9;">Install FX Portfolio</div>' +
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
    try:
        stored = load_portfolio()
    except Exception:
        logging.getLogger(__name__).exception("Failed to load portfolio, falling back to empty")
        stored = {}

    # Stripe checkout return — detect via URL param, show toast, clean URL
    ui.run_javascript('''
        const params = new URLSearchParams(window.location.search);
        if (params.get("upgraded") === "1") {
            window.history.replaceState({}, "", "/");
            setTimeout(() => {
                Quasar.Notify.create({
                    message: "Welcome to Pro! All features are now unlocked.",
                    color: "positive",
                    timeout: 5000,
                    position: "top"
                });
            }, 1000);
        }
    ''')

    portfolio = stored.get("portfolio", {})
    currency = stored.get("currency", list(CURRENCY_SYMBOLS.keys())[0])

    # ── Load stock options (preloaded at startup, fallback to empty) ──
    stock_options = getattr(app.state, 'stock_options', None) or {}

    # Show verification banner for unverified logged-in users
    user_id = app.storage.user.get("user_id")
    user_row = None
    if user_id:
        try:
            user_row = await run.io_bound(db.get_user_by_id, user_id)
        except Exception:
            logging.getLogger(__name__).exception("Failed to fetch user %s", user_id)
        if user_row and not user_row["email_verified"]:
            ui.html(
                f'<div style="background:rgba(234,179,8,0.15); border:1px solid rgba(234,179,8,0.3);'
                f' border-radius:8px; padding:8px 16px; margin:8px 16px; font-size:12px;'
                f' color:#EAB308;">Verify your email to enable cross-device sync.</div>'
            )

        # Show email alert opt-in prompt (one-time, for verified users never asked)
        try:
            email_alerts_pref = await run.io_bound(db.get_email_alerts, user_id)
        except Exception:
            logging.getLogger(__name__).exception("Failed to fetch email alerts for %s", user_id)
            email_alerts_pref = None
        # Cache for the account dropdown toggle
        app.storage.user["_email_alerts_cached"] = email_alerts_pref

        if email_alerts_pref is None and user_row and user_row["email_verified"]:
            with ui.dialog() as optin_dlg, ui.card().style(
                f"min-width:360px; max-width:440px; background:{BG_CARD};"
                f" border:1px solid rgba(255,255,255,0.12); border-radius:10px; padding:24px;"
            ):
                ui.label("Stay on top of your portfolio").style(
                    f"font-size:16px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:8px;"
                )
                ui.label(
                    "We can email you when we detect concentration risk or high "
                    "correlation in your holdings. One email per day, only when "
                    "something changes."
                ).style(f"font-size:13px; color:{TEXT_MUTED}; margin-bottom:20px; line-height:1.5;")
                with ui.row().classes("w-full justify-end gap-2"):
                    async def _opt_out():
                        await run.io_bound(db.set_email_alerts, user_id, False)
                        app.storage.user["_email_alerts_cached"] = False
                        optin_dlg.close()

                    async def _opt_in():
                        await run.io_bound(db.set_email_alerts, user_id, True)
                        app.storage.user["_email_alerts_cached"] = True
                        optin_dlg.close()

                    ui.button("No thanks", on_click=_opt_out).props(
                        "flat no-caps"
                    ).style(f"color:{TEXT_MUTED}; font-size:13px;")
                    ui.button("Enable alerts", on_click=_opt_in).props(
                        "no-caps unelevated"
                    ).style(f"background:{ACCENT}; border-radius:8px; font-size:13px;")
            optin_dlg.open()

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
            ui.label("FX Portfolio").style(
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

        # Right: currency pill + info + export dropdown
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

            # ── Info button + dialog ─────────────────────────
            with ui.dialog() as about_dlg, ui.card().style(
                f"min-width:380px; max-width:480px; background:{BG_CARD}; border:1px solid rgba(255,255,255,0.12);"
                f" border-radius:10px; padding:20px;"
            ):
                ui.label("FX Portfolio").style(
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
                    async def _export_excel_gated():
                        if not is_pro(app.storage.user.get("user_id")):
                            ui.notify("Excel export is a Pro feature.", type="warning")
                            return
                        await export_excel(portfolio, currency)

                    with ui.menu_item(on_click=_export_excel_gated).style("padding:10px 14px;"):
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

            # ── Auth / account ────────────────────────────────
            auth_user_id = app.storage.user.get("user_id")
            auth_email = app.storage.user.get("auth_email")

            if auth_user_id:
                _user_tier = "Pro" if is_pro(auth_user_id) else "Free"
                _tier_color = ACCENT if _user_tier == "Pro" else TEXT_DIM

                with ui.button(icon="person").classes("header-account-btn").props(
                    "flat dense no-caps size=sm color=none"
                ).style(
                    f"border:1px solid {BORDER_INPUT}; border-radius:6px; padding:0 10px;"
                    f" height:28px; color:{TEXT_MUTED} !important; font-size:11px;"
                    f" min-width:0;"
                ):
                    with ui.menu().style(
                        f"background:{BG_CARD}; border:1px solid rgba(255,255,255,0.12);"
                        f" border-radius:10px; min-width:220px;"
                    ):
                        # Email + tier badge
                        with ui.menu_item().style("padding:8px 14px;"):
                            with ui.column().style("gap:4px;"):
                                ui.label(auth_email or "").style(
                                    f"font-size:12px; color:{TEXT_PRIMARY}; font-weight:500;"
                                    f" overflow:hidden; text-overflow:ellipsis; max-width:200px;"
                                )
                                ui.label(_user_tier).style(
                                    f"font-size:11px; font-weight:600; color:{_tier_color};"
                                    f" background:rgba(59,130,246,0.1); border-radius:4px; padding:2px 8px;"
                                    f" display:inline-block; width:fit-content;"
                                )

                        ui.separator().style("margin:4px 14px; opacity:0.15;")

                        # Email alerts toggle (Pro only)
                        with ui.menu_item().style("padding:10px 14px;"):
                            with ui.row().classes("items-center gap-3 no-wrap w-full"):
                                ui.label("Email alerts").style(
                                    f"font-size:13px; color:{TEXT_PRIMARY}; font-weight:500;"
                                )
                                if is_pro(auth_user_id):
                                    alert_pref = app.storage.user.get("_email_alerts_cached")
                                    alert_switch = ui.switch(value=bool(alert_pref)).props("dense")

                                    async def _toggle_alerts(e):
                                        await run.io_bound(db.set_email_alerts, auth_user_id, e.value)
                                        app.storage.user["_email_alerts_cached"] = e.value

                                    alert_switch.on_value_change(_toggle_alerts)
                                else:
                                    ui.label("Pro").style(
                                        f"font-size:10px; color:{TEXT_DIM}; background:rgba(255,255,255,0.06);"
                                        f" border-radius:3px; padding:1px 6px;"
                                    )

                        # Promo code (non-Pro users only)
                        if not is_pro(auth_user_id):
                            ui.separator().style("margin:4px 14px; opacity:0.15;")
                            with ui.element("div").style("padding:10px 14px;").on("click.stop", lambda: None):
                                promo_col = ui.column().classes("w-full").style("gap:6px;")
                                promo_input = None

                                def _show_promo():
                                    nonlocal promo_input
                                    promo_col.clear()
                                    with promo_col:
                                        with ui.row().classes("items-center gap-2 w-full"):
                                            promo_input = ui.input("Code").props(
                                                "outlined dense"
                                            ).style(
                                                f"flex:1; background:{BG_INPUT};"
                                            )
                                            async def _apply():
                                                from src.billing import apply_promo_code
                                                result = await run.io_bound(
                                                    apply_promo_code, auth_user_id, promo_input.value
                                                )
                                                if result == "ok":
                                                    ui.notify("Pro activated for 30 days!", type="positive")
                                                    ui.navigate.to("/")
                                                elif result == "already_used":
                                                    ui.notify("Promo code already used", type="warning")
                                                else:
                                                    ui.notify("Invalid code", type="negative")

                                            ui.button("Apply", on_click=_apply).props(
                                                "no-caps unelevated dense size=sm"
                                            ).style(
                                                f"background:{ACCENT}; border-radius:6px; font-size:11px;"
                                            )

                                with promo_col:
                                    ui.label("Have a promo code?").style(
                                        f"font-size:12px; color:{ACCENT}; cursor:pointer;"
                                        f" text-decoration:underline;"
                                    ).on("click", _show_promo)

                        # Manage subscription (Pro with Stripe only)
                        _fresh_user = db.get_user_by_id(auth_user_id) or {}
                        _stripe_cust = _fresh_user.get("stripe_customer_id")
                        if is_pro(auth_user_id) and _stripe_cust:
                            async def _manage_sub():
                                url = await run.io_bound(create_portal_session, _stripe_cust)
                                ui.navigate.to(url, new_tab=False)

                            with ui.menu_item(on_click=_manage_sub).style("padding:10px 14px;"):
                                ui.label("Manage subscription").style(
                                    f"font-size:13px; color:{TEXT_PRIMARY};"
                                )

                        ui.separator().style("margin:4px 14px; opacity:0.15;")

                        # Sign out
                        async def _logout():
                            uid = app.storage.user.get("user_id")
                            if uid:
                                try:
                                    from src.auth import delete_user_auth_tokens
                                    await run.io_bound(delete_user_auth_tokens, uid)
                                except Exception:
                                    pass
                            app.storage.user.pop("user_id", None)
                            app.storage.user.pop("encryption_key", None)
                            app.storage.user.pop("auth_email", None)
                            app.storage.user.pop("_email_alerts_cached", None)
                            ui.run_javascript(
                                "document.cookie = 'auth_token=; path=/; max-age=0';"
                            )
                            ui.navigate.to("/")

                        with ui.menu_item(on_click=_logout).style("padding:10px 14px;"):
                            ui.label("Sign out").style(
                                f"font-size:13px; color:{TEXT_PRIMARY};"
                            )
            else:
                async def _show_sign_in():
                    async def _on_login_success(result):
                        import base64 as _b64
                        app.storage.user["user_id"] = result["user_id"]
                        app.storage.user["encryption_key"] = _b64.urlsafe_b64encode(
                            result["encryption_key"]
                        ).decode()
                        app.storage.user["auth_email"] = result["email"]
                        # Apply pending promo code from signup
                        _pending = app.storage.user.pop("_pending_promo", None)
                        if _pending:
                            from src.billing import apply_promo_code
                            await run.io_bound(apply_promo_code, result["user_id"], _pending)
                        try:
                            await _maybe_migrate_local_portfolio(result)
                        except Exception:
                            logging.getLogger(__name__).exception(
                                "Portfolio migration failed for %s", result["user_id"]
                            )
                        # Create persistent auth token so login survives server restarts
                        try:
                            from src.auth import create_auth_token
                            raw_token = await run.io_bound(
                                create_auth_token, result["user_id"]
                            )
                            ui.run_javascript(
                                f"document.cookie = 'auth_token={raw_token};"
                                f" path=/; max-age={30 * 86400}; SameSite=Lax';"
                            )
                        except Exception:
                            logging.getLogger(__name__).exception("Failed to create auth token")
                        ui.navigate.to("/")

                    for name in _TAB_NAMES:
                        _tab_built[name] = False
                    _content_container.clear()
                    with _content_container:
                        await show_auth_ui(_content_container, _on_login_success)

                # Auto-open sign-in if redirected from pricing
                ui.run_javascript('''
                    const params = new URLSearchParams(window.location.search);
                    if (params.get("signin") === "1") {
                        window.history.replaceState({}, "", "/");
                        document.querySelector(".header-signin-btn")?.click();
                    }
                ''')

                ui.button("Sign in", icon="person_outline", on_click=_show_sign_in).classes("header-signin-btn").props(
                    "flat dense no-caps size=sm color=none"
                ).style(
                    f"border:1px solid {BORDER_INPUT}; border-radius:6px;"
                    f" color:{TEXT_MUTED} !important; font-size:12px; padding:4px 12px;"
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
    ).props(':width="$q.screen.lt.md ? $q.screen.width : 220" :breakpoint="768"') as sidebar_drawer:
        _drawer_ref["drawer"] = sidebar_drawer

        # ── Zone 1: Fixed top (mobile) — title + close + search ──
        zone_top = ui.element("div").classes("sidebar-zone-top w-full")
        with zone_top:
            with ui.row().classes("w-full items-center justify-between touch-only").style("margin-bottom:10px;"):
                ui.label("Portfolio").style(
                    f"font-size:15px;font-weight:700;color:{TEXT_PRIMARY};"
                )
                ui.button(
                    icon="close", on_click=lambda: sidebar_drawer.hide()
                ).props("flat dense round size=md color=none").style(
                    f"color:{TEXT_MUTED};min-width:44px;min-height:44px;"
                )
            # Search bar will be rendered here via search_container arg

        # ── Zone 2: Scrollable middle (visible on all devices, styled by media query) ──
        zone_mid = ui.element("div").classes("sidebar-zone-mid w-full")

        # ── Zone 3: Pinned bottom (mobile) — actions + currency ──
        zone_bottom = ui.element("div").classes("sidebar-zone-bottom touch-only")
        with zone_bottom:
            # Action buttons will be rendered here via actions_container arg
            pass

        # Build sidebar content — search goes to zone_top, actions go to zone_bottom
        # Positions and desktop elements render inline (inside zone_mid on mobile)
        with zone_mid:
            build_sidebar(
                portfolio, stock_options, _shared, _active_tab,
                on_mutation=_mutation_ref,
                search_container=zone_top,
                actions_container=zone_bottom,
            )

        # Currency pills in zone-bottom (after action buttons)
        with zone_bottom:
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

            # Feature gate — show paywall for locked tabs
            auth_uid = app.storage.user.get("user_id")
            if is_tab_locked(name) and not is_pro(auth_uid):
                container.clear()
                with container:
                    render_locked_overlay(name, currency)
                _tab_built[name] = True
                return

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


# ── Domain redirect middleware ─────────────────────────────
_CANONICAL_HOST = "fxportfolio.app"

class _DomainRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host.endswith(".fly.dev"):
            url = request.url.replace(scheme="https", hostname=_CANONICAL_HOST, port=443)
            return RedirectResponse(str(url), status_code=301)
        return await call_next(request)

app.add_middleware(_DomainRedirectMiddleware)

# ── Security headers middleware ────────────────────────────
class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://js.stripe.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self' wss: ws: https://api.stripe.com; "
            "frame-src https://js.stripe.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(_SecurityHeadersMiddleware)

# ── Global rate limit middleware ───────────────────────────
import time as _time
_global_rate: dict[str, list[float]] = {}
_GLOBAL_RATE_MAX = 120   # requests per window
_GLOBAL_RATE_WINDOW = 60  # seconds

class _GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP rate limit across all endpoints (120 req/min)."""
    async def dispatch(self, request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = _time.monotonic()
        hits = _global_rate.get(ip, [])
        hits = [t for t in hits if now - t < _GLOBAL_RATE_WINDOW]
        if len(hits) >= _GLOBAL_RATE_MAX:
            from starlette.responses import JSONResponse
            return JSONResponse({"error": "Rate limit exceeded"}, status_code=429,
                                headers={"Retry-After": str(_GLOBAL_RATE_WINDOW)})
        hits.append(now)
        _global_rate[ip] = hits
        return await call_next(request)

app.add_middleware(_GlobalRateLimitMiddleware)

@ui.page("/reset")
async def reset_page(token: str = ""):
    """Password reset landing page — linked from reset emails."""
    if not token:
        ui.label("Invalid reset link.").style(f"color:{TEXT_MUTED}; padding:40px;")
        return
    build_reset_complete_form(token)

@ui.page("/pricing")
async def pricing_page(request: Request):
    """Pricing page — Free vs Pro comparison."""
    await _restore_session_from_cookie(request)
    user_id = app.storage.user.get("user_id")
    currency = "EUR"
    if user_id:
        stored = load_portfolio()
        currency = stored.get("currency", "EUR")
    build_pricing_page(user_id, currency)

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    import stripe
    from starlette.responses import JSONResponse
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, webhook_secret)
    except (ValueError, stripe.SignatureVerificationError):
        return JSONResponse({"error": "Invalid signature"}, status_code=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        customer_id = session.get("customer")
        subscription_id = session.get("subscription")
        if user_id:
            from src.billing import handle_checkout_completed
            await run.io_bound(handle_checkout_completed, user_id, customer_id, subscription_id)

    elif event["type"] == "customer.subscription.deleted":
        customer_id = event["data"]["object"].get("customer")
        if customer_id:
            from src.billing import handle_subscription_deleted
            await run.io_bound(handle_subscription_deleted, customer_id)

    return JSONResponse({"status": "ok"})

@ui.page("/admin")
async def admin_page(request: Request):
    """Admin dashboard — user management and subscription summary."""
    await _restore_session_from_cookie(request)
    auth_email = app.storage.user.get("auth_email")
    if not is_admin(auth_email):
        log_security_event(UNAUTHORIZED_ACCESS, "HIGH", details={"email": auth_email, "path": "/admin"})
        ui.label("Access denied.").style(f"color:{TEXT_MUTED}; padding:40px;")
        return

    log_security_event(ADMIN_ACTION, "LOW", details={"email": auth_email, "action": "view_admin_dashboard"})
    users = await run.io_bound(db.get_all_users)

    with ui.column().classes("w-full").style(f"background:{BG_MAIN}; min-height:100vh; padding:24px;"):
        ui.label("Admin Dashboard").style(
            f"font-size:22px; font-weight:700; color:{TEXT_PRIMARY}; margin-bottom:20px;"
        )

        # Summary cards
        total = len(users)
        pro_count = sum(1 for u in users if u.get("tier") == "pro")
        free_count = total - pro_count
        sub_count = sum(1 for u in users if u.get("stripe_subscription_id"))

        with ui.row().classes("gap-4 flex-wrap").style("margin-bottom:24px;"):
            for label, value in [("Total users", total), ("Pro", pro_count), ("Free", free_count), ("Subscriptions", sub_count)]:
                with ui.card().style(
                    f"background:{BG_CARD}; border:1px solid rgba(255,255,255,0.08);"
                    f" border-radius:10px; padding:16px 24px; min-width:120px;"
                ):
                    ui.label(str(value)).style(f"font-size:28px; font-weight:700; color:{TEXT_PRIMARY};")
                    ui.label(label).style(f"font-size:12px; color:{TEXT_DIM};")

        # User table
        admin_emails = set(
            e.strip().lower()
            for e in os.environ.get("ADMIN_EMAILS", "").split(",")
            if e.strip()
        )
        columns = [
            {"name": "email", "label": "Email", "field": "email", "align": "left", "sortable": True},
            {"name": "tier", "label": "Tier", "field": "tier", "align": "left", "sortable": True},
            {"name": "admin", "label": "Admin", "field": "admin", "align": "left", "sortable": True},
            {"name": "created_at", "label": "Signed up", "field": "created_at", "align": "left", "sortable": True},
            {"name": "stripe_customer_id", "label": "Stripe", "field": "stripe_customer_id", "align": "left"},
            {"name": "pro_expires_at", "label": "Pro expires", "field": "pro_expires_at", "align": "left", "sortable": True},
        ]
        rows = [
            {
                "id": u["id"],
                "email": u["email"],
                "tier": u.get("tier", "free"),
                "admin": "Yes" if u["email"].lower() in admin_emails else "",
                "created_at": str(u.get("created_at") or "")[:10],
                "stripe_customer_id": u.get("stripe_customer_id") or "",
                "pro_expires_at": str(u.get("pro_expires_at") or "")[:10] if u.get("pro_expires_at") else "",
            }
            for u in users
        ]

        # Filter input
        filter_input = ui.input("Filter users...").props("outlined dense clearable").style(
            f"width:300px; background:{BG_INPUT}; margin-bottom:12px;"
        )

        table = ui.table(columns=columns, rows=rows, row_key="id").style(
            f"background:{BG_CARD}; border-radius:10px; width:100%;"
        ).props("flat bordered")

        def _filter(e):
            query = (e.value or "").lower()
            if not query:
                table.rows = rows
            else:
                table.rows = [r for r in rows if query in r["email"].lower() or query in r["tier"].lower()]
            table.update()

        filter_input.on("update:model-value", _filter)

        # Tier override
        ui.label("Tier Override").style(
            f"font-size:16px; font-weight:600; color:{TEXT_PRIMARY}; margin-top:24px; margin-bottom:8px;"
        )
        with ui.row().classes("items-end gap-3"):
            email_input = ui.input("User email").props("outlined dense").style("width:250px;")
            tier_select = ui.select(["free", "pro"], value="pro").props("outlined dense").style("width:100px;")

            async def _override_tier():
                target = await run.io_bound(db.get_user_by_email, email_input.value.strip().lower())
                if not target:
                    ui.notify("User not found.", type="warning")
                    return
                await run.io_bound(db.set_tier, target["id"], tier_select.value)
                ui.notify(f"Set {email_input.value} to {tier_select.value}.", type="positive")
                ui.navigate.to("/admin")

            ui.button("Apply", on_click=_override_tier).props("no-caps unelevated").style(
                f"background:{ACCENT}; border-radius:6px;"
            )

        # Gift free month
        ui.label("Gift Free Month").style(
            f"font-size:16px; font-weight:600; color:{TEXT_PRIMARY}; margin-top:24px; margin-bottom:8px;"
        )
        with ui.row().classes("items-end gap-3"):
            gift_email_input = ui.input("User email").props("outlined dense").style("width:250px;")
            gift_days_select = ui.select([30, 60, 90], value=30, label="Days").props("outlined dense").style("width:100px;")

            async def _gift_pro():
                from datetime import datetime, timedelta, timezone
                target = await run.io_bound(db.get_user_by_email, gift_email_input.value.strip().lower())
                if not target:
                    ui.notify("User not found.", type="warning")
                    return
                expires = datetime.now(timezone.utc) + timedelta(days=gift_days_select.value)
                await run.io_bound(db.set_tier, target["id"], "pro")
                await run.io_bound(db.set_pro_expires, target["id"], expires)
                log_security_event(ADMIN_ACTION, "MEDIUM", details={
                    "admin_email": app.storage.user.get("auth_email"),
                    "action": "gift_pro",
                    "target_user_id": target["id"],
                    "target_email": gift_email_input.value.strip().lower(),
                    "days": gift_days_select.value,
                })
                # Send gift notification email
                await run.io_bound(
                    _send_gift_email,
                    gift_email_input.value.strip().lower(),
                    gift_days_select.value,
                    expires,
                )
                ui.notify(f"Gifted {gift_days_select.value} days Pro to {gift_email_input.value}.", type="positive")
                ui.navigate.to("/admin")

            ui.button("Gift", on_click=_gift_pro).props("no-caps unelevated").style(
                f"background:{ACCENT}; border-radius:6px;"
            )

        # Admin management
        ui.label("Admin Access").style(
            f"font-size:16px; font-weight:600; color:{TEXT_PRIMARY}; margin-top:24px; margin-bottom:8px;"
        )
        ui.label(
            "Admin emails are stored in the ADMIN_EMAILS environment variable. "
            "Add or remove emails below — changes take effect on next deploy."
        ).style(f"font-size:12px; color:{TEXT_DIM}; margin-bottom:8px;")

        current_admins = os.environ.get("ADMIN_EMAILS", "")
        admin_display = ui.label(f"Current: {current_admins or 'none'}").style(
            f"font-size:13px; color:{TEXT_MUTED}; margin-bottom:8px;"
        )

        with ui.row().classes("items-end gap-3"):
            admin_email_input = ui.input("Email").props("outlined dense").style("width:250px;")

            async def _add_admin():
                new_email = admin_email_input.value.strip().lower()
                if not new_email:
                    return
                current = os.environ.get("ADMIN_EMAILS", "")
                existing = [e.strip() for e in current.split(",") if e.strip()]
                if new_email in [e.lower() for e in existing]:
                    ui.notify("Already an admin.", type="info")
                    return
                existing.append(new_email)
                os.environ["ADMIN_EMAILS"] = ",".join(existing)
                admin_display.text = f"Current: {os.environ['ADMIN_EMAILS']}"
                ui.notify(
                    f"Added {new_email} as admin for this session. "
                    f"Run: fly secrets set ADMIN_EMAILS=\"{os.environ['ADMIN_EMAILS']}\" to persist.",
                    type="positive",
                )

            async def _remove_admin():
                rm_email = admin_email_input.value.strip().lower()
                if not rm_email:
                    return
                current = os.environ.get("ADMIN_EMAILS", "")
                existing = [e.strip() for e in current.split(",") if e.strip()]
                if len(existing) <= 1:
                    ui.notify("Cannot remove the last admin.", type="warning")
                    return
                if rm_email == auth_email.lower():
                    ui.notify("Cannot remove yourself.", type="warning")
                    return
                updated = [e for e in existing if e.lower() != rm_email]
                if len(updated) == len(existing):
                    ui.notify("Not an admin.", type="info")
                    return
                os.environ["ADMIN_EMAILS"] = ",".join(updated)
                admin_display.text = f"Current: {os.environ['ADMIN_EMAILS']}"
                ui.notify(
                    f"Removed {rm_email}. "
                    f"Run: fly secrets set ADMIN_EMAILS=\"{os.environ['ADMIN_EMAILS']}\" to persist.",
                    type="positive",
                )

            ui.button("Add", on_click=_add_admin).props("no-caps unelevated dense").style(
                f"background:{ACCENT}; border-radius:6px;"
            )
            ui.button("Remove", on_click=_remove_admin).props("no-caps unelevated dense").style(
                f"background:#EF4444; border-radius:6px;"
            )

# ── Run ────────────────────────────────────────────────────
ui.run(
    title="FX Portfolio",
    host=os.environ.get("HOST", "0.0.0.0"),
    port=int(os.environ.get("PORT", "8080")),
    dark=True,
    storage_secret=get_storage_secret(),
    reconnect_timeout=10.0,
    viewport="width=device-width, initial-scale=1, viewport-fit=cover",
)
