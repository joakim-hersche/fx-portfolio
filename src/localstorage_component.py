import os
import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "localstorage_frontend")
_ls = components.declare_component("localstorage", path=_FRONTEND_DIR)


def ls_get(key: str):
    """Read a string value from localStorage.
    Returns None on the first render (JS not yet run), then the stored string."""
    return _ls(operation="get", storage_key=key, key=f"_lsget_{key}", default=None)


def ls_set(key: str, value: str):
    """Write a string value to localStorage. Fire-and-forget."""
    _ls(operation="set", storage_key=key, value=value, key=f"_lsset_{key}", default=None)
