"""
Winners & Losers — biggest movers across the healthcare universe.

Single yfinance fetch powers: stat cards, benchmark chart, and movers table.
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

/* Category pills */
.wl-pill {
    padding: 2px 8px; border-radius: 4px; font-size: 10px;
    font-weight: 500; display: inline-block; white-space: nowrap;
}

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
    f'margin-bottom:24px;border:1px solid #DBEAFE;border-left:4px solid #3B82F6;">'
    f'<div style="font-size:28px;font-weight:800;color:#111827;margin-bottom:4px;">'
    f'Winners &amp; Losers</div>'
    f'<div style="font-size:14px;color:#6B7280;font-weight:500;">'
    f'Biggest movers across the healthcare universe'
    f'&nbsp;&nbsp;&middot;&nbsp;&nbsp;'
    f'<span style="color:#9CA3AF;">Data as of {date_str}</span>'
    f'</div></div>',
    unsafe_allow_html=True,
)

# ── Period selector ───────────────────────────────────────────────────────────
_PERIOD_OPTIONS = ["1W", "1M", "3M", "6M", "12M", "YTD"]
_PERIOD_LABELS = {
    "1W": "Last Week", "1M": "Last Month", "3M": "Last 3 Months",
    "6M": "Last 6 Months", "12M": "Last 12 Months", "YTD": "Year to Date",
}

selected_period = st.radio(
    "Time Period", _PERIOD_OPTIONS, horizontal=True, index=0,
    key="wl_period_radio",
)
period_label = _PERIOD_LABELS[selected_period]


# ── yfinance price fetch (single call, cached) ───────────────────────────────
def _period_start(period, ref_date):
    ref = pd.Timestamp(ref_date)
    if period == "1W":  return ref - pd.Timedelta(weeks=1)
    if period == "1M":  return ref - pd.DateOffset(months=1)
    if period == "3M":  return ref - pd.DateOffset(months=3)
    if period == "6M":  return ref - pd.DateOffset(months=6)
    if period == "12M": return ref - pd.DateOffset(months=12)
    if period == "YTD": return pd.Timestamp(f"{ref.year - 1}-12-31")
    return ref - pd.Timedelta(weeks=1)


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_all_prices(tickers_tuple):
    """Batch-download 14 months of adj-close prices from yfinance."""
    import yfinance as yf
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
def _fetch_index_prices():
    """Download S&P 500 and NASDAQ index closes."""
    import yfinance as yf
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
    return results


def _compute_returns(close_df, ref_date, period):
    """Returns Series(ticker -> pct_return) for the given period."""
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
    past_safe = past[common].replace(0, np.nan)
    ret = ((cur[common] / past_safe) - 1) * 100
    return ret.dropna()


# ── Fetch prices ──────────────────────────────────────────────────────────────
tickers = sorted({d.get("ticker") for d in all_data if d.get("ticker")})

with st.spinner("Loading price data from Yahoo Finance..."):
    close_df = _fetch_all_prices(tuple(tickers))
    index_prices = _fetch_index_prices()

returns = _compute_returns(close_df, as_of, selected_period)

# ── Stat cards ────────────────────────────────────────────────────────────────
if not returns.empty:
    total = len(returns)
    up_count = int((returns >= 0).sum())
    down_count = total - up_count
    median_chg = float(returns.median())
    pct_adv = up_count / total * 100 if total else 0

    best_ticker = returns.idxmax()
    worst_ticker = returns.idxmin()
    best_pct = float(returns.max())
    worst_pct = float(returns.min())

    ticker_to_co = {d["ticker"]: d for d in all_data if d.get("ticker")}
    best_name = ticker_to_co.get(best_ticker, {}).get("name", best_ticker)
    worst_name = ticker_to_co.get(worst_ticker, {}).get("name", worst_ticker)

    med_color = GREEN if median_chg >= 0 else RED
    med_sign = "+" if median_chg >= 0 else ""
    adv_color = GREEN if pct_adv >= 50 else RED

    best_logo = logo_img_tag(best_ticker, size=18)
    worst_logo = logo_img_tag(worst_ticker, size=18)

    cards = '<div class="wl-stat-grid">'

    # Universe
    cards += (
        '<div class="wl-stat-card">'
        '<div class="wl-stat-label">Universe</div>'
        f'<div class="wl-stat-value">{total}</div>'
        f'<div class="wl-stat-sub">companies with {period_label.lower()} data</div>'
        '</div>'
    )

    # Advancing / Declining
    cards += (
        '<div class="wl-stat-card">'
        '<div class="wl-stat-label">Advancing / Declining</div>'
        f'<div class="wl-stat-value" style="color:{adv_color};">{pct_adv:.0f}%</div>'
        f'<div class="wl-stat-sub">'
        f'<span style="color:{GREEN};font-weight:700;">{up_count}</span> up &nbsp; '
        f'<span style="color:{RED};font-weight:700;">{down_count}</span> down'
        f'</div></div>'
    )

    # Median change
    cards += (
        '<div class="wl-stat-card">'
        f'<div class="wl-stat-label">Median {selected_period} Change</div>'
        f'<div class="wl-stat-value" style="color:{med_color};">{med_sign}{median_chg:.1f}%</div>'
        f'<div class="wl-stat-sub">{"Bullish" if median_chg >= 0 else "Bearish"} sentiment</div>'
        '</div>'
    )

    # Best performer
    best_short = (best_name[:22] + "...") if len(best_name) > 25 else best_name
    cards += (
        '<div class="wl-stat-card">'
        '<div class="wl-stat-label">Best Performer</div>'
        f'<div class="wl-stat-value" style="color:{GREEN};">+{best_pct:.1f}%</div>'
        f'<div class="wl-stat-sub">'
        f'{best_logo + "&nbsp;" if best_logo else ""}'
        f'<span style="font-weight:600;color:#111827;">{best_ticker}</span> '
        f'{_html_lib.escape(best_short)}</div>'
        '</div>'
    )

    # Worst performer
    worst_short = (worst_name[:22] + "...") if len(worst_name) > 25 else worst_name
    cards += (
        '<div class="wl-stat-card">'
        '<div class="wl-stat-label">Worst Performer</div>'
        f'<div class="wl-stat-value" style="color:{RED};">{worst_pct:.1f}%</div>'
        f'<div class="wl-stat-sub">'
        f'{worst_logo + "&nbsp;" if worst_logo else ""}'
        f'<span style="font-weight:600;color:#111827;">{worst_ticker}</span> '
        f'{_html_lib.escape(worst_short)}</div>'
        '</div>'
    )

    cards += '</div>'
    st.markdown(cards, unsafe_allow_html=True)


# ── Benchmark chart: segment lines rebased to 100 ────────────────────────────
st.markdown(
    '<div style="font-size:16px;font-weight:700;color:#111827;'
    'margin-bottom:2px;margin-top:8px;">Segment Performance</div>'
    '<div style="font-size:12px;color:#9CA3AF;margin-bottom:8px;">'
    'Equal-weighted segment price indices, rebased to 100 at 12 months ago</div>',
    unsafe_allow_html=True,
)

# Build per-segment indices
ticker_segment = {d["ticker"]: d["segment"] for d in all_data if d.get("ticker") and d.get("segment")}
start_12m = as_of - pd.DateOffset(months=12)

series_map = {}
if not close_df.empty:
    hc_daily = close_df[(close_df.index >= start_12m) & (close_df.index <= as_of)]
    if not hc_daily.empty:
        for seg_key, seg_name in SEGMENT_DISPLAY.items():
            seg_tickers = [t for t, s in ticker_segment.items()
                           if s == seg_key and t in hc_daily.columns]
            if not seg_tickers:
                continue
            seg_prices = hc_daily[seg_tickers]
            first_valid = seg_prices.bfill().iloc[0].replace(0, np.nan)
            normed = seg_prices.div(first_valid) * 100
            seg_avg = normed.mean(axis=1).dropna()
            if not seg_avg.empty:
                short_name = SEGMENT_SHORT.get(seg_key, seg_name)
                series_map[short_name] = (seg_avg, SEGMENT_COLORS.get(seg_key, "#6B7280"))

# Segment checkboxes
if series_map:
    seg_names = list(series_map.keys())
    cols = st.columns(min(len(seg_names), 7))
    visible = []
    for i, name in enumerate(seg_names):
        with cols[i % len(cols)]:
            if st.checkbox(name, value=True, key=f"seg_vis_{name}"):
                visible.append(name)

    fig = go.Figure()

    # Reference indices (S&P, NASDAQ)
    ref_colors = {"S&P 500": "#9CA3AF", "NASDAQ": "#B0B7C3"}
    ref_series = {}
    for name in ["S&P 500", "NASDAQ"]:
        s = index_prices.get(name)
        if s is not None and not s.empty:
            s = s[(s.index >= start_12m) & (s.index <= as_of)]
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
        is_visible = seg_name in visible
        fig.add_trace(go.Scatter(
            x=seg_series.index, y=seg_series.values, name=seg_name,
            mode="lines",
            line=dict(color=seg_color, width=2.5),
            visible=True if is_visible else "legendonly",
            hovertemplate=f"<b>{seg_name}</b>: %{{y:.1f}}<extra></extra>",
        ))

    fig.add_hline(y=100, line_dash="dash", line_color="#94A3B8", line_width=1, opacity=0.5)

    # End-of-line labels
    label_items = []
    for seg_name, (seg_series, seg_color) in series_map.items():
        if seg_name in visible and not seg_series.empty:
            label_items.append((seg_name, float(seg_series.iloc[-1]), seg_color))
    for name, ref_s in ref_series.items():
        if not ref_s.empty:
            label_items.append((name, float(ref_s.iloc[-1]), ref_colors.get(name, "#94A3B8")))

    label_items.sort(key=lambda x: x[1])
    adj_y = [it[1] for it in label_items]
    for i in range(1, len(adj_y)):
        if adj_y[i] - adj_y[i - 1] < 8:
            adj_y[i] = adj_y[i - 1] + 8

    for (name, _, color), y in zip(label_items, adj_y):
        fig.add_annotation(
            x=1.0, xref="paper", xanchor="left", y=y,
            text=f"<b>{name}  {y:.0f}</b>",
            showarrow=False, xshift=10,
            font=dict(size=10, color="white", family="DM Sans"),
            bgcolor=color, borderpad=5, bordercolor=color, borderwidth=1,
        )

    fig.update_layout(
        height=380,
        margin=dict(l=40, r=180, t=10, b=40),
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="DM Sans, sans-serif"),
        showlegend=False,
        xaxis=dict(
            showgrid=False, tickformat="%b '%y",
            tickfont=dict(size=10, color="#9CA3AF"),
            linecolor="#E5E7EB", fixedrange=True,
            range=[start_12m, as_of], constrain="domain",
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#F3F4F6",
            tickfont=dict(size=10, color="#9CA3AF"),
            linecolor="#E5E7EB", ticksuffix="  ",
        ),
        hovermode="x",
        hoverlabel=dict(bgcolor="white", bordercolor="#E5E7EB",
                        font=dict(size=12, family="DM Sans")),
    )

    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "scrollZoom": False})
else:
    st.caption("Not enough price history for segment performance chart.")


# ── Distribution chart ────────────────────────────────────────────────────────
if not returns.empty:
    bucket_labels = ["Down >10%", "-10% to -5%", "-5% to 0%", "0% to +5%", "+5% to +10%", "Up >10%"]
    bucket_colors = ["#DC2626", "#EF4444", "#FCA5A5", "#86EFAC", "#22C55E", "#059669"]
    counts = [0] * 6
    for c in returns.values:
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


# ── Category pill styles ──────────────────────────────────────────────────────
_PILL_BASE = "padding:2px 8px;border-radius:4px;font-size:10px;font-weight:500;display:inline-block;white-space:nowrap;"
_PILL_STYLES = {
    "Pharma":               f"background:#E9EFFC;color:#1D4ED8;{_PILL_BASE}",
    "Consumer Health":      f"background:#E6F4EE;color:#047857;{_PILL_BASE}",
    "MedTech":              f"background:#FCEAEA;color:#B91C1C;{_PILL_BASE}",
    "LST / Dx":             f"background:#F1EAFB;color:#6D28D9;{_PILL_BASE}",
    "Asset-Light Services": f"background:#FEF3E2;color:#B45309;{_PILL_BASE}",
    "Asset-Heavy Services": f"background:#FDECE0;color:#C2410C;{_PILL_BASE}",
    "Health Tech":          f"background:#E2F1F5;color:#0E7490;{_PILL_BASE}",
}
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
    st.info(f"No price data available for {period_label}.")
else:
    ticker_to_co = {d["ticker"]: d for d in all_data if d.get("ticker")}

    sorted_ret = returns.sort_values(ascending=False)
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
        short = (name[:26] + "\u2026") if len(name) > 27 else name

        seg_key = co.get("segment", "")
        seg_name = SEGMENT_SHORT.get(seg_key, seg_key)
        pill = _PILL_STYLES.get(seg_name, _PILL_DEFAULT)

        # TEV
        ev = co.get("enterprise_value")
        try:
            ev = float(ev)
            tev_str = f"${ev/1e9:.1f}B" if ev >= 1e9 else f"${ev/1e6:.0f}M"
        except (TypeError, ValueError):
            tev_str = "\u2014"

        # NTM Rev multiple
        rev_x = co.get("ntm_tev_rev")
        try:
            rev_x = float(rev_x)
            rev_str = f"{rev_x:.1f}x" if 0 < rev_x <= 75 else "N/M"
        except (TypeError, ValueError):
            rev_str = "N/M"

        # NTM Growth
        gr = co.get("ntm_revenue_growth")
        try:
            gr = float(gr) * 100
            gr_color = "#16A34A" if gr >= 15 else "#374151" if gr >= 5 else "#DC2626"
            gr_str = f'<span style="color:{gr_color};">{"+" if gr >= 0 else ""}{gr:.0f}%</span>'
        except (TypeError, ValueError):
            gr_str = "\u2014"

        chg_color = "#059669" if pct >= 0 else "#DC2626"
        chg_text = f"+{pct:.1f}%" if pct >= 0 else f"{pct:.1f}%"

        rank_col = "#111827" if rank <= 3 else "#64748B"
        rank_fw = "700" if rank <= 3 else "500"

        return (
            f'<tr>'
            f'<td style="text-align:center;color:{rank_col};font-weight:{rank_fw};font-size:12px;">{rank}</td>'
            f'<td style="text-align:left;">{logo_html}'
            f'<span style="color:#3B82F6;font-weight:600;font-size:12px;">{_html_lib.escape(ticker)}</span></td>'
            f'<td style="text-align:left;color:#374151;font-size:12px;">{_html_lib.escape(short)}</td>'
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
        tbody += _make_row(i, ticker, pct, "winners")

    # Losers header
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
        tbody += _make_row(i, ticker, pct, "losers")

    tbody += "</tbody>"

    st.markdown(
        f'<div class="comb-outer"><table class="comb-tbl">'
        f'<thead>{header}</thead>{tbody}</table></div>',
        unsafe_allow_html=True,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div style="font-size:10px;color:#B0B7C3;margin-top:14px;padding-left:4px;">'
    f'<span style="color:#64748B;font-weight:500;">Source:</span> '
    f'Yahoo Finance (share prices) &middot; FactSet (fundamentals) &middot; '
    f'As of {date_str} &middot; '
    f'Segment lines = equal-weighted price index per segment</div>',
    unsafe_allow_html=True,
)
