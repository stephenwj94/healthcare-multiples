"""
pages/drafts/comp_set_builder.py — Custom Comp Set Builder
Select 3–10 companies, view Comps Table / Regression / Trading History.
Save and load named comp sets to/from data/comp_sets.json.

Run standalone:  streamlit run pages/drafts/comp_set_builder.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from config.settings import DB_PATH, DATA_DIR, EXCEL_OVERRIDE_PATH
from fetcher.db_manager import DBManager
from fetcher.excel_override import load_overrides, apply_overrides
from utils.scatter_builder import (
    build_scatter_df, build_regression_scatter,
    SEGMENT_SHORT, SEG_COLOR_MAP, plotly_layout,
    _FONT_FAM, PLOTLY_BG, PLOTLY_GRID, PLOTLY_TEXT,
)

st.set_page_config(page_title="Comp Set Builder", page_icon="🧩", layout="wide")
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
.csb-card {
    background:white;
    border:1px solid #E5E7EB;
    border-radius:12px;
    padding:16px 20px;
    box-shadow:0 1px 3px rgba(0,0,0,0.04);
    margin-bottom:12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:22px;font-weight:700;color:#111827;margin-bottom:2px;">Comp Set Builder</div>'
    '<div style="font-size:12px;color:#94A3B8;margin-bottom:16px;">'
    'Build and save custom peer groups — 3 to 10 companies</div>',
    unsafe_allow_html=True,
)

# ── Data ───────────────────────────────────────────────────────────────────────
db = DBManager(DB_PATH)

@st.cache_data(ttl=60)
def _load_current():
    data = db.get_all_latest_snapshots()
    ovr  = load_overrides(EXCEL_OVERRIDE_PATH)
    if ovr and data:
        data = apply_overrides(data, ovr, skip_sources={"factset"})
    return data

@st.cache_data(ttl=300)
def _load_daily(days_back=730):
    return db.get_daily_multiples(days_back=days_back)

records = _load_current()
if not records:
    st.info("No data available. Run the data fetcher to populate the database.")
    st.stop()

df_all = pd.DataFrame(records)
df_all["seg_label"] = df_all["segment"].map(SEGMENT_SHORT).fillna(df_all["segment"])

# Build ticker → display label
ticker_list = sorted(df_all["ticker"].unique().tolist())
name_map    = df_all.set_index("ticker")["name"].to_dict()
options     = [f"{t}  —  {name_map.get(t, '')}" for t in ticker_list]
ticker_from_opt = {f"{t}  —  {name_map.get(t, '')}": t for t in ticker_list}

# ── Saved comp sets ────────────────────────────────────────────────────────────
COMP_SETS_PATH = DATA_DIR / "comp_sets.json"

def _load_saved() -> dict:
    try:
        if COMP_SETS_PATH.exists():
            return json.loads(COMP_SETS_PATH.read_text())
    except Exception:
        pass
    return {}

def _save_sets(sets: dict) -> None:
    try:
        COMP_SETS_PATH.write_text(json.dumps(sets, indent=2))
    except Exception as e:
        st.error(f"Could not save comp set: {e}")

saved_sets = _load_saved()

# ── Sidebar: load / save comp sets ────────────────────────────────────────────
with st.sidebar:
    st.markdown("---")
    st.markdown("**Saved Comp Sets**")
    if saved_sets:
        for set_name, meta in list(saved_sets.items()):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                n_cos = len(meta.get("tickers", []))
                if st.button(f"📂 {set_name} ({n_cos})", key=f"load_{set_name}",
                             use_container_width=True):
                    st.session_state["csb_selected_tickers"] = meta.get("tickers", [])
                    st.rerun()
            with col_b:
                if st.button("✕", key=f"del_{set_name}", help=f"Delete '{set_name}'"):
                    del saved_sets[set_name]
                    _save_sets(saved_sets)
                    st.rerun()
    else:
        st.caption("No saved comp sets yet.")

# ── Company selector ───────────────────────────────────────────────────────────
if "csb_selected_tickers" not in st.session_state:
    st.session_state["csb_selected_tickers"] = []

saved_tickers = st.session_state["csb_selected_tickers"]
default_opts  = [o for o in options if ticker_from_opt[o] in saved_tickers]

sc1, sc2 = st.columns([7, 3])
with sc1:
    selected_opts = st.multiselect(
        "Select 3–10 companies",
        options=options,
        default=default_opts,
        max_selections=10,
        key="csb_multiselect",
    )
with sc2:
    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
    save_name = st.text_input("Save as…", placeholder="e.g. Cloud Peers", key="csb_save_name",
                              label_visibility="collapsed")
    if st.button("💾 Save comp set", use_container_width=True):
        if save_name.strip() and len(selected_opts) >= 3:
            tickers_to_save = [ticker_from_opt[o] for o in selected_opts]
            saved_sets[save_name.strip()] = {
                "tickers": tickers_to_save,
                "created": datetime.utcnow().isoformat(),
            }
            _save_sets(saved_sets)
            st.success(f"Saved '{save_name.strip()}'")
        elif len(selected_opts) < 3:
            st.warning("Select at least 3 companies to save.")
        else:
            st.warning("Enter a name for this comp set.")

selected_tickers = [ticker_from_opt[o] for o in selected_opts]
st.session_state["csb_selected_tickers"] = selected_tickers

if len(selected_tickers) < 3:
    st.info("Select at least 3 companies to view the comp set.")
    st.stop()

df_sel = df_all[df_all["ticker"].isin(selected_tickers)].copy()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📋 Comps Table", "📈 Regression", "📊 Trading History"])

# ─── Tab 1: Comps Table ───────────────────────────────────────────────────────
with tab1:
    df_sel["rev_growth_pct"] = df_sel["ntm_revenue_growth"].mul(100)
    df_sel["ebitda_mgn_pct"] = df_sel["ebitda_margin"].mul(100)
    df_sel["gross_mgn_pct"]  = df_sel["gross_margin"].mul(100)
    df_sel["tev_bn"]         = df_sel["enterprise_value"].div(1e9)
    df_sel["chg_2w_pct"]     = df_sel["price_change_2w"].mul(100)
    df_sel["chg_2m_pct"]     = df_sel["price_change_2m"].mul(100)

    def _fmt(v, sfx="", d=1):
        return f"{v:.{d}f}{sfx}" if pd.notna(v) else "—"

    tbl_rows = []
    for _, row in df_sel.iterrows():
        tbl_rows.append({
            "Ticker":         row["ticker"],
            "Company":        (row.get("name") or "")[:32],
            "Segment":        row["seg_label"],
            "TEV ($B)":       _fmt(row["tev_bn"], "B"),
            "NTM EV/Rev":     _fmt(row["ntm_tev_rev"], "x"),
            "NTM EV/EBITDA":  _fmt(row["ntm_tev_ebitda"], "x"),
            "Rev Growth %":   _fmt(row["rev_growth_pct"], "%"),
            "EBITDA Mgn %":   _fmt(row["ebitda_mgn_pct"], "%"),
            "Gross Mgn %":    _fmt(row["gross_mgn_pct"], "%"),
            "2W Chg %":       _fmt(row["chg_2w_pct"], "%"),
            "2M Chg %":       _fmt(row["chg_2m_pct"], "%"),
        })

    # Median row
    med_row: dict = {"Ticker": "—", "Company": "Median", "Segment": "—"}
    for col_src, col_disp, sfx, d in [
        ("tev_bn", "TEV ($B)", "B", 1),
        ("ntm_tev_rev", "NTM EV/Rev", "x", 1),
        ("ntm_tev_ebitda", "NTM EV/EBITDA", "x", 1),
        ("rev_growth_pct", "Rev Growth %", "%", 1),
        ("ebitda_mgn_pct", "EBITDA Mgn %", "%", 1),
        ("gross_mgn_pct", "Gross Mgn %", "%", 1),
        ("chg_2w_pct", "2W Chg %", "%", 1),
        ("chg_2m_pct", "2M Chg %", "%", 1),
    ]:
        med_v = df_sel[col_src].median()
        med_row[col_disp] = _fmt(med_v, sfx, d)

    tbl_rows.append(med_row)
    df_tbl = pd.DataFrame(tbl_rows)

    st.markdown('<div class="csb-card">', unsafe_allow_html=True)
    st.dataframe(df_tbl, use_container_width=True, hide_index=True, height=min(420, (len(tbl_rows)+1)*38))
    st.markdown('</div>', unsafe_allow_html=True)

# ─── Tab 2: Regression ────────────────────────────────────────────────────────
with tab2:
    rc1, rc2 = st.columns(2)
    with rc1:
        x_opt = st.selectbox("X axis", ["NTM EV/Revenue", "NTM EV/EBITDA"], key="csb_x")
    with rc2:
        y_opt = st.selectbox("Y axis", ["NTM Revenue Growth %", "EBITDA Margin %"],
                             key="csb_y")

    _x_map = {"NTM EV/Revenue": "NTM Rev x", "NTM EV/EBITDA": "NTM EBITDA x"}
    _y_map = {"NTM Revenue Growth %": "NTM Rev Growth",
              "EBITDA Margin %": "EBITDA Margin"}
    _y_sfx = {"NTM Revenue Growth %": "%", "EBITDA Margin %": "%"}

    df_scatter = build_scatter_df(df_sel.to_dict("records"))
    fig = build_regression_scatter(
        df_scatter, _x_map[x_opt], _y_map[y_opt],
        x_label=x_opt + " (x)",
        y_label=y_opt,
        height=520,
        x_suffix="x",
        y_suffix=_y_sfx[y_opt],
    )
    if fig:
        st.markdown('<div class="csb-card">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.caption("Not enough data for regression scatter.")

# ─── Tab 3: Trading History ───────────────────────────────────────────────────
with tab3:
    th1, th2 = st.columns([3, 7])
    with th1:
        hist_metric = st.selectbox(
            "Metric",
            ["NTM TEV/Revenue", "NTM TEV/EBITDA"],
            key="csb_hist_metric",
        )
    _HIST_COL = {"NTM TEV/Revenue": "ntm_tev_rev", "NTM TEV/EBITDA": "ntm_tev_ebitda"}
    hist_col = _HIST_COL[hist_metric]

    daily_records = _load_daily(730)
    if not daily_records:
        st.caption("No daily multiples history available.")
    else:
        df_dm = pd.DataFrame(daily_records)
        df_dm["_dt"] = pd.to_datetime(df_dm["date"], errors="coerce")
        df_dm = df_dm[df_dm["ticker"].isin(selected_tickers)].dropna(subset=["_dt", hist_col])

        if df_dm.empty:
            st.caption("No historical data for selected companies.")
        else:
            fig_ts = go.Figure()
            layout = plotly_layout(height=520)
            layout["hovermode"] = "x unified"
            layout["yaxis"]["ticksuffix"] = "x"
            layout["legend"] = dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=10, family=_FONT_FAM),
                bgcolor="rgba(0,0,0,0)",
            )
            layout["xaxis"]["showgrid"] = False
            layout["margin"].update({"r": 60, "t": 55})

            _COLORS = [
                "#3B82F6", "#16A34A", "#F59E0B", "#EF4444", "#8B5CF6",
                "#EC4899", "#06B6D4", "#F97316", "#84CC16", "#6366F1",
            ]

            for i, ticker in enumerate(selected_tickers):
                sub = df_dm[df_dm["ticker"] == ticker].sort_values("_dt")
                if sub.empty:
                    continue
                # 7-day rolling smoothing
                sub = sub.set_index("_dt")[hist_col].rolling(window=7, min_periods=2).mean().reset_index()
                sub.columns = ["_dt", hist_col]
                sub = sub.dropna()

                color = _COLORS[i % len(_COLORS)]
                d_strs = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in sub["_dt"]]
                fig_ts.add_trace(go.Scatter(
                    x=d_strs,
                    y=sub[hist_col].tolist(),
                    mode="lines",
                    name=ticker,
                    line=dict(color=color, width=2),
                    hovertemplate=f"{ticker}: %{{y:.1f}}x<extra></extra>",
                ))

            fig_ts.update_layout(**layout)

            st.markdown('<div class="csb-card">', unsafe_allow_html=True)
            st.plotly_chart(fig_ts, use_container_width=True, config={"displayModeBar": False})
            st.markdown('</div>', unsafe_allow_html=True)
