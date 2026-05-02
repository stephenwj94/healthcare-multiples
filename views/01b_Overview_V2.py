"""
Overview V2 — Compact dashboard view.

Everything visible without scrolling: segment chart, key stats,
distribution, and top movers all in a single dense layout.
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
    padding: 1rem 2rem !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stApp { background-color: #FAFBFC !important; }
.main .block-container { background-color: #FAFBFC !important; color: #1A1A2E !important; }
h1,h2,h3,h4,h5,h6 { color: #111827 !important; }
/* Tighter Streamlit spacing */
div[data-testid="stVerticalBlock"] > div { padding-top: 0 !important; }
div[data-testid="stHorizontalBlock"] { gap: 0.5rem !important; }
/* Compact stat boxes */
.v2-card {
    background: white; border: 1px solid #E5E7EB; border-radius: 10px;
    padding: 12px 16px; height: 100%;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
.v2-card-title {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #6B7280; margin-bottom: 6px;
}
.v2-big { font-size: 24px; font-weight: 800; color: #111827; line-height: 1.1; }
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
</style>
""", unsafe_allow_html=True)

render_sidebar()

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

# ── Controls: period + segment filters in one row ─────────────────────────────
seg_keys = list(SEGMENT_DISPLAY.keys())
_CB_LABELS = {
    "pharma": "Pharma", "consumer_health": "Consumer", "medtech": "MedTech",
    "life_sci_tools": "LST/Dx", "services": "Asset-Light",
    "cdmo": "Asset-Heavy", "health_tech": "Health Tech",
}
_SEG_ICONS = {
    "pharma": "💊", "consumer_health": "🛒", "medtech": "🩺",
    "life_sci_tools": "🔬", "services": "🏥", "cdmo": "⚗️", "health_tech": "💻",
}

_PERIOD_OPTIONS = ["1W", "1M", "3M", "6M", "12M", "YTD"]
_PERIOD_LABELS = {
    "1W": "Last Week", "1M": "Last Month", "3M": "Last 3 Months",
    "6M": "Last 6 Months", "12M": "Last 12 Months", "YTD": "Year to Date",
}

# Period selector
_pc, _ = st.columns([2, 8])
with _pc:
    selected_period = st.selectbox("Period", _PERIOD_OPTIONS, index=0,
                                   key="v2_period", label_visibility="collapsed")
period_label = _PERIOD_LABELS[selected_period]

# Segment checkboxes — compact row
def _hex_to_rgba(hex_color, alpha):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

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

_seg_cols = st.columns([1] * len(seg_keys))
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
         "12M": pd.DateOffset(months=12)}
    if period == "YTD":
        return pd.Timestamp(f"{ref.year - 1}-12-31")
    return ref - m.get(period, pd.Timedelta(weeks=1))

all_tickers = sorted({d.get("ticker") for d in all_data if d.get("ticker")})
filtered_tickers = sorted({d.get("ticker") for d in filtered_data if d.get("ticker")})
months_needed = {"1W": 3, "1M": 5, "3M": 8, "6M": 14, "12M": 14, "YTD": 14}.get(selected_period, 14)

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

def _safe_float(val, default=None):
    try:
        f = float(val)
        return default if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return default

# ── ROW 1: Stats + Segment Chart side by side ─────────────────────────────────
left_col, right_col = st.columns([3, 7])

with left_col:
    # Quick stats as compact cards
    _clean = returns.dropna()
    n_total = len(filtered_data)
    n_with_data = len(_clean)
    up = int((_clean >= 0).sum()) if n_with_data else 0
    down = n_with_data - up
    pct_adv = up / n_with_data * 100 if n_with_data else 0
    med_ret = float(_clean.median()) if n_with_data else 0

    st.markdown(
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">'
        # Universe
        f'<div class="v2-card"><div class="v2-card-title">Universe</div>'
        f'<div class="v2-big">{n_total}</div>'
        f'<div class="v2-sub">{n_with_data} with data</div></div>'
        # Advancing
        f'<div class="v2-card"><div class="v2-card-title">Advancing</div>'
        f'<div class="v2-big" style="color:{GREEN};">{pct_adv:.0f}%</div>'
        f'<div class="v2-sub"><span style="color:{GREEN};font-weight:700;">{up}</span> up &nbsp;'
        f'<span style="color:{RED};font-weight:700;">{down}</span> down</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Median by segment — ultra compact
    ticker_seg_map = {d["ticker"]: d["segment"] for d in filtered_data if d.get("ticker")}
    _seg_rows = ""
    _seg_med_list = []
    for sk in seg_keys:
        if sk not in selected_segments:
            continue
        seg_t = [t for t, s in ticker_seg_map.items() if s == sk and t in returns.index]
        if not seg_t:
            continue
        sm = returns[seg_t].median()
        if pd.isna(sm):
            continue
        _seg_med_list.append((sk, float(sm)))
    _seg_med_list.sort(key=lambda x: x[1], reverse=True)

    _max_abs = max((abs(m) for _, m in _seg_med_list), default=1) or 1
    for sk, sm in _seg_med_list:
        sc = SEGMENT_COLORS.get(sk, "#6B7280")
        sn = _CB_LABELS.get(sk, sk)
        s_color = GREEN if sm >= 0 else RED
        bar_pct = min(abs(sm) / _max_abs * 100, 100)
        _seg_rows += (
            f'<div style="display:flex;align-items:center;gap:6px;padding:2px 0;font-size:11px;">'
            f'<span style="width:7px;height:7px;border-radius:50%;background:{sc};flex-shrink:0;"></span>'
            f'<span style="color:#374151;width:70px;font-weight:500;">{_html_lib.escape(sn)}</span>'
            f'<div style="flex:1;height:4px;background:#F3F4F6;border-radius:2px;overflow:hidden;">'
            f'<div style="height:100%;width:{bar_pct:.0f}%;background:{sc};border-radius:2px;"></div></div>'
            f'<span style="color:{s_color};font-weight:700;width:45px;text-align:right;'
            f'font-variant-numeric:tabular-nums;">{"+" if sm >= 0 else ""}{sm:.1f}%</span>'
            f'</div>'
        )

    st.markdown(
        f'<div class="v2-card" style="margin-bottom:10px;">'
        f'<div class="v2-card-title">Median {selected_period} by Segment</div>'
        f'{_seg_rows}</div>',
        unsafe_allow_html=True,
    )

    # Distribution — inline mini bar chart
    if n_with_data:
        bucket_labels = [">10%\u2193", "5-10\u2193", "0-5\u2193", "0-5\u2191", "5-10\u2191", ">10%\u2191"]
        bucket_colors = ["#DC2626", "#EF4444", "#FCA5A5", "#86EFAC", "#22C55E", "#059669"]
        counts = [0] * 6
        for c in _clean.values:
            cv = float(c)
            if cv < -10: counts[0] += 1
            elif cv < -5: counts[1] += 1
            elif cv < 0: counts[2] += 1
            elif cv < 5: counts[3] += 1
            elif cv < 10: counts[4] += 1
            else: counts[5] += 1
        max_c = max(counts) or 1
        _dist_bars = ""
        for lbl, cnt, clr in zip(bucket_labels, counts, bucket_colors):
            bw = cnt / max_c * 100
            _dist_bars += (
                f'<div style="display:flex;align-items:center;gap:4px;padding:1px 0;font-size:10px;">'
                f'<span style="width:42px;color:#6B7280;text-align:right;">{lbl}</span>'
                f'<div style="flex:1;height:10px;background:#F3F4F6;border-radius:2px;overflow:hidden;">'
                f'<div style="height:100%;width:{bw:.0f}%;background:{clr};border-radius:2px;"></div></div>'
                f'<span style="width:20px;color:#374151;font-weight:600;">{cnt}</span>'
                f'</div>'
            )
        st.markdown(
            f'<div class="v2-card">'
            f'<div class="v2-card-title">{period_label} Distribution</div>'
            f'{_dist_bars}</div>',
            unsafe_allow_html=True,
        )

with right_col:
    # Segment performance chart — compact
    ticker_segment = {d["ticker"]: d["segment"] for d in all_data if d.get("ticker") and d.get("segment")}
    _ticker_mcap = {}
    for d in all_data:
        t = d.get("ticker")
        mc = d.get("market_cap") or d.get("enterprise_value")
        if t and mc:
            mcf = _safe_float(mc)
            if mcf and mcf > 0:
                _ticker_mcap[t] = mcf

    chart_months = {"1W": 1, "1M": 3, "3M": 6, "6M": 12, "12M": 12, "YTD": 12}.get(selected_period, 12)
    chart_start = as_of - pd.DateOffset(months=chart_months)

    series_map = {}
    if not close_df.empty:
        hc_daily = close_df[(close_df.index >= chart_start) & (close_df.index <= as_of)]
        if not hc_daily.empty:
            for sk in seg_keys:
                if sk not in selected_segments:
                    continue
                seg_t = [t for t, s in ticker_segment.items() if s == sk and t in hc_daily.columns]
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

        fig.add_hline(y=100, line_dash="dash", line_color="#94A3B8", line_width=1, opacity=0.5)

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

        tick_fmt = "%b '%y" if chart_months > 3 else "%b %d"
        fig.update_layout(
            height=310,
            margin=dict(l=35, r=160, t=8, b=30),
            plot_bgcolor="white", paper_bgcolor="white",
            font=dict(family="DM Sans, sans-serif"),
            showlegend=False,
            xaxis=dict(showgrid=False, tickformat=tick_fmt,
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
            f'<div style="font-size:13px;font-weight:700;color:#111827;margin-bottom:2px;">'
            f'Segment Performance</div>'
            f'<div style="font-size:10px;color:#9CA3AF;margin-bottom:4px;">'
            f'Market-cap weighted, rebased to 100 ({period_label.lower()})</div>',
            unsafe_allow_html=True,
        )
        st.plotly_chart(fig, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False})
    else:
        st.caption("Not enough price history for chart.")

# ── ROW 2: Top 10 Winners + Top 10 Losers side by side ───────────────────────
if not returns.empty:
    _spark_start = _period_start(selected_period, as_of)

    def _mini_spark(ticker, color="#3B82F6"):
        if close_df.empty or ticker not in close_df.columns:
            return ""
        s = close_df[ticker]
        s = s[(s.index >= _spark_start) & (s.index <= as_of)].dropna()
        if len(s) < 3:
            return ""
        vals = s.values.tolist()
        ymin, ymax = min(vals), max(vals)
        yr = ymax - ymin if ymax != ymin else 1
        w, h = 60, 18
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

    def _movers_table(items, accent_color, title, sign=""):
        rows = ""
        for i, (ticker, pct) in enumerate(items, 1):
            pv = _safe_float(pct)
            if pv is None:
                continue
            co = ticker_to_co.get(ticker, {})
            logo = logo_img_tag(ticker, size=12)
            lh = f'{logo}&nbsp;' if logo else ''
            name = str(co.get("name") or ticker)
            short = (name[:22] + "\u2026") if len(name) > 23 else name
            sk = co.get("segment", "")
            sc = SEGMENT_COLORS.get(sk, "#6B7280")
            spark = _mini_spark(ticker, accent_color)

            ev_f = _safe_float(co.get("enterprise_value"))
            tev = f"${ev_f/1e9:.1f}B" if ev_f and ev_f >= 1e9 else (f"${ev_f/1e6:.0f}M" if ev_f and ev_f > 0 else "\u2014")

            rev_f = _safe_float(co.get("ntm_tev_rev"))
            rev = f"{rev_f:.1f}x" if rev_f and 0 < rev_f < 75 else "N/M"

            rows += (
                f'<tr>'
                f'<td style="text-align:center;font-size:11px;color:#9CA3AF;width:24px;">{i}</td>'
                f'<td style="text-align:left;font-size:11px;">{lh}'
                f'<span style="color:#3B82F6;font-weight:600;">{_html_lib.escape(ticker)}</span></td>'
                f'<td style="text-align:left;font-size:11px;color:#374151;max-width:140px;'
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{_html_lib.escape(short)}</td>'
                f'<td style="text-align:right;font-size:11px;color:#6B7280;">{tev}</td>'
                f'<td style="text-align:right;font-size:11px;color:#6B7280;">{rev}</td>'
                f'<td style="text-align:right;font-weight:700;font-size:12px;color:{accent_color};">'
                f'{sign}{pv:.1f}%</td>'
                f'<td style="text-align:center;">{spark}</td>'
                f'</tr>'
            )

        return (
            f'<div style="background:white;border:1px solid #E5E7EB;border-radius:10px;'
            f'overflow:hidden;box-shadow:0 1px 2px rgba(0,0,0,0.03);">'
            f'<div style="display:flex;align-items:center;gap:6px;padding:8px 12px;'
            f'border-left:3px solid {accent_color};'
            f'background:linear-gradient(90deg,{_hex_to_rgba(accent_color, 0.04)},transparent 40%);">'
            f'<span style="font-size:12px;font-weight:800;color:{accent_color};'
            f'text-transform:uppercase;letter-spacing:0.05em;">{title}</span>'
            f'<span style="font-size:10px;color:#94A3B8;">{period_label}</span></div>'
            f'<table style="width:100%;border-collapse:collapse;font-family:DM Sans,sans-serif;">'
            f'<thead><tr>'
            f'<th style="font-size:9px;color:#9CA3AF;text-transform:uppercase;padding:4px 6px;'
            f'border-bottom:1px solid #E5E7EB;text-align:center;width:24px;">#</th>'
            f'<th style="font-size:9px;color:#9CA3AF;text-transform:uppercase;padding:4px 6px;'
            f'border-bottom:1px solid #E5E7EB;text-align:left;">Ticker</th>'
            f'<th style="font-size:9px;color:#9CA3AF;text-transform:uppercase;padding:4px 6px;'
            f'border-bottom:1px solid #E5E7EB;text-align:left;">Company</th>'
            f'<th style="font-size:9px;color:#9CA3AF;text-transform:uppercase;padding:4px 6px;'
            f'border-bottom:1px solid #E5E7EB;text-align:right;">TEV</th>'
            f'<th style="font-size:9px;color:#9CA3AF;text-transform:uppercase;padding:4px 6px;'
            f'border-bottom:1px solid #E5E7EB;text-align:right;">Rev x</th>'
            f'<th style="font-size:9px;color:#9CA3AF;text-transform:uppercase;padding:4px 6px;'
            f'border-bottom:1px solid #E5E7EB;text-align:right;">Change</th>'
            f'<th style="font-size:9px;color:#9CA3AF;text-transform:uppercase;padding:4px 6px;'
            f'border-bottom:1px solid #E5E7EB;text-align:center;">Price</th>'
            f'</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )

    sorted_ret = returns.dropna().sort_values(ascending=False)
    win_items = list(sorted_ret.head(10).items())
    lose_items = list(sorted_ret.tail(10).sort_values(ascending=True).items())

    w_col, l_col = st.columns(2)
    with w_col:
        st.markdown(_movers_table(win_items, "#059669", "Top 10 Winners", "+"), unsafe_allow_html=True)
    with l_col:
        st.markdown(_movers_table(lose_items, "#DC2626", "Top 10 Losers"), unsafe_allow_html=True)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="font-size:9px;color:#B0B7C3;margin-top:8px;">'
    f'Source: Yahoo Finance &middot; FactSet &middot; As of {as_of.strftime("%B %d, %Y")} &middot; '
    f'Market-cap weighted segment indices</div>',
    unsafe_allow_html=True,
)
