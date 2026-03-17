"""Session state initialisation and browser localStorage sync."""

import json
import streamlit as st

from src.fx import CURRENCY_SYMBOLS
from src.localstorage_component import ls_get, ls_set

_LS_KEY = "market_dashboard_portfolio"


def init_session_state() -> None:
    """Initialise all session state keys. Must run before any widgets."""
    if "ls_loaded" not in st.session_state:
        _ls_data = ls_get(_LS_KEY)
        if _ls_data is not None:
            st.session_state.ls_loaded = True
            if _ls_data:
                try:
                    _parsed = json.loads(_ls_data)
                    if isinstance(_parsed, dict):
                        if "portfolio" in _parsed:
                            st.session_state.portfolio = _parsed["portfolio"]
                        if "currency" in _parsed:
                            st.session_state.currency = _parsed["currency"]
                except Exception:
                    pass

    if "portfolio" not in st.session_state:
        st.session_state.portfolio = {}

    if "currency" not in st.session_state:
        st.session_state.currency = list(CURRENCY_SYMBOLS.keys())[0]

    if "imported" not in st.session_state:
        st.session_state.imported = False

    if "confirm_clear" not in st.session_state:
        st.session_state.confirm_clear = False

    if "pending_remove" not in st.session_state:
        st.session_state.pending_remove = False

    if "confirm_sample" not in st.session_state:
        st.session_state.confirm_sample = False


def sync_localstorage() -> None:
    """Persist portfolio and currency to browser localStorage after every rerun."""
    if st.session_state.get("ls_loaded"):
        ls_set(_LS_KEY, json.dumps({
            "portfolio": st.session_state.portfolio,
            "currency": st.session_state.currency,
        }))
