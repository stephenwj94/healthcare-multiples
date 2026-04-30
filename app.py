"""
Healthcare Public Market Comps Dashboard
Main Streamlit entrypoint.
"""

import streamlit as st

st.set_page_config(
    page_title="Healthcare Public Market Comps",
    page_icon=":material/bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS — light theme, DM Sans font ────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

/* ── Base typography ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}
.stApp { background-color: #FAFBFC !important; }
.main .block-container {
    background-color: #FAFBFC !important;
    max-width: 100% !important;
    padding-top: 1rem !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    padding-bottom: 1rem !important;
    color: #111827 !important;
}
/* Tighten h1 title top margin so it sits closer to the page top */
h1 {
    margin-top: 0 !important;
    padding-top: 0 !important;
}

/* ── Headings ── */
h1, h2, h3, h4, h5, h6 { color: #111827 !important; }
h4 {
    font-size: 15px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px !important;
    border-left: 3px solid #3B82F6 !important;
    padding-left: 10px !important;
    margin-top: 1.5rem !important;
    color: #374151 !important;
}

/* ── Hide Streamlit chrome clutter ── */
#MainMenu { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent !important; }
footer { visibility: hidden; }
/* ── Sidebar always visible — force open regardless of stored state ── */
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="collapsedControl"]        { display: none !important; }
section[data-testid="stSidebar"] {
    transform: none !important;
    min-width: 244px !important;
    max-width: 344px !important;
    visibility: visible !important;
    display: flex !important;
    opacity: 1 !important;
}
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* ── Dataframe tables ── */
div[data-testid="stDataFrame"] table {
    font-size: 13px !important;
    font-family: 'DM Sans', sans-serif !important;
}
div[data-testid="stDataFrame"] th {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
    color: #6B7280 !important;
    background-color: #F9FAFB !important;
    border-bottom: 2px solid #E5E7EB !important;
    padding: 8px 10px !important;
    white-space: nowrap !important;
}
div[data-testid="stDataFrame"] td {
    padding: 6px 10px !important;
    border-bottom: 1px solid #F3F4F6 !important;
    white-space: nowrap !important;
    color: #111827 !important;
}
div[data-testid="stDataFrame"] tr:nth-child(even) td {
    background-color: #FAFBFC !important;
}
div[data-testid="stDataFrame"] tr:hover td {
    background-color: #EFF6FF !important;
}

/* ── Metric cards ── */
div[data-testid="stMetric"] {
    background-color: #FFFFFF;
    border-radius: 10px;
    padding: 12px 16px;
    border: 1px solid #E5E7EB;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
div[data-testid="stMetric"] label {
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #6B7280 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 22px !important;
    font-weight: 700 !important;
    color: #111827 !important;
}

/* ── Dividers ── */
hr {
    border-color: #E5E7EB !important;
    margin: 1.5rem 0 !important;
}

/* ── Captions ── */
div[data-testid="stCaptionContainer"] p,
.stCaption p {
    font-size: 12px !important;
    color: #9CA3AF !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    border-bottom: 1px solid #E5E7EB !important;
    gap: 4px !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"], button[role="tab"] {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #9CA3AF !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 20px !important;
    margin-right: 4px !important;
}
.stTabs [aria-selected="true"], button[role="tab"][aria-selected="true"] {
    color: #111827 !important;
    font-weight: 600 !important;
    border-bottom: 2px solid #3B82F6 !important;
    background: transparent !important;
}

/* ── Select / multiselect ── */
div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label,
div[data-testid="stRadio"] label {
    color: #374151 !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}

/* ── Buttons ── */
.stButton button {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    color: #374151 !important;
    border-radius: 6px !important;
}
.stButton button:hover {
    border-color: #D1D5DB !important;
    background: #F9FAFB !important;
}

/* ── Spinner ── */
.stSpinner { color: #3B82F6 !important; }

/* ── Info / warning / error boxes ── */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)

# ── Password gate ─────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] { display: none !important; }
    .login-wrap {
        display: flex; flex-direction: column; align-items: center;
        justify-content: center; min-height: 70vh; gap: 0;
    }
    .login-box {
        background: #FFFFFF; border: 1px solid #E5E7EB;
        border-radius: 12px; padding: 40px 48px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.06);
        width: 100%; max-width: 380px;
    }
    .login-title {
        font-size: 20px; font-weight: 700; color: #111827;
        margin-bottom: 4px; text-align: center;
    }
    .login-sub {
        font-size: 13px; color: #6B7280;
        margin-bottom: 28px; text-align: center;
    }
    </style>
    <div class="login-wrap"><div class="login-box">
        <p class="login-title">Healthcare Public Market Comps</p>
        <p class="login-sub">Enter password to continue</p>
    </div></div>
    """, unsafe_allow_html=True)

    pwd = st.text_input("Password", type="password", label_visibility="collapsed",
                        placeholder="Password")
    if pwd:
        try:
            correct = st.secrets.get("APP_PASSWORD", "permirahc")
        except (FileNotFoundError, Exception):
            correct = "permirahc"
        if pwd == correct:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()

pg = st.navigation({
    "Overview": [
        st.Page("views/01_Winners_and_Losers.py",     title="Winners & Losers",        icon=":material/trending_up:"),
        st.Page("views/02_Valuation_Lookback.py",     title="Valuation Lookback",      icon=":material/history:"),
        st.Page("views/03_Valuation_Regression.py",   title="Valuation Regression",    icon=":material/analytics:"),
    ],
    "Segment Comps": [
        st.Page("views/04_Pharma.py",          title="Pharma",                              icon=":material/medication:"),
        st.Page("views/05_Consumer_Health.py", title="Consumer Health",                     icon=":material/storefront:"),
        st.Page("views/06_MedTech.py",         title="MedTech",                             icon=":material/medical_services:"),
        st.Page("views/07_Life_Sci_Tools.py",  title="Life Sci Tools / Dx / Bioprocessing", icon=":material/biotech:"),
        st.Page("views/08_Services.py",        title="Asset-Light Services",                icon=":material/handshake:"),
        st.Page("views/09_CDMOs.py",           title="CDMOs",                               icon=":material/factory:"),
        st.Page("views/10_Health_Tech.py",     title="Health Tech",                         icon=":material/devices:"),
    ],
    "Explore": [
        st.Page("views/11_Scenario_Screener.py",     title="Scenario Screener",     icon=":material/filter_alt:"),
        st.Page("views/12_Comp_Set_Builder.py",      title="Comp Set Builder",      icon=":material/group_work:"),
    ],
})

pg.run()
