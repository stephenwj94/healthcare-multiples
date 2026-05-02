"""
Overview — biggest movers across the healthcare universe.

Single yfinance fetch powers: stat cards, benchmark chart, and movers table.
Segment checkboxes at the top filter the entire page.
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import html as _html_lib
from pathlib import Path
from datetime import datetime
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from components.logos import logo_img_tag
from config.settings import DB_PATH, EXCEL_OVERRIDE_PATH, SEGMENT_DISPLAY
from config.color_palette import (
    SEGMENT_SHORT, SEG_COLOR_MAP, SEGMENT_COLORS,
    GREEN, RED, MUTED,
    PLOTLY_BG, PLOTLY_GRID, PLOTLY_TEXT,
)
from fetcher.db_manager import DBManager
from fetcher.excel_override import load_overrides, apply_overrides

# ── Page setup ────────────────────────────────────────────────────────────────
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

/* Hide default details triangle — use › text arrow instead */
details summary { list-style: none; }
details summary::-webkit-details-marker { display: none; }

/* Stat cards */
.wl-stat-grid { display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap; }
.wl-stat-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 20px 24px;
    min-width: 150px;
    flex: 1;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
}
.wl-stat-label {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #6B7280; margin-bottom: 8px;
}
.wl-stat-value { font-size: 30px; font-weight: 800; color: #111827; line-height: 1.2; }
.wl-stat-sub { font-size: 13px; color: #9CA3AF; margin-top: 4px; }

/* Combined table */
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
    font-size: 13px;
    font-variant-numeric: tabular-nums;
    font-family: 'DM Sans', sans-serif;
}
.comb-tbl thead th {
    font-size: 10px; font-weight: 700; color: #6B7280;
    text-transform: uppercase; letter-spacing: 0.05em;
    padding: 10px 12px; border-bottom: 2px solid #E5E7EB;
    background: #F9FAFB; white-space: nowrap;
}
.comb-tbl tbody td {
    padding: 7px 12px; font-size: 13px; border-bottom: 1px solid #F3F4F6;
    color: #374151; white-space: nowrap; vertical-align: middle;
}
.comb-tbl tbody tr:nth-child(odd) td  { background: #FFFFFF; }
.comb-tbl tbody tr:nth-child(even) td { background: #FAFBFD; }
.comb-tbl tbody tr:hover td           { background: #F0F4FF !important; }

@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .wl-stat-grid { gap: 8px; }
    .wl-stat-card { padding: 16px 18px; min-width: 120px; }
    .wl-stat-value { font-size: 24px; }
}
</style>
""", unsafe_allow_html=True)

render_sidebar()

# ── Load fundamental data ─────────────────────────────────────────────────────
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

# Date context
raw_dates = [d.get("snapshot_date") for d in all_data if d.get("snapshot_date")]
as_of = (max(pd.Timestamp(str(d)[:10]) for d in raw_dates)
         if raw_dates else pd.Timestamp.today().normalize())
date_str = as_of.strftime("%B %d, %Y")

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="background:#F0F4FF;border-radius:12px;padding:24px 32px;'
    f'margin-bottom:16px;border:1px solid #DBEAFE;border-left:4px solid #3B82F6;">'
    f'<div style="font-size:28px;font-weight:800;color:#111827;margin-bottom:4px;">'
    f'Overview</div>'
    f'<div style="font-size:14px;color:#6B7280;font-weight:500;">'
    f'Healthcare universe performance &amp; biggest movers'
    f'&nbsp;&nbsp;&middot;&nbsp;&nbsp;'
    f'<span style="color:#9CA3AF;">Data as of {date_str}</span>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ── Segment filter checkboxes (top of page, filters everything) ──────────────
seg_keys = list(SEGMENT_DISPLAY.keys())
seg_labels = {k: SEGMENT_SHORT.get(k, v) for k, v in SEGMENT_DISPLAY.items()}
# Shorter labels for checkbox pills (fit in equal-width columns)
_CB_LABELS = {
    "pharma":          "Pharma",
    "consumer_health": "Consumer",
    "medtech":         "MedTech",
    "life_sci_tools":  "LST/Dx",
    "services":        "Asset-Light",
    "cdmo":            "Asset-Heavy",
    "health_tech":     "Health Tech",
}

# Segment icons (emoji after the segment name)
_SEG_ICONS = {
    "pharma":          "💊",
    "consumer_health": "🛒",
    "medtech":         "🩺",
    "life_sci_tools":  "🔬",
    "services":        "🏥",
    "cdmo":            "⚗️",
    "health_tech":     "💻",
}

def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# CSS: style each checkbox container as a colored pill box with proper alignment
_pill_css = "<style>\n"
# Ensure all columns are equal width, no wrapping, vertically centered
_pill_css += (
    '/* Equal-width segment columns */\n'
    'div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {\n'
    '  flex: 1 1 0 !important; min-width: 0 !important;\n'
    '}\n'
    '/* Vertically center checkbox label with the box, prevent wrapping */\n'
    'div[data-testid="stCheckbox"] label {\n'
    '  display: flex !important; align-items: center !important;\n'
    '  white-space: nowrap !important;\n'
    '}\n'
    'div[data-testid="stCheckbox"] label p {\n'
    '  margin: 0 !important; line-height: 1 !important;\n'
    '  white-space: nowrap !important; font-size: 14px !important;\n'
    '}\n'
)
for seg_key in seg_keys:
    color = SEGMENT_COLORS.get(seg_key, "#6B7280")
    bg = _hex_to_rgba(color, 0.08)
    border = _hex_to_rgba(color, 0.35)
    cb_label = _CB_LABELS.get(seg_key, seg_labels[seg_key])
    aria = f"{cb_label} {_SEG_ICONS.get(seg_key, '')}"
    # Checked state: colored pill
    _pill_css += (
        f'/* {cb_label} pill — checked */\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:checked) {{\n'
        f'  background: {bg}; border: 1.5px solid {border}; border-radius: 10px;\n'
        f'  padding: 8px 12px; transition: all 0.15s ease;\n'
        f'}}\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:checked) label p {{\n'
        f'  color: {color} !important; font-weight: 600 !important; font-size: 14px !important;\n'
        f'}}\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:checked):hover {{\n'
        f'  background: {_hex_to_rgba(color, 0.14)}; border-color: {_hex_to_rgba(color, 0.5)};\n'
        f'  transform: translateY(-1px); box-shadow: 0 2px 6px {_hex_to_rgba(color, 0.12)};\n'
        f'}}\n'
    )
    # Unchecked state: gray pill
    _pill_css += (
        f'/* {cb_label} pill — unchecked */\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:not(:checked)) {{\n'
        f'  background: #F3F4F6; border: 1.5px solid #D1D5DB; border-radius: 10px;\n'
        f'  padding: 8px 12px; transition: all 0.15s ease; opacity: 0.7;\n'
        f'}}\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:not(:checked)) label p {{\n'
        f'  color: #9CA3AF !important; font-weight: 500 !important; font-size: 14px !important;\n'
        f'}}\n'
    )
_pill_css += "</style>"
st.markdown(_pill_css, unsafe_allow_html=True)

# Segment columns (equal) + narrow period column
_n_seg = len(seg_keys)
_col_spec = [1] * _n_seg + [0.7]  # period column narrower
_all_cols = st.columns(_col_spec)

selected_segments = set()
for i, seg_key in enumerate(seg_keys):
    cb_label = _CB_LABELS.get(seg_key, seg_labels[seg_key])
    icon = _SEG_ICONS.get(seg_key, "")
    with _all_cols[i]:
        checked = st.checkbox(
            f"{cb_label} {icon}", value=True, key=f"ov_seg_{seg_key}",
        )
        if checked:
            selected_segments.add(seg_key)

# Time period selector in the last column
_PERIOD_OPTIONS = ["1W", "1M", "3M", "6M", "12M", "YTD", "3Y", "5Y"]
_PERIOD_LABELS = {
    "1W": "Last Week", "1M": "Last Month", "3M": "Last 3 Months",
    "6M": "Last 6 Months", "12M": "Last 12 Months", "YTD": "Year to Date",
    "3Y": "Last 3 Years", "5Y": "Last 5 Years",
}

with _all_cols[-1]:
    selected_period = st.selectbox(
        "Period", _PERIOD_OPTIONS, index=0,
        key="wl_period_select",
    )
period_label = _PERIOD_LABELS[selected_period]

# Filter data by selected segments
filtered_data = [d for d in all_data if d.get("segment") in selected_segments]
if not filtered_data:
    st.warning("No segments selected. Select at least one segment above.")
    st.stop()

# Full universe count (all segments)
total_universe = len(all_data)


# ── yfinance price fetch ─────────────────────────────────────────────────────
def _period_start(period, ref_date):
    ref = pd.Timestamp(ref_date)
    if period == "1W":  return ref - pd.Timedelta(weeks=1)
    if period == "1M":  return ref - pd.DateOffset(months=1)
    if period == "3M":  return ref - pd.DateOffset(months=3)
    if period == "6M":  return ref - pd.DateOffset(months=6)
    if period == "12M": return ref - pd.DateOffset(months=12)
    if period == "YTD": return pd.Timestamp(f"{ref.year - 1}-12-31")
    if period == "3Y":  return ref - pd.DateOffset(years=3)
    if period == "5Y":  return ref - pd.DateOffset(years=5)
    return ref - pd.Timedelta(weeks=1)


def _chart_lookback_months(period):
    """How many months of chart data to show for the segment performance chart."""
    return {"1W": 1, "1M": 3, "3M": 6, "6M": 12, "12M": 12,
            "YTD": 12, "3Y": 36, "5Y": 60}.get(period, 12)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_all_prices(tickers_tuple, months_back):
    """Batch-download prices from yfinance."""
    import yfinance as yf
    tickers = list(tickers_tuple)
    start = (pd.Timestamp.today() - pd.DateOffset(months=months_back)).strftime("%Y-%m-%d")
    try:
        raw = yf.download(tickers, start=start, auto_adjust=True,
                          progress=False, threads=True)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            if "Close" in raw.columns.get_level_values(0):
                close = raw["Close"].copy()
            else:
                return pd.DataFrame()
        else:
            # Single ticker or flat columns
            if "Close" in raw.columns:
                close = raw[["Close"]].copy()
                if len(tickers) == 1:
                    close.columns = [tickers[0]]
            else:
                close = raw.copy()
        close.index = pd.to_datetime(close.index)
        if close.index.tz is not None:
            close.index = close.index.tz_localize(None)
        return close
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_index_prices(months_back):
    """Download S&P 500 and NASDAQ index closes."""
    import yfinance as yf
    start = (pd.Timestamp.today() - pd.DateOffset(months=months_back)).strftime("%Y-%m-%d")
    results = {}
    for name, sym in [("S&P 500", "^GSPC"), ("NASDAQ", "^IXIC")]:
        try:
            hist = yf.Ticker(sym).history(start=start, auto_adjust=True)
            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)
            results[name] = hist["Close"] if not hist.empty else None
        except Exception:
            results[name] = None
    return results


def _compute_returns(close_df, ref_date, period, ticker_list=None):
    """Returns Series(ticker -> pct_return) for the given period.

    If ticker_list is provided, only includes those tickers (but still returns
    data for all that have prices — never drops tickers that exist in close_df).
    """
    if close_df.empty:
        return pd.Series(dtype=float)
    ref = pd.Timestamp(ref_date)
    prior_idx = close_df.index[close_df.index <= ref]
    if prior_idx.empty:
        return pd.Series(dtype=float)
    cur = close_df.loc[prior_idx[-1]].dropna()
    start = _period_start(period, ref)
    past_idx = close_df.index[close_df.index <= start]
    if past_idx.empty:
        return pd.Series(dtype=float)
    past = close_df.loc[past_idx[-1]].dropna()
    common = cur.index.intersection(past.index)
    if common.empty:
        return pd.Series(dtype=float)
    if ticker_list is not None:
        common = common.intersection(pd.Index(ticker_list))
        if common.empty:
            return pd.Series(dtype=float)
    past_safe = past[common].replace(0, np.nan)
    ret = ((cur[common] / past_safe) - 1) * 100
    return ret.dropna()


# ── Fetch prices ──────────────────────────────────────────────────────────────
# Always fetch ALL tickers (full universe) so segment filtering doesn't re-fetch
all_tickers = sorted({d.get("ticker") for d in all_data if d.get("ticker")})
# Filtered tickers for the selected segments
filtered_tickers = sorted({d.get("ticker") for d in filtered_data if d.get("ticker")})

# Determine how much history we need
months_needed = max(
    _chart_lookback_months(selected_period) + 2,  # chart needs this
    {"3Y": 38, "5Y": 62}.get(selected_period, 14),  # returns need this
)

with st.spinner("Loading price data from Yahoo Finance..."):
    close_df = _fetch_all_prices(tuple(all_tickers), months_needed)
    index_prices = _fetch_index_prices(months_needed)

# Compute returns only for filtered tickers
returns = _compute_returns(close_df, as_of, selected_period, filtered_tickers)

# ── Stat cards ────────────────────────────────────────────────────────────────
ticker_to_co = {d["ticker"]: d for d in all_data if d.get("ticker")}

# Universe count = total filtered companies (not just those with return data)
universe_count = len(filtered_data)

cards = '<div class="wl-stat-grid">'

# Universe card with expandable company list
from config.company_registry import COMPANY_REGISTRY
filtered_companies = sorted(
    [c for c in COMPANY_REGISTRY if c["segment"] in selected_segments],
    key=lambda c: c["name"],
)

# Build company list as a clean flowing list (dot + name · ticker + logo)
_comp_items = ""
for c in filtered_companies:
    _seg_color = SEGMENT_COLORS.get(c["segment"], "#6B7280")
    _logo = logo_img_tag(c["ticker"], size=13)
    _logo_html = f'{_logo}&nbsp;' if _logo else ''
    _comp_items += (
        f'<div style="display:flex;align-items:center;gap:5px;padding:2px 0;'
        f'font-size:11px;line-height:1.4;">'
        f'<span style="width:7px;height:7px;border-radius:50%;background:{_seg_color};'
        f'flex-shrink:0;display:inline-block;"></span>'
        f'<span style="color:#374151;">{_html_lib.escape(c["name"])}</span>'
        f'<span style="color:#9CA3AF;font-size:10px;">·</span>'
        f'<span style="display:inline-flex;align-items:center;gap:3px;">'
        f'{_logo_html}'
        f'<span style="color:#6B7280;font-weight:600;font-size:10px;">'
        f'{_html_lib.escape(c["ticker"])}</span></span>'
        f'</div>'
    )

cards += (
    '<div class="wl-stat-card" style="position:relative;">'
    '<div class="wl-stat-label">Universe</div>'
    f'<div class="wl-stat-value">{universe_count}</div>'
    f'<div class="wl-stat-sub">of {total_universe} total companies</div>'
    f'<details style="margin-top:10px;">'
    f'<summary style="font-size:11px;color:#3B82F6;cursor:pointer;font-weight:600;'
    f'user-select:none;">View all {universe_count} companies</summary>'
    f'<div style="max-height:280px;overflow-y:auto;margin-top:6px;'
    f'border-top:1px solid #E5E7EB;padding-top:6px;">'
    f'{_comp_items}'
    f'</div></details>'
    '</div>'
)

# Advancing / Declining
if not returns.empty:
    _clean_ret = returns.dropna()
    total_with_data = len(_clean_ret)
    up_count = int((_clean_ret >= 0).sum())
    down_count = total_with_data - up_count
    pct_adv = up_count / total_with_data * 100 if total_with_data else 0

    # Build advancing/declining lists sorted by return (most → least)
    adv_series = _clean_ret[_clean_ret >= 0].sort_values(ascending=False)
    dec_series = _clean_ret[_clean_ret < 0].sort_values(ascending=True)

    def _build_return_list(series, color, sign_prefix=""):
        items = ""
        for t, ret_val in series.items():
            try:
                rv = float(ret_val)
                if np.isnan(rv):
                    continue
            except (TypeError, ValueError):
                continue
            co = ticker_to_co.get(t, {})
            seg_key = co.get("segment", "")
            seg_color = SEGMENT_COLORS.get(seg_key, "#6B7280")
            name = str(co.get("name") or t)
            short = (name[:24] + "…") if len(name) > 25 else name
            _logo = logo_img_tag(t, size=12)
            _lh = f'{_logo}&nbsp;' if _logo else ''
            items += (
                f'<div style="display:flex;align-items:center;gap:5px;padding:2px 0;'
                f'font-size:10px;line-height:1.4;">'
                f'<span style="width:6px;height:6px;border-radius:50%;background:{seg_color};'
                f'flex-shrink:0;"></span>'
                f'<span style="color:#374151;flex:1;overflow:hidden;text-overflow:ellipsis;'
                f'white-space:nowrap;">{_lh}{_html_lib.escape(short)}</span>'
                f'<span style="color:{color};font-weight:700;white-space:nowrap;'
                f'font-variant-numeric:tabular-nums;">{sign_prefix}{rv:.0f}%</span>'
                f'</div>'
            )
        return items

    _adv_items = _build_return_list(adv_series, GREEN, "+")
    _dec_items = _build_return_list(dec_series, RED, "")

    # Use a named details group so only one can be open at a time (HTML exclusive)
    cards += (
        '<div class="wl-stat-card">'
        '<div class="wl-stat-label">% Advancing vs. Declining</div>'
        f'<div class="wl-stat-value">{pct_adv:.0f}% <span style="font-size:16px;'
        f'font-weight:500;color:#6B7280;">advancing</span></div>'
        f'<div class="wl-stat-sub">'
        f'<span style="color:{GREEN};font-weight:700;">{up_count}</span> up &nbsp; '
        f'<span style="color:{RED};font-weight:700;">{down_count}</span> down'
        f'</div>'
        f'<div style="margin-top:8px;">'
        # Advancing list
        f'<details name="adv_dec" style="margin-bottom:4px;">'
        f'<summary style="font-size:11px;color:{GREEN};cursor:pointer;font-weight:600;'
        f'user-select:none;list-style:none;">'
        f'View {up_count} advancing ›</summary>'
        f'<div style="max-height:240px;overflow-y:auto;margin-top:4px;'
        f'padding-top:4px;border-top:1px solid #E5E7EB;">{_adv_items}</div>'
        f'</details>'
        # Declining list
        f'<details name="adv_dec">'
        f'<summary style="font-size:11px;color:{RED};cursor:pointer;font-weight:600;'
        f'user-select:none;list-style:none;">'
        f'View {down_count} declining ›</summary>'
        f'<div style="max-height:240px;overflow-y:auto;margin-top:4px;'
        f'padding-top:4px;border-top:1px solid #E5E7EB;">{_dec_items}</div>'
        f'</details>'
        f'</div>'
        '</div>'
    )

    # Median change by segment (sorted most positive → most negative)
    ticker_seg_map = {d["ticker"]: d["segment"] for d in filtered_data if d.get("ticker")}
    _seg_med_list = []
    for sk in seg_keys:
        if sk not in selected_segments:
            continue
        seg_ticks = [t for t, s in ticker_seg_map.items() if s == sk and t in returns.index]
        if not seg_ticks:
            continue
        seg_med = returns[seg_ticks].median()
        if pd.isna(seg_med):
            continue
        _seg_med_list.append((sk, float(seg_med)))
    _seg_med_list.sort(key=lambda x: x[1], reverse=True)

    _seg_medians = ""
    # Find max absolute value for scaling bars
    _max_abs = max((abs(m) for _, m in _seg_med_list), default=1) or 1
    for sk, seg_med in _seg_med_list:
        sc = SEGMENT_COLORS.get(sk, "#6B7280")
        sn = _CB_LABELS.get(sk, SEGMENT_SHORT.get(sk, sk))
        icon = _SEG_ICONS.get(sk, "")
        s_sign = "+" if seg_med >= 0 else ""
        s_color = GREEN if seg_med >= 0 else RED
        bar_pct = min(abs(seg_med) / _max_abs * 100, 100)
        bar_color = _hex_to_rgba(sc, 0.25)
        _seg_medians += (
            f'<div style="padding:6px 0;">'
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'margin-bottom:3px;">'
            f'<span style="display:flex;align-items:center;gap:6px;">'
            f'<span style="width:10px;height:10px;border-radius:50%;background:{sc};'
            f'display:inline-block;flex-shrink:0;"></span>'
            f'<span style="color:#374151;font-size:14px;font-weight:600;">'
            f'{_html_lib.escape(sn)} {icon}</span></span>'
            f'<span style="color:{s_color};font-weight:800;font-size:16px;'
            f'font-variant-numeric:tabular-nums;">'
            f'{s_sign}{seg_med:.1f}%</span>'
            f'</div>'
            f'<div style="height:6px;background:#F3F4F6;border-radius:3px;overflow:hidden;">'
            f'<div style="height:100%;width:{bar_pct:.0f}%;background:{sc};'
            f'border-radius:3px;"></div>'
            f'</div>'
            f'</div>'
        )

    cards += (
        '<div class="wl-stat-card">'
        f'<div class="wl-stat-label" style="font-size:13px;">Median {selected_period} Change</div>'
        f'{_seg_medians}'
        '</div>'
    )

    # Top / Bottom performers — show 10 directly, no expand needed
    sorted_ret = returns.sort_values(ascending=False)
    top_items = list(sorted_ret.head(10).items())
    bot_items = list(sorted_ret.tail(10).sort_values(ascending=True).items())

    def _perf_row(ticker, pct, color, sign=""):
        try:
            pct_f = float(pct)
            if np.isnan(pct_f):
                return ""
            pct_str = f"{sign}{pct_f:.0f}%"
        except (TypeError, ValueError):
            return ""
        co = ticker_to_co.get(ticker, {})
        seg_key = co.get("segment", "")
        seg_color = SEGMENT_COLORS.get(seg_key, "#6B7280")
        logo = logo_img_tag(ticker, size=13)
        logo_h = f'{logo}&nbsp;' if logo else ''
        name = str(co.get("name") or ticker)
        return (
            f'<div style="display:flex;align-items:center;gap:5px;padding:3px 0;'
            f'font-size:12px;line-height:1.4;">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{seg_color};'
            f'flex-shrink:0;"></span>'
            f'{logo_h}'
            f'<span style="font-weight:600;color:#3B82F6;font-size:11px;">{_html_lib.escape(ticker)}</span>'
            f'<span style="color:#374151;flex:1;overflow:hidden;text-overflow:ellipsis;'
            f'white-space:nowrap;">{_html_lib.escape(name)}</span>'
            f'<span style="color:{color};font-weight:700;margin-left:auto;white-space:nowrap;'
            f'font-variant-numeric:tabular-nums;">{pct_str}</span>'
            f'</div>'
        )

    top_html = "".join(_perf_row(t, p, GREEN, "+") for t, p in top_items)
    cards += (
        '<div class="wl-stat-card">'
        '<div class="wl-stat-label">Best Performers</div>'
        f'{top_html}'
        '</div>'
    )

    bot_html = "".join(_perf_row(t, p, RED) for t, p in bot_items)
    cards += (
        '<div class="wl-stat-card">'
        '<div class="wl-stat-label">Worst Performers</div>'
        f'{bot_html}'
        '</div>'
    )

cards += '</div>'
st.markdown(cards, unsafe_allow_html=True)


# ── Segment performance chart ─────────────────────────────────────────────────
chart_months = _chart_lookback_months(selected_period)
chart_start = as_of - pd.DateOffset(months=chart_months)

st.markdown(
    '<div style="font-size:16px;font-weight:700;color:#111827;'
    'margin-bottom:2px;margin-top:8px;">Segment Performance</div>'
    f'<div style="font-size:12px;color:#9CA3AF;margin-bottom:8px;">'
    f'Market-cap weighted segment price indices, rebased to 100 ({period_label.lower()})</div>',
    unsafe_allow_html=True,
)

ticker_segment = {d["ticker"]: d["segment"] for d in all_data if d.get("ticker") and d.get("segment")}
# Market cap weights for each ticker (for cap-weighted index)
_ticker_mcap = {}
for d in all_data:
    t = d.get("ticker")
    mc = d.get("market_cap") or d.get("enterprise_value")
    if t and mc:
        try:
            mcf = float(mc)
            if not np.isnan(mcf) and mcf > 0:
                _ticker_mcap[t] = mcf
        except (TypeError, ValueError):
            pass

series_map = {}
if not close_df.empty:
    hc_daily = close_df[(close_df.index >= chart_start) & (close_df.index <= as_of)]
    if not hc_daily.empty:
        for seg_key in seg_keys:
            if seg_key not in selected_segments:
                continue
            seg_tickers = [t for t, s in ticker_segment.items()
                           if s == seg_key and t in hc_daily.columns]
            if not seg_tickers:
                continue
            seg_prices = hc_daily[seg_tickers].dropna(axis=1, how="all")
            if seg_prices.empty:
                continue
            first_valid = seg_prices.bfill().iloc[0].replace(0, np.nan)
            valid_cols = first_valid.dropna().index
            if valid_cols.empty:
                continue
            normed = seg_prices[valid_cols].div(first_valid[valid_cols]) * 100
            # Market-cap weighted average (like S&P 500 methodology)
            weights = pd.Series({t: _ticker_mcap.get(t, 1.0) for t in valid_cols})
            w_sum = weights.sum()
            if w_sum == 0 or pd.isna(w_sum):
                weights = pd.Series(1.0 / len(valid_cols), index=valid_cols)
            else:
                weights = weights / w_sum
            seg_avg = normed.mul(weights, axis=1).sum(axis=1).dropna()
            if not seg_avg.empty:
                short_name = _CB_LABELS.get(seg_key, SEGMENT_SHORT.get(seg_key, seg_key))
                series_map[short_name] = (seg_avg, SEGMENT_COLORS.get(seg_key, "#6B7280"))

if series_map:
  try:
    fig = go.Figure()

    # Reference indices (S&P, NASDAQ)
    ref_colors = {"S&P 500": "#9CA3AF", "NASDAQ": "#B0B7C3"}
    ref_series = {}
    for name in ["S&P 500", "NASDAQ"]:
        s = index_prices.get(name)
        if s is not None and not s.empty:
            s = s[(s.index >= chart_start) & (s.index <= as_of)]
            if not s.empty:
                base = s.iloc[0]
                if base and base != 0:
                    ref_s = (s / base) * 100
                    ref_series[name] = ref_s
                    fig.add_trace(go.Scatter(
                        x=ref_s.index, y=ref_s.values, name=name,
                        mode="lines",
                        line=dict(color=ref_colors[name], width=1.5, dash="dot"),
                        opacity=0.4,
                        hovertemplate=f"<b>{name}</b>: %{{y:.1f}}<extra></extra>",
                    ))

    # Segment lines
    for seg_name, (seg_series, seg_color) in series_map.items():
        fig.add_trace(go.Scatter(
            x=seg_series.index, y=seg_series.values, name=seg_name,
            mode="lines",
            line=dict(color=seg_color, width=2.5),
            hovertemplate=f"<b>{seg_name}</b>: %{{y:.1f}}<extra></extra>",
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="#94A3B8", line_width=1, opacity=0.5)

    # Collect all y values for proper axis range (filter NaN/inf)
    all_y_vals = []
    for _, (ss, _) in series_map.items():
        all_y_vals.extend(v for v in ss.values.tolist() if np.isfinite(v))
    for _, rs in ref_series.items():
        if rs is not None:
            all_y_vals.extend(v for v in rs.values.tolist() if np.isfinite(v))

    # End-of-line labels — show ACTUAL values, position adjusted to avoid overlap
    label_items = []
    for seg_name, (seg_series, seg_color) in series_map.items():
        if not seg_series.empty:
            try:
                actual_val = float(seg_series.iloc[-1])
                if np.isnan(actual_val) or np.isinf(actual_val):
                    continue
            except (TypeError, ValueError):
                continue
            label_items.append((seg_name, actual_val, seg_color))
    for name, ref_s in ref_series.items():
        if not ref_s.empty:
            try:
                actual_val = float(ref_s.iloc[-1])
                if np.isnan(actual_val) or np.isinf(actual_val):
                    continue
            except (TypeError, ValueError):
                continue
            label_items.append((name, actual_val, ref_colors.get(name, "#94A3B8")))

    if label_items:
        label_items.sort(key=lambda x: x[1])
        # Place labels at actual y values with small spacing to prevent overlap
        # Use yshift (pixels) for spacing so labels stay near their line
        positions = [it[1] for it in label_items]
        # Convert to pixel offsets for overlap avoidance (approx 16px per label)
        min_gap_px = 16
        y_shifts = [0.0] * len(positions)
        for i in range(1, len(positions)):
            # Rough: 1 data unit ≈ some pixels, use small nudge
            if positions[i] - positions[i - 1] < 3:
                y_shifts[i] = min_gap_px * (i - (len(positions) // 2))

        for idx, (name, actual_val, color) in enumerate(label_items):
            fig.add_annotation(
                x=1.0, xref="paper", xanchor="left",
                y=actual_val,
                yshift=y_shifts[idx],
                text=f"<b>{name}  {actual_val:.0f}</b>",
                showarrow=False, xshift=10,
                font=dict(size=10, color="white", family="DM Sans"),
                bgcolor=color, borderpad=4, bordercolor=color, borderwidth=1,
            )

    # Compute y-axis range with padding
    if all_y_vals:
        y_min = min(all_y_vals)
        y_max = max(all_y_vals)
        y_pad = (y_max - y_min) * 0.08 or 5
        y_range = [y_min - y_pad, y_max + y_pad]
    else:
        y_range = None

    tick_fmt = "%b '%y" if chart_months > 3 else "%b %d"
    fig.update_layout(
        height=380,
        margin=dict(l=40, r=180, t=10, b=40),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="DM Sans, sans-serif"),
        showlegend=False,
        xaxis=dict(
            showgrid=False, tickformat=tick_fmt,
            tickfont=dict(size=10, color="#9CA3AF"),
            linecolor="#E5E7EB", fixedrange=True,
            range=[chart_start, as_of], constrain="domain",
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#F3F4F6",
            tickfont=dict(size=10, color="#9CA3AF"),
            linecolor="#E5E7EB", ticksuffix="  ",
            range=y_range,
        ),
        hovermode="x",
        hoverlabel=dict(bgcolor="white", bordercolor="#E5E7EB",
                        font=dict(size=12, family="DM Sans")),
    )

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "scrollZoom": False})
  except (ValueError, TypeError, KeyError) as _chart_err:
    st.warning(f"Chart rendering error: {_chart_err}")
else:
    st.caption("Not enough price history for segment performance chart.")


# ── Distribution chart ────────────────────────────────────────────────────────
if not returns.empty:
  try:
    bucket_labels = ["Down >10%", "-10% to -5%", "-5% to 0%", "0% to +5%", "+5% to +10%", "Up >10%"]
    bucket_colors = ["#DC2626", "#EF4444", "#FCA5A5", "#86EFAC", "#22C55E", "#059669"]
    counts = [0] * 6
    for c in returns.dropna().values:
        if c < -10: counts[0] += 1
        elif c < -5: counts[1] += 1
        elif c < 0: counts[2] += 1
        elif c < 5: counts[3] += 1
        elif c < 10: counts[4] += 1
        else: counts[5] += 1

    dist_fig = go.Figure()
    dist_fig.add_trace(go.Bar(
        x=bucket_labels, y=counts, marker_color=bucket_colors,
        text=[str(c) for c in counts], textposition="outside",
        textfont=dict(size=12, color="#374151", family="DM Sans"),
        hovertemplate="<b>%{x}</b><br>%{y} companies<extra></extra>",
    ))
    dist_fig.update_layout(
        title=dict(text=f"{period_label} Price Change Distribution",
                   font=dict(size=14, color="#374151", family="DM Sans")),
        height=260, margin=dict(l=40, r=20, t=50, b=40),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="DM Sans, sans-serif", color="#64748B", size=11),
        xaxis=dict(showgrid=False, linecolor="#E5E7EB",
                   tickfont=dict(size=11, color="#6B7280")),
        yaxis=dict(showgrid=True, gridcolor="#F3F4F6", linecolor="#E5E7EB",
                   tickfont=dict(size=10, color="#9CA3AF"),
                   title="Number of Companies",
                   titlefont=dict(size=11, color="#9CA3AF")),
        bargap=0.15,
    )
    st.plotly_chart(dist_fig, use_container_width=True,
                    config={"displayModeBar": False, "scrollZoom": False})
  except (ValueError, TypeError, KeyError):
    st.caption("Distribution chart could not be rendered.")


# ── Category pill styles (tied to segment chart colors) ───────────────────────
_PILL_BASE = "padding:2px 8px;border-radius:4px;font-size:10px;font-weight:500;display:inline-block;white-space:nowrap;"

# Generate pill styles from SEGMENT_COLORS so they match the chart
def _pill_style_from_color(hex_color):
    """Create a light-bg pill style from the segment's chart color."""
    # Parse hex to RGB, then create a 10% opacity background
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"background:rgba({r},{g},{b},0.10);color:{hex_color};{_PILL_BASE}"

_PILL_STYLES = {}
for _sk, _sn in SEGMENT_SHORT.items():
    _sc = SEGMENT_COLORS.get(_sk)
    if _sc:
        _PILL_STYLES[_sn] = _pill_style_from_color(_sc)
_PILL_DEFAULT = f"background:#F1F5F9;color:#64748B;{_PILL_BASE}"


# ── Winners & Losers table ────────────────────────────────────────────────────
st.markdown(
    '<div style="font-size:18px;font-weight:700;color:#111827;'
    'margin-top:24px;margin-bottom:4px;">Top Winners &amp; Losers</div>'
    f'<div style="font-size:13px;color:#94A3B8;margin-bottom:12px;">'
    f'Top 25 by {period_label.lower()} price change</div>',
    unsafe_allow_html=True,
)

if returns.empty:
    st.info(f"No price data available for {period_label}. Try a shorter time period.")
else:
  try:
    sorted_ret = returns.dropna().sort_values(ascending=False)
    winners = list(sorted_ret.head(25).items())
    losers = list(sorted_ret.tail(25).sort_values(ascending=True).items())

    header = (
        '<tr>'
        '<th style="text-align:center;width:40px;">#</th>'
        '<th style="text-align:left;width:90px;">Ticker</th>'
        '<th style="text-align:left;">Company</th>'
        '<th style="text-align:left;width:140px;">Segment</th>'
        '<th style="text-align:right;width:80px;">TEV</th>'
        '<th style="text-align:right;width:80px;">NTM Rev x</th>'
        '<th style="text-align:right;width:80px;">NTM Gr%</th>'
        '<th style="text-align:right;width:100px;">% Change</th>'
        '</tr>'
    )

    def _make_row(rank, ticker, pct, direction):
        co = ticker_to_co.get(ticker, {})
        logo = logo_img_tag(ticker, size=14)
        logo_html = f'{logo}&nbsp;' if logo else ''

        name = str(co.get("name") or ticker)

        seg_key = co.get("segment", "")
        seg_name = _CB_LABELS.get(seg_key, SEGMENT_SHORT.get(seg_key, seg_key))
        pill = _PILL_STYLES.get(SEGMENT_SHORT.get(seg_key, seg_key), _PILL_DEFAULT)

        # TEV
        ev = co.get("enterprise_value")
        try:
            ev_f = float(ev)
            if np.isnan(ev_f) or ev_f <= 0:
                tev_str = "\u2014"
            elif ev_f >= 1e9:
                tev_str = f"${ev_f/1e9:.1f}B"
            else:
                tev_str = f"${ev_f/1e6:.0f}M"
        except (TypeError, ValueError):
            tev_str = "\u2014"

        # NTM Rev multiple
        rev_x = co.get("ntm_tev_rev")
        try:
            rev_f = float(rev_x)
            if np.isnan(rev_f) or rev_f <= 0 or rev_f > 75:
                rev_str = "N/M"
            else:
                rev_str = f"{rev_f:.1f}x"
        except (TypeError, ValueError):
            rev_str = "N/M"

        # NTM Growth
        gr = co.get("ntm_revenue_growth")
        try:
            gr_f = float(gr) * 100
            if np.isnan(gr_f):
                gr_str = "\u2014"
            else:
                gr_color = "#16A34A" if gr_f >= 15 else "#374151" if gr_f >= 5 else "#DC2626"
                gr_str = f'<span style="color:{gr_color};">{"+" if gr_f >= 0 else ""}{gr_f:.0f}%</span>'
        except (TypeError, ValueError):
            gr_str = "\u2014"

        try:
            pct_val = float(pct)
            if np.isnan(pct_val):
                return ""
        except (TypeError, ValueError):
            return ""
        chg_color = "#059669" if pct_val >= 0 else "#DC2626"
        chg_text = f"+{pct_val:.1f}%" if pct_val >= 0 else f"{pct_val:.1f}%"

        rank_col = "#111827" if rank <= 3 else "#64748B"
        rank_fw = "700" if rank <= 3 else "500"

        return (
            f'<tr>'
            f'<td style="text-align:center;color:{rank_col};font-weight:{rank_fw};font-size:12px;">{rank}</td>'
            f'<td style="text-align:left;">{logo_html}'
            f'<span style="color:#3B82F6;font-weight:600;font-size:12px;">{_html_lib.escape(ticker)}</span></td>'
            f'<td style="text-align:left;color:#374151;font-size:12px;">{_html_lib.escape(name)}</td>'
            f'<td style="text-align:left;"><span style="{pill}">{_html_lib.escape(seg_name)}</span></td>'
            f'<td style="text-align:right;font-size:12px;">{tev_str}</td>'
            f'<td style="text-align:right;font-size:12px;">{rev_str}</td>'
            f'<td style="text-align:right;font-size:12px;">{gr_str}</td>'
            f'<td style="text-align:right;font-weight:700;font-size:13px;color:{chg_color};">{chg_text}</td>'
            f'</tr>'
        )

    tbody = "<tbody>"

    # Winners header
    tbody += (
        '<tr><td colspan="8" style="padding:0;background:white;border-top:none;">'
        '<div style="display:flex;align-items:center;gap:8px;'
        'padding:10px 12px 6px 12px;border-left:3px solid #059669;'
        'background:linear-gradient(90deg,rgba(5,150,105,0.05),transparent 40%);">'
        '<span style="font-size:14px;font-weight:800;color:#059669;'
        'text-transform:uppercase;letter-spacing:0.05em;">Top 25 Winners</span>'
        f'<span style="font-size:12px;color:#94A3B8;">{period_label}</span>'
        '</div></td></tr>'
    )
    for i, (ticker, pct) in enumerate(winners, 1):
        try:
            if np.isnan(float(pct)):
                continue
        except (TypeError, ValueError):
            continue
        tbody += _make_row(i, ticker, float(pct), "winners")

    # Losers header
    if losers:
        tbody += (
            '<tr><td colspan="8" style="padding:0;background:white;border-top:2px solid #E2E8F0;">'
            '<div style="display:flex;align-items:center;gap:8px;'
            'padding:10px 12px 6px 12px;border-left:3px solid #DC2626;'
            'background:linear-gradient(90deg,rgba(220,38,38,0.05),transparent 40%);">'
            '<span style="font-size:14px;font-weight:800;color:#DC2626;'
            'text-transform:uppercase;letter-spacing:0.05em;">Top 25 Losers</span>'
            f'<span style="font-size:12px;color:#94A3B8;">{period_label}</span>'
            '</div></td></tr>'
        )
        for i, (ticker, pct) in enumerate(losers, 1):
            try:
                if np.isnan(float(pct)):
                    continue
            except (TypeError, ValueError):
                continue
            tbody += _make_row(i, ticker, float(pct), "losers")

    tbody += "</tbody>"

    st.markdown(
        f'<div class="comb-outer"><table class="comb-tbl">'
        f'<thead>{header}</thead>{tbody}</table></div>',
        unsafe_allow_html=True,
    )
  except (ValueError, TypeError, KeyError) as _tbl_err:
    st.error(f"Error rendering table: {_tbl_err}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="font-size:10px;color:#B0B7C3;margin-top:14px;padding-left:4px;">'
    f'<span style="color:#64748B;font-weight:500;">Source:</span> '
    f'Yahoo Finance (share prices) &middot; FactSet (fundamentals) &middot; '
    f'As of {date_str} &middot; '
    f'Segment lines = market-cap weighted price index per segment</div>',
    unsafe_allow_html=True,
)
