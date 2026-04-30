"""
Plotly chart builders for the dashboard.
Light theme — white/off-white backgrounds, DM Sans font, gray gridlines.
"""

import plotly.graph_objects as go
import pandas as pd
import numpy as np
from config.settings import SEGMENT_COLORS, SEGMENT_DISPLAY

# ── Light theme constants ────────────────────────────────────────────────────
_PAPER_BG  = "#FAFBFC"
_PLOT_BG   = "#FFFFFF"
_GRID_CLR  = "#E5E7EB"
_AXIS_CLR  = "#9CA3AF"
_FONT_FAM  = "DM Sans, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"
_FONT_CLR  = "#374151"


def _base_layout(height=450, title=""):
    """Return a base layout dict for light-theme Plotly charts."""
    return dict(
        title=dict(text=title, font=dict(size=13, color=_FONT_CLR, family=_FONT_FAM)),
        plot_bgcolor=_PLOT_BG,
        paper_bgcolor=_PAPER_BG,
        font=dict(family=_FONT_FAM, color=_FONT_CLR, size=11),
        height=height,
        margin=dict(l=50, r=30, t=45, b=40),
        xaxis=dict(
            gridcolor=_GRID_CLR, showgrid=True, zeroline=False,
            showline=True, linecolor=_GRID_CLR, linewidth=1,
            tickfont=dict(size=10, color=_AXIS_CLR),
        ),
        yaxis=dict(
            gridcolor=_GRID_CLR, showgrid=True, zeroline=False,
            showline=True, linecolor=_GRID_CLR, linewidth=1,
            tickfont=dict(size=10, color=_AXIS_CLR),
        ),
        hoverlabel=dict(
            bgcolor="rgba(255,255,255,0.97)",
            font=dict(size=11, color="#1F2937", family=_FONT_FAM),
            bordercolor="#E5E7EB",
        ),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            borderwidth=0,
            font=dict(size=10, color=_FONT_CLR),
        ),
    )


# Metric display configuration for all supported multiples
METRIC_LABELS = {
    "ntm_tev_rev": {
        "short": "TEV/Rev",
        "full": "NTM TEV/Revenue",
        "chart_title": "NTM Revenue Multiple by Segment (Median)",
        "bar_title": "Current Median NTM TEV/Revenue by Segment",
        "y_axis": "Median NTM TEV/Revenue",
        "hover": "Median NTM TEV/Rev",
        "scatter_y": "NTM TEV/Rev",
    },
    "ntm_tev_gp": {
        "short": "TEV/GP",
        "full": "NTM TEV/Gross Profit",
        "chart_title": "NTM Gross Profit Multiple by Segment (Median)",
        "bar_title": "Current Median NTM TEV/GP by Segment",
        "y_axis": "Median NTM TEV/GP",
        "hover": "Median NTM TEV/GP",
        "scatter_y": "NTM TEV/GP",
    },
    "ntm_tev_ebitda": {
        "short": "TEV/EBITDA",
        "full": "NTM TEV/EBITDA",
        "chart_title": "NTM EBITDA Multiple by Segment (Median)",
        "bar_title": "Current Median NTM TEV/EBITDA by Segment",
        "y_axis": "Median NTM TEV/EBITDA",
        "hover": "Median NTM TEV/EBITDA",
        "scatter_y": "NTM TEV/EBITDA",
    },
    "ltm_tev_rev": {
        "short": "LTM TEV/Rev",
        "full": "LTM TEV/Revenue",
        "chart_title": "LTM Revenue Multiple by Segment (Median)",
        "bar_title": "Current Median LTM TEV/Revenue by Segment",
        "y_axis": "Median LTM TEV/Revenue",
        "hover": "Median LTM TEV/Rev",
        "scatter_y": "LTM TEV/Rev",
    },
    "ltm_tev_ebitda": {
        "short": "LTM TEV/EBITDA",
        "full": "LTM TEV/EBITDA",
        "chart_title": "LTM EBITDA Multiple by Segment (Median)",
        "bar_title": "Current Median LTM TEV/EBITDA by Segment",
        "y_axis": "Median LTM TEV/EBITDA",
        "hover": "Median LTM TEV/EBITDA",
        "scatter_y": "LTM TEV/EBITDA",
    },
    "growth_adj_rev": {
        "short": "GA Rev",
        "full": "Growth-Adj Revenue",
        "chart_title": "Growth-Adjusted Revenue Multiple by Segment (Median)",
        "bar_title": "Current Median Growth-Adj Revenue by Segment",
        "y_axis": "Median Growth-Adj Revenue",
        "hover": "Median GA Rev",
        "scatter_y": "Growth-Adj Rev",
    },
}

# Metrics available for the time-series multiple selector
TIMESERIES_METRICS = {
    "NTM TEV/Revenue":    "ntm_tev_rev",
    "NTM TEV/Gross Profit": "ntm_tev_gp",
    "NTM TEV/EBITDA":     "ntm_tev_ebitda",
    "LTM TEV/Revenue":    "ltm_tev_rev",
    "LTM TEV/EBITDA":     "ltm_tev_ebitda",
    "Growth-Adj Revenue": "growth_adj_rev",
}


def build_ntm_timeseries_chart(daily_data, days_back=365, metric="ntm_tev_rev"):
    """
    Build a time-series line chart of median NTM multiple by segment.
    Supports both ntm_tev_rev and ntm_tev_ebitda.
    Falls back to a bar chart if only 1 day of data exists.
    """
    labels = METRIC_LABELS.get(metric, METRIC_LABELS["ntm_tev_rev"])

    if not daily_data:
        return _empty_chart("No historical data available yet. Run the daily fetch to build history.")

    df = pd.DataFrame(daily_data)
    df["date"] = pd.to_datetime(df["date"])

    # Drop rows where the selected metric is null
    df = df.dropna(subset=[metric])

    # ── Outlier defence ───────────────────────────────────────────────────────
    # 1. Exclude non-positive multiples (negative EBITDA denominators produce
    #    economically meaningless values that distort segment medians wildly).
    df = df[df[metric] > 0].copy()
    # 2. Cap at 100x — prevents near-zero-but-positive denominators from
    #    creating absurd spikes (e.g. 134,000x).
    df[metric] = df[metric].clip(upper=100.0)
    # 3. Weekly bucketing — collapses daily live-fetch rows and weekly Excel
    #    history rows onto the same cadence so density is uniform.
    df["_week"] = df["date"].dt.to_period("W").dt.start_time
    df = df.groupby(["_week", "ticker", "segment"])[metric].mean().reset_index()
    df = df.rename(columns={"_week": "date"})
    # 4. Tukey IQR filter (1.5×) per week — removes per-company transient spikes.
    _q1  = df.groupby("date")[metric].transform(lambda s: s.quantile(0.25))
    _q3  = df.groupby("date")[metric].transform(lambda s: s.quantile(0.75))
    _iqr = _q3 - _q1
    df   = df[(df[metric] >= _q1 - 1.5 * _iqr) & (df[metric] <= _q3 + 1.5 * _iqr)].copy()
    # ─────────────────────────────────────────────────────────────────────────

    if df.empty:
        return _empty_chart(f"No {labels['short']} data available yet.")

    unique_dates = df["date"].dt.date.nunique()

    # If only 1-2 days of data, show a bar chart instead
    if unique_dates <= 2:
        return _build_segment_bar_chart(df, metric=metric)

    fig = go.Figure()

    for segment_key, segment_name in SEGMENT_DISPLAY.items():
        seg_df = df[df["segment"] == segment_key].copy()
        if seg_df.empty:
            continue

        daily_median = seg_df.groupby("date")[metric].median().reset_index()
        daily_median = daily_median.dropna(subset=[metric])
        daily_median = daily_median.sort_values("date")

        fig.add_trace(go.Scatter(
            x=daily_median["date"],
            y=daily_median[metric],
            mode="lines",
            name=segment_name,
            line=dict(color=SEGMENT_COLORS.get(segment_key, "#999"), width=2),
            hovertemplate=f"{segment_name}<br>%{{x|%b %d, %Y}}<br>{labels['hover']}: %{{y:.1f}}x<extra></extra>",
        ))

    layout = _base_layout(height=500, title=labels["chart_title"])
    layout["xaxis"]["title"] = "Date"
    layout["yaxis"]["title"] = labels["y_axis"]
    layout["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            font=dict(size=10), bgcolor="rgba(0,0,0,0)")
    layout["hovermode"] = "x unified"
    fig.update_layout(**layout)

    return fig


def _build_segment_bar_chart(df, metric="ntm_tev_rev"):
    """Bar chart of median multiple by segment when time-series data is limited."""
    labels = METRIC_LABELS.get(metric, METRIC_LABELS["ntm_tev_rev"])
    segment_medians = []
    for segment_key, segment_name in SEGMENT_DISPLAY.items():
        seg_df = df[df["segment"] == segment_key]
        if seg_df.empty:
            continue
        median_val = seg_df[metric].median()
        if pd.notna(median_val):
            segment_medians.append({
                "segment": segment_name,
                "segment_key": segment_key,
                "median": median_val,
            })

    if not segment_medians:
        return _empty_chart("No multiple data available.")

    sdf = pd.DataFrame(segment_medians)
    sdf = sdf.sort_values("median", ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=sdf["median"],
        y=sdf["segment"],
        orientation="h",
        marker_color=[SEGMENT_COLORS.get(k, "#999") for k in sdf["segment_key"]],
        text=[f"{v:.1f}x" for v in sdf["median"]],
        textposition="outside",
        textfont=dict(size=14, color=_FONT_CLR),
        hovertemplate=f"%{{y}}<br>{labels['hover']}: %{{x:.1f}}x<extra></extra>",
    ))

    layout = _base_layout(height=350, title=labels["bar_title"])
    layout["xaxis"]["title"] = labels["y_axis"]
    layout["xaxis"]["range"] = [0, max(sdf["median"]) * 1.3]
    layout["margin"]["l"] = 200
    layout["showlegend"] = False
    fig.update_layout(**layout)

    return fig


def build_segment_scatter(snapshots_by_segment, metric="ntm_tev_rev"):
    """
    Scatter plot: NTM Rev Growth (x) vs NTM multiple (y), sized by TEV, colored by segment.
    Shows individual company positioning across the growth-valuation spectrum.
    """
    labels = METRIC_LABELS.get(metric, METRIC_LABELS["ntm_tev_rev"])
    fig = go.Figure()

    for seg_key, seg_name in SEGMENT_DISPLAY.items():
        data = snapshots_by_segment.get(seg_key, [])
        if not data:
            continue

        df = pd.DataFrame(data)
        # Filter to companies with both growth and multiple data
        df = df.dropna(subset=["ntm_revenue_growth", metric])
        df = df[df[metric] > 0]
        if df.empty:
            continue

        # Size by TEV (normalize to reasonable bubble sizes)
        tev_billions = df["enterprise_value"].apply(lambda x: x / 1e9 if x and x > 0 else 1)
        sizes = np.clip(tev_billions * 1.5, 5, 60)

        fig.add_trace(go.Scatter(
            x=df["ntm_revenue_growth"] * 100,
            y=df[metric],
            mode="markers",
            name=seg_name,
            marker=dict(
                color=SEGMENT_COLORS.get(seg_key, "#999"),
                size=sizes,
                opacity=0.75,
                line=dict(width=1, color="#E5E7EB"),
            ),
            text=df["ticker"],
            hovertemplate=(
                "<b>%{text}</b><br>"
                f"Segment: {seg_name}<br>"
                "NTM Rev Growth: %{x:.1f}%<br>"
                f"{labels['scatter_y']}: %{{y:.1f}}x<br>"
                "<extra></extra>"
            ),
        ))

    layout = _base_layout(height=550, title="Valuation vs. Growth (Bubble Size = TEV)")
    layout["xaxis"]["title"] = "NTM Revenue Growth (%)"
    layout["yaxis"]["title"] = labels["scatter_y"]
    layout["legend"] = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                            font=dict(size=10), bgcolor="rgba(0,0,0,0)")
    layout["hovermode"] = "closest"
    fig.update_layout(**layout)

    return fig


def build_multiple_distribution(snapshots_by_segment, metric="ntm_tev_rev", title="NTM TEV/Revenue Distribution"):
    """
    Box plot showing distribution of a multiple across segments.
    """
    fig = go.Figure()

    for seg_key, seg_name in SEGMENT_DISPLAY.items():
        data = snapshots_by_segment.get(seg_key, [])
        if not data:
            continue

        vals = [d[metric] for d in data if d.get(metric) and d[metric] > 0]
        if not vals:
            continue

        fig.add_trace(go.Box(
            y=vals,
            name=seg_name,
            marker_color=SEGMENT_COLORS.get(seg_key, "#999"),
            line_color=SEGMENT_COLORS.get(seg_key, "#999"),
            fillcolor=SEGMENT_COLORS.get(seg_key, "#999"),
            opacity=0.7,
            boxmean=True,
            hovertemplate=f"{seg_name}<br>%{{y:.1f}}x<extra></extra>",
        ))

    layout = _base_layout(height=450, title=title)
    layout["yaxis"]["title"] = "Multiple"
    layout["showlegend"] = False
    fig.update_layout(**layout)

    return fig


def build_segment_summary_cards(snapshots_by_segment, metric="ntm_tev_rev"):
    """
    Build summary metrics for each segment (current median of selected multiple).
    Returns a dict of segment_name -> {median, mean, count}.
    """
    summaries = {}
    for seg_key, seg_name in SEGMENT_DISPLAY.items():
        data = snapshots_by_segment.get(seg_key, [])
        if data:
            vals = [d[metric] for d in data if d.get(metric) and d[metric] > 0]
            if vals:
                summaries[seg_name] = {
                    "median": np.median(vals),
                    "mean": np.mean(vals),
                    "count": len(vals),
                }
    return summaries


def build_winners_losers_chart(data, metric_col, title, top_n=25, ascending=True):
    """
    Build a horizontal bar chart for winners or losers.
    """
    if not data:
        return _empty_chart("No data available.")

    df = pd.DataFrame(data)
    df = df.dropna(subset=[metric_col])
    df = df.sort_values(metric_col, ascending=ascending).head(top_n)

    colors = [
        "#22C55E" if v >= 0 else "#EF4444"
        for v in df[metric_col]
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df[metric_col] * 100,
        y=df["ticker"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:.1f}%" for v in df[metric_col] * 100],
        textposition="outside",
        textfont=dict(size=11, color=_FONT_CLR),
        hovertemplate="%{y}<br>%{x:.1f}%<extra></extra>",
    ))

    layout = _base_layout(height=max(400, top_n * 28), title=title)
    layout["xaxis"]["title"] = "Price Change (%)"
    layout["yaxis"]["autorange"] = "reversed" if not ascending else True
    layout["margin"]["l"] = 80
    fig.update_layout(**layout)

    return fig


def _empty_chart(message):
    """Return an empty figure with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=14, color="#9CA3AF", family=_FONT_FAM),
    )
    fig.update_layout(
        plot_bgcolor=_PLOT_BG,
        paper_bgcolor=_PAPER_BG,
        height=380,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig
