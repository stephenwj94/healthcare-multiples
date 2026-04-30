"""
Number formatting, color-coding, and table styling for the dashboard.
Styled to match Meritech Analytics comps table layout.
"""

import pandas as pd
import numpy as np


# ── Color palette (muted, professional) ──
GREEN = "#22C55E"   # green-500
YELLOW = "#F59E0B"  # amber-500
RED = "#EF4444"     # red-500
MUTED = "#6B7280"   # gray-500


# ── Single-value formatters ──

def fmt_billions(val):
    if pd.isna(val) or val is None:
        return "N/A"
    return f"${val:.1f}bn"


def fmt_millions(val):
    if pd.isna(val) or val is None:
        return "N/A"
    return f"${val:,.0f}M"


def fmt_pct(val, decimals=1):
    if pd.isna(val) or val is None:
        return "N/A"
    return f"{val * 100:.{decimals}f}%"


def fmt_multiple(val, decimals=1):
    if pd.isna(val) or val is None:
        return "N/A"
    return f"{val:.{decimals}f}x"


def fmt_growth_adj(val):
    if pd.isna(val) or val is None:
        return "N/A"
    return f"{val:.2f}x"


# ── Meritech-style formatters (parentheses for negatives, $ in millions) ──

def _fmt_tev(val):
    """TEV in $M with commas, parentheses for negative."""
    if pd.isna(val) or val is None:
        return "-"
    v = val * 1000  # convert from $B to $M
    if v < 0:
        return f"(${abs(v):,.0f})"
    return f"${v:,.0f}"


def _fmt_dollar_m(val):
    """Dollar value already in $M, with commas."""
    if pd.isna(val) or val is None:
        return "-"
    if val < 0:
        return f"(${abs(val):,.0f})"
    return f"${val:,.0f}"


def _fmt_pct_clean(val):
    """Percentage with no decimal, parentheses for negative. Expects 0-1 range."""
    if pd.isna(val) or val is None:
        return "-"
    pct = val * 100
    if pct < 0:
        return f"({abs(pct):.0f}%)"
    return f"{pct:.0f}%"


def _fmt_pct_1dp(val):
    """Percentage with 1 decimal place + Meritech-style arrow indicator. Expects 0-1 range."""
    if pd.isna(val) or val is None:
        return "-"
    pct = val * 100
    if pct < 0:
        return f"▼  ({abs(pct):.1f}%)"
    return f"▲  {pct:.1f}%"


def _fmt_multiple_1dp(val):
    """Multiple with 1 decimal, e.g. 12.3x."""
    if pd.isna(val) or val is None:
        return "-"
    if val < 0:
        return f"({abs(val):.1f}x)"
    return f"{val:.1f}x"


def _fmt_multiple_2dp(val):
    """Growth-adjusted multiple with 2 decimals."""
    if pd.isna(val) or val is None:
        return "-"
    if val < 0:
        return f"({abs(val):.2f}x)"
    return f"{val:.2f}x"


# ── Color functions ──

def color_for_value(val, thresholds):
    if pd.isna(val) or val is None:
        return ""
    for threshold, color in thresholds:
        if val >= threshold:
            return f"color: {color}"
    return ""


def color_pct_change(val):
    if pd.isna(val) or val is None:
        return f"color: {MUTED}"
    return f"color: {GREEN}; font-weight: 600" if val >= 0 else f"color: {RED}; font-weight: 600"


def color_gross_margin(val):
    if pd.isna(val) or val is None:
        return f"color: {MUTED}"
    if val >= 0.70:
        return f"color: {GREEN}"
    elif val >= 0.50:
        return f"color: {YELLOW}"
    return f"color: {RED}"


def color_ebitda_margin(val):
    if pd.isna(val) or val is None:
        return f"color: {MUTED}"
    if val >= 0.25:
        return f"color: {GREEN}"
    elif val >= 0.10:
        return f"color: {YELLOW}"
    return f"color: {RED}"


def color_rev_growth(val):
    if pd.isna(val) or val is None:
        return f"color: {MUTED}"
    if val >= 0.20:
        return f"color: {GREEN}"
    elif val >= 0.10:
        return f"color: {YELLOW}"
    return f"color: {RED}"


def color_52wk(val):
    if pd.isna(val) or val is None:
        return f"color: {MUTED}"
    if val >= 0.90:
        return f"color: {GREEN}"
    elif val >= 0.70:
        return f"color: {YELLOW}"
    return f"color: {RED}"


def color_multiple(val):
    """Subtle color for multiples - higher = blue, lower = muted."""
    if pd.isna(val) or val is None:
        return f"color: {MUTED}"
    return ""


# ── Column ordering (Meritech-style groups) ──

# Market Data columns
MARKET_DATA_COLS = ["Market Cap", "TEV", "% 52W Hi", "NTM Revenue", "Revenue Gr%"]

# Valuation Multiples columns
VALUATION_COLS = ["NTM Revenue x", "NTM GP x", "NTM EBITDA x", "LTM Revenue x", "LTM GP x", "LTM EBITDA x", "GA Revenue", "GA GP"]

# Margins & Performance columns
MARGIN_COLS = ["EBITDA Mgn", "3Y CAGR"]

# Price Performance columns
PRICE_PERF_COLS = ["2W Chg", "2M Chg"]

# Full ordered column list for Revenue view
REVENUE_VIEW_COLS = (
    ["Company"] + MARKET_DATA_COLS + VALUATION_COLS + MARGIN_COLS + PRICE_PERF_COLS
)

# EBITDA view: swap out revenue/GP multiples
EBITDA_VALUATION_COLS = ["NTM EBITDA x", "LTM EBITDA x"]
EBITDA_VIEW_COLS = (
    ["Company"] + MARKET_DATA_COLS + EBITDA_VALUATION_COLS + MARGIN_COLS + PRICE_PERF_COLS
)


# ── DataFrame preparation ──

def prepare_display_df(data, include_sub_segment=False):
    """
    Convert raw snapshot data (list of dicts) into a display-ready DataFrame.
    Columns ordered Meritech-style: Market Data -> Multiples -> Margins -> Price Changes.
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    display = pd.DataFrame()
    display["Company"] = df["name"]

    # Market Data
    display["Market Cap"] = df["market_cap"].apply(
        lambda x: x / 1e6 if x and x > 0 else np.nan
    )
    display["TEV"] = df["enterprise_value"].apply(
        lambda x: x / 1e6 if x and x > 0 else np.nan
    )
    display["% 52W Hi"] = df["pct_52wk_high"]
    display["NTM Revenue"] = df["ntm_revenue"].apply(lambda x: x / 1e6 if x else np.nan)
    display["Revenue Gr%"] = df["ntm_revenue_growth"]

    # Valuation Multiples - clip negatives to NaN
    for col in ["ntm_tev_rev", "ntm_tev_gp", "ntm_tev_ebitda", "ltm_tev_rev", "ltm_tev_gp", "ltm_tev_ebitda"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: x if x and x > 0 else np.nan)

    display["NTM Revenue x"] = df["ntm_tev_rev"]
    display["NTM GP x"] = df["ntm_tev_gp"]
    display["NTM EBITDA x"] = df.get("ntm_tev_ebitda", np.nan)
    display["LTM Revenue x"] = df["ltm_tev_rev"]
    display["LTM GP x"] = df["ltm_tev_gp"]
    display["LTM EBITDA x"] = df.get("ltm_tev_ebitda", np.nan)
    display["GA Revenue"] = df["growth_adj_rev"]
    display["GA GP"] = df["growth_adj_gp"]

    # Margins
    display["EBITDA Mgn"] = df["ebitda_margin"]
    display["3Y CAGR"] = df["n3y_revenue_cagr"]

    # Price Performance
    display["2W Chg"] = df["price_change_2w"]
    display["2M Chg"] = df["price_change_2m"]

    if include_sub_segment:
        display["sub_segment"] = df["sub_segment"]

    # Sort by TEV descending
    display = display.sort_values("TEV", ascending=False, na_position="last")

    return display


def style_comp_table(df):
    """
    Apply Meritech-style formatting and color-coding to a display DataFrame.
    Uses custom format functions for parentheses on negatives, $ in millions, clean %.
    """
    format_dict = {
        "Market Cap": _fmt_dollar_m,
        "TEV": _fmt_dollar_m,
        "% 52W Hi": _fmt_pct_clean,
        "NTM Revenue": _fmt_dollar_m,
        "Revenue Gr%": _fmt_pct_clean,
        "EBITDA Mgn": _fmt_pct_clean,
        "3Y CAGR": _fmt_pct_clean,
        "NTM Revenue x": _fmt_multiple_1dp,
        "NTM GP x": _fmt_multiple_1dp,
        "NTM EBITDA x": _fmt_multiple_1dp,
        "LTM Revenue x": _fmt_multiple_1dp,
        "LTM GP x": _fmt_multiple_1dp,
        "LTM EBITDA x": _fmt_multiple_1dp,
        "GA Revenue": _fmt_multiple_2dp,
        "GA GP": _fmt_multiple_2dp,
        "2W Chg": _fmt_pct_1dp,
        "2M Chg": _fmt_pct_1dp,
    }

    active_formats = {k: v for k, v in format_dict.items() if k in df.columns}
    styled = df.style.format(active_formats, na_rep="-")

    # Color-coding per column
    color_maps = {
        "EBITDA Mgn": color_ebitda_margin,
        "Revenue Gr%": color_rev_growth,
        "3Y CAGR": color_rev_growth,
        "% 52W Hi": color_52wk,
        "2W Chg": color_pct_change,
        "2M Chg": color_pct_change,
    }

    for col, func in color_maps.items():
        if col in df.columns:
            styled = styled.map(func, subset=[col])

    # Right-align all numeric columns for clean appearance
    numeric_cols = [c for c in df.columns if c not in ("Company", "sub_segment")]
    for col in numeric_cols:
        if col in df.columns:
            styled = styled.set_properties(subset=[col], **{"text-align": "right"})

    # Left-align Company column
    if "Company" in df.columns:
        styled = styled.set_properties(
            subset=["Company"],
            **{"text-align": "left", "font-weight": "500", "white-space": "nowrap"}
        )

    return styled


def compute_summary_rows(df):
    """
    Compute mean and median rows for numeric columns.
    Returns two dicts: mean_row, median_row.
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    mean_row = df[numeric_cols].mean()
    median_row = df[numeric_cols].median()

    mean_row["Company"] = "Mean"
    median_row["Company"] = "Median"

    return mean_row, median_row


# ─────────────────────────────────────────────────────────────────────────────
# HTML Table Helpers — custom comp table rendering
# ─────────────────────────────────────────────────────────────────────────────
import html as _html_lib  # noqa: E402  (late import is fine in Python)

# Short display names for the Category pill badge
SEGMENT_SHORT = {
    "pharma":          "Pharma",
    "consumer_health": "Cons Health",
    "medtech":         "MedTech",
    "life_sci_tools":  "Life Sci",
    "services":        "Services",
    "cdmo":            "CDMO",
    "health_tech":     "Health Tech",
}

# Pill badge colors (bg, text) per segment — light theme
SEGMENT_PILL_COLORS = {
    "pharma":          ("#DBEAFE", "#1D4ED8"),
    "consumer_health": ("#D1FAE5", "#065F46"),
    "medtech":         ("#EDE9FE", "#5B21B6"),
    "life_sci_tools":  ("#FEE2E2", "#991B1B"),
    "services":        ("#FEF3C7", "#92400E"),
    "cdmo":            ("#CFFAFE", "#155E75"),
    "health_tech":     ("#FCE7F3", "#9D174D"),
}

# Numeric column keys used for mean / median computation
COMPS_NUMERIC_COLS = [
    "mkt_cap_m", "tev_m",
    "pct_52wk", "ev_rev", "ev_ebitda", "ev_gp",
    "ltm_rev_x", "ltm_ebitda_x", "ltm_gp_x",
    "ga_rev", "ga_gp",
    "rev_gr", "cagr_3y", "gm", "ebitda_mgn",
    "chg_2w", "chg_2m",
]

# Multiple columns — filtered in summary rows (exclude N/M and >75x, require min 5 values)
MULTIPLE_COLS = {
    "ev_rev", "ev_ebitda", "ev_gp",
    "ltm_rev_x", "ltm_ebitda_x", "ltm_gp_x",
    "ga_rev", "ga_gp",
}
_MULT_CAP = 75
_MIN_SUMMARY_N = 5

# Raw dollar columns where mean/median are not meaningful — show "—" in summary rows.
# We care about averages for price changes, growth/margin rates, and multiples only.
COMPS_NO_SUMMARY_COLS = {
    "mkt_cap_m", # market cap
    "tev_m",     # enterprise value
}

_ND_CHAR = "N/A"


def _safe_num(val):
    """Return float(val) if finite and valid, else None."""
    if val is None:
        return None
    try:
        f = float(val)
        if np.isnan(f) or np.isinf(f):
            return None
        return f
    except (TypeError, ValueError):
        return None


def _cell_nd():
    return f'<span style="color:#9CA3AF">{_ND_CHAR}</span>'


def _cell_dollar_m(val):
    """Format a value already in $mm — smart B/M suffix (≥1000M → $X.XB, else $X,XXXM)."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    abs_v = abs(v)
    if abs_v >= 1000:
        text = f"${abs_v / 1000:.1f}bn"
    else:
        text = f"${abs_v:,.0f}M"
    if v < 0:
        text = f"({text})"
    return f'<span style="font-variant-numeric:tabular-nums">{text}</span>'


def _cell_price_fmt(val):
    """Stock price formatted as $XX.XX."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    return f'<span style="font-variant-numeric:tabular-nums">${v:.2f}</span>'


def _cell_mult(val):
    """EV-multiple — XX.Xx. N/M for non-positive (negative EBITDA). Capped at 75x."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    if v <= 0:
        return '<span style="color:#9CA3AF;font-style:italic;font-variant-numeric:tabular-nums">N/M</span>'
    if v > _MULT_CAP:
        return '<span style="color:#9CA3AF;font-style:italic;font-variant-numeric:tabular-nums">N/M</span>'
    return f'<span style="font-variant-numeric:tabular-nums">{v:.1f}x</span>'


def _cell_ga_mult(val):
    """Growth-adjusted multiple (GA EV/Rev, GA EV/GP) — 2 decimal places, clips non-positive."""
    v = _safe_num(val)
    if v is None or v <= 0:
        return _cell_nd()
    return f'<span style="font-variant-numeric:tabular-nums">{v:.2f}x</span>'


def _cell_52wk_html(val):
    """% of 52-week high with green/yellow/red coding. val is 0-1 fraction."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    pct = v * 100
    text = f"{pct:.0f}%"
    color = "#111827"
    return f'<span style="color:{color};font-weight:500;font-variant-numeric:tabular-nums">{text}</span>'


def _cell_rev_growth_html(val):
    """Revenue growth % with color coding. val is 0-1 fraction."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    pct = v * 100
    text = f"({abs(pct):.0f}%)" if pct < 0 else f"{pct:.0f}%"
    color = "#111827"
    return f'<span style="color:{color};font-variant-numeric:tabular-nums">{text}</span>'


def _cell_gm_html(val):
    """Gross margin % — neutral color."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    pct = v * 100
    text = f"({abs(pct):.0f}%)" if pct < 0 else f"{pct:.0f}%"
    color = "#111827"
    return f'<span style="color:{color};font-variant-numeric:tabular-nums">{text}</span>'


def _cell_ebitda_mgn_html(val):
    """EBITDA margin % — negative values muted."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    pct = v * 100
    text = f"({abs(pct):.0f}%)" if pct < 0 else f"{pct:.0f}%"
    color = "#111827"
    return f'<span style="color:{color};font-variant-numeric:tabular-nums">{text}</span>'


def _cell_grr_html(val):
    """Gross Revenue Retention % — plain black text."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    v = int(round(v))
    return f'<span style="color:#111827;font-variant-numeric:tabular-nums">{v}%</span>'


def _cell_nrr_html(val):
    """Net Revenue Retention % — plain black text."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    v = int(round(v))
    return f'<span style="color:#111827;font-variant-numeric:tabular-nums">{v}%</span>'


def _cell_price_change_html(val):
    """Price change — muted color, no background pill."""
    v = _safe_num(val)
    if v is None:
        return _cell_nd()
    pct = v * 100
    if pct >= 0:
        text = f"{pct:.1f}%"
        color = "#059669"
    else:
        text = f"({abs(pct):.1f}%)"
        color = "#DC2626"
    return (
        f'<span style="color:{color};font-size:11.5px;font-weight:500;white-space:nowrap;'
        f'font-variant-numeric:tabular-nums">{text}</span>'
    )


def _cell_category_html(segment_key):
    """Segment category pill badge."""
    short = SEGMENT_SHORT.get(str(segment_key), str(segment_key))
    bg, fg = SEGMENT_PILL_COLORS.get(str(segment_key), ("#374151", "#D1D5DB"))
    safe = _html_lib.escape(short)
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:4px;font-size:11px;font-weight:600;white-space:nowrap;">'
        f'{safe}</span>'
    )


# ── DataFrame builder ────────────────────────────────────────────────────────

def build_comps_df(data, include_sub_segment=False):
    """
    Build a clean 19-column DataFrame from raw snapshot dicts.
    Units:
      mkt_cap_m, tev_m  — $M
      price             — dollars
      pct_52wk          — 0-1 fraction
      ev_*, ltm_*       — raw multiples (clipped to NaN if ≤ 0)
      rev_gr, cagr_3y, gm, ebitda_mgn — 0-1 fraction
      chg_2w, chg_2m    — 0-1 fraction
    Sorted by tev_m descending.
    """
    if not data:
        return pd.DataFrame()

    rows = []
    for d in data:
        mc  = d.get("market_cap")
        tev = d.get("enterprise_value")
        rg  = d.get("ntm_revenue_growth")
        em  = d.get("ebitda_margin")

        ltm_rev_raw  = d.get("ltm_revenue")
        ntm_rev_raw  = d.get("ntm_revenue")
        ltm_ebit_raw = d.get("ltm_ebitda")

        row = {
            "name":          d.get("name", ""),
            "ticker":        (d.get("ticker") or "").upper(),
            "segment":       d.get("segment", ""),
            "mkt_cap_m":     float(mc)  / 1e6 if mc  else None,
            "tev_m":         float(tev) / 1e6 if tev else None,
            "price":         d.get("current_price"),
            "pct_52wk":      d.get("pct_52wk_high"),
            "ev_rev":        d.get("ntm_tev_rev"),
            "ev_ebitda":     d.get("ntm_tev_ebitda"),
            "ev_gp":         d.get("ntm_tev_gp"),
            "ltm_rev_x":     d.get("ltm_tev_rev"),
            "ltm_ebitda_x":  d.get("ltm_tev_ebitda"),
            "ltm_gp_x":      d.get("ltm_tev_gp"),
            # Growth-adjusted multiples (EV/NTM Multiple ÷ NTM Growth rate)
            "ga_rev":        d.get("growth_adj_rev"),
            "ga_gp":         d.get("growth_adj_gp"),
            # Operating scale — raw absolute dollars converted to $M
            "ltm_rev_m":     float(ltm_rev_raw)  / 1e6 if ltm_rev_raw  is not None else None,
            "ntm_rev_m":     float(ntm_rev_raw)  / 1e6 if ntm_rev_raw               else None,
            "ltm_ebitda_m":  float(ltm_ebit_raw) / 1e6 if ltm_ebit_raw is not None else None,
            "rev_gr":        rg,
            "cagr_3y":       d.get("n3y_revenue_cagr"),
            "gm":            d.get("gross_margin"),
            "ebitda_mgn":    em,
            "chg_2w":        d.get("price_change_2w"),
            "chg_2m":        d.get("price_change_2m"),
        }
        if include_sub_segment:
            row["sub_segment"] = d.get("sub_segment", "")
        rows.append(row)

    df = pd.DataFrame(rows)

    # Ensure multiple columns are numeric; negative values are kept (rendered as N/M in cells)
    for col in ["ev_rev", "ev_ebitda", "ev_gp", "ltm_rev_x", "ltm_ebitda_x", "ltm_gp_x"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("tev_m", ascending=False, na_position="last")
    return df


def compute_comps_summary(df):
    """
    Compute mean and median for COMPS_NUMERIC_COLS.
    Columns in COMPS_NO_SUMMARY_COLS (raw dollar values like price, market cap,
    revenue, EBITDA) are skipped — they render as '—' in the summary rows.
    Multiple columns (MULTIPLE_COLS) exclude N/M (≤0) and capped (>75x) values,
    and require at least _MIN_SUMMARY_N valid observations.
    Returns (mean_dict, median_dict) — values are floats or None.
    """
    mean_d, median_d = {}, {}
    for col in COMPS_NUMERIC_COLS:
        if col in COMPS_NO_SUMMARY_COLS:
            mean_d[col] = median_d[col] = None
        elif col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce").dropna()
            if col in MULTIPLE_COLS:
                # Exclude N/M (≤0) and outlier-capped (>75x) from summary stats
                s = s[(s > 0) & (s <= _MULT_CAP)]
                if len(s) < _MIN_SUMMARY_N:
                    mean_d[col] = median_d[col] = None
                    continue
            mean_d[col]   = float(s.mean())   if len(s) else None
            median_d[col] = float(s.median()) if len(s) else None
        else:
            mean_d[col] = median_d[col] = None
    return mean_d, median_d
