"""Add/Manage Positions form and Positions Table rendering."""

import json
import os

import pandas as pd
import streamlit as st

from src.charts import C_POSITIVE, C_NEGATIVE, C_NEUTRAL, C_CARD_BRD
from src.data_fetch import fetch_company_name
from src.fx import get_ticker_currency, get_fx_rate, get_historical_fx_rate
from src.portfolio import fetch_buy_price


def render_add_manage(all_stock_options: dict, base_currency: str, currency_symbol: str) -> None:
    """Render the Add / Manage Positions form (sidebar-friendly, no expander wrapper)."""
    is_new_user = not bool(st.session_state.portfolio)

    if is_new_user:
        st.markdown(
            '<p class="section-intro">'
            'Welcome! Start by adding your first stock below. '
            'Select which market it\'s listed on, search for it by name, enter how many shares you bought and when — '
            'the app looks up the price automatically. '
            'Already have a saved portfolio? Import it or load the sample to explore.</p>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<p class="section-intro">'
            'Add a new position or remove an existing one. '
            'Each time you bought the same stock counts as a separate purchase.</p>',
            unsafe_allow_html=True
        )

    # Import / Load Sample
    uploaded_file = st.file_uploader(
        "Import saved portfolio (.json file)",
        type="json",
        help="Use the .json file you previously downloaded with the 'Export Portfolio' button in the Positions tab.",
    )
    if st.button("Load Sample Portfolio", width="stretch"):
        st.session_state.confirm_sample = True

    if st.session_state.confirm_sample:
        st.warning("This will replace your current portfolio with sample data. Your existing positions will be lost.")
        col_yes, col_no = st.columns(2)
        if col_yes.button("Yes, load sample", key="confirm_sample_yes", use_container_width=True):
            sample_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "sample_portfolio.json")
            with open(sample_path) as f:
                st.session_state.portfolio = json.load(f)
            st.session_state.imported = False
            st.session_state.confirm_sample = False
            st.rerun()
        if col_no.button("Cancel", key="confirm_sample_no", use_container_width=True):
            st.session_state.confirm_sample = False
            st.rerun()

    if uploaded_file is not None and not st.session_state.imported:
        try:
            data = pd.read_json(uploaded_file, typ="series").to_dict()
            valid = (
                isinstance(data, dict)
                and all(
                    isinstance(ticker, str)
                    and isinstance(lots, list)
                    and all(
                        isinstance(lot, dict) and {"shares", "buy_price", "purchase_date"}.issubset(lot.keys())
                        for lot in lots
                    )
                    for ticker, lots in data.items()
                )
            )
            if not valid:
                st.error("Invalid portfolio file. Expected format: {ticker: [{shares, buy_price, purchase_date, ...}]}.")
            else:
                st.session_state.portfolio = data
                st.session_state.imported = True
                st.success("Portfolio imported successfully.")
                st.rerun()
        except Exception:
            st.error("Could not read the file. Make sure it is a valid portfolio JSON export.")

    if uploaded_file is None:
        st.session_state.imported = False

    st.markdown("---")

    # Add Position form
    manual_price = st.session_state.get("manual_price_toggle", False)

    col_mkt, col_stk = st.columns(2)
    with col_mkt:
        index_choice = st.selectbox(
            "Stock Market",
            options=list(all_stock_options.keys()),
            index=0,
        )

    alt_asset = index_choice in ("Crypto", "Commodities")
    stock_options = all_stock_options[index_choice]

    with col_stk:
        selected = st.selectbox(
            "Stock",
            options=list(stock_options.keys()),
            index=None,
            placeholder="Search by name or ticker…"
        )
    st.caption("US → S&P 500 · UK → FTSE 100 · Switzerland → SMI · Germany → DAX")

    col_shr, col_dt = st.columns(2)
    with col_shr:
        if alt_asset:
            amount_input = st.number_input(
                f"Amount ({base_currency})",
                min_value=0.0, value=None, step=1.0,
                placeholder="e.g. 5000"
            )
            shares_input = None
        else:
            shares_input = st.number_input(
                "Shares",
                min_value=0.0, value=None, step=1.0,
                placeholder="e.g. 5"
            )
            amount_input = None

    with col_dt:
        if not alt_asset and manual_price:
            buy_price_input = st.number_input(
                f"Buy Price ({base_currency})",
                min_value=0.0, value=None, step=0.01,
                placeholder="e.g. 180.00"
            )
            purchase_date = None
        else:
            purchase_date = st.date_input(
                "Purchase Date" + (" (optional)" if alt_asset else ""),
                value=None,
                min_value=pd.Timestamp("1980-01-01").date(),
                max_value=pd.Timestamp.today().date()
            )
            buy_price_input = None

    if not alt_asset:
        manual_price = st.checkbox("Enter price manually", key="manual_price_toggle")
        st.caption("Leave unchecked to use the market price on that date (recommended).")

    if st.button("Add to Portfolio"):
        if selected is None:
            st.warning("Please select a stock.")
        elif not alt_asset and (shares_input is None or shares_input == 0):
            st.warning("Please enter the number of shares.")
        elif alt_asset and (amount_input is None or amount_input == 0):
            st.warning("Please enter the amount.")
        elif not alt_asset and not manual_price and purchase_date is None:
            st.warning("Please select a purchase date or enter a price manually.")
        elif not alt_asset and manual_price and (buy_price_input is None or buy_price_input == 0):
            st.warning("Please enter a valid buy price.")
        else:
            ticker = stock_options[selected]
            ticker_currency = get_ticker_currency(ticker)
            if not alt_asset and manual_price:
                buy_price = buy_price_input
                buy_fx_rate = 1.0
            elif purchase_date is not None:
                result = fetch_buy_price(ticker, str(purchase_date))
                if result is None:
                    st.error("No price data found for that date. Try a different date.")
                    buy_price = None
                else:
                    buy_price, actual_date = result
                    if actual_date != str(purchase_date):
                        st.info(
                            f"{purchase_date} was not a trading day. "
                            f"Using the closing price from {actual_date} instead."
                        )
                buy_fx_rate = get_historical_fx_rate(ticker_currency, base_currency, str(purchase_date))
            else:
                purchase_date = pd.Timestamp.today().date()
                result = fetch_buy_price(ticker, str(purchase_date))
                buy_price = result[0] if result else None
                buy_fx_rate = get_fx_rate(ticker_currency, base_currency)

            if buy_price is not None:
                shares = round(amount_input / buy_price, 6) if alt_asset else shares_input
                lot = {
                    "shares": shares,
                    "buy_price": buy_price,
                    "buy_fx_rate": buy_fx_rate,
                    "purchase_date": str(purchase_date) if purchase_date else None,
                    "manual_price": manual_price
                }
                st.session_state.portfolio.setdefault(ticker, []).append(lot)
                st.success(f"Added {shares:g} units of {ticker} at {currency_symbol}{buy_price:,.2f}")

    # Manage existing positions
    if st.session_state.portfolio:
        st.markdown("---")
        col_manage_title, col_clear = st.columns([1, 1], vertical_alignment="bottom")
        col_manage_title.markdown("**Your purchases**")
        if col_clear.button("Clear All", key="clear_portfolio", width="stretch"):
            st.session_state.confirm_clear = True

        if st.session_state.confirm_clear:
            st.warning("This will delete all your positions. Are you sure?")
            col_yes, col_no = st.columns(2)
            if col_yes.button("Yes, clear all", key="confirm_clear_yes", use_container_width=True):
                st.session_state.portfolio = {}
                st.session_state.confirm_clear = False
                st.rerun()
            if col_no.button("Cancel", key="confirm_clear_no", use_container_width=True):
                st.session_state.confirm_clear = False
                st.rerun()

        for t, lots in list(st.session_state.portfolio.items()):
            for i, lot in enumerate(lots):
                col_info, col_btn = st.columns([5, 1], vertical_alignment="center")
                tc = get_ticker_currency(t)
                display_tc = "GBP" if tc == "GBX" else tc
                col_info.markdown(
                    f"**{t}** — Buy {i + 1}  \n"
                    f"<span style='font-size:12px;color:var(--text-muted);'>"
                    f"{lot['shares']:g} shares · {display_tc} {lot['buy_price']:,.2f} · {lot['purchase_date'] or 'Manual'}"
                    f"</span>",
                    unsafe_allow_html=True,
                )
                if col_btn.button("×", key=f"remove_{t}_{i}", use_container_width=True):
                    st.session_state.pending_remove = (t, i)
                    st.rerun()

        if st.session_state.pending_remove:
            pt, pi = st.session_state.pending_remove
            st.warning(f"Remove {pt} (Buy {pi + 1})? This cannot be undone.")
            col_yes, col_no = st.columns(2)
            if col_yes.button("Remove", key="confirm_remove_yes", use_container_width=True):
                st.session_state.portfolio[pt].pop(pi)
                if not st.session_state.portfolio[pt]:
                    del st.session_state.portfolio[pt]
                st.session_state.pending_remove = None
                st.rerun()
            if col_no.button("Cancel", key="confirm_remove_no", use_container_width=True):
                st.session_state.pending_remove = None
                st.rerun()

        st.markdown("---")
        st.download_button(
            label="Export Portfolio (.json)",
            data=pd.Series(st.session_state.portfolio).to_json(),
            file_name="portfolio.json",
            mime="application/json",
            help="Download your positions as a JSON file. Use 'Import saved portfolio' to restore it later.",
            use_container_width=True,
        )


def render_positions_table(
    df: pd.DataFrame,
    name_map: dict,
    currency_symbol: str,
) -> None:
    """Render the Positions table with summary/individual lot toggle."""
    st.markdown(
        '<p class="section-intro">Every stock you own, how much you paid, what it\'s worth now, '
        'and how much you\'ve gained or lost. <b>Today\'s Change</b> is how much your value moved since yesterday\'s market close. '
        '<b>Total Return</b> includes any dividends received. <b>Portfolio Share</b> is what percentage of your total investment this position represents.</p>',
        unsafe_allow_html=True
    )

    _multi_tickers = {t for t, g in df.groupby("Ticker", sort=False) if len(g) > 1}

    show_individual = _multi_tickers and st.toggle(
        "Show individual purchases", value=False, key="show_individual_lots"
    )

    display_rows = []
    for ticker, group in df.groupby("Ticker", sort=False):
        if len(group) > 1:
            if show_individual:
                display_rows.append(group)
            else:
                total_value_t = group["Total Value"].sum()
                total_cost_t  = (group["Buy Price"] * group["Shares"]).sum()
                total_divs_t  = group["Dividends"].sum()
                summary = {
                    "Ticker":        f"► {ticker}",
                    "Purchase":      "Total",
                    "Shares":        group["Shares"].sum(),
                    "Buy Price":     round(total_cost_t / group["Shares"].sum(), 2),
                    "Purchase Date": "",
                    "Current Price": group["Current Price"].iloc[0],
                    "Total Value":   round(total_value_t, 2),
                    "Dividends":     round(total_divs_t, 2),
                    "Daily P&L":     round(group["Daily P&L"].sum(), 2),
                    "Return (%)":    round(
                        (total_value_t + total_divs_t - total_cost_t) / total_cost_t * 100, 2
                    ) if total_cost_t else None,
                    "Weight (%)":    round(group["Weight (%)"].sum(), 2),
                }
                display_rows.append(pd.DataFrame([summary]))
        else:
            display_rows.append(group)
    display_df = pd.concat(display_rows, ignore_index=True) if display_rows else df.copy()
    display_df["Purchase"] = display_df["Purchase"].astype(str)

    styled_df = display_df.rename(columns={
        "Daily P&L":  "Today",
        "Purchase":   "Buy #",
    })
    styled_df.insert(1, "Company", styled_df["Ticker"].str.replace("► ", "", regex=False).map(name_map))

    def _color_pnl(val):
        if val > 0:   return f"color: {C_POSITIVE}; font-weight: 500"
        elif val < 0: return f"color: {C_NEGATIVE}; font-weight: 500"
        return f"color: {C_NEUTRAL}"

    def _fmt_shares(x):
        return f"{int(x):,}" if x == int(x) else f"{x:g}"

    def _style_row(row):
        if show_individual:
            return [""] * len(row)
        ticker_val = row.name[0]
        if ticker_val.startswith("► "):
            return ["font-weight: 700; background-color: rgba(29,78,216,0.08)"] * len(row)
        return [""] * len(row)

    styled = (
        styled_df.set_index(["Ticker", "Company", "Buy #"])
        .style
        .format({
            "Shares":           _fmt_shares,
            "Buy Price":        lambda x: f"{currency_symbol}{x:,.2f}",
            "Current Price":    lambda x: f"{currency_symbol}{x:,.2f}",
            "Total Value":      lambda x: f"{currency_symbol}{x:,.2f}",
            "Dividends":        lambda x: f"{currency_symbol}{x:,.2f}",
            "Today":            lambda x: f"{currency_symbol}{x:,.2f}",
            "Return (%)":       lambda x: f"{x:+,.2f}%" if isinstance(x, (int, float)) else str(x),
            "Weight (%)":       "{:,.2f}%",
        })
        .map(_color_pnl, subset=["Today", "Return (%)"])
        .apply(_style_row, axis=1)
    )

    st.dataframe(styled, width="stretch", column_config={
        "Shares":               st.column_config.TextColumn("Shares"),
        "Buy Price":            st.column_config.TextColumn("Buy Price"),
        "Purchase Date":        st.column_config.TextColumn("Purchase Date"),
        "Current Price":        st.column_config.TextColumn("Current Price"),
        "Total Value":          st.column_config.TextColumn("Total Value"),
        "Dividends":            st.column_config.NumberColumn("Dividends", help="Total dividends received since purchase. Already included in Total Return."),
        "Today":                st.column_config.TextColumn("Today"),
        "Return (%)":           st.column_config.TextColumn("Return (%)"),
        "Weight (%)":           st.column_config.TextColumn("Weight (%)"),
    })

