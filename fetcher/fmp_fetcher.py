"""
Financial Modeling Prep (FMP) data fetcher.

FMP Starter plan provides:
- /stable/profile (all tickers): market cap, price, 52-wk range, company info
- /stable/key-metrics-ttm (large caps): EV, EV/Sales, EV/EBITDA TTM
- /stable/ratios-ttm (large caps): margins, turnover ratios
- /stable/income-statement (large caps): revenue, gross profit, EBITDA
- /stable/balance-sheet-statement (large caps): debt, cash
- /stable/analyst-estimates (large caps, annual only): consensus revenue/EPS/EBITDA
- /stable/stock-price-change (large caps): multi-period returns
- /stable/historical-price-eod/light (large caps): daily prices

Strategy: Use FMP profile for all tickers (market cap, price data).
Use premium endpoints where they return 200. Fall back to yfinance for
anything FMP doesn't cover on the current plan.
"""

import requests
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com"
REQUEST_TIMEOUT = 15


def _get(endpoint, params, api_key):
    """Make a GET request to FMP stable API."""
    params["apikey"] = api_key
    url = f"{BASE_URL}/stable/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200 and r.text.strip():
            data = r.json()
            if isinstance(data, list):
                return data
            return [data] if data else []
        elif r.status_code == 402:
            # Premium endpoint not available on current plan
            return None
        elif r.status_code == 403:
            logger.warning(f"FMP 403 for {endpoint}: legacy endpoint")
            return None
        else:
            return None
    except Exception as e:
        logger.warning(f"FMP request failed for {endpoint}: {e}")
        return None


def fetch_fmp_profile(ticker, api_key):
    """
    Fetch company profile from FMP. Works for all tickers on Starter plan.
    Returns dict with market cap, price, 52-wk range, company info.
    """
    data = _get("profile", {"symbol": ticker}, api_key)
    if data and len(data) > 0:
        return data[0]
    return None


def fetch_fmp_quote(ticker, api_key):
    """Fetch real-time quote. May require premium for some tickers."""
    data = _get("quote", {"symbol": ticker}, api_key)
    if data and len(data) > 0:
        return data[0]
    return None


def fetch_fmp_key_metrics_ttm(ticker, api_key):
    """Fetch TTM key metrics (EV, EV/Sales, etc). Premium for some tickers."""
    data = _get("key-metrics-ttm", {"symbol": ticker}, api_key)
    if data and len(data) > 0:
        return data[0]
    return None


def fetch_fmp_ratios_ttm(ticker, api_key):
    """Fetch TTM financial ratios (margins). Premium for some tickers."""
    data = _get("ratios-ttm", {"symbol": ticker}, api_key)
    if data and len(data) > 0:
        return data[0]
    return None


def fetch_fmp_income_statement(ticker, api_key, limit=4, period="annual"):
    """Fetch income statements. Premium for some tickers."""
    data = _get("income-statement", {"symbol": ticker, "limit": limit, "period": period}, api_key)
    return data


def fetch_fmp_balance_sheet(ticker, api_key, limit=1):
    """Fetch balance sheet. Premium for some tickers."""
    data = _get("balance-sheet-statement", {"symbol": ticker, "limit": limit}, api_key)
    if data and len(data) > 0:
        return data[0]
    return None


def fetch_fmp_analyst_estimates(ticker, api_key, limit=5):
    """Fetch annual analyst estimates (revenue, EPS, EBITDA consensus). Premium for some tickers."""
    data = _get("analyst-estimates", {"symbol": ticker, "period": "annual", "limit": limit}, api_key)
    return data


def fetch_fmp_price_change(ticker, api_key):
    """Fetch multi-period price changes. Premium for some tickers."""
    data = _get("stock-price-change", {"symbol": ticker}, api_key)
    if data and len(data) > 0:
        return data[0]
    return None


def fetch_fmp_historical_prices(ticker, api_key, days_back=90):
    """Fetch historical daily prices. Premium for some tickers."""
    from_date = (date.today() - timedelta(days=days_back)).isoformat()
    data = _get("historical-price-eod/light", {"symbol": ticker, "from": from_date}, api_key)
    return data


def fetch_company_data_fmp(ticker, api_key):
    """
    Fetch all available data from FMP for a single company.
    Returns a dict with all the data we could get.
    Keys set to None if the endpoint isn't available on the current plan.
    """
    result = {
        "profile": fetch_fmp_profile(ticker, api_key),
        "quote": fetch_fmp_quote(ticker, api_key),
        "key_metrics_ttm": fetch_fmp_key_metrics_ttm(ticker, api_key),
        "ratios_ttm": fetch_fmp_ratios_ttm(ticker, api_key),
        "income_statements": fetch_fmp_income_statement(ticker, api_key, limit=4, period="annual"),
        "balance_sheet": fetch_fmp_balance_sheet(ticker, api_key),
        "analyst_estimates": fetch_fmp_analyst_estimates(ticker, api_key),
        "price_change": fetch_fmp_price_change(ticker, api_key),
    }
    return result


def parse_fmp_data(fmp_data, company_info):
    """
    Parse FMP API responses into a flat metrics dict matching our DB schema.
    Returns a dict of metrics, with None for anything unavailable.
    """
    metrics = {}
    profile = fmp_data.get("profile") or {}
    quote = fmp_data.get("quote") or {}
    km = fmp_data.get("key_metrics_ttm") or {}
    ratios = fmp_data.get("ratios_ttm") or {}
    estimates_list = fmp_data.get("analyst_estimates") or []
    income_stmts = fmp_data.get("income_statements") or []
    balance = fmp_data.get("balance_sheet") or {}
    price_chg = fmp_data.get("price_change") or {}

    # --- Profile data (available for all tickers) ---
    metrics["market_cap"] = _safe_num(profile.get("marketCap"))
    metrics["current_price"] = _safe_num(profile.get("price") or quote.get("price"))
    metrics["currency"] = profile.get("currency", "USD")

    # Parse 52-week range from profile
    price_range = profile.get("range", "")
    if price_range and "-" in price_range:
        parts = price_range.split("-")
        try:
            metrics["fifty_two_week_high"] = float(parts[-1].strip())
        except (ValueError, IndexError):
            metrics["fifty_two_week_high"] = None
    else:
        metrics["fifty_two_week_high"] = _safe_num(quote.get("yearHigh"))

    # --- Quote data (premium for some tickers) ---
    if quote:
        metrics["current_price"] = _safe_num(quote.get("price")) or metrics.get("current_price")
        metrics["fifty_two_week_high"] = _safe_num(quote.get("yearHigh")) or metrics.get("fifty_two_week_high")
        metrics["shares_outstanding"] = _safe_num(quote.get("sharesOutstanding"))

    # --- Key Metrics TTM (premium for some) ---
    if km:
        metrics["enterprise_value"] = _safe_num(km.get("enterpriseValueTTM"))
        # These are pre-calculated LTM multiples from FMP
        metrics["fmp_ev_to_sales_ttm"] = _safe_num(km.get("evToSalesTTM"))
        metrics["fmp_ev_to_ebitda_ttm"] = _safe_num(km.get("evToEBITDATTM"))

    # --- Ratios TTM (premium for some) ---
    if ratios:
        metrics["gross_margin"] = _safe_num(ratios.get("grossProfitMarginTTM"))
        metrics["ebitda_margin"] = _safe_num(ratios.get("ebitdaMarginTTM"))

    # --- Income Statements (premium for some) ---
    if income_stmts:
        latest = income_stmts[0]
        metrics["ltm_revenue"] = _safe_num(latest.get("revenue"))
        metrics["ltm_gross_profit"] = _safe_num(latest.get("grossProfit"))
        metrics["ltm_ebitda"] = _safe_num(latest.get("ebitda"))
        if not metrics.get("gross_margin") and metrics.get("ltm_revenue") and metrics["ltm_revenue"] > 0:
            gp = metrics.get("ltm_gross_profit", 0) or 0
            metrics["gross_margin"] = gp / metrics["ltm_revenue"]
        if not metrics.get("ebitda_margin") and metrics.get("ltm_revenue") and metrics["ltm_revenue"] > 0:
            ebitda = metrics.get("ltm_ebitda", 0) or 0
            metrics["ebitda_margin"] = ebitda / metrics["ltm_revenue"]

    # --- Balance Sheet (premium for some) ---
    if balance:
        metrics["total_debt"] = _safe_num(balance.get("totalDebt"))
        metrics["total_cash"] = _safe_num(balance.get("cashAndCashEquivalents"))
        if not metrics.get("total_cash"):
            metrics["total_cash"] = _safe_num(balance.get("cashAndShortTermInvestments"))

    # --- Analyst Estimates (premium for some, annual only) ---
    if estimates_list:
        today = date.today()
        # Sort by date ascending and find current FY and next FY
        sorted_est = sorted(estimates_list, key=lambda x: x.get("date", ""))
        current_fy_est = None
        next_fy_est = None
        for est in sorted_est:
            est_date_str = est.get("date", "")
            if not est_date_str:
                continue
            try:
                est_date = date.fromisoformat(est_date_str[:10])
            except ValueError:
                continue
            # Current FY: closest future date
            if est_date >= today and current_fy_est is None:
                current_fy_est = est
            elif est_date >= today and current_fy_est is not None and next_fy_est is None:
                next_fy_est = est

        if current_fy_est:
            metrics["current_fy_rev_est"] = _safe_num(current_fy_est.get("revenueAvg"))
            metrics["current_fy_ebitda_est"] = _safe_num(current_fy_est.get("ebitdaAvg"))
            metrics["current_fy_eps_est"] = _safe_num(current_fy_est.get("epsAvg"))
            metrics["num_analysts_revenue"] = _safe_num(current_fy_est.get("numAnalystsRevenue"))
        if next_fy_est:
            metrics["next_fy_rev_est"] = _safe_num(next_fy_est.get("revenueAvg"))
            metrics["next_fy_ebitda_est"] = _safe_num(next_fy_est.get("ebitdaAvg"))
            metrics["next_fy_eps_est"] = _safe_num(next_fy_est.get("epsAvg"))

    # --- Price Changes (premium for some) ---
    if price_chg:
        # FMP returns percentages as whole numbers (e.g., 5.2 for 5.2%)
        # We store as decimals (0.052)
        one_m = _safe_num(price_chg.get("1M"))
        three_m = _safe_num(price_chg.get("3M"))
        five_d = _safe_num(price_chg.get("5D"))
        # Approximate 2-week from 5D+1M blend, 2-month from 1M+3M blend
        # Better to let yfinance handle price changes
        metrics["fmp_price_change_1m"] = one_m / 100 if one_m is not None else None
        metrics["fmp_price_change_3m"] = three_m / 100 if three_m is not None else None

    return metrics


def _safe_num(val):
    """Safely convert to float, returning None for non-numeric."""
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None
