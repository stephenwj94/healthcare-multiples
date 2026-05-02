"""
Overview — Compact healthcare dashboard.

Single-screen layout: segment chart, key stats, distribution, top movers.
Market-cap weighted segment indices, expandable details everywhere.
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import html as _html_lib
from pathlib import Path
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from components.logos import logo_img_tag
from config.settings import DB_PATH, EXCEL_OVERRIDE_PATH, SEGMENT_DISPLAY
from config.color_palette import (
    SEGMENT_SHORT, SEGMENT_COLORS,
    GREEN, RED,
)
from fetcher.db_manager import DBManager
from fetcher.excel_override import load_overrides, apply_overrides

# ── Page setup ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
.block-container {
    max-width: 100% !important;
    padding: 0.8rem 2rem 1rem 2rem !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stApp { background-color: #FAFBFC !important; }
.main .block-container { background-color: #FAFBFC !important; color: #1A1A2E !important; }
/* Tighter Streamlit spacing */
div[data-testid="stVerticalBlock"] > div { padding-top: 0 !important; }
/* Compact stat boxes */
.v2-card {
    background: white; border: 1px solid #E5E7EB; border-radius: 10px;
    padding: 10px 14px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.v2-card-title {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #6B7280; margin-bottom: 4px;
}
.v2-big { font-size: 22px; font-weight: 800; color: #111827; line-height: 1.1; }
.v2-sub { font-size: 11px; color: #9CA3AF; margin-top: 2px; }
/* Checkbox pills */
div[data-testid="stCheckbox"] label {
    display: flex !important; align-items: center !important;
    white-space: nowrap !important;
}
div[data-testid="stCheckbox"] label p {
    margin: 0 !important; line-height: 1 !important;
    white-space: nowrap !important; font-size: 12px !important;
}
div[data-testid="stColumn"] {
    flex: 1 1 0 !important; min-width: 0 !important;
}
/* Expandable details styling */
details summary { list-style: none; cursor: pointer; user-select: none; }
details summary::-webkit-details-marker { display: none; }
</style>
""", unsafe_allow_html=True)

render_sidebar()

# ── Helpers ───────────────────────────────────────────────────────────────────
def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

def _safe_float(val, default=None):
    try:
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default

def _fmt_tev(ev_f):
    if ev_f and ev_f > 0:
        return f"${ev_f/1e9:.1f}B" if ev_f >= 1e9 else f"${ev_f/1e6:.0f}M"
    return "\u2014"

# ── Load data ─────────────────────────────────────────────────────────────────
db = DBManager(DB_PATH)
try:
    all_data = db.get_all_latest_snapshots()
except Exception:
    all_data = []

overrides = load_overrides(EXCEL_OVERRIDE_PATH)
if overrides and all_data:
    all_data = apply_overrides(all_data, overrides, skip_sources={"factset"})

if not all_data:
    st.info("No data available.")
    st.stop()

raw_dates = [d.get("snapshot_date") for d in all_data if d.get("snapshot_date")]
as_of = (max(pd.Timestamp(str(d)[:10]) for d in raw_dates)
         if raw_dates else pd.Timestamp.today().normalize())
date_str = as_of.strftime("%b %d, %Y")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="display:flex;align-items:baseline;gap:12px;margin-bottom:6px;">'
    f'<span style="font-size:22px;font-weight:800;color:#111827;">Overview</span>'
    f'<span style="font-size:12px;color:#9CA3AF;">Healthcare universe performance '
    f'&middot; {date_str}</span></div>',
    unsafe_allow_html=True,
)

# ── Controls ──────────────────────────────────────────────────────────────────
seg_keys = list(SEGMENT_DISPLAY.keys())
_CB_LABELS = {
    "pharma": "Pharma", "consumer_health": "Consumer", "medtech": "MedTech",
    "life_sci_tools": "LST/Dx", "services": "Asset-Light",
    "cdmo": "Asset-Heavy", "health_tech": "Health Tech",
}
_SEG_ICONS = {
    "pharma": "\U0001f48a", "consumer_health": "\U0001f6d2", "medtech": "\U0001fa7a",
    "life_sci_tools": "\U0001f52c", "services": "\U0001f3e5", "cdmo": "\u2697\ufe0f",
    "health_tech": "\U0001f4bb",
}

_PERIOD_OPTIONS = ["1W", "1M", "3M", "6M", "12M", "YTD", "3Y", "5Y"]
_PERIOD_LABELS = {
    "1W": "1 Week", "1M": "1 Month", "3M": "3 Months",
    "6M": "6 Months", "12M": "12 Months", "YTD": "Year to Date",
    "3Y": "3 Years", "5Y": "5 Years",
}

# Period + segments in one row
_lbl_col, _sel_col, *_seg_cols = st.columns([0.5, 0.6] + [1] * len(seg_keys))
with _lbl_col:
    st.markdown('<div style="font-size:12px;font-weight:600;color:#374151;'
                'padding-top:8px;">Period</div>', unsafe_allow_html=True)
with _sel_col:
    selected_period = st.selectbox("Period", _PERIOD_OPTIONS, index=0,
                                   key="v2_period", label_visibility="collapsed")
period_label = _PERIOD_LABELS[selected_period]

# Segment pill CSS
_pill_css = "<style>\n"
for seg_key in seg_keys:
    color = SEGMENT_COLORS.get(seg_key, "#6B7280")
    bg = _hex_to_rgba(color, 0.08)
    border = _hex_to_rgba(color, 0.35)
    cb_label = _CB_LABELS.get(seg_key, seg_key)
    aria = f"{cb_label} {_SEG_ICONS.get(seg_key, '')}"
    _pill_css += (
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:checked) {{\n'
        f'  background: {bg}; border: 1.5px solid {border}; border-radius: 8px;\n'
        f'  padding: 4px 8px;\n}}\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:checked) label p {{\n'
        f'  color: {color} !important; font-weight: 600 !important;\n}}\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:not(:checked)) {{\n'
        f'  background: #F3F4F6; border: 1.5px solid #D1D5DB; border-radius: 8px;\n'
        f'  padding: 4px 8px; opacity: 0.6;\n}}\n'
        f'div[data-testid="stCheckbox"]:has(input[aria-label="{aria}"]:not(:checked)) label p {{\n'
        f'  color: #9CA3AF !important;\n}}\n'
    )
_pill_css += "</style>"
st.markdown(_pill_css, unsafe_allow_html=True)

selected_segments = set()
for i, sk in enumerate(seg_keys):
    with _seg_cols[i]:
        if st.checkbox(f"{_CB_LABELS.get(sk, sk)} {_SEG_ICONS.get(sk, '')}",
                       value=True, key=f"v2_seg_{sk}"):
            selected_segments.add(sk)

filtered_data = [d for d in all_data if d.get("segment") in selected_segments]
if not filtered_data:
    st.warning("No segments selected.")
    st.stop()

# ── Price data ────────────────────────────────────────────────────────────────
def _period_start(period, ref):
    ref = pd.Timestamp(ref)
    m = {"1W": pd.Timedelta(weeks=1), "1M": pd.DateOffset(months=1),
         "3M": pd.DateOffset(months=3), "6M": pd.DateOffset(months=6),
         "12M": pd.DateOffset(months=12),
         "3Y": pd.DateOffset(years=3), "5Y": pd.DateOffset(years=5)}
    if period == "YTD":
        return pd.Timestamp(f"{ref.year - 1}-12-31")
    return ref - m.get(period, pd.Timedelta(weeks=1))

all_tickers = sorted({d.get("ticker") for d in all_data if d.get("ticker")})
filtered_tickers = sorted({d.get("ticker") for d in filtered_data if d.get("ticker")})
months_needed = {"1W": 3, "1M": 5, "3M": 8, "6M": 14, "12M": 14,
                 "YTD": 14, "3Y": 38, "5Y": 62}.get(selected_period, 14)

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_prices(tickers_tuple, months):
    import yfinance as yf
    start = (pd.Timestamp.today() - pd.DateOffset(months=months)).strftime("%Y-%m-%d")
    try:
        raw = yf.download(list(tickers_tuple), start=start, auto_adjust=True,
                          progress=False, threads=True)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            close = raw["Close"].copy() if "Close" in raw.columns.get_level_values(0) else pd.DataFrame()
        else:
            close = raw[["Close"]].copy() if "Close" in raw.columns else raw.copy()
            if len(list(tickers_tuple)) == 1:
                close.columns = [list(tickers_tuple)[0]]
        close.index = pd.to_datetime(close.index)
        if close.index.tz is not None:
            close.index = close.index.tz_localize(None)
        return close
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_indices(months):
    import yfinance as yf
    start = (pd.Timestamp.today() - pd.DateOffset(months=months)).strftime("%Y-%m-%d")
    res = {}
    for name, sym in [("S&P 500", "^GSPC"), ("NASDAQ", "^IXIC")]:
        try:
            hist = yf.Ticker(sym).history(start=start, auto_adjust=True)
            if hist.index.tz is not None:
                hist.index = hist.index.tz_localize(None)
            res[name] = hist["Close"] if not hist.empty else None
        except Exception:
            res[name] = None
    return res

with st.spinner("Loading prices..."):
    close_df = _fetch_prices(tuple(all_tickers), months_needed)
    index_prices = _fetch_indices(months_needed)

def _compute_returns(cdf, ref_date, period, tlist=None):
    if cdf.empty:
        return pd.Series(dtype=float)
    ref = pd.Timestamp(ref_date)
    pi = cdf.index[cdf.index <= ref]
    if pi.empty:
        return pd.Series(dtype=float)
    cur = cdf.loc[pi[-1]].dropna()
    start = _period_start(period, ref)
    si = cdf.index[cdf.index <= start]
    if si.empty:
        return pd.Series(dtype=float)
    past = cdf.loc[si[-1]].dropna()
    common = cur.index.intersection(past.index)
    if tlist is not None:
        common = common.intersection(pd.Index(tlist))
    if common.empty:
        return pd.Series(dtype=float)
    ret = ((cur[common] / past[common].replace(0, np.nan)) - 1) * 100
    return ret.dropna()

returns = _compute_returns(close_df, as_of, selected_period, filtered_tickers)
ticker_to_co = {d["ticker"]: d for d in all_data if d.get("ticker")}
ticker_seg_map = {d["ticker"]: d["segment"] for d in filtered_data if d.get("ticker")}

# Market cap weights per ticker
_ticker_mcap = {}
for d in all_data:
    t = d.get("ticker")
    mc = d.get("market_cap") or d.get("enterprise_value")
    if t and mc:
        mcf = _safe_float(mc)
        if mcf and mcf > 0:
            _ticker_mcap[t] = mcf

# ── ROW 1: Stats + Segment Chart ─────────────────────────────────────────────
left_col, right_col = st.columns([3, 7], gap="small")

with left_col:
    _clean = returns.dropna()
    n_total = len(filtered_data)
    n_with_data = len(_clean)
    up = int((_clean >= 0).sum()) if n_with_data else 0
    down = n_with_data - up
    pct_adv = up / n_with_data * 100 if n_with_data else 0

    # Universe + Advancing side by side
    st.markdown(
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;">'
        f'<div class="v2-card" title="Source: FactSet fundamentals">'
        f'<div class="v2-card-title">Universe</div>'
        f'<div class="v2-big">{n_total}</div>'
        f'<div class="v2-sub">{n_with_data} with price data</div></div>'
        f'<div class="v2-card" title="Source: Yahoo Finance prices">'
        f'<div class="v2-card-title">Advancing</div>'
        f'<div class="v2-big" style="color:{GREEN};">{pct_adv:.0f}%</div>'
        f'<div class="v2-sub"><span style="color:{GREEN};font-weight:700;">{up}</span> up '
        f'<span style="color:{RED};font-weight:700;">{down}</span> down</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Market-cap weighted return by segment — expandable
    _seg_data = []
    for sk in seg_keys:
        if sk not in selected_segments:
            continue
        seg_t = [t for t, s in ticker_seg_map.items() if s == sk and t in returns.index]
        if not seg_t:
            continue
        # Market-cap weighted return
        seg_rets = returns[seg_t]
        seg_weights = pd.Series({t: _ticker_mcap.get(t, 1.0) for t in seg_t})
        ws = seg_weights.sum()
        if ws > 0 and not pd.isna(ws):
            seg_weights = seg_weights / ws
            wcr = (seg_rets * seg_weights).sum()
        else:
            wcr = seg_rets.mean()
        if pd.isna(wcr):
            continue
        # Individual tickers sorted by return
        tickers_sorted = seg_rets.sort_values(ascending=False)
        _seg_data.append((sk, float(wcr), tickers_sorted))
    _seg_data.sort(key=lambda x: x[1], reverse=True)

    _max_abs = max((abs(m) for _, m, _ in _seg_data), default=1) or 1
    _seg_html = ""
    for sk, wcr, tickers_sorted in _seg_data:
        sc = SEGMENT_COLORS.get(sk, "#6B7280")
        sn = _CB_LABELS.get(sk, sk)
        icon = _SEG_ICONS.get(sk, "")
        s_color = GREEN if wcr >= 0 else RED
        bar_pct = min(abs(wcr) / _max_abs * 100, 100)
        # Build expandable list of tickers
        _ticker_rows = ""
        for t, rv in tickers_sorted.items():
            co = ticker_to_co.get(t, {})
            name = str(co.get("name") or t)
            logo = logo_img_tag(t, size=11)
            lh = f'{logo}&nbsp;' if logo else ''
            tc = GREEN if rv >= 0 else RED
            _ticker_rows += (
                f'<div style="display:flex;align-items:center;gap:4px;padding:1px 0;font-size:10px;">'
                f'{lh}<span style="color:#3B82F6;font-weight:600;width:48px;" '
                f'title="{_html_lib.escape(name)} — Source: Yahoo Finance">{_html_lib.escape(t)}</span>'
                f'<span style="color:#6B7280;flex:1;overflow:hidden;text-overflow:ellipsis;'
                f'white-space:nowrap;">{_html_lib.escape(name)}</span>'
                f'<span style="color:{tc};font-weight:700;font-variant-numeric:tabular-nums;">'
                f'{"+" if rv >= 0 else ""}{rv:.1f}%</span></div>'
            )

        _seg_html += (
            f'<details style="margin-bottom:2px;">'
            f'<summary style="display:flex;align-items:center;gap:5px;padding:2px 0;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{sc};flex-shrink:0;"></span>'
            f'<span style="color:#374151;font-size:11px;font-weight:500;width:68px;">{_html_lib.escape(sn)}</span>'
            f'<span style="flex:1;height:4px;background:#F3F4F6;border-radius:2px;overflow:hidden;">'
            f'<span style="display:block;height:100%;width:{bar_pct:.0f}%;background:{sc};'
            f'border-radius:2px;"></span></span>'
            f'<span style="color:{s_color};font-weight:700;font-size:11px;width:48px;text-align:right;'
            f'font-variant-numeric:tabular-nums;" title="Market-cap weighted return — Source: Yahoo Finance">'
            f'{"+" if wcr >= 0 else ""}{wcr:.1f}%</span>'
            f'<span style="color:#CBD5E1;font-size:9px;"> \u25B8</span>'
            f'</summary>'
            f'<div style="margin:2px 0 4px 12px;padding:4px 8px;background:#F9FAFB;'
            f'border-radius:6px;border:1px solid #F3F4F6;max-height:160px;overflow-y:auto;">'
            f'{_ticker_rows}</div></details>'
        )

    st.markdown(
        f'<div class="v2-card" style="margin-bottom:8px;" '
        f'title="Market-cap weighted {period_label.lower()} return by segment — Source: Yahoo Finance">'
        f'<div class="v2-card-title">{period_label} by Segment '
        f'<span style="font-weight:400;text-transform:none;color:#9CA3AF;">'
        f'(mcap-weighted \u2022 click to expand)</span></div>'
        f'{_seg_html}</div>',
        unsafe_allow_html=True,
    )

    # Distribution — expandable buckets
    if n_with_data:
        bucket_defs = [
            ("Down >10%", -999, -10, "#DC2626"),
            ("-5% to -10%", -10, -5, "#EF4444"),
            ("-0% to -5%", -5, 0, "#FCA5A5"),
            ("+0% to +5%", 0, 5, "#86EFAC"),
            ("+5% to +10%", 5, 10, "#22C55E"),
            ("Up >10%", 10, 999, "#059669"),
        ]
        buckets = {lbl: [] for lbl, _, _, _ in bucket_defs}
        for t, rv in _clean.items():
            cv = float(rv)
            for lbl, lo, hi, _ in bucket_defs:
                if lo <= cv < hi or (hi == 999 and cv >= lo) or (lo == -999 and cv < hi):
                    buckets[lbl].append((t, cv))
                    break

        max_c = max(len(v) for v in buckets.values()) or 1
        _dist_html = ""
        for lbl, lo, hi, clr in bucket_defs:
            items = sorted(buckets[lbl], key=lambda x: x[1], reverse=True)
            cnt = len(items)
            bw = cnt / max_c * 100
            # Expandable ticker list
            _inner = ""
            for t, cv in items:
                co = ticker_to_co.get(t, {})
                name = str(co.get("name") or t)
                sk = co.get("segment", "")
                sc = SEGMENT_COLORS.get(sk, "#6B7280")
                tc = GREEN if cv >= 0 else RED
                _inner += (
                    f'<div style="display:flex;align-items:center;gap:4px;padding:1px 0;font-size:10px;">'
                    f'<span style="width:5px;height:5px;border-radius:50%;background:{sc};flex-shrink:0;"></span>'
                    f'<span style="color:#3B82F6;font-weight:600;width:44px;" '
                    f'title="{_html_lib.escape(name)}">{_html_lib.escape(t)}</span>'
                    f'<span style="color:{tc};font-weight:600;margin-left:auto;'
                    f'font-variant-numeric:tabular-nums;">{"+" if cv >= 0 else ""}{cv:.1f}%</span></div>'
                )

            _dist_html += (
                f'<details style="margin-bottom:1px;">'
                f'<summary style="display:flex;align-items:center;gap:3px;padding:1px 0;font-size:10px;">'
                f'<span style="width:52px;color:#6B7280;text-align:right;flex-shrink:0;">{lbl}</span>'
                f'<span style="flex:1;height:10px;background:#F3F4F6;border-radius:2px;overflow:hidden;">'
                f'<span style="display:block;height:100%;width:{bw:.0f}%;background:{clr};'
                f'border-radius:2px;"></span></span>'
                f'<span style="width:22px;color:#374151;font-weight:600;">{cnt}</span>'
                f'<span style="color:#CBD5E1;font-size:8px;"> \u25B8</span>'
                f'</summary>'
                f'<div style="margin:1px 0 3px 55px;padding:3px 6px;background:#F9FAFB;'
                f'border-radius:4px;border:1px solid #F3F4F6;max-height:120px;overflow-y:auto;">'
                f'{_inner or "<span style=&quot;color:#9CA3AF;font-size:10px;&quot;>None</span>"}'
                f'</div></details>'
            )

        st.markdown(
            f'<div class="v2-card" title="Source: Yahoo Finance">'
            f'<div class="v2-card-title">{period_label} Distribution '
            f'<span style="font-weight:400;text-transform:none;color:#9CA3AF;">'
            f'(click to expand)</span></div>'
            f'{_dist_html}</div>',
            unsafe_allow_html=True,
        )

with right_col:
    # Segment performance chart
    ticker_segment = {d["ticker"]: d["segment"] for d in all_data
                      if d.get("ticker") and d.get("segment")}

    chart_months = {"1W": 1, "1M": 3, "3M": 6, "6M": 12, "12M": 12,
                    "YTD": 12, "3Y": 36, "5Y": 60}.get(selected_period, 12)
    chart_start = as_of - pd.DateOffset(months=chart_months)

    series_map = {}
    if not close_df.empty:
        hc_daily = close_df[(close_df.index >= chart_start) & (close_df.index <= as_of)]
        if not hc_daily.empty:
            for sk in seg_keys:
                if sk not in selected_segments:
                    continue
                seg_t = [t for t, s in ticker_segment.items()
                         if s == sk and t in hc_daily.columns]
                if not seg_t:
                    continue
                sp = hc_daily[seg_t].dropna(axis=1, how="all")
                if sp.empty:
                    continue
                fv = sp.bfill().iloc[0].replace(0, np.nan)
                vc = fv.dropna().index
                if vc.empty:
                    continue
                normed = sp[vc].div(fv[vc]) * 100
                weights = pd.Series({t: _ticker_mcap.get(t, 1.0) for t in vc})
                ws = weights.sum()
                if ws == 0 or pd.isna(ws):
                    weights = pd.Series(1.0 / len(vc), index=vc)
                else:
                    weights = weights / ws
                seg_avg = normed.mul(weights, axis=1).sum(axis=1).dropna()
                if not seg_avg.empty:
                    sn = _CB_LABELS.get(sk, SEGMENT_SHORT.get(sk, sk))
                    series_map[sn] = (seg_avg, SEGMENT_COLORS.get(sk, "#6B7280"))

    if series_map:
        fig = go.Figure()

        ref_colors = {"S&P 500": "#9CA3AF", "NASDAQ": "#B0B7C3"}
        ref_series = {}
        for name in ["S&P 500", "NASDAQ"]:
            s = index_prices.get(name)
            if s is not None and not s.empty:
                s = s[(s.index >= chart_start) & (s.index <= as_of)]
                if not s.empty:
                    base = s.iloc[0]
                    if base and base != 0:
                        rs = (s / base) * 100
                        ref_series[name] = rs
                        fig.add_trace(go.Scatter(
                            x=rs.index, y=rs.values, name=name,
                            mode="lines",
                            line=dict(color=ref_colors[name], width=1.5, dash="dot"),
                            opacity=0.4,
                            hovertemplate=f"<b>{name}</b>: %{{y:.1f}}<extra></extra>",
                        ))

        for sn, (ss, sc) in series_map.items():
            fig.add_trace(go.Scatter(
                x=ss.index, y=ss.values, name=sn,
                mode="lines", line=dict(color=sc, width=2.5),
                hovertemplate=f"<b>{sn}</b>: %{{y:.1f}}<extra></extra>",
            ))

        fig.add_hline(y=100, line_dash="dash", line_color="#94A3B8",
                      line_width=1, opacity=0.5)

        # Y range
        all_y = []
        for _, (ss, _) in series_map.items():
            all_y.extend(v for v in ss.values.tolist() if np.isfinite(v))
        for _, rs in ref_series.items():
            if rs is not None:
                all_y.extend(v for v in rs.values.tolist() if np.isfinite(v))

        y_range = None
        if all_y:
            y_min, y_max = min(all_y), max(all_y)
            pad = (y_max - y_min) * 0.08 or 5
            y_range = [y_min - pad, y_max + pad]

        # End-of-line labels
        label_items = []
        for sn, (ss, sc) in series_map.items():
            if not ss.empty:
                v = _safe_float(ss.iloc[-1])
                if v is not None:
                    label_items.append((sn, v, sc))
        for name, rs in ref_series.items():
            if not rs.empty:
                v = _safe_float(rs.iloc[-1])
                if v is not None:
                    label_items.append((name, v, ref_colors.get(name, "#94A3B8")))

        if label_items:
            label_items.sort(key=lambda x: x[1])
            positions = [it[1] for it in label_items]
            y_shifts = [0.0] * len(positions)
            for i in range(1, len(positions)):
                if positions[i] - positions[i - 1] < 3:
                    y_shifts[i] = 16 * (i - len(positions) // 2)

            for idx, (name, val, color) in enumerate(label_items):
                fig.add_annotation(
                    x=1.0, xref="paper", xanchor="left",
                    y=val, yshift=y_shifts[idx],
                    text=f"<b>{name}  {val:.0f}</b>",
                    showarrow=False, xshift=10,
                    font=dict(size=9, color="white", family="DM Sans"),
                    bgcolor=color, borderpad=3, bordercolor=color, borderwidth=1,
                )

        # X-axis ticks — clean month boundaries
        if chart_months <= 3:
            dtick = "M1"
            tick_fmt = "%b %d"
        elif chart_months <= 12:
            dtick = "M2"
            tick_fmt = "%b '%y"
        else:
            dtick = "M6"
            tick_fmt = "%b '%y"

        fig.update_layout(
            height=340,
            margin=dict(l=35, r=150, t=6, b=28),
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(family="DM Sans, sans-serif"),
            showlegend=False,
            xaxis=dict(showgrid=False, tickformat=tick_fmt, dtick=dtick,
                       tickfont=dict(size=9, color="#9CA3AF"),
                       linecolor="#E5E7EB", fixedrange=True,
                       range=[chart_start, as_of]),
            yaxis=dict(showgrid=True, gridcolor="#F3F4F6",
                       tickfont=dict(size=9, color="#9CA3AF"),
                       linecolor="#E5E7EB", ticksuffix="  ",
                       range=y_range),
            hovermode="x",
            hoverlabel=dict(bgcolor="white", bordercolor="#E5E7EB",
                            font=dict(size=11, family="DM Sans")),
        )

        st.markdown(
            f'<div style="font-size:13px;font-weight:700;color:#111827;margin-bottom:1px;">'
            f'Segment Performance</div>'
            f'<div style="font-size:10px;color:#9CA3AF;margin-bottom:2px;"'
            f' title="Source: Yahoo Finance. Weighted by market cap.">'
            f'Market-cap weighted, rebased to 100 ({period_label.lower()})</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False})
    else:
        st.caption("Not enough price history for chart.")


# ── ROW 2: Top Winners + Top Losers ──────────────────────────────────────────
def _est_beg_multiple(cur_mult, pct_chg, cur_tev, cur_mcap):
    """Estimate beginning-of-period multiple from price change."""
    if not all(v and v > 0 for v in [cur_mult, cur_tev, cur_mcap]):
        return None
    div = 1 + pct_chg / 100
    if div <= 0:
        return None
    beg_mcap = cur_mcap / div
    beg_tev = beg_mcap + (cur_tev - cur_mcap)
    if beg_tev <= 0:
        return None
    denom = cur_tev / cur_mult
    return beg_tev / denom if denom > 0 else None


def _mini_spark(ticker, color="#3B82F6"):
    if close_df.empty or ticker not in close_df.columns:
        return ""
    s = close_df[ticker]
    s = s[(s.index >= _period_start(selected_period, as_of)) & (s.index <= as_of)].dropna()
    if len(s) < 3:
        return ""
    vals = s.values.tolist()
    ymin, ymax = min(vals), max(vals)
    yr = ymax - ymin if ymax != ymin else 1
    w, h = 56, 16
    pts = []
    for j, v in enumerate(vals):
        x = j / (len(vals) - 1) * w
        y = h - ((v - ymin) / yr * (h - 2) + 1)
        pts.append(f"{x:.1f},{y:.1f}")
    return (
        f'<svg width="{w}" height="{h}" style="vertical-align:middle;">'
        f'<path d="M{"L".join(pts)}" fill="none" stroke="{color}" '
        f'stroke-width="1.5" stroke-linecap="round"/></svg>'
    )


def _beg_now_cell(beg_val, now_val, cap=75):
    """Format a 'beg → now' cell."""
    if now_val and 0 < now_val < cap:
        if beg_val and 0 < beg_val < cap:
            return (f'<span style="color:#9CA3AF;font-size:10px;">{beg_val:.1f}x</span>'
                    f'<span style="color:#CBD5E1;"> \u2192 </span>'
                    f'<b>{now_val:.1f}x</b>')
        return f'<b>{now_val:.1f}x</b>'
    return "N/M"


if not returns.empty:
    st.markdown('<div style="height:4px;"></div>', unsafe_allow_html=True)

    _sub_hdr = '<span style="font-weight:400;font-size:7px;color:#9CA3AF;">BEG\u2192NOW</span>'
    _tbl_header = (
        '<tr>'
        '<th style="text-align:center;width:22px;padding:3px 4px;">#</th>'
        '<th style="text-align:left;padding:3px 6px;width:54px;">Ticker</th>'
        '<th style="text-align:right;width:48px;padding:3px 4px;">TEV</th>'
        f'<th style="text-align:center;width:90px;padding:3px 2px;">Rev x {_sub_hdr}</th>'
        f'<th style="text-align:center;width:100px;padding:3px 2px;">EBITDA x {_sub_hdr}</th>'
        '<th style="text-align:right;width:44px;padding:3px 4px;">Gr%</th>'
        '<th style="text-align:right;width:44px;padding:3px 4px;">Mgn%</th>'
        '<th style="text-align:right;width:58px;padding:3px 4px;">\u0394 Price</th>'
        '<th style="text-align:center;width:60px;padding:3px 2px;">Chart</th>'
        '</tr>'
    )

    def _movers_rows(items, accent, sign="", limit=10):
        rows = ""
        for i, (ticker, pct) in enumerate(items[:limit], 1):
            pv = _safe_float(pct)
            if pv is None:
                continue
            co = ticker_to_co.get(ticker, {})
            name = str(co.get("name") or ticker)
            logo = logo_img_tag(ticker, size=12)
            lh = f'{logo}&nbsp;' if logo else ''
            sk = co.get("segment", "")
            sc = SEGMENT_COLORS.get(sk, "#6B7280")

            ev_f = _safe_float(co.get("enterprise_value"))
            mcap_f = _safe_float(co.get("market_cap"))

            rev_now = _safe_float(co.get("ntm_tev_rev"))
            rev_beg = _est_beg_multiple(rev_now, pv, ev_f, mcap_f)
            rev_cell = _beg_now_cell(rev_beg, rev_now)

            ebitda_now = _safe_float(co.get("ntm_tev_ebitda"))
            ebitda_beg = _est_beg_multiple(ebitda_now, pv, ev_f, mcap_f)
            ebitda_cell = _beg_now_cell(ebitda_beg, ebitda_now, cap=150)

            gr_f = _safe_float(co.get("ntm_revenue_growth"))
            gr_str = f'{gr_f*100:+.0f}%' if gr_f is not None else "\u2014"

            mgn_f = _safe_float(co.get("ebitda_margin"))
            mgn_str = f'{mgn_f*100:.0f}%' if mgn_f is not None else "\u2014"

            spark = _mini_spark(ticker, accent)

            rows += (
                f'<tr title="{_html_lib.escape(name)} \u2014 Source: Yahoo Finance / FactSet">'
                f'<td style="text-align:center;font-size:10px;color:#9CA3AF;padding:3px 4px;">{i}</td>'
                f'<td style="text-align:left;padding:3px 6px;font-size:11px;">'
                f'<span style="width:6px;height:6px;border-radius:50%;background:{sc};'
                f'display:inline-block;vertical-align:middle;margin-right:3px;" '
                f'title="{_html_lib.escape(_CB_LABELS.get(sk, sk))}"></span>'
                f'{lh}<span style="color:#3B82F6;font-weight:600;" '
                f'title="{_html_lib.escape(name)}">{_html_lib.escape(ticker)}</span></td>'
                f'<td style="text-align:right;font-size:10px;color:#6B7280;padding:3px 4px;"'
                f' title="Source: FactSet">{_fmt_tev(ev_f)}</td>'
                f'<td style="text-align:center;font-size:10px;padding:3px 2px;"'
                f' title="NTM EV/Revenue — Source: FactSet">{rev_cell}</td>'
                f'<td style="text-align:center;font-size:10px;padding:3px 2px;"'
                f' title="NTM EV/EBITDA — Source: FactSet">{ebitda_cell}</td>'
                f'<td style="text-align:right;font-size:10px;color:#6B7280;padding:3px 4px;"'
                f' title="NTM Revenue Growth — Source: FactSet">{gr_str}</td>'
                f'<td style="text-align:right;font-size:10px;color:#6B7280;padding:3px 4px;"'
                f' title="EBITDA Margin — Source: FactSet">{mgn_str}</td>'
                f'<td style="text-align:right;font-weight:700;font-size:11px;color:{accent};'
                f'padding:3px 4px;">{sign}{pv:.1f}%</td>'
                f'<td style="text-align:center;padding:3px 2px;">{spark}</td>'
                f'</tr>'
            )
        return rows

    def _movers_table(items, accent, title, sign="", show_more_key=None):
        """Build a movers table with optional show-more."""
        limit = 10
        if show_more_key and st.session_state.get(show_more_key):
            limit = 25
        rows = _movers_rows(items, accent, sign, limit)
        has_more = len(items) > limit

        html = (
            f'<div style="background:white;border:1px solid #E5E7EB;border-radius:10px;'
            f'overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
            f'<div style="display:flex;align-items:center;gap:6px;padding:6px 10px;'
            f'border-left:3px solid {accent};'
            f'background:linear-gradient(90deg,{_hex_to_rgba(accent, 0.04)},transparent 40%);">'
            f'<span style="font-size:11px;font-weight:800;color:{accent};'
            f'text-transform:uppercase;letter-spacing:0.05em;">{title}</span>'
            f'<span style="font-size:10px;color:#94A3B8;">{period_label}</span></div>'
            f'<table style="width:100%;border-collapse:collapse;font-family:DM Sans,sans-serif;'
            f'font-variant-numeric:tabular-nums;">'
            f'<thead><tr style="border-bottom:1px solid #E5E7EB;background:#F9FAFB;">'
        )
        # Minimal header
        for th_txt in ["#", "Ticker", "TEV", "Rev x", "EBITDA x", "Gr%", "Mgn%",
                       "\u0394 Price", "Chart"]:
            align = "center" if th_txt in ("#", "Rev x", "EBITDA x", "Chart") else (
                "left" if th_txt == "Ticker" else "right")
            html += (
                f'<th style="font-size:8px;color:#9CA3AF;text-transform:uppercase;'
                f'padding:3px 4px;text-align:{align};">{th_txt}</th>'
            )
        html += f'</tr></thead><tbody>{rows}</tbody></table></div>'
        return html, has_more

    sorted_ret = returns.dropna().sort_values(ascending=False)
    win_items = list(sorted_ret.head(25).items())
    lose_items = list(sorted_ret.tail(25).sort_values(ascending=True).items())

    w_col, l_col = st.columns(2, gap="small")
    with w_col:
        w_html, w_more = _movers_table(win_items, "#059669", "Winners", "+", "v2_show_more_w")
        st.markdown(w_html, unsafe_allow_html=True)
        if w_more or st.session_state.get("v2_show_more_w"):
            if st.button("Show more winners" if not st.session_state.get("v2_show_more_w")
                         else "Show fewer", key="v2_btn_more_w"):
                st.session_state["v2_show_more_w"] = not st.session_state.get("v2_show_more_w", False)
                st.rerun()
    with l_col:
        l_html, l_more = _movers_table(lose_items, "#DC2626", "Losers", "", "v2_show_more_l")
        st.markdown(l_html, unsafe_allow_html=True)
        if l_more or st.session_state.get("v2_show_more_l"):
            if st.button("Show more losers" if not st.session_state.get("v2_show_more_l")
                         else "Show fewer", key="v2_btn_more_l"):
                st.session_state["v2_show_more_l"] = not st.session_state.get("v2_show_more_l", False)
                st.rerun()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="font-size:9px;color:#B0B7C3;margin-top:6px;">'
    f'Source: Yahoo Finance (prices) &middot; FactSet (fundamentals) &middot; '
    f'As of {date_str} &middot; Market-cap weighted segment indices</div>',
    unsafe_allow_html=True,
)
