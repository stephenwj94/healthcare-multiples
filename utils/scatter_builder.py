"""
utils/scatter_builder.py
Shared regression scatter utility used by draft pages.
Extracted and generalised from pages/03_Valuation_Regression.py.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

try:
    from scipy import stats as _sp_stats
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False

from config.color_palette import (
    SEGMENT_SHORT, SEG_COLOR_MAP, PLOTLY_BG, PLOTLY_GRID, PLOTLY_TEXT,
)

# ── Shared constants ───────────────────────────────────────────────────────────
_FONT_FAM   = "DM Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"

_TEV_MEGA  = 50_000_000_000   # >$50B → 14px
_TEV_LARGE = 10_000_000_000   # $10–50B → 10px


# ── DataFrame builder ─────────────────────────────────────────────────────────

def build_scatter_df(records: list[dict]) -> pd.DataFrame:
    """Convert raw DB records (list of dicts) to a scatter-ready DataFrame.

    Returns a DataFrame with columns:
        Ticker, Name, Category, NTM Rev x, NTM EBITDA x, TEV,
        NTM Rev Growth, EBITDA Margin, Gross Margin
    """
    rows = []
    for d in records:
        rev_x    = d.get("ntm_tev_rev")
        ebitda_x = d.get("ntm_tev_ebitda")
        seg      = SEGMENT_SHORT.get(d.get("segment", ""), d.get("segment", ""))
        ticker   = d.get("ticker", "?")
        name     = d.get("name") or ticker
        tev      = d.get("enterprise_value")
        rev_gr   = d.get("ntm_revenue_growth")       # decimal (0.25 = 25%)
        ebitda_m = d.get("ebitda_margin")             # decimal
        gross_m  = d.get("gross_margin")              # decimal

        if (rev_x and rev_x > 0) or (ebitda_x and ebitda_x > 0):
            rows.append({
                "Ticker":        ticker,
                "Name":          name,
                "Category":      seg,
                "NTM Rev x":     rev_x    if rev_x    and 0 < rev_x    < 100 else None,
                "NTM EBITDA x":  ebitda_x if ebitda_x and 0 < ebitda_x < 100 else None,
                "TEV":           tev      if tev      and tev      > 0 else None,
                "NTM Rev Growth": rev_gr  * 100 if rev_gr   is not None else None,
                "EBITDA Margin": ebitda_m * 100 if ebitda_m is not None else None,
                "Gross Margin":  gross_m  * 100 if gross_m  is not None else None,
            })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── Plotly layout helper ───────────────────────────────────────────────────────

def plotly_layout(height: int = 500, title: str = "") -> dict:
    """Return a base Plotly layout dict matching the app's visual style."""
    _axis = dict(
        gridcolor=PLOTLY_GRID, gridwidth=0.5,
        showgrid=True, zeroline=False,
        showline=True, linecolor="#D1D5DB", linewidth=1,
        tickfont=dict(size=11, color="#6B7280", family=_FONT_FAM),
    )
    return dict(
        title=dict(text=title, font=dict(size=13, color=PLOTLY_TEXT)),
        plot_bgcolor=PLOTLY_BG,
        paper_bgcolor=PLOTLY_BG,
        font=dict(family=_FONT_FAM, color=PLOTLY_TEXT, size=11),
        xaxis=dict(**_axis),
        yaxis=dict(**_axis),
        margin=dict(l=60, r=40, t=55, b=60),
        height=height,
        legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0, font=dict(size=10)),
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E5E7EB",
            font=dict(size=11, color="#374151", family=_FONT_FAM),
        ),
    )


# ── Regression scatter builder ────────────────────────────────────────────────

def build_regression_scatter(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    x_label: str,
    y_label: str,
    *,
    height: int = 600,
    x_suffix: str = "x",
    y_suffix: str = "%",
    fixed_color: str | None = None,   # if set, overrides category coloring
    shared_range: tuple[tuple, tuple] | None = None,  # ((x0,x1),(y0,y1))
) -> go.Figure | None:
    """Return a fully-formatted Plotly regression scatter figure.

    Parameters
    ----------
    df          : DataFrame from build_scatter_df() (or any df with Ticker, Name,
                  Category, TEV columns plus x_col / y_col).
    x_col       : Column name for x-axis.
    y_col       : Column name for y-axis.
    x_label     : Human-readable x-axis label.
    y_label     : Human-readable y-axis label.
    height      : Chart height in pixels.
    x_suffix    : Tick suffix for x-axis (e.g. "x", "%", "").
    y_suffix    : Tick suffix for y-axis.
    fixed_color : If given, all dots get this color (no category coloring).
    shared_range: Pre-computed axis ranges for locked axes (Then vs Now).
    """
    df = df.dropna(subset=[x_col, y_col]).copy()
    if df.empty or len(df) < 3:
        return None

    # ── TEV dot sizing ────────────────────────────────────────────────────────
    def _dot_size(tev):
        if pd.isna(tev):
            return 8
        if tev >= _TEV_MEGA:
            return 14
        if tev >= _TEV_LARGE:
            return 10
        return 7

    df["_msize"] = df["TEV"].apply(_dot_size) if "TEV" in df.columns else 8

    x_arr = df[x_col].values.astype(float)
    y_arr = df[y_col].values.astype(float)

    # ── OLS regression ────────────────────────────────────────────────────────
    r_squared = trend_x = trend_y = None
    if _HAS_SCIPY and len(x_arr) >= 4:
        slope, intercept, r_val, _, _ = _sp_stats.linregress(x_arr, y_arr)
        r_squared = r_val ** 2
        trend_x   = np.linspace(x_arr.min(), x_arr.max(), 120)
        trend_y   = slope * trend_x + intercept

    # ── Axis extents ──────────────────────────────────────────────────────────
    if shared_range:
        x0_r, x1_r = shared_range[0]
        y0_r, y1_r = shared_range[1]
    else:
        x_span = max(x_arr.max() - x_arr.min(), 1.0)
        y_span = max(y_arr.max() - y_arr.min(), 2.0)
        x0_r, x1_r = x_arr.min() - x_span * 0.06, x_arr.max() + x_span * 0.06
        y0_r, y1_r = y_arr.min() - y_span * 0.10, y_arr.max() + y_span * 0.12

    median_x = float(np.median(x_arr))
    median_y = float(np.median(y_arr))

    # ── Label set: top movers + mega-caps ─────────────────────────────────────
    label_set: set[str] = set()
    if "TEV" in df.columns:
        tev_clean = df["TEV"].dropna()
        n = min(5, len(tev_clean))
        if n > 0:
            label_set |= set(df.nlargest(n, "TEV")["Ticker"].tolist())
    label_set |= set(df.nlargest(3, x_col)["Ticker"].tolist())
    label_set |= set(df.nsmallest(3, x_col)["Ticker"].tolist())
    label_set |= set(df.nlargest(2, y_col)["Ticker"].tolist())
    label_set |= set(df.nsmallest(2, y_col)["Ticker"].tolist())

    # ── Hover formatting ──────────────────────────────────────────────────────
    def _fmt_x(v):
        if not pd.notna(v):
            return "–"
        return f"{v:.1f}{x_suffix}"

    def _fmt_y(v):
        if not pd.notna(v):
            return "–"
        return f"{v:.1f}{y_suffix}"

    _all_xf = [_fmt_x(v) for v in df[x_col]]
    _all_yf = [_fmt_y(v) for v in df[y_col]]
    _max_vw  = max(max((len(s) for s in _all_xf), default=4),
                   max((len(s) for s in _all_yf), default=4))
    _lw      = max(len(x_label), len(y_label))
    _xl_pad  = x_label.ljust(_lw)
    _yl_pad  = y_label.ljust(_lw)
    _pad_tot = _lw + 2 + _max_vw + 6

    _hover_tmpl = (
        "<b>%{customdata[0]}</b> (%{customdata[1]})<br><br>"
        "%{customdata[2]}<br>%{customdata[3]}"
        "<extra></extra>"
    )

    fig = go.Figure()

    # ── Median reference lines ────────────────────────────────────────────────
    fig.add_shape(type="line",
                  x0=median_x, x1=median_x, y0=y0_r, y1=y1_r,
                  xref="x", yref="y",
                  line=dict(color="#E2E8F0", width=0.75, dash="dot"))
    fig.add_shape(type="line",
                  x0=x0_r, x1=x1_r, y0=median_y, y1=median_y,
                  xref="x", yref="y",
                  line=dict(color="#E2E8F0", width=0.75, dash="dot"))

    # ── Scatter traces ────────────────────────────────────────────────────────
    if fixed_color:
        # Single trace, no category split
        custom = list(zip(
            df["Name"].fillna("?").tolist(),
            df["Ticker"].tolist(),
            [(_xl_pad + "  " + _fmt_x(v).rjust(_max_vw)).ljust(_pad_tot) for v in df[x_col]],
            [(_yl_pad + "  " + _fmt_y(v).rjust(_max_vw)).ljust(_pad_tot) for v in df[y_col]],
        ))
        tick_labels = [t if t in label_set else "" for t in df["Ticker"].tolist()]
        fig.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col],
            mode="markers+text",
            name="",
            text=tick_labels,
            textposition="top right",
            textfont=dict(size=9, color="#374151", family=_FONT_FAM),
            marker=dict(
                size=df["_msize"].tolist() if "_msize" in df.columns else 8,
                color=fixed_color,
                opacity=0.75,
                line=dict(width=1, color="white"),
            ),
            customdata=custom,
            hovertemplate=_hover_tmpl,
        ))
    else:
        # Category-colored traces
        for label, color in SEG_COLOR_MAP.items():
            sub = df[df["Category"] == label].copy() if "Category" in df.columns else df
            if sub.empty:
                continue
            custom = list(zip(
                sub["Name"].fillna("?").tolist(),
                sub["Ticker"].tolist(),
                [(_xl_pad + "  " + _fmt_x(v).rjust(_max_vw)).ljust(_pad_tot) for v in sub[x_col]],
                [(_yl_pad + "  " + _fmt_y(v).rjust(_max_vw)).ljust(_pad_tot) for v in sub[y_col]],
            ))
            tick_labels = [t if t in label_set else "" for t in sub["Ticker"].tolist()]
            fig.add_trace(go.Scatter(
                x=sub[x_col], y=sub[y_col],
                mode="markers+text",
                name=label,
                text=tick_labels,
                textposition="top right",
                textfont=dict(size=9, color="#374151", family=_FONT_FAM),
                marker=dict(
                    size=sub["_msize"].tolist() if "_msize" in sub.columns else 8,
                    color=color, opacity=0.75,
                    line=dict(width=1, color="white"),
                ),
                customdata=custom,
                hovertemplate=_hover_tmpl,
            ))

    # ── OLS trendline ─────────────────────────────────────────────────────────
    if trend_x is not None:
        fig.add_trace(go.Scatter(
            x=trend_x, y=trend_y,
            mode="lines",
            line=dict(color="#94A3B8", width=1.5, dash="dash"),
            showlegend=False,
            hoverinfo="skip",
        ))

    # ── Annotations ───────────────────────────────────────────────────────────
    annotations = []
    if r_squared is not None:
        annotations.append(dict(
            x=0.02, xref="paper", y=0.98, yref="paper",
            text=f"R² = {r_squared:.2f}",
            showarrow=False,
            font=dict(size=11, color="#64748B", family=_FONT_FAM),
            bgcolor="rgba(255,255,255,0.8)",
            borderpad=4,
            xanchor="left", yanchor="top",
        ))
    annotations.append(dict(
        x=0.99, xref="paper", y=0.01, yref="paper",
        text="Dot size = TEV",
        showarrow=False,
        font=dict(size=8, color="#B0B7C3", family=_FONT_FAM),
        xanchor="right", yanchor="bottom",
    ))

    # ── Layout ────────────────────────────────────────────────────────────────
    layout = plotly_layout(height=height)
    layout["xaxis"].update(dict(
        title=dict(text=x_label, font=dict(size=12, color="#374151", family=_FONT_FAM),
                   standoff=30),
        ticksuffix=x_suffix,
        range=[x0_r, x1_r],
        gridcolor="#F3F4F6", gridwidth=0.5,
        linecolor="#D1D5DB", linewidth=1, zeroline=False,
    ))
    layout["yaxis"].update(dict(
        title=dict(text=y_label, font=dict(size=12, color="#374151", family=_FONT_FAM),
                   standoff=15),
        ticksuffix=y_suffix,
        range=[y0_r, y1_r],
        gridcolor="#F3F4F6", gridwidth=0.5,
        linecolor="#D1D5DB", linewidth=1,
        zeroline=True, zerolinecolor="#D1D5DB", zerolinewidth=1,
    ))
    layout["legend"] = dict(
        orientation="h",
        yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(size=10, color="#6B7280", family=_FONT_FAM),
        itemsizing="constant", itemwidth=30,
        bgcolor="rgba(255,255,255,0)",
    )
    layout["annotations"] = annotations
    layout["margin"]      = dict(l=60, r=40, t=55, b=80)

    fig.update_layout(**layout)
    fig.update_xaxes(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )
    fig.update_yaxes(
        showspikes=True, spikemode="across", spikesnap="cursor",
        spikethickness=1, spikecolor="#94A3B8", spikedash="dot",
    )
    fig.update_layout(
        hovermode="closest",
        spikedistance=-1,
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#E2E8F0",
            font=dict(size=11, color="#374151",
                      family="Menlo, Monaco, Consolas, monospace"),
            align="left",
            namelength=0,
        ),
    )
    return fig
