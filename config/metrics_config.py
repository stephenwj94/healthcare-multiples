"""
Column definitions, display names, formatting rules, and color thresholds
for the comp tables.
"""

# Column ordering for comp tables
COMP_TABLE_COLUMNS = [
    "ticker",
    "name",
    "tev_b",
    "pct_52wk_high",
    "ntm_revenue_m",
    "ntm_rev_growth",
    "gross_margin",
    "ebitda_margin",
    "n3y_cagr",
    "ntm_tev_rev",
    "ntm_tev_gp",
    "ntm_tev_ebitda",
    "ltm_tev_rev",
    "ltm_tev_gp",
    "ltm_tev_ebitda",
    "growth_adj_rev",
    "growth_adj_gp",
    "price_change_2w",
    "price_change_2m",
]

# Display names for column headers (shorter, cleaner)
COLUMN_DISPLAY_NAMES = {
    "ticker": "Ticker",
    "name": "Company",
    "tev_b": "TEV",
    "pct_52wk_high": "% 52W Hi",
    "ntm_revenue_m": "NTM Rev",
    "ntm_rev_growth": "Rev Gr%",
    "gross_margin": "Gross Mgn",
    "ebitda_margin": "EBITDA Mgn",
    "n3y_cagr": "3Y CAGR",
    "ntm_tev_rev": "NTM Rev x",
    "ntm_tev_gp": "NTM GP x",
    "ntm_tev_ebitda": "NTM EBITDA x",
    "ltm_tev_rev": "LTM Rev x",
    "ltm_tev_gp": "LTM GP x",
    "ltm_tev_ebitda": "LTM EBITDA x",
    "growth_adj_rev": "GA Rev",
    "growth_adj_gp": "GA GP",
    "price_change_2w": "2W Chg",
    "price_change_2m": "2M Chg",
}

# Format strings for each column type
COLUMN_FORMATS = {
    "tev_b": "${:.1f}B",
    "pct_52wk_high": "{:.0%}",
    "ntm_revenue_m": "${:,.0f}M",
    "ntm_rev_growth": "{:.1%}",
    "gross_margin": "{:.1%}",
    "ebitda_margin": "{:.1%}",
    "n3y_cagr": "{:.1%}",
    "ntm_tev_rev": "{:.1f}x",
    "ntm_tev_gp": "{:.1f}x",
    "ntm_tev_ebitda": "{:.1f}x",
    "ltm_tev_rev": "{:.1f}x",
    "ltm_tev_gp": "{:.1f}x",
    "ltm_tev_ebitda": "{:.1f}x",
    "growth_adj_rev": "{:.2f}x",
    "growth_adj_gp": "{:.2f}x",
    "price_change_2w": "{:.1%}",
    "price_change_2m": "{:.1%}",
}

# Color thresholds using muted professional palette
# Colors applied from first matching threshold (>=)
COLOR_THRESHOLDS = {
    "gross_margin": [
        (0.70, "#34D399"),   # emerald >= 70%
        (0.50, "#FBBF24"),   # amber 50-70%
        (0.0, "#F87171"),    # red < 50%
    ],
    "ebitda_margin": [
        (0.25, "#34D399"),   # emerald >= 25%
        (0.10, "#FBBF24"),   # amber 10-25%
        (0.0, "#F87171"),    # red < 10%
    ],
    "ntm_rev_growth": [
        (0.20, "#34D399"),   # emerald >= 20%
        (0.10, "#FBBF24"),   # amber 10-20%
        (0.0, "#F87171"),    # red < 10%
    ],
    "pct_52wk_high": [
        (0.90, "#34D399"),   # emerald >= 90%
        (0.70, "#FBBF24"),   # amber 70-90%
        (0.0, "#F87171"),    # red < 70%
    ],
    "price_change_2w": [
        (0.0, "#34D399"),    # emerald >= 0%
        (-1.0, "#F87171"),   # red < 0%
    ],
    "price_change_2m": [
        (0.0, "#34D399"),    # emerald >= 0%
        (-1.0, "#F87171"),   # red < 0%
    ],
}
