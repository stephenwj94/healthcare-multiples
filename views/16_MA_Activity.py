"""
M&A & Deal Activity — tracks acquisitions, IPOs, and universe management
for the healthcare screening platform.
"""

import sys
from collections import Counter
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import render_sidebar
from config.color_palette import LIGHT_BADGE_STYLES, SEGMENT_SHORT, SEGMENT_COLORS
from config.company_registry import COMPANY_REGISTRY
from config.settings import SEGMENT_DISPLAY

render_sidebar()

# ── Page title ────────────────────────────────────────────────────────────────
st.title("M&A & Deal Activity")
st.markdown(
    '<p style="color:#94A3B8;font-size:13px;margin-top:-8px;margin-bottom:24px;">'
    "Notable transactions and IPO activity across healthcare segments"
    "</p>",
    unsafe_allow_html=True,
)

# ── Page-level CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* DM Sans import */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

.ma-card {
    background: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 24px 28px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.02);
    font-family: 'DM Sans', sans-serif;
}
.ma-card-header {
    font-size: 16px;
    font-weight: 700;
    color: #111827;
    margin-bottom: 6px;
    font-family: 'DM Sans', sans-serif;
}
.ma-card-sub {
    font-size: 12px;
    color: #9CA3AF;
    margin-bottom: 0;
    font-family: 'DM Sans', sans-serif;
}
.ma-empty-state {
    background: #F9FAFB;
    border: 1px dashed #D1D5DB;
    border-radius: 6px;
    padding: 20px 24px;
    margin-top: 14px;
    font-family: 'DM Sans', sans-serif;
}
.ma-empty-icon {
    font-size: 28px;
    margin-bottom: 8px;
    opacity: 0.5;
}
.ma-empty-text {
    font-size: 13px;
    color: #6B7280;
    line-height: 1.6;
    margin: 0;
}
.seg-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'DM Sans', sans-serif;
    white-space: nowrap;
}
.universe-stat {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid #F3F4F6;
}
.universe-stat:last-child { border-bottom: none; }
.universe-stat-label {
    font-size: 13px;
    font-weight: 500;
    color: #374151;
    font-family: 'DM Sans', sans-serif;
}
.universe-stat-count {
    font-size: 13px;
    font-weight: 700;
    color: #111827;
    font-family: 'DM Sans', sans-serif;
}
.news-item {
    padding: 12px 0;
    border-bottom: 1px solid #F3F4F6;
    font-family: 'DM Sans', sans-serif;
}
.news-item:last-child { border-bottom: none; }
.news-meta {
    font-size: 11px;
    color: #9CA3AF;
    margin-bottom: 4px;
}
.news-title a {
    font-size: 14px;
    color: #111827;
    text-decoration: none;
    font-weight: 500;
    font-family: 'DM Sans', sans-serif;
}
.news-title a:hover { color: #2563EB; text-decoration: underline; }
.source-attr {
    font-size: 11px;
    color: #9CA3AF;
    text-align: center;
    padding: 16px 0 4px 0;
    border-top: 1px solid #F3F4F6;
    margin-top: 20px;
    font-family: 'DM Sans', sans-serif;
}

/* Sortable table styles */
.sort-table {
    width: 100%;
    border-collapse: collapse;
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
}
.sort-table thead th {
    background: #F9FAFB;
    color: #6B7280;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 10px 12px;
    border-bottom: 2px solid #E5E7EB;
    text-align: left;
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
}
.sort-table thead th:hover { color: #111827; }
.sort-table thead th::after {
    content: ' \\2195';
    font-size: 10px;
    opacity: 0.4;
}
.sort-table tbody tr { border-bottom: 1px solid #F3F4F6; }
.sort-table tbody tr:hover { background: #F9FAFB; }
.sort-table tbody td {
    padding: 9px 12px;
    color: #374151;
    vertical-align: middle;
}
.sort-table tbody td a {
    color: #1D4ED8;
    text-decoration: none;
    font-weight: 500;
}
.sort-table tbody td a:hover { text-decoration: underline; }
.status-active {
    display: inline-block;
    background: #ECFDF5;
    color: #059669;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ── Helper: segment pill HTML ─────────────────────────────────────────────────
def _seg_pill(seg_key: str) -> str:
    short = SEGMENT_SHORT.get(seg_key, seg_key)
    bg, fg = LIGHT_BADGE_STYLES.get(short, ("#F3F4F6", "#374151"))
    return f'<span class="seg-pill" style="background:{bg};color:{fg};">{short}</span>'


# ==============================================================================
# Section A — Companies Under Acquisition
# ==============================================================================
st.markdown(
    '<div class="ma-card">'
    '<p class="ma-card-header">Companies Under Acquisition</p>'
    '<p class="ma-card-sub">Companies with active definitive M&amp;A agreements</p>'
    '<div class="ma-empty-state">'
    '<div class="ma-empty-icon">--</div>'
    '<p class="ma-empty-text">'
    "Companies under active M&amp;A agreements will be flagged here. "
    "Use the admin panel to flag companies as \"under acquisition\" to remove "
    "them from active screening."
    "</p>"
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)


# ==============================================================================
# Section B — Recent IPOs & New Listings
# ==============================================================================
st.markdown(
    '<div class="ma-card">'
    '<p class="ma-card-header">Recent IPOs & New Listings</p>'
    '<p class="ma-card-sub">Newly public healthcare companies to consider for the universe</p>'
    '<div class="ma-empty-state">'
    '<div class="ma-empty-icon">--</div>'
    '<p class="ma-empty-text">'
    "Recently IPO'd or newly listed healthcare companies will appear here. "
    "Add new companies to the screening universe by editing "
    "<code>config/company_registry.py</code> and re-running the data pipeline."
    "</p>"
    "</div>"
    "</div>",
    unsafe_allow_html=True,
)


# ==============================================================================
# Section C — Universe Management
# ==============================================================================
seg_counts = Counter(c["segment"] for c in COMPANY_REGISTRY)
total_companies = len(COMPANY_REGISTRY)

# Stats row
stats_html = ""
for seg_key in SEGMENT_DISPLAY:
    short = SEGMENT_SHORT.get(seg_key, seg_key)
    color = SEGMENT_COLORS.get(seg_key, "#6B7280")
    count = seg_counts.get(seg_key, 0)
    stats_html += (
        f'<div class="universe-stat">'
        f'<span class="universe-stat-label">'
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f'background:{color};margin-right:8px;"></span>{short}</span>'
        f'<span class="universe-stat-count">{count}</span>'
        f'</div>'
    )

st.markdown(
    '<div class="ma-card">'
    '<p class="ma-card-header">Universe Management</p>'
    '<p class="ma-card-sub">'
    f"Current screening universe: <strong style=\"color:#111827;\">{total_companies}</strong> companies across "
    f"{len(seg_counts)} segments"
    "</p>"
    "</div>",
    unsafe_allow_html=True,
)

col_stats, col_note = st.columns([1, 1])

with col_stats:
    st.markdown(
        '<div class="ma-card">'
        f'<p style="font-size:12px;font-weight:600;color:#6B7280;text-transform:uppercase;'
        f'letter-spacing:0.06em;margin-bottom:10px;">Companies by Segment</p>'
        f'{stats_html}'
        '</div>',
        unsafe_allow_html=True,
    )

with col_note:
    st.markdown(
        '<div class="ma-card">'
        '<p style="font-size:12px;font-weight:600;color:#6B7280;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:10px;">How to Update</p>'
        '<div style="font-size:13px;color:#374151;line-height:1.7;">'
        '<p style="margin:0 0 8px 0;"><strong>Add a company:</strong> Append a new entry to '
        '<code>config/company_registry.py</code> with ticker, name, segment, and country. '
        'Then re-run the data pipeline.</p>'
        '<p style="margin:0 0 8px 0;"><strong>Remove a company:</strong> Delete or comment out '
        'the entry in the registry file. Historical data is retained in the database.</p>'
        '<p style="margin:0;"><strong>Flag M&amp;A:</strong> Future releases will support an '
        '<code>under_acquisition</code> field in the registry to auto-exclude companies from '
        'active screening.</p>'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ── Full universe table (sortable via JS) ────────────────────────────────────
st.markdown(
    '<div class="ma-card">'
    '<p class="ma-card-header">Full Company Universe</p>'
    '<p class="ma-card-sub" style="margin-bottom:14px;">Click any column header to sort</p>',
    unsafe_allow_html=True,
)

# Build table rows grouped by segment
rows_html = ""
for co in sorted(COMPANY_REGISTRY, key=lambda c: (c["segment"], c["name"])):
    pill = _seg_pill(co["segment"])
    country = co.get("country", "N/A")
    rows_html += (
        "<tr>"
        f'<td><a href="/Company?ticker={co["ticker"]}" target="_self">{co["name"]}</a></td>'
        f'<td style="font-family:Roboto Mono,monospace;font-size:12px;font-weight:600;'
        f'color:#1D4ED8;">{co["ticker"]}</td>'
        f"<td>{country}</td>"
        f"<td>{pill}</td>"
        f'<td><span class="status-active">Active</span></td>'
        "</tr>"
    )

table_id = "universe-table"
st.markdown(
    f'<table class="sort-table" id="{table_id}">'
    "<thead><tr>"
    "<th>Company Name</th>"
    "<th>Ticker</th>"
    "<th>Country</th>"
    "<th>Segment</th>"
    "<th>Status</th>"
    "</tr></thead>"
    f"<tbody>{rows_html}</tbody>"
    "</table>"
    "</div>",  # close .ma-card
    unsafe_allow_html=True,
)

# Sortable table JavaScript
st.markdown(
    f"""
<script>
(function() {{
  const table = document.getElementById("{table_id}");
  if (!table) return;
  const headers = table.querySelectorAll("thead th");
  let sortCol = -1, sortAsc = true;
  headers.forEach((th, idx) => {{
    th.addEventListener("click", () => {{
      if (sortCol === idx) {{ sortAsc = !sortAsc; }}
      else {{ sortCol = idx; sortAsc = true; }}
      const tbody = table.querySelector("tbody");
      const rows = Array.from(tbody.querySelectorAll("tr"));
      rows.sort((a, b) => {{
        const aText = (a.children[idx].textContent || "").trim().toLowerCase();
        const bText = (b.children[idx].textContent || "").trim().toLowerCase();
        if (aText < bText) return sortAsc ? -1 : 1;
        if (aText > bText) return sortAsc ? 1 : -1;
        return 0;
      }});
      rows.forEach(r => tbody.appendChild(r));
    }});
  }});
}})();
</script>
""",
    unsafe_allow_html=True,
)


# ==============================================================================
# Section D — Notable Healthcare M&A News
# ==============================================================================
st.markdown(
    '<div class="ma-card">'
    '<p class="ma-card-header">Notable Healthcare M&A News</p>'
    '<p class="ma-card-sub" style="margin-bottom:14px;">'
    "Recent deal-related headlines from Yahoo Finance (cached 6 hours)"
    "</p>",
    unsafe_allow_html=True,
)

MA_SEARCH_TICKERS = ["XLV", "IBB", "IHI", "XBI"]
MA_KEYWORDS = [
    "acquisition", "acquire", "merger", "merge", "deal", "buyout",
    "takeover", "ipo", "listing", "spin-off", "spinoff", "divest",
]


@st.cache_data(ttl=60 * 60 * 6)
def _fetch_ma_news(ticker: str) -> list[dict]:
    """Fetch news for a proxy ticker and filter for M&A keywords."""
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        return []
    results = []
    for item in raw:
        content = item.get("content") or item
        title = content.get("title") or item.get("title") or ""
        url = (
            (content.get("canonicalUrl") or {}).get("url")
            or (content.get("clickThroughUrl") or {}).get("url")
            or item.get("link")
            or ""
        )
        pub_raw = content.get("pubDate") or content.get("displayTime") or ""
        provider = (
            (content.get("provider") or {}).get("displayName")
            or item.get("publisher")
            or ""
        )
        title_lower = title.lower()
        if any(kw in title_lower for kw in MA_KEYWORDS):
            results.append({
                "title": title,
                "url": url,
                "published": pub_raw,
                "provider": provider,
                "source_ticker": ticker,
            })
    return results


with st.spinner("Fetching healthcare M&A news..."):
    all_ma_news: list[dict] = []
    seen_titles: set[str] = set()
    for proxy in MA_SEARCH_TICKERS:
        for item in _fetch_ma_news(proxy):
            dedup_key = item["title"].strip().lower()
            if dedup_key not in seen_titles:
                seen_titles.add(dedup_key)
                all_ma_news.append(item)

# Sort by published date descending
def _parse_pub(raw: str):
    from datetime import datetime
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None

all_ma_news.sort(key=lambda x: _parse_pub(x["published"]) or datetime.min, reverse=True)

if all_ma_news:
    news_html = ""
    for item in all_ma_news[:30]:
        pub_dt = _parse_pub(item["published"])
        pub_str = pub_dt.strftime("%b %d, %Y") if pub_dt else ""
        meta_parts = [p for p in [item["provider"], pub_str] if p]
        meta = " &middot; ".join(meta_parts)
        news_html += (
            '<div class="news-item">'
            f'<div class="news-meta">{meta}</div>'
            f'<div class="news-title">'
            f'<a href="{item["url"]}" target="_blank" rel="noopener noreferrer">'
            f'{item["title"]}</a></div>'
            "</div>"
        )
    st.markdown(news_html + "</div>", unsafe_allow_html=True)
else:
    st.markdown(
        '<div style="padding:16px 0;">'
        '<p style="font-size:13px;color:#9CA3AF;margin:0;">'
        "No M&amp;A-related headlines found in recent news. Check back later."
        "</p></div></div>",
        unsafe_allow_html=True,
    )


# ── Source attribution ────────────────────────────────────────────────────────
st.markdown(
    '<div class="source-attr">'
    "News data sourced from Yahoo Finance. Company universe maintained in "
    "<code>config/company_registry.py</code>. "
    "Market data &amp; fundamentals from FactSet."
    "</div>",
    unsafe_allow_html=True,
)
