import io
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule, CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

# ── Styling constants ──────────────────────────────────────────────────────────

_HEADER_FILL   = PatternFill("solid", fgColor="1F4E79")
_HEADER_FONT   = Font(bold=True, color="FFFFFF")
_LABEL_FONT    = Font(bold=True)
_TOTAL_FONT    = Font(bold=True, color="1F4E79")
_INPUT_FONT    = Font(color="1F4E79")           # blue  — user-editable cells
_INPUT_FILL    = PatternFill("solid", fgColor="EBF3FB")
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

_TABLE_STYLE = TableStyleInfo(
    name="TableStyleMedium2",
    showFirstColumn=False, showLastColumn=False,
    showRowStripes=True,   showColumnStripes=False,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _write_headers(ws, headers: list[str], start_row: int = 1) -> None:
    for col, h in enumerate(headers, 1):
        cell           = ws.cell(start_row, col, h)
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


def _add_table(ws, name: str, ref: str) -> None:
    t = Table(displayName=name, ref=ref)
    t.tableStyleInfo = _TABLE_STYLE
    ws.add_table(t)


def _set_print(ws, area: str = None) -> None:
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage   = True
    ws.page_setup.fitToWidth  = 1
    ws.page_setup.fitToHeight = 0
    if area:
        ws.print_area = area


def _input_cell(cell, value, number_format: str = None) -> None:
    """Write a blue-styled editable input cell."""
    cell.value         = value
    cell.font          = _INPUT_FONT
    cell.fill          = _INPUT_FILL
    if number_format:
        cell.number_format = number_format


# ── Sheet builders ─────────────────────────────────────────────────────────────

def _sheet_net_worth(wb: Workbook, kpis: dict, currency: str) -> None:
    ws       = wb.create_sheet("Net Worth")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    # Banner
    ws.merge_cells("A1:C1")
    banner           = ws["A1"]
    banner.value     = "Net Worth Overview"
    banner.font      = Font(bold=True, size=14, color="1F4E79")
    banner.fill      = _TEMPLATE_FILL
    banner.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:C2")
    sub           = ws["A2"]
    sub.value     = (
        f"Portfolio values snapshot from the dashboard. "
        f"Fill in 'Other Assets' to complete your net worth ({currency})."
    )
    sub.font      = Font(italic=True, size=10, color="595959")
    sub.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[2].height = 24

    # Table headers (row 3)
    for col, label in enumerate(["Category", f"Value ({currency})", "% of Total"], 1):
        cell           = ws.cell(3, col, label)
        cell.fill      = _HEADER_FILL
        cell.font      = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    # Row 4: Portfolio — links to Summary!B4 (which is a SUM formula)
    ws["A4"] = "Portfolio (Dashboard)"
    ws["A4"].font = _LABEL_FONT
    ws["B4"] = "=Summary!B4"
    ws["B4"].number_format = curr_fmt
    ws["C4"] = '=IF(B6=0,"",B4/B6)'
    ws["C4"].number_format = '0.0"%"'

    # Row 5: Other Assets — links to Net Equity SUM in Other Assets!H23
    ws["A5"] = "Other Assets (Manual)"
    ws["A5"].font = _LABEL_FONT
    ws["B5"] = "='Other Assets'!H23"
    ws["B5"].number_format = curr_fmt
    ws["C5"] = '=IF(B6=0,"",B5/B6)'
    ws["C5"].number_format = '0.0"%"'

    # Row 6: Total
    for col in range(1, 4):
        c        = ws.cell(6, col)
        c.border = _TOP_BORDER
        c.fill   = _TOTAL_FILL
        c.font   = _TOTAL_FONT
    ws["A6"] = "Total Net Worth"
    ws["B6"] = "=B4+B5"
    ws["B6"].number_format = curr_fmt
    ws["C6"] = "100%"
    ws["C6"].number_format = '0.0"%"'

    # Bar chart
    chart              = BarChart()
    chart.type         = "bar"
    chart.title        = "Net Worth Breakdown"
    chart.style        = 2
    chart.grouping     = "clustered"
    chart.y_axis.delete = True

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
    _set_print(ws, "A1:I12")


def _sheet_summary(wb: Workbook, kpis: dict, currency: str) -> None:
    ws       = wb.create_sheet("Summary")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    # Row 1-2: metadata (hardcoded — snapshot info)
    ws.cell(1, 1, "Report Generated").font = _LABEL_FONT
    ws.cell(1, 2, datetime.now().strftime("%Y-%m-%d %H:%M")).alignment = Alignment(horizontal="right")
    ws.cell(2, 1, "Currency").font = _LABEL_FONT
    ws.cell(2, 2, currency).alignment = Alignment(horizontal="right")

    # Row 4+: live formulas referencing tblPositions
    formula_rows = [
        # (label, formula_or_value, number_format, is_formula)
        ("Total Portfolio Value", "=SUM(Positions!$H:$H)",                                  curr_fmt, True),
        ("Today's Change",        kpis["daily_pnl"],                                        curr_fmt, False),  # needs yesterday's close — hardcoded
        ("Cost Basis",            "=SUMPRODUCT(Positions!$D$2:$D$10000,Positions!$E$2:$E$10000)", curr_fmt, True),
        ("Dividends Received",    "=SUM(Positions!$I:$I)",                                  curr_fmt, True),
        ("Total Return",          "=B4+B7-B6",                                            curr_fmt, True),
        ("Total Return (%)",      '=IF(B6=0,"",B8/B6*100)',                               '0.00"%"', True),
        ("Number of Positions",   kpis["n_positions"],                                    "0",      False),
    ]

    for idx, (label, value, fmt, is_formula) in enumerate(formula_rows, 4):
        ws.cell(idx, 1, label).font = _LABEL_FONT
        cell               = ws.cell(idx, 2, value)
        cell.number_format = fmt
        cell.alignment     = Alignment(horizontal="right")
        if is_formula:
            cell.font = Font(color="000000")  # black = computed

    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 20
    _set_print(ws, "A1:B10")


# Column layout for Positions (must be stable — other sheets reference by name via tblPositions)
_POS_COLS = [
    "Ticker", "Company", "Purchase", "Shares",
    "Buy Price", "Purchase Date", "Current Price",
    "Total Value", "Dividends", "Daily P&L",
    "Return (%)", "Weight (%)",
]
# Map name → 1-based column index
_POS_IDX = {c: i for i, c in enumerate(_POS_COLS, 1)}


def _sheet_positions(wb: Workbook, df: pd.DataFrame, name_map: dict, currency: str) -> None:
    ws       = wb.create_sheet("Positions")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    export_df = df.copy()
    export_df.insert(1, "Company", export_df["Ticker"].map(name_map))
    export_df = export_df[[c for c in _POS_COLS if c in export_df.columns]]

    # Column indices (letters)
    D = get_column_letter(_POS_IDX["Shares"])         # Shares
    E = get_column_letter(_POS_IDX["Buy Price"])      # Buy Price
    G = get_column_letter(_POS_IDX["Current Price"])  # Current Price
    H = get_column_letter(_POS_IDX["Total Value"])    # Total Value
    I = get_column_letter(_POS_IDX["Dividends"])      # Dividends
    K = get_column_letter(_POS_IDX["Return (%)"])     # Return
    L = get_column_letter(_POS_IDX["Weight (%)"])     # Weight

    n            = len(export_df)
    last_data    = n + 1            # last data row (header is row 1)
    totals_row   = last_data + 2    # blank gap then totals

    _write_headers(ws, list(export_df.columns))

    # Blue-input columns: Shares, Buy Price, Current Price
    input_cols = {"Shares", "Buy Price", "Current Price"}

    for row_idx, row in enumerate(export_df.itertuples(index=False), 2):
        for col_idx, (col_name, value) in enumerate(zip(export_df.columns, row), 1):
            cell = ws.cell(row_idx, col_idx)
            safe = value if pd.notna(value) else None

            if col_name == "Total Value":
                cell.value         = f"={D}{row_idx}*{G}{row_idx}"
                cell.number_format = curr_fmt
            elif col_name == "Return (%)":
                cell.value = (
                    f'=IF({E}{row_idx}*{D}{row_idx}=0,"",'
                    f'(({G}{row_idx}*{D}{row_idx}+{I}{row_idx}-{E}{row_idx}*{D}{row_idx})'
                    f'/({E}{row_idx}*{D}{row_idx}))*100)'
                )
                cell.number_format = '0.00"%"'
            elif col_name == "Weight (%)":
                cell.value = (
                    f'=IF(SUM({H}$2:{H}${last_data})=0,"",'
                    f'{H}{row_idx}/SUM({H}$2:{H}${last_data})*100)'
                )
                cell.number_format = '0.00"%"'
            else:
                cell.value = safe
                if col_name in {"Buy Price", "Current Price", "Dividends", "Daily P&L"}:
                    cell.number_format = curr_fmt
                elif col_name == "Shares":
                    cell.number_format = "#,##0.######"

            # Blue styling for editable inputs
            if col_name in input_cols:
                cell.font = _INPUT_FONT
                cell.fill = _INPUT_FILL

    # Conditional formatting: green/red on Return (%) and Daily P&L
    J = get_column_letter(_POS_IDX["Daily P&L"])
    for col_l in (K, J):
        rng = f"{col_l}2:{col_l}{last_data}"
        ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"], fill=_GREEN_FILL))
        ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan",    formula=["0"], fill=_RED_FILL))

    # Totals row
    ws.cell(totals_row, 1, "TOTAL").font = _TOTAL_FONT
    for col_idx in range(1, len(export_df.columns) + 1):
        ws.cell(totals_row, col_idx).fill   = _TOTAL_FILL
        ws.cell(totals_row, col_idx).border = _TOP_BORDER
        ws.cell(totals_row, col_idx).font   = _TOTAL_FONT

    sum_cols = {
        H: curr_fmt,
        I: curr_fmt,
        J: curr_fmt,
    }
    for col_l, fmt in sum_cols.items():
        cell               = ws.cell(totals_row, _POS_IDX[{H: "Total Value", I: "Dividends", J: "Daily P&L"}[col_l]])
        cell.value         = f"=SUM({col_l}2:{col_l}{last_data})"
        cell.number_format = fmt
        cell.font          = _TOTAL_FONT

    # Weighted-average return
    ret_cell               = ws.cell(totals_row, _POS_IDX["Return (%)"])
    ret_cell.value         = f'=IF(SUM({H}2:{H}{last_data})=0,"",SUMPRODUCT({H}2:{H}{last_data},{K}2:{K}{last_data})/SUM({H}2:{H}{last_data}))'
    ret_cell.number_format = '0.00"%"'
    ret_cell.font          = _TOTAL_FONT

    # Weight sum (should be 100%)
    wt_cell               = ws.cell(totals_row, _POS_IDX["Weight (%)"])
    wt_cell.value         = f"=SUM({L}2:{L}{last_data})"
    wt_cell.number_format = '0.00"%"'
    wt_cell.font          = _TOTAL_FONT

    _autofit(ws)
    ws.freeze_panes = "A2"
    _add_table(ws, "tblPositions", f"A1:{get_column_letter(len(export_df.columns))}{last_data}")
    _set_print(ws, f"A1:{get_column_letter(len(export_df.columns))}{totals_row}")


def _sheet_allocation(wb: Workbook, df: pd.DataFrame, name_map: dict, currency: str) -> None:
    ws       = wb.create_sheet("Allocation")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    tickers  = list(dict.fromkeys(df["Ticker"]))   # unique, preserve order
    n        = len(tickers)
    last_row = n + 1

    _write_headers(ws, ["Ticker", "Company", "Total Value", "Weight (%)"])

    for row_idx, ticker in enumerate(tickers, 2):
        ws.cell(row_idx, 1, ticker)
        ws.cell(row_idx, 2, name_map.get(ticker, ticker))

        # SUMIF referencing Positions sheet — live: updates when user edits Current Price
        val_cell               = ws.cell(row_idx, 3,
            f"=SUMIF(Positions!$A:$A,A{row_idx},Positions!$H:$H)")
        val_cell.number_format = curr_fmt

        wt_cell               = ws.cell(row_idx, 4,
            f'=IF(SUM(C$2:C${last_row})=0,"",C{row_idx}/SUM(C$2:C${last_row})*100)')
        wt_cell.number_format = '0.00"%"'

    # Horizontal bar chart
    chart              = BarChart()
    chart.type         = "bar"
    chart.title        = "Portfolio Allocation"
    chart.style        = 2
    chart.y_axis.title = "Ticker"
    chart.x_axis.title = "Weight (%)"

    data = Reference(ws, min_col=4, max_col=4, min_row=1, max_row=last_row)
    cats = Reference(ws, min_col=1, min_row=2, max_row=last_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.shape  = 4
    chart.width  = 20
    chart.height = max(10, n * 1.2)
    ws.add_chart(chart, "F2")

    _autofit(ws)
    ws.freeze_panes = "A2"
    _add_table(ws, "tblAlloc", f"A1:D{last_row}")


def _sheet_risk(wb: Workbook, analytics_df: pd.DataFrame, name_map: dict, positions_df: pd.DataFrame) -> None:
    ws = wb.create_sheet("Risk Metrics")

    if analytics_df.empty:
        ws["A1"] = "Risk data not available — open the Risk & Analytics section in the dashboard first."
        return

    export_df = analytics_df.copy()
    export_df.insert(1, "Company", export_df["Ticker"].map(name_map))
    export_df = export_df.rename(columns={"Volatility": "Volatility (%)", "Max Drawdown": "Max Drawdown (%)"})
    headers   = ["Ticker", "Company", "Volatility (%)", "Max Drawdown (%)", "Sharpe Ratio", "Beta"]
    export_df = export_df[[c for c in headers if c in export_df.columns]]

    _write_headers(ws, headers)

    sharpe_col = None
    for col_idx, col_name in enumerate(headers, 1):
        if col_name == "Sharpe Ratio":
            sharpe_col = get_column_letter(col_idx)

    for row_idx, row in enumerate(export_df.itertuples(index=False), 2):
        for col_idx, (col_name, value) in enumerate(zip(export_df.columns, row), 1):
            cell = ws.cell(row_idx, col_idx, value if pd.notna(value) else None)
            if col_name in ("Volatility (%)", "Max Drawdown (%)") and isinstance(value, (int, float)):
                cell.number_format = '0.0"%"'
            elif col_name in ("Sharpe Ratio", "Beta") and isinstance(value, (int, float)):
                cell.number_format = "0.00"

    # Portfolio weighted-average row (computed in Python — requires positions for weights)
    if not positions_df.empty and len(export_df) > 1:
        total_val = positions_df.groupby("Ticker")["Total Value"].sum()
        portfolio_val = total_val.sum()
        if portfolio_val > 0:
            weights = (total_val / portfolio_val).reindex(export_df["Ticker"].values, fill_value=0)

            def _wavg(col):
                vals  = export_df[col].fillna(0).values
                return round(float((weights.values * vals).sum()), 2)

            last_row = len(export_df) + 1
            totals_row = last_row + 2
            ws.cell(totals_row, 1, "Portfolio (weighted avg)").font = _TOTAL_FONT
            for col_idx in range(1, len(headers) + 1):
                ws.cell(totals_row, col_idx).fill   = _TOTAL_FILL
                ws.cell(totals_row, col_idx).border = _TOP_BORDER
                ws.cell(totals_row, col_idx).font   = _TOTAL_FONT

            for col_name in ("Volatility (%)", "Max Drawdown (%)", "Sharpe Ratio", "Beta"):
                if col_name not in export_df.columns:
                    continue
                col_idx = headers.index(col_name) + 1
                cell = ws.cell(totals_row, col_idx, _wavg(col_name))
                cell.font = _TOTAL_FONT
                cell.number_format = '0.0"%"' if col_name in ("Volatility (%)", "Max Drawdown (%)") else "0.00"

    if sharpe_col:
        n_rows     = len(export_df) + 1
        data_range = f"{sharpe_col}2:{sharpe_col}{n_rows}"
        ws.conditional_formatting.add(data_range, CellIsRule(operator="greaterThanOrEqual", formula=["1"],      fill=_GREEN_FILL))
        ws.conditional_formatting.add(data_range, CellIsRule(operator="between",            formula=["0", "1"], fill=_AMBER_FILL))
        ws.conditional_formatting.add(data_range, CellIsRule(operator="lessThan",           formula=["0"],      fill=_RED_FILL))

    _autofit(ws)
    ws.freeze_panes = "A2"
    _add_table(ws, "tblRisk", f"A1:{get_column_letter(len(headers))}{len(export_df) + 1}")


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
    ws.freeze_panes = "A2"
    _add_table(ws, "tblFund", f"A1:{get_column_letter(len(fund_df.columns))}{len(fund_df) + 1}")


def _sheet_correlation(wb: Workbook, price_histories: dict, positions_df: pd.DataFrame) -> None:
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

    # Portfolio weights for context column
    total_val = positions_df.groupby("Ticker")["Total Value"].sum() if not positions_df.empty else pd.Series(dtype=float)
    port_total = total_val.sum()
    weights = {t: round(total_val.get(t, 0) / port_total * 100, 1) if port_total else 0 for t in tickers}

    # Row 1: note
    ws.merge_cells(f"A1:{get_column_letter(len(tickers) + 2)}1")
    ws["A1"] = "Correlation of daily returns (12-month). Weight (%) = portfolio allocation per ticker."
    ws["A1"].font = Font(italic=True, size=10, color="595959")

    # Row 2: headers — col A = "Ticker", col B = "Weight (%)", cols C+ = tickers
    ws.cell(2, 1, "Ticker").fill      = _HEADER_FILL
    ws.cell(2, 1).font                = _HEADER_FONT
    ws.cell(2, 1).alignment           = Alignment(horizontal="center")
    ws.cell(2, 2, "Weight (%)").fill  = _HEADER_FILL
    ws.cell(2, 2).font                = _HEADER_FONT
    ws.cell(2, 2).alignment           = Alignment(horizontal="center")
    for col_idx, t in enumerate(tickers, 3):
        cell           = ws.cell(2, col_idx, t)
        cell.fill      = _HEADER_FILL
        cell.font      = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    # Data rows start at row 3
    for row_idx, t_row in enumerate(tickers, 3):
        label           = ws.cell(row_idx, 1, t_row)
        label.fill      = _HEADER_FILL
        label.font      = _HEADER_FONT
        label.alignment = Alignment(horizontal="center")

        wt_cell               = ws.cell(row_idx, 2, weights.get(t_row, 0))
        wt_cell.number_format = '0.0"%"'
        wt_cell.alignment     = Alignment(horizontal="center")

        for col_idx, t_col in enumerate(tickers, 3):
            cell               = ws.cell(row_idx, col_idx, round(corr_df.loc[t_row, t_col], 4))
            cell.number_format = "0.00"
            cell.alignment     = Alignment(horizontal="center")

    # Color scale on correlation values only (skip weight column)
    n          = len(tickers)
    data_range = f"C3:{get_column_letter(n + 2)}{n + 2}"
    ws.conditional_formatting.add(data_range, ColorScaleRule(
        start_type="num", start_value=-1, start_color="C0392B",
        mid_type="num",   mid_value=0,    mid_color="FFFFFF",
        end_type="num",   end_value=1,    end_color="2E7D32",
    ))

    _autofit(ws)
    ws.freeze_panes = "C3"


def _sheet_price_history(wb: Workbook, price_histories: dict) -> None:
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
    pivot       = pivot.ffill()   # forward-fill market holiday gaps so charts have no holes
    n_tickers   = len(pivot.columns)
    n_rows      = len(pivot)

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

    # Line chart placed below data
    chart              = LineChart()
    chart.title        = "6-Month Price History"
    chart.style        = 2
    chart.y_axis.title = "Price"
    chart.smooth       = True

    for col_idx in range(2, n_tickers + 2):
        data = Reference(ws, min_col=col_idx, max_col=col_idx, min_row=1, max_row=n_rows + 1)
        chart.add_data(data, titles_from_data=True)

    cats = Reference(ws, min_col=1, min_row=2, max_row=n_rows + 1)
    chart.set_categories(cats)
    chart.width  = 28
    chart.height = 16
    ws.add_chart(chart, f"A{n_rows + 3}")

    _autofit(ws)
    ws.freeze_panes = "B2"


def _sheet_daily_returns(wb: Workbook, price_histories: dict) -> None:
    ws = wb.create_sheet("Daily Returns")

    close_series = {
        t: h["Close"]
        for t, h in price_histories.items()
        if not h.empty and "Close" in h.columns
    }
    if not close_series:
        ws["A1"] = "No price history available."
        return

    pivot   = pd.DataFrame(close_series).sort_index()
    pivot.index = pd.to_datetime(pivot.index).tz_localize(None)
    returns = pivot.ffill().pct_change().dropna()

    ws.cell(1, 1, "Date").fill      = _HEADER_FILL
    ws.cell(1, 1).font              = _HEADER_FONT
    ws.cell(1, 1).alignment         = Alignment(horizontal="center")
    for col_idx, t in enumerate(returns.columns, 2):
        cell           = ws.cell(1, col_idx, t)
        cell.fill      = _HEADER_FILL
        cell.font      = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")

    for row_idx, (date, row) in enumerate(returns.iterrows(), 2):
        date_cell               = ws.cell(row_idx, 1, date.to_pydatetime())
        date_cell.number_format = "YYYY-MM-DD"
        for col_idx, value in enumerate(row, 2):
            safe = round(float(value), 6) if pd.notna(value) else None
            cell               = ws.cell(row_idx, col_idx, safe)
            cell.number_format = '0.00"%"'
            if safe is not None:
                if safe > 0:
                    cell.fill = _GREEN_FILL
                elif safe < 0:
                    cell.fill = _RED_FILL

    _autofit(ws)
    ws.freeze_panes = "B2"


# Other Assets layout constants
_OA_HEADERS = [
    "Asset Name", "Type", "Units / Shares",
    "Cost Basis", "Purchase Date", "Current Value",
    "Debt / Mortgage", "Net Equity", "Annual Income",
    "Unrealised Gain", "Weight (%)", "Notes",
]
_OA_DATA_ROWS   = range(3, 22)  # rows 3–21 (19 usable rows)
_OA_SUM_ROW     = 22
_OA_COL_COST    = 4   # D
_OA_COL_VALUE   = 6   # F
_OA_COL_DEBT    = 7   # G
_OA_COL_EQUITY  = 8   # H  (formula = F - G)
_OA_COL_INCOME  = 9   # I
_OA_COL_GAIN    = 10  # J  (formula = F - D)
_OA_COL_WEIGHT  = 11  # K  (formula = H / SUM(H) * 100)


def _sheet_other_assets(wb: Workbook, currency: str) -> None:
    ws       = wb.create_sheet("Other Assets")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")
    n_cols   = len(_OA_HEADERS)
    sum_row  = _OA_SUM_ROW

    # Row 1: instruction banner (merged)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)
    instruction           = ws.cell(1, 1,
        f"Add your non-market assets below. Values in {currency}. "
        "Blue cells are editable inputs. Orange cells are computed automatically."
    )
    instruction.fill      = _TEMPLATE_FILL
    instruction.font      = Font(italic=True, color="1F4E79")
    instruction.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 30

    # Row 2: column headers  ← fixed: now correctly in row 2 (not row 1)
    _write_headers(ws, _OA_HEADERS, start_row=2)
    ws.freeze_panes = "A3"

    # Rows 3–21: data rows
    for row_idx in _OA_DATA_ROWS:
        # Blue input cells: Cost Basis, Current Value, Debt, Annual Income
        for col_idx in (_OA_COL_COST, _OA_COL_VALUE, _OA_COL_DEBT, _OA_COL_INCOME):
            c               = ws.cell(row_idx, col_idx)
            c.font          = _INPUT_FONT
            c.fill          = _INPUT_FILL
            c.number_format = curr_fmt

        # Purchase Date
        ws.cell(row_idx, 5).number_format = "YYYY-MM-DD"

        # Net Equity formula: Current Value - Debt
        eq = ws.cell(row_idx, _OA_COL_EQUITY,
            f'=IF(AND(F{row_idx}="",G{row_idx}=""),"",F{row_idx}-G{row_idx})')
        eq.number_format = curr_fmt
        eq.font          = Font(color="E65100")  # orange = computed from inputs

        # Unrealised Gain formula: Current Value - Cost Basis
        gain = ws.cell(row_idx, _OA_COL_GAIN,
            f'=IF(AND(F{row_idx}="",D{row_idx}=""),"",F{row_idx}-D{row_idx})')
        gain.number_format = curr_fmt
        gain.font          = Font(color="E65100")

        # Weight (%) formula: Net Equity / SUM(Net Equity column) * 100
        wt = ws.cell(row_idx, _OA_COL_WEIGHT,
            f'=IF(SUM(H$3:H${sum_row - 1})=0,"",H{row_idx}/SUM(H$3:H${sum_row - 1})*100)')
        wt.number_format = '0.0"%"'
        wt.font          = Font(color="E65100")

    # Row 22: SUM totals
    for col_idx in range(1, n_cols + 1):
        c        = ws.cell(sum_row, col_idx)
        c.fill   = _TOTAL_FILL
        c.font   = _TOTAL_FONT
        c.border = _TOP_BORDER
    ws.cell(sum_row, 1, "Total").font = _TOTAL_FONT

    for col_idx, col_letter in [
        (_OA_COL_COST,   "D"),
        (_OA_COL_VALUE,  "F"),
        (_OA_COL_DEBT,   "G"),
        (_OA_COL_EQUITY, "H"),
        (_OA_COL_INCOME, "I"),
        (_OA_COL_GAIN,   "J"),
    ]:
        c               = ws.cell(sum_row, col_idx, f"=SUM({col_letter}3:{col_letter}{sum_row - 1})")
        c.number_format = curr_fmt
        c.font          = _TOTAL_FONT

    # Type dropdown (B3:B21) — expanded list
    dv = DataValidation(
        type="list",
        formula1=(
            '"Real Estate,Private Equity,Cash & Savings,'
            'Bonds & Fixed Income,Crypto,Vehicles,'
            'Art & Collectibles,Business Ownership,'
            'Retirement Account,Other"'
        ),
        showDropDown=False,
        showErrorMessage=True,
        errorTitle="Invalid Type",
        error="Select a type from the dropdown list.",
    )
    ws.add_data_validation(dv)
    dv.sqref = f"B3:B{sum_row - 1}"

    # Input validation: Cost Basis, Current Value, Debt, Annual Income must be >= 0
    dv_num = DataValidation(
        type="decimal",
        operator="greaterThanOrEqual",
        formula1="0",
        showErrorMessage=True,
        errorTitle="Invalid Value",
        error="Value must be 0 or greater.",
    )
    ws.add_data_validation(dv_num)
    dv_num.sqref = (
        f"D3:D{sum_row - 1} F3:F{sum_row - 1} "
        f"G3:G{sum_row - 1} I3:I{sum_row - 1}"
    )

    # Date validation on Purchase Date (E3:E21)
    dv_date = DataValidation(
        type="date",
        operator="greaterThan",
        formula1="1900-01-01",
        showErrorMessage=True,
        errorTitle="Invalid Date",
        error="Enter a valid date (YYYY-MM-DD).",
    )
    ws.add_data_validation(dv_date)
    dv_date.sqref = f"E3:E{sum_row - 1}"

    # Excel Table for auto-expand (header row 2, data rows 3–21)
    _add_table(ws, "tblOther", f"A2:{get_column_letter(n_cols)}{sum_row - 1}")

    _autofit(ws)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["L"].width = 25


def _sheet_scenario(wb: Workbook, positions_df: pd.DataFrame, name_map: dict, currency: str) -> None:
    ws       = wb.create_sheet("Scenario Analysis")
    curr_fmt = _CURRENCY_FMT.get(currency, "#,##0.00")

    if positions_df.empty:
        ws["A1"] = "No positions available."
        return

    # Banner
    ws.merge_cells("A1:J1")
    banner           = ws["A1"]
    banner.value     = (
        "Scenario Analysis — edit Target Price (blue cells) to model portfolio impact. "
        "All other columns update automatically."
    )
    banner.font      = Font(italic=True, size=10, color="1F4E79")
    banner.fill      = _TEMPLATE_FILL
    banner.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 26

    headers = [
        "Ticker", "Company", "Total Shares", "Avg Buy Price",
        "Current Price", "Target Price",
        "Current Value", "Projected Value",
        "Value Change", "Projected Return (%)",
    ]
    _write_headers(ws, headers, start_row=2)
    ws.freeze_panes = "A3"

    # One row per unique ticker
    tickers = list(dict.fromkeys(positions_df["Ticker"]))
    n       = len(tickers)

    # Precompute aggregates in Python for display; formulas link to tblPositions
    agg = (
        positions_df.groupby("Ticker")
        .apply(lambda g: pd.Series({
            "Shares":        g["Shares"].sum(),
            "AvgBuyPrice":   (g["Buy Price"] * g["Shares"]).sum() / g["Shares"].sum() if g["Shares"].sum() else 0,
            "CurrentPrice":  g["Current Price"].iloc[0],
            "TotalValue":    g["Total Value"].sum(),
        }), include_groups=False)
        .reindex(tickers)
    )

    last_data = n + 2   # header at row 2, data rows 3 to n+2

    for row_idx, ticker in enumerate(tickers, 3):
        row_data = agg.loc[ticker]

        # A: Ticker
        ws.cell(row_idx, 1, ticker)
        # B: Company
        ws.cell(row_idx, 2, name_map.get(ticker, ticker))
        # C: Total Shares — SUMIF formula (live)
        ws.cell(row_idx, 3, f"=SUMIF(Positions!$A:$A,A{row_idx},Positions!$D:$D)").number_format = "#,##0.######"
        # D: Avg Buy Price — SUMPRODUCT weighted average
        ws.cell(row_idx, 4,
            f"=IFERROR(SUMPRODUCT((Positions!$A$2:$A$10000=A{row_idx})"
            f"*Positions!$D$2:$D$10000*Positions!$E$2:$E$10000)"
            f"/SUMIF(Positions!$A:$A,A{row_idx},Positions!$D:$D),\"\")"
        ).number_format = curr_fmt
        # E: Current Price — blue input (pre-filled, user can override for scenario)
        curr_cell = ws.cell(row_idx, 5, float(row_data["CurrentPrice"]) if pd.notna(row_data["CurrentPrice"]) else 0)
        curr_cell.number_format = curr_fmt
        curr_cell.font          = _INPUT_FONT
        curr_cell.fill          = _INPUT_FILL
        # F: Target Price — blue input (pre-filled with current, user changes this)
        tgt_cell = ws.cell(row_idx, 6, float(row_data["CurrentPrice"]) if pd.notna(row_data["CurrentPrice"]) else 0)
        tgt_cell.number_format = curr_fmt
        tgt_cell.font          = _INPUT_FONT
        tgt_cell.fill          = _INPUT_FILL
        # G: Current Value — SUMIF formula
        ws.cell(row_idx, 7,
            f"=SUMIF(Positions!$A:$A,A{row_idx},Positions!$H:$H)"
        ).number_format = curr_fmt
        # H: Projected Value = Total Shares * Target Price
        ws.cell(row_idx, 8, f"=C{row_idx}*F{row_idx}").number_format = curr_fmt
        # I: Value Change = Projected - Current
        change = ws.cell(row_idx, 9, f"=H{row_idx}-G{row_idx}")
        change.number_format = curr_fmt
        # J: Projected Return (%) = (Target - Avg Cost) / Avg Cost * 100
        ws.cell(row_idx, 10,
            f'=IF(D{row_idx}=0,"",((F{row_idx}-D{row_idx})/D{row_idx})*100)'
        ).number_format = '0.00"%"'

    # Conditional formatting on Value Change (col I) and Projected Return (col J)
    for col_l in ("I", "J"):
        rng = f"{col_l}3:{col_l}{last_data}"
        ws.conditional_formatting.add(rng, CellIsRule(operator="greaterThan", formula=["0"], fill=_GREEN_FILL))
        ws.conditional_formatting.add(rng, CellIsRule(operator="lessThan",    formula=["0"], fill=_RED_FILL))

    # Totals row
    totals_row = last_data + 2
    ws.cell(totals_row, 1, "TOTAL").font = _TOTAL_FONT
    for col_idx in range(1, len(headers) + 1):
        ws.cell(totals_row, col_idx).fill   = _TOTAL_FILL
        ws.cell(totals_row, col_idx).border = _TOP_BORDER
        ws.cell(totals_row, col_idx).font   = _TOTAL_FONT
    for col_l in ("G", "H", "I"):
        c               = ws.cell(totals_row, ord(col_l) - ord("A") + 1, f"=SUM({col_l}3:{col_l}{last_data})")
        c.number_format = curr_fmt
        c.font          = _TOTAL_FONT

    _autofit(ws)
    ws.freeze_panes = "A3"
    _add_table(ws, "tblScenario", f"A2:{get_column_letter(len(headers))}{last_data}")


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
    wb.remove(wb.active)

    builders = [
        ("Net Worth",        lambda: _sheet_net_worth(wb, summary_kpis, currency)),
        ("Summary",          lambda: _sheet_summary(wb, summary_kpis, currency)),
        ("Positions",        lambda: _sheet_positions(wb, positions_df, name_map, currency)),
        ("Scenario Analysis",lambda: _sheet_scenario(wb, positions_df, name_map, currency)),
        ("Allocation",       lambda: _sheet_allocation(wb, positions_df, name_map, currency)),
        ("Risk Metrics",     lambda: _sheet_risk(wb, analytics_df, name_map, positions_df)),
        ("Fundamentals",     lambda: _sheet_fundamentals(wb, fund_rows, name_map)),
        ("Correlation",      lambda: _sheet_correlation(wb, price_histories, positions_df)),
        ("Price History",    lambda: _sheet_price_history(wb, price_histories)),
        ("Daily Returns",    lambda: _sheet_daily_returns(wb, price_histories)),
        ("Other Assets",     lambda: _sheet_other_assets(wb, currency)),
    ]

    for sheet_name, builder in builders:
        try:
            builder()
        except Exception as exc:
            ws       = wb.create_sheet(sheet_name)
            ws["A1"] = f"Error generating sheet: {exc}"
            print(f"[excel_export] Sheet '{sheet_name}' failed: {exc}")

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
