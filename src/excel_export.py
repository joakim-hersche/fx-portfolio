import io
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

# ── Styling constants ──────────────────────────────────────────────────────────

_HEADER_FILL   = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT   = Font(bold=True, color="FFFFFF")
_LABEL_FONT    = Font(bold=True)
_TOTAL_FONT    = Font(bold=True, color="1F4E79")
_GREEN_FILL    = PatternFill("solid", fgColor="C8E6C9")
_RED_FILL      = PatternFill("solid", fgColor="FFCDD2")
_AMBER_FILL    = PatternFill("solid", fgColor="FFF9C4")
_TEMPLATE_FILL = PatternFill("solid", fgColor="E3F2FD")
_TOTAL_FILL    = PatternFill("solid", fgColor="EEF2F7")
_TOP_BORDER    = Border(top=Side(style="medium", color="1F4E79"))

_CURRENCY_FMT = {
    "USD": '"$"#,##0.00',
    "EUR": '"€"#,##0.00',
    "GBP": '"£"#,##0.00',
    "CHF": '"CHF "#,##0.00',
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_headers(ws, headers: list[str]) -> None:
    for col, h in enumerate(headers, 1):
        cell = ws.cell(1, col, h)
        cell.fill      = _HEADER_FILL
        cell.font      = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _autofit(ws) -> None:
    for col in ws.columns:
        width = max((len(str(c.value or "")) for c in col), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(width + 3, 42)


def _freeze_and_filter(ws, freeze_at: str = "A2") -> None:
    ws.freeze_panes    = freeze_at
    ws.auto_filter.ref = ws.dimensions


# ── Sheet builders ─────────────────────────────────────────────────────────────

def _sheet_net_worth(wb: Workbook, kpis: dict, currency: str) -> None:
    """
    First sheet — live net worth summary.
    Portfolio total links to Summary!B4.
    Other Assets total links to 'Other Assets'!F21 (the SUM row).
    Grand total = B4 + B5, updates automatically when user fills Other Assets.
    """
    ws = wb.create_sheet("Net Worth")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    # Banner
    ws.merge_cells("A1:C1")
    banner = ws["A1"]
    banner.value     = "Net Worth Overview"
    banner.font      = Font(bold=True, size=14, color="1F4E79")
    banner.fill      = _TEMPLATE_FILL
    banner.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:C2")
    sub = ws["A2"]
    sub.value     = f"Portfolio values are live from the dashboard. Fill in 'Other Assets' to complete your net worth ({currency})."
    sub.font      = Font(italic=True, size=10, color="595959")
    sub.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 24

    # Table headers (row 3)
    for col, label in enumerate(["Category", "Value", "% of Total"], 1):
        cell       = ws.cell(3, col, label)
        cell.fill  = _HEADER_FILL
        cell.font  = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    # Row 4: Portfolio
    ws["A4"] = "Portfolio (Dashboard)"
    ws["A4"].font = _LABEL_FONT
    ws["B4"] = "=Summary!B4"        # links to Total Portfolio Value
    ws["B4"].number_format = curr_fmt
    ws["C4"] = '=IF(B6=0,"",B4/B6)'
    ws["C4"].number_format = '0.0"%"'

    # Row 5: Other Assets
    ws["A5"] = "Other Assets (Manual)"
    ws["A5"].font = _LABEL_FONT
    ws["B5"] = "='Other Assets'!F21"  # links to SUM row in Other Assets sheet
    ws["B5"].number_format = curr_fmt
    ws["C5"] = '=IF(B6=0,"",B5/B6)'
    ws["C5"].number_format = '0.0"%"'

    # Row 6: Total (bold, blue, border on top)
    for col in range(1, 4):
        ws.cell(6, col).border = _TOP_BORDER
        ws.cell(6, col).fill   = _TOTAL_FILL
        ws.cell(6, col).font   = _TOTAL_FONT

    ws["A6"] = "Total Net Worth"
    ws["B6"] = "=B4+B5"
    ws["B6"].number_format = curr_fmt
    ws["C6"] = '100%'
    ws["C6"].number_format = '0.0"%"'

    # Bar chart: Portfolio vs Other Assets
    chart = BarChart()
    chart.type    = "bar"
    chart.title   = "Net Worth Breakdown"
    chart.style   = 2
    chart.grouping = "clustered"
    chart.y_axis.delete = True
    chart.x_axis.delete = False

    data = Reference(ws, min_col=2, max_col=2, min_row=3, max_row=5)
    cats = Reference(ws, min_col=1, min_row=4, max_row=5)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.width  = 18
    chart.height = 10
    ws.add_chart(chart, "E3")

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 14


def _sheet_summary(wb: Workbook, kpis: dict, currency: str) -> None:
    ws = wb.create_sheet("Summary")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    rows = [
        ("Report Generated",      datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Currency",              currency),
        (None, None),
        ("Total Portfolio Value", kpis["total_value"]),
        ("Today's Change",        kpis["daily_pnl"]),
        ("Cost Basis",            kpis["cost_basis"]),
        ("Dividends Received",    kpis["total_divs"]),
        ("Total Return",          kpis["total_return"]),
        ("Total Return (%)",      kpis["total_ret_pct"]),
        ("Number of Positions",   kpis["n_positions"]),
    ]

    for row_idx, (label, value) in enumerate(rows, 1):
        if label is None:
            continue
        label_cell       = ws.cell(row_idx, 1, label)
        label_cell.font  = _LABEL_FONT

        val_cell           = ws.cell(row_idx, 2, value)
        val_cell.alignment = Alignment(horizontal="right")

        if isinstance(value, float):
            if label.endswith("(%)"):
                val_cell.number_format = '0.00"%"'
            elif label == "Number of Positions":
                val_cell.number_format = "0"
            else:
                val_cell.number_format = curr_fmt

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 20


def _sheet_positions(wb: Workbook, df: pd.DataFrame, name_map: dict, currency: str) -> None:
    ws = wb.create_sheet("Positions")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    export_df = df.copy()
    export_df.insert(1, "Company", export_df["Ticker"].map(name_map))

    col_order = [
        "Ticker", "Company", "Purchase", "Shares",
        "Buy Price", "Purchase Date", "Current Price",
        "Total Value", "Dividends", "Daily P&L",
        "Return (%)", "Weight (%)",
    ]
    export_df = export_df[[c for c in col_order if c in export_df.columns]]

    _write_headers(ws, list(export_df.columns))

    currency_cols = {"Buy Price", "Current Price", "Total Value", "Dividends", "Daily P&L"}
    pct_cols      = {"Return (%)", "Weight (%)"}
    col_letters   = {}
    for col_idx, col_name in enumerate(export_df.columns, 1):
        col_letters[col_name] = get_column_letter(col_idx)

    for row_idx, row in enumerate(export_df.itertuples(index=False), 2):
        for col_idx, (col_name, value) in enumerate(zip(export_df.columns, row), 1):
            cell = ws.cell(row_idx, col_idx, value if pd.notna(value) else None)
            if col_name in currency_cols and isinstance(value, (int, float)):
                cell.number_format = curr_fmt
            elif col_name in pct_cols and isinstance(value, (int, float)):
                cell.number_format = '0.00"%"'
            elif col_name == "Shares" and isinstance(value, (int, float)):
                cell.number_format = "#,##0.######"

    n_rows = len(export_df) + 1
    for col_name in ("Return (%)", "Daily P&L"):
        if col_name in col_letters:
            col_l      = col_letters[col_name]
            data_range = f"{col_l}2:{col_l}{n_rows}"
            ws.conditional_formatting.add(data_range, CellIsRule(operator="greaterThan", formula=["0"], fill=_GREEN_FILL))
            ws.conditional_formatting.add(data_range, CellIsRule(operator="lessThan",    formula=["0"], fill=_RED_FILL))

    _autofit(ws)
    _freeze_and_filter(ws)


def _sheet_allocation(wb: Workbook, df: pd.DataFrame, name_map: dict, currency: str) -> None:
    ws = wb.create_sheet("Allocation")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    alloc = (
        df.groupby("Ticker")["Total Value"]
        .sum()
        .reset_index()
        .sort_values("Total Value", ascending=False)
    )
    alloc["Company"]    = alloc["Ticker"].map(name_map)
    total               = alloc["Total Value"].sum()
    alloc["Weight (%)"] = (alloc["Total Value"] / total * 100).round(2) if total else 0.0
    alloc               = alloc[["Ticker", "Company", "Total Value", "Weight (%)"]]
    n_rows              = len(alloc) + 1

    _write_headers(ws, list(alloc.columns))
    for row_idx, row in enumerate(alloc.itertuples(index=False), 2):
        ws.cell(row_idx, 1, row.Ticker)
        ws.cell(row_idx, 2, row.Company)
        ws.cell(row_idx, 3, row._2).number_format = curr_fmt
        ws.cell(row_idx, 4, row._3).number_format = '0.00"%"'

    # Horizontal bar chart — Weight (%) per Ticker
    chart              = BarChart()
    chart.type         = "bar"   # horizontal
    chart.title        = "Portfolio Allocation"
    chart.style        = 2
    chart.y_axis.title = "Ticker"
    chart.x_axis.title = "Weight (%)"

    data = Reference(ws, min_col=4, max_col=4, min_row=1, max_row=n_rows)
    cats = Reference(ws, min_col=1, min_row=2, max_row=n_rows)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape  = 4
    chart.width  = 20
    chart.height = max(10, len(alloc) * 1.2)
    ws.add_chart(chart, "F2")

    _autofit(ws)
    ws.freeze_panes = "A2"


def _sheet_risk(wb: Workbook, analytics_df: pd.DataFrame, name_map: dict) -> None:
    ws = wb.create_sheet("Risk Metrics")

    if analytics_df.empty:
        ws["A1"] = "Risk data not available — open the Risk & Analytics section in the dashboard first."
        return

    export_df = analytics_df.copy()
    export_df.insert(1, "Company", export_df["Ticker"].map(name_map))
    col_map   = {"Volatility": "Volatility (%)", "Max Drawdown": "Max Drawdown (%)"}
    export_df = export_df.rename(columns=col_map)
    headers   = ["Ticker", "Company", "Volatility (%)", "Max Drawdown (%)", "Sharpe Ratio", "Beta"]
    export_df = export_df[[c for c in headers if c in export_df.columns]]

    _write_headers(ws, list(export_df.columns))
    sharpe_col = None
    for col_idx, col_name in enumerate(export_df.columns, 1):
        if col_name == "Sharpe Ratio":
            sharpe_col = get_column_letter(col_idx)

    for row_idx, row in enumerate(export_df.itertuples(index=False), 2):
        for col_idx, (col_name, value) in enumerate(zip(export_df.columns, row), 1):
            cell = ws.cell(row_idx, col_idx, value if pd.notna(value) else None)
            if col_name in ("Volatility (%)", "Max Drawdown (%)") and isinstance(value, (int, float)):
                cell.number_format = '0.0"%"'
            elif col_name in ("Sharpe Ratio", "Beta") and isinstance(value, (int, float)):
                cell.number_format = "0.00"

    if sharpe_col:
        n_rows     = len(export_df) + 1
        data_range = f"{sharpe_col}2:{sharpe_col}{n_rows}"
        ws.conditional_formatting.add(data_range, CellIsRule(operator="greaterThanOrEqual", formula=["1"],      fill=_GREEN_FILL))
        ws.conditional_formatting.add(data_range, CellIsRule(operator="between",            formula=["0", "1"], fill=_AMBER_FILL))
        ws.conditional_formatting.add(data_range, CellIsRule(operator="lessThan",           formula=["0"],      fill=_RED_FILL))

    _autofit(ws)
    _freeze_and_filter(ws)


def _sheet_fundamentals(wb: Workbook, fund_rows: list[dict], name_map: dict) -> None:
    ws = wb.create_sheet("Fundamentals")

    if not fund_rows:
        ws["A1"] = "Fundamentals data not available — open the Risk & Analytics section in the dashboard first."
        return

    fund_df = pd.DataFrame(fund_rows)
    fund_df.insert(1, "Company", fund_df["Ticker"].map(name_map))
    headers = ["Ticker", "Company", "P/E Ratio", "Div Yield (%)", "1-Year Low", "1-Year High", "1-Year Position (%)"]
    fund_df = fund_df[[c for c in headers if c in fund_df.columns]]

    _write_headers(ws, list(fund_df.columns))
    for row_idx, row in enumerate(fund_df.itertuples(index=False), 2):
        for col_idx, (col_name, value) in enumerate(zip(fund_df.columns, row), 1):
            cell = ws.cell(row_idx, col_idx, value if pd.notna(value) else None)
            if col_name == "P/E Ratio" and isinstance(value, (int, float)):
                cell.number_format = "0.0"
            elif col_name in ("Div Yield (%)", "1-Year Position (%)") and isinstance(value, (int, float)):
                cell.number_format = '0.00"%"'
            elif col_name in ("1-Year Low", "1-Year High") and isinstance(value, (int, float)):
                cell.number_format = "#,##0.00"

    _autofit(ws)
    _freeze_and_filter(ws)


def _sheet_correlation(wb: Workbook, price_histories: dict[str, pd.DataFrame]) -> None:
    ws = wb.create_sheet("Correlation")

    returns = {
        t: h["Close"].pct_change().dropna()
        for t, h in price_histories.items()
        if not h.empty and "Close" in h.columns
    }
    if len(returns) < 2:
        ws["A1"] = "At least 2 positions with price history are needed to compute correlation."
        return

    corr_df = pd.DataFrame(returns).dropna().corr()
    tickers = list(corr_df.columns)

    for col_idx, t in enumerate(tickers, 2):
        cell       = ws.cell(1, col_idx, t)
        cell.fill  = _HEADER_FILL
        cell.font  = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    for row_idx, t_row in enumerate(tickers, 2):
        label       = ws.cell(row_idx, 1, t_row)
        label.fill  = _HEADER_FILL
        label.font  = _HEADER_FONT
        label.alignment = Alignment(horizontal="center")
        for col_idx, t_col in enumerate(tickers, 2):
            cell               = ws.cell(row_idx, col_idx, round(corr_df.loc[t_row, t_col], 4))
            cell.number_format = "0.00"
            cell.alignment     = Alignment(horizontal="center")

    n = len(tickers)
    data_range = f"B2:{get_column_letter(n + 1)}{n + 1}"
    ws.conditional_formatting.add(data_range, ColorScaleRule(
        start_type="num", start_value=-1, start_color="C0392B",
        mid_type="num",   mid_value=0,    mid_color="FFFFFF",
        end_type="num",   end_value=1,    end_color="2E7D32",
    ))

    _autofit(ws)
    ws.freeze_panes = "B2"


def _sheet_price_history(wb: Workbook, price_histories: dict[str, pd.DataFrame]) -> None:
    ws = wb.create_sheet("Price History")

    close_series = {
        t: h["Close"]
        for t, h in price_histories.items()
        if not h.empty and "Close" in h.columns
    }
    if not close_series:
        ws["A1"] = "No price history available."
        return

    pivot       = pd.DataFrame(close_series).sort_index()
    pivot.index = pd.to_datetime(pivot.index).tz_localize(None)
    n_data_rows = len(pivot)
    n_tickers   = len(pivot.columns)

    ws.cell(1, 1, "Date").fill      = _HEADER_FILL
    ws.cell(1, 1).font              = _HEADER_FONT
    ws.cell(1, 1).alignment         = Alignment(horizontal="center")
    for col_idx, t in enumerate(pivot.columns, 2):
        cell           = ws.cell(1, col_idx, t)
        cell.fill      = _HEADER_FILL
        cell.font      = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    for row_idx, (date, row) in enumerate(pivot.iterrows(), 2):
        date_cell               = ws.cell(row_idx, 1, date.to_pydatetime())
        date_cell.number_format = "YYYY-MM-DD"
        for col_idx, value in enumerate(row, 2):
            cell               = ws.cell(row_idx, col_idx, round(float(value), 4) if pd.notna(value) else None)
            cell.number_format = "#,##0.00"

    # Line chart — one series per ticker
    chart              = LineChart()
    chart.title        = "6-Month Price History"
    chart.style        = 2
    chart.y_axis.title = "Price"
    chart.smooth       = True

    for col_idx in range(2, n_tickers + 2):
        data = Reference(ws, min_col=col_idx, max_col=col_idx, min_row=1, max_row=n_data_rows + 1)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n_data_rows + 1)
    chart.set_categories(cats)
    chart.width  = 28
    chart.height = 16
    ws.add_chart(chart, f"A{n_data_rows + 3}")

    _autofit(ws)
    ws.freeze_panes = "B2"


_OTHER_ASSETS_DATA_ROWS = range(3, 21)   # rows 3–20
_OTHER_ASSETS_SUM_ROW   = 21
_OTHER_ASSETS_VALUE_COL = 6              # column F = Current Value


def _sheet_other_assets(wb: Workbook, currency: str) -> None:
    ws       = wb.create_sheet("Other Assets")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    headers = [
        "Asset Name", "Type", "Units / Shares",
        f"Cost Basis ({currency})", "Purchase Date",
        f"Current Value ({currency})", "Notes",
    ]
    n_cols   = len(headers)
    sum_row  = _OTHER_ASSETS_SUM_ROW
    val_col  = _OTHER_ASSETS_VALUE_COL
    cost_col = 4

    # Row 1: instruction banner
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    instruction           = ws.cell(1, 1,
        f"Add your non-market assets below ({currency}). "
        "These rows are not connected to the dashboard — for personal net worth analysis only."
    )
    instruction.fill      = _TEMPLATE_FILL
    instruction.font      = Font(italic=True, color="1F4E79")
    instruction.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30

    # Row 2: column headers
    _write_headers(ws, headers)
    ws.freeze_panes = "A3"

    # Rows 3–20: pre-formatted empty cells
    for row_idx in _OTHER_ASSETS_DATA_ROWS:
        for col_idx in range(1, n_cols + 1):
            cell = ws.cell(row_idx, col_idx)
            if col_idx == cost_col:
                cell.number_format = curr_fmt
            elif col_idx == val_col:
                cell.number_format = curr_fmt
            elif col_idx == 5:
                cell.number_format = "YYYY-MM-DD"

    # Row 21: totals with SUM formulas
    for col_idx in range(1, n_cols + 1):
        cell        = ws.cell(sum_row, col_idx)
        cell.fill   = _TOTAL_FILL
        cell.font   = _TOTAL_FONT
        cell.border = _TOP_BORDER

    ws.cell(sum_row, 1, "Total").font = _TOTAL_FONT
    cost_col_l = get_column_letter(cost_col)
    val_col_l  = get_column_letter(val_col)
    ws.cell(sum_row, cost_col, f"=SUM({cost_col_l}3:{cost_col_l}20)").number_format = curr_fmt
    ws.cell(sum_row, val_col,  f"=SUM({val_col_l}3:{val_col_l}20)").number_format  = curr_fmt

    # Unrealised gain formula column H (col 8) in sum row
    ws.cell(sum_row, 8, f"=F{sum_row}-D{sum_row}").number_format = curr_fmt
    ws.cell(2, 8, "Unrealised Gain").fill      = _HEADER_FILL
    ws.cell(2, 8).font                          = _HEADER_FONT
    ws.cell(2, 8).alignment                     = Alignment(horizontal="center")

    # Per-row unrealised gain formula (col 8, rows 3–20)
    for row_idx in _OTHER_ASSETS_DATA_ROWS:
        cell               = ws.cell(row_idx, 8, f"=IF(F{row_idx}=\"\",\"\",F{row_idx}-D{row_idx})")
        cell.number_format = curr_fmt
        cell.border        = _TOP_BORDER if row_idx == sum_row else cell.border

    # Dropdown for Type column (B3:B20)
    dv = DataValidation(
        type="list",
        formula1='"Real Estate,Private Equity,Cash,Bonds,Other"',
        showDropDown=False,
        showErrorMessage=True,
        errorTitle="Invalid Type",
        error="Choose from: Real Estate, Private Equity, Cash, Bonds, Other",
    )
    ws.add_data_validation(dv)
    dv.sqref = "B3:B20"

    _autofit(ws)
    ws.column_dimensions["A"].width = 35


# ── Public API ─────────────────────────────────────────────────────────────────

def build_excel_report(
    positions_df: pd.DataFrame,
    analytics_df: pd.DataFrame,
    fund_rows: list[dict],
    price_histories: dict[str, pd.DataFrame],
    name_map: dict[str, str],
    currency: str,
    summary_kpis: dict,
) -> bytes:
    """
    Build a comprehensive multi-sheet interactive Excel report.
    Returns raw bytes suitable for st.download_button(data=...).
    """
    wb = Workbook()
    wb.remove(wb.active)  # remove default empty sheet

    builders = [
        ("Net Worth",     lambda: _sheet_net_worth(wb, summary_kpis, currency)),
        ("Summary",       lambda: _sheet_summary(wb, summary_kpis, currency)),
        ("Positions",     lambda: _sheet_positions(wb, positions_df, name_map, currency)),
        ("Allocation",    lambda: _sheet_allocation(wb, positions_df, name_map, currency)),
        ("Risk Metrics",  lambda: _sheet_risk(wb, analytics_df, name_map)),
        ("Fundamentals",  lambda: _sheet_fundamentals(wb, fund_rows, name_map)),
        ("Correlation",   lambda: _sheet_correlation(wb, price_histories)),
        ("Price History", lambda: _sheet_price_history(wb, price_histories)),
        ("Other Assets",  lambda: _sheet_other_assets(wb, currency)),
    ]

    for sheet_name, builder in builders:
        try:
            builder()
        except Exception as exc:
            ws        = wb.create_sheet(sheet_name)
            ws["A1"]  = f"Error generating sheet: {exc}"
            print(f"[excel_export] Sheet '{sheet_name}' failed: {exc}")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
