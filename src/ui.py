"""Shared UI helpers used across all section modules."""

import streamlit as st


def section_header(title: str, subtitle: str = "") -> None:
    """Render a small-caps section header with optional subtitle.

    Uses CSS classes defined in app.py's global stylesheet so styles are
    consistent everywhere they appear.
    """
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)
