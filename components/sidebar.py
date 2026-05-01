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

/* ── Sidebar shell — dark control panel ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0F172A 0%, #111827 60%, #0B1220 100%) !important;
    border-right: 1px solid #1F2937 !important;
    box-shadow: inset -1px 0 0 rgba(255,255,255,0.02);
}
section[data-testid="stSidebar"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, #2563EB 0%, #7C3AED 50%, #059669 100%);
    opacity: 0.55;
    pointer-events: none;
    z-index: 5;
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

    # ── Brand header — sits at the top of the sidebar ──────────────────────────
    brand_svg = (
        "<svg width='26' height='26' viewBox='0 0 26 26' xmlns='http://www.w3.org/2000/svg' "
        "style='flex-shrink:0;'>"
        "<defs>"
        "<linearGradient id='pmrBars' x1='0' y1='0' x2='1' y2='1'>"
        "<stop offset='0%' stop-color='#3B82F6'/>"
        "<stop offset='100%' stop-color='#7C3AED'/>"
        "</linearGradient>"
        "</defs>"
        "<rect x='2'  y='14' width='4' height='10' rx='1' fill='url(#pmrBars)' opacity='0.55'/>"
        "<rect x='8'  y='9'  width='4' height='15' rx='1' fill='url(#pmrBars)' opacity='0.75'/>"
        "<rect x='14' y='4'  width='4' height='20' rx='1' fill='url(#pmrBars)'/>"
        "<rect x='20' y='10' width='4' height='14' rx='1' fill='#10B981' opacity='0.85'/>"
        "</svg>"
    )

    st.sidebar.markdown(
        "<div style='display:flex;align-items:center;gap:10px;"
        "padding:6px 0 14px 0;margin-bottom:10px;"
        "border-bottom:1px solid #1F2937;'>"
        f"{brand_svg}"
        "<div style='line-height:1.2;'>"
        "<div style='font-size:10px;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.14em;color:#3B82F6;margin-bottom:3px;'>Healthcare Multiples</div>"
        "<div style='font-size:14px;font-weight:600;color:#F1F5F9;'>"
        "Market Screening</div>"
        "<div style='font-size:10.5px;color:#64748B;font-weight:500;margin-top:2px;"
        "letter-spacing:0.02em;'>Permira &middot; Healthcare Investments</div>"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

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
