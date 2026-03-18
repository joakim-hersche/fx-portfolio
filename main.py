"""Market Dashboard — NiceGUI entry point.

Replaces the Streamlit app.py with a reactive, WebSocket-driven UI that
matches the approved design_proposal.html visual concept.
"""

import json
import os

import pandas as pd
from nicegui import app, ui

from src.data_fetch import load_stock_options
from src.fx import (
    CURRENCY_SYMBOLS, get_fx_rate, get_historical_fx_rate, get_ticker_currency,
)
from src.portfolio import fetch_buy_price
from src.theme import (
    ACCENT, ACCENT_DARK, BG_MAIN, BG_SIDEBAR, BG_TOPBAR,
    BORDER, BORDER_INPUT, BORDER_SUBTLE, GLOBAL_CSS,
    TEXT_DIM, TEXT_FAINT, TEXT_GHOST, TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    TICKER_PALETTE,
)

# ── Storage key (matches the Streamlit version's localStorage key) ──
_LS_KEY = "market_dashboard_portfolio"

# ── Sample portfolio path ──
_SAMPLE_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_portfolio.json")

# ── Market names list (matches load_stock_options keys) ──
_MARKETS = [
    "US — S&P 500", "UK — FTSE 100", "Germany — DAX", "France — CAC 40",
    "Switzerland — SMI", "Netherlands — AEX", "Spain — IBEX 35",
    "ETFs", "REITs", "Bonds", "Emerging Markets", "Crypto", "Commodities",
]

_ALT_ASSETS = {"Crypto", "Commodities"}


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

    # ── Load stock options (cached 24h) ────────────────────
    stock_options = load_stock_options()

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
            ui.select(
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
        _build_sidebar(portfolio, stock_options, currency)

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


def _build_sidebar(portfolio: dict, stock_options: dict, currency: str) -> None:
    """Build the sidebar: add-position form + positions list + import/export."""

    # ── Add Position form ──────────────────────────────────
    ui.html('<div class="sidebar-section-header">Portfolio</div>')

    # Market select
    market_select = ui.select(
        _MARKETS,
        value=_MARKETS[0],
        label="Market",
    ).props("dense outlined").classes("w-full").style("font-size:11px;")

    # Ticker select (populated from stock options)
    initial_options = stock_options.get(_MARKETS[0], {})
    ticker_select = ui.select(
        options=initial_options,
        label="Ticker",
        with_input=True,
    ).props("dense outlined use-input").classes("w-full").style("font-size:11px;")

    def on_market_change(e):
        market = e.value
        opts = stock_options.get(market, {})
        ticker_select.options = opts
        ticker_select.value = None
        ticker_select.update()
        is_alt = market in _ALT_ASSETS
        # Update shares/amount label
        shares_input.props(f'label="{"Amount (" + currency + ")" if is_alt else "Shares"}"')
        shares_input.update()
        # Toggle date vs price visibility
        _update_price_date_visibility(is_alt, manual_checkbox.value if not is_alt else False)

    market_select.on_value_change(on_market_change)

    # Shares / Amount + Buy Price row
    with ui.row().classes("w-full gap-1"):
        shares_input = ui.number(label="Shares", placeholder="10", min=0).props(
            "dense outlined"
        ).classes("flex-grow").style("font-size:11px;")
        price_input = ui.number(label="Buy Price", placeholder="150.00", min=0, step=0.01).props(
            "dense outlined"
        ).classes("flex-grow").style("font-size:11px; display:none;")

    # Date input with date picker popup
    date_input = ui.input(label="Date", placeholder="2024-01-15").props(
        "dense outlined"
    ).classes("w-full").style("font-size:11px;")
    with date_input:
        with ui.menu().props("no-parent-event") as date_menu:
            with ui.date().bind_value(date_input) as date_picker:
                with ui.row().classes("justify-end"):
                    ui.button("Close", on_click=date_menu.close).props("flat")
        with date_input.add_slot("append"):
            ui.icon("edit_calendar").on("click", date_menu.open).classes("cursor-pointer")

    # Manual price checkbox (hidden for alt assets)
    manual_checkbox = ui.checkbox("Enter price manually", value=False).style(
        "font-size:10px;"
    )

    def _update_price_date_visibility(is_alt: bool, is_manual: bool):
        if is_alt:
            date_input.style("font-size:11px;")  # show date (optional for alt)
            price_input.style("font-size:11px; display:none;")
            manual_checkbox.set_visibility(False)
        elif is_manual:
            date_input.style("font-size:11px; display:none;")
            price_input.style("font-size:11px;")
            manual_checkbox.set_visibility(True)
        else:
            date_input.style("font-size:11px;")
            price_input.style("font-size:11px; display:none;")
            manual_checkbox.set_visibility(True)

    def on_manual_change(e):
        is_alt = market_select.value in _ALT_ASSETS
        _update_price_date_visibility(is_alt, e.value)

    manual_checkbox.on_value_change(on_manual_change)

    # ── Add Position button ──────────────────────────────
    def on_add_position():
        market = market_select.value
        is_alt = market in _ALT_ASSETS
        ticker = ticker_select.value
        manual = manual_checkbox.value and not is_alt

        # Validation
        if not ticker:
            ui.notify("Please select a stock.", type="warning")
            return
        if not is_alt and (shares_input.value is None or shares_input.value <= 0):
            ui.notify("Please enter the number of shares.", type="warning")
            return
        if is_alt and (shares_input.value is None or shares_input.value <= 0):
            ui.notify("Please enter the amount.", type="warning")
            return
        if not is_alt and not manual and not date_input.value:
            ui.notify("Please select a purchase date or enter a price manually.", type="warning")
            return
        if manual and (price_input.value is None or price_input.value <= 0):
            ui.notify("Please enter a valid buy price.", type="warning")
            return

        # Determine buy price and FX rate
        ticker_currency = get_ticker_currency(ticker)
        base_currency = currency
        purchase_date = date_input.value

        if manual:
            buy_price = price_input.value
            buy_fx_rate = 1.0
        elif purchase_date:
            result = fetch_buy_price(ticker, str(purchase_date))
            if result is None:
                ui.notify("No price data found for that date. Try a different date.", type="negative")
                return
            buy_price, actual_date = result
            if actual_date != str(purchase_date):
                ui.notify(
                    f"{purchase_date} was not a trading day. Using price from {actual_date}.",
                    type="info",
                )
            buy_fx_rate = get_historical_fx_rate(ticker_currency, base_currency, str(purchase_date))
        else:
            # Alt asset without date — use today
            purchase_date = str(pd.Timestamp.today().date())
            result = fetch_buy_price(ticker, purchase_date)
            buy_price = result[0] if result else None
            if buy_price is None:
                ui.notify("Could not fetch current price.", type="negative")
                return
            buy_fx_rate = get_fx_rate(ticker_currency, base_currency)

        # Compute shares for alt assets
        if is_alt:
            shares = round(shares_input.value / buy_price, 6)
        else:
            shares = shares_input.value

        lot = {
            "shares": shares,
            "buy_price": buy_price,
            "buy_fx_rate": buy_fx_rate,
            "purchase_date": str(purchase_date) if purchase_date else None,
            "manual_price": manual,
        }

        # Mutate portfolio and save
        portfolio.setdefault(ticker, []).append(lot)
        stored = _load_portfolio()
        stored["portfolio"] = portfolio
        _save_portfolio(stored)

        sym = CURRENCY_SYMBOLS.get(base_currency, "$")
        ui.notify(f"Added {shares:g} units of {ticker} at {sym}{buy_price:,.2f}", type="positive")

        # Reset form
        ticker_select.value = None
        shares_input.value = None
        price_input.value = None
        date_input.value = ""

        # Refresh positions list
        positions_list.refresh()

    ui.html(
        '<button class="add-btn" onclick="document.getElementById(\'add-position-btn\').click()">+ Add Position</button>'
    )
    ui.button("add", on_click=on_add_position).props(
        'id="add-position-btn"'
    ).style("display:none;")

    # ── Divider + positions list ───────────────────────────
    ui.html('<hr class="sidebar-divider" style="margin-top:12px;">')
    ui.html('<div class="sidebar-section-header">Positions</div>')

    @ui.refreshable
    def positions_list():
        if portfolio:
            tickers = list(portfolio.keys())
            for i, ticker in enumerate(tickers):
                color = TICKER_PALETTE[i % len(TICKER_PALETTE)]
                lots = portfolio[ticker]
                total_shares = sum(lot.get("shares", 0) for lot in lots)
                with ui.row().classes("w-full items-center").style(
                    "padding:3px 4px; gap:6px;"
                ):
                    ui.html(
                        f'<div style="width:6px;height:6px;border-radius:50%;background:{color};flex-shrink:0;"></div>'
                    )
                    with ui.column().classes("flex-grow").style("gap:0;"):
                        ui.label(ticker).style(
                            f"font-size:11px;font-weight:600;color:{TEXT_PRIMARY};line-height:1.2;"
                        )
                        ui.label(f"{total_shares:g} shares").style(
                            f"font-size:9px;color:{TEXT_FAINT};line-height:1.2;"
                        )
                    # Remove button
                    _t = ticker  # capture for closure
                    ui.button(
                        icon="close",
                        on_click=lambda _, t=_t: _confirm_remove(t),
                    ).props("flat dense round size=xs").style(
                        f"color:{TEXT_DIM}; min-width:0; padding:2px;"
                    )
        else:
            ui.html(
                f'<div style="font-size:11px;color:{TEXT_DIM};padding:8px 4px;">'
                "No positions yet. Add one above.</div>"
            )

    positions_list()

    # ── Confirmation dialog for remove ─────────────────────
    def _confirm_remove(ticker: str):
        lots = portfolio.get(ticker, [])
        with ui.dialog() as dialog, ui.card().style("min-width:260px;"):
            ui.label(f"Remove {ticker}?").style("font-weight:600;font-size:14px;")
            if len(lots) == 1:
                ui.label("This will remove the position. This cannot be undone.").style("font-size:12px;")
            else:
                ui.label(f"This will remove all {len(lots)} lots. This cannot be undone.").style("font-size:12px;")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                def do_remove(d=dialog, t=ticker):
                    del portfolio[t]
                    stored = _load_portfolio()
                    stored["portfolio"] = portfolio
                    _save_portfolio(stored)
                    positions_list.refresh()
                    d.close()
                    ui.notify(f"Removed {t}", type="info")
                ui.button("Remove", on_click=do_remove, color="red").props("flat")
        dialog.open()

    # ── Import / Export / Sample / Clear ──────────────────
    ui.html('<hr class="sidebar-divider">')

    # Import
    def on_import_upload(e):
        try:
            content = e.content.read()
            data = json.loads(content)
            # Validate structure
            valid = (
                isinstance(data, dict)
                and all(
                    isinstance(t, str)
                    and isinstance(lots, list)
                    and all(
                        isinstance(lot, dict) and {"shares", "buy_price", "purchase_date"}.issubset(lot.keys())
                        for lot in lots
                    )
                    for t, lots in data.items()
                )
            )
            if not valid:
                ui.notify("Invalid portfolio file.", type="negative")
                return
            portfolio.clear()
            portfolio.update(data)
            stored = _load_portfolio()
            stored["portfolio"] = portfolio
            _save_portfolio(stored)
            positions_list.refresh()
            ui.notify("Portfolio imported successfully.", type="positive")
        except Exception:
            ui.notify("Could not read the file.", type="negative")

    ui.upload(
        label="Import Portfolio",
        auto_upload=True,
        on_upload=on_import_upload,
    ).props('accept=".json" flat dense').classes("w-full").style(
        "font-size:10px; max-height:32px;"
    )

    # Export
    def on_export():
        if not portfolio:
            ui.notify("No positions to export.", type="warning")
            return
        content = json.dumps(portfolio, indent=2)
        ui.download(content.encode(), "portfolio.json")

    ui.button("Export Portfolio", icon="download", on_click=on_export).props(
        "flat dense size=sm no-caps"
    ).classes("w-full").style(
        f"border:1px solid {BORDER_INPUT}; border-radius:6px; color:{TEXT_MUTED}; font-size:10px; text-transform:none; margin-top:4px;"
    )

    # Load Sample
    def on_load_sample():
        with ui.dialog() as dialog, ui.card().style("min-width:260px;"):
            ui.label("Load Sample Portfolio?").style("font-weight:600;font-size:14px;")
            ui.label("This will replace your current portfolio with sample data.").style("font-size:12px;")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                def do_load_sample(d=dialog):
                    with open(_SAMPLE_PATH) as f:
                        sample = json.load(f)
                    portfolio.clear()
                    portfolio.update(sample)
                    stored = _load_portfolio()
                    stored["portfolio"] = portfolio
                    _save_portfolio(stored)
                    positions_list.refresh()
                    d.close()
                    ui.notify("Sample portfolio loaded.", type="positive")
                ui.button("Load Sample", on_click=do_load_sample, color="blue").props("flat")
        dialog.open()

    ui.button("Load Sample", icon="science", on_click=on_load_sample).props(
        "flat dense size=sm no-caps"
    ).classes("w-full").style(
        f"border:1px solid {BORDER_INPUT}; border-radius:6px; color:{TEXT_MUTED}; font-size:10px; text-transform:none; margin-top:4px;"
    )

    # Clear All
    def on_clear_all():
        if not portfolio:
            ui.notify("Portfolio is already empty.", type="info")
            return
        with ui.dialog() as dialog, ui.card().style("min-width:260px;"):
            ui.label("Clear All Positions?").style("font-weight:600;font-size:14px;")
            ui.label("This will delete all your positions. This cannot be undone.").style("font-size:12px;")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                def do_clear(d=dialog):
                    portfolio.clear()
                    stored = _load_portfolio()
                    stored["portfolio"] = portfolio
                    _save_portfolio(stored)
                    positions_list.refresh()
                    d.close()
                    ui.notify("Portfolio cleared.", type="info")
                ui.button("Clear All", on_click=do_clear, color="red").props("flat")
        dialog.open()

    ui.button("Clear All", icon="delete_sweep", on_click=on_clear_all).props(
        "flat dense size=sm no-caps"
    ).classes("w-full").style(
        f"border:1px solid {BORDER_INPUT}; border-radius:6px; color:{TEXT_MUTED}; font-size:10px; text-transform:none; margin-top:4px;"
    )


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
