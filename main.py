"""Market Dashboard — NiceGUI entry point.

Replaces the Streamlit app.py with a reactive, WebSocket-driven UI that
matches the approved design_proposal.html visual concept.
"""

import json

from nicegui import app, ui

from src.fx import CURRENCY_SYMBOLS
from src.theme import (
    ACCENT, ACCENT_DARK, BG_MAIN, BG_SIDEBAR, BG_TOPBAR,
    BORDER, BORDER_INPUT, BORDER_SUBTLE, GLOBAL_CSS,
    TEXT_DIM, TEXT_FAINT, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    TICKER_PALETTE,
)

# ── Storage key (matches the Streamlit version's localStorage key) ──
_LS_KEY = "market_dashboard_portfolio"


def _load_portfolio() -> dict:
    """Load portfolio from browser storage, falling back to empty dict."""
    raw = app.storage.browser.get(_LS_KEY, "{}")
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _save_portfolio(data: dict) -> None:
    """Persist portfolio to browser storage."""
    app.storage.browser[_LS_KEY] = json.dumps(data)


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


@ui.page("/")
def index():
    # ── Head: CSS + PWA ────────────────────────────────────
    ui.add_head_html(GLOBAL_CSS)
    ui.add_head_html(_PWA_HEAD)

    # Force dark mode to match design concept
    ui.dark_mode(True)

    # ── Load persisted state ───────────────────────────────
    stored = _load_portfolio()
    portfolio = stored.get("portfolio", {})
    currency = stored.get("currency", list(CURRENCY_SYMBOLS.keys())[0])

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
        with ui.row().classes("items-center gap-2"):
            currency_select = ui.select(
                list(CURRENCY_SYMBOLS.keys()),
                value=currency,
                on_change=lambda e: _on_currency_change(e.value),
            ).props('dense borderless').style(
                f"background:{BG_TOPBAR}; color:{TEXT_MUTED}; font-size:12px; min-width:70px;"
            )
            ui.button("Export", icon="download", on_click=lambda: ui.notify("Export coming in Phase 3")).props(
                "flat dense size=sm"
            ).style(
                f"border:1px solid {BORDER_INPUT}; border-radius:6px; color:{TEXT_MUTED}; font-size:12px; text-transform:none;"
            )

    # ── Sidebar (left drawer) ──────────────────────────────
    with ui.left_drawer(value=True, fixed=True).classes("sidebar").style(
        f"width:220px; background:{BG_SIDEBAR}; border-right:1px solid {BORDER}; padding:16px 12px;"
    ).props('width=220 :breakpoint="0"'):
        _build_sidebar(portfolio)

    # ── Main content area ──────────────────────────────────
    with ui.column().classes("w-full").style(f"background:{BG_MAIN}; min-height:100vh;"):

        # Tab bar
        with ui.tabs().classes("w-full") as tabs:
            overview_tab = ui.tab("Overview")
            positions_tab = ui.tab("Positions")
            risk_tab = ui.tab("Risk & Analytics")
            forecast_tab = ui.tab("Forecast")
            diagnostics_tab = ui.tab("Diagnostics")

        # Tab panels
        with ui.tab_panels(tabs, value=overview_tab).classes("w-full flex-grow"):

            with ui.tab_panel(overview_tab):
                _build_overview_placeholder()

            with ui.tab_panel(positions_tab):
                _build_tab_placeholder("Positions", "Positions table and price history will render here.")

            with ui.tab_panel(risk_tab):
                _build_tab_placeholder("Risk & Analytics", "Attribution, risk metrics, correlation heatmap, and fundamentals.")

            with ui.tab_panel(forecast_tab):
                _build_tab_placeholder("Forecast", "Portfolio & position Monte Carlo outlook, fan charts, VaR/CVaR.")

            with ui.tab_panel(diagnostics_tab):
                _build_tab_placeholder("Diagnostics", "Monte Carlo backtest, model diagnostics, QQ plots.")

    # ── Callbacks ──────────────────────────────────────────
    def _on_currency_change(new_currency: str):
        stored = _load_portfolio()
        stored["currency"] = new_currency
        _save_portfolio(stored)


def _build_sidebar(portfolio: dict) -> None:
    """Build the sidebar: add-position form + positions list + import/export."""

    # ── Add Position form ──────────────────────────────────
    ui.html('<div class="sidebar-section-header">Portfolio</div>')

    market_select = ui.select(
        ["US — S&P 500", "UK — FTSE 100", "Germany — DAX", "France — CAC 40",
         "Switzerland — SMI", "Netherlands — AEX", "Spain — IBEX 35",
         "ETFs", "REITs", "Bonds", "Emerging Markets", "Crypto", "Commodities"],
        value="US — S&P 500",
        label="Market",
    ).props("dense outlined").classes("w-full").style("font-size:11px;")

    ticker_input = ui.input(label="Ticker", placeholder="e.g. AAPL").props(
        "dense outlined"
    ).classes("w-full").style("font-size:11px;")

    with ui.row().classes("w-full gap-1"):
        shares_input = ui.number(label="Shares", placeholder="10", min=0).props(
            "dense outlined"
        ).classes("flex-grow").style("font-size:11px;")
        price_input = ui.number(label="Buy Price", placeholder="150.00", min=0, step=0.01).props(
            "dense outlined"
        ).classes("flex-grow").style("font-size:11px;")

    date_input = ui.input(label="Date", placeholder="2024-01-15").props(
        "dense outlined"
    ).classes("w-full").style("font-size:11px;")

    ui.html(
        '<button class="add-btn" onclick="document.getElementById(\'add-position-btn\').click()">+ Add Position</button>'
    )
    # Hidden button to handle the click from the styled HTML button
    ui.button("add", on_click=lambda: ui.notify("Add position — full wiring in Phase 2")).props(
        'id="add-position-btn"'
    ).style("display:none;")

    # ── Divider + positions list ───────────────────────────
    ui.html('<hr class="sidebar-divider" style="margin-top:12px;">')
    ui.html('<div class="sidebar-section-header">Positions</div>')

    if portfolio:
        tickers = list(portfolio.keys())
        for i, ticker in enumerate(tickers[:4]):
            color = TICKER_PALETTE[i % len(TICKER_PALETTE)]
            lots = portfolio[ticker]
            total_shares = sum(lot.get("shares", 0) for lot in lots)
            ui.html(f"""
                <div class="position-row">
                    <div class="pos-dot" style="background:{color};"></div>
                    <div class="pos-info">
                        <div class="pos-ticker">{ticker}</div>
                        <div class="pos-name">{total_shares} shares</div>
                    </div>
                </div>
            """)
        if len(tickers) > 4:
            ui.html(
                f'<div style="font-size:10px;color:{TEXT_GHOST};padding:3px 4px;font-style:italic;">'
                f"…and {len(tickers) - 4} more positions</div>"
            )
    else:
        ui.html(
            f'<div style="font-size:11px;color:{TEXT_DIM};padding:8px 4px;">'
            "No positions yet. Add one above.</div>"
        )

    # ── Import / Export buttons ────────────────────────────
    ui.html('<hr class="sidebar-divider">')
    ui.html('<button class="sidebar-btn">⬆ Import Portfolio</button>')
    ui.html('<button class="sidebar-btn">⬇ Export Portfolio</button>')


def _build_overview_placeholder() -> None:
    """Overview tab — KPI cards placeholder + chart area placeholders."""

    # KPI row (4 cards)
    ui.html("""
        <div class="kpi-row">
            <div class="kpi-card hero">
                <div class="kpi-label">Portfolio Value</div>
                <div class="kpi-value">—</div>
                <div class="kpi-sub">Add positions to get started</div>
            </div>
            <div class="kpi-card hero">
                <div class="kpi-label">Total Return</div>
                <div class="kpi-value">—</div>
                <div class="kpi-sub">vs. total cost basis</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Today's Change</div>
                <div class="kpi-value" style="font-size:20px;">—</div>
                <div class="kpi-sub">Since market open</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Positions</div>
                <div style="font-size:28px;font-weight:700;color:#F1F5F9;line-height:1.1;">0</div>
                <div class="kpi-sub">Add positions in the sidebar</div>
            </div>
        </div>
    """)

    ui.html('<hr class="content-divider">')

    # Chart placeholders
    ui.html("""
        <div class="charts-row">
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">Portfolio Allocation</div>
                </div>
                <div style="height:180px;display:flex;align-items:center;justify-content:center;color:#475569;font-size:12px;">
                    Allocation chart — Phase 3
                </div>
            </div>
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">Portfolio Comparison</div>
                </div>
                <div style="height:180px;display:flex;align-items:center;justify-content:center;color:#475569;font-size:12px;">
                    Comparison chart — Phase 3
                </div>
            </div>
        </div>
    """)


def _build_tab_placeholder(title: str, description: str) -> None:
    """Render a placeholder card for tabs not yet ported."""
    ui.html(f"""
        <div class="chart-card" style="max-width:600px;">
            <div class="chart-header">
                <div class="chart-title">{title}</div>
            </div>
            <div style="color:#475569;font-size:12px;line-height:1.6;">
                {description}<br>
                <span style="color:#374151;font-size:11px;">Will be ported in later phases.</span>
            </div>
        </div>
    """)


# ── Run ────────────────────────────────────────────────────
ui.run(
    title="Market Dashboard",
    port=8080,
    dark=True,
    storage_secret="market-dashboard-secret",
)
