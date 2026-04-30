"""
Manual data overrides for companies where FMP/yfinance consistently return bad data.
These values take precedence over fetched data during compute_all_metrics().

Use this for:
  - Companies with known FX/ADR data issues
  - Stale or missing consensus estimates
  - Incorrect EV calculations from data providers
  - Delisted / taken-private companies still in the universe

Format: ticker -> dict of field overrides.
Only the specified fields are overridden; others still come from the automated fetch.

To update: Run the fetch first, review the VALIDATION warnings in the log,
then add overrides here for any remaining issues.

Sources for override values:
  - Capital IQ, Bloomberg, FactSet for consensus estimates
  - Company press releases for reported financials
  - SEC filings / annual reports for debt/cash
  - Morgan Stanley Software Weekly for cross-reference
"""

# Last updated: 2026-02-25
# Override values should be in USD (post-conversion)
DATA_OVERRIDES = {
    # Trend Micro — taken private in 2024/2025, 4704.T data is stale/incomplete
    # Acquisition at ~¥7,800/share × ~150M shares ≈ $7.8B equity value
    # Source: Broadcom/private equity filings, MS Software Weekly 02/20/2026
    "TMICY": {
        "enterprise_value": 4_800_000_000,      # ~$4.8B USD (takeout EV, net of cash)
        "ltm_revenue": 1_850_000_000,           # ~$1.85B USD (FY2025)
        "current_fy_rev_est": 1_900_000_000,    # CY2026E
        "next_fy_rev_est": 1_950_000_000,       # CY2027E
        "gross_margin": 0.769,                  # ~76.9%
        "ebitda_margin": 0.289,                 # ~28.9%
    },
}


def get_overrides(ticker):
    """Return override dict for a ticker, or empty dict if none."""
    return DATA_OVERRIDES.get(ticker, {})
