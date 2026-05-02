"""
Home / Dashboard — at-a-glance summary for Healthcare Multiples.
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
from components.sidebar import render_sidebar
from config.settings import DB_PATH, SEGMENT_DISPLAY
from config.color_palette import SEGMENT_COLORS, SEGMENT_SHORT, GREEN, RED
from fetcher.db_manager import DBManager
from config.company_registry import COMPANY_REGISTRY
from components.news_filter import filter_news, is_source_blocked

# ── Global styles (DM Sans, warm background) ─────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');

.block-container {
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stApp { background-color: #FBFAF6 !important; }
.main .block-container { background-color: #FBFAF6 !important; color: #1A1A2E !important; }
h1,h2,h3,h4,h5,h6 { color: #111827 !important; }

/* ── Summary cards row ── */
.summary-cards { display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }
.summary-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 20px 24px;
    flex: 1;
    min-width: 160px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
    transition: box-shadow 0.15s ease;
}
.summary-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.07), 0 1px 3px rgba(0,0,0,0.04);
}
.summary-card .label {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #6B7280; margin-bottom: 8px;
}
.summary-card .value {
    font-size: 30px; font-weight: 800; color: #111827; line-height: 1.2;
}
.summary-card .delta {
    font-size: 14px; font-weight: 600; margin-top: 4px;
}

/* ── Section header ── */
.section-head {
    font-family: 'DM Sans', sans-serif;
    font-size: 12px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.06em; color: #374151;
    margin: 36px 0 16px 0;
    border-bottom: 2px solid #E5E7EB;
    padding: 0 0 10px 0;
}

/* ── Movers table ── */
.movers-table { width: 100%; border-collapse: collapse; font-family: 'DM Sans', sans-serif; }
.movers-table th {
    font-size: 10px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.05em; color: #9CA3AF; padding: 6px 10px;
    text-align: left; border-bottom: 1px solid #E5E7EB;
}
.movers-table td {
    font-size: 13px; padding: 8px 10px; border-bottom: 1px solid #F3F4F6;
    color: #1A1A2E;
}
.movers-table .ticker { font-weight: 700; color: #1D4ED8; }

/* ── News feed ── */
.news-item {
    padding: 12px 0; border-bottom: 1px solid #F3F4F6;
}
.news-item:last-child { border-bottom: none; }
.news-title {
    font-size: 13px; font-weight: 600; color: #111827;
    text-decoration: none; line-height: 1.4;
}
.news-title:hover { color: #2563EB; }
.news-meta {
    font-size: 11px; color: #9CA3AF; margin-top: 3px;
}

/* ── Segment heatmap grid ── */
.seg-grid { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 4px; }
.seg-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 18px 20px;
    min-width: 170px;
    flex: 1;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
    border-left: 4px solid #E5E7EB;
}
.seg-card .seg-name {
    font-size: 13px; font-weight: 700; color: #111827; margin-bottom: 6px;
}
.seg-card .seg-stat {
    font-size: 11px; color: #6B7280; line-height: 1.6;
}
.seg-card .seg-multiple {
    font-size: 22px; font-weight: 800; color: #111827; margin-top: 4px;
}

/* ── Footer ── */
.home-footer {
    font-size: 11px; color: #9CA3AF; text-align: center;
    margin-top: 48px; padding: 16px 0; border-top: 1px solid #E5E7EB;
}

/* ── iPad / tablet responsive ── */
@media (max-width: 1024px) {
    .block-container { padding-left: 1rem !important; padding-right: 1rem !important; }
    .summary-cards { gap: 10px; }
    .summary-card { padding: 16px 18px; min-width: 130px; }
    .summary-card .value { font-size: 24px; }
    .seg-grid { gap: 10px; }
    .seg-card { min-width: 140px; padding: 14px 16px; }
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

if not all_data:
    st.info("No data available. Run the data fetcher to populate the database.")
    st.stop()

df = pd.DataFrame(all_data)

# ── Date context ──────────────────────────────────────────────────────────────
latest_date_str = ""
raw_dates = df["snapshot_date"].dropna().tolist()
if raw_dates:
    try:
        latest_dt = max(datetime.strptime(str(d)[:10], "%Y-%m-%d") for d in raw_dates)
        latest_date_str = latest_dt.strftime("%B %d, %Y")
    except Exception:
        pass

date_note = ""
if latest_date_str:
    date_note = (
        f'<span style="font-size:14px;color:#9CA3AF;font-weight:400;">'
        f'Data as of {latest_date_str}</span>'
    )

# ── Title ─────────────────────────────────────────────────────────────────────
st.markdown(
    f'<h1 style="margin-bottom:2px;font-size:1.6rem;">Healthcare Multiples</h1>'
    f'<p style="font-size:15px;color:#6B7280;margin-top:0;margin-bottom:4px;">'
    f'Public market screening &amp; analytics'
    f'&nbsp;&nbsp;{("&middot;&nbsp;&nbsp;" + date_note) if date_note else ""}</p>',
    unsafe_allow_html=True,
)

# ── Market Summary Cards ─────────────────────────────────────────────────────
total_companies = len(df)
median_ntm_rev = df["ntm_tev_rev"].dropna().median()
median_2w = df["price_change_2w"].dropna().median() if "price_change_2w" in df.columns else None
median_2m = df["price_change_2m"].dropna().median() if "price_change_2m" in df.columns else None


def _fmt_pct(val):
    """Format a percentage value with sign and color."""
    if val is None or pd.isna(val):
        return '<span style="color:#9CA3AF;">--</span>'
    color = GREEN if val >= 0 else RED
    sign = "+" if val > 0 else ""
    return f'<span style="color:{color};">{sign}{val:.1f}%</span>'


cards_html = '<div class="summary-cards">'

# Total companies
cards_html += (
    '<div class="summary-card">'
    '<div class="label">Universe</div>'
    f'<div class="value">{total_companies}</div>'
    '<div class="delta" style="color:#9CA3AF;">companies</div>'
    '</div>'
)

# Median NTM EV/Revenue
cards_html += (
    '<div class="summary-card">'
    '<div class="label">Median NTM EV / Revenue</div>'
    f'<div class="value">{median_ntm_rev:.1f}x</div>'
    '<div class="delta" style="color:#9CA3AF;">across universe</div>'
    '</div>'
)

# Median 2-week change
cards_html += (
    '<div class="summary-card">'
    '<div class="label">Median 2-Week Change</div>'
    f'<div class="value">{_fmt_pct(median_2w)}</div>'
    '<div class="delta" style="color:#9CA3AF;">price performance</div>'
    '</div>'
)

# Median 2-month change
cards_html += (
    '<div class="summary-card">'
    '<div class="label">Median 2-Month Change</div>'
    f'<div class="value">{_fmt_pct(median_2m)}</div>'
    '<div class="delta" style="color:#9CA3AF;">price performance</div>'
    '</div>'
)

cards_html += '</div>'
st.markdown(cards_html, unsafe_allow_html=True)


# ── Today's Movers ───────────────────────────────────────────────────────────
st.markdown('<div class="section-head">Top Movers &mdash; 2-Week Price Change</div>', unsafe_allow_html=True)

if "price_change_2w" in df.columns:
    movers = df.dropna(subset=["price_change_2w"]).copy()

    top5 = movers.nlargest(5, "price_change_2w")
    bot5 = movers.nsmallest(5, "price_change_2w")

    def _movers_table(rows, title, dot_class):
        html = (
            f'<div style="font-size:14px;font-weight:700;color:#111827;'
            f'display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
            f'<span class="{dot_class}" style="width:9px;height:9px;border-radius:50%;'
            f'display:inline-block;flex-shrink:0;'
            f'background-color:{"#22C55E" if "green" in dot_class else "#EF4444"};"></span>'
            f'{title}</div>'
        )
        html += '<table class="movers-table"><thead><tr>'
        html += '<th>Ticker</th><th>Company</th><th>Segment</th><th style="text-align:right;">2W Chg</th>'
        html += '</tr></thead><tbody>'
        for _, r in rows.iterrows():
            chg = r["price_change_2w"]
            color = GREEN if chg >= 0 else RED
            sign = "+" if chg > 0 else ""
            seg_display = SEGMENT_SHORT.get(r.get("segment", ""), r.get("segment", ""))
            html += (
                f'<tr>'
                f'<td class="ticker">{r["ticker"]}</td>'
                f'<td>{r.get("name", "")}</td>'
                f'<td>{seg_display}</td>'
                f'<td style="text-align:right;font-weight:700;color:{color};">{sign}{chg:.1f}%</td>'
                f'</tr>'
            )
        html += '</tbody></table>'
        return html

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:18px 20px;'
            'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
            + _movers_table(top5, "Top Gainers", "dot-green")
            + '</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;padding:18px 20px;'
            'box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
            + _movers_table(bot5, "Top Losers", "dot-red")
            + '</div>',
            unsafe_allow_html=True,
        )
else:
    st.caption("Price change data not available.")


# ── Recent News & Earnings ───────────────────────────────────────────────────
st.markdown('<div class="section-head">Recent Healthcare News</div>', unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def _fetch_healthcare_news():
    """Fetch latest news from healthcare ETF tickers via yfinance."""
    import yfinance as yf

    etf_tickers = ["XLV", "IBB", "IHI", "XBI"]
    articles = []
    for t in etf_tickers:
        try:
            ticker_obj = yf.Ticker(t)
            news = getattr(ticker_obj, "news", None)
            if news:
                for item in news:
                    content = item.get("content", item) if isinstance(item, dict) else item
                    if isinstance(content, dict):
                        title = content.get("title", "")
                        link = content.get("clickThroughUrl", {})
                        if isinstance(link, dict):
                            link = link.get("url", "")
                        pub_date = content.get("pubDate", content.get("providerPublishTime", ""))
                        provider = content.get("provider", {})
                        if isinstance(provider, dict):
                            source = provider.get("displayName", "")
                        else:
                            source = str(provider) if provider else ""
                    else:
                        continue
                    if title:
                        articles.append({
                            "title": title,
                            "link": link if link else "",
                            "date": pub_date,
                            "source": source,
                            "etf": t,
                        })
        except Exception:
            continue

    # Deduplicate by title
    seen = set()
    unique = []
    for a in articles:
        key = a["title"].strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    # Filter: block low-quality sources and require healthcare relevance
    unique = filter_news(unique, require_hc_relevance=True)

    return unique[:15]


try:
    news_items = _fetch_healthcare_news()
except Exception:
    news_items = []

if news_items:
    news_html = (
        '<div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:12px;'
        'padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
    )
    for item in news_items:
        title_esc = item["title"].replace("<", "&lt;").replace(">", "&gt;")
        source = item.get("source", "")
        date_str = item.get("date", "")
        # Format date if it looks like ISO
        if date_str and len(str(date_str)) >= 10:
            try:
                dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
                date_str = dt.strftime("%b %d, %Y")
            except Exception:
                date_str = str(date_str)[:10] if date_str else ""
        meta_parts = [p for p in [source, date_str] if p]
        meta = " &middot; ".join(meta_parts)
        if item.get("link"):
            news_html += (
                f'<div class="news-item">'
                f'<a class="news-title" href="{item["link"]}" target="_blank">{title_esc}</a>'
                f'<div class="news-meta">{meta}</div>'
                f'</div>'
            )
        else:
            news_html += (
                f'<div class="news-item">'
                f'<span class="news-title">{title_esc}</span>'
                f'<div class="news-meta">{meta}</div>'
                f'</div>'
            )
    news_html += '</div>'
    st.markdown(news_html, unsafe_allow_html=True)
else:
    st.caption("No recent news available.")


# ── Segment Performance Heatmap ──────────────────────────────────────────────
st.markdown('<div class="section-head">Segment Overview</div>', unsafe_allow_html=True)

seg_stats = (
    df.groupby("segment")
    .agg(
        count=("ticker", "count"),
        median_ntm_rev=("ntm_tev_rev", "median"),
    )
    .reset_index()
)

grid_html = '<div class="seg-grid">'
for _, row in seg_stats.iterrows():
    seg_key = row["segment"]
    seg_name = SEGMENT_DISPLAY.get(seg_key, SEGMENT_SHORT.get(seg_key, seg_key))
    color = SEGMENT_COLORS.get(seg_key, "#6B7280")
    count = int(row["count"])
    med_val = row["median_ntm_rev"]
    med_str = f"{med_val:.1f}x" if pd.notna(med_val) else "--"

    grid_html += (
        f'<div class="seg-card" style="border-left-color:{color};border:1px solid #E5E7EB;'
        f'border-left:4px solid {color};">'
        f'<div class="seg-name">{seg_name}</div>'
        f'<div class="seg-stat">{count} companies</div>'
        f'<div class="seg-multiple">{med_str}</div>'
        f'<div class="seg-stat">Median NTM EV / Rev</div>'
        f'</div>'
    )
grid_html += '</div>'
st.markdown(grid_html, unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="home-footer">'
    'Data sourced from FactSet (primary) and Yahoo Finance (supplementary). '
    'For informational purposes only &mdash; not investment advice.'
    '</div>',
    unsafe_allow_html=True,
)
