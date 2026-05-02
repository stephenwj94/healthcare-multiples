"""
FactSet REST API fetcher — **sole** data source for the healthcare multiples app.

Endpoints used:
- /content/factset-fundamentals/v2/fundamentals — annual financials, EV, market cap
- /content/factset-fundamentals/v2/fundamentals — 52-week high (separate call, "price" data type)
- /content/factset-estimates/v2/rolling-consensus — consensus estimates relative to FY
- /content/factset-global-prices/v1/prices — daily closing prices (~90 days)
- /content/factset-global-prices/v1/security-shares — shares outstanding

Notes on units / currency:
- Fundamentals values are returned in MILLIONS of the reporting currency.
- Estimates: `mean` is in the metric's reported scale (also millions for SALES/EBITDA);
  `currency` is "LOCAL" but `estimateCurrency` gives the actual reporting code.
- Global Prices returns prices in the security's local currency.
- `security-shares` returns `totalOutstanding` in millions.
- We multiply all monetary values by 1e6 in the parser so downstream
  `compute_all_metrics` (which expects absolute dollars from FMP/yfinance) works
  unchanged. FX conversion is then handled by `_convert_financials_to_usd`.
"""

import logging
from datetime import date, timedelta

import requests

from config.factset_registry import display_to_factset

logger = logging.getLogger(__name__)

BASE_URL = "https://api.factset.com"
DEFAULT_TIMEOUT = 30

# Fundamentals metrics — fetched in a single call per company.
# EV and market cap are period-end values (in millions).
FUND_METRICS = [
    "FF_SALES",
    "FF_GROSS_INC",
    "FF_COGS",
    "FF_EBITDA_OPER",
    "FF_DEBT",
    "FF_DEBT_LT",
    "FF_DEBT_ST",
    "FF_CASH_GENERIC",
    "FF_CASH_ST",
    "FF_COM_SHS_OUT_EPS_DIL",
    "FF_ENTRPR_VAL",
    "FF_MKT_VAL",
]

# 52-week high is a "price" data type — cannot be mixed with numeric fundamentals.
PRICE_METRICS = ["FF_PRICE_HIGH_52WK"]

# Estimates metrics
EST_METRICS = ["SALES", "EBITDA"]

# Long-term EPS growth (5y consensus). Note: official metric ID is EPS_LTG.
LTG_METRIC = "EPS_LTG"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------
def _get(path, params, username_serial, api_key, timeout=DEFAULT_TIMEOUT):
    """GET an endpoint with HTTP basic auth. Returns parsed JSON or None on error."""
    url = f"{BASE_URL}{path}"
    try:
        r = requests.get(
            url,
            params=params,
            auth=(username_serial, api_key),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        if r.status_code == 200 and r.text.strip():
            return r.json()
        if r.status_code == 401:
            logger.error(f"FactSet 401 unauthorized for {path}")
        elif r.status_code == 403:
            logger.warning(f"FactSet 403 forbidden for {path} — endpoint not entitled")
        elif r.status_code == 429:
            logger.warning(f"FactSet 429 rate limited for {path}")
        else:
            logger.warning(f"FactSet {r.status_code} for {path}: {r.text[:200]}")
        return None
    except Exception as exc:
        logger.warning(f"FactSet request failed for {path}: {exc}")
        return None


def _post(path, json_body, username_serial, api_key, timeout=DEFAULT_TIMEOUT):
    """POST an endpoint with HTTP basic auth. Returns parsed JSON or None on error."""
    url = f"{BASE_URL}{path}"
    try:
        r = requests.post(
            url,
            json=json_body,
            auth=(username_serial, api_key),
            timeout=timeout,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        if r.status_code == 200 and r.text.strip():
            return r.json()
        if r.status_code == 401:
            logger.error(f"FactSet 401 unauthorized for {path}")
        elif r.status_code == 403:
            logger.warning(f"FactSet 403 forbidden for {path} — endpoint not entitled")
        elif r.status_code == 429:
            logger.warning(f"FactSet 429 rate limited for {path}")
        else:
            logger.warning(f"FactSet {r.status_code} for {path}: {r.text[:200]}")
        return None
    except Exception as exc:
        logger.warning(f"FactSet request failed for {path}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Public fetcher
# ---------------------------------------------------------------------------
def fetch_company_data_factset(ticker, factset_id=None, *, username_serial, api_key, timeout=DEFAULT_TIMEOUT):
    """
    Pull all FactSet data for a single company.

    Args:
        ticker: display ticker (e.g. "LLY"). Used to resolve the FactSet ID
                via the registry if `factset_id` isn't supplied.
        factset_id: optional explicit FactSet identifier (e.g. "LLY-US", "ROG-CH").
        username_serial / api_key: HTTP basic auth credentials.
        timeout: per-request timeout in seconds.

    Returns:
        dict with keys: factset_id, fundamentals, price_fundamentals, estimates, ltg,
                        prices, shares.
        Each value is the raw parsed JSON payload (or None on error).
    """
    fs_id = factset_id or display_to_factset(ticker)

    # 1. Annual fundamentals (financials + EV + market cap).
    fundamentals_params = {
        "ids": fs_id,
        "metrics": ",".join(FUND_METRICS),
        "fiscalPeriodStart": "2023-01-01",
        "fiscalPeriodEnd": "2026-12-31",
        "periodicity": "ANN",
    }
    fundamentals = _get(
        "/content/factset-fundamentals/v2/fundamentals",
        fundamentals_params,
        username_serial,
        api_key,
        timeout,
    )

    # 2. 52-week high — "price" data type, must be a separate call.
    price_fund_params = {
        "ids": fs_id,
        "metrics": ",".join(PRICE_METRICS),
        "fiscalPeriodStart": "2023-01-01",
        "fiscalPeriodEnd": "2026-12-31",
        "periodicity": "ANN",
    }
    price_fundamentals = _get(
        "/content/factset-fundamentals/v2/fundamentals",
        price_fund_params,
        username_serial,
        api_key,
        timeout,
    )

    # 3. Consensus estimates: FY0, FY1, FY2 for revenue and EBITDA.
    estimates_params = {
        "ids": fs_id,
        "metrics": ",".join(EST_METRICS),
        "periodicity": "ANN",
        "relativeFiscalStart": 0,
        "relativeFiscalEnd": 2,
    }
    estimates = _get(
        "/content/factset-estimates/v2/rolling-consensus",
        estimates_params,
        username_serial,
        api_key,
        timeout,
    )

    # 4. Long-term EPS growth — single relative period (FY0).
    ltg_params = {
        "ids": fs_id,
        "metrics": LTG_METRIC,
        "periodicity": "ANN",
        "relativeFiscalStart": 0,
        "relativeFiscalEnd": 0,
    }
    ltg = _get(
        "/content/factset-estimates/v2/rolling-consensus",
        ltg_params,
        username_serial,
        api_key,
        timeout,
    )

    # 5. Daily prices — ~90 calendar days of history.
    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=90)).isoformat()
    prices = _get(
        "/content/factset-global-prices/v1/prices",
        {"ids": fs_id, "startDate": start_date, "endDate": end_date},
        username_serial,
        api_key,
        timeout,
    )

    # 6. Shares outstanding.
    shares = _get(
        "/content/factset-global-prices/v1/security-shares",
        {"ids": fs_id},
        username_serial,
        api_key,
        timeout,
    )

    return {
        "factset_id": fs_id,
        "fundamentals": fundamentals,
        "price_fundamentals": price_fundamentals,
        "estimates": estimates,
        "ltg": ltg,
        "prices": prices,
        "shares": shares,
    }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _safe_num(val):
    if val is None:
        return None
    try:
        f = float(val)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _latest_fund_row(rows, metric_name):
    """Return the row with the highest fiscalYear for the given metric, or None."""
    if not rows:
        return None
    candidates = [r for r in rows if r.get("metric") == metric_name and r.get("value") is not None]
    if not candidates:
        return None
    candidates.sort(key=lambda r: r.get("fiscalYear") or 0)
    return candidates[-1]


def _est_row(rows, metric_name, relative_period):
    if not rows:
        return None
    for r in rows:
        if r.get("metric") == metric_name and r.get("relativePeriod") == relative_period:
            return r
    return None


def parse_factset_data(fs_data, company_info):
    """
    Convert the raw FactSet payload into a flat metrics dict matching the keys
    used by `compute_all_metrics`. All monetary values are scaled to absolute
    units (FactSet returns millions; we multiply by 1e6).
    """
    metrics = {"data_source": "factset"}

    fund_rows = ((fs_data or {}).get("fundamentals") or {}).get("data") or []
    price_fund_rows = ((fs_data or {}).get("price_fundamentals") or {}).get("data") or []
    est_rows = ((fs_data or {}).get("estimates") or {}).get("data") or []
    ltg_rows = ((fs_data or {}).get("ltg") or {}).get("data") or []
    price_rows = ((fs_data or {}).get("prices") or {}).get("data") or []
    shares_rows = ((fs_data or {}).get("shares") or {}).get("data") or []

    # ---- Pull most-recent FY rows per metric ----
    sales_row = _latest_fund_row(fund_rows, "FF_SALES")
    gross_row = _latest_fund_row(fund_rows, "FF_GROSS_INC")
    cogs_row = _latest_fund_row(fund_rows, "FF_COGS")
    ebitda_row = _latest_fund_row(fund_rows, "FF_EBITDA_OPER")
    debt_row = _latest_fund_row(fund_rows, "FF_DEBT")
    debt_lt_row = _latest_fund_row(fund_rows, "FF_DEBT_LT")
    debt_st_row = _latest_fund_row(fund_rows, "FF_DEBT_ST")
    cash_row = _latest_fund_row(fund_rows, "FF_CASH_GENERIC")
    cash_st_row = _latest_fund_row(fund_rows, "FF_CASH_ST")
    shares_fund_row = _latest_fund_row(fund_rows, "FF_COM_SHS_OUT_EPS_DIL")
    ev_row = _latest_fund_row(fund_rows, "FF_ENTRPR_VAL")
    mktval_row = _latest_fund_row(fund_rows, "FF_MKT_VAL")
    high52_row = _latest_fund_row(price_fund_rows, "FF_PRICE_HIGH_52WK")

    sales = _safe_num(sales_row.get("value")) if sales_row else None
    gross = _safe_num(gross_row.get("value")) if gross_row else None
    cogs = _safe_num(cogs_row.get("value")) if cogs_row else None
    ebitda = _safe_num(ebitda_row.get("value")) if ebitda_row else None
    debt = _safe_num(debt_row.get("value")) if debt_row else None
    debt_lt = _safe_num(debt_lt_row.get("value")) if debt_lt_row else None
    debt_st = _safe_num(debt_st_row.get("value")) if debt_st_row else None
    cash = _safe_num(cash_row.get("value")) if cash_row else None
    cash_st = _safe_num(cash_st_row.get("value")) if cash_st_row else None
    shares_fund = _safe_num(shares_fund_row.get("value")) if shares_fund_row else None
    ev_fund = _safe_num(ev_row.get("value")) if ev_row else None
    mktval_fund = _safe_num(mktval_row.get("value")) if mktval_row else None
    high_52wk = _safe_num(high52_row.get("value")) if high52_row else None

    # Fallbacks
    if gross is None and sales is not None and cogs is not None:
        gross = sales - cogs
    if debt is None and (debt_lt is not None or debt_st is not None):
        debt = (debt_lt or 0) + (debt_st or 0)
    if cash is None and cash_st is not None:
        cash = cash_st

    # FactSet fundamentals are in MILLIONS — multiply by 1e6 to match FMP/yfinance scale.
    SCALE = 1e6
    metrics["ltm_revenue"] = sales * SCALE if sales is not None else None
    metrics["ltm_gross_profit"] = gross * SCALE if gross is not None else None
    metrics["ltm_ebitda"] = ebitda * SCALE if ebitda is not None else None
    metrics["total_debt"] = debt * SCALE if debt is not None else None
    metrics["total_cash"] = cash * SCALE if cash is not None else None
    metrics["shares_outstanding"] = shares_fund * SCALE if shares_fund is not None else None

    # EV and market cap from fundamentals (period-end, in millions → scale).
    metrics["enterprise_value"] = ev_fund * SCALE if ev_fund is not None else None
    metrics["market_cap"] = mktval_fund * SCALE if mktval_fund is not None else None

    # 52-week high is a price — NOT in millions.
    metrics["fifty_two_week_high"] = high_52wk

    # ---- Global Prices: current price + price history ----
    current_price = None
    price_currency = None
    price_history = []
    if price_rows:
        # Sort by date ascending so the last entry is the most recent.
        sorted_prices = sorted(price_rows, key=lambda r: r.get("date", ""))
        for row in sorted_prices:
            p = _safe_num(row.get("price"))
            if p is not None:
                price_history.append({"date": row.get("date"), "price": p})
        if price_history:
            current_price = price_history[-1]["price"]
        # Currency from the prices response
        price_currency = sorted_prices[0].get("currency") if sorted_prices else None
    metrics["current_price"] = current_price
    metrics["price_history"] = price_history if price_history else None

    # ---- Shares outstanding from Global Prices security-shares ----
    shares_gp = None
    if shares_rows:
        # Pick the most recent entry
        for row in shares_rows:
            val = _safe_num(row.get("totalOutstanding"))
            if val is not None:
                shares_gp = val
    if shares_gp is not None:
        # security-shares returns totalOutstanding in millions
        metrics["shares_outstanding"] = shares_gp * SCALE

    # NOTE: We do NOT compute live market cap / EV here because for ADRs the
    # price currency (e.g. USD) may differ from the financial currency (e.g. DKK)
    # used for debt/cash.  Live computation happens in compute_all_metrics()
    # AFTER FX conversion, when all values are in USD.

    # Track the prior FY revenue for derived current_fy_rev_growth.
    prior_sales = None
    if sales_row:
        latest_fy = sales_row.get("fiscalYear")
        prior_candidates = [
            r for r in fund_rows
            if r.get("metric") == "FF_SALES"
            and r.get("value") is not None
            and (r.get("fiscalYear") or 0) < (latest_fy or 0)
        ]
        if prior_candidates:
            prior_candidates.sort(key=lambda r: r.get("fiscalYear") or 0)
            prior_sales = _safe_num(prior_candidates[-1].get("value"))

    # Margins
    if metrics["ltm_revenue"] and metrics["ltm_revenue"] > 0:
        if metrics["ltm_gross_profit"] is not None:
            metrics["gross_margin"] = metrics["ltm_gross_profit"] / metrics["ltm_revenue"]
        if metrics["ltm_ebitda"] is not None:
            metrics["ebitda_margin"] = metrics["ltm_ebitda"] / metrics["ltm_revenue"]

    # ---- Estimates (consensus mean) ----
    sales_fy0 = _est_row(est_rows, "SALES", 0)
    sales_fy1 = _est_row(est_rows, "SALES", 1)
    ebitda_fy0 = _est_row(est_rows, "EBITDA", 0)
    ebitda_fy1 = _est_row(est_rows, "EBITDA", 1)

    cur_rev = _safe_num(sales_fy0.get("mean")) if sales_fy0 else None
    nxt_rev = _safe_num(sales_fy1.get("mean")) if sales_fy1 else None
    cur_ebitda = _safe_num(ebitda_fy0.get("mean")) if ebitda_fy0 else None
    nxt_ebitda = _safe_num(ebitda_fy1.get("mean")) if ebitda_fy1 else None

    metrics["current_fy_rev_est"] = cur_rev * SCALE if cur_rev is not None else None
    metrics["next_fy_rev_est"] = nxt_rev * SCALE if nxt_rev is not None else None
    metrics["current_fy_ebitda_est"] = cur_ebitda * SCALE if cur_ebitda is not None else None
    metrics["next_fy_ebitda_est"] = nxt_ebitda * SCALE if nxt_ebitda is not None else None

    # Derived growth rates (decimals, not %).
    if prior_sales and sales is not None and prior_sales > 0:
        metrics["current_fy_rev_growth"] = (sales - prior_sales) / prior_sales
    else:
        metrics["current_fy_rev_growth"] = None
    if cur_rev and nxt_rev and cur_rev > 0:
        metrics["next_fy_rev_growth"] = (nxt_rev - cur_rev) / cur_rev
    else:
        metrics["next_fy_rev_growth"] = None

    # ---- Long-term growth ----
    metrics["five_year_growth_rate"] = None
    if ltg_rows:
        ltg_val = _safe_num(ltg_rows[0].get("mean"))
        if ltg_val is not None:
            # FactSet returns this as a percentage (e.g. 13.4 for 13.4%).
            metrics["five_year_growth_rate"] = ltg_val / 100.0

    # ---- Currency ----
    # Prefer fundamentals reporting currency; fall back to price currency or estimateCurrency.
    currency = None
    for row in (sales_row, ebitda_row, debt_row, cash_row):
        if row and row.get("currency"):
            currency = row["currency"]
            break
    if not currency:
        for row in (sales_fy0, sales_fy1, ebitda_fy0, ebitda_fy1):
            if row:
                currency = row.get("estimateCurrency") or row.get("currency")
                if currency and currency != "LOCAL":
                    break
    metrics["currency"] = currency or "USD"

    # Trading/price currency (from Global Prices) — separate from financial currency.
    metrics["price_currency"] = price_currency or metrics["currency"]

    return metrics
