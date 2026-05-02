"""
pages/drafts/scenario_screener.py -- Scenario Screener
Multi-condition filter engine for the healthcare universe.
Up to 6 filter rows (metric / operator / value), 5 preset screens,
results as count + comps table + optional scatter.

Run standalone:  streamlit run pages/drafts/scenario_screener.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from config.settings import DB_PATH, EXCEL_OVERRIDE_PATH
from fetcher.db_manager import DBManager
from fetcher.excel_override import load_overrides, apply_overrides
from utils.scatter_builder import (
    build_scatter_df, build_regression_scatter, SEGMENT_SHORT,
    _FONT_FAM, PLOTLY_BG,
)

render_sidebar()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
.block-container {
    max-width:100%!important;
    padding-left:2rem!important;
    padding-right:2rem!important;
    font-family:'DM Sans',sans-serif!important;
}
</style>
""", unsafe_allow_html=True)

# -- Page header with clear explanation ----------------------------------------
st.title("Scenario Screener")
st.markdown(
    '<p style="color:#64748B;font-size:14px;margin:-4px 0 18px 0;">'
    "Screen the full healthcare universe using up to 6 custom filters. "
    "Choose a preset or build your own criteria below, then view matched "
    "companies in the results table and scatter plot.</p>",
    unsafe_allow_html=True,
)

# -- Data ----------------------------------------------------------------------
db = DBManager(DB_PATH)

@st.cache_data(ttl=60)
def _load():
    data = db.get_all_latest_snapshots()
    ovr  = load_overrides(EXCEL_OVERRIDE_PATH)
    if ovr and data:
        data = apply_overrides(data, ovr, skip_sources={"factset"})
    return data

records = _load()
if not records:
    st.info("No data available. Run the data fetcher to populate the database.")
    st.stop()

df_all = pd.DataFrame(records)
df_all["seg_label"]      = df_all["segment"].map(SEGMENT_SHORT).fillna(df_all["segment"])
df_all["rev_growth_pct"] = df_all["ntm_revenue_growth"].mul(100)
df_all["ebitda_mgn_pct"] = df_all["ebitda_margin"].mul(100)
df_all["gross_mgn_pct"]  = df_all["gross_margin"].mul(100)
df_all["chg_2w_pct"]     = df_all["price_change_2w"].mul(100)
df_all["chg_2m_pct"]     = df_all["price_change_2m"].mul(100)
df_all["tev_bn"]         = df_all["enterprise_value"].div(1e9)
df_all["mcap_bn"]        = df_all["market_cap"].div(1e9)

# -- Metric definitions --------------------------------------------------------
# (display name, column name, type, unit)
METRICS: dict[str, tuple[str, str, str]] = {
    "NTM EV/Revenue (x)":       ("ntm_tev_rev",     "numeric", "x"),
    "NTM EV/EBITDA (x)":        ("ntm_tev_ebitda",  "numeric", "x"),
    "NTM Revenue Growth (%)":   ("rev_growth_pct",  "numeric", "%"),
    "NTM EBITDA Margin (%)":    ("ebitda_mgn_pct",  "numeric", "%"),
    "Gross Margin (%)":         ("gross_mgn_pct",   "numeric", "%"),
    "Enterprise Value ($B)":    ("tev_bn",           "numeric", "B"),
    "Market Cap ($B)":          ("mcap_bn",          "numeric", "B"),
    "2W Price Change (%)":      ("chg_2w_pct",       "numeric", "%"),
    "2M Price Change (%)":      ("chg_2m_pct",       "numeric", "%"),
    "Segment":                  ("seg_label",        "category", ""),
}

NUMERIC_OPS  = [">", "\u2265", "<", "\u2264", "between"]
CATEGORY_OPS = ["equals", "not equals"]

# -- Preset screens ------------------------------------------------------------
PRESETS: dict[str, list[dict]] = {
    "(none)": [],
    "Undervalued Growth": [
        {"metric": "NTM EV/Revenue (x)",       "op": "<",  "val": 10.0},
        {"metric": "NTM Revenue Growth (%)",   "op": "\u2265",  "val": 20.0},
    ],
    "Cash Cows": [
        {"metric": "NTM EBITDA Margin (%)",     "op": "\u2265",  "val": 20.0},
        {"metric": "Gross Margin (%)",          "op": "\u2265",  "val": 70.0},
    ],
    "High Growth (>30%)": [
        {"metric": "NTM Revenue Growth (%)",    "op": "\u2265",  "val": 30.0},
    ],
    "Large Cap Cheap": [
        {"metric": "Enterprise Value ($B)",     "op": "\u2265",  "val": 5.0},
        {"metric": "NTM EV/Revenue (x)",        "op": "<",  "val": 8.0},
    ],
}

# -- Filter UI -----------------------------------------------------------------
st.markdown("**Preset Screens** -- select a preset to auto-populate filters, or leave as (none) to build from scratch.")
preset_col, _ = st.columns([3, 7])
with preset_col:
    preset_choice = st.selectbox("Load preset screen", list(PRESETS.keys()), index=0,
                                 label_visibility="collapsed")

preset_filters = PRESETS[preset_choice]
MAX_FILTERS = 6

# Store filters in session state
if "ss_filters" not in st.session_state or (
    preset_choice != "(none)" and st.session_state.get("_last_preset") != preset_choice
):
    st.session_state["ss_filters"]   = preset_filters.copy() or [{}]
    st.session_state["_last_preset"] = preset_choice

current_filters: list[dict] = st.session_state["ss_filters"]

# Ensure at least one filter row
if not current_filters:
    current_filters = [{}]

st.markdown("---")
st.markdown("**Filter Conditions**")

# Column headers for the filter rows
hdr_c1, hdr_c2, hdr_c3, hdr_c4, hdr_c5 = st.columns([3, 2, 2, 2, 1])
with hdr_c1:
    st.caption("Metric")
with hdr_c2:
    st.caption("Operator")
with hdr_c3:
    st.caption("Value")
with hdr_c4:
    st.caption("Upper bound (between)")
with hdr_c5:
    st.caption("")

def _render_filter_row(idx: int, flt: dict) -> dict:
    c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 1])
    with c1:
        metric = st.selectbox(
            f"Metric {idx+1}", list(METRICS.keys()),
            index=list(METRICS.keys()).index(flt.get("metric", list(METRICS.keys())[0])),
            key=f"ss_metric_{idx}",
            label_visibility="collapsed",
        )
    col_name, col_type, unit = METRICS[metric]
    ops = CATEGORY_OPS if col_type == "category" else NUMERIC_OPS
    with c2:
        op = st.selectbox(
            f"Op {idx+1}", ops,
            index=ops.index(flt.get("op", ops[0])) if flt.get("op") in ops else 0,
            key=f"ss_op_{idx}",
            label_visibility="collapsed",
        )
    result = {"metric": metric, "op": op}
    with c3:
        if col_type == "category":
            seg_opts = sorted(df_all["seg_label"].dropna().unique().tolist())
            val = st.selectbox(
                f"Val {idx+1}", seg_opts,
                index=seg_opts.index(flt.get("val", seg_opts[0])) if flt.get("val") in seg_opts else 0,
                key=f"ss_val_{idx}",
                label_visibility="collapsed",
            )
            result["val"] = val
        else:
            col_min = float(df_all[col_name].dropna().min())
            col_max = float(df_all[col_name].dropna().max())
            step    = 0.5 if unit == "x" else 1.0
            default_val = flt.get("val", round((col_min + col_max) / 2, 1))
            val = st.number_input(
                f"Val {idx+1}", value=float(default_val),
                min_value=col_min, max_value=col_max, step=step,
                key=f"ss_val_{idx}",
                label_visibility="collapsed",
            )
            result["val"] = val
    with c4:
        if op == "between" and col_type == "numeric":
            default_val2 = flt.get("val2", float(val) + 5.0)
            val2 = st.number_input(
                f"Val2 {idx+1}", value=float(default_val2),
                min_value=col_min, max_value=col_max, step=step,
                key=f"ss_val2_{idx}",
                label_visibility="collapsed",
            )
            result["val2"] = val2
        else:
            st.empty()
    with c5:
        remove = st.button("Remove", key=f"ss_rm_{idx}", help="Remove this filter")
        result["_remove"] = remove
    return result


new_filters = []
for i, f in enumerate(current_filters):
    rendered = _render_filter_row(i, f)
    if not rendered.get("_remove"):
        rendered.pop("_remove", None)
        new_filters.append(rendered)

add_col, _ = st.columns([2, 8])
with add_col:
    if len(new_filters) < MAX_FILTERS:
        if st.button("+ Add filter"):
            new_filters.append({})

st.session_state["ss_filters"] = new_filters

# -- Apply filters -------------------------------------------------------------
df_result = df_all.copy()

for f in new_filters:
    if not f.get("metric"):
        continue
    col_name, col_type, _ = METRICS[f["metric"]]
    op  = f.get("op", ">")
    val = f.get("val")
    if val is None:
        continue

    if col_type == "category":
        if op == "equals":
            df_result = df_result[df_result[col_name] == val]
        else:
            df_result = df_result[df_result[col_name] != val]
    else:
        series = df_result[col_name]
        try:
            v = float(val)
        except (TypeError, ValueError):
            continue
        if op == ">":
            df_result = df_result[series > v]
        elif op == "\u2265":
            df_result = df_result[series >= v]
        elif op == "<":
            df_result = df_result[series < v]
        elif op == "\u2264":
            df_result = df_result[series <= v]
        elif op == "between":
            v2 = f.get("val2")
            if v2 is not None:
                df_result = df_result[(series >= v) & (series <= float(v2))]

# -- Results -------------------------------------------------------------------
st.markdown("---")
st.markdown("**Results**")

n_result = len(df_result)
n_total  = len(df_all)

rc1, rc2, rc3, rc4 = st.columns(4)
with rc1:
    st.metric("Companies Matched", n_result)
with rc2:
    pct = n_result / n_total * 100 if n_total else 0
    st.metric("% of Universe", f"{pct:.0f}%")
with rc3:
    med_rev_x = df_result["ntm_tev_rev"].median()
    st.metric("Median NTM EV/Rev", f"{med_rev_x:.1f}x" if pd.notna(med_rev_x) else "—")
with rc4:
    med_gr = df_result["rev_growth_pct"].median()
    st.metric("Median Rev Growth", f"{med_gr:.0f}%" if pd.notna(med_gr) else "—")

if df_result.empty:
    st.warning("No companies match all applied filters.")
    st.stop()

# -- Comps table ---------------------------------------------------------------
st.markdown(
    '<div style="font-size:14px;font-weight:600;color:#374151;margin-bottom:8px;">Matched Companies</div>',
    unsafe_allow_html=True,
)

display_cols = {
    "ticker":        "Ticker",
    "name":          "Company",
    "seg_label":     "Segment",
    "tev_bn":        "TEV ($B)",
    "ntm_tev_rev":   "NTM EV/Rev",
    "ntm_tev_ebitda":"NTM EV/EBITDA",
    "rev_growth_pct":"Rev Growth %",
    "ebitda_mgn_pct":"NTM EBITDA Mgn %",
    "gross_mgn_pct": "Gross Mgn %",
}
disp_df = df_result[[c for c in display_cols if c in df_result.columns]].copy()
disp_df.columns = [display_cols[c] for c in disp_df.columns]

def _fmt_cell(series, suffix="", decimals=1):
    return series.apply(
        lambda v: f"{v:.{decimals}f}{suffix}" if pd.notna(v) else "\u2014"
    )

if "NTM EV/Rev" in disp_df.columns:
    disp_df["NTM EV/Rev"]     = _fmt_cell(disp_df["NTM EV/Rev"], "x")
if "NTM EV/EBITDA" in disp_df.columns:
    disp_df["NTM EV/EBITDA"]  = _fmt_cell(disp_df["NTM EV/EBITDA"], "x")
if "TEV ($B)" in disp_df.columns:
    disp_df["TEV ($B)"]       = _fmt_cell(disp_df["TEV ($B)"], "B")
for pct_col in ["Rev Growth %", "NTM EBITDA Mgn %", "Gross Mgn %"]:
    if pct_col in disp_df.columns:
        disp_df[pct_col] = _fmt_cell(disp_df[pct_col], "%", decimals=1)

disp_df = disp_df.sort_values("TEV ($B)", ascending=False) if "TEV ($B)" in disp_df.columns else disp_df

st.dataframe(disp_df, use_container_width=True, hide_index=True, height=340)

# -- Optional scatter ----------------------------------------------------------
if n_result >= 3:
    st.markdown("---")
    scat_col1, scat_col2, _ = st.columns([2, 2, 6])
    with scat_col1:
        x_opt = st.selectbox(
            "Scatter X",
            ["NTM EV/Revenue", "NTM EV/EBITDA"],
            key="ss_scatter_x",
        )
    with scat_col2:
        y_opt = st.selectbox(
            "Scatter Y",
            ["NTM Revenue Growth %", "NTM EBITDA Margin %"],
            key="ss_scatter_y",
        )

    _x_map = {"NTM EV/Revenue": "NTM Rev x", "NTM EV/EBITDA": "NTM EBITDA x"}
    _y_map = {
        "NTM Revenue Growth %": "NTM Rev Growth",
        "NTM EBITDA Margin %":  "EBITDA Margin",
    }
    _y_sfx_map = {
        "NTM Revenue Growth %": "%",
        "NTM EBITDA Margin %":  "%",
    }

    scatter_records = df_result.to_dict("records")
    df_scatter = build_scatter_df(scatter_records)

    x_c = _x_map[x_opt]
    y_c = _y_map[y_opt]

    fig = build_regression_scatter(
        df_scatter, x_c, y_c,
        x_label=x_opt + " (x)",
        y_label=y_opt,
        height=540,
        x_suffix="x",
        y_suffix=_y_sfx_map[y_opt],
    )
    if fig:
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("Not enough data for scatter.")
