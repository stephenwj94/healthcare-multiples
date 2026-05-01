"""
Company Profile — single-company drill-down.

Reads `?ticker=XXX` from query params (set by the comp-table ticker link)
and renders: logo + name header, KPI strip, price chart, fundamentals,
multiples vs segment median, and recent news.
"""

import sys
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
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
g3.metric("EBITDA Margin",  _fmt_pct(snapshot.get("ebitda_margin")))


# ── Price chart (1Y, fetched live) ────────────────────────────────────────────
st.markdown("#### Share Price (1Y)")


@st.cache_data(ttl=60 * 30)  # 30-min cache
def _fetch_price_history(yt: str, period: str = "1y") -> pd.DataFrame:
    try:
        hist = yf.Ticker(yt).history(period=period, auto_adjust=True)
        return hist if hist is not None else pd.DataFrame()
    except Exception:
        return pd.DataFrame()


hist = _fetch_price_history(yahoo_ticker)
if hist.empty:
    st.info("Price history not available for this ticker right now.")
else:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hist.index, y=hist["Close"],
        line=dict(color="#1D4ED8", width=2),
        hovertemplate="<b>%{x|%b %d, %Y}</b><br>%{y:.2f}<extra></extra>",
        name="Close",
    ))
    fig.update_layout(
        height=320,
        margin=dict(l=0, r=0, t=10, b=10),
        plot_bgcolor=PLOTLY_BG,
        paper_bgcolor=PLOTLY_BG,
        showlegend=False,
        xaxis=dict(showgrid=False, color=PLOTLY_TEXT),
        yaxis=dict(gridcolor=PLOTLY_GRID, color=PLOTLY_TEXT,
                   tickformat=",.0f", tickprefix="$"),
        font=dict(family="DM Sans, sans-serif", size=12, color=PLOTLY_TEXT),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ── Multiples vs segment median ───────────────────────────────────────────────
st.markdown("#### Multiples — Company vs. Segment Median")


def _seg_median(rows, key: str):
    vals = [r.get(key) for r in rows if r.get(key) is not None and r.get(key) > 0 and r.get(key) <= 75]
    return sorted(vals)[len(vals)//2] if vals else None


peer_count = len(segment_peers)
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
    med_val = _seg_median(segment_peers, key)
    q25 = _seg_quartile(segment_peers, key, 0.25)
    q75 = _seg_quartile(segment_peers, key, 0.75)

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
    f'border-bottom:1px solid #E5E7EB;">{seg_short} Median</th>'
    f'<th style="text-align:right;padding:10px 14px;font-size:11px;'
    f'text-transform:uppercase;letter-spacing:0.05em;color:#6B7280;'
    f'border-bottom:1px solid #E5E7EB;">vs. Median</th>'
    f'</tr></thead>'
    f'<tbody>{"".join(rows_html)}</tbody>'
    f'</table></div>',
    unsafe_allow_html=True,
)
st.caption(
    f"Median computed across {peer_count} {seg_short} companies. "
    f"Highlighted cells fall above the 75th or below the 25th percentile of segment peers."
)


# ── Fundamentals card ─────────────────────────────────────────────────────────
st.markdown("#### Fundamentals (LTM)")
f1, f2, f3, f4 = st.columns(4)
f1.metric("LTM Revenue", _fmt_dollars_b(snapshot.get("ltm_revenue")))
f2.metric("LTM Gross Profit", _fmt_dollars_b(snapshot.get("ltm_gross_profit")))
f3.metric("LTM EBITDA", _fmt_dollars_b(snapshot.get("ltm_ebitda")))
f4.metric("Gross Margin", _fmt_pct(snapshot.get("gross_margin")))


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
    for item in news[:8]:
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


# ── Footer link back to comp table ────────────────────────────────────────────
st.markdown("---")
st.caption(
    f'Data via yfinance · LTM/NTM via fetcher snapshot {snapshot.get("snapshot_date","")}'
)
