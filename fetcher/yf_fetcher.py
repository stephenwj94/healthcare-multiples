"""
yfinance data retrieval: fetches all raw data needed per company.
"""

import yfinance as yf
import pandas as pd
import logging

logger = logging.getLogger(__name__)


def fetch_company_data(yahoo_ticker):
    """
    Fetch all raw data for a single company from yfinance.

    Returns dict with keys:
        - info: dict from ticker.info
        - estimates: dict with current/next FY revenue estimates
        - growth: dict with 5-year growth rate
        - price_history: DataFrame with 3 months of daily prices
    """
    ticker = yf.Ticker(yahoo_ticker)
    result = {
        "info": {},
        "estimates": {},
        "growth": {},
        "price_history": None,
    }

    # 1. Basic info (TEV, margins, LTM financials, 52wk high, etc.)
    try:
        result["info"] = ticker.info or {}
    except Exception as e:
        logger.warning(f"{yahoo_ticker}: info fetch failed: {e}")
        result["info"] = {}

    # 2. Revenue estimates (NTM calculation)
    try:
        rev_est = ticker.revenue_estimate
        if rev_est is not None and not rev_est.empty:
            result["estimates"] = _parse_revenue_estimates(rev_est)
        else:
            # Fallback: try analyst_price_targets or other properties
            result["estimates"] = _fallback_estimates(ticker)
    except Exception as e:
        logger.warning(f"{yahoo_ticker}: revenue_estimate failed: {e}")
        result["estimates"] = _fallback_estimates(ticker)

    # 3. Growth estimates (N3Y CAGR proxy)
    try:
        growth_est = ticker.growth_estimates
        if growth_est is not None and not growth_est.empty:
            result["growth"] = _parse_growth_estimates(growth_est, yahoo_ticker)
    except Exception as e:
        logger.warning(f"{yahoo_ticker}: growth_estimates failed: {e}")

    # 4. Price history (for 2-week and 2-month price changes)
    try:
        hist = ticker.history(period="3mo")
        if hist is not None and not hist.empty:
            result["price_history"] = hist
    except Exception as e:
        logger.warning(f"{yahoo_ticker}: history fetch failed: {e}")

    return result


def _parse_revenue_estimates(rev_est):
    """Parse revenue_estimate DataFrame into a clean dict."""
    estimates = {}
    try:
        if "0y" in rev_est.index:
            row = rev_est.loc["0y"]
            estimates["current_fy_rev"] = _safe_float(row.get("avg"))
            estimates["current_fy_growth"] = _safe_float(row.get("growth"))
        if "+1y" in rev_est.index:
            row = rev_est.loc["+1y"]
            estimates["next_fy_rev"] = _safe_float(row.get("avg"))
            estimates["next_fy_growth"] = _safe_float(row.get("growth"))
    except Exception as e:
        logger.warning(f"Error parsing revenue estimates: {e}")
    return estimates


def _fallback_estimates(ticker):
    """Try alternative methods to get revenue estimates."""
    estimates = {}
    try:
        # Try using the earnings_estimate for any data
        info = ticker.info or {}
        # Some tickers have revenueEstimate in info
        rev_growth = info.get("revenueGrowth")
        total_rev = info.get("totalRevenue")
        if rev_growth is not None and total_rev:
            # Rough approximation: project forward using trailing growth
            estimates["current_fy_rev"] = total_rev * (1 + rev_growth)
            estimates["next_fy_rev"] = total_rev * (1 + rev_growth) ** 2
            estimates["current_fy_growth"] = rev_growth
            estimates["next_fy_growth"] = rev_growth
    except Exception:
        pass
    return estimates


def _parse_growth_estimates(growth_est, yahoo_ticker):
    """Parse growth_estimates DataFrame for 5-year growth rate."""
    growth = {}
    try:
        # growth_estimates has rows like '0q', '+1q', '0y', '+1y', '+5y', '-5y'
        # and columns per entity (the ticker column, industry, sector, S&P 500)
        if "+5y" in growth_est.index:
            # Get the company-specific column (first column that isn't 'Industry', 'Sector', 'S&P 500')
            for col in growth_est.columns:
                if col not in ("Industry", "Sector", "S&P 500", "industry", "sector"):
                    val = growth_est.loc["+5y", col]
                    growth["five_year"] = _safe_float(val)
                    break
            if "five_year" not in growth:
                # Try first column
                growth["five_year"] = _safe_float(growth_est.loc["+5y"].iloc[0])
    except Exception as e:
        logger.warning(f"{yahoo_ticker}: growth_estimates parsing failed: {e}")
    return growth


def _safe_float(val):
    """Convert a value to float, returning None if not possible."""
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (TypeError, ValueError):
        return None
