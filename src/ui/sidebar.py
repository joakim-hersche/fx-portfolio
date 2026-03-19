"""Sidebar: add-position form, positions list, import/export/sample/clear."""

from __future__ import annotations

import json
import os
import re

import pandas as pd
from nicegui import run, ui

from src.charts import CHART_COLORS
from src.fx import CURRENCY_SYMBOLS, get_fx_rate, get_historical_fx_rate, get_ticker_currency
from src.portfolio import fetch_buy_price
from src.theme import ACCENT_DARK, BG_CARD, BORDER, BORDER_INPUT, TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY
from src.ui.shared import load_portfolio, save_portfolio

# ── Sample portfolio path ──
_SAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "sample_portfolio.json",
)

# ── Market names list (matches load_stock_options keys) ──
_MARKETS = [
    "US — S&P 500", "UK — FTSE 100", "Germany — DAX", "France — CAC 40",
    "Switzerland — SMI", "Netherlands — AEX", "Spain — IBEX 35",
    "Sweden — OMX 30",
    "ETFs", "REITs", "Bonds", "Emerging Markets", "Crypto", "Commodities",
]

_ALT_ASSETS = {"Crypto", "Commodities"}

_VALID_TICKER_RE = re.compile(r'^[A-Za-z0-9.\-=^]{1,15}$')


def _is_valid_ticker(ticker: str) -> bool:
    """Return True if ticker is a safe, well-formed symbol string."""
    return isinstance(ticker, str) and bool(_VALID_TICKER_RE.match(ticker))


def build_sidebar(
    portfolio: dict, stock_options: dict, shared: dict,
    active_tab: dict,
    on_mutation=None,
) -> None:
    """Build the sidebar: add-position form + positions list + import/export."""

    # ── Add Position form ──────────────────────────────────
    ui.html('<div class="sidebar-section-header">Portfolio</div>')

    # Market select
    ui.html('<label class="form-label">Market</label>').classes("w-full")
    market_select = ui.select(
        _MARKETS,
        value=_MARKETS[0],
    ).props("dense outlined").classes("w-full").style("font-size:11px;")

    # Ticker select (populated from stock options)
    initial_options = stock_options.get(_MARKETS[0], {})
    ui.html('<label class="form-label">Ticker</label>').classes("w-full")
    ticker_select = ui.select(
        options=initial_options,
        with_input=True,
    ).props("dense outlined use-input").classes("w-full").style("font-size:11px;")

    def on_market_change(e):
        market = e.value
        opts = stock_options.get(market, {})
        ticker_select.options = opts
        ticker_select.value = None
        ticker_select.update()
        is_alt = market in _ALT_ASSETS
        # Update shares/amount label text
        new_label = f"Amount ({shared['currency']})" if is_alt else "Shares"
        shares_label.content = f'<label class="form-label">{new_label}</label>'
        shares_label.update()
        # Toggle date vs price visibility
        _update_price_date_visibility(is_alt, manual_checkbox.value if not is_alt else False)

    market_select.on_value_change(on_market_change)

    # Shares / Amount + Buy Price row
    with ui.row().classes("w-full").style("gap:6px;"):
        with ui.column().classes("w-full").style("gap:0; min-width:0; flex:1;"):
            shares_label = ui.html('<label class="form-label">Shares</label>').classes("w-full")
            shares_input = ui.number(placeholder="10", min=0.01).props(
                "dense outlined"
            ).classes("w-full").style("font-size:11px;")
        with ui.column().classes("w-full").style("gap:0; min-width:0; flex:1;") as price_col:
            price_label = ui.html('<label class="form-label">Buy Price</label>').classes("w-full")
            price_input = ui.number(placeholder="150.00", min=0, step=0.01).props(
                "dense outlined"
            ).classes("w-full").style("font-size:11px;")
            price_col.set_visibility(False)

    # Date input with date picker popup (auto-close on pick to avoid backdrop trap)
    date_label = ui.html('<label class="form-label">Date</label>').classes("w-full")
    date_input = ui.input(placeholder="2024-01-15").props(
        'dense outlined mask="####-##-##"'
    ).classes("w-full").style("font-size:11px;")
    with date_input:
        with ui.menu().props("no-parent-event auto-close") as date_menu:
            ui.date().bind_value(date_input)
        with date_input.add_slot("append"):
            ui.icon("edit_calendar").on("click", date_menu.open).classes("cursor-pointer")

    # Manual price checkbox (hidden for alt assets)
    manual_checkbox = ui.checkbox("Enter price manually", value=False).style(
        "font-size:10px;"
    )

    def _update_price_date_visibility(is_alt: bool, is_manual: bool):
        if is_alt:
            date_label.set_visibility(True)
            date_input.set_visibility(True)
            price_col.set_visibility(False)
            manual_checkbox.set_visibility(False)
        elif is_manual:
            # Keep date visible but optional (#14)
            date_label.set_visibility(True)
            date_input.set_visibility(True)
            price_col.set_visibility(True)
            manual_checkbox.set_visibility(True)
        else:
            date_label.set_visibility(True)
            date_input.set_visibility(True)
            price_col.set_visibility(False)
            manual_checkbox.set_visibility(True)

    def on_manual_change(e):
        is_alt = market_select.value in _ALT_ASSETS
        _update_price_date_visibility(is_alt, e.value)

    manual_checkbox.on_value_change(on_manual_change)

    # ── Add Position button ──────────────────────────────
    async def on_add_position():
        add_btn.disable()
        try:
            await _on_add_position_inner()
        finally:
            add_btn.enable()

    async def _on_add_position_inner():
        market = market_select.value
        is_alt = market in _ALT_ASSETS
        ticker = ticker_select.value
        manual = manual_checkbox.value and not is_alt

        # Validation
        if not ticker:
            ui.notify("Please select a stock.", type="warning")
            return
        if not _is_valid_ticker(ticker):
            ui.notify("Invalid ticker symbol.", type="negative")
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

        # Determine buy price and FX rate (use run.io_bound for blocking I/O)
        ticker_currency = get_ticker_currency(ticker)
        base_currency = shared["currency"]
        purchase_date = date_input.value

        if manual:
            buy_price = price_input.value
            buy_fx_rate = 1.0
            if not purchase_date:
                ui.notify("No purchase date set. Optional — helps track dividends and purchase-relative returns.", type="info")
        elif purchase_date:
            notification = ui.notification("Fetching price data...", spinner=True, timeout=None)
            result = await run.io_bound(fetch_buy_price, ticker, str(purchase_date))
            notification.dismiss()
            if result is None:
                ui.notify(
                    f"Could not fetch price for {ticker} on {purchase_date}. "
                    "Check the ticker symbol and date, or try again if Yahoo Finance is slow.",
                    type="negative",
                )
                return
            buy_price, actual_date = result
            if actual_date != str(purchase_date):
                ui.notify(
                    f"{purchase_date} was not a trading day. Using price from {actual_date}.",
                    type="info",
                )
            buy_fx_rate = await run.io_bound(get_historical_fx_rate, ticker_currency, base_currency, str(purchase_date))
        else:
            # Alt asset without date — use today
            purchase_date = str(pd.Timestamp.today().date())
            notification = ui.notification("Fetching price data...", spinner=True, timeout=None)
            result = await run.io_bound(fetch_buy_price, ticker, purchase_date)
            notification.dismiss()
            buy_price = result[0] if result else None
            if buy_price is None:
                ui.notify("Could not fetch current price.", type="negative")
                return
            buy_fx_rate, _ = await run.io_bound(get_fx_rate, ticker_currency, base_currency)

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
        stored = load_portfolio()
        stored["portfolio"] = portfolio
        save_portfolio(stored)

        sym = CURRENCY_SYMBOLS.get(base_currency, "$")
        ui.notify(f"Added {shares:g} units of {ticker} at {sym}{buy_price:,.2f}", type="positive")

        # Reset form
        ticker_select.value = None
        shares_input.value = None
        price_input.value = None
        date_input.value = ""

        # Refresh visible tab + sidebar without full page reload
        positions_list.refresh()
        if on_mutation and on_mutation.get("fn"):
            await on_mutation["fn"]()

    add_btn = ui.button("+ Add Position", on_click=on_add_position).classes(
        "add-btn w-full"
    ).props('no-caps unelevated no-ripple color=none aria-label="Add position"').style(
        f"background:{ACCENT_DARK}; color:{TEXT_PRIMARY}; font-size:12px; font-weight:600; padding:8px 0; min-height:32px;"
    )

    # Enter key on shares and date inputs submits the form
    shares_input.on("keydown.enter", on_add_position)
    date_input.on("keydown.enter", on_add_position)

    # ── Divider + positions list ───────────────────────────
    ui.html('<hr class="sidebar-divider" style="margin-top:12px;">')
    ui.html('<div class="sidebar-section-header">Positions</div>')

    @ui.refreshable
    def positions_list():
        if portfolio:
            tickers = list(portfolio.keys())
            for i, ticker in enumerate(tickers):
                color = (shared.get("portfolio_color_map") or {}).get(ticker, CHART_COLORS[i % len(CHART_COLORS)])
                lots = portfolio[ticker]
                total_shares = sum(lot.get("shares", 0) for lot in lots)
                mkt_value = (shared.get("ticker_values") or {}).get(ticker)
                # Show dollar value if available, otherwise share count
                if mkt_value is not None:
                    value_text = f"{shared['currency_symbol']}{mkt_value:,.0f}"
                else:
                    value_text = f"{total_shares:g} shares"
                company_name = shared.get("name_map", {}).get(ticker, ticker)
                with ui.row().classes("w-full items-center position-row").style(
                    "gap:6px;"
                ):
                    ui.html(
                        f'<div style="width:8px;height:8px;border-radius:50%;background:{color};flex-shrink:0;"></div>'
                    )
                    with ui.column().classes("flex-grow").style("gap:0;"):
                        ui.label(ticker).style(
                            f"font-size:12px;font-weight:600;color:{TEXT_PRIMARY};line-height:1.2;"
                        )
                        ui.label(company_name).classes("pos-name").style(
                            f"font-size:10px;color:{TEXT_DIM};line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100px;"
                        ).props(f'title="{company_name}"')
                    ui.label(value_text).style(
                        f"font-size:11px;font-weight:500;color:{TEXT_MUTED};text-align:right;"
                    )
                    # Remove button
                    _t = ticker  # capture for closure
                    ui.button(
                        icon="close",
                        on_click=lambda _, t=_t: _confirm_remove(t),
                    ).props(f'flat dense round size=xs aria-label="Remove {_t}"').style(
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
        with ui.dialog() as dialog, ui.card().style(f"min-width:260px;background:{BG_CARD};"):
            ui.label(f"Remove {ticker}?").style("font-weight:600;font-size:14px;")
            if len(lots) == 1:
                ui.label("This will remove the position. This cannot be undone.").style("font-size:12px;")
            else:
                ui.label(f"This will remove all {len(lots)} lots. This cannot be undone.").style("font-size:12px;")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                async def do_remove(d=dialog, t=ticker):
                    # Soft delete with undo window (#21)
                    removed_lots = portfolio.pop(t)
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    positions_list.refresh()
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()

                    # Show undo toast
                    undo_state = {"undone": False}
                    async def _undo():
                        if undo_state["undone"]:
                            return
                        undo_state["undone"] = True
                        portfolio[t] = removed_lots
                        stored2 = load_portfolio()
                        stored2["portfolio"] = portfolio
                        save_portfolio(stored2)
                        positions_list.refresh()
                        if on_mutation and on_mutation.get("fn"):
                            await on_mutation["fn"]()
                        ui.notify(f"Restored {t}", type="positive")
                    with ui.notification(f"Removed {t}", timeout=5) as n:
                        ui.button("Undo", on_click=_undo).props("flat dense")
                ui.button("Remove", on_click=do_remove, color="red").props("flat")
        dialog.open()

    # ── Import / Export / Sample / Clear ──────────────────
    ui.html('<hr class="sidebar-divider">')

    # Import
    async def on_import_upload(e):
        try:
            content = e.content.read()
            data = json.loads(content)
            # Validate structure and types (#15)
            if not isinstance(data, dict):
                ui.notify("Invalid portfolio file: expected a JSON object.", type="negative")
                return
            for t, lots in data.items():
                if not isinstance(t, str) or not isinstance(lots, list):
                    ui.notify(f"Invalid portfolio file: bad entry for '{t}'.", type="negative")
                    return
                if not _is_valid_ticker(t):
                    ui.notify(f"Invalid ticker '{t}': must be 1-15 alphanumeric/.-=^ characters.", type="negative")
                    return
                for lot in lots:
                    if not isinstance(lot, dict) or not {"shares", "buy_price", "purchase_date"}.issubset(lot.keys()):
                        ui.notify(f"Invalid lot for {t}: missing required fields.", type="negative")
                        return
                    if not isinstance(lot["shares"], (int, float)) or lot["shares"] <= 0:
                        ui.notify(f"Invalid shares for {t}: must be a positive number.", type="negative")
                        return
                    if not isinstance(lot["buy_price"], (int, float)) or lot["buy_price"] <= 0:
                        ui.notify(f"Invalid buy_price for {t}: must be a positive number.", type="negative")
                        return
                    if lot["purchase_date"] is not None and not isinstance(lot["purchase_date"], str):
                        ui.notify(f"Invalid purchase_date for {t}: must be a string or null.", type="negative")
                        return
            portfolio.clear()
            portfolio.update(data)
            stored = load_portfolio()
            stored["portfolio"] = portfolio
            save_portfolio(stored)
            ui.notify("Portfolio imported successfully.", type="positive")
            positions_list.refresh()
            if on_mutation and on_mutation.get("fn"):
                await on_mutation["fn"]()
        except Exception:
            ui.notify("Could not read the file.", type="negative")

    import_upload = ui.upload(
        auto_upload=True,
        on_upload=on_import_upload,
    ).props('accept=".json"').style("display:none;")

    _sidebar_btn_style = (
        f"border:1px solid {BORDER_INPUT}; border-radius:5px; color:{TEXT_DIM}; "
        f"font-size:11px; font-weight:500; padding:6px 0; margin-bottom:4px; "
        f"text-transform:none; width:100%; box-sizing:border-box;"
    )
    _sidebar_btn_props = "flat no-caps no-ripple"

    ui.button("Import Portfolio", on_click=lambda: ui.run_javascript(
        f'document.getElementById("c{import_upload.id}").querySelector("input").click()'
    )).classes("w-full").props(_sidebar_btn_props).style(_sidebar_btn_style)

    # Export
    def on_export():
        if not portfolio:
            ui.notify("No positions to export.", type="warning")
            return
        content = json.dumps(portfolio, indent=2)
        ui.download(content.encode(), "portfolio.json")

    ui.button("Export Portfolio", on_click=on_export).props(
        _sidebar_btn_props
    ).classes("w-full").style(_sidebar_btn_style)

    # Load Sample
    def on_load_sample():
        with ui.dialog() as dialog, ui.card().style(f"min-width:260px;background:{BG_CARD};"):
            ui.label("Load Sample Portfolio?").style("font-weight:600;font-size:14px;")
            ui.label("This will replace your current portfolio with sample data.").style("font-size:12px;")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                async def do_load_sample(d=dialog):
                    with open(_SAMPLE_PATH) as f:
                        sample = json.load(f)
                    portfolio.clear()
                    portfolio.update(sample)
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    ui.notify("Sample portfolio loaded.", type="positive")
                    positions_list.refresh()
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()
                ui.button("Load Sample", on_click=do_load_sample, color="blue").props("flat")
        dialog.open()

    ui.button("Load Sample", on_click=on_load_sample).props(
        _sidebar_btn_props
    ).classes("w-full").style(_sidebar_btn_style)

    # Clear All
    def on_clear_all():
        if not portfolio:
            ui.notify("Portfolio is already empty.", type="info")
            return
        with ui.dialog() as dialog, ui.card().style(f"min-width:260px;background:{BG_CARD};"):
            ui.label("Clear All Positions?").style("font-weight:600;font-size:14px;")
            ui.label("This will delete all your positions. This cannot be undone.").style("font-size:12px;")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")
                async def do_clear(d=dialog):
                    portfolio.clear()
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    ui.notify("Portfolio cleared.", type="info")
                    positions_list.refresh()
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()
                ui.button("Clear All", on_click=do_clear, color="red").props("flat")
        dialog.open()

    ui.button("Clear All", on_click=on_clear_all).props(
        _sidebar_btn_props
    ).classes("w-full").style(_sidebar_btn_style)
