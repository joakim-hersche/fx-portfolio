"""Sidebar: search-first add-position, positions list, action icons."""

from __future__ import annotations

import json
import os
import re

import pandas as pd
from nicegui import run, ui

from src.charts import CHART_COLORS
from src.fx import CURRENCY_SYMBOLS, get_fx_rate, get_historical_fx_rate, get_ticker_currency
from src.portfolio import fetch_buy_price
from src.theme import (
    ACCENT, ACCENT_DARK, BG_CARD, BG_INPUT, BG_PILL,
    BORDER, BORDER_INPUT, BORDER_SUBTLE,
    TEXT_DIM, TEXT_MUTED, TEXT_PRIMARY,
)
from src.ui.shared import load_portfolio, save_portfolio

# ── Sample portfolio path ──
_SAMPLE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "sample_portfolio.json",
)

# ── Market names list (matches load_stock_options keys) ──
_MARKETS = [
    "US — S&P 500", "UK — FTSE 100", "Germany — DAX", "France — CAC 40",
    "Switzerland — SMI", "Switzerland — SMIM", "Netherlands — AEX", "Spain — IBEX 35",
    "Sweden — OMX 30",
    "ETFs", "REITs", "Bonds", "Emerging Markets", "Crypto", "Commodities",
]

_ALT_ASSETS = {"Crypto", "Commodities"}

_VALID_TICKER_RE = re.compile(r'^[A-Za-z0-9.\-=^]{1,15}$')


def _is_valid_ticker(ticker: str) -> bool:
    return isinstance(ticker, str) and bool(_VALID_TICKER_RE.match(ticker))


# ── Infer market from ticker ──
_MARKET_SUFFIXES = {
    ".L": "UK — FTSE 100",
    ".DE": "Germany — DAX",
    ".PA": "France — CAC 40",
    ".SW": "Switzerland — SMI",
    ".AS": "Netherlands — AEX",
    ".MC": "Spain — IBEX 35",
    ".ST": "Sweden — OMX 30",
}


def _infer_market(ticker: str) -> str | None:
    """Infer market from ticker suffix, or None for US/unknown."""
    for suffix, market in _MARKET_SUFFIXES.items():
        if ticker.upper().endswith(suffix):
            return market
    return None


def build_sidebar(
    portfolio: dict, stock_options: dict, shared: dict,
    active_tab: dict,
    on_mutation=None,
) -> None:
    """Build the sidebar: search-first add form + positions list + action icons."""

    # Build flat ticker->label map from all markets for the unified search
    all_tickers: dict[str, str] = {}
    for market, opts in stock_options.items():
        if isinstance(opts, dict):
            all_tickers.update(opts)
        elif isinstance(opts, list):
            all_tickers.update({t: t for t in opts})

    # ── Unified Search Bar ─────────────────────────────────
    ui.html(
        f'<div style="font-size:10px;font-weight:700;color:{TEXT_MUTED};letter-spacing:0.04em;'
        f'text-transform:uppercase;margin-bottom:4px;">Add Position</div>'
    )
    search_select = ui.select(
        options=all_tickers,
        with_input=True,
        label="Search ticker...",
    ).props(
        'dense outlined use-input clearable input-debounce="150" '
        'behavior="menu"'
    ).classes("w-full sidebar-search").style(
        f"font-size:11px;"
    )

    search_select.add_slot(
        "no-option",
        f'<div style="padding:8px 12px;font-size:11px;color:{TEXT_DIM};">No matching tickers found</div>'
    )
    search_select.add_slot(
        "prepend",
        '<q-icon name="search" style="font-size:16px;opacity:0.5;" />'
    )

    # After each input keystroke, auto-highlight the first filtered option
    # so pressing Enter selects it without needing arrow-down first.
    search_select.on(
        "input-value",
        lambda: ui.run_javascript(f'''
            setTimeout(() => {{
                const el = getElement({search_select.id});
                if (el && el.$refs && el.$refs.qRef) {{
                    const q = el.$refs.qRef;
                    q.setOptionIndex(-1);
                    q.moveOptionSelection(1, true);
                }}
            }}, 200);
        '''),
    )

    # ── Detail fields (hidden until ticker selected) ───────
    detail_container = ui.column().classes("w-full").style("gap:6px;")
    detail_container.set_visibility(False)

    with detail_container:
        # Market tag + company name
        ticker_info = ui.html("").classes("w-full")

        with ui.row().classes("w-full").style("gap:6px;"):
            with ui.column().classes("w-full").style("gap:0; min-width:0; flex:1;"):
                shares_label = ui.html(
                    f'<label style="font-size:9px;font-weight:600;color:{TEXT_DIM};letter-spacing:0.04em;text-transform:uppercase;">Shares</label>'
                ).classes("w-full")
                shares_input = ui.number(placeholder="10", min=0.01).props(
                    "dense outlined"
                ).classes("w-full").style("font-size:11px;")
            with ui.column().classes("w-full").style("gap:0; min-width:0; flex:1;"):
                ui.html(
                    f'<label style="font-size:9px;font-weight:600;color:{TEXT_DIM};letter-spacing:0.04em;text-transform:uppercase;">Date</label>'
                ).classes("w-full")
                date_input = ui.input(placeholder="2024-01-15").props(
                    'dense outlined mask="####-##-##"'
                ).classes("w-full").style("font-size:11px;min-width:95px;")
                with date_input:
                    with ui.menu().props("no-parent-event auto-close") as date_menu:
                        ui.date().bind_value(date_input)
                    with date_input.add_slot("append"):
                        ui.icon("edit_calendar").on("click", date_menu.open).classes(
                            "cursor-pointer"
                        ).style(f"font-size:16px;color:{TEXT_DIM};")

        # Manual price row (hidden by default)
        with ui.row().classes("w-full").style("gap:6px;") as price_row:
            with ui.column().classes("w-full").style("gap:0; min-width:0; flex:1;"):
                ui.html(
                    f'<label style="font-size:9px;font-weight:600;color:{TEXT_DIM};letter-spacing:0.04em;text-transform:uppercase;">Buy Price</label>'
                ).classes("w-full")
                price_input = ui.number(placeholder="150.00", min=0, step=0.01).props(
                    "dense outlined"
                ).classes("w-full").style("font-size:11px;")
        price_row.set_visibility(False)

        ui.html(
            f'<div style="font-size:9px;color:{TEXT_DIM};margin:-2px 0 2px 0;">'
            'Price is fetched automatically from the purchase date.</div>'
        )
        manual_checkbox = ui.checkbox("Enter price manually", value=False).style(
            f"font-size:10px;color:{TEXT_DIM};"
        )

        # Placeholder — real handler assigned after definition below
        _add_handler = {"fn": None}

        async def _on_add_click():
            if _add_handler["fn"]:
                await _add_handler["fn"]()

        add_btn = ui.button("+ Add", on_click=_on_add_click).props(
            'no-caps unelevated no-ripple color=none'
        ).classes("w-full").style(
            f"background:{ACCENT};color:white;font-size:11px;font-weight:600;"
            f"padding:5px 0;min-height:28px;border-radius:5px;"
        )

    # ── Show/hide detail fields on ticker selection ────────
    def _on_ticker_change(e):
        ticker = e.value
        if ticker and _is_valid_ticker(ticker):
            detail_container.set_visibility(True)
            market = _infer_market(ticker)
            market_label = market.split(" — ")[0] if market else "US"
            company = all_tickers.get(ticker, ticker)
            is_alt = market in _ALT_ASSETS if market else False
            ticker_info.content = (
                f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:2px;">'
                f'<span style="font-size:9px;font-weight:600;padding:1px 6px;border-radius:3px;'
                f'background:{ACCENT_DARK};color:#93C5FD;">{market_label}</span>'
                f'<span style="font-size:10px;color:{TEXT_MUTED};white-space:nowrap;overflow:hidden;'
                f'text-overflow:ellipsis;">{company}</span>'
                f'</div>'
            )
            ticker_info.update()
            # Update shares label for alt assets
            label_text = f"Amount ({shared['currency']})" if is_alt else "Shares"
            shares_label.content = (
                f'<label style="font-size:9px;font-weight:600;color:{TEXT_DIM};'
                f'letter-spacing:0.04em;text-transform:uppercase;">{label_text}</label>'
            )
            shares_label.update()
        else:
            detail_container.set_visibility(False)

    search_select.on_value_change(_on_ticker_change)

    def _on_manual_change(e):
        price_row.set_visibility(e.value)

    manual_checkbox.on_value_change(_on_manual_change)

    # ── Add Position logic ─────────────────────────────────
    async def on_add_position():
        add_btn.disable()
        spinner = ui.spinner("dots", size="sm")
        try:
            await _on_add_position_inner()
        finally:
            spinner.delete()
            add_btn.enable()

    async def _on_add_position_inner():
        ticker = search_select.value
        if not ticker:
            ui.notify("Please select a stock.", type="warning")
            return
        if not _is_valid_ticker(ticker):
            ui.notify("Invalid ticker symbol.", type="negative")
            return

        market = _infer_market(ticker)
        is_alt = market in _ALT_ASSETS if market else False
        manual = manual_checkbox.value and not is_alt

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

        ticker_currency = get_ticker_currency(ticker)
        base_currency = shared["currency"]
        purchase_date = date_input.value

        if manual:
            buy_price = price_input.value
            buy_fx_rate = 1.0
            if not purchase_date:
                ui.notify("No purchase date set. Optional — helps track dividends.", type="info")
        elif purchase_date:
            notification = ui.notification("Fetching price data...", spinner=True, timeout=None)
            result = await run.io_bound(fetch_buy_price, ticker, str(purchase_date))
            notification.dismiss()
            if result is None:
                ui.notify(
                    f"Could not fetch price for {ticker} on {purchase_date}. "
                    "Check the ticker and date, or try again.",
                    type="negative",
                )
                return
            buy_price, actual_date = result
            if actual_date != str(purchase_date):
                ui.notify(
                    f"{purchase_date} was not a trading day. Using {actual_date}.",
                    type="info",
                )
            buy_fx_rate = await run.io_bound(
                get_historical_fx_rate, ticker_currency, base_currency, str(purchase_date)
            )
        else:
            purchase_date = str(pd.Timestamp.today().date())
            notification = ui.notification("Fetching price data...", spinner=True, timeout=None)
            result = await run.io_bound(fetch_buy_price, ticker, purchase_date)
            notification.dismiss()
            buy_price = result[0] if result else None
            if buy_price is None:
                ui.notify("Could not fetch current price.", type="negative")
                return
            buy_fx_rate, _ = await run.io_bound(get_fx_rate, ticker_currency, base_currency)

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

        portfolio.setdefault(ticker, []).append(lot)
        stored = load_portfolio()
        stored["portfolio"] = portfolio
        save_portfolio(stored)

        sym = CURRENCY_SYMBOLS.get(base_currency, "$")
        ui.notify(f"Added {shares:g} units of {ticker} at {sym}{buy_price:,.2f}", type="positive")

        # Reset form
        search_select.value = None
        shares_input.value = None
        price_input.value = None
        date_input.value = ""
        detail_container.set_visibility(False)

        # Update color map + tabs first, then refresh sidebar with new colors
        if on_mutation and on_mutation.get("fn"):
            await on_mutation["fn"]()
        positions_list.refresh()

    _add_handler["fn"] = on_add_position
    shares_input.on("keydown.enter", on_add_position)
    date_input.on("keydown.enter", on_add_position)

    # ── Positions list ─────────────────────────────────────
    ui.html('<hr class="sidebar-divider" style="margin-top:4px;">')
    ui.html('<div class="sidebar-section-header">Positions</div>')

    # ── Edit lot dialog ──────────────────────────────────────
    def _edit_lot(ticker: str, lot_index: int):
        lots = portfolio.get(ticker, [])
        if lot_index >= len(lots):
            return
        lot = lots[lot_index]
        n_lots = len(lots)
        title = f"Edit {ticker}" + (f" — Lot {lot_index + 1}/{n_lots}" if n_lots > 1 else "")

        with ui.dialog() as dialog, ui.card().style(f"min-width:300px;background:{BG_CARD};"):
            ui.label(title).style("font-weight:600;font-size:14px;")

            with ui.column().classes("w-full").style("gap:8px;"):
                ui.html(
                    f'<label style="font-size:9px;font-weight:600;color:{TEXT_DIM};'
                    f'letter-spacing:0.04em;text-transform:uppercase;">Shares</label>'
                )
                edit_shares = ui.number(
                    value=lot.get("shares", 0), min=0.01
                ).props("dense outlined").classes("w-full").style("font-size:11px;")

                ui.html(
                    f'<label style="font-size:9px;font-weight:600;color:{TEXT_DIM};'
                    f'letter-spacing:0.04em;text-transform:uppercase;">Buy Price</label>'
                )
                edit_price = ui.number(
                    value=lot.get("buy_price", 0), min=0, step=0.01
                ).props("dense outlined").classes("w-full").style("font-size:11px;")

                ui.html(
                    f'<label style="font-size:9px;font-weight:600;color:{TEXT_DIM};'
                    f'letter-spacing:0.04em;text-transform:uppercase;">Purchase Date</label>'
                )
                edit_date = ui.input(
                    value=lot.get("purchase_date", "") or ""
                ).props('dense outlined mask="####-##-##"').classes("w-full").style("font-size:11px;")

            with ui.row().classes("w-full justify-between").style("margin-top:8px;"):
                async def do_delete(d=dialog, t=ticker, li=lot_index):
                    lots_ref = portfolio.get(t, [])
                    if len(lots_ref) <= 1:
                        portfolio.pop(t, None)
                    else:
                        lots_ref.pop(li)
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    positions_list.refresh()
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()
                    ui.notify(f"Deleted lot from {t}", type="info")

                ui.button("Delete", on_click=do_delete, color="red").props("flat")

                async def do_save(d=dialog, t=ticker, li=lot_index):
                    new_shares = edit_shares.value
                    new_price = edit_price.value
                    new_date = edit_date.value
                    if not new_shares or new_shares <= 0:
                        ui.notify("Shares must be positive.", type="warning")
                        return
                    if new_price is None or new_price < 0:
                        ui.notify("Price must be non-negative.", type="warning")
                        return
                    lots_ref = portfolio.get(t, [])
                    if li < len(lots_ref):
                        lots_ref[li]["shares"] = new_shares
                        lots_ref[li]["buy_price"] = new_price
                        lots_ref[li]["purchase_date"] = new_date if new_date else None
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    positions_list.refresh()
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()
                    ui.notify(f"Updated {t}", type="positive")

                ui.button("Save", on_click=do_save).props("flat").style(
                    f"color:{ACCENT};"
                )
        dialog.open()

    @ui.refreshable
    def positions_list():
        if portfolio:
            tickers = list(portfolio.keys())
            with ui.column().classes("w-full").style("gap:4px;"):
                for i, ticker in enumerate(tickers):
                    color = (shared.get("portfolio_color_map") or {}).get(
                        ticker, CHART_COLORS[i % len(CHART_COLORS)]
                    )
                    lots = portfolio[ticker]
                    total_shares = sum(lot.get("shares", 0) for lot in lots)
                    mkt_value = (shared.get("ticker_values") or {}).get(ticker)
                    if mkt_value is not None:
                        value_text = f"{shared['currency_symbol']}{mkt_value:,.0f}"
                    else:
                        value_text = f"{total_shares:g} shares"
                    company_name = shared.get("name_map", {}).get(ticker, ticker)

                    # Detect unavailable tickers
                    is_unavailable = (shared.get("unavailable_tickers") or set())
                    warn_html = ""
                    if ticker in is_unavailable:
                        warn_html = (
                            f'<span style="color:#D97706;font-size:12px;flex-shrink:0;" '
                            f'title="Data unavailable for {ticker}">\u26a0</span>'
                        )

                    _t = ticker
                    bridge = ui.element("div").style("display:none;")
                    bridge.on("remove_click", lambda _, t=_t: _confirm_remove(t))

                    # Edit bridges — one per lot
                    edit_bridges = []
                    for li in range(len(lots)):
                        eb = ui.element("div").style("display:none;")
                        eb.on("edit_click", lambda _, t=_t, idx=li: _edit_lot(t, idx))
                        edit_bridges.append(f"c{eb.id}")

                    bridge_id = f"c{bridge.id}"

                    # Build edit click JS — for single lot, click edit icon directly;
                    # for multi-lot, click opens first lot (user can navigate via dialog)
                    edit_onclick = (
                        f"document.getElementById('{edit_bridges[0]}')"
                        f".dispatchEvent(new Event('edit_click'))"
                    ) if edit_bridges else ""

                    ui.html(
                        f'<div style="display:flex;align-items:center;gap:8px;width:100%;'
                        f'background:{BG_PILL};border:1px solid {BORDER_SUBTLE};'
                        f'border-radius:6px;padding:7px 8px 7px 10px;box-sizing:border-box;">'
                        f'<div style="width:6px;height:6px;border-radius:50%;background:{color};flex-shrink:0;"></div>'
                        f'{warn_html}'
                        f'<div style="flex:1;min-width:0;font-size:11px;font-weight:600;color:{TEXT_PRIMARY};'
                        f'line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;" title="{company_name}">'
                        f'{ticker} <span style="font-weight:400;color:{TEXT_DIM};">{value_text}</span></div>'
                        f'<div onclick="{edit_onclick}" '
                        f'style="flex-shrink:0;cursor:pointer;color:{TEXT_MUTED};font-size:12px;line-height:1;'
                        f'padding:2px;" title="Edit {_t}">\u270e</div>'
                        f'<div onclick="document.getElementById(\'{bridge_id}\').dispatchEvent(new Event(\'remove_click\'))" '
                        f'style="flex-shrink:0;cursor:pointer;color:{TEXT_MUTED};font-size:14px;line-height:1;'
                        f'padding:2px;" title="Remove {_t}">&times;</div>'
                        f'</div>'
                    ).classes("w-full")
        else:
            ui.html(
                f'<div style="font-size:11px;color:{TEXT_DIM};padding:8px 4px;">'
                "No positions yet. Search above to add one.</div>"
            )

    positions_list()

    if on_mutation:
        on_mutation["sidebar_refresh"] = positions_list.refresh

    # ── Confirmation dialog for remove ─────────────────────
    _dlg_card_style = (
        f"min-width:280px;max-width:340px;background:{BG_CARD};"
        f"border:1px solid {BORDER};border-radius:10px;padding:20px;"
    )
    _dlg_cancel_style = (
        f"border:1px solid {BORDER_SUBTLE};border-radius:6px;color:{TEXT_MUTED};"
        f"font-size:11px;padding:6px 16px;text-transform:none;"
    )
    _dlg_danger_style = (
        f"background:rgba(220,38,38,0.15);border:1px solid rgba(220,38,38,0.3);"
        f"border-radius:6px;color:#FCA5A5;font-size:11px;padding:6px 16px;text-transform:none;"
    )
    _dlg_accent_style = (
        f"background:{ACCENT_DARK};border:1px solid rgba(59,130,246,0.3);"
        f"border-radius:6px;color:white !important;font-size:11px;padding:6px 16px;text-transform:none;"
    )

    def _confirm_remove(ticker: str):
        lots = portfolio.get(ticker, [])
        with ui.dialog() as dialog, ui.card().style(_dlg_card_style):
            ui.label(f"Remove {ticker}?").style(
                f"font-weight:600;font-size:14px;color:{TEXT_PRIMARY};margin-bottom:4px;"
            )
            msg = "This will remove the position." if len(lots) == 1 else f"This will remove all {len(lots)} lots."
            ui.label(msg).style(f"font-size:12px;color:{TEXT_MUTED};line-height:1.5;")
            with ui.row().classes("w-full justify-end gap-2").style("margin-top:12px;"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps").style(_dlg_cancel_style)

                async def do_remove(d=dialog, t=ticker):
                    removed_lots = portfolio.pop(t)
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()
                    positions_list.refresh()

                    undo_state = {"undone": False}

                    async def _undo():
                        if undo_state["undone"]:
                            return
                        undo_state["undone"] = True
                        portfolio[t] = removed_lots
                        stored2 = load_portfolio()
                        stored2["portfolio"] = portfolio
                        save_portfolio(stored2)
                        if on_mutation and on_mutation.get("fn"):
                            await on_mutation["fn"]()
                        positions_list.refresh()
                        ui.notify(f"Restored {t}", type="positive")

                    with ui.notification(f"Removed {t}", timeout=5):
                        ui.button("Undo", on_click=_undo).props("flat dense")

                ui.button("Remove", on_click=do_remove).props("flat no-caps").style(_dlg_danger_style)
        dialog.open()

    # ── Bottom action icons ────────────────────────────────
    ui.html('<hr class="sidebar-divider">')

    # Hidden upload element
    async def on_import_upload(e):
        try:
            content = e.content.read()
            data = json.loads(content)
            if not isinstance(data, dict):
                ui.notify("Invalid portfolio file.", type="negative")
                return
            for t, lots in data.items():
                if not isinstance(t, str) or not isinstance(lots, list):
                    ui.notify(f"Invalid entry for '{t}'.", type="negative")
                    return
                if not _is_valid_ticker(t):
                    ui.notify(f"Invalid ticker '{t}'.", type="negative")
                    return
                for lot in lots:
                    if not isinstance(lot, dict) or not {"shares", "buy_price", "purchase_date"}.issubset(lot.keys()):
                        ui.notify(f"Invalid lot for {t}.", type="negative")
                        return
                    if not isinstance(lot["shares"], (int, float)) or lot["shares"] <= 0:
                        ui.notify(f"Invalid shares for {t}.", type="negative")
                        return
                    if not isinstance(lot["buy_price"], (int, float)) or lot["buy_price"] <= 0:
                        ui.notify(f"Invalid buy_price for {t}.", type="negative")
                        return
            portfolio.clear()
            portfolio.update(data)
            stored = load_portfolio()
            stored["portfolio"] = portfolio
            save_portfolio(stored)
            ui.notify("Portfolio imported.", type="positive")
            if on_mutation and on_mutation.get("fn"):
                await on_mutation["fn"]()
            positions_list.refresh()
        except Exception:
            ui.notify("Could not read the file.", type="negative")

    import_upload = ui.upload(
        auto_upload=True,
        on_upload=on_import_upload,
    ).props('accept=".json"').style("display:none;")

    def on_export():
        if not portfolio:
            ui.notify("No positions to export.", type="warning")
            return
        ui.download(json.dumps(portfolio, indent=2).encode(), "portfolio.json")
        ui.notify("Portfolio exported.", type="positive")

    def on_load_sample():
        with ui.dialog() as dialog, ui.card().style(_dlg_card_style):
            ui.label("Load Sample Portfolio?").style(
                f"font-weight:600;font-size:14px;color:{TEXT_PRIMARY};margin-bottom:4px;"
            )
            ui.label("This replaces your current portfolio with example data.").style(
                f"font-size:12px;color:{TEXT_MUTED};line-height:1.5;"
            )
            with ui.row().classes("w-full justify-end gap-2").style("margin-top:12px;"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps").style(_dlg_cancel_style)

                async def do_load(d=dialog):
                    with open(_SAMPLE_PATH) as f:
                        sample = json.load(f)
                    portfolio.clear()
                    portfolio.update(sample)
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    ui.notify("Sample portfolio loaded.", type="positive")
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()
                    positions_list.refresh()

                ui.button("Load Sample", on_click=do_load).props("flat no-caps").style(_dlg_accent_style)
        dialog.open()

    def on_clear_all():
        if not portfolio:
            ui.notify("Portfolio is already empty.", type="info")
            return
        with ui.dialog() as dialog, ui.card().style(_dlg_card_style):
            ui.label("Clear All Positions?").style(
                f"font-weight:600;font-size:14px;color:{TEXT_PRIMARY};margin-bottom:4px;"
            )
            ui.label("This will delete all positions. This cannot be undone.").style(
                f"font-size:12px;color:{TEXT_MUTED};line-height:1.5;"
            )
            with ui.row().classes("w-full justify-end gap-2").style("margin-top:12px;"):
                ui.button("Cancel", on_click=dialog.close).props("flat no-caps").style(_dlg_cancel_style)

                async def do_clear(d=dialog):
                    portfolio.clear()
                    stored = load_portfolio()
                    stored["portfolio"] = portfolio
                    save_portfolio(stored)
                    d.close()
                    ui.notify("Portfolio cleared.", type="info")
                    if on_mutation and on_mutation.get("fn"):
                        await on_mutation["fn"]()
                    positions_list.refresh()

                ui.button("Clear All", on_click=do_clear).props("flat no-caps").style(_dlg_danger_style)
        dialog.open()

    _action_btn_style = (
        f"border:1px solid {BORDER_SUBTLE}; border-radius:6px; padding:6px 0;"
        f" color:{TEXT_MUTED} !important; font-size:11px; text-transform:none;"
        f" width:100%; justify-content:center;"
    )

    with ui.column().classes("w-full").style("gap:6px;"):
        ui.button(
            "Import Portfolio", icon="upload",
            on_click=lambda: ui.run_javascript(
                f'document.getElementById("c{import_upload.id}").querySelector("input").click()'
            ),
        ).props('flat no-caps').classes("w-full").style(_action_btn_style)

        _sample_btn = ui.button(
            "Load Sample", icon="science",
            on_click=on_load_sample,
        ).props('flat no-caps').classes("w-full").style(_action_btn_style)
        _sample_btn.props('id="btn-load-sample"')

        ui.button(
            "Clear All", icon="delete_outline",
            on_click=on_clear_all,
        ).props('flat no-caps').classes("w-full").style(
            _action_btn_style.replace(f"color:{TEXT_MUTED}", f"color:{TEXT_DIM}")
        )
