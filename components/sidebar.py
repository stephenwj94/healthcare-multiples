"""
Shared sidebar component — dark rail, institutional style.
"""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import DB_PATH
from fetcher.db_manager import DBManager


def render_sidebar():
    """Render the shared sidebar across all pages."""

    # ── CSS — dark sidebar rail ────────────────────────────────────────────────
    st.markdown("""
<style>
/* ── Global scale ── */
html { zoom: 0.9; }

/* ── Tighten page top padding ── */
.block-container {
    padding-top: 0.5rem !important;
    padding-bottom: 0.25rem !important;
}
.block-container h1 {
    margin-bottom: 0.15rem !important;
    padding-bottom: 0 !important;
    font-size: 1.6rem !important;
}

/* ── Always-visible sidebar ── */
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="collapsedControl"]        { display: none !important; }
section[data-testid="stSidebar"] {
    transform: none !important;
    min-width: 244px !important;
    max-width: 244px !important;
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
}

/* ── Sidebar shell — dark ── */
section[data-testid="stSidebar"] {
    background-color: #111827 !important;
    border-right: 1px solid #1F2937 !important;
}

/* ── Default text ── */
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] li {
    color: #E2E8F0 !important;
}

/* ── Headings ── */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #F1F5F9 !important;
    letter-spacing: -0.01em;
}

/* ── Muted captions ── */
section[data-testid="stSidebar"] small,
section[data-testid="stSidebar"] .stCaption p,
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: #4B5563 !important;
}

/* ── Dividers ── */
section[data-testid="stSidebar"] hr {
    border-color: #1F2937 !important;
    opacity: 1 !important;
    margin: 14px 0 !important;
}

/* ── Nav section group labels ── */
section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"],
section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] span {
    color: #64748B !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.10em !important;
}

/* ── Nav link items ── */
section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] span {
    color: #CBD5E1 !important;
    font-size: 13px !important;
    font-weight: 400 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] a {
    border-radius: 4px !important;
    transition: background 0.12s ease;
    border: 1px solid transparent !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] a:hover {
    background-color: #1E293B !important;
    border: 1px solid #334155 !important;
}

/* ── Active nav item ── */
section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] [aria-selected="true"] {
    background-color: #1E293B !important;
    border: 1px solid #334155 !important;
    border-left: 2px solid #3B82F6 !important;
    border-radius: 0 4px 4px 0 !important;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNavItems"] [aria-selected="true"] span {
    color: #FFFFFF !important;
    font-weight: 600 !important;
}

/* ── Metric widget ── */
section[data-testid="stSidebar"] [data-testid="stMetricValue"],
section[data-testid="stSidebar"] [data-testid="stMetricValue"] * {
    color: #F1F5F9 !important;
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] p,
section[data-testid="stSidebar"] [data-testid="stMetricLabel"] * {
    color: #4B5563 !important;
}
</style>
""", unsafe_allow_html=True)

    # ── Wordmark ───────────────────────────────────────────────────────────────
    st.sidebar.markdown(
        "<div style='padding:4px 0 14px 0;'>"
        "<div style='font-size:10px;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.12em;color:#3B82F6;margin-bottom:6px;'>Healthcare Multiples</div>"
        "<div style='font-size:15px;font-weight:600;color:#F1F5F9;line-height:1.4;'>"
        "Market Screening<br>"
        "<span style='color:#4B5563;font-weight:400;font-size:13px;'>Dashboard</span>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.divider()

    # ── Last updated ───────────────────────────────────────────────────────────
    db = DBManager(DB_PATH)
    try:
        last_fetch = db.get_last_fetch_time()
        if last_fetch:
            date_str = last_fetch[:10]
            time_str = last_fetch[11:16]
            st.sidebar.markdown(
                "<div style='background:#1E293B;border:1px solid #334155;border-radius:4px;padding:10px 12px;margin-bottom:8px;'>"
                "<p style='font-size:10px;font-weight:700;color:#64748B;"
                "text-transform:uppercase;letter-spacing:0.10em;margin:0 0 5px 0;'>"
                "Last Updated</p>"
                f"<p style='font-size:13px;font-weight:600;color:#FFFFFF;margin:0 0 1px 0;'>"
                f"{date_str}</p>"
                f"<p style='font-size:11px;color:#94A3B8;margin:0;'>{time_str} UTC</p>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            st.sidebar.markdown(
                "<p style='font-size:12px;color:#94A3B8;margin:0;'>No data yet.</p>",
                unsafe_allow_html=True,
            )
    except Exception:
        st.sidebar.markdown(
            "<p style='font-size:12px;color:#94A3B8;margin:0;'>DB not initialized.</p>",
            unsafe_allow_html=True,
        )

    # ── Data source ────────────────────────────────────────────────────────────
    st.sidebar.markdown(
        "<div style='background:#1E293B;border:1px solid #334155;border-radius:4px;padding:10px 12px;'>"
        "<p style='font-size:10px;font-weight:700;color:#64748B;"
        "text-transform:uppercase;letter-spacing:0.10em;margin:0 0 5px 0;'>"
        "Data Source</p>"
        "<p style='font-size:13px;font-weight:600;color:#FFFFFF;margin:0;'>FactSet</p>"
        "</div>",
        unsafe_allow_html=True,
    )
