"""
Valuation Regression
Two-tab page:
  Tab 1 — Valuation vs. Performance  (scatter with OLS regression trendline)
  Tab 2 — Valuation Trends  (NTM TEV/Rev or TEV/EBITDA time series, all companies)
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
from pathlib import Path
import plotly.graph_objects as go

try:
    from scipy import stats as _sp_stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from config.settings import DB_PATH, EXCEL_OVERRIDE_PATH
from fetcher.db_manager import DBManager
from fetcher.excel_override import load_overrides, apply_overrides

# ── Sidebar ───────────────────────────────────────────────────────────────────
render_sidebar()

# ── Data loading ──────────────────────────────────────────────────────────────
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

try:
    daily_mult = db.get_daily_multiples(days_back=9999)
except Exception:
    daily_mult = []

# ── Constants ─────────────────────────────────────────────────────────────────
IS_LIGHT    = True

from config.color_palette import (
    SEGMENT_SHORT, SEG_COLOR_MAP, PLOTLY_BG, PLOTLY_GRID, PLOTLY_TEXT,
)

# ── Band filter maps (TEV in raw $, growth in %) ────────────────────────────
TEV_BANDS = {
    "< $1B":  (0, 1e9),
    "$1-3B":  (1e9, 3e9),
    "$3-5B":  (3e9, 5e9),
    "$5-10B": (5e9, 10e9),
    "> $10B": (10e9, None),
}
GROWTH_BANDS = {
    "< 10%":  (None, 10),
    "10-20%": (10, 20),
    "20-30%": (20, 30),
    "30-40%": (30, 40),
    "> 40%":  (40, None),
}

def _in_any_band(value, selected_labels, band_map):
    """Return True if value falls within any of the selected bands."""
    if pd.isna(value):
        return False
    for label in selected_labels:
        lo, hi = band_map[label]
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return True
    return False

# ── Page styles ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
.stApp { background: #FAFBFC !important; }
.main .block-container {
    background: #FAFBFC !important;
    max-width: 100% !important;
    padding: 1.5rem 2rem !important;
}
h1, h2, h3, h4 { color: #111827 !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none !important; }
hr { border-color: #E5E7EB !important; margin: 1.2rem 0 !important; }

/* ── Control labels — small, muted, uppercase ── */
div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label,
div[data-testid="stCheckbox"] label,
div[data-testid="stRadio"] label {
    font-size: 9px !important;
    font-weight: 600 !important;
    color: #94A3B8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 2px !important;
}
/* ── Selectbox / multiselect — white box with gray border ── */
div[data-testid="stSelectbox"] > div > div {
    font-size: 12px !important;
}
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stMultiSelect"] > div > div {
    background: white !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
}
/* ── Multiselect tag pills — muted gray instead of Streamlit blue ── */
span[data-baseweb="tag"] {
    background: #F1F5F9 !important;
    border-radius: 4px !important;
}
span[data-baseweb="tag"] span {
    color: #475569 !important;
    font-size: 11px !important;
}
</style>
""", unsafe_allow_html=True)

# FIX 13 — clean page title
st.markdown(
    '<div style="font-size:22px;font-weight:700;color:#111827;margin-bottom:2px;">'
    "Valuation Regression</div>"
    '<div style="font-size:12px;color:#94A3B8;margin-bottom:16px;">'
    "EV multiple trends and valuation vs. performance scatter across the healthcare universe</div>",
    unsafe_allow_html=True,
)

# ── Plotly layout helper ───────────────────────────────────────────────────────
def _plotly_layout(title="", height=320):
    """Return a Plotly layout dict with DM Sans font, light-mode colors."""
    _axis_defaults = dict(
        gridcolor=PLOTLY_GRID, gridwidth=0.5,
        showgrid=True, zeroline=False,
        showline=True, linecolor="#D1D5DB", linewidth=1,
        tickfont=dict(size=11, color="#6B7280", family="DM Sans"),
    )
    return dict(
        title=dict(text=title, font=dict(size=13, color=PLOTLY_TEXT)),
        plot_bgcolor=PLOTLY_BG,
        paper_bgcolor=PLOTLY_BG,
        font=dict(family="DM Sans, sans-serif", color=PLOTLY_TEXT, size=11),
        xaxis=dict(**_axis_defaults),
        yaxis=dict(**_axis_defaults),
        margin=dict(l=60, r=40, t=55, b=60),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=10, color="#111827")),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E5E7EB",
            font=dict(size=11, color="#374151", family="DM Sans, sans-serif"),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — VALUATION TRENDS
# ─────────────────────────────────────────────────────────────────────────────

def _render_valuation_tab(daily_mult, all_data, tab_key):
    """NTM TEV/Revenue or TEV/EBITDA time series.
    Median + TEV-weighted avg (Universe view) or per-segment median lines
    (By Segment view), with P25-P75 shaded band and IQR outlier trimming.
    Uses ALL companies from daily_multiples — not filtered to top movers.
    """
    if not daily_mult:
        st.caption("No daily multiples history available.")
        return

    df_raw = pd.DataFrame(daily_mult)
    if df_raw.empty:
        st.caption("No daily multiples history available.")
        return

    # ── Filter controls ──────────────────────────────────────────────────────
    vl_left, _ = st.columns([4, 6])
    with vl_left:
        view_mode = st.radio(
            "VIEW",
            options=["Universe (Median + Wtd Avg)", "By Segment"],
            horizontal=True,
            index=1,
            key=f"vt_view_{tab_key}",
        )

    # ── Metric / Period row ─────────────────────────────────────────────────
    _fc1, _fc2, _fc3, _fc4, _fc5 = st.columns([2, 2, 2, 2, 2])
    with _fc1:
        metric = st.selectbox(
            "METRIC",
            options=["NTM TEV/Revenue", "NTM TEV/EBITDA"],
            index=0,
            key=f"vt_metric_{tab_key}",
        )
    with _fc2:
        period = st.selectbox(
            "PERIOD",
            options=["1Y", "2Y", "3Y", "All"],
            index=0,
            key=f"vt_period_{tab_key}",
        )
    with _fc3:
        _gr_all = list(GROWTH_BANDS.keys())
        vt_growth_sel = st.multiselect(
            "GROWTH", _gr_all, default=_gr_all,
            key=f"vt_gr_{tab_key}",
        )
    with _fc4:
        _tv_all = list(TEV_BANDS.keys())
        vt_tev_sel = st.multiselect(
            "TEV", _tv_all, default=_tv_all,
            key=f"vt_tev_{tab_key}",
        )

    # ── Sector checkboxes ────────────────────────────────────────────────────
    all_seg_labels = list(SEGMENT_SHORT.values())
    st.markdown(
        '<div style="font-size:9px;font-weight:600;color:#94A3B8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px;">'
        'SECTORS</div>',
        unsafe_allow_html=True,
    )
    _seg_cols = st.columns(len(all_seg_labels))
    sel_segs = []
    for i, seg_label in enumerate(all_seg_labels):
        with _seg_cols[i]:
            if st.checkbox(seg_label, value=True, key=f"vt_seg_{tab_key}_{i}"):
                sel_segs.append(seg_label)

    # ── Column mapping ───────────────────────────────────────────────────────
    _METRIC_COL = {
        "NTM TEV/Revenue": "ntm_tev_rev",
        "NTM TEV/EBITDA":  "ntm_tev_ebitda",
    }
    metric_col   = _METRIC_COL[metric]
    metric_short = "TEV/Rev" if metric == "NTM TEV/Revenue" else "TEV/EBITDA"

    # ── Parse dates ──────────────────────────────────────────────────────────
    df = df_raw.copy()
    df["_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["_dt"])

    # ── Period filter ────────────────────────────────────────────────────────
    _PERIOD_DAYS = {"1Y": 365, "2Y": 730, "3Y": 1095, "All": 99999}
    days_back_p = _PERIOD_DAYS[period]
    if days_back_p < 99999:
        cutoff = pd.Timestamp.today() - pd.Timedelta(days=days_back_p)
        df = df[df["_dt"] >= cutoff]

    # ── Sector filter ────────────────────────────────────────────────────────
    seg_rev = {v: k for k, v in SEGMENT_SHORT.items()}
    sel_segs_raw = [seg_rev[s] for s in sel_segs if s in seg_rev]
    if sel_segs_raw:
        df = df[df["segment"].isin(sel_segs_raw)]

    # ── TEV filter (band-based) ───────────────────────────────────────────────
    if len(vt_tev_sel) < len(TEV_BANDS) and "enterprise_value" in df.columns:
        df = df[df["enterprise_value"].apply(
            lambda v: _in_any_band(v, vt_tev_sel, TEV_BANDS)
        )]

    # ── NTM Growth filter (current snapshot as universe proxy, band-based) ──
    if len(vt_growth_sel) < len(GROWTH_BANDS) and all_data and "ticker" in df.columns:
        passing = {
            d["ticker"]
            for d in all_data
            if d.get("ntm_revenue_growth") is not None
            and _in_any_band(d["ntm_revenue_growth"] * 100, vt_growth_sel, GROWTH_BANDS)
        }
        df = df[df["ticker"].isin(passing)]

    df = df.dropna(subset=[metric_col])
    # Exclude non-positive or DB sentinel (≥ 100x) multiples
    df = df[(df[metric_col] > 0) & (df[metric_col] < 100)].copy()

    # ── Normalize to weekly buckets ───────────────────────────────────────────
    df["_week"] = df["_dt"].dt.to_period("W").dt.start_time
    _agg_d = {metric_col: "mean"}
    if "enterprise_value" in df.columns:
        _agg_d["enterprise_value"] = "mean"
    if "segment" in df.columns:
        _agg_d["segment"] = "first"
    df = (
        df.groupby(["_week", "ticker"])
        .agg(_agg_d)
        .reset_index()
        .rename(columns={"_week": "_dt"})
    )
    # Tukey fences (1.5 × IQR) per week
    _q1  = df.groupby("_dt")[metric_col].transform(lambda s: s.quantile(0.25))
    _q3  = df.groupby("_dt")[metric_col].transform(lambda s: s.quantile(0.75))
    _iqr = _q3 - _q1
    df   = df[
        (df[metric_col] >= _q1 - 1.5 * _iqr) &
        (df[metric_col] <= _q3 + 1.5 * _iqr)
    ].copy()

    if df.empty or df["_dt"].nunique() < 2:
        st.caption("Not enough data after filtering — try relaxing the filters.")
        return

    dates_sorted = sorted(df["_dt"].unique())
    dates_str    = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates_sorted]

    # ── Build figure ──────────────────────────────────────────────────────────
    fig         = go.Figure()
    annotations = []

    if view_mode == "Universe (Median + Wtd Avg)":
        medians, wavgs, p25s, p75s = [], [], [], []
        for d in dates_sorted:
            sub_day = df[df["_dt"] == d].dropna(subset=[metric_col])
            vals    = sub_day[metric_col]

            medians.append(float(vals.median()))
            p25s.append(float(vals.quantile(0.25)))
            p75s.append(float(vals.quantile(0.75)))

            if "enterprise_value" in sub_day.columns:
                ev   = sub_day["enterprise_value"].fillna(0)
                mask = (vals > 0) & (ev > 0)
                if mask.sum() >= 3:
                    wavgs.append(
                        float((vals[mask] * ev[mask]).sum() / ev[mask].sum())
                    )
                else:
                    wavgs.append(float("nan"))
            else:
                wavgs.append(float("nan"))

        # 8-week rolling smooth (trailing window, min 3 points)
        medians = pd.Series(medians).rolling(8, min_periods=3).mean().tolist()
        wavgs   = pd.Series(wavgs).rolling(8, min_periods=3).mean().tolist()
        p25s    = pd.Series(p25s).rolling(8, min_periods=3).mean().tolist()
        p75s    = pd.Series(p75s).rolling(8, min_periods=3).mean().tolist()

        # P25–P75 shaded band
        fig.add_trace(go.Scatter(
            x=dates_str, y=p25s,
            fill=None, mode="lines",
            line=dict(color="rgba(0,0,0,0)", width=0),
            showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=dates_str, y=p75s,
            fill="tonexty",
            fillcolor="rgba(34,197,94,0.06)",
            mode="lines",
            line=dict(color="rgba(0,0,0,0)", width=0),
            name="P25–P75 Band",
            hoverinfo="skip",
        ))

        fig.add_trace(go.Scatter(
            x=dates_str, y=medians,
            mode="lines",
            line=dict(color="#22C55E", width=2),
            name="Median",
            hovertemplate="Median: %{y:.1f}x<extra></extra>",
        ))

        has_wavg = any(not np.isnan(w) for w in wavgs)
        if has_wavg:
            fig.add_trace(go.Scatter(
                x=dates_str, y=wavgs,
                mode="lines",
                line=dict(color="#38BDF8", width=2),
                name="TEV-Wtd Avg",
                hovertemplate="TEV-Wtd Avg: %{y:.1f}x<extra></extra>",
            ))

        valid_m = [(i, m) for i, m in enumerate(medians) if not np.isnan(m)]
        if len(valid_m) >= 2:
            delta = valid_m[-1][1] - valid_m[0][1]
            sign  = "+" if delta >= 0 else ""
            arrow = "↑" if delta >= 0 else "↓"
            chart_title = (
                f"NTM {metric_short} — Universe  "
                f"({arrow} {sign}{delta:.1f}x over period)"
            )
        else:
            chart_title = f"NTM {metric_short} — Universe"

    else:  # By Segment
        seg_rev_lookup = {v: k for k, v in SEGMENT_SHORT.items()}
        for seg_label, color in SEG_COLOR_MAP.items():
            if seg_label not in sel_segs:
                continue
            seg_raw = seg_rev_lookup.get(seg_label)
            if not seg_raw:
                continue
            seg_df  = df[df["segment"] == seg_raw]
            grp     = seg_df.groupby("_dt")[metric_col]
            sub = (
                grp.median()
                .where(grp.count() >= 2)
                .dropna()
                .reset_index()
                .sort_values("_dt")
            )
            if sub.empty:
                continue

            sub = sub.copy()
            sub[metric_col] = (
                sub[metric_col].rolling(window=8, min_periods=3, center=False).mean()
            )
            sub = sub.dropna(subset=[metric_col])
            if sub.empty:
                continue

            d_strs = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in sub["_dt"]]
            y_vals = sub[metric_col].tolist()
            fig.add_trace(go.Scatter(
                x=d_strs, y=y_vals,
                mode="lines",
                line=dict(color=color, width=2),
                name=seg_label,
                hovertemplate=f"{seg_label}: %{{y:.1f}}x<extra></extra>",
            ))

        chart_title = f"NTM {metric_short} — By Segment"

    # ── Layout ────────────────────────────────────────────────────────────────
    layout = _plotly_layout(chart_title, height=580)
    layout["hovermode"]           = "x unified"
    layout["yaxis"]["ticksuffix"] = "x"
    layout["yaxis"]["zeroline"]   = False
    layout["xaxis"]["showgrid"]   = False
    layout["annotations"]         = annotations
    layout["legend"] = dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right",  x=1,
        font=dict(size=10, color="#111827"),
        bgcolor="rgba(0,0,0,0)",
    )
    layout["margin"].update({"r": 80, "t": 55})
    fig.update_layout(**layout)

    # ── Crosshair spikes ───────────────────────────────────────────────────
    fig.update_xaxes(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )
    fig.update_yaxes(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )
    fig.update_layout(spikedistance=-1, hoverdistance=-1)

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"scrollZoom": False, "displayModeBar": False},
        key=f"vt_chart_{tab_key}",
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — VALUATION VS. PERFORMANCE SCATTER
# ─────────────────────────────────────────────────────────────────────────────

def _build_scatter_df(records):
    """Flatten raw API records into a DataFrame for the scatter chart."""
    rows = []
    for d in records:
        rev_x    = d.get("ntm_tev_rev")
        ebitda_x = d.get("ntm_tev_ebitda")
        gp_x     = d.get("ntm_tev_gp")
        seg      = SEGMENT_SHORT.get(d.get("segment", ""), d.get("segment", ""))
        ticker   = d.get("ticker", "?")
        name     = d.get("name") or "?"
        tev      = d.get("enterprise_value")
        rev_gr   = d.get("ntm_revenue_growth")
        ebitda_m = d.get("ebitda_margin")
        gross_m  = d.get("gross_margin")
        rule_x   = (ebitda_m + 2 * rev_gr) * 100 if (
            rev_gr is not None and ebitda_m is not None
        ) else None
        has_any = (rev_x and rev_x > 0) or (ebitda_x and ebitda_x > 0) or (gp_x and gp_x > 0)
        if has_any:
            rows.append({
                "Ticker":             ticker,
                "Name":               name,
                "Category":           seg,
                "NTM Rev x":          rev_x    if rev_x    and rev_x    > 0 else None,
                "NTM EBITDA x":       ebitda_x if ebitda_x and ebitda_x > 0 else None,
                "NTM GP x":           gp_x     if gp_x     and gp_x     > 0 else None,
                "TEV":                tev      if tev      and tev      > 0 else None,
                "Rule of X":          rule_x,
                "NTM Rev Growth":     rev_gr   * 100 if rev_gr   is not None else None,
                "NTM EBITDA Margin":  ebitda_m * 100 if ebitda_m is not None else None,
                "NTM Gross Margin":   gross_m  * 100 if gross_m  is not None else None,
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _chart_scatter_figure(df_plot, x_metric="NTM Revenue Growth %",
                          y_metric="NTM EV/Revenue"):
    """Return a Plotly scatter: selective labels, OLS trendline, tiered TEV
    dot sizes, near-invisible quadrant guides, rich hover."""
    _X_COL = {
        "NTM Revenue Growth %":  "NTM Rev Growth",
        "NTM EBITDA Margin %":   "NTM EBITDA Margin",
        "NTM Gross Margin %":    "NTM Gross Margin",
        "Rule of X (NTM Rev Growth + NTM EBITDA Margin)": "Rule of X",
    }
    _Y_COL = {
        "NTM EV/Revenue":        "NTM Rev x",
        "NTM EV/EBITDA":         "NTM EBITDA x",
        "NTM EV/GP":             "NTM GP x",
    }
    _X_LBL = {
        "NTM Revenue Growth %":  "NTM Revenue Growth (%)",
        "NTM EBITDA Margin %":   "NTM EBITDA Margin (%)",
        "NTM Gross Margin %":    "NTM Gross Margin (%)",
        "Rule of X (NTM Rev Growth + NTM EBITDA Margin)": "Rule of X  (NTM EBITDA Margin + 2× NTM Rev Growth)",
    }
    _Y_LBL = {
        "NTM EV/Revenue":        "NTM EV/Revenue (x)",
        "NTM EV/EBITDA":         "NTM EV/EBITDA (x)",
        "NTM EV/GP":             "NTM EV/Gross Profit (x)",
    }

    x_col = _X_COL.get(x_metric, "NTM Rev x")
    y_col = _Y_COL.get(y_metric, "NTM Rev Growth")

    df = df_plot.dropna(subset=[x_col, y_col]).copy()
    if df.empty or len(df) < 3:
        return None

    # ── FIX 2 — 3-tier TEV-based dot sizing ──────────────────────────────────
    # Thresholds in raw dollars ($50B / $10B)
    _TEV_MEGA  = 50_000_000_000   # >$50B mega-cap  → 14px
    _TEV_LARGE = 10_000_000_000   # $10-50B          → 10px
    def _dot_size(tev):
        if pd.isna(tev):
            return 8
        if tev >= _TEV_MEGA:
            return 14
        if tev >= _TEV_LARGE:
            return 10
        return 7
    df["_msize"] = df["TEV"].apply(_dot_size)

    x_arr = df[x_col].values.astype(float)
    y_arr = df[y_col].values.astype(float)

    # ── OLS regression ────────────────────────────────────────────────────────
    r_squared = trend_x = trend_y = None
    if _HAS_SCIPY and len(x_arr) >= 4:
        slope, intercept, r_val, _, _ = _sp_stats.linregress(x_arr, y_arr)
        r_squared = r_val ** 2
        trend_x = np.linspace(x_arr.min(), x_arr.max(), 120)
        trend_y = slope * trend_x + intercept

    # ── Axis extents with padding ─────────────────────────────────────────────
    x_span = max(x_arr.max() - x_arr.min(), 1.0)
    y_span = max(y_arr.max() - y_arr.min(), 2.0)
    x0_r, x1_r = x_arr.min() - x_span * 0.06, x_arr.max() + x_span * 0.06
    y0_r, y1_r = y_arr.min() - y_span * 0.10, y_arr.max() + y_span * 0.12

    median_x = float(np.median(x_arr))
    zero_y   = float(np.median(y_arr))

    # ── FIX 3 — build label_set (top movers + mega-caps only) ─────────────────
    label_set = set()
    tev_col_clean = df["TEV"].dropna()
    if len(tev_col_clean) >= 5:
        label_set |= set(df.nlargest(5, "TEV")["Ticker"].tolist())
    elif len(tev_col_clean) > 0:
        label_set |= set(df.nlargest(len(tev_col_clean), "TEV")["Ticker"].tolist())
    label_set |= set(df.nlargest(3, x_col)["Ticker"].tolist())
    label_set |= set(df.nsmallest(3, x_col)["Ticker"].tolist())
    label_set |= set(df.nlargest(2, y_col)["Ticker"].tolist())
    label_set |= set(df.nsmallest(2, y_col)["Ticker"].tolist())

    fig = go.Figure()

    # ── FIX 8 — nearly-invisible median reference lines ───────────────────────
    fig.add_shape(type="line",
                  x0=median_x, x1=median_x, y0=y0_r, y1=y1_r,
                  xref="x", yref="y",
                  line=dict(color="#E2E8F0", width=0.75, dash="dot"))
    fig.add_shape(type="line",
                  x0=x0_r, x1=x1_r, y0=zero_y, y1=zero_y,
                  xref="x", yref="y",
                  line=dict(color="#E2E8F0", width=0.75, dash="dot"))

    # ── Monospace hover: short labels + right-justified values ───────────────
    _HOVER_X_LABELS = {
        "NTM Revenue Growth %":  "NTM Rev Growth",
        "NTM EBITDA Margin %":   "NTM EBITDA Margin",
        "NTM Gross Margin %":    "NTM Gross Margin",
        "Rule of X (NTM Rev Growth + NTM EBITDA Margin)": "Rule of X",
    }
    _HOVER_Y_LABELS = {
        "NTM EV/Revenue":  "NTM EV/Rev",
        "NTM EV/EBITDA":   "NTM EV/EBITDA",
        "NTM EV/GP":       "NTM EV/GP",
    }
    x_short = _HOVER_X_LABELS.get(x_metric, x_metric)
    y_short = _HOVER_Y_LABELS.get(y_metric, y_metric)

    def _fmt_x_val(val):
        if not pd.notna(val):
            return "–"
        if x_col == "Rule of X":
            return f"{val:.0f}"
        return f"{val:.0f}%"

    def _fmt_y_val(val):
        return f"{val:.1f}x" if pd.notna(val) else "–"

    # Pre-compute global max value width across all rows for alignment
    _all_x_fmt = [_fmt_x_val(v) for v in df[x_col]]
    _all_y_fmt = [_fmt_y_val(v) for v in df[y_col]]
    _max_val_w = max(
        max((len(s) for s in _all_x_fmt), default=4),
        max((len(s) for s in _all_y_fmt), default=4),
    )
    _label_w   = max(len(x_short), len(y_short))
    _x_lbl     = x_short.ljust(_label_w)
    _y_lbl     = y_short.ljust(_label_w)
    _pad_total = _label_w + 2 + _max_val_w + 6   # extra chars prevent value clipping

    _hover_tmpl = (
        "<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
        "<br>"
        "%{customdata[2]}<br>"
        "%{customdata[3]}"
        "<extra></extra>"
    )

    # ── Scatter traces — one per category, selective labels ───────────────────
    for label, color in SEG_COLOR_MAP.items():
        sub = df[df["Category"] == label].copy()
        if sub.empty:
            continue

        # customdata: [0] name  [1] ticker  [2] x_row  [3] y_row
        custom = list(zip(
            sub["Name"].fillna("?").tolist(),
            sub["Ticker"].tolist(),
            [(_x_lbl + "  " + _fmt_x_val(v).rjust(_max_val_w)).ljust(_pad_total) for v in sub[x_col]],
            [(_y_lbl + "  " + _fmt_y_val(v).rjust(_max_val_w)).ljust(_pad_total) for v in sub[y_col]],
        ))

        # Selective text — only label companies in label_set (FIX 3)
        tick_labels = [
            t if t in label_set else ""
            for t in sub["Ticker"].tolist()
        ]

        fig.add_trace(go.Scatter(
            x=sub[x_col],
            y=sub[y_col],
            mode="markers+text",
            name=label,
            text=tick_labels,
            textposition="top right",
            textfont=dict(size=9, color="#374151", family="DM Sans"),
            marker=dict(
                size=sub["_msize"].tolist(),
                color=color,
                opacity=0.75,                      # FIX 2
                line=dict(width=1, color="white"), # FIX 2
            ),
            customdata=custom,
            hovertemplate=_hover_tmpl,
        ))

    # ── FIX 5 — regression trendline: muted gray dashed ──────────────────────
    if trend_x is not None:
        fig.add_trace(go.Scatter(
            x=trend_x, y=trend_y,
            mode="lines",
            line=dict(color="#94A3B8", width=1.5, dash="dash"),
            showlegend=False,
            hoverinfo="skip",
        ))

    # ── Annotations ───────────────────────────────────────────────────────────
    annotations = []

    # FIX 5 — R² in top-left with semi-transparent background
    if r_squared is not None:
        annotations.append(dict(
            x=0.02, xref="paper", y=0.98, yref="paper",
            text=f"R² = {r_squared:.2f}",
            showarrow=False,
            font=dict(size=11, color="#64748B", family="DM Sans"),
            bgcolor="rgba(255,255,255,0.8)",
            borderpad=4,
            xanchor="left", yanchor="top",
        ))

    # FIX 12 — "Dot size = TEV" bottom-right, subtle
    annotations.append(dict(
        x=0.99, xref="paper", y=0.01, yref="paper",
        text="Dot size = TEV",
        showarrow=False,
        font=dict(size=8, color="#B0B7C3", family="DM Sans"),
        xanchor="right", yanchor="bottom",
    ))

    # ── FIX 1 + 6 + 7 — Layout ───────────────────────────────────────────────
    layout = _plotly_layout("", height=580)

    # X-axis: fundamentals (growth %, margin %, Rule of X)
    _x_suffix = "%" if x_col in ("NTM Rev Growth", "NTM EBITDA Margin", "NTM Gross Margin") else ""
    # Y-axis: multiples (x)
    _y_suffix = "x"
    layout["xaxis"].update(dict(
        title=dict(
            text=_X_LBL.get(x_metric, x_metric),
            font=dict(size=12, color="#374151", family="DM Sans"),
            standoff=30,
        ),
        ticksuffix=_x_suffix,
        range=[x0_r, x1_r],
        tickfont=dict(size=11, color="#6B7280", family="DM Sans"),
        gridcolor="#F3F4F6",
        gridwidth=0.5,
        linecolor="#D1D5DB",
        linewidth=1,
        zeroline=False,
    ))
    layout["yaxis"].update(dict(
        title=dict(
            text=_Y_LBL.get(y_metric, y_metric),
            font=dict(size=12, color="#374151", family="DM Sans"),
            standoff=15,
        ),
        ticksuffix=_y_suffix,
        range=[y0_r, y1_r],
        tickfont=dict(size=11, color="#6B7280", family="DM Sans"),
        gridcolor="#F3F4F6",
        gridwidth=0.5,
        linecolor="#D1D5DB",
        linewidth=1,
        zeroline=True,
        zerolinecolor="#D1D5DB",
        zerolinewidth=1,
    ))

    # FIX 7 — horizontal legend above chart
    layout["legend"] = dict(
        orientation="h",
        yanchor="bottom", y=1.02,
        xanchor="right",  x=1,
        font=dict(size=10, color="#111827", family="DM Sans"),
        itemsizing="constant",
        itemwidth=30,
        bgcolor="rgba(255,255,255,0)",
    )
    layout["annotations"] = annotations
    layout["margin"]      = dict(l=60, r=40, t=55, b=50)
    fig.update_layout(**layout)
    fig.update_xaxes(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )
    fig.update_yaxes(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )
    fig.update_layout(
        hovermode="closest",
        spikedistance=-1,
        hoverdistance=-1,
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E2E8F0",
            font=dict(size=11, color="#374151", family="Menlo, Monaco, Consolas, monospace"),
            align="left",
            namelength=0,
        ),
    )
    return fig


def _render_scatter_tab(all_data, tab_key):
    """Period selector + compact filter controls + scatter chart in white card."""

    # Build scatter df from all records (no price-change dependency)
    df_all = _build_scatter_df(all_data)
    if df_all.empty:
        st.caption("No valuation vs. performance data available.")
        return

    # ── Row 1: Category checkboxes ────────────────────────────────────────────
    all_cats = list(SEGMENT_SHORT.values())  # canonical display names
    st.markdown(
        '<div style="font-size:9px;font-weight:600;color:#94A3B8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px;">'
        'CATEGORIES</div>',
        unsafe_allow_html=True,
    )
    _n_cats = len(all_cats)
    _cat_cols = st.columns(_n_cats)
    sel_cats = []
    for i, cat in enumerate(all_cats):
        with _cat_cols[i]:
            if st.checkbox(cat, value=True, key=f"sc_cat_{tab_key}_{i}"):
                sel_cats.append(cat)

    # ── Row 2: TEV, Growth, Outliers, Reset Zoom ─────────────────────────────
    r1c1, r1c2, r1c3, r1c4 = st.columns([1.5, 1.5, 1.5, 1.5])
    with r1c1:
        _tv_all2 = list(TEV_BANDS.keys())
        sc_tev_sel = st.multiselect(
            "TEV", _tv_all2, default=_tv_all2,
            key=f"sc_tev_{tab_key}",
        )
    with r1c2:
        _gr_all2 = list(GROWTH_BANDS.keys())
        sc_growth_sel = st.multiselect(
            "GROWTH", _gr_all2, default=_gr_all2,
            key=f"sc_gr_{tab_key}",
        )
    with r1c3:
        remove_outliers = st.checkbox(
            "REMOVE OUTLIERS",
            value=False,
            key=f"sc_out_{tab_key}",
            help="Removes companies with metrics beyond the 5th/95th percentile to reduce distortion from extreme values.",
        )
    with r1c4:
        if st.button("Reset Zoom", key=f"sc_reset_{tab_key}"):
            st.rerun()

    # ── Row 3: Y-axis (multiple), X-axis (fundamental) ──────────────────────
    r2c1, r2c2, _ = st.columns([2, 2, 2])
    _y_options = ["NTM EV/Revenue", "NTM EV/EBITDA", "NTM EV/GP"]
    _x_options = [
        "NTM Revenue Growth %",
        "NTM EBITDA Margin %",
        "NTM Gross Margin %",
        "Rule of X (NTM Rev Growth + NTM EBITDA Margin)",
    ]
    with r2c1:
        y_metric = st.selectbox(
            "Y-AXIS (MULTIPLE)",
            options=_y_options,
            index=0,
            key=f"sc_yax_{tab_key}",
        )
    with r2c2:
        x_metric = st.selectbox(
            "X-AXIS (FUNDAMENTAL)",
            options=_x_options,
            index=0,
            key=f"sc_xax_{tab_key}",
        )

    # ── Apply filters ──────────────────────────────────────────────────────────
    df_plot = df_all.copy()

    if sel_cats:
        df_plot = df_plot[df_plot["Category"].isin(sel_cats)]

    if len(sc_tev_sel) < len(TEV_BANDS):
        df_plot = df_plot[df_plot["TEV"].apply(
            lambda v: _in_any_band(v, sc_tev_sel, TEV_BANDS)
        )]

    if len(sc_growth_sel) < len(GROWTH_BANDS):
        df_plot = df_plot[df_plot["NTM Rev Growth"].apply(
            lambda v: _in_any_band(v, sc_growth_sel, GROWTH_BANDS)
        )]

    _Y_COL_MAP = {
        "NTM EV/Revenue":  "NTM Rev x",
        "NTM EV/EBITDA":   "NTM EBITDA x",
        "NTM EV/GP":       "NTM GP x",
    }
    _X_COL_MAP = {
        "NTM Revenue Growth %":  "NTM Rev Growth",
        "NTM EBITDA Margin %":   "NTM EBITDA Margin",
        "NTM Gross Margin %":    "NTM Gross Margin",
        "Rule of X (NTM Rev Growth + NTM EBITDA Margin)": "Rule of X",
    }
    x_col = _X_COL_MAP.get(x_metric, "NTM Rev Growth")
    y_col = _Y_COL_MAP.get(y_metric, "NTM Rev x")
    df_plot = df_plot.dropna(subset=[x_col, y_col])

    if remove_outliers and len(df_plot) >= 10:
        xlo, xhi = df_plot[x_col].quantile(0.05), df_plot[x_col].quantile(0.95)
        ylo, yhi = df_plot[y_col].quantile(0.05), df_plot[y_col].quantile(0.95)
        df_plot = df_plot[
            df_plot[x_col].between(xlo, xhi) &
            df_plot[y_col].between(ylo, yhi)
        ]

    if df_plot.empty or len(df_plot) < 3:
        st.caption("Not enough data after filtering — try relaxing the filters.")
        return

    fig = _chart_scatter_figure(df_plot, x_metric, y_metric)
    if fig:
        st.plotly_chart(fig, use_container_width=True, key=f"scatter_{tab_key}",
                        config={"scrollZoom": False, "displayModeBar": False})
    else:
        st.caption("Could not render chart with the current data.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — R² DECOMPOSITION
# ─────────────────────────────────────────────────────────────────────────────

def _run_sequential_r2(reg_df):
    """Run sequential OLS to decompose R² by factor.

    Returns dict with r2_growth, r2_gm, r2_ebitda, r2_full, r2_unexplained, n, model.
    """
    try:
        import statsmodels.api as sm
    except ImportError:
        return None

    y = reg_df["ntm_tev_rev"]

    # Step 1: Growth only
    X1 = sm.add_constant(reg_df[["ntm_revenue_growth"]])
    r2_growth = sm.OLS(y, X1).fit().rsquared

    # Step 2: Growth + Gross Margin
    X2 = sm.add_constant(reg_df[["ntm_revenue_growth", "gross_margin"]])
    r2_growth_gm = sm.OLS(y, X2).fit().rsquared

    # Step 3: Growth + Gross Margin + EBITDA Margin
    X3 = sm.add_constant(reg_df[["ntm_revenue_growth", "gross_margin", "ebitda_margin"]])
    model = sm.OLS(y, X3).fit()
    r2_full = model.rsquared

    return {
        "r2_growth": r2_growth,
        "r2_gm": r2_growth_gm - r2_growth,
        "r2_ebitda": r2_full - r2_growth_gm,
        "r2_full": r2_full,
        "r2_unexplained": 1.0 - r2_full,
        "n": len(reg_df),
        "model": model,
    }


def _render_r2_bar(result, y_label="Current", height=120):
    """Render a horizontal stacked bar for R² decomposition."""
    fig = go.Figure()
    segments = [
        ("Revenue Growth", result["r2_growth"], "#3B82F6"),
        ("Gross Margin", result["r2_gm"], "#10B981"),
        ("NTM EBITDA Margin", result["r2_ebitda"], "#F59E0B"),
        ("Unexplained", result["r2_unexplained"], "#E5E7EB"),
    ]
    for label, val, color in segments:
        fig.add_trace(go.Bar(
            y=[y_label],
            x=[val * 100],
            name=f"{label} ({val:.0%})",
            orientation="h",
            marker_color=color,
            text=f"{val:.0%}",
            textposition="inside",
            textfont=dict(size=13, color="white" if color != "#E5E7EB" else "#6B7280"),
            hovertemplate=f"{label}: {val:.1%}<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        height=height,
        margin=dict(l=0, r=0, t=30, b=0),
        xaxis=dict(range=[0, 100], showticklabels=False, showgrid=False),
        yaxis=dict(showticklabels=False),
        legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center", font=dict(size=12)),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans"),
        showlegend=True,
    )
    return fig


def _render_r2_decomposition(all_data, daily_mult, tab_key):
    """Full R² decomposition tab: current period bar, coefficient table, historical."""
    st.markdown(
        '<div style="font-size:18px;font-weight:700;color:#111827;margin-bottom:4px;">'
        "What's Driving Multiples</div>"
        '<div style="font-size:12px;color:#94A3B8;margin-bottom:16px;">'
        "How much of the variation in healthcare multiples is explained by growth, "
        "margins, and profitability — and what's left to narrative and sentiment.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Category checkboxes ──────────────────────────────────────────────────
    all_cats = list(SEGMENT_SHORT.values())
    st.markdown(
        '<div style="font-size:9px;font-weight:600;color:#94A3B8;'
        'text-transform:uppercase;letter-spacing:0.05em;margin-bottom:2px;">'
        'CATEGORIES</div>',
        unsafe_allow_html=True,
    )
    _r2_cat_cols = st.columns(len(all_cats))
    sel_cats = []
    for i, cat in enumerate(all_cats):
        with _r2_cat_cols[i]:
            if st.checkbox(cat, value=True, key=f"r2_cat_{tab_key}_{i}"):
                sel_cats.append(cat)

    # ── Filters row ──────────────────────────────────────────────────────────
    _rf1, _rf2, _rf3 = st.columns([2, 2, 2])
    with _rf1:
        _tv_all = list(TEV_BANDS.keys())
        r2_tev_sel = st.multiselect(
            "TEV", _tv_all, default=_tv_all,
            key=f"r2_tev_{tab_key}",
        )
    with _rf2:
        _gr_all = list(GROWTH_BANDS.keys())
        r2_growth_sel = st.multiselect(
            "GROWTH", _gr_all, default=_gr_all,
            key=f"r2_gr_{tab_key}",
        )
    with _rf3:
        remove_outliers = st.checkbox(
            "REMOVE OUTLIERS",
            value=True,
            key=f"r2_out_{tab_key}",
            help="Removes companies with metrics beyond the 5th/95th percentile to reduce distortion from extreme values.",
        )

    # ── Build regression dataframe from current snapshot ──────────────────────
    rows = []
    for d in all_data:
        seg = SEGMENT_SHORT.get(d.get("segment", ""), d.get("segment", ""))
        ntm_rev = d.get("ntm_tev_rev")
        rev_gr = d.get("ntm_revenue_growth")
        gm = d.get("gross_margin")
        em = d.get("ebitda_margin")
        tev = d.get("enterprise_value")
        if ntm_rev and ntm_rev > 0 and rev_gr is not None and gm is not None and em is not None:
            rows.append({
                "ticker": d.get("ticker", "?"),
                "category": seg,
                "ntm_tev_rev": ntm_rev,
                "ntm_revenue_growth": rev_gr * 100,
                "gross_margin": gm * 100,
                "ebitda_margin": em * 100,
                "tev": tev,
            })
    reg_df = pd.DataFrame(rows)

    if reg_df.empty or len(reg_df) < 10:
        st.warning("Not enough data for regression analysis. Need at least 10 companies with complete data.")
        return

    # Apply filters
    if sel_cats:
        reg_df = reg_df[reg_df["category"].isin(sel_cats)]
    if len(r2_tev_sel) < len(TEV_BANDS):
        reg_df = reg_df[reg_df["tev"].apply(lambda v: _in_any_band(v, r2_tev_sel, TEV_BANDS))]
    if len(r2_growth_sel) < len(GROWTH_BANDS):
        reg_df = reg_df[reg_df["ntm_revenue_growth"].apply(
            lambda v: _in_any_band(v, r2_growth_sel, GROWTH_BANDS)
        )]

    if remove_outliers and len(reg_df) >= 10:
        lo, hi = reg_df["ntm_tev_rev"].quantile(0.025), reg_df["ntm_tev_rev"].quantile(0.975)
        reg_df = reg_df[reg_df["ntm_tev_rev"].between(lo, hi)]

    if len(reg_df) < 10:
        st.warning("Not enough data after filtering — try relaxing the filters.")
        return

    # ── Section A: Current Period Decomposition ───────────────────────────────
    result = _run_sequential_r2(reg_df)
    if not result:
        st.error("statsmodels is required for R² decomposition. Install with: pip install statsmodels")
        return

    if result["r2_full"] < 0.15:
        st.warning(
            f"Low R² ({result['r2_full']:.0%}) — fundamentals currently explain very little of "
            "multiple variation. The market may be driven primarily by sentiment, AI narrative, "
            "or macro factors."
        )

    fig_bar = _render_r2_bar(result)
    st.plotly_chart(fig_bar, use_container_width=True, key=f"r2_bar_{tab_key}",
                    config={"displayModeBar": False})

    # Metric cards
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue Growth R²", f"{result['r2_growth']:.0%}")
    c2.metric("Gross Margin R²", f"{result['r2_gm']:.0%}")
    c3.metric("NTM EBITDA Margin R²", f"{result['r2_ebitda']:.0%}")
    c4.metric("Total R²", f"{result['r2_full']:.0%}")

    # Narrative
    drivers = {
        "Revenue Growth": result["r2_growth"],
        "Gross Margin": result["r2_gm"],
        "NTM EBITDA Margin": result["r2_ebitda"],
    }
    top_driver = max(drivers, key=drivers.get)
    top_pct = drivers[top_driver]

    st.caption(
        f"Based on {result['n']} companies. **{top_driver}** is the single strongest driver of "
        f"NTM EV/Revenue variation, explaining {top_pct:.0%} of the total. "
        f"All three factors together explain {result['r2_full']:.0%} of multiple dispersion — "
        f"the remaining {result['r2_unexplained']:.0%} reflects market sentiment, AI narrative, "
        f"sector rotation, and other qualitative factors. "
        f"Attribution order: growth → gross margin → NTM EBITDA margin (first variable gets credit "
        f"for shared explanatory power)."
    )

    # ── Section D: Coefficient Table ──────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:8px;">'
        "Regression Coefficients</div>",
        unsafe_allow_html=True,
    )

    model = result["model"]
    coef_df = pd.DataFrame({
        "Variable": ["Intercept", "NTM Revenue Growth (%)", "Gross Margin (%)", "NTM EBITDA Margin (%)"],
        "Coefficient": [f"{v:.3f}" for v in model.params.values],
        "Std Error": [f"{v:.3f}" for v in model.bse.values],
        "t-stat": [f"{v:.2f}" for v in model.tvalues.values],
        "p-value": [f"{v:.4f}" for v in model.pvalues.values],
        "Interpretation": [
            "Base multiple when all factors = 0",
            f"Each 1pp of growth adds {model.params.iloc[1]:.3f}x to the multiple",
            f"Each 1pp of gross margin adds {model.params.iloc[2]:.3f}x",
            f"Each 1pp of NTM EBITDA margin adds {model.params.iloc[3]:.3f}x",
        ],
    })
    st.dataframe(coef_df, use_container_width=True, hide_index=True)

    # ── Section C: Correlation Over Time (dual-line chart) ───────────────────
    if not daily_mult:
        st.info("Historical decomposition requires snapshot data. Not available.")
        return

    st.markdown("---")
    st.markdown(
        '<div style="font-size:15px;font-weight:700;color:#111827;margin-bottom:4px;">'
        "Correlation of EV / NTM Revenue vs. Growth (& Growth + Profitability) Over Time</div>"
        '<div style="font-size:12px;color:#94A3B8;margin-bottom:8px;">'
        "How well fundamentals explain multiple variation each month</div>",
        unsafe_allow_html=True,
    )

    # Correlation method selector
    _corr_col1, _corr_col2, _ = st.columns([2, 2, 6])
    with _corr_col1:
        corr_method = st.selectbox(
            "CORRELATION METHOD",
            options=["Spearman Rank (ρ²)", "OLS R²"],
            index=0,
            key=f"r2_method_{tab_key}",
        )
    use_spearman = "Spearman" in corr_method

    df_hist = pd.DataFrame(daily_mult)
    if df_hist.empty:
        st.info("No historical data available for time-series decomposition.")
        return

    df_hist["_dt"] = pd.to_datetime(df_hist["date"], errors="coerce")
    df_hist = df_hist.dropna(subset=["_dt"])

    # Sector filter (use same selection)
    seg_rev = {v: k for k, v in SEGMENT_SHORT.items()}
    if sel_cats:
        full_segs = [seg_rev.get(s, s) for s in sel_cats]
        df_hist = df_hist[df_hist["segment"].isin(full_segs)]

    # Sample monthly (use last date per month)
    df_hist["_ym"] = df_hist["_dt"].dt.to_period("M")
    monthly_dates = df_hist.groupby("_ym")["_dt"].max().values

    try:
        import statsmodels.api as sm
        from scipy.stats import spearmanr
    except ImportError:
        st.error("statsmodels and scipy required.")
        return

    hist_r2 = []
    for dt in monthly_dates:
        snap = df_hist[df_hist["_dt"] == dt].copy()
        snap = snap.dropna(subset=["ntm_tev_rev", "ntm_revenue_growth", "ebitda_margin"])
        # Convert decimals → percentages
        for col in ["ntm_revenue_growth", "ebitda_margin"]:
            if snap[col].abs().max() <= 5:
                snap[col] = snap[col] * 100
        if len(snap) < 15:
            continue

        # Trim outliers (2.5% each tail on multiples)
        lo_q, hi_q = snap["ntm_tev_rev"].quantile(0.025), snap["ntm_tev_rev"].quantile(0.975)
        snap = snap[snap["ntm_tev_rev"].between(lo_q, hi_q)]
        if len(snap) < 15:
            continue

        y = snap["ntm_tev_rev"]

        if use_spearman:
            # Spearman rank correlation — captures nonlinear monotonic relationships
            try:
                rho_g, _ = spearmanr(y, snap["ntm_revenue_growth"])
                r2_growth = rho_g ** 2

                # Growth + Profitability: use average of individual Spearman ρ² values
                # (multivariate Spearman isn't standard, so use OLS on ranks)
                from scipy.stats import rankdata
                y_rank = rankdata(y)
                gr_rank = rankdata(snap["ntm_revenue_growth"].values)
                em_rank = rankdata(snap["ebitda_margin"].values)
                X_rank = sm.add_constant(np.column_stack([gr_rank, em_rank]))
                r2_growth_profit = sm.OLS(y_rank, X_rank).fit().rsquared
            except Exception:
                continue
        else:
            # Standard OLS R²
            X1 = sm.add_constant(snap[["ntm_revenue_growth"]])
            try:
                r2_growth = sm.OLS(y, X1).fit().rsquared
            except Exception:
                continue
            X2 = sm.add_constant(snap[["ntm_revenue_growth", "ebitda_margin"]])
            try:
                r2_growth_profit = sm.OLS(y, X2).fit().rsquared
            except Exception:
                r2_growth_profit = r2_growth

        hist_r2.append({
            "date": pd.Timestamp(dt),
            "r2_growth": r2_growth,
            "r2_growth_profit": r2_growth_profit,
            "n": len(snap),
        })

    if not hist_r2:
        st.info("Not enough historical data points for time-series chart.")
        return

    hist_df = pd.DataFrame(hist_r2).sort_values("date")

    fig_corr = go.Figure()

    # Thin text labels: show every 6th point label only
    _n_pts = len(hist_df)
    _g_labels = [f"{v:.2f}" if i % 6 == 0 else "" for i, v in enumerate(hist_df["r2_growth"])]
    _gp_labels = [f"{v:.2f}" if i % 6 == 0 else "" for i, v in enumerate(hist_df["r2_growth_profit"])]

    # Growth Correlation line (dark navy)
    fig_corr.add_trace(go.Scatter(
        x=hist_df["date"],
        y=hist_df["r2_growth"],
        name="Growth Correlation",
        mode="lines+markers+text",
        line=dict(color="#1E3A5F", width=2),
        marker=dict(size=5, color="#1E3A5F"),
        text=_g_labels,
        textposition="bottom center",
        textfont=dict(size=9, color="#1E3A5F"),
        hovertemplate="Growth R²: %{y:.3f}<br>n=%{customdata}<extra></extra>",
        customdata=hist_df["n"],
    ))

    # Growth + Profitability Correlation line (teal/cyan)
    fig_corr.add_trace(go.Scatter(
        x=hist_df["date"],
        y=hist_df["r2_growth_profit"],
        name="Growth + Profitability Correlation",
        mode="lines+markers+text",
        line=dict(color="#0EA5E9", width=2),
        marker=dict(size=5, color="#0EA5E9"),
        text=_gp_labels,
        textposition="top center",
        textfont=dict(size=9, color="#0EA5E9"),
        hovertemplate="Growth + Profitability R²: %{y:.3f}<br>n=%{customdata}<extra></extra>",
        customdata=hist_df["n"],
    ))

    # Tighten y-axis to actual data range + padding
    _y_max = max(hist_df["r2_growth"].max(), hist_df["r2_growth_profit"].max())
    _y_ceil = min(round(_y_max + 0.08, 1), 0.80)  # pad 8pp above max, cap at 0.80

    fig_corr.update_layout(
        yaxis=dict(
            title=dict(
                text="Spearman ρ²" if use_spearman else "R-Squared",
                font=dict(size=12, color="#374151", family="DM Sans"),
            ),
            range=[0, _y_ceil],
            dtick=0.05,
            gridcolor=PLOTLY_GRID,
            gridwidth=0.5,
            tickformat=".2f",
            tickfont=dict(size=11, color="#6B7280", family="DM Sans"),
        ),
        xaxis=dict(
            gridcolor=PLOTLY_GRID,
            gridwidth=0.5,
            tickfont=dict(size=11, color="#6B7280", family="DM Sans"),
        ),
        height=500,
        margin=dict(l=60, r=30, t=20, b=80),
        legend=dict(
            orientation="h", y=-0.15, x=0.5, xanchor="center",
            itemwidth=40, traceorder="normal",
            font=dict(size=11, family="DM Sans"),
        ),
        font=dict(family="DM Sans"),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="x",
    )

    st.plotly_chart(fig_corr, use_container_width=True, key=f"r2_corr_{tab_key}",
                    config={"displayModeBar": False})

    _method_note = (
        "Spearman rank correlation (ρ²) captures nonlinear monotonic relationships "
        "between multiples and fundamentals — more robust than linear R² for skewed data."
        if use_spearman else
        "OLS R² measures linear explanatory power."
    )
    st.caption(
        f"**Growth Correlation**: NTM EV/Revenue vs. NTM Revenue Growth alone. "
        f"**Growth + Profitability Correlation**: NTM EV/Revenue vs. NTM Revenue Growth + NTM EBITDA Margin. "
        f"When the gap between the two lines widens, the market is placing more weight on "
        f"profitability alongside growth. {_method_note} Source: FactSet estimates."
    )


# ─────────────────────────────────────────────────────────────────────────────
# PAGE RENDER
# ─────────────────────────────────────────────────────────────────────────────

tab1, tab2, tab3 = st.tabs(["Valuation vs. Performance", "Valuation Trends", "R² Decomposition"])

with tab1:
    _render_scatter_tab(all_data, "vr_t1")

with tab2:
    _render_valuation_tab(daily_mult, all_data, "vr_t2")

with tab3:
    _render_r2_decomposition(all_data, daily_mult, "vr_t3")
