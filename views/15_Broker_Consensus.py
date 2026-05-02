"""
Broker Consensus & Price Targets -- analyst target price dispersion
and upside/downside across the healthcare universe.
"""

from __future__ import annotations

import html as _html_lib
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from config.settings import DB_PATH, SEGMENT_DISPLAY, EXCEL_OVERRIDE_PATH
from config.color_palette import (
    SEGMENT_SHORT, SEGMENT_COLORS, LIGHT_BADGE_STYLES, SEG_COLOR_MAP,
    PLOTLY_BG, PLOTLY_GRID, PLOTLY_TEXT,
    GREEN, RED,
)
from config.company_registry import COMPANY_REGISTRY
from fetcher.db_manager import DBManager
from fetcher.excel_override import load_overrides, apply_overrides

# ── Page config ─────────────────────────────────────────────────────────────
render_sidebar()

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');

.block-container {
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stApp { background-color: #FAFBFC !important; }
.main .block-container { background-color: #FAFBFC !important; color: #1A1A2E !important; }
h1,h2,h3,h4,h5,h6 { color: #111827 !important; }
.stMarkdown p, .stMarkdown span, .stMarkdown div { color: #1A1A2E !important; }
hr { border-color: #E5E7EB !important; }

/* Stat cards */
.bc-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 18px 22px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
    text-align: center;
}
.bc-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.07), 0 1px 3px rgba(0,0,0,0.04);
}
.bc-card-value {
    font-size: 30px;
    font-weight: 700;
    color: #111827;
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
}
.bc-card-label {
    font-size: 11px;
    font-weight: 600;
    color: #9CA3AF;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 6px;
}

/* HTML table */
.bc-outer {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.bc-tbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    font-family: 'DM Sans', sans-serif;
}
.bc-tbl thead th {
    font-size: 9px;
    font-weight: 500;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 8px 10px;
    border-bottom: 1px solid #E5E7EB;
    background: #FFFFFF;
    white-space: nowrap;
}
.bc-tbl tbody td {
    padding: 6px 10px;
    border-bottom: 1px solid #F3F4F6;
    color: #374151;
    line-height: 1.3;
    white-space: nowrap;
    vertical-align: middle;
}
.bc-tbl tbody tr:nth-child(odd) td  { background: #FFFFFF; }
.bc-tbl tbody tr:nth-child(even) td { background: #FAFBFD; }
.bc-tbl tbody tr:hover td           { background: #F0F4FF !important; }
.bc-rt { text-align: right; }
.bc-lt { text-align: left; }
.bc-ct { text-align: center; }

/* Company link styling */
.bc-name-link {
    color: #374151;
    text-decoration: none;
    font-weight: 500;
}
.bc-name-link:hover {
    color: #3B82F6;
    text-decoration: underline;
}
.bc-tkr {
    color: #3B82F6;
    font-weight: 600;
    font-size: 11px;
}

/* Source attribution */
.bc-source {
    font-size: 11px;
    color: #9CA3AF;
    margin-top: 12px;
    padding-top: 8px;
    border-top: 1px solid #E5E7EB;
}
</style>
""", unsafe_allow_html=True)

# ── Title ───────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:22px;font-weight:700;color:#111827;margin-bottom:2px;">'
    'Broker Consensus &amp; Price Targets</div>'
    '<div style="font-size:12px;color:#94A3B8;margin-bottom:16px;">'
    'Analyst target price dispersion and upside/downside across the healthcare universe</div>',
    unsafe_allow_html=True,
)

# ── Build company lookup ────────────────────────────────────────────────────
_COMPANY_MAP = {}
for c in COMPANY_REGISTRY:
    _COMPANY_MAP[c["ticker"]] = c

# ── Parallel data fetching (cached 24 hours) ─────────────────────────────


def _fetch_single_company(company: dict) -> dict:
    """Fetch analyst data for a single company with a 3-second timeout guard."""
    ticker = company["ticker"]
    yahoo_ticker = company.get("yahoo_ticker", ticker)
    empty_row = {
        "ticker": ticker,
        "yahoo_ticker": yahoo_ticker,
        "name": company["name"],
        "segment": company["segment"],
        "currentPrice": None,
        "targetLowPrice": None,
        "targetMeanPrice": None,
        "targetMedianPrice": None,
        "targetHighPrice": None,
        "numberOfAnalystOpinions": None,
        "recommendationKey": None,
    }
    try:
        info = yf.Ticker(yahoo_ticker).info
        return {
            **empty_row,
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
            "targetLowPrice": info.get("targetLowPrice"),
            "targetMeanPrice": info.get("targetMeanPrice"),
            "targetMedianPrice": info.get("targetMedianPrice"),
            "targetHighPrice": info.get("targetHighPrice"),
            "numberOfAnalystOpinions": info.get("numberOfAnalystOpinions"),
            "recommendationKey": info.get("recommendationKey"),
        }
    except Exception:
        return empty_row


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def fetch_analyst_data() -> pd.DataFrame:
    """Fetch analyst price targets for all companies via yfinance in parallel."""
    rows: list[dict] = []
    total = len(COMPANY_REGISTRY)

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.markdown(
        f'<div style="font-size:12px;color:#94A3B8;">'
        f'Fetching analyst consensus data for {total} companies...</div>',
        unsafe_allow_html=True,
    )

    completed = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_company = {
            executor.submit(_fetch_single_company, company): company
            for company in COMPANY_REGISTRY
        }
        for future in as_completed(future_to_company, timeout=180):
            try:
                result = future.result(timeout=3)
                rows.append(result)
            except Exception:
                # Graceful degradation: skip companies that fail or time out
                company = future_to_company[future]
                rows.append({
                    "ticker": company["ticker"],
                    "yahoo_ticker": company.get("yahoo_ticker", company["ticker"]),
                    "name": company["name"],
                    "segment": company["segment"],
                    "currentPrice": None,
                    "targetLowPrice": None,
                    "targetMeanPrice": None,
                    "targetMedianPrice": None,
                    "targetHighPrice": None,
                    "numberOfAnalystOpinions": None,
                    "recommendationKey": None,
                })
            completed += 1
            progress_bar.progress(completed / total)

    # Clear progress indicators once done
    progress_bar.empty()
    status_text.empty()

    return pd.DataFrame(rows)


df_analyst = fetch_analyst_data()

# Compute upside/downside
df_analyst["upside_pct"] = np.where(
    df_analyst["currentPrice"].notna() & df_analyst["targetMedianPrice"].notna() & (df_analyst["currentPrice"] > 0),
    ((df_analyst["targetMedianPrice"] - df_analyst["currentPrice"]) / df_analyst["currentPrice"]) * 100,
    np.nan,
)

# Add segment labels
df_analyst["seg_label"] = df_analyst["segment"].map(SEGMENT_SHORT).fillna(df_analyst["segment"])

# Filter out rows with no analyst data
df_valid = df_analyst.dropna(subset=["currentPrice", "targetMedianPrice", "numberOfAnalystOpinions"]).copy()
df_valid = df_valid[df_valid["numberOfAnalystOpinions"] > 0]

if df_valid.empty:
    st.warning("No analyst consensus data available. This may be a temporary issue with the data source.")
    st.stop()

# ── Segment filter pills ───────────────────────────────────────────────────

SEGMENTS = list(SEGMENT_DISPLAY.keys())
SEGMENT_LABELS = {k: SEGMENT_SHORT.get(k, v) for k, v in SEGMENT_DISPLAY.items()}

if "bc_segments" not in st.session_state:
    st.session_state["bc_segments"] = set(SEGMENTS)

selected = st.session_state["bc_segments"]

pill_cols = st.columns(len(SEGMENTS) + 1)

with pill_cols[0]:
    all_selected = len(selected) == len(SEGMENTS)
    if st.button(
        "All" if not all_selected else "Clear",
        key="bc_toggle_all",
        type="secondary",
    ):
        if all_selected:
            st.session_state["bc_segments"] = set()
        else:
            st.session_state["bc_segments"] = set(SEGMENTS)
        st.rerun()

for i, seg_key in enumerate(SEGMENTS):
    label = SEGMENT_LABELS[seg_key]
    is_on = seg_key in selected
    with pill_cols[i + 1]:
        if st.button(
            label,
            key=f"bc_pill_{seg_key}",
            type="primary" if is_on else "secondary",
        ):
            if is_on:
                st.session_state["bc_segments"].discard(seg_key)
            else:
                st.session_state["bc_segments"].add(seg_key)
            st.rerun()

# Inject CSS to color the pill buttons per-segment
pill_css_parts = []
for i, seg_key in enumerate(SEGMENTS):
    full_color = SEGMENT_COLORS.get(seg_key, "#374151")
    is_on = seg_key in selected
    col_idx = i + 2
    if is_on:
        pill_css_parts.append(
            f'[data-testid="stHorizontalBlock"] > div:nth-child({col_idx}) button[kind="primary"] {{'
            f'  background-color: {full_color} !important;'
            f'  border-color: {full_color} !important;'
            f'  color: #FFFFFF !important;'
            f'}}'
        )
    else:
        pill_css_parts.append(
            f'[data-testid="stHorizontalBlock"] > div:nth-child({col_idx}) button[kind="secondary"] {{'
            f'  background-color: #F3F4F6 !important;'
            f'  border-color: #D1D5DB !important;'
            f'  color: #9CA3AF !important;'
            f'}}'
        )

if pill_css_parts:
    st.markdown(f"<style>{''.join(pill_css_parts)}</style>", unsafe_allow_html=True)

selected = st.session_state["bc_segments"]

if not selected:
    st.info("Select at least one segment to display analyst consensus data.")
    st.stop()

# Filter to selected segments
df_filtered = df_valid[df_valid["segment"].isin(selected)].copy()

if df_filtered.empty:
    st.warning("No analyst data available for the selected segments.")
    st.stop()

# ── Summary stat cards ──────────────────────────────────────────────────────

med_upside = df_filtered["upside_pct"].median()
n_upside_20 = int((df_filtered["upside_pct"] > 20).sum())
n_downside_20 = int((df_filtered["upside_pct"] < -20).sum())
med_analysts = df_filtered["numberOfAnalystOpinions"].median()

upside_color = GREEN if med_upside >= 0 else RED
upside_sign = "+" if med_upside >= 0 else ""

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        f'<div class="bc-card">'
        f'<div class="bc-card-value" style="color:{upside_color};">{upside_sign}{med_upside:.1f}%</div>'
        f'<div class="bc-card-label">Median Upside to Target</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        f'<div class="bc-card">'
        f'<div class="bc-card-value" style="color:{GREEN};">{n_upside_20}</div>'
        f'<div class="bc-card-label">Stocks with &gt;20% Upside</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        f'<div class="bc-card">'
        f'<div class="bc-card-value" style="color:{RED};">{n_downside_20}</div>'
        f'<div class="bc-card-label">Stocks with &gt;20% Downside</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        f'<div class="bc-card">'
        f'<div class="bc-card-value">{med_analysts:.0f}</div>'
        f'<div class="bc-card-label">Median Analyst Count</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div style="height:20px;"></div>', unsafe_allow_html=True)

# ── Horizontal bar chart: Upside/Downside by company ───────────────────────

st.markdown(
    '<div style="font-size:14px;font-weight:600;color:#374151;margin-bottom:8px;">'
    'Upside / Downside to Median Analyst Target</div>',
    unsafe_allow_html=True,
)

df_bar = df_filtered.sort_values("upside_pct", ascending=True).copy()
bar_colors = [GREEN if v >= 0 else RED for v in df_bar["upside_pct"]]

fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    y=df_bar["name"],
    x=df_bar["upside_pct"],
    orientation="h",
    marker_color=bar_colors,
    text=df_bar["upside_pct"].apply(lambda v: f"{v:+.1f}%"),
    textposition="outside",
    textfont=dict(size=9, family="DM Sans, sans-serif"),
    hovertemplate=(
        "<b>%{y}</b><br>"
        "Upside/Downside: %{x:.1f}%<br>"
        "<extra></extra>"
    ),
))

bar_height = max(400, len(df_bar) * 22 + 80)
fig_bar.update_layout(
    plot_bgcolor=PLOTLY_BG,
    paper_bgcolor=PLOTLY_BG,
    font=dict(family="DM Sans, sans-serif", color=PLOTLY_TEXT, size=11),
    xaxis=dict(
        title="Upside / Downside (%)",
        gridcolor=PLOTLY_GRID,
        showgrid=True,
        zeroline=True,
        zerolinecolor="#374151",
        zerolinewidth=1,
        showline=True,
        linecolor="#E5E7EB",
        linewidth=1,
        ticksuffix="%",
        tickfont=dict(size=10),
    ),
    yaxis=dict(
        showgrid=False,
        showline=False,
        tickfont=dict(size=10),
        automargin=True,
    ),
    margin=dict(l=10, r=60, t=10, b=40),
    height=bar_height,
    bargap=0.3,
    showlegend=False,
)

st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

# ── Detailed HTML table ─────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    '<div style="font-size:14px;font-weight:600;color:#374151;margin-bottom:8px;">'
    'Analyst Consensus Detail</div>',
    unsafe_allow_html=True,
)

# Category pill styles
_CAT_BASE = (
    "padding:2px 8px; border-radius:4px; font-size:10px; font-weight:500;"
    " display:inline-block; white-space:nowrap;"
)
_CAT_PILLS = {}
for seg_key, short_name in SEGMENT_SHORT.items():
    bg, fg = LIGHT_BADGE_STYLES.get(short_name, ("#F1F5F9", "#64748B"))
    _CAT_PILLS[short_name] = f"background:{bg}; color:{fg}; {_CAT_BASE}"
_CAT_DEFAULT = f"background:#F1F5F9; color:#64748B; {_CAT_BASE}"

_ND = '<span style="color:#CBD5E1;">--</span>'

_HEADERS = [
    ("Company",       "bc-lt", 170),
    ("Ticker",        "bc-lt",  60),
    ("Segment",       "bc-lt", 110),
    ("Current",       "bc-rt",  75),
    ("Target Low",    "bc-rt",  80),
    ("Target Median", "bc-rt",  90),
    ("Target High",   "bc-rt",  80),
    ("Upside",        "bc-rt",  85),
    ("# Analysts",    "bc-ct",  70),
    ("Rec",           "bc-ct",  90),
]

# Sort by upside descending
df_table = df_filtered.sort_values("upside_pct", ascending=False)

head_cells = "".join(
    f'<th class="{align}" style="min-width:{w}px;max-width:{w}px;">{label}</th>'
    for label, align, w in _HEADERS
)

body_rows = []
for _, row in df_table.iterrows():
    safe_ticker = _html_lib.escape(str(row["ticker"]))
    safe_name = _html_lib.escape(str(row["name"]))
    short_name = (safe_name[:24] + "...") if len(safe_name) > 25 else safe_name

    # Company name (linked)
    td_name = (
        f'<td class="bc-lt">'
        f'<a class="bc-name-link" href="/Company?ticker={safe_ticker}" target="_self">'
        f'{short_name}</a></td>'
    )

    # Ticker
    td_ticker = f'<td class="bc-lt"><span class="bc-tkr">{safe_ticker}</span></td>'

    # Segment pill
    seg_label = row["seg_label"]
    pill_style = _CAT_PILLS.get(seg_label, _CAT_DEFAULT)
    td_seg = f'<td class="bc-lt"><span style="{pill_style}">{_html_lib.escape(str(seg_label))}</span></td>'

    # Current price
    cp = row["currentPrice"]
    td_current = f'<td class="bc-rt">${cp:.2f}</td>' if pd.notna(cp) else f'<td class="bc-rt">{_ND}</td>'

    # Target low
    tl = row["targetLowPrice"]
    td_low = f'<td class="bc-rt">${tl:.2f}</td>' if pd.notna(tl) else f'<td class="bc-rt">{_ND}</td>'

    # Target median
    tm = row["targetMedianPrice"]
    td_median = f'<td class="bc-rt" style="font-weight:600;">${tm:.2f}</td>' if pd.notna(tm) else f'<td class="bc-rt">{_ND}</td>'

    # Target high
    th_val = row["targetHighPrice"]
    td_high = f'<td class="bc-rt">${th_val:.2f}</td>' if pd.notna(th_val) else f'<td class="bc-rt">{_ND}</td>'

    # Upside/downside pill
    upside = row["upside_pct"]
    if pd.notna(upside):
        if upside >= 0:
            pill_bg = "#F0FDF4"
            pill_fg = "#16A34A"
            arrow = "&#9650;"  # up triangle
            sign = "+"
        else:
            pill_bg = "#FEF2F2"
            pill_fg = "#DC2626"
            arrow = "&#9660;"  # down triangle
            sign = ""
        td_upside = (
            f'<td class="bc-rt">'
            f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;'
            f'background:{pill_bg};color:{pill_fg};font-weight:600;font-size:11px;">'
            f'{arrow} {sign}{upside:.1f}%</span></td>'
        )
    else:
        td_upside = f'<td class="bc-rt">{_ND}</td>'

    # Analyst count
    n_analysts = row["numberOfAnalystOpinions"]
    td_analysts = (
        f'<td class="bc-ct">{int(n_analysts)}</td>'
        if pd.notna(n_analysts)
        else f'<td class="bc-ct">{_ND}</td>'
    )

    # Recommendation
    rec = row["recommendationKey"]
    if pd.notna(rec) and rec:
        rec_str = str(rec).replace("_", " ").title()
        rec_colors = {
            "Strong Buy": ("#F0FDF4", "#16A34A"),
            "Buy": ("#F0FDF4", "#059669"),
            "Overweight": ("#F0FDF4", "#059669"),
            "Hold": ("#FEF9C3", "#A16207"),
            "Underweight": ("#FEF2F2", "#DC2626"),
            "Sell": ("#FEF2F2", "#DC2626"),
            "Strong Sell": ("#FEF2F2", "#B91C1C"),
        }
        rbg, rfg = rec_colors.get(rec_str, ("#F1F5F9", "#64748B"))
        td_rec = (
            f'<td class="bc-ct">'
            f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
            f'background:{rbg};color:{rfg};font-weight:500;font-size:10px;">'
            f'{_html_lib.escape(rec_str)}</span></td>'
        )
    else:
        td_rec = f'<td class="bc-ct">{_ND}</td>'

    body_rows.append(f"<tr>{td_name}{td_ticker}{td_seg}{td_current}{td_low}{td_median}{td_high}{td_upside}{td_analysts}{td_rec}</tr>")

table_html = (
    f'<div class="bc-outer">'
    f'<table class="bc-tbl">'
    f'<thead><tr>{head_cells}</tr></thead>'
    f'<tbody>{"".join(body_rows)}</tbody>'
    f'</table>'
    f'</div>'
)

st.markdown(table_html, unsafe_allow_html=True)

# ── Scatter: Upside/Downside vs NTM EV/Revenue ─────────────────────────────

st.markdown("---")
st.markdown(
    '<div style="font-size:14px;font-weight:600;color:#374151;margin-bottom:8px;">'
    'Analyst Upside vs. NTM EV/Revenue</div>'
    '<div style="font-size:11px;color:#94A3B8;margin-bottom:12px;">'
    'Identifying undervalued stocks with analyst upside -- lower-right quadrant is most attractive</div>',
    unsafe_allow_html=True,
)

# Load NTM EV/Revenue from DB
db = DBManager(DB_PATH)

@st.cache_data(ttl=60)
def _load_db_data():
    data = db.get_all_latest_snapshots()
    ovr = load_overrides(EXCEL_OVERRIDE_PATH)
    if ovr and data:
        data = apply_overrides(data, ovr, skip_sources={"factset"})
    return data

db_records = _load_db_data()
if db_records:
    df_db = pd.DataFrame(db_records)[["ticker", "ntm_tev_rev"]].dropna()
    df_scatter = df_filtered.merge(df_db, on="ticker", how="inner")
    df_scatter = df_scatter.dropna(subset=["upside_pct", "ntm_tev_rev"])
    df_scatter = df_scatter[df_scatter["ntm_tev_rev"] > 0]

    if len(df_scatter) >= 3:
        fig_scatter = go.Figure()

        # Add traces per segment for colored legend
        for seg_key, seg_label in SEGMENT_SHORT.items():
            mask = df_scatter["segment"] == seg_key
            if not mask.any():
                continue
            seg_df = df_scatter[mask]
            color = SEGMENT_COLORS.get(seg_key, "#94A3B8")

            fig_scatter.add_trace(go.Scatter(
                x=seg_df["upside_pct"],
                y=seg_df["ntm_tev_rev"],
                mode="markers+text",
                marker=dict(size=8, color=color, opacity=0.85, line=dict(width=1, color="#FFFFFF")),
                text=seg_df["ticker"],
                textposition="top center",
                textfont=dict(size=8, color=color, family="DM Sans, sans-serif"),
                name=seg_label,
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Upside: %{x:.1f}%<br>"
                    "NTM EV/Rev: %{y:.1f}x<br>"
                    "<extra></extra>"
                ),
            ))

        # Add quadrant lines at 0% upside
        fig_scatter.add_vline(x=0, line_dash="dash", line_color="#D1D5DB", line_width=1)

        fig_scatter.update_layout(
            plot_bgcolor=PLOTLY_BG,
            paper_bgcolor=PLOTLY_BG,
            font=dict(family="DM Sans, sans-serif", color=PLOTLY_TEXT, size=11),
            xaxis=dict(
                title="Upside / Downside to Median Target (%)",
                gridcolor=PLOTLY_GRID,
                showgrid=True,
                zeroline=False,
                showline=True,
                linecolor="#E5E7EB",
                linewidth=1,
                ticksuffix="%",
                tickfont=dict(size=10),
            ),
            yaxis=dict(
                title="NTM EV / Revenue (x)",
                gridcolor=PLOTLY_GRID,
                showgrid=True,
                zeroline=False,
                showline=True,
                linecolor="#E5E7EB",
                linewidth=1,
                ticksuffix="x",
                tickfont=dict(size=10),
            ),
            margin=dict(l=50, r=20, t=20, b=50),
            height=560,
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                font=dict(size=10),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            ),
            showlegend=True,
        )

        st.plotly_chart(fig_scatter, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("Not enough data to render the scatter plot.")
else:
    st.caption("Database not populated -- run the data fetcher first.")

# ── Source attribution ──────────────────────────────────────────────────────
st.markdown(
    '<div class="bc-source">'
    'Source: Yahoo Finance analyst consensus estimates. Price targets and recommendations '
    'reflect the latest available broker coverage. Data refreshed every 24 hours.'
    '</div>',
    unsafe_allow_html=True,
)
