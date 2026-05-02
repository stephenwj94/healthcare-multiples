"""
Top 25 Winners & Losers – institutional dark theme with analytics tabs.
Styled to match Meritech / MS Software Weekly aesthetic.
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import html as _html_lib
from pathlib import Path
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

try:
    from scipy import stats as _sp_stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from components.logos import logo_img_tag
from config.settings import DB_PATH, EXCEL_OVERRIDE_PATH, SEGMENT_DISPLAY
from config.color_palette import (
    SEGMENT_SHORT, SEG_COLOR_MAP, SEGMENT_COLORS,
    BADGE_STYLES, LIGHT_BADGE_STYLES,
    GREEN, YELLOW, RED, MUTED, TICKER_COLOR,
    PLOTLY_BG, PLOTLY_GRID, PLOTLY_TEXT,
)
from fetcher.db_manager import DBManager
from fetcher.excel_override import load_overrides, apply_overrides

IS_LIGHT = True

# ── Force full-width layout + DM Sans font ──────────────────────────────────
# Structure-only CSS (no colors — dark/light colors injected below after IS_LIGHT check)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');

.block-container {
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* Stat card grid — structure only */
.stat-grid { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.stat-card {
    border-radius: 12px;
    padding: 20px 24px;
    min-width: 130px;
    flex: 1;
    transition: box-shadow 0.15s ease;
}
.stat-label { font-size: 15px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.stat-value { font-size: 34px; font-weight: 800; line-height: 1.2; }
.stat-sub   { font-size: 14px; font-weight: 500; margin-top: 8px; }
.stat-delta-up   { font-weight: 700; font-size: 15px; }
.stat-delta-down { font-weight: 700; font-size: 15px; }
.stat-delta-neut { font-weight: 500; font-size: 11px; }

/* Section subheader — structure only */
.section-head {
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin: 40px 0 20px 0;
    border-bottom: 2px solid;
    padding: 0 0 12px 0;
}

/* Table title (Winners / Losers labels) — structure only */
.table-title {
    font-size: 15px;
    font-weight: 700;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
.dot-green { width: 9px; height: 9px; border-radius: 50%; background-color: #22C55E; display: inline-block; flex-shrink: 0; }
.dot-red   { width: 9px; height: 9px; border-radius: 50%; background-color: #EF4444; display: inline-block; flex-shrink: 0; }

/* Table column header — structure only */
div[data-testid="stDataFrame"] [role="columnheader"] {
    font-size: 10px !important;
    letter-spacing: 0.04em !important;
}

/* ── iPad / tablet responsive ── */
@media (max-width: 1024px) {
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    .stat-grid { gap: 8px; }
    .stat-card { padding: 16px 18px; min-width: 110px; }
    .stat-label { font-size: 13px; }
    .stat-value { font-size: 28px; }
    .stat-sub   { font-size: 12px; }
}
</style>
""", unsafe_allow_html=True)

render_sidebar()

db = DBManager(DB_PATH)
try:
    all_data = db.get_all_latest_snapshots()
except Exception:
    all_data = []

overrides = load_overrides(EXCEL_OVERRIDE_PATH)
if overrides and all_data:
    all_data = apply_overrides(all_data, overrides, skip_sources={"factset"})

if not all_data:
    st.info("No data available. Run the data fetcher to populate the database.")
    st.stop()

# ── Historical data for breadth chart ────────────────────────────────────────
try:
    hist_data = db.get_historical_snapshots(days_back=180)
    hist_dates = db.get_distinct_snapshot_dates(days_back=180)
except Exception:
    hist_data = []
    hist_dates = []

# ── Date context ─────────────────────────────────────────────────────────────
raw_dates = [d.get("snapshot_date") for d in all_data if d.get("snapshot_date")]
latest_date_str = ""
if raw_dates:
    try:
        latest_dt = max(datetime.strptime(str(d)[:10], "%Y-%m-%d") for d in raw_dates)
        latest_date_str = latest_dt.strftime("%B %d, %Y")
    except Exception:
        pass

_date_suffix = ""
if latest_date_str:
    _date_suffix = (
        f'&nbsp;&nbsp;&middot;&nbsp;&nbsp;<span style="color:#9CA3AF;">'
        f'Data as of {latest_date_str}</span>'
    )
# NOTE: page title rendered conditionally at bottom based on _page_view toggle

# ── Constants (colours imported from config.color_palette) ───────────────────
# Sentiment pill backgrounds (light mode)
PILL_BG_POS = "rgba(5,150,105,0.10)"
PILL_BG_NEG = "rgba(220,38,38,0.10)"
# Light mode — config.toml base="light" already handles component colors.
# We only need to pin the app shell and custom-HTML elements.
st.markdown("""
<style>
/* ── Page background — faint warm gray so white elements pop ── */
.stApp { background-color: #FAFBFC !important; }
.main .block-container { background-color: #FAFBFC !important; color: #1A1A2E !important; }
/* ── Typography ── */
h1,h2,h3,h4,h5,h6 { color: #111827 !important; }
.stMarkdown p, .stMarkdown span, .stMarkdown div { color: #1A1A2E !important; }
label { color: #374151 !important; }
.stCaption p, [data-testid="stCaptionContainer"] p { color: #9CA3AF !important; }
/* ── Tabs — gap between labels, underline active ── */
.stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid #E5E7EB !important; gap: 4px !important; }
.stTabs [data-baseweb="tab"], button[role="tab"] {
    font-size: 13px !important; font-weight: 500 !important;
    color: #9CA3AF !important; background: transparent !important;
    border-bottom: 2px solid transparent !important;
    padding: 10px 20px !important; margin-right: 4px !important;
}
.stTabs [aria-selected="true"], button[role="tab"][aria-selected="true"] {
    color: #111827 !important; font-weight: 600 !important;
    border-bottom: 2px solid #3B82F6 !important;
}
/* ── Metrics ── */
[data-testid="stMetric"] { background: transparent !important; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { color: #111827 !important; }
[data-testid="stMetricLabel"] p, [data-testid="stMetricLabel"] * { color: #6B7280 !important; }
hr { border-color: #E5E7EB !important; }
.stButton button { background: #FFFFFF !important; border: 1px solid #E5E7EB !important; color: #374151 !important; }
/* ── Stat cards — white with border + layered shadow ── */
.stat-card {
    background: #FFFFFF !important;
    border: 1px solid #E5E7EB !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02) !important;
}
.stat-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.07), 0 1px 3px rgba(0,0,0,0.04) !important;
}
.stat-label { color: #6B7280 !important; }
.stat-value { color: #111827 !important; font-weight: 700 !important; }
.stat-sub { color: #9CA3AF !important; }
.stat-delta-up { color: #059669 !important; } .stat-delta-down { color: #DC2626 !important; } .stat-delta-neut { color: #9CA3AF !important; }
/* ── Section head — darker, heavier border ── */
.section-head { color: #374151 !important; border-bottom-color: #E5E7EB !important; }
/* ── Table title color ── */
.table-title { color: #111827 !important; }
/* ── Table container — card treatment ── */
[data-testid="stDataFrame"] {
    border: 1px solid #E5E7EB !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    overflow: hidden !important;
}
[data-testid="stDataFrame"] > div { background-color: #FFFFFF !important; }
/* Column headers — #F9FAFB bg, 2px separator ── */
div[data-testid="stDataFrame"] [role="columnheader"],
div[data-testid="stDataFrame"] [role="columnheader"] * {
    color: #6B7280 !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: 0.04em !important;
    background-color: #F9FAFB !important;
    border-bottom: 2px solid #E5E7EB !important;
}
/* Data rows — alternating + hover */
div[data-testid="stDataFrame"] td { border-bottom: 1px solid #F3F4F6 !important; color: #1A1A2E !important; }
div[data-testid="stDataFrame"] tr:nth-child(odd) td  { background-color: #FFFFFF !important; }
div[data-testid="stDataFrame"] tr:nth-child(even) td { background-color: #FAFBFC !important; }
div[data-testid="stDataFrame"] tr:hover td           { background-color: #EFF6FF !important; }
</style>
""", unsafe_allow_html=True)

# ── HTML table CSS (injected once per render call) ───────────────────────────

_WL_CSS = """
<style>
.wl-outer {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.wl-tbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-variant-numeric: tabular-nums;
    font-family: 'DM Sans', sans-serif;
}
.wl-tbl thead th {
    font-size: 9px;
    font-weight: 500;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 6px 10px;
    border-bottom: 1px solid #E5E7EB;
    background: #FFFFFF;
    white-space: nowrap;
}
.wl-tbl tbody td {
    padding: 5px 10px;
    border-bottom: 1px solid #F3F4F6;
    color: #374151;
    line-height: 1.3;
    white-space: nowrap;
    vertical-align: middle;
}
.wl-tbl tbody tr:nth-child(odd) td  { background: #FFFFFF; }
.wl-tbl tbody tr:nth-child(even) td { background: #FAFBFD; }
.wl-tbl tbody tr:hover td           { background: #F0F4FF !important; }
.wl-rt { text-align: right; }
.wl-lt { text-align: left; }
.wl-ct { text-align: center; }
.wl-tkr { color: #3B82F6; font-weight: 600; font-size: 11px; }
</style>
"""

# ── Category pill styles ──────────────────────────────────────────────────────

_WL_CAT_BASE = (
    "padding:2px 8px; border-radius:4px; font-size:10px; font-weight:500;"
    " display:inline-block; white-space:nowrap;"
)
_WL_CAT_PILLS = {
    "Pharma":          f"background:#E9EFFC; color:#1D4ED8; {_WL_CAT_BASE}",
    "Consumer Health": f"background:#E6F4EE; color:#047857; {_WL_CAT_BASE}",
    "MedTech":         f"background:#FCEAEA; color:#B91C1C; {_WL_CAT_BASE}",
    "Life Sci Tools":  f"background:#F1EAFB; color:#6D28D9; {_WL_CAT_BASE}",
    "LST / Dx":        f"background:#F1EAFB; color:#6D28D9; {_WL_CAT_BASE}",
    "Services":        f"background:#FEF3E2; color:#B45309; {_WL_CAT_BASE}",
    "Asset-Light Services": f"background:#FEF3E2; color:#B45309; {_WL_CAT_BASE}",
    "CDMOs":           f"background:#FDECE0; color:#C2410C; {_WL_CAT_BASE}",
    "Asset-Heavy Services": f"background:#FDECE0; color:#C2410C; {_WL_CAT_BASE}",
    "Health Tech":     f"background:#E2F1F5; color:#0E7490; {_WL_CAT_BASE}",
}
_WL_CAT_DEFAULT = f"background:#F1F5F9; color:#64748B; {_WL_CAT_BASE}"

# ── Null sentinel ─────────────────────────────────────────────────────────────

_WL_ND       = '<span style="color:#CBD5E1;">—</span>'
_WL_MULT_CAP = 75.0

# ── Cell renderers ────────────────────────────────────────────────────────────

def _wl_rank(i):
    return (
        f'<td class="wl-ct" style="color:#CBD5E1;font-size:11px;font-weight:400;">'
        f'{i}</td>'
    )

def _wl_ticker(val):
    t = _html_lib.escape(str(val or "?"))
    logo = logo_img_tag(t, size=16)
    logo_html = f'{logo}&nbsp;' if logo else ''
    return f'<td class="wl-lt">{logo_html}<span class="wl-tkr">{t}</span></td>'

def _wl_company(val):
    full  = str(val or "\u2013")
    short = (full[:21] + "\u2026") if len(full) > 22 else full
    esc   = _html_lib.escape(short)
    return f'<td class="wl-lt" style="color:#374151;">{esc}</td>'

def _wl_category(val):
    cat = str(val) if val else ""
    sty = _WL_CAT_PILLS.get(cat, _WL_CAT_DEFAULT)
    esc = _html_lib.escape(cat) if cat else "\u2013"
    return f'<td class="wl-lt"><span style="{sty}">{esc}</span></td>'

def _wl_tev(val):
    """val is raw dollars (enterprise_value field)."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return f'<td class="wl-rt">{_WL_ND}</td>'
    if v <= 0 or np.isnan(v):
        return f'<td class="wl-rt">{_WL_ND}</td>'
    if v >= 1e9:
        return f'<td class="wl-rt">${v / 1e9:.1f}B</td>'
    return f'<td class="wl-rt">${v / 1e6:.0f}M</td>'

def _wl_mult(val):
    """NTM Rev x or NTM EBITDA x -- already in multiple units (e.g. 5.4)."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return f'<td class="wl-rt" style="color:#CBD5E1;font-style:italic;">N/M</td>'
    try:
        if np.isnan(v):
            return f'<td class="wl-rt" style="color:#CBD5E1;font-style:italic;">N/M</td>'
    except Exception:
        pass
    if v <= 0:
        return f'<td class="wl-rt" style="color:#CBD5E1;font-style:italic;">N/M</td>'
    if v > _WL_MULT_CAP:
        return (
            f'<td class="wl-rt" style="color:#CBD5E1;font-style:italic;">'
            f'&gt;{_WL_MULT_CAP:.0f}x</td>'
        )
    return f'<td class="wl-rt">{v:.1f}x</td>'

def _wl_growth(val):
    """val is raw decimal (0.20 = 20%). Display as integer %, colored."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return f'<td class="wl-rt">{_WL_ND}</td>'
    try:
        if np.isnan(v):
            return f'<td class="wl-rt">{_WL_ND}</td>'
    except Exception:
        pass
    pct = v * 100
    if   pct >= 25: color = "#16A34A"
    elif pct >= 15: color = "#374151"
    elif pct >= 5:  color = "#CA8A04"
    else:           color = "#DC2626"
    sign = "+" if pct >= 0 else ""
    return (
        f'<td class="wl-rt" style="color:{color};font-weight:500;">'
        f'{sign}{pct:.0f}%</td>'
    )

def _wl_chg_winner(val):
    """val is raw decimal -- multiply by 100 for %."""
    try:
        v = float(val) * 100
    except (TypeError, ValueError):
        return f'<td class="wl-rt">{_WL_ND}</td>'
    try:
        if np.isnan(v):
            return f'<td class="wl-rt">{_WL_ND}</td>'
    except Exception:
        pass
    pill = (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;'
        f'background:#F0FDF4;color:#16A34A;font-weight:600;font-size:11px;">'
        f'\u25b2 {v:.1f}%</span>'
    )
    return f'<td class="wl-rt">{pill}</td>'

def _wl_chg_loser(val):
    """val is raw decimal -- multiply by 100 for %."""
    try:
        v = float(val) * 100
    except (TypeError, ValueError):
        return f'<td class="wl-rt">{_WL_ND}</td>'
    try:
        if np.isnan(v):
            return f'<td class="wl-rt">{_WL_ND}</td>'
    except Exception:
        pass
    pill = (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:4px;'
        f'background:#FEF2F2;color:#DC2626;font-weight:600;font-size:11px;">'
        f'\u25bc ({abs(v):.1f}%)</span>'
    )
    return f'<td class="wl-rt">{pill}</td>'

# ── HTML table builder ────────────────────────────────────────────────────────

_WL_HEADERS = [
    ("#",            "wl-ct",  32),
    ("Ticker",       "wl-lt",  60),
    ("Company",      "wl-lt", 152),
    ("Category",     "wl-lt", 112),
    ("TEV",          "wl-rt",  72),
    ("NTM Rev x",    "wl-rt",  82),
    ("NTM EBITDA x", "wl-rt",  90),
    ("NTM Gr%",      "wl-rt",  68),
    ("Chg%",         "wl-rt", 100),
]

def _build_wl_html(records, change_col, is_winner):
    """Return a complete HTML string for a W/L table."""
    _chg_fn = _wl_chg_winner if is_winner else _wl_chg_loser

    head_cells = "".join(
        f'<th class="{align}" style="min-width:{w}px;max-width:{w}px;">{label}</th>'
        for label, align, w in _WL_HEADERS
    )

    body_rows = []
    for i, d in enumerate(records, 1):
        rev_growth = d.get("ntm_revenue_growth")
        cat = SEGMENT_SHORT.get(d.get("segment", ""), d.get("segment", ""))
        tds = (
            _wl_rank(i)
            + _wl_ticker(d.get("ticker"))
            + _wl_company(d.get("name"))
            + _wl_category(cat)
            + _wl_tev(d.get("enterprise_value"))
            + _wl_mult(d.get("ntm_tev_rev"))
            + _wl_mult(d.get("ntm_tev_ebitda"))
            + _wl_growth(rev_growth)
            + _chg_fn(d.get(change_col))
        )
        body_rows.append(f"<tr>{tds}</tr>")

    return (
        f'<div class="wl-outer">'
        f'<table class="wl-tbl">'
        f'<thead><tr>{head_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody>'
        f'</table>'
        f'</div>'
    )


# ── Plotly chart helpers ───────────────────────────────────────────────────────

def _plotly_layout(title="", height=320):
    # NOTE: xaxis and yaxis must be SEPARATE dicts — callers do layout["xaxis"].update(...)
    # and layout["yaxis"].update(...), so a shared reference would corrupt both axes.
    _axis_defaults = dict(
        gridcolor=PLOTLY_GRID, showgrid=True, zeroline=False,
        showline=True, linecolor="#E5E7EB", linewidth=1,
        tickfont=dict(size=10),
    )
    _hover_bg   = "rgba(255,255,255,0.97)" if IS_LIGHT else "#1A2540"
    _hover_font = "#1F2937"                 if IS_LIGHT else "#F9FAFB"
    return dict(
        title=dict(text=title, font=dict(size=13, color=PLOTLY_TEXT)),
        plot_bgcolor=PLOTLY_BG,
        paper_bgcolor=PLOTLY_BG,
        font=dict(family="DM Sans, sans-serif", color=PLOTLY_TEXT, size=11),
        xaxis=dict(**_axis_defaults),   # independent copy
        yaxis=dict(**_axis_defaults),   # independent copy
        margin=dict(l=50, r=20, t=40, b=40),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0,
                    font=dict(size=10)),
        hoverlabel=dict(bgcolor=_hover_bg,
                        font=dict(size=11, color=_hover_font,
                                  family="DM Sans, sans-serif"),
                        bordercolor="#E5E7EB"),
    )


def _chart_breadth(hist_data, change_col):
    """Line chart (or single bar) of % advancing per snapshot date."""
    if not hist_data:
        return None

    df = pd.DataFrame(hist_data)
    df = df.dropna(subset=[change_col])
    if df.empty:
        return None

    groups = df.groupby("snapshot_date").apply(
        lambda g: pd.Series({
            "adv":   (g[change_col] >= 0).sum(),
            "dec":   (g[change_col] < 0).sum(),
            "total": len(g),
        })
    ).reset_index()
    groups["pct_adv"] = groups["adv"] / groups["total"] * 100
    groups = groups.sort_values("snapshot_date")

    def _fmt_date(ds):
        try:
            return datetime.strptime(str(ds)[:10], "%Y-%m-%d").strftime("%b %-d")
        except Exception:
            return str(ds)[:10]

    groups["date_label"] = groups["snapshot_date"].apply(_fmt_date)

    fig = go.Figure()

    if len(groups) == 1:
        fig.add_trace(go.Bar(
            x=groups["date_label"], y=groups["pct_adv"],
            marker_color=GREEN,
            hovertemplate="%{x}<br>Adv: %{y:.1f}%<extra></extra>",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=groups["date_label"], y=groups["pct_adv"],
            mode="lines+markers",
            line=dict(color=GREEN, width=2),
            marker=dict(size=5),
            name="% Advancing",
            hovertemplate="%{x}<br>Adv: %{y:.1f}%<extra></extra>",
        ))

    fig.add_hline(y=50, line_dash="dash", line_color=PLOTLY_GRID, line_width=1)
    layout = _plotly_layout("Breadth: % Advancing Over Time", height=196)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["yaxis"]["range"] = [0, 100]
    layout["xaxis"]["type"] = "category"
    layout["xaxis"]["tickangle"] = 0
    layout["margin"]["r"] = 40
    fig.update_layout(**layout)

    fig.add_annotation(
        x=1, xref="paper", y=50, yref="y",
        text="50%", showarrow=False,
        font=dict(size=9, color=PLOTLY_GRID),
        xanchor="left", yanchor="middle", xshift=5,
    )

    if len(groups) == 1:
        fig.add_annotation(
            text="Trend will populate as data accumulates",
            xref="paper", yref="paper", x=0.5, y=-0.18,
            showarrow=False,
            font=dict(size=10, color=PLOTLY_TEXT),
        )

    return fig


def _chart_by_category(valid, change_col):
    """Box plot of % changes by segment category."""
    if not valid:
        return None

    rows = []
    for d in valid:
        chg = d.get(change_col)
        seg = SEGMENT_SHORT.get(d.get("segment", ""), d.get("segment", ""))
        if chg is not None:
            rows.append({"Category": seg, "Change": chg * 100})
    if not rows:
        return None

    df = pd.DataFrame(rows)
    cats = list(SEG_COLOR_MAP.keys())
    df["Category"] = pd.Categorical(df["Category"], categories=cats, ordered=True)
    df = df.sort_values("Category")

    fig = go.Figure()
    for cat in cats:
        sub = df[df["Category"] == cat]
        if sub.empty:
            continue
        fig.add_trace(go.Box(
            y=sub["Change"],
            name=cat,
            marker_color=SEG_COLOR_MAP.get(cat, "#6B7280"),
            line_color=SEG_COLOR_MAP.get(cat, "#6B7280"),
            boxmean=True,
            hovertemplate="%{y:.1f}%<extra>" + cat + "</extra>",
        ))
    layout = _plotly_layout("Movement Distribution by Category", height=280)
    layout["yaxis"]["ticksuffix"] = "%"
    layout["showlegend"] = False
    fig.update_layout(**layout)
    return fig


# ── (Valuation Trends + Scatter moved to 03_Valuation_Regression.py) ──────────


# ── Stat card HTML builder ────────────────────────────────────────────────────

def _stat_card(label, value, sub="", delta_val=None, extra_html="", top_color="#4A90D9"):
    if delta_val is not None:
        if delta_val > 0:
            delta_html = f'<div class="stat-delta-up">\u25b2 {abs(delta_val):.1f}%</div>'
        elif delta_val < 0:
            delta_html = f'<div class="stat-delta-down">\u25bc {abs(delta_val):.1f}%</div>'
        else:
            delta_html = f'<div class="stat-delta-neut">\u2500 0.0%</div>'
    else:
        delta_html = ""

    sub_html = f'<div class="stat-sub">{sub}</div>' if sub else ""
    return f"""
<div class="stat-card">
  <div class="stat-label">{label}</div>
  <div class="stat-value">{value}</div>
  {delta_html}
  {sub_html}
  {extra_html}
</div>"""




# ─────────────────────────────────────────────────────────────────────────────
# MULTI-PERIOD MOVERS — yfinance-powered
# ─────────────────────────────────────────────────────────────────────────────


_MP_PERIOD_NAMES  = ["Last Week", "Last Month", "Last 3M", "Last 6M", "Last 12M", "YTD"]
_MP_PERIOD_LABELS = {
    "Last Week":  "LAST WEEK",
    "Last Month": "LAST MONTH",
    "Last 3M":    "LAST 3M",
    "Last 6M":    "LAST 6M",
    "Last 12M":   "LAST 12M",
    "YTD":        "YTD",
}


def _mp_period_start(period_name, as_of):
    """Return the start Timestamp for a named period relative to as_of."""
    as_of = pd.Timestamp(as_of)
    if period_name == "Last Week":   return as_of - pd.Timedelta(weeks=1)
    if period_name == "Last Month":  return as_of - pd.DateOffset(months=1)
    if period_name == "Last 3M":     return as_of - pd.DateOffset(months=3)
    if period_name == "Last 6M":     return as_of - pd.DateOffset(months=6)
    if period_name == "Last 12M":    return as_of - pd.DateOffset(months=12)
    if period_name == "YTD":         return pd.Timestamp(f"{as_of.year - 1}-12-31")
    return as_of - pd.Timedelta(weeks=1)


@st.cache_data(ttl=3600, show_spinner=False)
def _mp_fetch_prices(tickers_tuple):
    """Batch-download 14 months of adj-close prices from yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame()
    tickers = list(tickers_tuple)
    start = (pd.Timestamp.today() - pd.DateOffset(months=14)).strftime("%Y-%m-%d")
    try:
        raw = yf.download(tickers, start=start, auto_adjust=True,
                          progress=False, threads=True)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].copy()
        else:
            close = raw[["Close"]].copy()
            if len(tickers) == 1:
                close.columns = [tickers[0]]
        close.index = pd.to_datetime(close.index).tz_localize(None)
        return close
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _mp_fetch_index_prices():
    """Download S&P 500, NASDAQ, and BVP Cloud index closes."""
    try:
        import yfinance as yf
    except ImportError:
        return {}, "BVP Cloud Index"
    start = (pd.Timestamp.today() - pd.DateOffset(months=14)).strftime("%Y-%m-%d")
    results = {}
    for name, sym in [("S&P 500", "^GSPC"), ("NASDAQ", "^IXIC")]:
        try:
            hist = yf.Ticker(sym).history(start=start, auto_adjust=True)
            if hist.index.tz:
                hist.index = hist.index.tz_localize(None)
            results[name] = hist["Close"] if not hist.empty else None
        except Exception:
            results[name] = None
    bvp_label = "BVP Cloud Index"
    results["BVP Cloud"] = None
    for sym, proxy in [("SKYY", "SKYY"), ("WCLD", "WCLD")]:
        try:
            hist = yf.Ticker(sym).history(start=start, auto_adjust=True)
            if not hist.empty:
                if hist.index.tz:
                    hist.index = hist.index.tz_localize(None)
                results["BVP Cloud"] = hist["Close"]
                bvp_label = (
                    f'BVP Cloud Index'
                    f'<span style="font-size:8px;color:#94A3B8;font-weight:400;">'
                    f' ({proxy} proxy)</span>'
                )
                break
        except Exception:
            continue
    return results, bvp_label


def _mp_price_on(series, target):
    """Price on or just before target date, or None."""
    if series is None or series.empty:
        return None
    target = pd.Timestamp(target)
    prior = series[series.index <= target]
    return float(prior.iloc[-1]) if not prior.empty else None


def _mp_compute_returns(close_df, as_of, periods):
    """Returns dict {period: Series(ticker -> pct_return)}."""
    if close_df.empty:
        return {p: pd.Series(dtype=float) for p in periods}
    as_of = pd.Timestamp(as_of)
    prior_idx = close_df.index[close_df.index <= as_of]
    if prior_idx.empty:
        return {p: pd.Series(dtype=float) for p in periods}
    cur = close_df.loc[prior_idx[-1]].dropna()
    result = {}
    for period in periods:
        start   = _mp_period_start(period, as_of)
        past_idx = close_df.index[close_df.index <= start]
        if past_idx.empty:
            result[period] = pd.Series(dtype=float)
            continue
        past   = close_df.loc[past_idx[-1]].dropna()
        common = cur.index.intersection(past.index)
        if common.empty:
            result[period] = pd.Series(dtype=float)
            continue
        past_safe = past[common].replace(0, np.nan)
        ret = ((cur[common] / past_safe) - 1) * 100
        result[period] = ret.dropna()
    return result


def _mp_compute_index_returns(index_prices, as_of, periods):
    """Returns dict {index_name: {period: pct_return|None}}."""
    results = {}
    for name, series in index_prices.items():
        cur = _mp_price_on(series, as_of)
        if cur is None:
            results[name] = {p: None for p in periods}
            continue
        pr = {}
        for period in periods:
            past = _mp_price_on(series, _mp_period_start(period, as_of))
            pr[period] = ((cur / past) - 1) * 100 if past and past != 0 else None
        results[name] = pr
    return results


def _mp_availability(close_df, as_of, periods):
    """Returns {period: bool} -- True if historical data covers that period."""
    avail = {}
    as_of = pd.Timestamp(as_of)
    for period in periods:
        start = _mp_period_start(period, as_of)
        if close_df.empty:
            avail[period] = False
        else:
            avail[period] = len(close_df.index[close_df.index <= start]) > 0
    return avail


def _mp_fmt_pct(val, direction):
    """Return (text, color_hex, bg_css) for a pct value."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "\u2014", "#CBD5E1", "transparent"
    val = float(val)
    if val < 0:
        text  = f"({abs(val):.0f}%)"
        color = "#DC2626"
    else:
        text  = f"{val:.0f}%"
        color = "#16A34A" if direction == "winners" else "#DC2626"
    if direction == "winners":
        bg = "rgba(22,163,74,0.08)" if val >= 50 else "rgba(22,163,74,0.04)" if val >= 20 else "transparent"
    else:
        bg = "rgba(220,38,38,0.08)" if val <= -30 else "rgba(220,38,38,0.04)" if val <= -15 else "transparent"
    return text, color, bg


def _mp_winner_heat(v):
    if v >= 100: return "rgba(22,163,74,0.22)"
    elif v >= 50: return "rgba(22,163,74,0.15)"
    elif v >= 30: return "rgba(22,163,74,0.10)"
    elif v >= 15: return "rgba(22,163,74,0.05)"
    else:         return "rgba(22,163,74,0.015)"


def _mp_loser_heat(v):
    a = abs(v)
    if a >= 70: return "rgba(220,38,38,0.20)"
    elif a >= 50: return "rgba(220,38,38,0.14)"
    elif a >= 30: return "rgba(220,38,38,0.09)"
    elif a >= 15: return "rgba(220,38,38,0.05)"
    else:         return "rgba(220,38,38,0.015)"


def _mp_bm_heat(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "transparent"
    if v >= 0:
        return f"rgba(22,163,74,{min(0.15, abs(v) / 100 * 0.3):.2f})"
    else:
        return f"rgba(220,38,38,{min(0.15, abs(v) / 100 * 0.3):.2f})"


def _mp_cell(val, direction):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "\u2014", "#CBD5E1", "transparent"
    v = float(val)
    text = f"({abs(v):.0f}%)" if v < 0 else f"{v:.0f}%"
    if direction == "winners":
        color   = "#16A34A"
        heat_bg = _mp_winner_heat(v)
    else:
        color   = "#DC2626"
        heat_bg = _mp_loser_heat(v)
    return text, color, heat_bg


def _mp_bm_cell(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "\u2014", "#CBD5E1", "transparent"
    v = float(val)
    text    = f"({abs(v):.0f}%)" if v < 0 else f"{v:.0f}%"
    color   = "#DC2626" if v < 0 else "#16A34A"
    heat_bg = _mp_bm_heat(v)
    return text, color, heat_bg


def _render_combined_html(period_returns, period_avail, index_returns=None, sw_returns=None,
                          n=10, bvp_label="BVP Cloud Index"):
    """ONE table: Winners + Losers with perfect column alignment."""
    periods  = _MP_PERIOD_NAMES
    n_period = len(periods)
    n_cols   = 1 + n_period * 2

    def _col_bg(pi):
        return "#F8FAFC" if pi % 2 == 1 else "transparent"

    colgroup = '<colgroup><col style="width:18px;">'
    for _ in periods:
        colgroup += '<col style="width:72px;"><col style="width:52px;">'
    colgroup += '</colgroup>'

    head1 = (
        '<th style="'
        'width:18px;min-width:18px;'
        'border-right:1px solid #E5E7EB;'
        'border-bottom:2px solid #E5E7EB;'
        'background:#F9FAFB;'
        'position:sticky;top:0;z-index:21;"></th>'
    )
    for pi, p in enumerate(periods):
        label    = _MP_PERIOD_LABELS.get(p, p)
        avail    = period_avail.get(p, True)
        txt_col  = "#111827" if avail else "#94A3B8"
        hdr_bg   = "#F1F5F9" if pi % 2 == 1 else "#F9FAFB"
        head1 += (
            f'<th colspan="2" style="'
            f'text-align:center;font-size:13px;font-weight:800;'
            f'color:{txt_col};text-transform:uppercase;letter-spacing:0.05em;'
            f'padding:14px 8px;'
            f'border-bottom:2px solid #E5E7EB;'
            f'border-left:1px solid #E5E7EB;background:{hdr_bg};'
            f'position:sticky;top:0;z-index:20;">{label}</th>'
        )

    thead = (
        f'<thead>'
        f'<tr style="background:#F9FAFB;">{head1}</tr>'
        f'</thead>'
    )

    def _data_row(rank, sorted_returns_by_period, direction):
        tick_fw  = "700" if rank <= 3 else "500"
        tick_col = "#111827" if rank <= 3 else "#475569"
        rank_bg = "background:rgba(251,191,36,0.06);" if rank == 1 else ""
        rank_col = "#111827"
        row = (
            f'<tr style="{rank_bg}">'
            f'<td style="text-align:center;font-size:13px;color:{rank_col};font-weight:700;'
            f'padding:6px 0px;width:18px;min-width:18px;max-width:18px;'
            f'border-right:1px solid #E5E7EB;'
            f'border-bottom:1px solid #F3F4F6;">{rank}</td>'
        )
        for pi, p in enumerate(periods):
            col_bg = _col_bg(pi)
            if not period_avail.get(p, True):
                row += (
                    f'<td style="border-left:1.5px solid #E2E8F0;padding:5px 8px;'
                    f'background:{col_bg};border-bottom:1px solid #F3F4F6;'
                    f'color:#CBD5E1;font-size:11px;">\u2014</td>'
                    f'<td style="padding:5px 8px;background:{col_bg};'
                    f'border-bottom:1px solid #F3F4F6;color:#CBD5E1;font-size:11px;">\u2014</td>'
                )
                continue
            sorted_s = sorted_returns_by_period.get(p, pd.Series(dtype=float))
            if rank <= len(sorted_s):
                ticker             = sorted_s.index[rank - 1]
                pct                = sorted_s.iloc[rank - 1]
                pct_text, pct_col, heat_bg = _mp_cell(pct, direction)
                logo = logo_img_tag(ticker, size=14)
                logo_html = f'{logo}&nbsp;' if logo else ''
                pct_size = "13px" if rank <= 3 else "12px"
                row += (
                    f'<td style="text-align:left;font-size:11px;'
                    f'font-weight:{tick_fw};color:{tick_col};'
                    f'padding:5px 8px;border-bottom:1px solid #F3F4F6;'
                    f'border-left:1.5px solid #E2E8F0;letter-spacing:0.02em;'
                    f'min-width:48px;max-width:72px;overflow:hidden;'
                    f'text-overflow:ellipsis;white-space:nowrap;'
                    f'background:{col_bg};">'
                    f'{logo_html}{ticker}</td>'
                    f'<td style="text-align:center;font-size:{pct_size};'
                    f'color:{pct_col};font-weight:700;'
                    f'padding:5px 8px;border-bottom:1px solid #F3F4F6;'
                    f'font-variant-numeric:tabular-nums;line-height:1.15;'
                    f'background:{heat_bg};">{pct_text}</td>'
                )
            else:
                row += (
                    f'<td style="border-left:1.5px solid #E2E8F0;padding:5px 8px;'
                    f'background:{col_bg};border-bottom:1px solid #F3F4F6;'
                    f'color:#CBD5E1;font-size:11px;">\u2014</td>'
                    f'<td style="padding:5px 8px;background:{col_bg};'
                    f'border-bottom:1px solid #F3F4F6;color:#CBD5E1;font-size:11px;">\u2014</td>'
                )
        row += "</tr>"
        return row

    winners_sorted = {
        p: period_returns.get(p, pd.Series(dtype=float)).sort_values(ascending=False)
        for p in periods
    }
    losers_sorted = {
        p: period_returns.get(p, pd.Series(dtype=float)).sort_values(ascending=True)
        for p in periods
    }

    tbody = "<tbody>"

    tbody += (
        f'<tr><td colspan="{n_cols}" style="'
        f'padding:0;background:white;border-top:none;">'
        f'<div style="display:flex;align-items:center;gap:8px;'
        f'padding:10px 12px 6px 12px;'
        f'border-left:3px solid #16A34A;'
        f'background:linear-gradient(90deg,rgba(22,163,74,0.05),transparent 40%);">'
        f'<span style="font-size:14px;font-weight:800;color:#16A34A;'
        f'text-transform:uppercase;letter-spacing:0.05em;">'
        f'Top 10 Winners</span>'
        f'</div></td></tr>'
    )
    for rank in range(1, n + 1):
        tbody += _data_row(rank, winners_sorted, "winners")

    tbody += (
        f'<tr><td colspan="{n_cols}" style="'
        f'padding:0;background:white;border-top:2px solid #E2E8F0;">'
        f'<div style="display:flex;align-items:center;gap:8px;'
        f'padding:10px 12px 6px 12px;'
        f'border-left:3px solid #DC2626;'
        f'background:linear-gradient(90deg,rgba(220,38,38,0.05),transparent 40%);">'
        f'<span style="font-size:14px;font-weight:800;color:#DC2626;'
        f'text-transform:uppercase;letter-spacing:0.05em;">'
        f'Top 10 Losers</span>'
        f'</div></td></tr>'
    )
    for rank in range(1, n + 1):
        tbody += _data_row(rank, losers_sorted, "losers")

    tbody += "</tbody>"

    hover_css = (
        '<style>'
        '.movers-table tbody tr:hover td {'
        '  background-color: rgba(59,130,246,0.04) !important;'
        '}'
        '</style>'
    )

    return (
        f'{hover_css}'
        f'<div style="overflow-x:auto;'
        f'border-radius:12px;border:1px solid #E5E7EB;'
        f'box-shadow:0 1px 3px rgba(0,0,0,0.04);position:relative;">'
        f'<table class="movers-table" style="width:100%;'
        f'border-collapse:separate;border-spacing:0;'
        f"min-width:1100px;font-family:'DM Sans',sans-serif;\">"
        f'{colgroup}{thead}{tbody}'
        f'</table></div>'
    )


def _render_benchmark_chart(index_prices, close_df, as_of, data):
    """Plotly line chart: individual segment lines + S&P/NASDAQ references, rebased to 100."""
    as_of = pd.Timestamp(as_of)
    start_12m = as_of - pd.DateOffset(months=12)

    # Build a ticker -> segment mapping from data
    ticker_segment = {}
    for d in data:
        t = d.get("ticker")
        s = d.get("segment")
        if t and s:
            ticker_segment[t] = s

    series_map = {}

    # Build per-segment equal-weighted price indices
    if not close_df.empty:
        hc_daily = close_df[(close_df.index >= start_12m) & (close_df.index <= as_of)]
        if not hc_daily.empty:
            for seg_key, seg_name in SEGMENT_DISPLAY.items():
                seg_tickers = [t for t, s in ticker_segment.items()
                               if s == seg_key and t in hc_daily.columns]
                if not seg_tickers:
                    continue
                seg_prices = hc_daily[seg_tickers]
                first_valid = seg_prices.bfill().iloc[0]
                first_valid = first_valid.replace(0, np.nan)
                normed = seg_prices.div(first_valid) * 100
                seg_avg = normed.mean(axis=1).dropna()
                if not seg_avg.empty:
                    short_name = SEGMENT_SHORT.get(seg_key, seg_name)
                    series_map[short_name] = (seg_avg, SEGMENT_COLORS.get(seg_key, "#6B7280"), seg_key)

    # S&P 500, NASDAQ as references
    ref_series = {}
    for name, display in [("S&P 500", "S&P 500"), ("NASDAQ", "NASDAQ")]:
        s = index_prices.get(name)
        if s is not None and not s.empty:
            s = s[(s.index >= start_12m) & (s.index <= as_of)]
            if not s.empty:
                base = s.iloc[0]
                if base and base != 0:
                    ref_series[display] = (s / base) * 100

    if not series_map and not ref_series:
        return None, list(SEGMENT_DISPLAY.keys())

    return (series_map, ref_series, start_12m, as_of), list(series_map.keys())


def _build_segment_chart(chart_data, visible_segments):
    """Build and return the Plotly figure given pre-computed data and visibility."""
    series_map, ref_series, start_12m, as_of = chart_data

    fig = go.Figure()

    # Add reference lines first (faint)
    ref_colors = {"S&P 500": "#9CA3AF", "NASDAQ": "#B0B7C3"}
    for name, s in ref_series.items():
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values,
            name=name,
            mode="lines",
            line=dict(color=ref_colors.get(name, "#94A3B8"), width=1.5, dash="dot"),
            opacity=0.4,
            hovertemplate=f"<b>{name}</b>: %{{y:.1f}}<extra></extra>",
        ))

    # Add segment lines
    for seg_name, (seg_series, seg_color, seg_key) in series_map.items():
        visible = seg_name in visible_segments
        fig.add_trace(go.Scatter(
            x=seg_series.index, y=seg_series.values,
            name=seg_name,
            mode="lines",
            line=dict(color=seg_color, width=2.5),
            opacity=1.0,
            visible=True if visible else "legendonly",
            hovertemplate=f"<b>{seg_name}</b>: %{{y:.1f}}<extra></extra>",
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="#94A3B8", line_width=1, opacity=0.5)

    fig.add_annotation(
        x=0, xref="paper", xanchor="right",
        y=100, text="100", showarrow=False, xshift=-6,
        font=dict(size=10, color="#94A3B8", family="DM Sans"),
    )

    # End-of-line labels for visible segment lines
    visible_items = []
    for seg_name, (seg_series, seg_color, _) in series_map.items():
        if seg_name in visible_segments and not seg_series.empty:
            visible_items.append((seg_name, float(seg_series.iloc[-1]), seg_color))
    for name, s in ref_series.items():
        if not s.empty:
            visible_items.append((name, float(s.iloc[-1]), ref_colors.get(name, "#94A3B8")))

    label_items = sorted(visible_items, key=lambda x: x[1])
    min_gap = 8
    adjusted_y = [item[1] for item in label_items]
    for i in range(1, len(adjusted_y)):
        if adjusted_y[i] - adjusted_y[i - 1] < min_gap:
            adjusted_y[i] = adjusted_y[i - 1] + min_gap

    for (name, last_val, color), adj_y in zip(label_items, adjusted_y):
        fig.add_annotation(
            x=1.0, xref="paper", xanchor="left",
            y=adj_y,
            text=f"<b>{name}  {last_val:.0f}</b>",
            showarrow=False,
            xshift=10,
            font=dict(size=11, color="white", family="DM Sans"),
            bgcolor=color,
            borderpad=6,
            bordercolor=color,
            borderwidth=1,
            opacity=1.0,
        )

    fig.update_layout(
        height=400,
        margin=dict(l=40, r=180, t=10, b=40),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="DM Sans, sans-serif"),
        showlegend=False,
        xaxis=dict(
            showgrid=False,
            tickformat="%b '%y",
            tickfont=dict(size=10, color="#9CA3AF"),
            linecolor="#E5E7EB",
            range=[start_12m, as_of],
            constrain="domain",
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F3F4F6",
            tickfont=dict(size=10, color="#9CA3AF"),
            linecolor="#E5E7EB",
            title=None,
            ticksuffix="  ",
        ),
        hovermode="x",
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E5E7EB",
            font=dict(size=12, family="DM Sans"),
        ),
    )

    return fig


def render_multi_period_view(data):
    """Render the full multi-period Share Price Performance view."""
    tickers = sorted({d.get("ticker") for d in data if d.get("ticker")})
    if not tickers:
        st.warning("No company data available.")
        return

    raw_dates = [d.get("snapshot_date") for d in data if d.get("snapshot_date")]
    as_of = (max(pd.Timestamp(str(d)[:10]) for d in raw_dates)
             if raw_dates else pd.Timestamp.today().normalize())

    with st.spinner("Loading price history from Yahoo Finance\u2026"):
        close_df     = _mp_fetch_prices(tuple(tickers))
        index_prices, bvp_label = _mp_fetch_index_prices()

    periods = _MP_PERIOD_NAMES

    period_returns = _mp_compute_returns(close_df, as_of, periods)
    period_avail   = _mp_availability(close_df, as_of, periods)
    index_returns  = _mp_compute_index_returns(index_prices, as_of, periods)

    sw_returns = {}
    for p in periods:
        s = period_returns.get(p, pd.Series(dtype=float)).dropna()
        sw_returns[p] = float(s.mean()) if not s.empty else None

    # ── Benchmark chart with segment lines ────────────────────────────────────
    chart_result, all_seg_names = _render_benchmark_chart(index_prices, close_df, as_of, data)

    if chart_result:
        st.markdown(
            '<div style="font-size:16px;font-weight:700;color:#111827;'
            'margin-bottom:2px;margin-top:8px;">Share Price Performance</div>'
            '<div style="font-size:12px;color:#9CA3AF;margin-bottom:8px;">'
            'Rebased to 100 at 12 months ago</div>',
            unsafe_allow_html=True,
        )

        # Segment visibility checkboxes
        cols = st.columns(len(all_seg_names))
        visible_segments = []
        for i, seg_name in enumerate(all_seg_names):
            with cols[i]:
                checked = st.checkbox(seg_name, value=True, key=f"seg_vis_{seg_name}")
                if checked:
                    visible_segments.append(seg_name)

        chart_fig = _build_segment_chart(chart_result, visible_segments)
        st.plotly_chart(chart_fig, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False})

    # ── Single combined table ─────────────────────────────────────────────────
    st.markdown(
        _render_combined_html(period_returns, period_avail, n=10),
        unsafe_allow_html=True,
    )

    # ── Footnote ──────────────────────────────────────────────────────────────
    unavail = [p for p, a in period_avail.items() if not a]
    unavail_note = (
        f" \u00b7 Grayed periods ({', '.join(unavail)}) need more price history"
        if unavail else ""
    )
    st.markdown(
        f'<div style="font-size:9px;color:#B0B7C3;margin-top:10px;padding-left:4px;">'
        f'<span style="color:#64748B;font-weight:500;">Source:</span> Yahoo Finance (share prices) \u00b7 FactSet (fundamentals) \u00b7 As of {as_of.strftime("%b %d, %Y")} \u00b7 '
        f'Segment lines = equal-weighted price index per segment'
        f'{unavail_note}</div>',
        unsafe_allow_html=True,
    )




# ── Stat card renderer (standalone) ──────────────────────────────────────────

def _render_stat_cards(data, change_col):
    """Render the 6 stat-card row -- all performance-focused, with color-coded percentages."""
    valid = [d for d in data if d.get(change_col) is not None]
    if not valid:
        return

    period_label = "2-Week" if "2w" in change_col else "2-Month"

    all_changes  = [d[change_col] * 100 for d in valid]
    total_valid  = len(valid)
    up_count     = sum(1 for c in all_changes if c >= 0)
    down_count   = total_valid - up_count
    median_chg   = np.median(all_changes)
    max_gain     = max(all_changes)
    max_loss     = min(all_changes)
    pct_adv      = up_count / total_valid * 100 if total_valid else 0

    winners_raw  = sorted(valid, key=lambda x: x[change_col], reverse=True)
    losers_raw   = sorted(valid, key=lambda x: x[change_col])
    best_d       = winners_raw[0] if winners_raw else {}
    worst_d      = losers_raw[0] if losers_raw else {}
    best_ticker  = best_d.get("ticker", "?")
    best_name    = best_d.get("name", best_ticker)
    worst_ticker = worst_d.get("ticker", "?")
    worst_name   = worst_d.get("name", worst_ticker)

    sentiment_label = "Bullish" if median_chg >= 0 else "Bearish"

    # Radial gauge for Adv / Dec
    r = 44
    circ = 2 * 3.14159 * r
    green_arc = circ * pct_adv / 100
    red_arc = circ * (100 - pct_adv) / 100
    advdec_gauge = (
        f'<div style="display:flex;align-items:center;gap:18px;margin-top:2px;">'
        f'<svg width="110" height="110" viewBox="0 0 110 110">'
        f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="{RED}" stroke-width="10" opacity="0.25"/>'
        f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="{GREEN}" stroke-width="10"'
        f' stroke-dasharray="{green_arc:.1f} {red_arc:.1f}"'
        f' stroke-dashoffset="0" stroke-linecap="round"'
        f' transform="rotate(-90 55 55)"/>'
        f'<text x="55" y="50" text-anchor="middle" font-size="28" font-weight="800"'
        f' fill="#111827" font-family="DM Sans,sans-serif">{pct_adv:.0f}%</text>'
        f'<text x="55" y="68" text-anchor="middle" font-size="11" font-weight="600"'
        f' fill="#6B7280" font-family="DM Sans,sans-serif">advancing</text>'
        f'</svg>'
        f'<div style="font-size:16px;line-height:2.2;color:#111827;font-weight:600;">'
        f'<span style="color:{GREEN};font-weight:800;font-size:18px;">{up_count}</span> up<br>'
        f'<span style="color:{RED};font-weight:800;font-size:18px;">{down_count}</span> down'
        f'</div>'
        f'</div>'
    )

    pill_color = GREEN if median_chg >= 0 else RED
    pill_bg    = PILL_BG_POS if median_chg >= 0 else PILL_BG_NEG
    sentiment_pill = (
        f'<span style="display:inline-block;padding:4px 12px;border-radius:10px;'
        f'background:{pill_bg};color:{pill_color};font-size:14px;font-weight:700;">'
        f'{sentiment_label}</span>'
    )

    # Color-coded median change
    median_color = "#059669" if median_chg >= 0 else "#DC2626"
    median_fmt = (
        f'<span style="color:{median_color};font-size:34px;font-weight:800;">'
        + (f"+{median_chg:.1f}%" if median_chg >= 0 else f"-{abs(median_chg):.1f}%")
        + '</span>'
    )

    # Best performer card content
    best_logo = logo_img_tag(best_ticker, size=20)
    best_logo_html = f'{best_logo}&nbsp;' if best_logo else ''
    best_pct = max_gain
    best_short = (best_name[:24] + "...") if len(best_name) > 27 else best_name
    best_val_html = (
        f'<div style="display:flex;align-items:center;gap:8px;justify-content:start;">'
        f'{best_logo_html}'
        f'<span style="font-size:28px;font-weight:800;color:#059669;">'
        f'+{best_pct:.1f}%</span>'
        f'</div>'
        f'<div style="font-size:14px;font-weight:700;color:#111827;margin-top:4px;">'
        f'{_html_lib.escape(best_short)}</div>'
        f'<div style="font-size:11px;color:#6B7280;margin-top:1px;">{best_ticker}</div>'
    )

    # Worst performer card content
    worst_logo = logo_img_tag(worst_ticker, size=20)
    worst_logo_html = f'{worst_logo}&nbsp;' if worst_logo else ''
    worst_pct = abs(max_loss)
    worst_short = (worst_name[:24] + "...") if len(worst_name) > 27 else worst_name
    worst_val_html = (
        f'<div style="display:flex;align-items:center;gap:8px;justify-content:start;">'
        f'{worst_logo_html}'
        f'<span style="font-size:28px;font-weight:800;color:#DC2626;">'
        f'-{worst_pct:.1f}%</span>'
        f'</div>'
        f'<div style="font-size:14px;font-weight:700;color:#111827;margin-top:4px;">'
        f'{_html_lib.escape(worst_short)}</div>'
        f'<div style="font-size:11px;color:#6B7280;margin-top:1px;">{worst_ticker}</div>'
    )

    adv_top_color    = GREEN if pct_adv >= 50 else RED
    median_top_color = GREEN if median_chg >= 0 else RED

    # Universe card
    from config.company_registry import COMPANY_REGISTRY
    all_names = sorted([c["name"] for c in COMPANY_REGISTRY])
    names_list_html = "".join(
        f'<div style="padding:3px 0;font-size:12px;color:#374151;'
        f'border-bottom:1px solid #F3F4F6;">{_html_lib.escape(n)}</div>'
        for n in all_names
    )
    universe_popup = (
        f'<details style="margin-top:6px;">'
        f'<summary style="font-size:11px;color:#3B82F6;cursor:pointer;font-weight:500;">'
        f'View all companies</summary>'
        f'<div style="max-height:300px;overflow-y:auto;margin-top:6px;'
        f'padding:8px;background:#F9FAFB;border-radius:6px;border:1px solid #E5E7EB;">'
        f'{names_list_html}</div></details>'
    )

    cards_html = '<div class="stat-grid">'
    cards_html += _stat_card("Universe", str(total_valid),
                              sub="companies tracked",
                              extra_html=universe_popup,
                              top_color="#4A90D9")
    cards_html += _stat_card(
        f"{period_label} Advancing / Declining", "",
        extra_html=advdec_gauge,
        top_color=adv_top_color,
    )
    cards_html += _stat_card(
        f"Median {period_label} Change", median_fmt,
        sub=sentiment_pill,
        top_color=median_top_color,
    )
    cards_html += _stat_card(
        f"Best {period_label} Performer", "",
        extra_html=best_val_html,
        top_color=GREEN,
    )
    cards_html += _stat_card(
        f"Worst {period_label} Performer", "",
        extra_html=worst_val_html,
        top_color=RED,
    )
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)


# ── Distribution chart ───────────────────────────────────────────────────────

def _render_distribution_chart(data, change_col):
    """Stacked bar chart showing distribution of stock performance in buckets."""
    valid = [d for d in data if d.get(change_col) is not None]
    if not valid:
        return

    changes = [d[change_col] * 100 for d in valid]

    # Define buckets
    bucket_labels = ["Down >10%", "-10% to -5%", "-5% to 0%", "0% to +5%", "+5% to +10%", "Up >10%"]
    bucket_colors = ["#DC2626", "#EF4444", "#FCA5A5", "#86EFAC", "#22C55E", "#059669"]

    counts = [0] * 6
    for c in changes:
        if c < -10:
            counts[0] += 1
        elif c < -5:
            counts[1] += 1
        elif c < 0:
            counts[2] += 1
        elif c < 5:
            counts[3] += 1
        elif c < 10:
            counts[4] += 1
        else:
            counts[5] += 1

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=bucket_labels,
        y=counts,
        marker_color=bucket_colors,
        text=[str(c) for c in counts],
        textposition="outside",
        textfont=dict(size=12, color="#374151", family="DM Sans"),
        hovertemplate="<b>%{x}</b><br>%{y} companies<extra></extra>",
    ))

    period_label = "2-Week" if "2w" in change_col else "2-Month"
    fig.update_layout(
        title=dict(
            text=f"{period_label} Price Change Distribution",
            font=dict(size=14, color="#374151", family="DM Sans"),
        ),
        height=280,
        margin=dict(l=40, r=20, t=50, b=40),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="DM Sans, sans-serif", color="#64748B", size=11),
        xaxis=dict(
            showgrid=False,
            linecolor="#E5E7EB",
            tickfont=dict(size=11, color="#6B7280"),
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#F3F4F6",
            linecolor="#E5E7EB",
            tickfont=dict(size=10, color="#9CA3AF"),
            title="Number of Companies",
            titlefont=dict(size=11, color="#9CA3AF"),
        ),
        bargap=0.15,
    )

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "scrollZoom": False})


# ── Combined Winners & Losers table (new single-table design) ────────────────

_COMBINED_CSS = """
<style>
.comb-outer {
    background: white;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.comb-tbl {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    font-variant-numeric: tabular-nums;
    font-family: 'DM Sans', sans-serif;
}
.comb-tbl thead th {
    font-size: 11px;
    font-weight: 700;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 10px 12px;
    border-bottom: 2px solid #E5E7EB;
    background: #F9FAFB;
    white-space: nowrap;
}
.comb-tbl tbody td {
    padding: 8px 12px;
    font-size: 14px;
    border-bottom: 1px solid #F3F4F6;
    color: #374151;
    line-height: 1.4;
    white-space: nowrap;
    vertical-align: middle;
}
.comb-tbl tbody tr:nth-child(odd) td  { background: #FFFFFF; }
.comb-tbl tbody tr:nth-child(even) td { background: #FAFBFD; }
.comb-tbl tbody tr:hover td           { background: #F0F4FF !important; }
</style>
"""


def _build_combined_wl_table(data, change_col, n=25):
    """Build a single combined table of top N winners + top N losers.

    Columns: Rank, Logo+Ticker, Company Name, Segment (pill), % Change (colored).
    """
    valid = [d for d in data if d.get(change_col) is not None]
    if not valid:
        return ""

    sorted_all = sorted(valid, key=lambda x: x[change_col], reverse=True)
    winners = sorted_all[:n]
    losers = sorted_all[-n:] if len(sorted_all) > n else []
    # Reverse losers so worst is first
    losers = list(reversed(losers))

    # Build header
    header = (
        '<tr>'
        '<th style="text-align:center;width:40px;">#</th>'
        '<th style="text-align:left;width:100px;">Ticker</th>'
        '<th style="text-align:left;">Company</th>'
        '<th style="text-align:left;width:140px;">Segment</th>'
        '<th style="text-align:right;width:100px;">% Change</th>'
        '</tr>'
    )

    def _make_row(rank, d, direction):
        ticker = _html_lib.escape(str(d.get("ticker") or "?"))
        logo = logo_img_tag(ticker, size=16)
        logo_html = f'{logo}&nbsp;' if logo else ''

        name = str(d.get("name") or "\u2013")
        short_name = (name[:28] + "\u2026") if len(name) > 29 else name

        seg_key = d.get("segment", "")
        seg_name = SEGMENT_SHORT.get(seg_key, seg_key)
        pill_style = _WL_CAT_PILLS.get(seg_name, _WL_CAT_DEFAULT)

        chg_val = d.get(change_col)
        try:
            pct = float(chg_val) * 100
        except (TypeError, ValueError):
            pct = 0.0

        if pct >= 0:
            chg_color = "#059669"
            chg_text = f"+{pct:.1f}%"
        else:
            chg_color = "#DC2626"
            chg_text = f"-{abs(pct):.1f}%"

        rank_col = "#111827" if rank <= 3 else "#64748B"
        rank_fw = "700" if rank <= 3 else "500"

        return (
            f'<tr>'
            f'<td style="text-align:center;color:{rank_col};font-weight:{rank_fw};font-size:13px;">{rank}</td>'
            f'<td style="text-align:left;">{logo_html}<span style="color:#3B82F6;font-weight:600;font-size:13px;">{ticker}</span></td>'
            f'<td style="text-align:left;color:#374151;">{_html_lib.escape(short_name)}</td>'
            f'<td style="text-align:left;"><span style="{pill_style}">{_html_lib.escape(seg_name)}</span></td>'
            f'<td style="text-align:right;font-weight:700;font-size:14px;color:{chg_color};">{chg_text}</td>'
            f'</tr>'
        )

    period_label = "2-Week" if "2w" in change_col else "2-Month"

    tbody = "<tbody>"

    # Winners section header
    tbody += (
        f'<tr><td colspan="5" style="padding:0;background:white;border-top:none;">'
        f'<div style="display:flex;align-items:center;gap:8px;'
        f'padding:10px 12px 6px 12px;'
        f'border-left:3px solid #059669;'
        f'background:linear-gradient(90deg,rgba(5,150,105,0.05),transparent 40%);">'
        f'<span style="font-size:14px;font-weight:800;color:#059669;'
        f'text-transform:uppercase;letter-spacing:0.05em;">'
        f'Top {n} Winners</span>'
        f'<span style="font-size:12px;color:#94A3B8;font-weight:400;">{period_label}</span>'
        f'</div></td></tr>'
    )
    for i, d in enumerate(winners, 1):
        tbody += _make_row(i, d, "winners")

    # Losers section header
    if losers:
        tbody += (
            f'<tr><td colspan="5" style="padding:0;background:white;border-top:2px solid #E2E8F0;">'
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'padding:10px 12px 6px 12px;'
            f'border-left:3px solid #DC2626;'
            f'background:linear-gradient(90deg,rgba(220,38,38,0.05),transparent 40%);">'
            f'<span style="font-size:14px;font-weight:800;color:#DC2626;'
            f'text-transform:uppercase;letter-spacing:0.05em;">'
            f'Top {n} Losers</span>'
            f'<span style="font-size:12px;color:#94A3B8;font-weight:400;">{period_label}</span>'
            f'</div></td></tr>'
        )
        for i, d in enumerate(losers, 1):
            tbody += _make_row(i, d, "losers")

    tbody += "</tbody>"

    return (
        f'<div class="comb-outer">'
        f'<table class="comb-tbl">'
        f'<thead>{header}</thead>'
        f'{tbody}'
        f'</table>'
        f'</div>'
    )


# ── Unified page rendering ────────────────────────────────────────────────────

# Page header -- block style
st.markdown(
    f'<div style="background:#F0F4FF;'
    f'border-radius:12px;padding:24px 32px;margin-bottom:24px;'
    f'border:1px solid #DBEAFE;border-left:4px solid #3B82F6;">'
    f'<div style="font-size:30px;font-weight:800;color:#111827;margin-bottom:4px;">'
    f'Winners &amp; Losers</div>'
    f'<div style="font-size:14px;color:#6B7280;font-weight:500;">'
    f'Biggest movers across the healthcare universe{_date_suffix}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

# Stat cards -- use 2-week data as the default context
_render_stat_cards(all_data, "price_change_2w")

# ── Distribution chart (after stat cards) ─────────────────────────────────────
_render_distribution_chart(all_data, "price_change_2w")

# ── Section 2: Share Price Performance (hero table) ───────────────────────────
st.markdown(
    '<div style="font-size:18px;font-weight:700;color:#111827;'
    'margin-top:24px;margin-bottom:12px;">Share Price Performance</div>',
    unsafe_allow_html=True,
)
render_multi_period_view(all_data)

# ── Section 3: Top Winners and Losers ─────────────────────────────────────────
st.markdown(
    '<div style="height:32px;"></div>'
    '<div style="font-size:18px;font-weight:700;color:#111827;margin-bottom:4px;">'
    'Top Winners and Losers</div>'
    '<div style="font-size:14px;color:#94A3B8;margin-bottom:12px;">'
    'Top 25 winners and losers by selected period</div>',
    unsafe_allow_html=True,
)

st.markdown(_COMBINED_CSS, unsafe_allow_html=True)

# Radio buttons for period selection
_PERIOD_OPTIONS = ["1W", "1M", "3M", "6M", "12M", "YTD"]
_PERIOD_TO_MP = {
    "1W":  "Last Week",
    "1M":  "Last Month",
    "3M":  "Last 3M",
    "6M":  "Last 6M",
    "12M": "Last 12M",
    "YTD": "YTD",
}

selected_period = st.radio(
    "Time Period",
    _PERIOD_OPTIONS,
    horizontal=True,
    index=0,
    key="wl_period_radio",
)

# Use yfinance to compute returns for the selected period
_wl_tickers = sorted({d.get("ticker") for d in all_data if d.get("ticker")})
_wl_raw_dates = [d.get("snapshot_date") for d in all_data if d.get("snapshot_date")]
_wl_as_of = (max(pd.Timestamp(str(d)[:10]) for d in _wl_raw_dates)
             if _wl_raw_dates else pd.Timestamp.today().normalize())

with st.spinner("Computing returns..."):
    _wl_close_df = _mp_fetch_prices(tuple(_wl_tickers))
    _wl_mp_name = _PERIOD_TO_MP.get(selected_period, "Last Week")
    _wl_returns = _mp_compute_returns(_wl_close_df, _wl_as_of, [_wl_mp_name])
    _wl_ret_series = _wl_returns.get(_wl_mp_name, pd.Series(dtype=float))

# Inject computed returns into data dicts (as decimal, e.g. 0.05 for 5%)
_change_col_name = f"_yf_{selected_period}"
_enriched_data = []
for d in all_data:
    d2 = dict(d)
    ticker = d2.get("ticker")
    if ticker and ticker in _wl_ret_series.index:
        d2[_change_col_name] = float(_wl_ret_series[ticker]) / 100.0  # convert % to decimal
    else:
        d2[_change_col_name] = None
    _enriched_data.append(d2)

_has_data = any(d.get(_change_col_name) is not None for d in _enriched_data)

if _has_data:
    st.markdown(
        _build_combined_wl_table(_enriched_data, _change_col_name, n=25),
        unsafe_allow_html=True,
    )
else:
    st.info(f"No data available for {selected_period} period. Try a different time period.")

_as_of_str = latest_date_str if latest_date_str else "\u2014"
st.markdown(
    f'<div style="font-size:11px;color:#94A3B8;margin-top:12px;padding-left:4px;">'
    f'<span style="color:#64748B;font-weight:500;">Source:</span> '
    f'FactSet (fundamentals &amp; estimates) \u00b7 Yahoo Finance (share prices)  \u00b7  '
    f'Data as of {_as_of_str}'
    f'</div>',
    unsafe_allow_html=True,
)
