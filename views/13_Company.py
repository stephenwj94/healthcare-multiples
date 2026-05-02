"""
Company Profile — single-company drill-down.

Reads `?ticker=XXX` from query params (set by the comp-table ticker link)
and renders: logo + name header, KPI strip, multi-metric chart, fundamentals,
multiples vs segment median, operating metrics benchmark, and recent news.
"""

import sys
from datetime import datetime, timedelta, date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import render_sidebar
from components.logos import logo_url
from config.color_palette import (
    LIGHT_BADGE_STYLES, SEGMENT_SHORT, PLOTLY_BG, PLOTLY_GRID, PLOTLY_TEXT,
)
from config.company_registry import COMPANY_REGISTRY
from config.settings import DB_PATH
from fetcher.db_manager import DBManager
from components.news_filter import is_source_blocked

render_sidebar()

# ── Resolve ticker from query param or selectbox ──────────────────────────────
qp_ticker = st.query_params.get("ticker")
all_tickers = sorted([c["ticker"] for c in COMPANY_REGISTRY])
ticker_to_company = {c["ticker"]: c for c in COMPANY_REGISTRY}

if not qp_ticker or qp_ticker not in ticker_to_company:
    st.title("Company Profile")
    st.markdown(
        '<p style="color:#94A3B8;font-size:13px;margin-top:-8px;">'
        "Pick a company below — or click any ticker / company name in a "
        "comp table to land here directly."
        "</p>",
        unsafe_allow_html=True,
    )
    pick = st.selectbox(
        "Company",
        all_tickers,
        index=None,
        placeholder="Search by ticker (LLY, JNJ, ROG, ...)",
        format_func=lambda t: f"{t} — {ticker_to_company[t]['name']}",
    )
    if pick:
        st.query_params["ticker"] = pick
        st.rerun()
    st.stop()

company = ticker_to_company[qp_ticker]
ticker = company["ticker"]
yahoo_ticker = company["yahoo_ticker"]

# ── Fetch latest snapshot from DB ─────────────────────────────────────────────
db = DBManager(DB_PATH)
try:
    snap_rows = db.get_latest_snapshots()
    snapshot = next((r for r in snap_rows if r.get("ticker") == ticker), None)
    segment_peers = [r for r in snap_rows if r.get("segment") == company["segment"]]
except Exception:
    snapshot = None
    segment_peers = []

if not snapshot:
    st.error(
        f"No snapshot data for {ticker} yet — run `python -m fetcher.run_fetch {ticker}` "
        f"to populate the database."
    )
    st.stop()


# ── Header — logo + name + ticker + segment badge ─────────────────────────────
seg_short = SEGMENT_SHORT.get(company["segment"], company["segment"])
badge_bg, badge_fg = LIGHT_BADGE_STYLES.get(seg_short, ("#F3F4F6", "#374151"))
sub_seg_label = (company.get("sub_segment") or "").replace("_", " ").title()

logo_src = logo_url(ticker, size=128)
logo_html = (
    f'<img src="{logo_src}" width="56" height="56" '
    f'style="border-radius:8px;object-fit:contain;border:1px solid #E5E7EB;'
    f'background:#FFFFFF;padding:4px;flex-shrink:0;" '
    f'onerror="this.style.display=\'none\'" loading="lazy">'
    if logo_src else ""
)

st.markdown(
    f"""
<div style="position:relative;padding:24px 24px 24px 24px;margin:0 0 28px 0;
            background:linear-gradient(180deg, #FFFFFF 0%, #FBFAF6 100%);
            border:1px solid rgba(0,0,0,0.05);border-radius:12px;
            box-shadow:0 1px 2px rgba(0,0,0,0.03);overflow:hidden;">
  <div style="position:absolute;top:0;left:0;right:0;height:2px;
              background:linear-gradient(90deg, {badge_fg} 0%, rgba(124,58,237,0.6) 50%, transparent 100%);"></div>
  <div style="display:flex;align-items:center;gap:18px;">
    {logo_html}
    <div style="flex:1;">
      <div style="font-size:26px;font-weight:700;color:#0F172A;line-height:1.15;
                  letter-spacing:-0.02em;">
        {snapshot.get("name", company["name"])}
      </div>
      <div style="display:flex;align-items:center;gap:10px;margin-top:8px;flex-wrap:wrap;">
        <span style="font-size:14px;font-weight:700;color:#1D4ED8;
                     font-family:'Roboto Mono',ui-monospace,monospace;
                     letter-spacing:0.02em;">{ticker}</span>
        <span style="color:#D1D5DB;">&bull;</span>
        <span style="background:{badge_bg};color:{badge_fg};
                     padding:3px 9px;border-radius:4px;font-size:11px;
                     font-weight:600;letter-spacing:0.02em;">{seg_short}</span>
        {f'<span style="font-size:12px;color:#6B7280;">{sub_seg_label}</span>' if sub_seg_label else ""}
        <span style="font-size:12px;color:#9CA3AF;">{company.get("country") or ""}</span>
      </div>
    </div>
  </div>
  <div style="position:absolute;bottom:0;left:24px;right:24px;height:1px;
              background:linear-gradient(90deg, rgba(0,0,0,0.06) 0%, rgba(0,0,0,0.02) 60%, transparent 100%);"></div>
</div>
""",
    unsafe_allow_html=True,
)

# ── KPI strip — grouped into "Valuation" + "Growth & Quality" clusters ────────
def _fmt_dollars_b(x):
    if x is None:
        return "—"
    return f"${x/1e9:,.1f}B" if abs(x) >= 1e9 else f"${x/1e6:,.0f}M"


def _fmt_mult(x):
    if x is None or x <= 0 or x > 75:
        return "N/M"
    return f"{x:.1f}x"


def _fmt_pct(x):
    if x is None:
        return "—"
    return f"{x*100:.1f}%"


def _cluster_label(text: str):
    st.markdown(
        f"<div style='font-size:10px;font-weight:700;text-transform:uppercase;"
        f"letter-spacing:0.12em;color:#64748B;margin:0 0 8px 2px;'>"
        f"{text}</div>",
        unsafe_allow_html=True,
    )


_cluster_label("Valuation")
v1, v2, v3 = st.columns(3)
v1.metric("TEV",            _fmt_dollars_b(snapshot.get("enterprise_value")))
v2.metric("NTM EV/Rev",     _fmt_mult(snapshot.get("ntm_tev_rev")))
v3.metric("NTM EV/EBITDA",  _fmt_mult(snapshot.get("ntm_tev_ebitda")))

st.markdown("<div style='height:14px;'></div>", unsafe_allow_html=True)

_cluster_label("Growth & Quality")
g1, g2, g3 = st.columns(3)
g1.metric("Market Cap",     _fmt_dollars_b(snapshot.get("market_cap")))
g2.metric("NTM Rev Growth", _fmt_pct(snapshot.get("ntm_revenue_growth")))
g3.metric("NTM EBITDA Margin",  _fmt_pct(snapshot.get("ebitda_margin")))

st.markdown(
    '<div style="font-size:10px;color:#9CA3AF;margin-top:4px;margin-bottom:16px;">'
    '<span style="color:#64748B;font-weight:500;">Source:</span> FactSet</div>',
    unsafe_allow_html=True,
)


# ── Multi-metric chart with time period selector ─────────────────────────────
st.markdown("#### Metrics Over Time")

_period_options = {"1W": "5d", "1M": "1mo", "3M": "3mo", "6M": "6mo", "YTD": "ytd", "1Y": "1y", "3Y": "3y", "5Y": "5y"}
_price_cols = st.columns(len(_period_options))
_selected_period = st.session_state.get("_cp_period", "1Y")
for i, (label, _) in enumerate(_period_options.items()):
    if _price_cols[i].button(label, key=f"cp_btn_{label}",
                              use_container_width=True,
                              type="primary" if label == _selected_period else "secondary"):
        st.session_state["_cp_period"] = label
        _selected_period = label
        st.rerun()

_yf_period = _period_options[_selected_period]

# Metric selector
_CHART_METRICS = [
    "Share Price",
    "NTM Revenue Growth %",
    "NTM EBITDA Margin %",
    "NTM EV/Revenue",
    "NTM EV/EBITDA",
]
_default_metrics = ["Share Price"]
_chart_selected = st.multiselect(
    "Metrics to display",
    _CHART_METRICS,
    default=st.session_state.get("_cp_chart_metrics", _default_metrics),
    key="_cp_chart_metrics_select",
)
if _chart_selected:
    st.session_state["_cp_chart_metrics"] = _chart_selected
else:
    _chart_selected = _default_metrics


@st.cache_data(ttl=60 * 30)  # 30-min cache
def _fetch_price_history(yt: str, period: str = "1y") -> pd.DataFrame:
    try:
        hist = yf.Ticker(yt).history(period=period, auto_adjust=True)
        return hist if hist is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60 * 30)
def _fetch_daily_multiples_for_ticker(tkr: str, days_back: int = 1825) -> pd.DataFrame:
    """Fetch daily multiples for a single ticker from the DB."""
    try:
        _db = DBManager(DB_PATH)
        rows = _db.get_daily_multiples(days_back=days_back)
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()
        df = df[df["ticker"] == tkr].copy()
        if df.empty:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        return df
    except Exception:
        return pd.DataFrame()


# Map period label to approx days for DB query
_period_to_days = {"1W": 10, "1M": 35, "3M": 100, "6M": 190, "YTD": 370, "1Y": 370, "3Y": 1100, "5Y": 1830}
_days_back = _period_to_days.get(_selected_period, 370)

hist = _fetch_price_history(yahoo_ticker, _yf_period)
dm_df = _fetch_daily_multiples_for_ticker(ticker, _days_back)

# Determine what data we have
_has_price = not hist.empty and "Share Price" in _chart_selected
_has_dm = not dm_df.empty
_non_price_metrics = [m for m in _chart_selected if m != "Share Price"]
_has_secondary = bool(_non_price_metrics)

if not _chart_selected:
    st.info("Select at least one metric to display.")
elif not _has_price and not _has_dm and _non_price_metrics:
    st.info("No data available for the selected metrics and time period.")
else:
    # Build the chart
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Color palette for traces
    _trace_colors = {
        "Share Price": "#1D4ED8",
        "NTM Revenue Growth %": "#16A34A",
        "NTM EBITDA Margin %": "#D97706",
        "NTM EV/Revenue": "#7C3AED",
        "NTM EV/EBITDA": "#DC2626",
    }

    # Map metric names to daily_multiples columns
    _metric_to_col = {
        "NTM Revenue Growth %": "ntm_revenue_growth",
        "NTM EBITDA Margin %": "ebitda_margin",
        "NTM EV/Revenue": "ntm_tev_rev",
        "NTM EV/EBITDA": "ntm_tev_ebitda",
    }

    if _has_price:
        fig.add_trace(
            go.Scatter(
                x=hist.index, y=hist["Close"],
                line=dict(color=_trace_colors["Share Price"], width=2),
                hovertemplate="<b>%{x|%b %d, %Y}</b><br>$%{y:.2f}<extra>Share Price</extra>",
                name="Share Price",
            ),
            secondary_y=False,
        )

    # Add non-price metrics from daily_multiples
    for metric_name in _non_price_metrics:
        col = _metric_to_col.get(metric_name)
        if col and _has_dm and col in dm_df.columns:
            series = dm_df.dropna(subset=[col])
            if series.empty:
                continue
            y_vals = series[col].copy()
            # Convert fractional values to percentage for growth/margin
            if "%" in metric_name:
                y_vals = y_vals * 100
                hover_suffix = "%"
                hover_fmt = ",.1f"
            else:
                hover_suffix = "x"
                hover_fmt = ",.1f"
            fig.add_trace(
                go.Scatter(
                    x=series["date"], y=y_vals,
                    line=dict(color=_trace_colors.get(metric_name, "#999"), width=2),
                    hovertemplate=(
                        f"<b>%{{x|%b %d, %Y}}</b><br>"
                        f"%{{y:{hover_fmt}}}{hover_suffix}"
                        f"<extra>{metric_name}</extra>"
                    ),
                    name=metric_name,
                ),
                secondary_y=True,
            )

    # Layout
    _show_legend = len(_chart_selected) > 1
    fig.update_layout(
        height=360,
        margin=dict(l=0, r=0, t=10, b=10),
        plot_bgcolor=PLOTLY_BG,
        paper_bgcolor=PLOTLY_BG,
        showlegend=_show_legend,
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
            font=dict(size=11),
        ),
        xaxis=dict(showgrid=False, color=PLOTLY_TEXT),
        font=dict(family="DM Sans, sans-serif", size=12, color=PLOTLY_TEXT),
    )

    # Left y-axis (price)
    if _has_price:
        fig.update_yaxes(
            gridcolor=PLOTLY_GRID, color=PLOTLY_TEXT,
            tickformat=",.0f", tickprefix="$",
            secondary_y=False,
            title_text="Share Price" if _has_secondary else None,
        )
    else:
        fig.update_yaxes(showticklabels=False, showgrid=False, secondary_y=False)

    # Right y-axis (multiples / percentages)
    if _has_secondary:
        _pct_metrics = [m for m in _non_price_metrics if "%" in m]
        _mult_metrics = [m for m in _non_price_metrics if "%" not in m]
        if _pct_metrics and not _mult_metrics:
            _right_suffix = "%"
            _right_fmt = ",.1f"
        elif _mult_metrics and not _pct_metrics:
            _right_suffix = "x"
            _right_fmt = ",.1f"
        else:
            _right_suffix = ""
            _right_fmt = ",.1f"
        fig.update_yaxes(
            gridcolor=PLOTLY_GRID, color=PLOTLY_TEXT,
            tickformat=_right_fmt,
            ticksuffix=_right_suffix,
            secondary_y=True,
            showgrid=not _has_price,
        )
    else:
        fig.update_yaxes(showticklabels=False, showgrid=False, secondary_y=True)

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown(
    '<div style="font-size:10px;color:#9CA3AF;margin-bottom:16px;">'
    '<span style="color:#64748B;font-weight:500;">Source:</span> '
    'Yahoo Finance (share price) · FactSet (multiples &amp; operating metrics)</div>',
    unsafe_allow_html=True,
)


# ── Multiples vs segment median ───────────────────────────────────────────────
st.markdown("#### Multiples — Company vs. Peer Median")


def _seg_median(rows, key: str):
    vals = [r.get(key) for r in rows if r.get(key) is not None and r.get(key) > 0 and r.get(key) <= 75]
    return sorted(vals)[len(vals)//2] if vals else None


def _seg_median_pct(rows, key: str):
    """Median for percentage-type metrics (no 0-75 filter)."""
    vals = [r.get(key) for r in rows if r.get(key) is not None]
    return sorted(vals)[len(vals)//2] if vals else None


# ── Customizable peer set via expander ────────────────────────────────────────
_peer_tickers_in_segment = sorted(
    [(r.get("ticker"), r.get("name", r.get("ticker"))) for r in segment_peers],
    key=lambda x: x[1],
)

# Initialize peer selection in session state
_peer_state_key = f"_peer_sel_{ticker}"
if _peer_state_key not in st.session_state:
    st.session_state[_peer_state_key] = [t for t, _ in _peer_tickers_in_segment]

with st.expander(f"Customize peer group ({len(_peer_tickers_in_segment)} {seg_short} companies)", expanded=False):
    _sel_all_col, _clear_col = st.columns(2)
    if _sel_all_col.button("Select All", key="_peer_sel_all"):
        st.session_state[_peer_state_key] = [t for t, _ in _peer_tickers_in_segment]
        st.rerun()
    if _clear_col.button("Clear All", key="_peer_clr_all"):
        st.session_state[_peer_state_key] = []
        st.rerun()

    _peer_selected = []
    _cols_per_row = 3
    for row_start in range(0, len(_peer_tickers_in_segment), _cols_per_row):
        row_items = _peer_tickers_in_segment[row_start:row_start + _cols_per_row]
        cols = st.columns(_cols_per_row)
        for j, (ptk, pname) in enumerate(row_items):
            checked = ptk in st.session_state[_peer_state_key]
            if cols[j].checkbox(
                f"{ptk} — {pname}",
                value=checked,
                key=f"_peer_cb_{ticker}_{ptk}",
            ):
                _peer_selected.append(ptk)
    st.session_state[_peer_state_key] = _peer_selected

# Filter peers based on selection
_custom_peers = [r for r in segment_peers if r.get("ticker") in st.session_state.get(_peer_state_key, [])]
peer_count = len(_custom_peers)

mult_rows = [
    ("NTM EV/Rev",     "ntm_tev_rev"),
    ("NTM EV/EBITDA",  "ntm_tev_ebitda"),
    ("NTM EV/GP",      "ntm_tev_gp"),
    ("LTM EV/Rev",     "ltm_tev_rev"),
    ("LTM EV/EBITDA",  "ltm_tev_ebitda"),
]


def _seg_quartile(rows, key: str, q: float):
    vals = sorted([r.get(key) for r in rows
                   if r.get(key) is not None and r.get(key) > 0 and r.get(key) <= 75])
    if not vals:
        return None
    idx = max(0, min(len(vals) - 1, int(q * (len(vals) - 1))))
    return vals[idx]


_logo_for_header = logo_url(ticker, size=64)
_logo_cell = (
    f'<img src="{_logo_for_header}" width="20" height="20" '
    f'style="border-radius:4px;object-fit:contain;border:1px solid #E5E7EB;'
    f'background:#FFFFFF;padding:2px;vertical-align:middle;margin-right:8px;" '
    f'onerror="this.style.display=\'none\'" loading="lazy">'
    if _logo_for_header else ""
)

rows_html = []
for label, key in mult_rows:
    co_val = snapshot.get(key)
    med_val = _seg_median(_custom_peers, key)
    q25 = _seg_quartile(_custom_peers, key, 0.25)
    q75 = _seg_quartile(_custom_peers, key, 0.75)

    # Highlight extreme values (above 75th pct or below 25th pct)
    co_style = ""
    if co_val and co_val > 0 and co_val <= 75:
        if q75 is not None and co_val >= q75:
            co_style = f"background:{badge_bg};color:{badge_fg};font-weight:700;"
        elif q25 is not None and co_val <= q25:
            co_style = f"background:{badge_bg};color:{badge_fg};font-weight:700;"

    if med_val and co_val and med_val > 0 and co_val > 0:
        delta_pct = (co_val / med_val - 1) * 100
        if delta_pct >= 0:
            delta_html = (
                f'<span style="color:#047857;background:rgba(16,185,129,0.10);'
                f'padding:2px 8px;border-radius:4px;font-weight:600;font-size:12px;">'
                f'+{delta_pct:.0f}%</span>'
            )
        else:
            delta_html = (
                f'<span style="color:#B91C1C;background:rgba(239,68,68,0.10);'
                f'padding:2px 8px;border-radius:4px;font-weight:600;font-size:12px;">'
                f'{delta_pct:.0f}%</span>'
            )
    else:
        delta_html = '<span style="color:#9CA3AF;">—</span>'

    rows_html.append(
        f'<tr>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'font-weight:500;color:#374151;">{label}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'text-align:right;font-variant-numeric:tabular-nums;'
        f'border-radius:4px;{co_style}">{_fmt_mult(co_val)}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'text-align:right;color:#6B7280;font-variant-numeric:tabular-nums;">'
        f'{_fmt_mult(med_val)}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'text-align:right;">{delta_html}</td>'
        f'</tr>'
    )

_peer_label = "Peer Median" if peer_count < len(segment_peers) else f"{seg_short} Median"

st.markdown(
    f'<div style="border:1px solid rgba(0,0,0,0.06);border-radius:10px;'
    f'overflow:hidden;background:#FFFFFF;'
    f'box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
    f'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
    f'<thead><tr style="background:#F9FAFB;">'
    f'<th style="text-align:left;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">Multiple</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">{_logo_cell}{ticker}</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">{_peer_label}</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">vs. Median</th>'
    f'</tr></thead>'
    f'<tbody>{"".join(rows_html)}</tbody>'
    f'</table></div>',
    unsafe_allow_html=True,
)
st.caption(
    f"Median computed across {peer_count} peer companies. "
    f"Highlighted cells fall above the 75th or below the 25th percentile."
)
st.markdown(
    '<div style="font-size:10px;color:#9CA3AF;margin-bottom:16px;">'
    '<span style="color:#64748B;font-weight:500;">Source:</span> FactSet</div>',
    unsafe_allow_html=True,
)


# ── Operating Metrics Benchmark ──────────────────────────────────────────────
st.markdown("#### Operating Metrics — Company vs. Peer Median")

_op_metrics = [
    ("NTM Revenue Growth",  "ntm_revenue_growth"),
    ("NTM EBITDA Margin",   "ebitda_margin"),
    ("Gross Margin",        "gross_margin"),
]

_op_rows_html = []
for _op_label, _op_key in _op_metrics:
    _co_val = snapshot.get(_op_key)
    _med_val = _seg_median_pct(_custom_peers, _op_key)

    _co_display = _fmt_pct(_co_val)
    _med_display = _fmt_pct(_med_val)

    if _co_val is not None and _med_val is not None and _med_val != 0:
        _delta_pp = (_co_val - _med_val) * 100  # percentage point difference
        if _delta_pp >= 0:
            _op_delta_html = (
                f'<span style="color:#047857;background:rgba(16,185,129,0.10);'
                f'padding:2px 8px;border-radius:4px;font-weight:600;font-size:12px;">'
                f'+{_delta_pp:.1f}pp</span>'
            )
        else:
            _op_delta_html = (
                f'<span style="color:#B91C1C;background:rgba(239,68,68,0.10);'
                f'padding:2px 8px;border-radius:4px;font-weight:600;font-size:12px;">'
                f'{_delta_pp:.1f}pp</span>'
            )
    else:
        _op_delta_html = '<span style="color:#9CA3AF;">—</span>'

    _co_color = "#111827"
    if _co_val is not None and "Growth" in _op_label:
        _co_color = "#16A34A" if _co_val > 0 else "#DC2626"

    _op_rows_html.append(
        f'<tr>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'font-weight:500;color:#374151;">{_op_label}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'text-align:right;font-variant-numeric:tabular-nums;font-weight:600;'
        f'color:{_co_color};">{_co_display}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'text-align:right;color:#6B7280;font-variant-numeric:tabular-nums;">'
        f'{_med_display}</td>'
        f'<td style="padding:10px 14px;border-bottom:1px solid #F3F4F6;'
        f'text-align:right;">{_op_delta_html}</td>'
        f'</tr>'
    )

st.markdown(
    f'<div style="border:1px solid rgba(0,0,0,0.06);border-radius:10px;'
    f'overflow:hidden;background:#FFFFFF;'
    f'box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
    f'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
    f'<thead><tr style="background:#F9FAFB;">'
    f'<th style="text-align:left;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">Metric</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">{_logo_cell}{ticker}</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">{_peer_label}</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">vs. Median</th>'
    f'</tr></thead>'
    f'<tbody>{"".join(_op_rows_html)}</tbody>'
    f'</table></div>',
    unsafe_allow_html=True,
)
st.caption(
    f"Difference shown in percentage points (pp) relative to peer median ({peer_count} companies)."
)
st.markdown(
    '<div style="font-size:10px;color:#9CA3AF;margin-bottom:16px;">'
    '<span style="color:#64748B;font-weight:500;">Source:</span> FactSet</div>',
    unsafe_allow_html=True,
)


# ── Income Statement Summary ──────────────────────────────────────────────────
st.markdown("#### Income Statement Summary")

_is_rows = [
    ("Revenue (LTM)", snapshot.get("ltm_revenue")),
    ("Gross Profit (LTM)", snapshot.get("ltm_gross_profit")),
    ("EBITDA (LTM)", snapshot.get("ltm_ebitda")),
    ("Revenue (NTM Est.)", snapshot.get("ntm_revenue")),
    ("EBITDA (NTM Est.)", snapshot.get("ntm_ebitda")),
]
_is_html_rows = ""
for _is_label, _is_val in _is_rows:
    _is_html_rows += (
        f'<tr>'
        f'<td style="padding:8px 14px;border-bottom:1px solid #F3F4F6;color:#374151;">'
        f'{_is_label}</td>'
        f'<td style="padding:8px 14px;border-bottom:1px solid #F3F4F6;text-align:right;'
        f'font-variant-numeric:tabular-nums;font-weight:600;color:#111827;">'
        f'{_fmt_dollars_b(_is_val)}</td>'
        f'</tr>'
    )

_margin_rows = [
    ("Gross Margin", snapshot.get("gross_margin")),
    ("NTM EBITDA Margin", snapshot.get("ebitda_margin")),
    ("NTM Revenue Growth", snapshot.get("ntm_revenue_growth")),
    ("3Y Revenue CAGR", snapshot.get("n3y_revenue_cagr")),
]
for _m_label, _m_val in _margin_rows:
    _m_display = _fmt_pct(_m_val)
    _m_color = "#111827"
    if _m_val is not None:
        if "Growth" in _m_label or "CAGR" in _m_label:
            _m_color = "#16A34A" if _m_val > 0 else "#DC2626"
    _is_html_rows += (
        f'<tr>'
        f'<td style="padding:8px 14px;border-bottom:1px solid #F3F4F6;color:#374151;">'
        f'{_m_label}</td>'
        f'<td style="padding:8px 14px;border-bottom:1px solid #F3F4F6;text-align:right;'
        f'font-weight:600;color:{_m_color};">{_m_display}</td>'
        f'</tr>'
    )

st.markdown(
    f'<div style="border:1px solid rgba(0,0,0,0.06);border-radius:10px;overflow:hidden;'
    f'background:#FFFFFF;box-shadow:0 1px 2px rgba(0,0,0,0.03);margin-bottom:8px;">'
    f'<table style="width:100%;border-collapse:collapse;font-size:13px;">'
    f'<thead><tr style="background:#F9FAFB;">'
    f'<th style="text-align:left;padding:10px 14px;font-size:11px;text-transform:uppercase;'
    f'letter-spacing:0.05em;color:#6B7280;border-bottom:1px solid #E5E7EB;">Metric</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;text-transform:uppercase;'
    f'letter-spacing:0.05em;color:#6B7280;border-bottom:1px solid #E5E7EB;">Value</th>'
    f'</tr></thead>'
    f'<tbody>{_is_html_rows}</tbody>'
    f'</table></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div style="font-size:10px;color:#9CA3AF;margin-bottom:16px;">'
    '<span style="color:#64748B;font-weight:500;">Source:</span> FactSet (fundamentals &amp; estimates)</div>',
    unsafe_allow_html=True,
)


# ── Broker Price Targets ─────────────────────────────────────────────────────
st.markdown("#### Analyst Price Targets")

@st.cache_data(ttl=60 * 60)
def _fetch_analyst_data(yt: str):
    try:
        t = yf.Ticker(yt)
        info = t.info or {}
        # Try to get individual broker upgrades/downgrades
        upgrades = None
        try:
            ud_df = t.upgrades_downgrades
            if ud_df is not None and not ud_df.empty:
                upgrades = ud_df.head(20).reset_index().to_dict("records")
        except Exception:
            pass
        return {
            "target_low": info.get("targetLowPrice"),
            "target_mean": info.get("targetMeanPrice"),
            "target_median": info.get("targetMedianPrice"),
            "target_high": info.get("targetHighPrice"),
            "current": info.get("currentPrice") or info.get("regularMarketPrice"),
            "recommendation": info.get("recommendationKey"),
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "upgrades_downgrades": upgrades,
        }
    except Exception:
        return {}

_analyst = _fetch_analyst_data(yahoo_ticker)
if _analyst and _analyst.get("target_mean"):
    _cur = _analyst.get("current") or snapshot.get("current_price")
    _low = _analyst.get("target_low")
    _mean = _analyst.get("target_mean")
    _med = _analyst.get("target_median")
    _high = _analyst.get("target_high")
    _n = _analyst.get("num_analysts")
    _rec = (_analyst.get("recommendation") or "").replace("_", " ").title()

    if _cur and _med:
        _upside = ((_med / _cur) - 1) * 100
        _upside_color = "#16A34A" if _upside >= 0 else "#DC2626"
        _upside_html = (
            f'<span style="font-size:20px;font-weight:700;color:{_upside_color};">'
            f'{"+" if _upside >= 0 else ""}{_upside:.1f}%</span>'
            f'<span style="font-size:12px;color:#6B7280;margin-left:6px;">to median target</span>'
        )
    else:
        _upside_html = ""

    # Visual range bar
    if _cur and _low and _high and _high > _low:
        _range = _high - _low
        _cur_pct = max(0, min(100, ((_cur - _low) / _range) * 100))
        _med_pct = max(0, min(100, ((_med - _low) / _range) * 100)) if _med else 50
        _range_bar = (
            f'<div style="position:relative;height:8px;background:linear-gradient(90deg, #FEE2E2 0%, #FEF3C7 50%, #DCFCE7 100%);'
            f'border-radius:4px;margin:16px 0 8px 0;">'
            f'<div style="position:absolute;top:-4px;left:{_cur_pct:.0f}%;transform:translateX(-50%);'
            f'width:16px;height:16px;background:#1D4ED8;border-radius:50%;border:2px solid white;'
            f'box-shadow:0 1px 3px rgba(0,0,0,0.2);"></div>'
            f'<div style="position:absolute;top:-3px;left:{_med_pct:.0f}%;transform:translateX(-50%);'
            f'width:2px;height:14px;background:#6B7280;"></div>'
            f'</div>'
            f'<div style="display:flex;justify-content:space-between;font-size:11px;color:#6B7280;">'
            f'<span>Low: ${_low:.0f}</span>'
            f'<span>Median: ${_med:.0f}</span>'
            f'<span>High: ${_high:.0f}</span>'
            f'</div>'
        )
    else:
        _range_bar = ""

    st.markdown(
        f'<div style="background:#FFFFFF;border:1px solid rgba(0,0,0,0.06);border-radius:10px;'
        f'padding:20px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;'
        f'margin-bottom:12px;">'
        f'<div>'
        f'<span style="font-size:14px;color:#374151;font-weight:500;">Current: </span>'
        f'<span style="font-size:20px;font-weight:700;color:#111827;">'
        f'${_cur:.2f}</span>'
        f'</div>'
        f'<div>{_upside_html}</div>'
        f'</div>'
        f'{_range_bar}'
        f'<div style="display:flex;gap:24px;margin-top:12px;font-size:12px;color:#6B7280;">'
        f'{"<span>Consensus: <b>" + _rec + "</b></span>" if _rec else ""}'
        f'{"<span>Analysts: <b>" + str(_n) + "</b></span>" if _n else ""}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Individual broker estimates (upgrades/downgrades) ─────────────────────
    _ud = _analyst.get("upgrades_downgrades")
    if _ud and len(_ud) > 0:
        st.markdown(
            "<div style='margin-top:16px;'>"
            "<span style='font-size:13px;font-weight:600;color:#374151;'>"
            "Recent Broker Actions</span></div>",
            unsafe_allow_html=True,
        )
        _broker_rows_html = []
        for _b in _ud[:15]:
            _b_firm = _b.get("Firm", _b.get("firm", ""))
            _b_grade = _b.get("ToGrade", _b.get("toGrade", ""))
            _b_from = _b.get("FromGrade", _b.get("fromGrade", ""))
            _b_action = _b.get("Action", _b.get("action", ""))
            _b_date_raw = _b.get("Date", _b.get("GradeDate", _b.get("date", "")))
            # Format date
            try:
                if hasattr(_b_date_raw, "strftime"):
                    _b_date_str = _b_date_raw.strftime("%b %d, %Y")
                else:
                    _b_date_str = pd.to_datetime(str(_b_date_raw)).strftime("%b %d, %Y")
            except Exception:
                _b_date_str = str(_b_date_raw)[:10] if _b_date_raw else ""

            # Color the action
            _action_color = "#6B7280"
            _action_lower = str(_b_action).lower()
            if "up" in _action_lower or "init" in _action_lower:
                _action_color = "#16A34A"
            elif "down" in _action_lower:
                _action_color = "#DC2626"

            _grade_display = _b_grade
            if _b_from and _b_from != _b_grade:
                _grade_display = f"{_b_from} &rarr; {_b_grade}"

            _broker_rows_html.append(
                f'<tr>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #F3F4F6;'
                f'color:#374151;font-size:12px;">{_b_date_str}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #F3F4F6;'
                f'font-weight:500;color:#111827;font-size:12px;">{_b_firm}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #F3F4F6;'
                f'color:{_action_color};font-weight:600;font-size:12px;">{_b_action}</td>'
                f'<td style="padding:6px 12px;border-bottom:1px solid #F3F4F6;'
                f'color:#374151;font-size:12px;">{_grade_display}</td>'
                f'</tr>'
            )

        st.markdown(
            f'<div style="border:1px solid rgba(0,0,0,0.06);border-radius:10px;'
            f'overflow:hidden;background:#FFFFFF;margin-top:8px;'
            f'box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
            f'<table style="width:100%;border-collapse:collapse;font-size:12px;">'
            f'<thead><tr style="background:#F9FAFB;">'
            f'<th style="text-align:left;padding:8px 12px;font-size:10px;'
            f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
            f'border-bottom:1px solid #E5E7EB;">Date</th>'
            f'<th style="text-align:left;padding:8px 12px;font-size:10px;'
            f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
            f'border-bottom:1px solid #E5E7EB;">Firm</th>'
            f'<th style="text-align:left;padding:8px 12px;font-size:10px;'
            f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
            f'border-bottom:1px solid #E5E7EB;">Action</th>'
            f'<th style="text-align:left;padding:8px 12px;font-size:10px;'
            f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
            f'border-bottom:1px solid #E5E7EB;">Rating</th>'
            f'</tr></thead>'
            f'<tbody>{"".join(_broker_rows_html)}</tbody>'
            f'</table></div>',
            unsafe_allow_html=True,
        )
    else:
        st.caption("Individual broker estimates not available. Showing aggregate consensus only.")

    st.markdown(
        '<div style="font-size:10px;color:#9CA3AF;margin-top:4px;margin-bottom:16px;">'
        '<span style="color:#64748B;font-weight:500;">Source:</span> Yahoo Finance (analyst consensus &amp; broker actions)</div>',
        unsafe_allow_html=True,
    )
else:
    st.caption("Analyst price target data not available for this ticker.")


# ── News (yfinance, fetched live) ─────────────────────────────────────────────
st.markdown("#### Recent News")
st.markdown(
    "<style>"
    ".company-news-item { padding:12px 14px; border-bottom:1px solid #F3F4F6; "
    "border-radius:6px; transition: background 0.15s ease; margin: 0 -10px; }"
    ".company-news-item:hover { background:#FAFAF7; }"
    ".company-news-item a { font-weight:500; color:#111827; "
    "text-decoration:none; font-size:14px; line-height:1.4; }"
    ".company-news-item a:hover { color:#1D4ED8; }"
    ".company-news-meta { color:#9CA3AF; font-size:11px; margin-top:4px; }"
    "</style>",
    unsafe_allow_html=True,
)


@st.cache_data(ttl=60 * 30)
def _fetch_news(yt: str) -> list[dict]:
    try:
        return yf.Ticker(yt).news or []
    except Exception:
        return []


news = _fetch_news(yahoo_ticker)
if not news:
    st.caption("No recent news returned by Yahoo Finance for this ticker.")
else:
    shown = 0
    for item in news:
        if shown >= 8:
            break
        # yfinance news items have nested "content" with title/pubDate/canonicalUrl/provider
        content = item.get("content") or item
        title = content.get("title") or item.get("title") or "(no title)"
        url = (
            (content.get("canonicalUrl") or {}).get("url")
            or (content.get("clickThroughUrl") or {}).get("url")
            or item.get("link")
            or "#"
        )
        pub_raw = content.get("pubDate") or content.get("displayTime") or ""
        try:
            pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
            pub_str = pub_dt.strftime("%b %d, %Y")
        except Exception:
            pub_str = ""
        provider = ((content.get("provider") or {}).get("displayName")
                    or item.get("publisher") or "")
        if is_source_blocked(provider):
            continue
        shown += 1
        st.markdown(
            f'<div class="company-news-item">'
            f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
            f'{title}</a>'
            f'<div class="company-news-meta">'
            f'{provider}{" · " if provider and pub_str else ""}{pub_str}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown(
    '<div style="font-size:10px;color:#9CA3AF;margin-top:4px;margin-bottom:16px;">'
    '<span style="color:#64748B;font-weight:500;">Source:</span> Yahoo Finance</div>',
    unsafe_allow_html=True,
)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f'<div style="font-size:10px;color:#9CA3AF;">'
    f'<span style="color:#64748B;font-weight:500;">Sources:</span> '
    f'FactSet (fundamentals, estimates, multiples) · Yahoo Finance (share prices, news, analyst targets) · '
    f'Snapshot date: {snapshot.get("snapshot_date","")}'
    f'</div>',
    unsafe_allow_html=True,
)
