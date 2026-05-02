"""
Valuation Lookback — How Multiples vs. Fundamentals Have Shifted Over Time.

Compares two real snapshot dates via side-by-side scatter plots, delta stat cards,
biggest movers tables, a migration bar chart, and a growth-regression table.

Only shows real data — synthetic/illustrative data is never generated.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit.components.v1 as components
from datetime import datetime, timedelta

import sqlite3
from config.settings import DB_PATH, SEGMENT_DISPLAY as _SEG_DISPLAY
from config.color_palette import SEGMENT_COLORS
from components.sidebar import render_sidebar

# ── Page config ──────────────────────────────────────────────────────────────���
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }
.stApp { background: #FAFBFC !important; }
.main .block-container {
    background: #FAFBFC !important;
    max-width: 100% !important;
    padding: 1.5rem 2rem !important;
}
h1, h2, h3, h4 { color: #111827 !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none !important; }
hr { border-color: #E5E7EB !important; margin: 1.2rem 0 !important; }

/* Control bar — tighter labels */
div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label,
div[data-testid="stCheckbox"] label {
    font-size: 9px !important;
    font-weight: 600 !important;
    color: #94A3B8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin-bottom: 2px !important;
}
div[data-testid="stSelectbox"] > div > div {
    font-size: 12px !important;
}
div[data-testid="stSelectbox"] > div > div,
div[data-testid="stMultiSelect"] > div > div {
    background: white !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
}
/* ── Scatter chart header bars — fixed height prevents vertical misalignment ── */
.chart-header {
    height: 38px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
    overflow: hidden !important;
    white-space: nowrap !important;
    text-overflow: ellipsis !important;
}
/* ── Multiselect tag pills — uniform muted style ── */
span[data-baseweb="tag"] {
    background: #F1F5F9 !important;
    border-radius: 4px !important;
}
span[data-baseweb="tag"] span {
    color: #475569 !important;
    font-size: 11px !important;
}
/* ── Number inputs (calculator) ── */
.stNumberInput > div > div > input {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #111827 !important;
    text-align: right !important;
    font-variant-numeric: tabular-nums !important;
    background: white !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
}
/* ── Expander ── */
details summary {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #374151 !important;
}
/* ── Horizontal radio — compact pill style ── */
div[data-testid="stRadio"] > div {
    flex-direction: row !important;
    gap: 0 !important;
}
div[data-testid="stRadio"] > div > label {
    padding: 4px 12px !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 6px !important;
    margin-right: 4px !important;
    background: white !important;
    cursor: pointer !important;
}
div[data-testid="stRadio"] > div > label[data-checked="true"] {
    background: #EFF6FF !important;
    border-color: #3B82F6 !important;
    color: #1D4ED8 !important;
}
</style>
""", unsafe_allow_html=True)

render_sidebar()

# ── Constants ─────────────────────────────────────────────────────────────────
# New lookback periods: 1W, 1M, 3M, 6M, 12M, YTD
LOOKBACK_OPTIONS = ["1W", "1M", "3M", "6M", "12M", "YTD"]

LOOKBACK_DAYS_MAP = {
    "1W":  7,
    "1M":  30,
    "3M":  90,
    "6M":  182,
    "12M": 365,
    # YTD is computed dynamically
}

CATEGORY_MAP = dict(_SEG_DISPLAY)
CATEGORY_COLORS_DISPLAY = {
    "Pharma":                              SEGMENT_COLORS.get("pharma", "#29335C"),
    "Consumer Health":                     SEGMENT_COLORS.get("consumer_health", "#7CEA9C"),
    "MedTech":                             SEGMENT_COLORS.get("medtech", "#F3A712"),
    "LST/Dx":                            SEGMENT_COLORS.get("life_sci_tools", "#DB2B39"),
    "Life Sci Tools / Dx / Bioprocessing": SEGMENT_COLORS.get("life_sci_tools", "#DB2B39"),
    "LST/Dx / Bioprocessing":            SEGMENT_COLORS.get("life_sci_tools", "#DB2B39"),
    "Asset-Light Services":                SEGMENT_COLORS.get("services", "#0D9488"),
    "Asset-Heavy Services":                SEGMENT_COLORS.get("cdmo", "#7C3AED"),
    "CDMOs":                               SEGMENT_COLORS.get("cdmo", "#7C3AED"),
    "Health Tech":                         SEGMENT_COLORS.get("health_tech", "#EC4899"),
}
CATEGORY_ORDER = list(CATEGORY_MAP.values())

# Default single dot color (Meritech-style teal) — used when not coloring by segment
DOT_COLOR = "#0D9488"
CATEGORY_PILLS = {
    "Pharma":                              ("#ECEEF6", "#29335C"),
    "Consumer Health":                     ("#EDFAF3", "#1D6A40"),
    "MedTech":                             ("#FEF9E7", "#A87000"),
    "LST/Dx":                            ("#FDEDEF", "#B01E29"),
    "Life Sci Tools / Dx / Bioprocessing": ("#FDEDEF", "#B01E29"),
    "LST/Dx / Bioprocessing":            ("#FDEDEF", "#B01E29"),
    "Asset-Light Services":                ("#E6FFFA", "#0F766E"),
    "Asset-Heavy Services":                ("#F5F3FF", "#5B21B6"),
    "CDMOs":                               ("#F5F3FF", "#5B21B6"),
    "Health Tech":                         ("#FDF2F8", "#9D174D"),
}

X_AXIS_MAP = {
    "NTM Revenue Growth %":  ("ntm_revenue_growth", "NTM Revenue Growth (%)"),
    "NTM EBITDA Margin %":   ("ntm_ebitda_margin",  "NTM EBITDA Margin (%)"),
    "NTM Gross Margin %":    ("gross_margin",        "NTM Gross Margin (%)"),
    "Rule of X":             ("rule_of_x",           "Rule of X (Growth + EBITDA Margin)"),
}
Y_AXIS_MAP = {
    "NTM EV/Revenue":    ("ntm_ev_revenue",    "NTM EV/Revenue"),
    "NTM EV/EBITDA":     ("ntm_ev_ebitda",     "NTM EV/EBITDA"),
    "NTM EV/GP":         ("ntm_ev_gp",         "NTM EV/GP"),
}
TEV_BANDS = {
    "< $1B":  (0, 1),
    "$1-3B":  (1, 3),
    "$3-5B":  (3, 5),
    "$5-10B": (5, 10),
    "> $10B": (10, None),
}
GROWTH_BANDS = {
    "< 10%":  (None, 10),
    "10-20%": (10, 20),
    "20-30%": (20, 30),
    "30-40%": (30, 40),
    "> 40%":  (40, None),
}

# Multiple cards: lower = good for PE buyers (compression is desirable)
_MULTIPLE_LABELS = {"AVG MULTIPLE", "MEDIAN MULTIPLE"}

# ── Source attribution helper ────��───────────────────────────────��────────────
def _source_attribution():
    st.markdown(
        '<div style="font-size:9px;color:#B0B7C3;margin-top:4px;">Source: FactSet</div>',
        unsafe_allow_html=True,
    )

# ── Section headers ───────────���───────────────────────────────────────────────

def _section_header(title, color="#6B7280"):
    st.markdown(
        f'<div style="margin:32px 0 16px 0;padding-bottom:8px;border-bottom:2px solid #E5E7EB;">'
        f'<span style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.06em;color:{color};">{title}</span></div>',
        unsafe_allow_html=True,
    )

# ── Formatting helpers ───────��────────────────────────────────────────────────

def _pill(cat):
    bg, fg = CATEGORY_PILLS.get(cat, ("#F3F4F6", "#6B7280"))
    return (f'<span style="background:{bg};color:{fg};padding:2px 7px;'
            f'border-radius:4px;font-size:10px;font-weight:500;">{cat}</span>')


def _fmt_mult(v, muted=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '<span style="color:#9CA3AF;">—</span>'
    if v >= 100:
        return '<span style="color:#9CA3AF;">&gt;100x</span>'
    c = "#6B7280" if muted else "#374151"
    return f'<span style="color:{c};font-variant-numeric:tabular-nums;">{v:.1f}x</span>'


def _fmt_val(v, suffix="", muted=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '<span style="color:#9CA3AF;">—</span>'
    c = "#6B7280" if muted else "#374151"
    return f'<span style="color:{c};font-variant-numeric:tabular-nums;">{v:.1f}{suffix}</span>'


def _fmt_delta_mult(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '<span style="color:#9CA3AF;">—</span>'
    if v < 0:
        return f'<span style="color:#DC2626;font-variant-numeric:tabular-nums;">({abs(v):.1f}x)</span>'
    return f'<span style="color:#16A34A;font-variant-numeric:tabular-nums;">+{v:.1f}x</span>'


def _fmt_delta_pp(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '<span style="color:#9CA3AF;">—</span>'
    if v < -1:
        return f'<span style="color:#DC2626;">({abs(v):.1f}pp)</span>'
    if v > 1:
        return f'<span style="color:#16A34A;">+{v:.1f}pp</span>'
    return f'<span style="color:#9CA3AF;">{v:+.1f}pp</span>'


def _fmt_gap_pct(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return '<span style="color:#9CA3AF;">—</span>'
    if v <= -40:
        return f'<span style="color:#166534;font-weight:600;">{v:+.0f}%</span>'
    if v <= -20:
        return f'<span style="color:#16A34A;">{v:+.0f}%</span>'
    if v <= -10:
        return f'<span style="color:#65A30D;">{v:+.0f}%</span>'
    if v <= 10:
        return f'<span style="color:#9CA3AF;">{v:+.0f}%</span>'
    if v <= 20:
        return f'<span style="color:#D97706;">{v:+.0f}%</span>'
    if v <= 40:
        return f'<span style="color:#DC2626;">{v:+.0f}%</span>'
    return f'<span style="color:#991B1B;font-weight:600;">{v:+.0f}%</span>'


def _gap_interp(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    if v <= -40:
        return '<span style="color:#166534;font-weight:600;">Deeply Cheap</span>'
    if v <= -20:
        return '<span style="color:#16A34A;">Cheap vs. History</span>'
    if v <= -10:
        return '<span style="color:#65A30D;">Slightly Cheap</span>'
    if v <= 10:
        return '<span style="color:#94A3B8;">In Line</span>'
    if v <= 20:
        return '<span style="color:#D97706;">Slightly Rich</span>'
    if v <= 40:
        return '<span style="color:#DC2626;">Rich vs. History</span>'
    return '<span style="color:#991B1B;font-weight:600;">Deeply Rich</span>'


def mover_signal_pill(multiple_delta, growth_delta):
    """Return a concise HTML pill badge for the signal type."""
    if pd.isna(multiple_delta) or pd.isna(growth_delta):
        return '<span style="color:#94A3B8;font-size:10px;">—</span>'
    md, gd = multiple_delta, growth_delta
    _p = lambda bg, fg, txt: (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;'
        f'border-radius:4px;font-size:10px;font-weight:600;">{txt}</span>'
    )
    if md < -2 and gd < -5:
        return _p("#FEF2F2", "#DC2626", "JUSTIFIED DERATE")
    if md < -2 and abs(gd) <= 3:
        return _p("#FFF7ED", "#C2410C", "UNJUSTIFIED DERATE")
    if md < -2 and gd > 3:
        return _p("#F0FDF4", "#16A34A", "OPPORTUNITY")
    if md > 2 and gd > 5:
        return _p("#F0FDF4", "#16A34A", "EARNED RERATE")
    if md > 2 and gd <= 0:
        return _p("#FEF2F2", "#DC2626", "FROTHY")
    if abs(md) <= 1:
        return '<span style="color:#94A3B8;font-size:10px;">STABLE</span>'
    return '<span style="color:#94A3B8;font-size:10px;">MODEST</span>'


def _safe_median(df, col):
    v = df[col].dropna()
    return float(v.median()) if len(v) else float("nan")


def _safe_mean(df, col):
    v = df[col].dropna()
    return float(v.mean()) if len(v) else float("nan")


# ── Lightweight OLS helpers (pure numpy, no sklearn) ──────────────────────────

class _LinReg:
    """Minimal OLS linear regression wrapper built on numpy."""
    __slots__ = ("coefs", "intercept", "r2", "n")

    def __init__(self, coefs, intercept, r2, n):
        self.coefs     = coefs
        self.intercept = intercept
        self.r2        = r2
        self.n         = n

    def predict_one(self, feature_vals):
        """Return scalar prediction for a single observation."""
        return float(np.dot(np.array(feature_vals, dtype=float), self.coefs)
                     + self.intercept)


def _numpy_fit(X_df, y_arr):
    """OLS fit via np.linalg.lstsq. X_df rows = observations, cols = features."""
    X = np.array(X_df, dtype=float)
    y = np.array(y_arr, dtype=float)
    A = np.column_stack([X, np.ones(len(X))])   # design matrix with intercept
    params, _, _, _ = np.linalg.lstsq(A, y, rcond=None)
    coefs, intercept = params[:-1], params[-1]
    y_pred = X @ coefs + intercept
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2     = max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0
    return _LinReg(coefs, intercept, r2, len(y))


def _fit_regression_models(df):
    """
    Fit multiple OLS models on df (current filtered universe).
    Returns dict of model specs; uses pure numpy — no sklearn dependency.
    """
    cols_needed = ["ntm_ev_revenue", "ntm_ev_ebitda", "ntm_revenue_growth",
                   "gross_margin", "ntm_ebitda_margin"]
    df_c = df.dropna(subset=cols_needed)
    if len(df_c) < 5:
        return {}

    models  = {}
    y_rev   = df_c["ntm_ev_revenue"].values
    y_ebitda = df_c["ntm_ev_ebitda"].values

    # ── EV/Revenue models ──────────���─────────────────────────���─────────────────
    for key, feats, display in [
        ("ev_rev_simple", ["ntm_revenue_growth"],
         ("Growth only",       ["NTM Rev Growth %"])),
        ("ev_rev_two",    ["ntm_revenue_growth", "gross_margin"],
         ("Growth + GM",       ["NTM Rev Growth %", "Gross Margin %"])),
        ("ev_rev_three",  ["ntm_revenue_growth", "gross_margin", "ntm_ebitda_margin"],
         ("Growth + GM + EBITDA Mgn", ["NTM Rev Growth %", "Gross Margin %", "NTM EBITDA Mgn %"])),
    ]:
        label_short, label_list = display
        models[key] = {
            "reg":      _numpy_fit(df_c[feats], y_rev),
            "features": feats,
            "display":  label_short,
            "labels":   label_list,
            "target":   "NTM EV/Revenue",
        }

    # ── EV/EBITDA models ───────────────���──────────────────────��────────────────
    for key, feats, display in [
        ("ev_ebitda_simple", ["ntm_revenue_growth"],
         ("Growth only",        ["NTM Rev Growth %"])),
        ("ev_ebitda_two",    ["ntm_revenue_growth", "ntm_ebitda_margin"],
         ("Growth + EBITDA Mgn", ["NTM Rev Growth %", "NTM EBITDA Mgn %"])),
    ]:
        label_short, label_list = display
        models[key] = {
            "reg":      _numpy_fit(df_c[feats], y_ebitda),
            "features": feats,
            "display":  label_short,
            "labels":   label_list,
            "target":   "NTM EV/EBITDA",
        }

    return models


# ── DB data loading ───────────���──────────────────────────���────────────────────

@st.cache_data(ttl=300)
def _all_snapshot_dates():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT snapshot_date FROM company_snapshots ORDER BY snapshot_date DESC"
    ).fetchall()
    conn.close()
    return [r["snapshot_date"] for r in rows]


@st.cache_data(ttl=300)
def _load_snapshot(snapshot_date: str):
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT ticker, name, segment, enterprise_value,
                  ntm_tev_rev, ntm_tev_ebitda, ntm_tev_gp, ntm_revenue_growth,
                  ebitda_margin, gross_margin, current_price
           FROM company_snapshots WHERE snapshot_date = ?
           ORDER BY enterprise_value DESC""",
        (snapshot_date,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=300)
def _all_daily_dates():
    """Return distinct dates from daily_multiples, newest first."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute(
            "SELECT DISTINCT date FROM daily_multiples ORDER BY date DESC"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


@st.cache_data(ttl=300)
def _load_daily_multiples(date_str: str):
    """Load multiples from daily_multiples for one specific date.

    Growth/margin fundamentals come from weekly Excel history rows.  If the
    target date is a daily-fetcher row (no growth data), we back-fill from
    the nearest weekly date within +/-7 days that does have growth data.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT ticker, segment, ntm_tev_rev, ntm_tev_ebitda, enterprise_value,
                  ntm_revenue_growth, gross_margin, ebitda_margin
           FROM daily_multiples WHERE date = ?""",
        (date_str,),
    ).fetchall()

    result = [dict(r) for r in rows]

    # If target date has no growth data, fill from nearest weekly date that does
    has_growth = any(r.get("ntm_revenue_growth") is not None for r in result)
    if not has_growth and result:
        nearby = conn.execute(
            """SELECT date FROM daily_multiples
               WHERE ntm_revenue_growth IS NOT NULL
                 AND date BETWEEN date(?, '-7 days') AND date(?, '+7 days')
               ORDER BY ABS(julianday(date) - julianday(?))
               LIMIT 1""",
            (date_str, date_str, date_str),
        ).fetchone()
        if nearby:
            growth_rows = conn.execute(
                """SELECT ticker, ntm_revenue_growth, gross_margin, ebitda_margin
                   FROM daily_multiples
                   WHERE date = ? AND ntm_revenue_growth IS NOT NULL""",
                (nearby[0],),
            ).fetchall()
            growth_map = {r["ticker"]: dict(r) for r in growth_rows}
            for rec in result:
                g = growth_map.get(rec["ticker"])
                if g:
                    if rec.get("ntm_revenue_growth") is None:
                        rec["ntm_revenue_growth"] = g.get("ntm_revenue_growth")
                    if rec.get("gross_margin") is None:
                        rec["gross_margin"] = g.get("gross_margin")
                    if rec.get("ebitda_margin") is None:
                        rec["ebitda_margin"] = g.get("ebitda_margin")

    conn.close()
    return result


def _build_hist_df_from_daily(daily_rows, df_current_fundamentals):
    """
    Build a historical DataFrame from daily_multiples rows.

    Historical multiples (Y-axis) come from real stored market data.
    Growth/margin fundamentals (X-axis) use actual stored historical values
    when available (from Excel history sheets), falling back to the current
    snapshot as proxy for any companies/dates where historical values are NULL.
    """
    if not daily_rows:
        return pd.DataFrame()
    df_dm = pd.DataFrame(daily_rows)
    df_dm = df_dm.rename(columns={
        "ntm_tev_rev":      "ntm_ev_revenue",
        "ntm_tev_ebitda":   "ntm_ev_ebitda",
        "enterprise_value": "_tev_raw",
    })
    df_dm["category"] = df_dm["segment"].map(CATEGORY_MAP).fillna("Other")
    df_dm["tev"] = df_dm["_tev_raw"].apply(
        lambda x: x / 1e9 if pd.notna(x) and x > 0 else np.nan
    )
    for col in ["ntm_ev_revenue", "ntm_ev_ebitda"]:
        df_dm[col] = pd.to_numeric(df_dm[col], errors="coerce")
        df_dm.loc[(df_dm[col] <= 0) | (df_dm[col] >= 100), col] = np.nan

    # Convert stored historical growth/margin decimals -> percentages (same as _raw_to_df)
    df_dm["ntm_revenue_growth"] = pd.to_numeric(df_dm.get("ntm_revenue_growth"), errors="coerce") * 100
    df_dm["ntm_ebitda_margin"]  = pd.to_numeric(df_dm.get("ebitda_margin"), errors="coerce") * 100
    df_dm["gross_margin"]       = pd.to_numeric(df_dm.get("gross_margin"), errors="coerce") * 100

    # daily_multiples does not have ntm_tev_gp — set to NaN
    if "ntm_ev_gp" not in df_dm.columns:
        df_dm["ntm_ev_gp"] = np.nan

    # Compute Rule of X = NTM Revenue Growth % + NTM EBITDA Margin %
    df_dm["rule_of_x"] = df_dm["ntm_revenue_growth"] + df_dm["ntm_ebitda_margin"]

    # Merge in current fundamentals for company name + as fallback for NaN growth/margin
    fund_cols = ["ticker", "company", "ntm_revenue_growth", "ntm_ebitda_margin",
                 "gross_margin"]
    avail_fund = [c for c in fund_cols if c in df_current_fundamentals.columns]
    df_fund = df_current_fundamentals[avail_fund].drop_duplicates("ticker")

    # Rename fund columns to avoid collision on merge (suffix _proxy)
    proxy_rename = {c: f"{c}_proxy" for c in avail_fund if c not in ("ticker", "company")}
    df_fund = df_fund.rename(columns=proxy_rename)

    df_dm = df_dm.merge(df_fund, on="ticker", how="left")

    # Fill NaN historical values with current proxy (graceful fallback)
    for real_col, proxy_col in proxy_rename.items():
        if real_col in df_dm.columns and proxy_col in df_dm.columns:
            df_dm[real_col] = df_dm[real_col].fillna(df_dm[proxy_col])
            df_dm.drop(columns=[proxy_col], inplace=True)
        elif proxy_col in df_dm.columns:
            df_dm.rename(columns={proxy_col: real_col}, inplace=True)

    return df_dm


def _raw_to_df(rows):
    """Convert raw DB rows to the working DataFrame with all derived columns."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df = df.rename(columns={
        "name":             "company",
        "enterprise_value": "_tev_raw",
        "ntm_tev_rev":      "ntm_ev_revenue",
        "ntm_tev_ebitda":   "ntm_ev_ebitda",
        "ntm_tev_gp":       "ntm_ev_gp",
        "current_price":    "stock_price",
    })
    df["category"] = df["segment"].map(CATEGORY_MAP).fillna("Other")
    df["tev"]      = df["_tev_raw"].apply(
        lambda x: x / 1e9 if pd.notna(x) and x > 0 else np.nan
    )
    # Decimals -> percentages
    df["ntm_revenue_growth"] = pd.to_numeric(df["ntm_revenue_growth"], errors="coerce") * 100
    df["ntm_ebitda_margin"]  = pd.to_numeric(df["ebitda_margin"],       errors="coerce") * 100
    df["gross_margin"]       = pd.to_numeric(df["gross_margin"],        errors="coerce") * 100
    # Sanitise multiples: non-positive or DB sentinel (>= 100x) -> NaN
    for col in ["ntm_ev_revenue", "ntm_ev_ebitda", "ntm_ev_gp"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            df.loc[(df[col] <= 0) | (df[col] >= 100), col] = np.nan
        else:
            df[col] = np.nan

    # Compute Rule of X = NTM Revenue Growth % + NTM EBITDA Margin %
    df["rule_of_x"] = df["ntm_revenue_growth"] + df["ntm_ebitda_margin"]

    return df


def _find_nearest_date(all_dates, target_str, max_gap_days=45):
    if not all_dates:
        return None
    target  = datetime.strptime(target_str, "%Y-%m-%d").date()
    nearest = min(all_dates, key=lambda d: abs(
        datetime.strptime(d, "%Y-%m-%d").date() - target
    ))
    gap = abs(datetime.strptime(nearest, "%Y-%m-%d").date() - target)
    return nearest if gap.days <= max_gap_days else None


def _period_to_target(period, current_date_str):
    current_date = datetime.strptime(current_date_str, "%Y-%m-%d").date()
    if period == "YTD":
        return current_date.replace(month=1, day=1).strftime("%Y-%m-%d")
    days = LOOKBACK_DAYS_MAP.get(period, 30)
    return (current_date - timedelta(days=days)).strftime("%Y-%m-%d")


def _available_periods(all_dates, current_date_str):
    """Return ordered list of periods with a real historical snapshot != current date."""
    result = []
    for period in LOOKBACK_OPTIONS:
        target  = _period_to_target(period, current_date_str)
        nearest = _find_nearest_date(all_dates, target, max_gap_days=45)
        if nearest and nearest != current_date_str:
            result.append(period)
    return result


# ── Axis / scatter helpers ────────────────────────────────────────────────────

def _nice_min(s):
    c = s.dropna()
    if len(c) == 0: return -5
    mn = float(c.quantile(0.02))
    return (mn * 1.15) if mn < 0 else max(-5, mn - abs(mn) * 0.15)


def _nice_max(s, pad=1.15):
    c = s.dropna()
    if len(c) == 0: return 20
    return float(c.quantile(0.98)) * pad


def _grid_bins(s, n=3):
    c = s.dropna()
    if len(c) < 4: return None
    lo, hi = float(c.quantile(0.05)), float(c.quantile(0.95))
    if hi <= lo: return None
    step = (hi - lo) / n
    bins = [lo + i * step for i in range(n + 1)]
    bins[0]  = float(c.min()) - 0.1
    bins[-1] = float(c.max()) + 0.1
    return bins


def _dot_size(tev):
    """2-tier dot sizes: large-cap ($20B+) vs. everyone else."""
    if pd.isna(tev): return 8
    if tev >= 20:    return 12
    return 8


def _get_outlier_labels(df, x_col, y_col):
    """Label only clear visual outliers — ~5-8 dots far from the pack."""
    labels = [""] * len(df)
    if len(df) < 5:
        return [str(r.get("ticker", "")) for _, r in df.iterrows()]

    x_mean, x_std = df[x_col].mean(), df[x_col].std()
    y_mean, y_std = df[y_col].mean(), df[y_col].std()

    top_y = set(df.nlargest(3, y_col).index)
    bot_y = set(df.nsmallest(2, y_col).index)
    top_x = set(df.nlargest(2, x_col).index)
    bot_x = set(df.nsmallest(2, x_col).index)

    for idx in (top_y | bot_y | top_x | bot_x):
        row  = df.loc[idx]
        x_z  = abs((row[x_col] - x_mean) / x_std) if x_std > 0 else 0
        y_z  = abs((row[y_col] - y_mean) / y_std) if y_std > 0 else 0
        if x_z > 1.2 or y_z > 1.2:
            labels[df.index.get_loc(idx)] = str(row.get("ticker", ""))

    return labels


# ── Scatter chart builder ────────��───────────────────────────────��────────────

def build_scatter(df, x_col, y_col, x_label, y_label,
                  show_grid_avgs, x_range, y_range,
                  reg_coeffs=None, r_sq=None):
    fig   = go.Figure()
    valid = df.dropna(subset=[x_col, y_col]).reset_index(drop=True)

    if valid.empty:
        return fig

    # Dot sizes — 2-tier
    sizes = valid["tev"].apply(_dot_size).tolist()

    # No labels on dots
    labels = [""] * len(valid)

    # Colors — always per-segment
    colors = [CATEGORY_COLORS_DISPLAY.get(c, "#9CA3AF") for c in valid["category"]]

    # ── Hover card — pre-formatted strings for clean two-column alignment ────────
    _HOVER_LABELS = {
        "ntm_ev_revenue":    "NTM EV/Revenue",
        "ntm_ev_ebitda":     "NTM EV/EBITDA",
        "ntm_ev_gp":         "NTM EV/GP",
        "ntm_revenue_growth":"NTM Rev Growth",
        "ntm_ebitda_margin": "EBITDA Margin",
        "gross_margin":      "Gross Margin",
        "rule_of_x":         "Rule of X",
        "n3y_revenue_cagr":  "3Y Rev CAGR",
        "growth_adj_rev":    "Growth-Adj Rev",
        "growth_adj_gp":     "Growth-Adj GP",
    }
    x_hover = _HOVER_LABELS.get(x_col, x_label)
    y_hover = _HOVER_LABELS.get(y_col, y_label)

    def _fmt_val_hover(val, metric):
        m = metric.lower()
        if pd.isna(val):
            return "—"
        if "ev/" in m or ("revenue" in m and "growth" not in m and "cagr" not in m):
            return f"{val:.1f}x"
        if "growth" in m or "margin" in m or "cagr" in m:
            return f"{val:.0f}%"
        if "rule" in m:
            return f"{val:.0f}"
        return f"{val:.1f}"

    # Monospace hover card: pre-combined rows with trailing padding so Plotly
    # allocates the correct box width (prevents teal values clipping at right edge)
    x_vals_str = [_fmt_val_hover(v, x_hover) for v in valid[x_col]]
    y_vals_str = [_fmt_val_hover(v, y_hover) for v in valid[y_col]]
    max_val_w  = max(
        max((len(s) for s in x_vals_str), default=4),
        max((len(s) for s in y_vals_str), default=4),
    )
    label_w   = max(len(x_hover), len(y_hover))
    x_lbl_pad = x_hover.ljust(label_w)
    y_lbl_pad = y_hover.ljust(label_w)
    pad_total = label_w + 2 + max_val_w + 6   # 6 extra chars of breathing room

    # Pre-combine label + rjust value into one string; trailing spaces widen the box
    x_rows = [(x_lbl_pad + "  " + s.rjust(max_val_w)).ljust(pad_total) for s in x_vals_str]
    y_rows = [(y_lbl_pad + "  " + s.rjust(max_val_w)).ljust(pad_total) for s in y_vals_str]

    # customdata: [0] company  [1] ticker  [2] x_row  [3] y_row
    hover_custom = np.column_stack([
        valid["company"].fillna("").values,
        valid["ticker"].fillna("").values,
        x_rows,
        y_rows,
    ])

    hovertemplate = (
        "<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
        "<br>"
        "%{customdata[2]}<br>"
        "%{customdata[3]}"
        "<extra></extra>"
    )

    # ── SINGLE trace for ALL dots (fixes multi-trace hover dead zones) ──────────
    fig.add_trace(go.Scatter(
        x=valid[x_col], y=valid[y_col],
        mode="markers+text",
        name="",
        marker=dict(
            size=sizes,
            color=colors,
            opacity=0.8,
            line=dict(color="white", width=1.2),
        ),
        selected=dict(marker=dict(opacity=1.0)),
        unselected=dict(marker=dict(opacity=0.28)),
        text=labels,
        textposition="top right",
        textfont=dict(size=9, color="#475569", family="DM Sans"),
        customdata=hover_custom,
        hovertemplate=hovertemplate,
        showlegend=False,
    ))

    # Phantom legend traces — segment colors always shown
    for cat in CATEGORY_ORDER:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=8, color=CATEGORY_COLORS_DISPLAY.get(cat, "#9CA3AF")),
            name=cat, showlegend=True,
        ))

    # Grid averages — nearly invisible, structure without distraction
    if show_grid_avgs:
        xb = _grid_bins(df[x_col].dropna(), 3)
        yb = _grid_bins(df[y_col].dropna(), 4)
        if xb and yb:
            for i in range(len(xb) - 1):
                for j in range(len(yb) - 1):
                    xl, xh = xb[i], xb[i + 1]
                    yl, yh = yb[j], yb[j + 1]
                    cell   = df[
                        df[x_col].between(xl, xh) & df[y_col].between(yl, yh)
                    ].dropna(subset=[x_col, y_col])
                    if len(cell) < 2:
                        continue
                    avg = float(cell[y_col].mean())
                    fig.add_shape(
                        type="rect", x0=xl, x1=xh, y0=yl, y1=yh,
                        line=dict(color="#F1F5F9", width=0.3, dash="dot"),
                        fillcolor="rgba(0,0,0,0)",
                    )
                    fig.add_annotation(
                        x=(xl + xh) / 2, y=(yl + yh) / 2,
                        text=f"{avg:.1f}x",
                        showarrow=False,
                        font=dict(size=9, color="#C8CED6"),
                        bgcolor="rgba(255,255,255,0.5)",
                        bordercolor="rgba(0,0,0,0)", borderpad=2,
                    )

    # Regression line — dotted red like Meritech, R^2 top-right
    if reg_coeffs is not None and len(valid) >= 3:
        xr = np.linspace(x_range[0], x_range[1], 60)
        yr = np.polyval(reg_coeffs, xr).clip(0)
        fig.add_trace(go.Scatter(
            x=xr, y=yr,
            mode="lines",
            line=dict(color="#EF4444", width=1.5, dash="dot"),
            name="Regression fit",
            showlegend=False,
            hoverinfo="skip",
        ))
        if r_sq is not None:
            fig.add_annotation(
                text=f"R\u00b2 = {r_sq:.2f}",
                xref="paper", yref="paper",
                x=0.98, y=0.98,
                xanchor="right", yanchor="top",
                showarrow=False,
                font=dict(size=11, color="#EF4444", family="DM Sans"),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=4,
                bordercolor="rgba(0,0,0,0)",
            )

    # Median crosshairs — very faint, edge-annotated
    if not valid.empty:
        mx = float(valid[x_col].median())
        my = float(valid[y_col].median())
        fig.add_hline(y=my, line_dash="dash", line_color="#D1D5DB", line_width=0.5)
        fig.add_vline(x=mx, line_dash="dash", line_color="#D1D5DB", line_width=0.5)
        fig.add_annotation(
            x=1.0, y=my, xref="paper", yref="y",
            text=f"Med: {my:.1f}x", showarrow=False,
            font=dict(size=8, color="#94A3B8"), xanchor="left",
        )
        fig.add_annotation(
            x=mx, y=1.0, xref="x", yref="paper",
            text=f"Med: {mx:.1f}", showarrow=False,
            font=dict(size=8, color="#94A3B8"), yanchor="bottom",
        )

    # X-axis tick labels: parentheses for negative percentages
    x_min, x_max = x_range[0], x_range[1]
    raw_step = (x_max - x_min) / 6.0
    tick_step = next((n for n in [1, 2, 5, 10, 20, 25, 50, 100] if n >= raw_step), 100)
    tick_vals = np.arange(
        np.ceil(x_min / tick_step)  * tick_step,
        np.floor(x_max / tick_step) * tick_step + tick_step * 0.1,
        tick_step,
    )
    is_pct = any(kw in x_col for kw in ("growth", "margin", "rule"))
    if is_pct:
        tick_texts = [f"({abs(v):.0f}%)" if v < 0 else f"{v:.0f}%" for v in tick_vals]
    else:
        tick_texts = [f"{v:.1f}" for v in tick_vals]

    fig.update_layout(
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="DM Sans, sans-serif", size=11, color="#111827"),
        xaxis=dict(
            title=dict(text=""),
            range=x_range, gridcolor="#F3F4F6", gridwidth=0.5,
            showline=True, linecolor="#E5E7EB", linewidth=1,
            tickfont=dict(size=10, color="#111827", family="DM Sans"),
            zeroline=False,
            tickvals=tick_vals.tolist(), ticktext=tick_texts,
            showspikes=True, spikemode="across", spikesnap="cursor",
            spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
        ),
        yaxis=dict(
            title=dict(text=y_label, font=dict(size=11, color="#111827"), standoff=12),
            range=y_range, gridcolor="#F3F4F6", gridwidth=0.5,
            showline=True, linecolor="#E5E7EB", linewidth=1,
            tickfont=dict(size=10, color="#111827", family="DM Sans"),
            zeroline=False,
            ticksuffix="%" if y_col == "ntm_revenue_growth" else "x",
            showspikes=True, spikemode="across", spikesnap="cursor",
            spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0,
            font=dict(size=9, color="#111827", family="DM Sans"),
            itemsizing="constant", tracegroupgap=2, itemwidth=30,
            bgcolor="rgba(0,0,0,0)",
        ),
        height=650,
        margin=dict(l=60, r=30, t=20, b=80),
        showlegend=True,
        hovermode="closest",
        hoverdistance=25,
        spikedistance=-1,
        clickmode="event+select",
        dragmode="zoom",
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E2E8F0",
            font=dict(size=11, color="#374151", family="Menlo, Monaco, Consolas, monospace"),
            align="left",
            namelength=0,
        ),
    )
    # Place x-axis title as an annotation so it reliably renders below tick labels
    fig.add_annotation(
        xref="paper", yref="paper",
        x=0.5, y=-0.11,
        text=x_label,
        showarrow=False,
        font=dict(size=11, color="#6B7280", family="DM Sans"),
        xanchor="center", yanchor="top",
    )
    return fig


# ── Migration bar chart ────────────────────────────────────────────────────────

def build_migration_bar_chart(df_delta, y_col, y_label, top_n=20):
    """Horizontal bar: biggest multiple movers, direction-colored (gray=compression, blue=expansion)."""
    _is_pct = y_col == "ntm_revenue_growth"
    _unit   = "%" if _is_pct else "x"

    df_show = df_delta.copy()
    df_show["_abs"] = df_show["multiple_delta"].abs()
    df_show = df_show.nlargest(top_n, "_abs").sort_values("multiple_delta", ascending=True)

    n        = len(df_show)
    y_then_c = f"{y_col}_then"
    y_now_c  = f"{y_col}_now"

    # Direction-based colors: light red = compression, green = expansion
    bar_colors = [
        "#F87171" if v < 0 else "#22C55E"
        for v in df_show["multiple_delta"]
    ]

    # customdata: company, category, then-value, now-value
    custom = list(zip(
        df_show["company"].fillna("\u2014"),
        df_show["category"].fillna("\u2014"),
        df_show[y_then_c].fillna(0),
        df_show[y_now_c].fillna(0),
    ))

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_show["ticker"],
        x=df_show["multiple_delta"],
        orientation="h",
        marker=dict(
            color=bar_colors,
            line=dict(width=0),
            cornerradius=3,
        ),
        opacity=0.90,
        customdata=custom,
        text=[f"({abs(v):.1f}{_unit})" if v < 0 else f"+{v:.1f}{_unit}"
              for v in df_show["multiple_delta"]],
        textposition="outside",
        textfont=dict(size=9, color="#6B7280", family="DM Sans"),
        hovertemplate=(
            "<b>%{customdata[0]}</b> \u00b7 %{customdata[1]}<br>"
            f"Then: %{{customdata[2]:.1f}}{_unit} \u2192 Now: %{{customdata[3]:.1f}}{_unit}<br>"
            f"\u0394: %{{x:+.1f}}{_unit}<br><extra></extra>"
        ),
    ))
    fig.update_layout(
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font=dict(family="DM Sans, sans-serif", color="#6B7280", size=11),
        bargap=0.35,
        xaxis=dict(
            showgrid=True,
            gridcolor="#F3F4F6",
            zeroline=True,
            zerolinecolor="#9CA3AF",
            zerolinewidth=1.2,
            ticksuffix=_unit,
            showline=False,
            tickfont=dict(size=9, color="#9CA3AF"),
            title=None,
        ),
        yaxis=dict(
            showgrid=False,
            tickfont=dict(size=10, color="#374151"),
            autorange="reversed",
        ),
        height=max(400, n * 28 + 60),
        margin=dict(l=60, r=50, t=10, b=40),
        showlegend=False,
    )

    # Subtle "0x" annotation below the zero line
    fig.add_annotation(
        x=0, y=-0.5,
        xref="x", yref="y",
        text="0x",
        showarrow=False,
        font=dict(size=8, color="#9CA3AF"),
        xanchor="center", yanchor="top",
    )

    return fig


# ─��� Segment summary boxes ────────��────────────────────────────────────────────

# Use SEGMENT_COLORS from config.color_palette for canonical colors
_SEG_META = [
    {"label": "All",             "short": "All",     "color": "#475569", "bg": "#F8FAFC", "border": "#E2E8F0"},
    {"label": "Pharma",          "short": "Pharma",  "color": SEGMENT_COLORS.get("pharma", "#1D4ED8"),        "bg": "#E9EFFC", "border": SEGMENT_COLORS.get("pharma", "#1D4ED8")},
    {"label": "Consumer Health", "short": "CH",      "color": SEGMENT_COLORS.get("consumer_health", "#047857"), "bg": "#E6F4EE", "border": SEGMENT_COLORS.get("consumer_health", "#047857")},
    {"label": "MedTech",         "short": "MedTech", "color": SEGMENT_COLORS.get("medtech", "#B91C1C"),       "bg": "#FCEAEA", "border": SEGMENT_COLORS.get("medtech", "#B91C1C")},
    {"label": "LST/Dx",              "short": "LST",     "color": SEGMENT_COLORS.get("life_sci_tools", "#6D28D9"), "bg": "#F1EAFB", "border": SEGMENT_COLORS.get("life_sci_tools", "#6D28D9")},
    {"label": "Asset-Light Services", "short": "A-Light", "color": SEGMENT_COLORS.get("services", "#B45309"),      "bg": "#FEF3E2", "border": SEGMENT_COLORS.get("services", "#B45309")},
    {"label": "Asset-Heavy Services", "short": "A-Heavy", "color": SEGMENT_COLORS.get("cdmo", "#C2410C"),          "bg": "#FDECE0", "border": SEGMENT_COLORS.get("cdmo", "#C2410C")},
    {"label": "Health Tech",     "short": "HCIT",    "color": SEGMENT_COLORS.get("health_tech", "#0E7490"),   "bg": "#E2F1F5", "border": SEGMENT_COLORS.get("health_tech", "#0E7490")},
]


def render_segment_summary_boxes(df_hist, df_current, y_col, y_label, category_filter):
    """Row of small stat boxes: median Then -> Now by segment + total universe.

    Layout: flex-wrap with 25% width so boxes flow into rows of 4+4 (including All).
    No segment is isolated on its own row.
    """
    boxes_html = ""
    visible_segs = []
    for seg in _SEG_META:
        lbl = seg["label"]
        # Skip deselected segments; always show All
        if lbl != "All" and lbl not in category_filter:
            continue
        visible_segs.append(seg)

    for seg in visible_segs:
        lbl = seg["label"]

        if lbl == "All":
            t_vals = df_hist[y_col].dropna()
            n_vals = df_current[y_col].dropna()
        else:
            t_vals = df_hist[df_hist["category"] == lbl][y_col].dropna()
            n_vals = df_current[df_current["category"] == lbl][y_col].dropna()

        if len(t_vals) and len(n_vals):
            med_t = t_vals.median()
            med_n = n_vals.median()
            avg_t = t_vals.mean()
            avg_n = n_vals.mean()
            delta = med_n - med_t
            delta_pct = (delta / med_t * 100) if med_t else 0.0

            if delta < -0.1:
                arrow, dc = "\u25bc", "#16A34A"
            elif delta > 0.1:
                arrow, dc = "\u25b2", "#DC2626"
            else:
                arrow, dc = "\u2014", "#94A3B8"

            then_s  = f"{med_t:.1f}x"
            now_s   = f"{med_n:.1f}x"
            delta_s = f"{arrow} {abs(delta):.1f}x ({abs(delta_pct):.0f}%)"
            avg_s   = f"Avg: {avg_t:.1f}x \u2192 {avg_n:.1f}x"
            count_s = f"{len(n_vals)} cos."
        else:
            then_s = now_s = delta_s = "\u2014"
            dc = "#94A3B8"
            avg_s = count_s = ""

        boxes_html += (
            f'<div style="flex:1 1 calc(25% - 10px);min-width:140px;max-width:260px;'
            f'background:{seg["bg"]};'
            f'border:1px solid {seg["border"]};border-radius:8px;'
            f'padding:10px 12px;text-align:center;">'

            # Segment label — readable font size with good contrast
            f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.05em;color:{seg["color"]};margin-bottom:6px;">'
            f'{seg["short"]}</div>'

            # Then -> Now values
            f'<div style="display:flex;justify-content:center;align-items:baseline;'
            f'gap:6px;margin-bottom:4px;">'
            f'  <div style="text-align:center;">'
            f'    <div style="font-size:9px;color:#64748B;text-transform:uppercase;font-weight:500;">Then</div>'
            f'    <div style="font-size:18px;font-weight:600;color:#475569;'
            f'font-variant-numeric:tabular-nums;">{then_s}</div>'
            f'  </div>'
            f'  <div style="font-size:14px;color:#94A3B8;">\u2192</div>'
            f'  <div style="text-align:center;">'
            f'    <div style="font-size:9px;color:#64748B;text-transform:uppercase;font-weight:500;">Now</div>'
            f'    <div style="font-size:18px;font-weight:700;color:#111827;'
            f'font-variant-numeric:tabular-nums;">{now_s}</div>'
            f'  </div>'
            f'</div>'

            # Delta line
            f'<div style="font-size:12px;font-weight:600;color:{dc};'
            f'font-variant-numeric:tabular-nums;margin-bottom:2px;">{delta_s}</div>'

            # Mean subtext + count
            f'<div style="font-size:9px;color:#64748B;">{avg_s}</div>'
            f'<div style="font-size:9px;color:#94A3B8;">{count_s}</div>'
            f'</div>'
        )

    st.markdown(
        f'<div style="font-size:11px;font-weight:600;color:#6B7280;text-transform:uppercase;'
        f'letter-spacing:0.05em;margin-bottom:8px;">Median {y_label} by Segment</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap;">'
        f'{boxes_html}</div>',
        unsafe_allow_html=True,
    )
    _source_attribution()


# ── HTML table constants & builders ────────────���──────────────────────────────
_TD  = ("padding:6px 10px;font-size:12px;border-bottom:1px solid #F3F4F6;"
        "text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;")
_TDL = _TD.replace("text-align:right;", "text-align:left;")
_TH  = ("padding:7px 10px;font-size:9px;font-weight:500;text-transform:uppercase;"
        "letter-spacing:0.04em;color:#94A3B8;background:#FFFFFF;"
        "border-bottom:1px solid #E5E7EB;white-space:nowrap;text-align:right;")
_THL = _TH.replace("text-align:right;", "text-align:left;")


def _wrap_table(inner_html):
    return (
        '<div style="background:white;border:1px solid #E5E7EB;border-radius:12px;'
        'overflow:auto;box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
        f'<table style="width:100%;border-collapse:collapse;">{inner_html}</table></div>'
    )


def _build_movers_table(df, y_col, x_col, ascending, top_n=None):
    """Build an HTML compression/expansion table. Shows all companies when top_n is None."""
    if top_n is None:
        df_s = df.sort_values("multiple_delta", ascending=ascending).reset_index(drop=True)
    else:
        df_s = df.sort_values("multiple_delta", ascending=ascending).head(top_n).reset_index(drop=True)

    has_growth_then = df_s[f"{x_col}_then"].notna().any()

    _SEG_COLORS_LOCAL = {
        "Pharma":                SEGMENT_COLORS.get("pharma", "#2563EB"),
        "Consumer Health":       SEGMENT_COLORS.get("consumer_health", "#059669"),
        "MedTech":               SEGMENT_COLORS.get("medtech", "#DC2626"),
        "LST/Dx":              SEGMENT_COLORS.get("life_sci_tools", "#7C3AED"),
        "Life Sci Tools":        SEGMENT_COLORS.get("life_sci_tools", "#7C3AED"),
        "Asset-Light Services":  SEGMENT_COLORS.get("services", "#F59E0B"),
        "Services":              SEGMENT_COLORS.get("services", "#F59E0B"),
        "Asset-Heavy Services":  SEGMENT_COLORS.get("cdmo", "#EA580C"),
        "CDMOs":                 SEGMENT_COLORS.get("cdmo", "#EA580C"),
        "Health Tech":           SEGMENT_COLORS.get("health_tech", "#0891B2"),
    }
    _TH_S = (
        "background:#F9FAFB;color:#6B7280;font-size:9px;text-transform:uppercase;"
        "letter-spacing:0.05em;padding:8px 10px;font-weight:600;white-space:nowrap;"
        "border-bottom:1px solid #E5E7EB;"
    )
    _TD_S  = "padding:8px 10px;border-bottom:1px solid #F3F4F6;font-variant-numeric:tabular-nums;"
    _MONO  = "font-family:Menlo,Monaco,Consolas,monospace;font-size:11px;white-space:nowrap;"

    # ── Header ─────────��──────────────────────────────────────────────────────
    col_defs = [
        ("#",         "text-align:right;width:30px;"),
        ("Company",   "text-align:left;"),
        ("Multiple",  "text-align:left;"),
        ("Chg",       "text-align:left;"),
        ("Growth",    "text-align:left;"),
    ]
    if has_growth_then:
        col_defs += [("Chg", "text-align:left;"), ("Implied", "text-align:center;")]

    hdr_html = "".join(
        f'<th style="{_TH_S}{extra}">{label}</th>'
        for label, extra in col_defs
    )

    # ── Rows ─────────────��────────────────────────────────��───────────────────
    rows_html = ""
    for rank, (_, r) in enumerate(df_s.iterrows(), 1):
        bg = "#FFFFFF" if rank % 2 == 1 else "#FAFBFC"

        # Segment dot
        cat       = r.get("category", "")
        dot_color = _SEG_COLORS_LOCAL.get(cat, "#94A3B8")
        dot_html  = (
            f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;'
            f'background:{dot_color};margin-right:6px;vertical-align:middle;"></span>'
        )

        # Company name as clickable link to Company Profile page
        ticker = r.get("ticker", "")
        company_name = r.get("company", ticker)
        company_link = (
            f'<a href="/Company?ticker={ticker}" target="_self" '
            f'style="color:#111827;text-decoration:none;border-bottom:1px dotted #CBD5E1;" '
            f'onmouseover="this.style.color=\'#2563EB\';this.style.borderBottomColor=\'#2563EB\'" '
            f'onmouseout="this.style.color=\'#111827\';this.style.borderBottomColor=\'#CBD5E1\'">'
            f'{company_name}</a>'
        )

        # Multiple Then -> Now
        m_then = r.get(f"{y_col}_then")
        m_now  = r.get(f"{y_col}_now")
        mt_s   = f"{m_then:.1f}x" if pd.notna(m_then) else "\u2014"
        mn_s   = f"{m_now:.1f}x"  if pd.notna(m_now)  else "\u2014"
        mult_cell = (
            f'<span style="color:#94A3B8;">{mt_s}</span>'
            f'<span style="color:#CBD5E1;"> \u2192 </span>'
            f'<b style="color:#111827;">{mn_s}</b>'
        )

        # Delta Multiple  (abs x) + (pct%)
        d     = r.get("multiple_delta")
        d_pct = r.get("multiple_delta_pct")
        if pd.notna(d) and pd.notna(d_pct):
            if d < 0:
                delta_cell = (
                    f'<span style="color:#DC2626;white-space:nowrap;">'
                    f'({abs(d):.1f}x) ({abs(d_pct):.0f}%)</span>'
                )
            else:
                delta_cell = (
                    f'<span style="color:#16A34A;white-space:nowrap;">'
                    f'+{d:.1f}x (+{d_pct:.0f}%)</span>'
                )
        else:
            delta_cell = "\u2014"

        # Growth Then -> Now
        g_then = r.get(f"{x_col}_then")
        g_now  = r.get(f"{x_col}_now")
        gt_s   = f"{g_then:.0f}%" if pd.notna(g_then) else "\u2014"
        gn_s   = f"{g_now:.0f}%"  if pd.notna(g_now)  else "\u2014"
        growth_cell = (
            f'<span style="color:#94A3B8;">{gt_s}</span>'
            f'<span style="color:#CBD5E1;"> \u2192 </span>'
            f'<b style="color:#111827;">{gn_s}</b>'
        )

        rows_html += (
            f'<tr style="background:{bg};" '
            f'onmouseover="this.style.background=\'#EFF6FF\'" '
            f'onmouseout="this.style.background=\'{bg}\'">'
            f'<td style="{_TD_S}text-align:right;color:#94A3B8;font-size:11px;width:30px;">{rank}</td>'
            f'<td style="{_TD_S}font-size:12px;white-space:nowrap;">'
            f'{dot_html}{company_link}</td>'
            f'<td style="{_TD_S}{_MONO}">{mult_cell}</td>'
            f'<td style="{_TD_S}{_MONO}">{delta_cell}</td>'
            f'<td style="{_TD_S}{_MONO}">{growth_cell}</td>'
        )

        if has_growth_then:
            # Delta Growth (pp)
            gd = r.get("fundamental_delta")
            if pd.notna(gd):
                if gd < 0:
                    gd_cell = f'<span style="color:#DC2626;">{gd:.0f}pp</span>'
                elif gd > 0:
                    gd_cell = f'<span style="color:#16A34A;">+{gd:.0f}pp</span>'
                else:
                    gd_cell = '<span style="color:#94A3B8;">0pp</span>'
            else:
                gd_cell = "\u2014"

            # Implied
            implied_cell = "\u2014"
            if pd.notna(d_pct) and pd.notna(gd):
                gap = d_pct - (gd * 3)
                if gap < -15:
                    implied_cell = '<span style="color:#16A34A;font-weight:600;">Cheap</span>'
                elif gap > 15:
                    implied_cell = '<span style="color:#DC2626;font-weight:600;">Rich</span>'
                else:
                    implied_cell = '<span style="color:#94A3B8;">Fair</span>'

            rows_html += (
                f'<td style="{_TD_S}{_MONO}">{gd_cell}</td>'
                f'<td style="{_TD_S}font-size:11px;text-align:center;">{implied_cell}</td>'
            )

        rows_html += "</tr>"

    return (
        f'<table style="width:100%;border-collapse:collapse;font-family:DM Sans,sans-serif;table-layout:auto;">'
        f'<thead><tr>{hdr_html}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
    )


def _build_regression_table(df_reg, y_col, x_col):
    df_s      = df_reg.sort_values("gap_pct").reset_index(drop=True)
    cols_left = {"#", "Ticker", "Company", "Category", "Interpretation"}
    headers   = ["#", "Ticker", "Company", "Category", "Growth",
                 "Current Multiple", "Implied Multiple", "Gap", "Gap %", "Interpretation"]
    hdr = "".join(
        f'<th style="{_THL if c in cols_left else _TH}">{c}</th>'
        for c in headers
    )
    rows = ""
    for rank, (_, r) in enumerate(df_s.iterrows(), 1):
        bg  = "#FAFBFC" if rank % 2 == 0 else "#FFFFFF"
        co  = str(r.get("company", ""))
        if len(co) > 22: co = co[:20] + "\u2026"
        rows += (
            f'<tr style="background:{bg};" '
            f'onmouseover="this.style.background=\'#EFF6FF\'" '
            f'onmouseout="this.style.background=\'{bg}\'">'
            f'<td style="{_TDL}color:#9CA3AF;">{rank}</td>'
            f'<td style="{_TDL}"><b style="color:#1D4ED8;font-size:11px;">{r.get("ticker","")}</b></td>'
            f'<td style="{_TDL}color:#374151;font-size:11px;">{co}</td>'
            f'<td style="{_TDL}">{_pill(r.get("category",""))}</td>'
            f'<td style="{_TD}">{_fmt_val(r.get(x_col), suffix="%")}</td>'
            f'<td style="{_TD}">{_fmt_mult(r.get(y_col))}</td>'
            f'<td style="{_TD}">{_fmt_mult(r.get("implied_multiple"), muted=True)}</td>'
            f'<td style="{_TD}">{_fmt_delta_mult(r.get("gap"))}</td>'
            f'<td style="{_TD}">{_fmt_gap_pct(r.get("gap_pct"))}</td>'
            f'<td style="{_TDL}font-size:11px;">{_gap_interp(r.get("gap_pct"))}</td>'
            '</tr>'
        )
    return _wrap_table(f"<thead><tr>{hdr}</tr></thead><tbody>{rows}</tbody>")


def _build_combined_scatter(
    df_then, df_now,
    x_col, y_col, x_label, y_label,
    x_range, y_range,
    reg_coeffs=None, r_sq=None,
):
    """
    Two-panel (Then | Now) Plotly subplot with ghost-dot hover cross-linking.
    Returns a full HTML string for rendering via components.html().
    Hovering a company in either panel lights up a teal ring on its counterpart
    in the other panel.
    """
    valid_then = df_then.dropna(subset=[x_col, y_col]).reset_index(drop=True).copy()
    valid_now  = df_now.dropna(subset=[x_col, y_col]).reset_index(drop=True).copy()

    # ── Build merged index for ghost-dot cross-linking ─────────────────────────
    merged = (
        valid_then[["ticker", x_col, y_col]]
        .rename(columns={x_col: "x_then", y_col: "y_then"})
        .merge(
            valid_now[["ticker", x_col, y_col]]
            .rename(columns={x_col: "x_now", y_col: "y_now"}),
            on="ticker",
            how="inner",
        )
        .reset_index(drop=True)
    )
    ticker_to_midx = {row["ticker"]: int(i) for i, row in merged.iterrows()}
    valid_then["_midx"] = valid_then["ticker"].map(ticker_to_midx).fillna(-1).astype(int)
    valid_now["_midx"]  = valid_now["ticker"].map(ticker_to_midx).fillna(-1).astype(int)
    N_MERGED = len(merged)

    # ── Trace index plan ──────────���─────────────────────────────────���──────────
    N_CATS          = len(CATEGORY_ORDER)
    N_REG           = 2 if (reg_coeffs is not None and len(valid_then) >= 3) else 0
    GHOST_RIGHT_IDX = 2 + N_CATS + N_REG
    GHOST_LEFT_IDX  = GHOST_RIGHT_IDX + 1

    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.06)

    # ── Hover card helpers ────���────────────────────────────────────────────────
    _HOVER_LABELS = {
        "ntm_ev_revenue":     "NTM EV/Revenue",
        "ntm_ev_ebitda":      "NTM EV/EBITDA",
        "ntm_ev_gp":          "NTM EV/GP",
        "ntm_revenue_growth": "NTM Rev Growth",
        "ntm_ebitda_margin":  "EBITDA Margin",
        "gross_margin":       "Gross Margin",
        "rule_of_x":          "Rule of X",
        "n3y_revenue_cagr":   "3Y Rev CAGR",
        "growth_adj_rev":     "Growth-Adj Rev",
        "growth_adj_gp":      "Growth-Adj GP",
    }
    x_hover = _HOVER_LABELS.get(x_col, x_label)
    y_hover = _HOVER_LABELS.get(y_col, y_label)

    def _fmt_val_hover(val, metric):
        m = metric.lower()
        if pd.isna(val):
            return "\u2014"
        if "ev/" in m or ("revenue" in m and "growth" not in m and "cagr" not in m):
            return f"{val:.1f}x"
        if "growth" in m or "margin" in m or "cagr" in m:
            return f"{val:.0f}%"
        if "rule" in m:
            return f"{val:.0f}"
        return f"{val:.1f}"

    def _build_cd(valid):
        """customdata: [0] company  [1] ticker  [2] x_row  [3] y_row  [4] merged_idx"""
        if len(valid) == 0:
            return np.empty((0, 5), dtype=object)
        x_vals_str = [_fmt_val_hover(v, x_hover) for v in valid[x_col]]
        y_vals_str = [_fmt_val_hover(v, y_hover) for v in valid[y_col]]
        max_val_w  = max(
            max((len(s) for s in x_vals_str), default=4),
            max((len(s) for s in y_vals_str), default=4),
        )
        label_w   = max(len(x_hover), len(y_hover))
        x_lbl_pad = x_hover.ljust(label_w)
        y_lbl_pad = y_hover.ljust(label_w)
        pad_total = label_w + 2 + max_val_w + 6
        x_rows = [(x_lbl_pad + "  " + s.rjust(max_val_w)).ljust(pad_total) for s in x_vals_str]
        y_rows = [(y_lbl_pad + "  " + s.rjust(max_val_w)).ljust(pad_total) for s in y_vals_str]
        return np.column_stack([
            valid["company"].fillna("").values,
            valid["ticker"].fillna("").values,
            x_rows,
            y_rows,
            valid["_midx"].values.astype(str),
        ])

    hovertemplate = (
        "<b>%{customdata[0]}</b> (%{customdata[1]})<br>"
        "<br>"
        "%{customdata[2]}<br>"
        "%{customdata[3]}"
        "<extra></extra>"
    )

    # ── Trace 0: dots_then (left panel) ──────────���─────────────────────────────
    fig.add_trace(go.Scatter(
        x=valid_then[x_col] if not valid_then.empty else [],
        y=valid_then[y_col] if not valid_then.empty else [],
        mode="markers+text",
        name="",
        marker=dict(
            size=valid_then["tev"].apply(_dot_size).tolist() if not valid_then.empty else [],
            color=[CATEGORY_COLORS_DISPLAY.get(c, "#9CA3AF") for c in valid_then["category"]] if not valid_then.empty else [],
            opacity=0.8,
            line=dict(color="white", width=1.2),
        ),
        text=[""] * len(valid_then),
        textposition="top right",
        textfont=dict(size=9, color="#475569", family="DM Sans"),
        customdata=_build_cd(valid_then),
        hovertemplate=hovertemplate,
        showlegend=False,
    ), row=1, col=1)

    # ── Trace 1: dots_now (right panel) ────────────���───────────────────────────
    fig.add_trace(go.Scatter(
        x=valid_now[x_col] if not valid_now.empty else [],
        y=valid_now[y_col] if not valid_now.empty else [],
        mode="markers+text",
        name="",
        marker=dict(
            size=valid_now["tev"].apply(_dot_size).tolist() if not valid_now.empty else [],
            color=[CATEGORY_COLORS_DISPLAY.get(c, "#9CA3AF") for c in valid_now["category"]] if not valid_now.empty else [],
            opacity=0.8,
            line=dict(color="white", width=1.2),
        ),
        text=[""] * len(valid_now),
        textposition="top right",
        textfont=dict(size=9, color="#475569", family="DM Sans"),
        customdata=_build_cd(valid_now),
        hovertemplate=hovertemplate,
        showlegend=False,
    ), row=1, col=2)

    # ── Traces 2..2+N_CATS-1: phantom legend (one per category) ───────────────
    for cat in CATEGORY_ORDER:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(size=8, color=CATEGORY_COLORS_DISPLAY.get(cat, "#9CA3AF")),
            name=cat, showlegend=True,
        ), row=1, col=1)

    # ── Regression line traces ─────��───────────────────────────────────────────
    if reg_coeffs is not None and len(valid_then) >= 3:
        xr = np.linspace(x_range[0], x_range[1], 60)
        yr = np.polyval(reg_coeffs, xr).clip(0)
        for _c in (1, 2):
            fig.add_trace(go.Scatter(
                x=xr, y=yr, mode="lines",
                line=dict(color="#EF4444", width=1.5, dash="dot"),
                name="Regression fit", showlegend=False, hoverinfo="skip",
            ), row=1, col=_c)

    # ── Ghost traces — initially invisible ────────────────────────────────────
    _n_g         = max(N_MERGED, 1)
    _blank_c     = ["rgba(0,0,0,0)"] * _n_g
    _zero_s      = [0] * _n_g
    _ghost_x_now = merged["x_now"].tolist()  if N_MERGED > 0 else [None]
    _ghost_y_now = merged["y_now"].tolist()  if N_MERGED > 0 else [None]
    _ghost_x_th  = merged["x_then"].tolist() if N_MERGED > 0 else [None]
    _ghost_y_th  = merged["y_then"].tolist() if N_MERGED > 0 else [None]

    # ghost_on_right (GHOST_RIGHT_IDX): right panel, lit when LEFT is hovered
    fig.add_trace(go.Scatter(
        x=_ghost_x_now, y=_ghost_y_now, mode="markers", name="",
        marker=dict(size=_zero_s, color=_blank_c, line=dict(color=_blank_c, width=3.5)),
        hoverinfo="skip", showlegend=False,
    ), row=1, col=2)

    # ghost_on_left (GHOST_LEFT_IDX): left panel, lit when RIGHT is hovered
    fig.add_trace(go.Scatter(
        x=_ghost_x_th, y=_ghost_y_th, mode="markers", name="",
        marker=dict(size=_zero_s, color=_blank_c, line=dict(color=_blank_c, width=3.5)),
        hoverinfo="skip", showlegend=False,
    ), row=1, col=1)

    # ── Median crosshairs ────────��────────────────────────────────────────────
    for _vd, _ci in [(valid_then, 1), (valid_now, 2)]:
        if not _vd.empty:
            _mx = float(_vd[x_col].median())
            _my = float(_vd[y_col].median())
            fig.add_hline(y=_my, line_dash="dash", line_color="#D1D5DB",
                          line_width=0.5, row=1, col=_ci)
            fig.add_vline(x=_mx, line_dash="dash", line_color="#D1D5DB",
                          line_width=0.5, row=1, col=_ci)

    # ── R^2 annotations ──────────────────────────────────────────────────────
    if reg_coeffs is not None and r_sq is not None and len(valid_then) >= 3:
        for _r2x in (0.455, 0.985):
            fig.add_annotation(
                text=f"R\u00b2 = {r_sq:.2f}",
                xref="paper", yref="paper",
                x=_r2x, y=0.98,
                xanchor="right", yanchor="top",
                showarrow=False,
                font=dict(size=11, color="#EF4444", family="DM Sans"),
                bgcolor="rgba(255,255,255,0.7)",
                borderpad=4, bordercolor="rgba(0,0,0,0)",
            )

    # ── Axis tick formatting ────────────────────────────────────────���──────────
    _x_min, _x_max = x_range[0], x_range[1]
    _raw_step  = (_x_max - _x_min) / 6.0
    _tick_step = next((n for n in [1, 2, 5, 10, 20, 25, 50, 100] if n >= _raw_step), 100)
    _tick_vals = np.arange(
        np.ceil(_x_min  / _tick_step) * _tick_step,
        np.floor(_x_max / _tick_step) * _tick_step + _tick_step * 0.1,
        _tick_step,
    )
    _is_pct = any(kw in x_col for kw in ("growth", "margin", "rule"))
    _tick_texts = [
        f"({abs(v):.0f}%)" if (_is_pct and v < 0) else (f"{v:.0f}%" if _is_pct else f"{v:.1f}")
        for v in _tick_vals
    ]

    _x_ax = dict(
        range=x_range, gridcolor="#F3F4F6", gridwidth=0.5,
        showline=True, linecolor="#E5E7EB", linewidth=1,
        tickfont=dict(size=10, color="#111827", family="DM Sans"),
        zeroline=False,
        tickvals=_tick_vals.tolist(), ticktext=_tick_texts,
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )
    _y_ax = dict(
        range=y_range, gridcolor="#F3F4F6", gridwidth=0.5,
        showline=True, linecolor="#E5E7EB", linewidth=1,
        tickfont=dict(size=10, color="#111827", family="DM Sans"),
        zeroline=False,
        ticksuffix="%" if y_col == "ntm_revenue_growth" else "x",
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )

    fig.update_layout(
        plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        font=dict(family="DM Sans, sans-serif", size=11, color="#111827"),
        xaxis =dict(**_x_ax),
        xaxis2=dict(**_x_ax),
        yaxis =dict(
            title=dict(text=y_label, font=dict(size=11, color="#111827"), standoff=12),
            **_y_ax,
        ),
        yaxis2=dict(showticklabels=False, **_y_ax),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0,
            font=dict(size=9, color="#111827", family="DM Sans"),
            itemsizing="constant", tracegroupgap=2, itemwidth=30,
            bgcolor="rgba(0,0,0,0)",
        ),
        height=600,
        margin=dict(l=60, r=30, t=40, b=80),
        showlegend=True,
        hovermode="closest",
        hoverdistance=25,
        spikedistance=-1,
        clickmode="event+select",
        dragmode="zoom",
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E2E8F0",
            font=dict(size=11, color="#374151", family="Menlo, Monaco, Consolas, monospace"),
            align="left",
            namelength=0,
        ),
    )

    # X-axis title annotations below each panel
    for _ax_x in (0.235, 0.765):
        fig.add_annotation(
            xref="paper", yref="paper",
            x=_ax_x, y=-0.10,
            text=x_label, showarrow=False,
            font=dict(size=11, color="#111827", family="DM Sans"),
            xanchor="center", yanchor="top",
        )

    # ── JavaScript: ghost-dot hover cross-linking ──────────────────────────────
    _js = (
        "<script>\n"
        "(function waitForPlotly() {\n"
        "  var gd = document.querySelector('.js-plotly-plot');\n"
        "  if (!gd) { setTimeout(waitForPlotly, 150); return; }\n"
        "  var N           = " + str(N_MERGED) + ";\n"
        "  var GHOST_RIGHT = " + str(GHOST_RIGHT_IDX) + ";\n"
        "  var GHOST_LEFT  = " + str(GHOST_LEFT_IDX) + ";\n"
        "  var blank = Array(Math.max(N, 1)).fill('rgba(0,0,0,0)');\n"
        "  var zeros = Array(Math.max(N, 1)).fill(0);\n"
        "\n"
        "  gd.on('plotly_hover', function(data) {\n"
        "    var pt = data.points[0];\n"
        "    if (pt.curveNumber > 1) return;\n"
        "    var mIdx = parseInt(pt.customdata[4]);\n"
        "    if (isNaN(mIdx) || mIdx < 0 || mIdx >= N) return;\n"
        "    var isLeft       = (pt.xaxis._id === 'x' || pt.xaxis._id === 'x1');\n"
        "    var ghostToShow  = isLeft ? GHOST_RIGHT : GHOST_LEFT;\n"
        "    var ghostToReset = isLeft ? GHOST_LEFT  : GHOST_RIGHT;\n"
        "    var showC = blank.slice();\n"
        "    var showLC = blank.slice();\n"
        "    var showS = zeros.slice();\n"
        "    showC[mIdx]  = 'rgba(239,68,68,0.20)';\n"
        "    showLC[mIdx] = 'rgba(239,68,68,1.0)';\n"
        "    showS[mIdx]  = 26;\n"
        "    Plotly.restyle(gd,\n"
        "      {'marker.color':      [showC,  blank],\n"
        "       'marker.line.color': [showLC, blank],\n"
        "       'marker.size':       [showS,  zeros]},\n"
        "      [ghostToShow, ghostToReset]\n"
        "    );\n"
        "  });\n"
        "\n"
        "  gd.on('plotly_unhover', function() {\n"
        "    Plotly.restyle(gd,\n"
        "      {'marker.color':      [blank, blank],\n"
        "       'marker.line.color': [blank, blank],\n"
        "       'marker.size':       [zeros, zeros]},\n"
        "      [GHOST_RIGHT, GHOST_LEFT]\n"
        "    );\n"
        "  });\n"
        "})();\n"
        "</script>"
    )

    _html = fig.to_html(
        include_plotlyjs="cdn",
        full_html=True,
        config={"displayModeBar": False, "scrollZoom": False},
    )
    return _html.replace("</body>", _js + "\n</body>")


# ===============================================================================
# PAGE HEADER & JUMP NAVIGATION
# ===============================================================================

st.markdown(
    '<h1 style="font-size:28px;font-weight:700;color:#111827;margin:0 0 4px 0;">'
    'Valuation Lookback</h1>'
    '<p style="font-size:13px;color:#6B7280;margin:0 0 12px 0;">'
    'How multiples relative to growth and profitability have shifted over time'
    '</p>',
    unsafe_allow_html=True,
)


# ── Load snapshot dates + daily multiples dates ───────────���───────────────────
all_snap_dates  = _all_snapshot_dates()
all_daily_dates = _all_daily_dates()

if not all_snap_dates:
    st.error("No snapshot data found. Run the fetcher first.")
    st.stop()

current_date_str = all_snap_dates[0]

# Prefer daily_multiples dates for period availability (goes back to 2024+)
avail_dates_for_lookback = all_daily_dates if all_daily_dates else all_snap_dates
avail_periods            = _available_periods(avail_dates_for_lookback, current_date_str)

if not avail_periods:
    st.markdown(
        '<div style="font-size:12px;color:#94A3B8;padding:6px 0;margin:4px 0;">'
        'No historical snapshots available yet. Snapshots are saved weekly and will '
        'power lookback comparisons over time. Check back after a few weekly fetches.'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ===============================================================================
# SECTION 1 — CONTROL BAR
# ===============================================================================

# ── Lookback period: horizontal radio selector ─────────��──────────────────────
st.markdown(
    '<div style="font-size:9px;font-weight:600;text-transform:uppercase;'
    'letter-spacing:0.05em;color:#94A3B8;margin-bottom:2px;">LOOKBACK PERIOD</div>',
    unsafe_allow_html=True,
)
# Default to 12M if available, else last available
default_period_idx = avail_periods.index("12M") if "12M" in avail_periods else len(avail_periods) - 1
lookback_period = st.radio(
    "LOOKBACK PERIOD",
    avail_periods,
    index=default_period_idx,
    horizontal=True,
    label_visibility="collapsed",
)

col2, col3, col5, col6 = st.columns([1.5, 1.5, 1.5, 1.5])

with col2:
    y_axis_label = st.selectbox("Y-AXIS (MULTIPLE)", list(Y_AXIS_MAP.keys()), index=0)
with col3:
    x_axis_label = st.selectbox("X-AXIS (FUNDAMENTAL)", list(X_AXIS_MAP.keys()), index=0)
with col5:
    _tev_all = list(TEV_BANDS.keys())
    tev_bands_sel = st.multiselect("TEV", _tev_all, default=_tev_all)
with col6:
    _growth_all = list(GROWTH_BANDS.keys())
    growth_bands_sel = st.multiselect("GROWTH", _growth_all, default=_growth_all)

# ── Category filters: individual checkboxes in columns ────────────────────────
cat_all = list(dict.fromkeys(CATEGORY_MAP.values()))  # unique display names, ordered
st.markdown(
    '<div style="font-size:9px;font-weight:600;text-transform:uppercase;'
    'letter-spacing:0.05em;color:#94A3B8;margin-bottom:2px;margin-top:8px;">SEGMENTS</div>',
    unsafe_allow_html=True,
)
n_cats = len(cat_all)
n_cols = min(n_cats, 7)
cat_cols = st.columns(n_cols)
category_filter = []
for i, cat_name in enumerate(cat_all):
    with cat_cols[i % n_cols]:
        checked = st.checkbox(cat_name, value=True, key=f"cat_{cat_name}")
        if checked:
            category_filter.append(cat_name)

x_col, x_label = X_AXIS_MAP[x_axis_label]
y_col, y_label = Y_AXIS_MAP[y_axis_label]

# ===============================================================================
# DATA LOADING
# ===============================================================================

with st.spinner("Loading current snapshot..."):
    df_current_full = _raw_to_df(_load_snapshot(current_date_str))

target_hist_str = _period_to_target(lookback_period, current_date_str)
nearest_hist    = _find_nearest_date(avail_dates_for_lookback, target_hist_str, max_gap_days=45)

if not nearest_hist or nearest_hist == current_date_str:
    st.markdown(
        f'''<div style="background:#FFFBEB;border:1px solid #FDE68A;border-radius:10px;
            padding:20px 24px;margin:16px 0;">
            <div style="font-size:14px;font-weight:600;color:#92400E;">
                No data available for {lookback_period}
            </div>
            <div style="font-size:13px;color:#A16207;margin-top:6px;">
                Historical snapshots need to be collected over time. This period will
                become available once enough weekly snapshots have been saved.
            </div>
            <div style="font-size:12px;color:#B45309;margin-top:12px;">
                <b>Available periods:</b> {', '.join(avail_periods)}
            </div>
        </div>''',
        unsafe_allow_html=True,
    )
    st.stop()

# Load historical data — prefer daily_multiples (longer history) over company_snapshots
with st.spinner("Loading historical multiples..."):
    if all_daily_dates and nearest_hist in all_daily_dates:
        _hist_rows    = _load_daily_multiples(nearest_hist)
        df_hist_full  = _build_hist_df_from_daily(_hist_rows, df_current_full)
        _using_daily  = True
    else:
        df_hist_full  = _raw_to_df(_load_snapshot(nearest_hist))
        _using_daily  = False

lookback_date_str = nearest_hist

# ── Apply filters ───────────���─────────────────────────────────────────────────

def _in_any_band(value, selected_labels, band_map):
    """Return True if value falls within any of the selected bands."""
    if pd.isna(value):
        return False
    for label in selected_labels:
        lo, hi = band_map[label]
        if (lo is None or value >= lo) and (hi is None or value < hi):
            return True
    return False

def _filter(df, apply_tev=True, apply_growth=True):
    df = df[df["category"].isin(category_filter)].copy()
    if apply_tev and len(tev_bands_sel) < len(TEV_BANDS):
        df = df[df["tev"].apply(lambda v: _in_any_band(v, tev_bands_sel, TEV_BANDS))]
    if apply_growth and len(growth_bands_sel) < len(GROWTH_BANDS):
        df = df[df["ntm_revenue_growth"].apply(
            lambda v: _in_any_band(v, growth_bands_sel, GROWTH_BANDS)
        )]
    return df

df_current = _filter(df_current_full, apply_tev=True,  apply_growth=True)
df_hist    = _filter(df_hist_full,    apply_tev=False, apply_growth=False)

# EBITDA / GP view: exclude N/M multiples
if y_col in ("ntm_ev_ebitda", "ntm_ev_gp"):
    df_current = df_current.dropna(subset=[y_col])
    df_hist    = df_hist.dropna(subset=[y_col])

# Keep only companies present in both periods
both = set(df_current["ticker"]) & set(df_hist["ticker"])
excl = len(set(df_current["ticker"]) | set(df_hist["ticker"])) - len(both)
if excl:
    st.markdown(
        f'<div style="font-size:11px;color:#94A3B8;margin:2px 0 6px 0;">'
        f'{excl} companies excluded \u2014 not present in both periods.</div>',
        unsafe_allow_html=True,
    )
df_current = df_current[df_current["ticker"].isin(both)]
df_hist    = df_hist[df_hist["ticker"].isin(both)]

if len(df_current) < 5:
    st.markdown(
        f'<div style="font-size:11px;color:#94A3B8;margin:2px 0 6px 0;">'
        f'Only {len(df_current)} companies match current filters \u2014 '
        f'consider broadening category or TEV filters.</div>',
        unsafe_allow_html=True,
    )

# ── Shared axis ranges ────────────────────────────────────────────────────────
combined = pd.concat([df_hist, df_current])
x_range  = [_nice_min(combined[x_col]), _nice_max(combined[x_col])]
_y_min   = float(combined[y_col].min()) if not combined[y_col].dropna().empty else 0.0
y_range  = [min(0, _y_min * 1.05) if _y_min < 0 else 0, _nice_max(combined[y_col])]

# ── Summary stats ─────────────────────────────────────��───────────────────────
avg_now   = _safe_mean(df_current,    y_col)
avg_then  = _safe_mean(df_hist,       y_col)
med_now   = _safe_median(df_current,  y_col)
med_then  = _safe_median(df_hist,     y_col)
ag_now    = _safe_mean(df_current,    "ntm_revenue_growth")
am_now    = _safe_mean(df_current,    "ntm_ebitda_margin")

ag_then   = _safe_mean(df_hist,    "ntm_revenue_growth")
am_then   = _safe_mean(df_hist,    "ntm_ebitda_margin")

lookback_fmt = datetime.strptime(lookback_date_str, "%Y-%m-%d").strftime("%b %Y")
current_fmt  = datetime.strptime(current_date_str,  "%Y-%m-%d").strftime("%b %d, %Y")
n_hist       = df_hist.dropna(subset=[y_col, x_col]).shape[0]
n_curr       = df_current.dropna(subset=[y_col, x_col]).shape[0]


# ── Fit historical regression ────────────���────────────────────────────────────
reg_df     = df_hist[[x_col, y_col]].dropna()
reg_coeffs = None
r_sq       = None
slope      = None

if len(reg_df) >= 5:
    X_fit, y_fit = reg_df[x_col].values, reg_df[y_col].values
    reg_coeffs   = np.polyfit(X_fit, y_fit, 1)
    slope        = reg_coeffs[0]
    y_pred_fit   = np.polyval(reg_coeffs, X_fit)
    ss_res       = float(np.sum((y_fit - y_pred_fit) ** 2))
    ss_tot       = float(np.sum((y_fit - y_fit.mean())   ** 2))
    r_sq         = (1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


# ===============================================================================
# SECTION 2 — DELTA SUMMARY STAT CARDS (ABOVE the scatter plot)
# ===============================================================================

st.markdown('<div style="height:16px;"></div><div id="deltas"></div>', unsafe_allow_html=True)

stat_defs = [
    ("AVG MULTIPLE",      avg_now,  avg_then,  "x"),
    ("MEDIAN MULTIPLE",   med_now,  med_then,  "x"),
    ("AVG GROWTH",        ag_now,   ag_then,   "%"),
    ("AVG EBITDA MARGIN", am_now,   am_then,   "%"),
]

stat_cols = st.columns(len(stat_defs))
for i, (label, cur, hist, suf) in enumerate(stat_defs):
    nan_c = isinstance(cur,  float) and np.isnan(cur)
    nan_h = isinstance(hist, float) and np.isnan(hist)
    delta = (cur - hist) if not (nan_c or nan_h) else float("nan")
    nan_d = isinstance(delta, float) and np.isnan(delta)

    if nan_d:
        arrow_html = '<span style="color:#9CA3AF;font-size:13px;">\u2014</span>'
    else:
        # Multiple cards: compression = green (cheaper = good for PE buyers)
        if label in _MULTIPLE_LABELS:
            d_color = "#16A34A" if delta < 0 else ("#DC2626" if delta > 0 else "#9CA3AF")
        else:
            d_color = "#16A34A" if delta > 0 else ("#DC2626" if delta < 0 else "#9CA3AF")

        if delta > 0:
            arrow_html = (f'<span style="color:{d_color};font-weight:600;font-size:13px;">'
                          f'\u25b2 {abs(delta):.1f}{suf}</span>')
        elif delta < 0:
            arrow_html = (f'<span style="color:{d_color};font-weight:600;font-size:13px;">'
                          f'\u25bc {abs(delta):.1f}{suf}</span>')
        else:
            arrow_html = '<span style="color:#9CA3AF;font-size:13px;">\u2014 flat</span>'

    c_str = f"{cur:.1f}{suf}"  if not nan_c else "\u2014"
    h_str = f"{hist:.1f}{suf}" if not nan_h else "\u2014"

    with stat_cols[i]:
        st.markdown(
            f'<div style="background:white;border:1px solid #E5E7EB;border-radius:10px;'
            f'padding:16px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
            f'<div style="font-size:9px;font-weight:500;text-transform:uppercase;'
            f'letter-spacing:0.04em;color:#9CA3AF;margin-bottom:4px;">{label}</div>'
            f'<div style="font-size:20px;font-weight:700;color:#111827;">{c_str}</div>'
            f'<div style="margin-top:4px;">{arrow_html}</div>'
            f'<div style="font-size:11px;color:#9CA3AF;margin-top:2px;">'
            f'vs. {lookback_period} ago \u00b7 was {h_str}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

_source_attribution()

# ── Segment summary boxes ─────────��───────────────────────────────────────────
render_segment_summary_boxes(df_hist, df_current, y_col, y_label, category_filter)

# ===============================================================================
# SECTION 3 — SIDE-BY-SIDE SCATTER PLOTS
# ===============================================================================

st.markdown('<div style="height:32px;"></div><div id="scatter"></div>', unsafe_allow_html=True)

def _fmt_s(v, suf="x"):
    return f"{v:.1f}{suf}" if isinstance(v, float) and not np.isnan(v) else "\u2014"

col_left, col_right = st.columns(2, gap="medium")

with col_left:
    st.markdown(
        f'<div class="chart-header" style="background:#F8FAFC;border:1px solid #E2E8F0;'
        f'border-radius:8px;padding:0 14px;margin-bottom:8px;">'
        f'<span style="font-size:12px;font-weight:600;color:#475569;">{lookback_fmt}</span>'
        f'<span style="font-size:10px;color:#94A3B8;margin-left:8px;">'
        f'Avg: {_fmt_s(avg_then)} \u00b7 Med: {_fmt_s(med_then)} \u00b7 {n_hist} cos.</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

with col_right:
    st.markdown(
        f'<div class="chart-header" style="background:#F0F7FF;border:1px solid #BFDBFE;'
        f'border-radius:8px;padding:0 14px;margin-bottom:8px;">'
        f'<span style="font-size:12px;font-weight:600;color:#1E40AF;">Current ({current_fmt})</span>'
        f'<span style="font-size:10px;color:#3B82F6;margin-left:8px;">'
        f'Avg: {_fmt_s(avg_now)} \u00b7 Med: {_fmt_s(med_now)} \u00b7 {n_curr} cos.</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

combined_html = _build_combined_scatter(
    df_hist, df_current,
    x_col, y_col, x_label, y_label,
    x_range, y_range,
    reg_coeffs=reg_coeffs, r_sq=r_sq,
)
components.html(combined_html, height=620, scrolling=False)

st.markdown(
    '<div style="font-size:9px;color:#CBD5E1;text-align:center;margin-top:4px;">'
    'Box-select to zoom \u00b7 Double-click to reset \u00b7 Hover a dot to highlight its position on the other chart'
    '</div>',
    unsafe_allow_html=True,
)
# Reset zoom button
if st.button("Reset Zoom", key="reset_zoom"):
    st.rerun()

if reg_coeffs is not None:
    st.caption(
        f"Dotted line = linear regression fit from {lookback_fmt} historical data. "
        "Companies above the line trade at a premium to their historical growth-adjusted multiple; "
        "below the line = discount."
    )

_source_attribution()

# ===============================================================================
# SECTION 4 — BIGGEST MOVERS TABLES (Expansions on top, Compressions below)
# ===============================================================================

st.markdown('<div id="movers"></div>', unsafe_allow_html=True)

# Build merged delta dataframe
df_merged = df_current.merge(
    df_hist[["ticker", y_col, x_col, "tev"]],
    on="ticker",
    suffixes=("_now", "_then"),
)
df_merged["multiple_delta"]     = df_merged[f"{y_col}_now"] - df_merged[f"{y_col}_then"]
df_merged["multiple_delta_pct"] = (
    df_merged["multiple_delta"] / df_merged[f"{y_col}_then"].replace(0, np.nan)
) * 100
df_merged["fundamental_delta"] = df_merged[f"{x_col}_now"] - df_merged[f"{x_col}_then"]

# Expansions on top, Compressions below — stacked vertically
if len(df_merged) >= 2:
    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#16A34A;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:8px;">Biggest Multiple Expansions</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="background:white;border:1px solid #E5E7EB;border-radius:10px;'
        'overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
        + _build_movers_table(df_merged, y_col, x_col, ascending=False, top_n=None)
        + '</div>',
        unsafe_allow_html=True,
    )
    _source_attribution()

    st.markdown('<div style="height:24px;"></div>', unsafe_allow_html=True)

    st.markdown(
        '<div style="font-size:11px;font-weight:700;color:#DC2626;text-transform:uppercase;'
        'letter-spacing:0.06em;margin-bottom:8px;">Biggest Multiple Compressions</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="background:white;border:1px solid #E5E7EB;border-radius:10px;'
        'overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.04);">'
        + _build_movers_table(df_merged, y_col, x_col, ascending=True, top_n=None)
        + '</div>',
        unsafe_allow_html=True,
    )
    _source_attribution()
else:
    st.caption("Not enough data for movers tables.")

# ===============================================================================
# SECTION 5 — MIGRATION MAP (horizontal bar chart)
# ===============================================================================

st.markdown('<div id="migration"></div>', unsafe_allow_html=True)
st.markdown(
    f'<div style="font-size:13px;font-weight:600;color:#111827;margin-bottom:4px;">Biggest Movers</div>'
    f'<div style="font-size:11px;color:#94A3B8;margin-bottom:12px;">'
    f'Top 20 by absolute {y_label} change\u2002\u00b7\u2002'
    f'<span style="color:#F87171;font-weight:500;">&#x25A0; Compression</span>\u2002\u00b7\u2002'
    f'<span style="color:#22C55E;font-weight:500;">&#x25A0; Expansion</span></div>',
    unsafe_allow_html=True,
)

df_delta = (
    df_current[["ticker", "company", "category", x_col, y_col, "tev"]]
    .merge(
        df_hist[["ticker", x_col, y_col]]
        .rename(columns={x_col: f"{x_col}_then", y_col: f"{y_col}_then"}),
        on="ticker", how="inner",
    )
    .rename(columns={x_col: f"{x_col}_now", y_col: f"{y_col}_now"})
)
df_delta["multiple_delta"] = df_delta[f"{y_col}_now"] - df_delta[f"{y_col}_then"]

if len(df_delta) >= 3:
    fig_mig = build_migration_bar_chart(df_delta, y_col, y_label, top_n=20)
    st.markdown(
        '<div style="background:white;border:1px solid #E5E7EB;border-radius:10px;'
        'padding:16px;box-shadow:0 1px 2px rgba(0,0,0,0.03);">',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig_mig, use_container_width=True, config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)
    _source_attribution()
else:
    st.markdown(
        '<div style="font-size:11px;color:#94A3B8;">Not enough matched companies for migration chart.</div>',
        unsafe_allow_html=True,
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    '<div style="font-size:10px;color:#9CA3AF;">'
    '<span style="color:#64748B;font-weight:500;">Source:</span> '
    'FactSet (fundamentals, estimates, multiples) \u00b7 Historical data from weekly snapshots'
    '</div>',
    unsafe_allow_html=True,
)
