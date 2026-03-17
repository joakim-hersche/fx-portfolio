"""Shared UI helpers used across all section modules."""

import streamlit as st
from pandas.io.formats.style import Styler


def section_header(title: str, subtitle: str = "") -> None:
    """Render a small-caps section header with optional subtitle.

    Uses CSS classes defined in app.py's global stylesheet so styles are
    consistent everywhere they appear.
    """
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-subtitle">{subtitle}</div>', unsafe_allow_html=True)


def render_styled_table(styled: Styler) -> None:
    """Render a Pandas Styler as a native HTML table.

    Unlike st.dataframe (canvas-based, blurry on high-DPI mobile screens),
    HTML tables render crisply at any resolution and scale naturally with
    the responsive CSS.
    """
    html = styled.set_table_attributes('class="styled-table"').to_html()
    st.markdown(
        '<div style="overflow-x: auto; width: 100%;">' + html + "</div>",
        unsafe_allow_html=True,
    )
