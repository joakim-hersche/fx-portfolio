# Team 4: Positions & Sidebar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add analyst target price column to positions table, editable positions dialog in sidebar, and error state handling for delisted/unavailable tickers.

**Architecture:** Modifications to `src/ui/positions.py` (target price column), `src/ui/sidebar.py` (edit dialog), and graceful error handling across UI modules. All changes are additive to existing rendering functions.

**Tech Stack:** NiceGUI, HTML/CSS

**Spec:** `docs/superpowers/specs/2026-03-19-feature-expansion-design.md` — Sections 4, 7, 9F

**Prerequisite:** Team 0 (data_fetch changes) must be complete — this plan consumes `Target Price` from `fetch_fundamentals()`.

---

## File Map

- **Modify:** `src/ui/positions.py:151-164` — Add "Target" column to positions table
- **Modify:** `src/ui/positions.py:175-232` — Add target price cell to each row
- **Modify:** `src/ui/sidebar.py:335-375` — Add edit icon/handler to position pills
- **Modify:** `src/ui/sidebar.py` — Add edit dialog function
- **Modify:** `src/ui/positions.py` — Add error state rendering for delisted tickers
- **Modify:** `src/ui/sidebar.py` — Add warning icon for delisted tickers
- **Modify:** `src/excel_export.py` — Add Target Price column to Positions sheet

---

### Task 1: Add Analyst Target Price Column

**Files:**
- Modify: `src/ui/positions.py:151-164`
- Modify: `src/ui/positions.py:175-232`

- [ ] **Step 1: Read positions.py to understand table structure**

Read `src/ui/positions.py` lines 140-240 to understand how the HTML table is built.

- [ ] **Step 2: Add "Target" to column definitions**

In the columns list (around line 151-164), add `"Target"` after `"Current Price"`:

```python
columns = [
    "Ticker", "Company", "Lot", "Shares",
    "Buy Price", "Purchase Date", "Current Price", "Target",
    "Total Value", "Dividends", "Day P&L",
    "Return (%)", "Share (%)",
]
```

- [ ] **Step 3: Add target price cell to row rendering**

In the row rendering loop (around lines 175-232), after the Current Price cell, add the target price cell. The target price data comes from `fetch_fundamentals()` which should be called and cached somewhere accessible.

```python
# Get target price for this ticker
target = fund_data.get(ticker, {}).get("Target Price")
current_price = row.get("Current Price", 0)

if target and current_price and current_price > 0:
    upside = (target - current_price) / current_price * 100
    if upside > 10:
        badge_class = "td-pos"
        badge_text = f"+{upside:.0f}%"
    elif upside >= 0:
        badge_class = "td-amb"
        badge_text = f"+{upside:.0f}%"
    else:
        badge_class = "td-neg"
        badge_text = f"{upside:.0f}%"
    target_cell = f'{currency} {target:,.2f} <span class="{badge_class}" style="font-size:10px;margin-left:4px;">{badge_text}</span>'
else:
    target_cell = "—"
```

Add this as a `<td>` in the row HTML.

- [ ] **Step 4: Ensure fundamentals data is available in positions tab**

Read how `build_positions_tab()` currently fetches data. If it doesn't fetch fundamentals, add a parallel fetch for `fetch_fundamentals()` per ticker (same pattern as risk tab).

- [ ] **Step 5: Run app to verify**

Run: `python main.py`
Expected: Positions table shows "Target" column with consensus price and colored upside/downside badge.

- [ ] **Step 6: Commit**

```bash
git add src/ui/positions.py
git commit -m "feat: add analyst target price column to positions table"
```

---

### Task 2: Add Target Price to Excel Export

**Files:**
- Modify: `src/excel_export.py`

- [ ] **Step 1: Read `_sheet_positions()` in excel_export.py**

Find the function and understand the current column layout.

- [ ] **Step 2: Add "Target Price" and "Upside/Downside %" columns**

After the "Current Price" column, add two new columns:
- "Target Price" — raw target price value
- "Upside %" — formula: `=(TargetPrice - CurrentPrice) / CurrentPrice * 100`

Apply conditional formatting: green for positive, red for negative.

- [ ] **Step 3: Commit**

```bash
git add src/excel_export.py
git commit -m "feat: add target price columns to excel positions sheet"
```

---

### Task 3: Editable Positions Dialog

**Files:**
- Modify: `src/ui/sidebar.py:335-375`

- [ ] **Step 1: Read the position pills rendering**

Read `src/ui/sidebar.py` lines 335-375 to understand the current pill layout and click handlers.

- [ ] **Step 2: Add edit icon to position pills**

Modify the pill rendering to include a small pencil icon (✎ or ✏) that opens the edit dialog:

```python
# Inside the pill HTML, add an edit button
edit_icon = f'<span style="cursor:pointer;margin-left:auto;color:{TEXT_FAINT};font-size:12px;" title="Edit">✎</span>'
```

- [ ] **Step 3: Implement the edit dialog function**

Add to `src/ui/sidebar.py`:

```python
async def _open_edit_dialog(ticker: str, lot_index: int, portfolio: dict, on_mutation) -> None:
    """Open a dialog to edit a specific lot."""
    lot = portfolio[ticker][lot_index]

    with ui.dialog() as dialog, ui.card().style(f"background:{BG_CARD};min-width:350px;"):
        ui.label(f"Edit {ticker} — Lot {lot_index + 1}").style(f"color:{TEXT_PRIMARY};font-size:16px;font-weight:600;")

        shares_input = ui.number("Shares", value=lot["shares"], min=0.01, step=0.01)
        price_input = ui.number("Buy Price", value=lot.get("buy_price", 0), min=0.01, step=0.01)
        date_input = ui.input("Purchase Date", value=lot.get("purchase_date", ""))

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            async def _save():
                lot["shares"] = shares_input.value
                lot["buy_price"] = price_input.value
                if date_input.value:
                    lot["purchase_date"] = date_input.value
                save_portfolio({"portfolio": portfolio, "currency": _shared["currency"]})
                dialog.close()
                await on_mutation()

            async def _delete():
                portfolio[ticker].pop(lot_index)
                if not portfolio[ticker]:
                    del portfolio[ticker]
                save_portfolio({"portfolio": portfolio, "currency": _shared["currency"]})
                dialog.close()
                await on_mutation()

            ui.button("Delete", on_click=_delete, color="red").props("flat")
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=_save).props("flat")

    dialog.open()
```

- [ ] **Step 4: Wire edit icon click to the dialog**

In the position pill rendering, attach the edit dialog open handler. For multi-lot tickers, show a lot picker first (simple select dropdown in a small dialog).

- [ ] **Step 5: Run app to verify**

Run: `python main.py`
Expected: Clicking the edit icon on a position pill opens the edit dialog. Saving or deleting updates the portfolio and rebuilds all tabs.

- [ ] **Step 6: Commit**

```bash
git add src/ui/sidebar.py
git commit -m "feat: add editable positions dialog in sidebar"
```

---

### Task 4: Error State for Delisted Stocks

**Files:**
- Modify: `src/ui/sidebar.py`
- Modify: `src/ui/positions.py`

- [ ] **Step 1: Add error detection in data fetching**

When `fetch_fundamentals()` or `fetch_price_history_short()` returns empty/error for a ticker, mark it as "unavailable". This can be tracked in a set passed through the shared state.

```python
# In the data fetching section of each tab builder
unavailable_tickers = set()
for ticker in tickers:
    try:
        fund = fetch_fundamentals(ticker)
        if not fund or fund.get("Current Price") is None:
            unavailable_tickers.add(ticker)
    except Exception:
        unavailable_tickers.add(ticker)
```

- [ ] **Step 2: Add warning icon to sidebar position pills**

In the pill rendering, check if the ticker is in the unavailable set:

```python
if ticker in unavailable_tickers:
    warning_icon = f'<span style="color:{AMBER};margin-left:4px;" title="Data unavailable">⚠</span>'
else:
    warning_icon = ""
```

- [ ] **Step 3: Add error badge to positions table rows**

In the row rendering, for unavailable tickers, show an amber "Data unavailable" badge:

```python
if ticker in unavailable_tickers:
    # Show available data with warning badge
    status_badge = f'<span style="background:{AMBER};color:white;padding:2px 6px;border-radius:3px;font-size:10px;">Data unavailable</span>'
```

- [ ] **Step 4: Add footnote to risk/income tabs**

When unavailable tickers are excluded from calculations, show at the bottom:

```python
if unavailable_tickers:
    excluded = ", ".join(sorted(unavailable_tickers))
    ui.label(f"{len(unavailable_tickers)} ticker(s) excluded due to missing data: {excluded}").style(
        f"color: {AMBER}; font-size: 11px; margin-top: 12px;"
    )
```

- [ ] **Step 5: Run app to verify**

Test with a known delisted ticker (e.g., add a position for a ticker that no longer exists). Expected: warning icon in sidebar, amber badge in positions table, footnote in risk tab.

- [ ] **Step 6: Commit**

```bash
git add src/ui/sidebar.py src/ui/positions.py
git commit -m "feat: add error state handling for delisted/unavailable tickers"
```
