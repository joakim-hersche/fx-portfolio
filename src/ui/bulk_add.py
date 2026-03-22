"""Bulk Add Positions dialog — add multiple positions at once."""

import re
from dataclasses import dataclass, field
from datetime import datetime

from src.data_fetch import load_stock_options


def parse_date(raw: str) -> str | None:
    """Parse a date string in various formats, return YYYY-MM-DD or None.

    Priority: ISO > European (DD.MM, DD/MM, DD-MM) > US (MM/DD).
    Disambiguation: if both values <= 12, defaults to European (DD/MM)
    since the app targets European investors.
    """
    if not raw or not raw.strip():
        return None
    raw = raw.strip()

    # ISO format: YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        return _validate_and_format(y, mo, d)

    # Separated format: A.B.C or A/B/C or A-B-C (non-ISO)
    # Backreference \2 enforces consistent separator; year must be exactly 2 or 4 digits
    m = re.match(r"^(\d{1,2})([./\-])(\d{1,2})\2(\d{4}|\d{2})$", raw)
    if m:
        a, b, c = int(m[1]), int(m[3]), int(m[4])
        year = c if c > 99 else 2000 + c

        # If first value > 12, it must be a day (European: DD/MM/YYYY)
        if a > 12:
            return _validate_and_format(year, b, a)
        # If second value > 12, it must be a day — so first is month (US: MM/DD/YYYY)
        if b > 12:
            return _validate_and_format(year, a, b)
        # Both <= 12: default European (DD/MM/YYYY)
        return _validate_and_format(year, b, a)

    return None


def _validate_and_format(year: int, month: int, day: int) -> str | None:
    """Validate date components and return YYYY-MM-DD string or None."""
    try:
        dt = datetime(year, month, day)
        return dt.strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None


def format_date_confirm(iso_date: str) -> str:
    """Convert YYYY-MM-DD to human-readable 'D-Mon-YYYY' for confirmation."""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return f"{dt.day}-{dt.strftime('%b')}-{dt.year}"
    except (ValueError, TypeError):
        return "Invalid"


# ---------------------------------------------------------------------------
# Ticker resolution
# ---------------------------------------------------------------------------

_ALT_ASSET_LISTS = {"Crypto", "Commodities"}


@dataclass
class TickerMatch:
    status: str  # "resolved" | "ambiguous" | "not_found"
    ticker: str | None = None
    label: str | None = None
    is_alt: bool = False
    market: str | None = None
    matches: list[dict] = field(default_factory=list)


def resolve_ticker(query: str) -> TickerMatch:
    """Resolve a user query to a ticker symbol.

    Checks cached stock option lists first (exact symbol, then fuzzy name).
    Falls back to yfinance validation if no cached match.
    """
    query = query.strip()
    if not query:
        return TickerMatch(status="not_found")

    options = load_stock_options()
    query_upper = query.upper()
    query_lower = query.lower()

    # Pass 1: exact symbol match
    for market, tickers in options.items():
        if query_upper in tickers:
            return TickerMatch(
                status="resolved",
                ticker=query_upper,
                label=tickers[query_upper],
                is_alt=market in _ALT_ASSET_LISTS,
                market=market,
            )

    # Pass 2: fuzzy name search
    matches = []
    for market, tickers in options.items():
        for symbol, label in tickers.items():
            if query_lower in label.lower() or query_lower in symbol.lower():
                matches.append({
                    "ticker": symbol,
                    "label": label,
                    "market": market,
                    "is_alt": market in _ALT_ASSET_LISTS,
                })

    if len(matches) == 1:
        m = matches[0]
        return TickerMatch(
            status="resolved",
            ticker=m["ticker"],
            label=m["label"],
            is_alt=m["is_alt"],
            market=m["market"],
        )
    if len(matches) > 1:
        return TickerMatch(status="ambiguous", matches=matches)

    # Pass 3: yfinance fallback
    name = _validate_via_yfinance(query_upper)
    if name:
        return TickerMatch(
            status="resolved",
            ticker=query_upper,
            label=f"{name} ({query_upper})",
            is_alt=False,
        )

    return TickerMatch(status="not_found")


def _validate_via_yfinance(ticker: str) -> str | None:
    """Check if a ticker exists on Yahoo Finance. Returns company name or None."""
    from src.data_fetch import get_provider

    try:
        hist = get_provider().get_price_history_short(ticker)
        if hist.empty:
            return None
        info = get_provider().get_fundamentals(ticker)
        return info.get("shortName") or ticker
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Row state model
# ---------------------------------------------------------------------------


@dataclass
class BulkRow:
    """State model for one row in the bulk-add table."""

    index: int
    ticker_input: str = ""
    resolved_ticker: str | None = None
    resolved_label: str | None = None
    ticker_status: str = "pending"  # pending | resolved | ambiguous | not_found
    is_alt: bool = False
    market: str | None = None
    ambiguous_matches: list[dict] = field(default_factory=list)

    shares: float = 0.0
    date_input: str = ""
    parsed_date: str | None = None
    price: float | None = None
    price_status: str = "idle"  # idle | loading | fetched | failed
    buy_fx_rate: float | None = None
    manual_price: bool = False
    _cancelled: bool = False  # for cancelling in-flight fetches

    def is_empty(self) -> bool:
        return not self.ticker_input.strip()

    def is_ready(self) -> bool:
        """True if this row can be submitted."""
        if self.ticker_status != "resolved":
            return False
        if self.is_alt:
            return self.shares > 0 and self.price is not None and self.price > 0
        return self.shares > 0 and self.price is not None

    def to_lot(self) -> dict:
        """Convert to the portfolio lot structure."""
        shares = self.shares
        if self.is_alt and self.price and self.price > 0:
            shares = round(self.shares / self.price, 6)
        return {
            "shares": shares,
            "buy_price": self.price or 0.0,
            "buy_fx_rate": self.buy_fx_rate or 1.0,
            "purchase_date": self.parsed_date,
            "manual_price": self.manual_price,
        }

    def reset_resolution(self):
        """Clear derived state when ticker input changes. Preserves shares and date."""
        self.resolved_ticker = None
        self.resolved_label = None
        self.ticker_status = "pending"
        self.is_alt = False
        self.market = None
        self.ambiguous_matches = []
        self.price = None
        self.price_status = "idle"
        self.buy_fx_rate = None
        self.manual_price = False
        self._cancelled = True  # cancel any in-flight fetches


# ---------------------------------------------------------------------------
# Dialog UI
# ---------------------------------------------------------------------------

import asyncio

from nicegui import app, run, ui

from src.billing import FREE_POSITION_LIMIT, is_pro
from src.fx import get_fx_rate, get_historical_fx_rate, get_ticker_currency
from src.portfolio import fetch_buy_price
from src.theme import (
    ACCENT,
    AMBER,
    BG_CARD,
    BG_INPUT,
    BORDER,
    BORDER_INPUT,
    GREEN,
    RED,
    TEXT_DIM,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)
from src.ui.shared import load_portfolio, save_portfolio

_INITIAL_ROWS = 5

# Shared styles
_INPUT_STYLE = (
    f"background:{BG_INPUT}; border:1px solid {BORDER_INPUT}; border-radius:6px;"
    f" color:{TEXT_PRIMARY}; font-size:13px;"
)
_HEADER_CELL_STYLE = (
    f"font-size:10px; font-weight:600; color:{TEXT_MUTED}; letter-spacing:0.08em;"
    " text-transform:uppercase; white-space:nowrap; padding:0;"
)


def _row_bg(row: BulkRow) -> str:
    if row.ticker_status == "ambiguous":
        return "rgba(217,119,6,0.08)"
    if row.ticker_status == "not_found":
        return "rgba(220,38,38,0.08)"
    return "transparent"


# ---------------------------------------------------------------------------
# Price + FX fetching
# ---------------------------------------------------------------------------


async def _fetch_price_and_fx(row: BulkRow, base_currency: str):
    """Fetch price and FX rate in parallel, update row state."""
    row.price_status = "loading"
    row._cancelled = False
    _update_price_cell(row)

    try:
        ticker_ccy = await run.io_bound(get_ticker_currency, row.resolved_ticker)

        price_task = run.io_bound(fetch_buy_price, row.resolved_ticker, row.parsed_date)
        if ticker_ccy == base_currency:

            async def _unity():
                return 1.0

            fx_task = _unity()
        elif row.parsed_date:
            fx_task = run.io_bound(
                get_historical_fx_rate, ticker_ccy, base_currency, row.parsed_date
            )
        else:

            async def _get_fx():
                rate, _ = await run.io_bound(get_fx_rate, ticker_ccy, base_currency)
                return rate

            fx_task = _get_fx()

        price_result, fx_rate = await asyncio.gather(price_task, fx_task)

        if row._cancelled:
            return

        if price_result is None:
            row.price_status = "failed"
        else:
            row.price = price_result[0]
            row.price_status = "fetched"
            row.buy_fx_rate = fx_rate
    except Exception:
        if not row._cancelled:
            row.price_status = "failed"

    _update_price_cell(row)
    _update_footer(row)


# ---------------------------------------------------------------------------
# Cell update helpers (mutate existing UI elements stored on row)
# ---------------------------------------------------------------------------


def _update_confirm_cell(row: BulkRow):
    """Update the ticker confirmation container for a row."""
    container = getattr(row, "ui_confirm_container", None)
    if container is None:
        return
    container.clear()
    with container:
        if row.ticker_status == "resolved":
            ui.html(
                f'<span style="color:{GREEN}; font-size:13px;" '
                f'title="{row.resolved_label or row.resolved_ticker}">'
                f"&#10003; {row.resolved_label or row.resolved_ticker}</span>"
            )
        elif row.ticker_status == "ambiguous":
            options = {
                m["ticker"]: f'{m["ticker"]} — {m["label"]}'
                for m in row.ambiguous_matches
            }
            sel = ui.select(
                options=options,
                label="Pick one...",
                on_change=lambda e, r=row: _on_disambiguate(r, e.value),
            ).props("dense borderless dark options-dense").style(
                f"min-width:170px; font-size:12px; color:{AMBER};"
                f" background:{BG_INPUT}; border:1px solid rgba(217,119,6,0.4);"
                f" border-radius:6px;"
            )
        elif row.ticker_status == "not_found":
            ui.html(
                f'<span style="color:{RED}; font-size:12px;">'
                f"&#10007; Not found</span>"
            )


def _update_price_cell(row: BulkRow):
    """Update the price container for a row."""
    container = getattr(row, "ui_price_container", None)
    if container is None:
        return
    container.clear()
    with container:
        if row.price_status == "loading":
            ui.spinner("dots", size="sm").style(f"color:{ACCENT};")
        elif row.price_status == "fetched":
            ui.html(
                f'<span style="color:{GREEN}; font-size:13px;">'
                f"&#10003; {row.price:.2f}</span>"
            )
        elif row.price_status == "failed":
            inp = ui.number(
                placeholder="Enter price",
                value=None,
                min=0.01,
                on_change=lambda e, r=row: _on_manual_price(r, e.value),
            ).props("dense borderless"
            ).style(f"width:100px; {_INPUT_STYLE} padding:6px 10px;")
            row.manual_price = True


def _update_row_bg(row: BulkRow):
    """Update a row's background color."""
    el = getattr(row, "ui_row_element", None)
    if el is None:
        return
    el.style(
        f"background:{_row_bg(row)}; padding:10px 0;"
        " align-items:center; gap:8px; width:100%;"
        " border-bottom:1px solid rgba(255,255,255,0.04);"
    )


def _update_footer(row: BulkRow):
    """Re-render the footer status and button state. row is any row (we use _footer_refs)."""
    refs = getattr(row, "_footer_refs", None)
    if refs is None:
        return
    rows = refs["rows"]
    status_html_el = refs["status_html"]
    submit_btn = refs["submit_btn"]

    ready = sum(1 for r in rows if r.is_ready())
    total = sum(1 for r in rows if not r.is_empty())
    errors = sum(1 for r in rows if r.ticker_status == "not_found")
    ambiguous = sum(1 for r in rows if r.ticker_status == "ambiguous")
    loading = sum(1 for r in rows if r.price_status == "loading")

    parts = []
    if ready:
        parts.append(f'<span style="color:{GREEN};">{ready} ready</span>')
    if ambiguous:
        parts.append(f'<span style="color:{AMBER};">{ambiguous} ambiguous</span>')
    if errors:
        parts.append(f'<span style="color:{RED};">{errors} not found</span>')
    if loading:
        parts.append(f'<span style="color:{TEXT_MUTED};">{loading} loading</span>')
    if not parts:
        parts.append(f'<span style="color:{TEXT_DIM};">No positions yet</span>')

    status_html_el.content = (
        f'<div style="font-size:12px; display:flex; gap:10px; align-items:center;">'
        + " &middot; ".join(parts)
        + "</div>"
    )

    submit_btn.text = f"Add {ready} Position{'s' if ready != 1 else ''}"
    if ready > 0:
        submit_btn.props(remove="disable")
    else:
        submit_btn.props("disable")


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _on_manual_price(row: BulkRow, value):
    """Handle manual price input for failed price fetches."""
    try:
        row.price = float(value) if value else None
    except (ValueError, TypeError):
        row.price = None
    _update_footer(row)


def _on_disambiguate(row: BulkRow, ticker: str):
    """Handle disambiguation select change."""
    if not ticker:
        return
    match = next((m for m in row.ambiguous_matches if m["ticker"] == ticker), None)
    if not match:
        return
    row.resolved_ticker = match["ticker"]
    row.resolved_label = match["label"]
    row.ticker_status = "resolved"
    row.is_alt = match.get("is_alt", False)
    row.market = match.get("market")
    _update_confirm_cell(row)
    _update_row_bg(row)
    _update_footer(row)
    # Trigger price fetch if date is available
    if row.parsed_date:
        base_currency = getattr(row, "_base_currency", "USD")
        asyncio.ensure_future(_fetch_price_and_fx(row, base_currency))


async def _on_ticker_change(row: BulkRow, value: str, base_currency: str):
    """Handle ticker input change: resolve and update UI."""
    value = (value or "").strip()
    if value == row.ticker_input and row.ticker_status != "pending":
        return  # no change
    row.ticker_input = value
    if not value:
        row.reset_resolution()
        _update_confirm_cell(row)
        _update_price_cell(row)
        _update_row_bg(row)
        _update_footer(row)
        return

    row.reset_resolution()
    row._cancelled = False  # allow THIS call's result to land
    row.ticker_input = value
    _update_confirm_cell(row)  # clear while resolving

    result = await run.io_bound(resolve_ticker, value)

    if row._cancelled:
        return  # user re-edited

    row.ticker_status = result.status
    row.resolved_ticker = result.ticker
    row.resolved_label = result.label
    row.is_alt = result.is_alt
    row.market = result.market
    row.ambiguous_matches = result.matches

    _update_confirm_cell(row)
    _update_row_bg(row)
    _update_footer(row)

    # Auto-fetch price if resolved and date is set
    if row.ticker_status == "resolved" and row.parsed_date:
        await _fetch_price_and_fx(row, base_currency)


async def _on_date_change(row: BulkRow, value: str, base_currency: str):
    """Handle date input change: parse and trigger price fetch."""
    row.date_input = (value or "").strip()
    row.parsed_date = parse_date(row.date_input) if row.date_input else None

    date_label = getattr(row, "ui_date_confirm", None)
    if date_label is not None:
        if row.parsed_date:
            date_label.text = format_date_confirm(row.parsed_date)
            date_label.style(f"color:{GREEN}; font-size:12px; white-space:nowrap;")
        elif row.date_input:
            date_label.text = "Invalid"
            date_label.style(f"color:{RED}; font-size:12px; white-space:nowrap;")
        else:
            date_label.text = ""

    # Re-fetch price if ticker is resolved
    if row.ticker_status == "resolved" and row.parsed_date:
        row._cancelled = True  # cancel previous fetch
        row._cancelled = False
        await _fetch_price_and_fx(row, base_currency)
    _update_footer(row)


def _on_shares_change(row: BulkRow, value):
    """Handle shares input change."""
    try:
        row.shares = float(value) if value else 0.0
    except (ValueError, TypeError):
        row.shares = 0.0
    _update_footer(row)


# ---------------------------------------------------------------------------
# Row rendering
# ---------------------------------------------------------------------------


def _render_row(row: BulkRow, rows: list[BulkRow], base_currency: str,
                table_body, footer_refs: dict):
    """Render a single row inside the table body. Stores UI refs on the row."""
    row._base_currency = base_currency
    row._footer_refs = footer_refs

    row_el = ui.row().style(
        f"background:{_row_bg(row)}; padding:10px 0;"
        f" align-items:center; gap:8px; width:100%;"
        f" border-bottom:1px solid rgba(255,255,255,0.04);"
    )
    row.ui_row_element = row_el

    with row_el:
        # Row number
        ui.label(str(row.index)).style(
            f"color:{TEXT_DIM}; font-size:13px; min-width:28px; text-align:left;"
        )

        # Ticker input — debounce=500 so on_change fires 500ms after user stops typing
        ticker_inp = ui.input(
            placeholder="Type or paste...",
            value=row.ticker_input,
            on_change=lambda e, r=row: asyncio.ensure_future(
                _on_ticker_change(r, e.value, base_currency)
            ),
        ).props("dense borderless debounce=500"
        ).classes("bulk-ticker-input").style(
            f"min-width:170px; {_INPUT_STYLE} padding:6px 10px;"
        )

        # Confirm container
        confirm_container = ui.element("div").style(
            "min-width:200px; display:flex; align-items:center; overflow:hidden;"
        )
        row.ui_confirm_container = confirm_container

        # Shares input
        shares_inp = ui.number(
            placeholder="—",
            value=row.shares if row.shares else None,
            min=0.01,
            on_change=lambda e, r=row: _on_shares_change(r, e.value),
        ).props("dense borderless"
        ).style(f"width:90px; {_INPUT_STYLE} padding:6px 10px;")

        # Date input — debounce=500 so on_change fires after user stops typing
        date_inp = ui.input(
            placeholder="DD/MM/YYYY",
            value=row.date_input,
            on_change=lambda e, r=row: asyncio.ensure_future(
                _on_date_change(r, e.value, base_currency)
            ),
        ).props("dense borderless debounce=500"
        ).style(f"min-width:110px; {_INPUT_STYLE} padding:6px 10px;")

        # Date confirm label
        date_confirm = ui.label("").style(
            f"color:{TEXT_DIM}; font-size:12px; min-width:100px; white-space:nowrap;"
        )
        row.ui_date_confirm = date_confirm

        # Price container
        price_container = ui.element("div").style(
            "min-width:100px; display:flex; align-items:center; justify-content:flex-end;"
        )
        row.ui_price_container = price_container

        # Remove button
        remove_div = ui.element("div").style(
            f"cursor:pointer; color:{TEXT_MUTED}; font-size:15px; line-height:1;"
            " padding:2px 4px; user-select:none;"
        )
        remove_div.on(
            "click",
            lambda _, r=row: _remove_row(r, rows, table_body, base_currency, footer_refs),
        )
        with remove_div:
            ui.html("&times;")


def _remove_row(row: BulkRow, rows: list[BulkRow], table_body,
                base_currency: str, footer_refs: dict):
    """Remove a row and rebuild the table."""
    if len(rows) <= 1:
        return  # keep at least one row
    rows.remove(row)
    # Re-index
    for i, r in enumerate(rows, 1):
        r.index = i
    _rebuild_table(rows, table_body, base_currency, footer_refs)


def _add_empty_row(rows: list[BulkRow], table_body, base_currency: str,
                   footer_refs: dict):
    """Add a new empty row at the end."""
    new_row = BulkRow(index=len(rows) + 1)
    rows.append(new_row)
    with table_body:
        _render_row(new_row, rows, base_currency, table_body, footer_refs)


def _rebuild_table(rows: list[BulkRow], table_body, base_currency: str,
                   footer_refs: dict):
    """Clear and re-render all rows. Used after paste or row deletion."""
    table_body.clear()
    with table_body:
        for row in rows:
            _render_row(row, rows, base_currency, table_body, footer_refs)
    _update_footer_from_refs(footer_refs)


def _update_footer_from_refs(footer_refs: dict):
    """Update footer using the refs dict directly."""
    rows = footer_refs["rows"]
    if rows:
        # Use the first row to trigger footer update (it has _footer_refs)
        _update_footer(rows[0])


# ---------------------------------------------------------------------------
# Close confirmation
# ---------------------------------------------------------------------------


def _maybe_close(dialog, rows: list[BulkRow]):
    """Close the dialog, prompting if there are unsaved rows."""
    non_empty = [r for r in rows if not r.is_empty()]
    if not non_empty:
        dialog.close()
        return

    with ui.dialog() as confirm, ui.card().style(
        f"min-width:min(300px, 90vw); background:{BG_CARD};"
        f" border:1px solid {BORDER}; border-radius:10px;"
    ):
        ui.label(
            f"Discard {len(non_empty)} unsaved row{'s' if len(non_empty) != 1 else ''}?"
        ).style(f"font-weight:600; font-size:14px; color:{TEXT_PRIMARY};")
        with ui.row().classes("w-full justify-between").style("margin-top:12px;"):
            ui.button("Cancel", on_click=confirm.close).props("flat no-caps").style(
                f"color:{TEXT_DIM};"
            )
            ui.button(
                "Discard",
                on_click=lambda: (confirm.close(), dialog.close()),
            ).props("flat no-caps").style(f"color:{RED};")
    confirm.open()


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------


async def _submit(dialog, rows: list[BulkRow], portfolio: dict,
                  base_currency: str, on_complete):
    """Submit all ready rows to the portfolio."""
    ready = [r for r in rows if r.is_ready()]
    if not ready:
        return

    # Free tier limit
    uid = app.storage.user.get("user_id")
    if not is_pro(uid):
        existing_tickers = set(portfolio.keys())
        new_tickers_seen = set()
        capped = []
        for r in ready:
            ticker = r.resolved_ticker
            if ticker in existing_tickers or ticker in new_tickers_seen:
                capped.append(r)
            elif len(existing_tickers) + len(new_tickers_seen) < FREE_POSITION_LIMIT:
                new_tickers_seen.add(ticker)
                capped.append(r)
        ready = capped

    if not ready:
        ui.notify("Free tier position limit reached.", type="warning")
        return

    # Atomic batch add
    additions = {}
    for r in ready:
        additions.setdefault(r.resolved_ticker, []).append(r.to_lot())
    for ticker, lots in additions.items():
        portfolio.setdefault(ticker, []).extend(lots)

    stored = load_portfolio()
    stored["portfolio"] = portfolio
    save_portfolio(stored)

    dialog.close()
    ui.notify(
        f"Added {len(ready)} position{'s' if len(ready) != 1 else ''}.",
        type="positive",
    )
    on_complete()


# ---------------------------------------------------------------------------
# Main dialog entry point
# ---------------------------------------------------------------------------


def open_bulk_add_dialog(portfolio: dict, base_currency: str, on_complete):
    """Open the bulk-add positions dialog."""
    rows: list[BulkRow] = [BulkRow(index=i) for i in range(1, _INITIAL_ROWS + 1)]

    with ui.dialog() as dialog, ui.card().style(
        f"min-width:min(1120px, 95vw); max-width:1120px; background:{BG_CARD};"
        f" border:1px solid {BORDER}; border-radius:10px; padding:0;"
    ):
        dialog.props("persistent maximized=false")

        # ── Header ──
        with ui.row().classes("w-full items-center justify-between").style(
            f"padding:20px 24px 16px; border-bottom:1px solid {BORDER};"
        ):
            with ui.column().style("gap:2px;"):
                ui.label("Bulk Add Positions").style(
                    f"font-size:16px; font-weight:600; color:{TEXT_PRIMARY};"
                )
                ui.label(
                    "Add multiple positions at once. Paste a column of tickers to auto-fill."
                ).style(f"font-size:12px; color:{TEXT_MUTED};")
            ui.button(icon="close", on_click=lambda: _maybe_close(dialog, rows)).props(
                "flat round dense"
            ).style(f"color:{TEXT_MUTED};")

        # ── Scrollable container ──
        scroll_container = ui.column().classes("w-full").style(
            "max-height:60vh; overflow-y:auto; padding:0;"
        )

        with scroll_container:
            # ── Sticky table header ──
            with ui.row().classes("w-full items-center").style(
                f"position:sticky; top:0; z-index:1; background:{BG_CARD};"
                f" padding:12px 24px 8px 24px; gap:8px;"
                f" border-bottom:1px solid {BORDER};"
            ):
                ui.label("#").style(f"{_HEADER_CELL_STYLE} min-width:28px; text-align:left;")
                ui.label("Ticker / Name").style(f"{_HEADER_CELL_STYLE} width:170px;")
                ui.label("Confirmed Match").style(f"{_HEADER_CELL_STYLE} min-width:200px;")
                ui.label("Shares").style(f"{_HEADER_CELL_STYLE} width:90px; text-align:right;")
                ui.label("Purchase Date").style(f"{_HEADER_CELL_STYLE} width:110px;")
                ui.label("Date Confirm").style(f"{_HEADER_CELL_STYLE} min-width:100px;")
                ui.label("Price").style(f"{_HEADER_CELL_STYLE} min-width:100px; text-align:right;")
                ui.label("").style(f"{_HEADER_CELL_STYLE} width:36px;")

            # ── Table body ──
            table_body = ui.column().classes("w-full").style(
                "padding:0 24px 8px 24px; gap:0;"
            )

        # ── Footer ──
        with ui.row().classes("w-full items-center justify-between").style(
            f"padding:16px 24px; border-top:1px solid {BORDER};"
        ):
            with ui.row().classes("items-center").style("gap:12px;"):
                status_html = ui.html(
                    f'<div style="font-size:12px; color:{TEXT_DIM};">No positions yet</div>'
                )

                ui.button(
                    "+ Row",
                    on_click=lambda: _add_empty_row(
                        rows, table_body, base_currency, footer_refs
                    ),
                ).props("flat no-caps dense").style(
                    f"color:{ACCENT}; font-size:12px;"
                )

            with ui.row().classes("items-center").style("gap:8px;"):
                ui.button(
                    "Cancel",
                    on_click=lambda: _maybe_close(dialog, rows),
                ).props("flat no-caps").style(f"color:{TEXT_DIM};")

                submit_btn = ui.button(
                    "Add 0 Positions",
                    on_click=lambda: asyncio.ensure_future(
                        _submit(dialog, rows, portfolio, base_currency, on_complete)
                    ),
                ).props("unelevated no-caps disable").style(
                    f"background:{ACCENT}; color:white; border-radius:6px;"
                    " font-weight:600; font-size:13px;"
                )

        # Build footer refs dict (shared across all rows)
        footer_refs = {
            "rows": rows,
            "status_html": status_html,
            "submit_btn": submit_btn,
        }

        # ── Paste bridge ──
        paste_bridge = ui.element("div").style("display:none;")
        paste_bridge_id = f"c{paste_bridge.id}"

        ui.run_javascript(f"""
            document.addEventListener('paste', function(e) {{
                const active = document.activeElement;
                if (active && active.closest('.bulk-ticker-input')) {{
                    const text = (e.clipboardData || window.clipboardData).getData('text');
                    if (text && text.includes('\\n')) {{
                        e.preventDefault();
                        const bridge = document.getElementById('{paste_bridge_id}');
                        if (bridge) {{
                            bridge.setAttribute('data-paste', text);
                            bridge.dispatchEvent(new Event('paste_bulk'));
                        }}
                    }}
                }}
            }});
        """)

        async def _on_paste(_e):
            text = await ui.run_javascript(
                f'document.getElementById("{paste_bridge_id}").getAttribute("data-paste")'
            )
            if not text:
                return
            lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
            if not lines:
                return

            # Expand rows to fit pasted tickers
            while len(rows) < len(lines):
                rows.append(BulkRow(index=len(rows) + 1))

            for i, line in enumerate(lines):
                rows[i].ticker_input = line
                rows[i].reset_resolution()
                rows[i]._cancelled = False

            _rebuild_table(rows, table_body, base_currency, footer_refs)

            # Resolve all pasted tickers in parallel
            async def _resolve_one(r):
                result = await run.io_bound(resolve_ticker, r.ticker_input)
                if r._cancelled:
                    return
                r.ticker_status = result.status
                r.resolved_ticker = result.ticker
                r.resolved_label = result.label
                r.is_alt = result.is_alt
                r.market = result.market
                r.ambiguous_matches = result.matches
                _update_confirm_cell(r)
                _update_row_bg(r)
                _update_footer(r)

            tasks = [_resolve_one(r) for r in rows[:len(lines)]]
            await asyncio.gather(*tasks)

        paste_bridge.on("paste_bulk", _on_paste)

        # ── Render initial rows ──
        _rebuild_table(rows, table_body, base_currency, footer_refs)

    dialog.open()
