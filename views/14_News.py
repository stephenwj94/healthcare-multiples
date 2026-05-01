"""
News & Earnings — filterable feed across the healthcare universe.

Pulls news per ticker from Yahoo Finance on demand, plus next-earnings
dates from each ticker's calendar. Filters: segment, ticker, date range.
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf

sys.path.insert(0, str(Path(__file__).parent.parent))

from components.sidebar import render_sidebar
from components.logos import logo_img_tag
from config.color_palette import LIGHT_BADGE_STYLES, SEGMENT_SHORT
from config.company_registry import COMPANY_REGISTRY
from config.settings import SEGMENT_DISPLAY

render_sidebar()
st.title("News & Earnings")
st.markdown(
    '<p style="color:#94A3B8;font-size:13px;margin-top:-8px;">'
    "Live news + upcoming earnings dates pulled from Yahoo Finance. "
    "Filter by segment or specific tickers."
    "</p>",
    unsafe_allow_html=True,
)


# ── Filter controls ───────────────────────────────────────────────────────────
seg_keys = list(SEGMENT_DISPLAY.keys())
seg_labels = list(SEGMENT_DISPLAY.values())

with st.container():
    c1, c2, c3 = st.columns([2, 3, 1])
    sel_segments = c1.multiselect(
        "Segments",
        options=seg_labels,
        default=seg_labels,
    )
    selected_seg_keys = {k for k, v in SEGMENT_DISPLAY.items() if v in sel_segments}

    universe = [c for c in COMPANY_REGISTRY if c["segment"] in selected_seg_keys]
    universe_tickers = sorted([c["ticker"] for c in universe])

    sel_tickers = c2.multiselect(
        "Tickers (leave empty = all in selected segments)",
        options=universe_tickers,
        default=[],
        placeholder="Type to search a ticker",
    )
    days_back = c3.number_input("Days back", min_value=1, max_value=60, value=14, step=1)

# Effective ticker list to query
if sel_tickers:
    target_tickers = [t for t in sel_tickers if t in {c["ticker"] for c in universe}]
else:
    # Avoid hammering yfinance for all 318 names — cap at the largest 40 by mkt cap
    # if the user didn't narrow down with explicit tickers.
    target_tickers = universe_tickers[:40]
    if not sel_tickers:
        st.caption(
            f"Showing news for {len(target_tickers)} tickers in the selected segments. "
            "Add specific tickers above to narrow the feed."
        )

if not target_tickers:
    st.info("No tickers match the current filters.")
    st.stop()


# ── Fetchers (cached) ─────────────────────────────────────────────────────────
@st.cache_data(ttl=60 * 30)
def _fetch_news(yt: str) -> list[dict]:
    try:
        return yf.Ticker(yt).news or []
    except Exception:
        return []


@st.cache_data(ttl=60 * 60 * 6)
def _fetch_calendar(yt: str) -> dict:
    try:
        cal = yf.Ticker(yt).calendar or {}
        return cal if isinstance(cal, dict) else {}
    except Exception:
        return {}


def _parse_news_rows(items: list[dict], ticker: str) -> list[dict]:
    rows = []
    for it in items:
        content = it.get("content") or it
        title = content.get("title") or it.get("title") or "(no title)"
        url = (
            (content.get("canonicalUrl") or {}).get("url")
            or (content.get("clickThroughUrl") or {}).get("url")
            or it.get("link")
            or ""
        )
        pub_raw = content.get("pubDate") or content.get("displayTime") or ""
        try:
            pub_dt = datetime.fromisoformat(pub_raw.replace("Z", "+00:00"))
        except Exception:
            pub_dt = None
        provider = ((content.get("provider") or {}).get("displayName")
                    or it.get("publisher") or "")
        rows.append({
            "ticker": ticker,
            "title": title,
            "url": url,
            "published": pub_dt,
            "provider": provider,
        })
    return rows


# ── Pull and merge news + earnings ────────────────────────────────────────────
ticker_to_company = {c["ticker"]: c for c in COMPANY_REGISTRY}
cutoff = datetime.now(tz=timezone.utc) - timedelta(days=int(days_back))

with st.spinner(f"Fetching news for {len(target_tickers)} ticker(s)…"):
    all_news: list[dict] = []
    upcoming: list[dict] = []
    for t in target_tickers:
        co = ticker_to_company[t]
        yt = co["yahoo_ticker"]
        all_news.extend(_parse_news_rows(_fetch_news(yt), t))
        cal = _fetch_calendar(yt)
        # `cal["Earnings Date"]` is typically a list of date or datetime objects
        ed = cal.get("Earnings Date")
        if ed:
            if isinstance(ed, (list, tuple)):
                ed_first = ed[0] if ed else None
            else:
                ed_first = ed
            if ed_first:
                try:
                    if hasattr(ed_first, "isoformat"):
                        ed_dt = ed_first
                    else:
                        ed_dt = datetime.fromisoformat(str(ed_first))
                    upcoming.append({
                        "ticker": t,
                        "name": co["name"],
                        "segment": SEGMENT_SHORT.get(co["segment"], co["segment"]),
                        "earnings_date": ed_dt,
                    })
                except Exception:
                    pass

# Filter news by cutoff and sort by published desc
news_df_rows = [
    r for r in all_news
    if r["published"] is not None and r["published"] >= cutoff
]
news_df_rows.sort(key=lambda r: r["published"], reverse=True)

# ── News list ─────────────────────────────────────────────────────────────────
st.markdown("#### Headlines")
if not news_df_rows:
    st.caption(f"No news in the last {days_back} day(s) for the selected filters.")
else:
    for r in news_df_rows[:200]:
        co = ticker_to_company.get(r["ticker"])
        seg_short = SEGMENT_SHORT.get(co["segment"], co["segment"]) if co else ""
        bg, fg = LIGHT_BADGE_STYLES.get(seg_short, ("#F3F4F6", "#374151"))
        logo = logo_img_tag(r["ticker"], size=14)
        pub_str = r["published"].strftime("%b %d, %Y · %H:%M") if r["published"] else ""
        st.markdown(
            f'<div style="padding:10px 0;border-bottom:1px solid #F3F4F6;">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
            f'{logo}'
            f'<a href="/Company?ticker={r["ticker"]}" target="_self" '
            f'style="font-weight:600;color:#1D4ED8;text-decoration:none;'
            f'font-family:Roboto Mono,monospace;font-size:12px;">{r["ticker"]}</a>'
            f'<span style="background:{bg};color:{fg};padding:1px 6px;'
            f'border-radius:4px;font-size:10px;font-weight:600;">{seg_short}</span>'
            f'<span style="color:#9CA3AF;font-size:11px;">'
            f'{r["provider"]}{" · " if r["provider"] and pub_str else ""}{pub_str}</span>'
            f'</div>'
            f'<a href="{r["url"]}" target="_blank" rel="noopener noreferrer" '
            f'style="font-size:14px;color:#111827;text-decoration:none;font-weight:500;">'
            f'{r["title"]}</a>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Upcoming earnings table ───────────────────────────────────────────────────
st.markdown("#### Upcoming Earnings")
if not upcoming:
    st.caption("No upcoming earnings dates returned for the selected tickers.")
else:
    today = datetime.now().date()
    upcoming_df = pd.DataFrame([
        {
            "Ticker":   u["ticker"],
            "Company":  u["name"],
            "Segment":  u["segment"],
            "Earnings Date": (
                u["earnings_date"].strftime("%a %b %d, %Y")
                if hasattr(u["earnings_date"], "strftime")
                else str(u["earnings_date"])
            ),
            "_sort": (
                u["earnings_date"]
                if hasattr(u["earnings_date"], "year")
                else datetime.max
            ),
        }
        for u in upcoming
    ])
    upcoming_df = (upcoming_df.sort_values("_sort").drop(columns=["_sort"])
                              .reset_index(drop=True))
    st.dataframe(upcoming_df, use_container_width=True, hide_index=True)
