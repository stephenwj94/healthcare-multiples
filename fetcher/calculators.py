"""
Financial metric calculations: NTM calendarization, multiples, CAGR, price changes.
Includes FX conversion for foreign-listed companies and data validation.
"""

from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation thresholds — flag or null out obviously broken data
# ---------------------------------------------------------------------------
MAX_REASONABLE_TEV_REV = 60.0      # Multiples above 60x are almost certainly wrong
MIN_REASONABLE_TEV_B = 0.05        # TEV below $50M for our universe is suspect
MAX_REASONABLE_TEV_B = 1500.0      # Largest healthcare names (LLY, JNJ) exceed $500B legitimately; raise ceiling.
MIN_REASONABLE_NTM_REV = 10e6      # NTM revenue below $10M is suspect for public SW co


def calc_ntm_revenue(current_fy_rev_est, next_fy_rev_est, fy_end_month):
    """
    NTM Revenue = weighted interpolation between current FY and next FY estimates.
    Weight for current FY = months remaining in current FY / 12.
    """
    if not current_fy_rev_est or not next_fy_rev_est:
        return current_fy_rev_est or next_fy_rev_est

    today = date.today()
    fy_end_year = today.year if today.month <= fy_end_month else today.year + 1
    months_remaining = max(0, (fy_end_year - today.year) * 12 + fy_end_month - today.month)
    months_remaining = min(12, months_remaining)

    weight_current = months_remaining / 12.0
    weight_next = 1.0 - weight_current

    return (weight_current * current_fy_rev_est) + (weight_next * next_fy_rev_est)


def calc_ntm_ebitda(current_fy_ebitda_est, next_fy_ebitda_est, fy_end_month):
    """
    NTM EBITDA = weighted interpolation between current FY and next FY EBITDA estimates.
    Same calendarization logic as calc_ntm_revenue().
    Returns None if no consensus EBITDA estimates are available.
    """
    if not current_fy_ebitda_est or not next_fy_ebitda_est:
        return current_fy_ebitda_est or next_fy_ebitda_est

    today = date.today()
    fy_end_year = today.year if today.month <= fy_end_month else today.year + 1
    months_remaining = max(0, (fy_end_year - today.year) * 12 + fy_end_month - today.month)
    months_remaining = min(12, months_remaining)

    weight_current = months_remaining / 12.0
    weight_next = 1.0 - weight_current

    return (weight_current * current_fy_ebitda_est) + (weight_next * next_fy_ebitda_est)


def calc_ntm_revenue_growth(current_fy_rev_growth, next_fy_rev_growth, fy_end_month):
    """
    NTM Revenue Growth = time-weighted blend of current-FY and next-FY analyst
    growth estimates, using the same calendarization weights as calc_ntm_revenue().

    The old approach (NTM Revenue / LTM Revenue - 1) systematically overstated
    growth for non-December FY companies because it compared forward estimates
    against a stale LTM window — e.g. for a January-FY company the numerator is
    essentially FY+2 while the denominator anchors to FY+0 actuals, embedding two
    years of compounding into one metric.  Using analyst FY growth rates and
    blending by months-remaining eliminates that distortion and aligns with the
    calendar-year growth convention used by broker comp tables (e.g. CY2026/CY2025).
    """
    today = date.today()
    fy_end_year = today.year if today.month <= fy_end_month else today.year + 1
    months_remaining = max(0, (fy_end_year - today.year) * 12 + fy_end_month - today.month)
    months_remaining = min(12, months_remaining)

    w_curr = months_remaining / 12.0
    w_next = 1.0 - w_curr

    if current_fy_rev_growth is not None and next_fy_rev_growth is not None:
        return w_curr * current_fy_rev_growth + w_next * next_fy_rev_growth
    elif current_fy_rev_growth is not None:
        return current_fy_rev_growth
    elif next_fy_rev_growth is not None:
        return next_fy_rev_growth
    return None


def calc_tev(market_cap, total_debt, total_cash):
    """TEV = Market Cap + Total Debt - Total Cash."""
    if not market_cap:
        return None
    debt = total_debt or 0
    cash = total_cash or 0
    return market_cap + debt - cash


def calc_pct_52wk_high(current_price, fifty_two_week_high):
    """Current price as % of 52-week high."""
    if current_price and fifty_two_week_high and fifty_two_week_high > 0:
        return current_price / fifty_two_week_high
    return None


def calc_ntm_tev_rev(tev, ntm_revenue):
    """TEV / NTM Revenue."""
    if tev and ntm_revenue and ntm_revenue > 0:
        return tev / ntm_revenue
    return None


def calc_ntm_tev_gp(tev, ntm_revenue, gross_margin):
    """TEV / NTM Gross Profit (NTM Revenue * Gross Margin)."""
    if tev and ntm_revenue and gross_margin and gross_margin > 0:
        ntm_gp = ntm_revenue * gross_margin
        return tev / ntm_gp if ntm_gp > 0 else None
    return None


def calc_ntm_tev_ebitda(tev, ntm_ebitda_consensus=None, ntm_revenue=None, ebitda_margin=None):
    """
    TEV / NTM EBITDA.
    Prefers consensus NTM EBITDA from analyst estimates (calendarized).
    Falls back to NTM Revenue * EBITDA Margin if no consensus available.
    """
    ntm_ebitda = ntm_ebitda_consensus
    if not ntm_ebitda and ntm_revenue and ebitda_margin and ebitda_margin > 0:
        ntm_ebitda = ntm_revenue * ebitda_margin
    if tev and ntm_ebitda and ntm_ebitda > 0:
        return tev / ntm_ebitda
    return None


def calc_ltm_tev_rev(tev, ltm_revenue):
    """TEV / LTM Revenue."""
    if tev and ltm_revenue and ltm_revenue > 0:
        return tev / ltm_revenue
    return None


def calc_ltm_tev_gp(tev, ltm_gross_profit):
    """TEV / LTM Gross Profit."""
    if tev and ltm_gross_profit and ltm_gross_profit > 0:
        return tev / ltm_gross_profit
    return None


def calc_ltm_tev_ebitda(tev, ltm_ebitda):
    """TEV / LTM EBITDA."""
    if tev and ltm_ebitda and ltm_ebitda > 0:
        return tev / ltm_ebitda
    return None


def calc_growth_adj_multiple(multiple, growth_pct):
    """Growth-adjusted multiple = multiple / (growth% as whole number)."""
    if multiple and growth_pct and growth_pct > 0:
        growth_whole = growth_pct * 100  # Convert 0.20 to 20
        if growth_whole > 0:
            return multiple / growth_whole
    return None


def calc_n3y_cagr(five_year_growth_rate, current_fy_rev, next_fy_rev):
    """
    Approximate N3Y Revenue CAGR.
    Uses 5-year growth rate if available, otherwise 1-year estimate growth.
    """
    if five_year_growth_rate is not None:
        return five_year_growth_rate
    if current_fy_rev and next_fy_rev and current_fy_rev > 0:
        return (next_fy_rev / current_fy_rev) - 1.0
    return None


def calc_price_changes(price_history):
    """
    Compute 2-week and 2-month price changes from a price history.
    Accepts either a pandas DataFrame (yfinance) with "Close" column
    or a list of {date, price} dicts (FactSet).
    Returns (change_2w, change_2m) as decimals.
    """
    if price_history is None:
        return None, None

    # Extract a list of closing prices from either format.
    closes = None
    if isinstance(price_history, list):
        # FactSet format: list of {date, price} dicts
        closes = [row["price"] for row in price_history if row.get("price") is not None]
    elif hasattr(price_history, "__len__") and len(price_history) >= 2:
        # pandas DataFrame from yfinance
        col = price_history.get("Close") if hasattr(price_history, "get") else None
        if col is not None and hasattr(col, "iloc"):
            closes = list(col)

    if not closes or len(closes) < 2:
        return None, None

    latest = closes[-1]

    # 2-week ~ 10 trading days
    idx_2w = min(10, len(closes) - 1)
    price_2w_ago = closes[-(idx_2w + 1)]
    change_2w = (latest / price_2w_ago) - 1.0 if price_2w_ago > 0 else None

    # 2-month ~ 42 trading days
    idx_2m = min(42, len(closes) - 1)
    price_2m_ago = closes[-(idx_2m + 1)]
    change_2m = (latest / price_2m_ago) - 1.0 if price_2m_ago > 0 else None

    return change_2w, change_2m


def _convert_financials_to_usd(metrics_dict, financial_currency, trading_currency):
    """
    Convert financial statement items from their reporting currency to USD.

    Scenarios:
    1. Foreign-listed (e.g., NEM.DE): EVERYTHING is in local currency.
       → Convert market cap, EV, revenue, debt, cash all to USD.
    2. US-listed ADR (e.g., DASTY): Price/market cap in USD, financials in EUR.
       → Only convert revenue, GP, EBITDA, debt, cash, estimates to USD.
    3. Foreign-listed, reports in USD (e.g., CSU.TO): Market items in CAD, financials in USD.
       → Only convert market cap, EV, price to USD.
    4. London stocks (GBp): yfinance uses "GBp" for price but marketCap/EV/financials are in GBP.
       → Convert market items and financials from GBP (NOT GBp) to USD.
    """
    from fetcher.ticker_utils import convert_to_usd, get_fx_rate

    needs_fin_conversion = (financial_currency != "USD")
    needs_mkt_conversion = (trading_currency != "USD")

    if not needs_fin_conversion and not needs_mkt_conversion:
        return metrics_dict

    # --- Handle London Stock Exchange GBp quirk ---
    # yfinance reports currency as "GBp" (pence) but marketCap, EV, and financials
    # are actually in GBP (pounds), not pence. Only share price is in pence.
    # So for non-price items, treat GBp as GBP.
    mkt_currency_for_values = trading_currency
    if trading_currency in ("GBp", "GBX"):
        mkt_currency_for_values = "GBP"
        # Only the share price needs the pence→GBP conversion
        if metrics_dict.get("current_price"):
            metrics_dict["current_price"] = metrics_dict["current_price"] / 100.0 * get_fx_rate("GBP", "USD")
        if metrics_dict.get("fifty_two_week_high"):
            metrics_dict["fifty_two_week_high"] = metrics_dict["fifty_two_week_high"] / 100.0 * get_fx_rate("GBP", "USD")

    # --- Convert financial statement items (revenue, debt, cash, estimates) ---
    if needs_fin_conversion:
        logger.info(f"  Converting financials from {financial_currency} to USD")
        fin_keys = [
            "ltm_revenue", "ltm_gross_profit", "ltm_ebitda",
            "current_fy_rev_est", "next_fy_rev_est",
            "current_fy_ebitda_est", "next_fy_ebitda_est",
            "total_debt", "total_cash",
        ]
        for key in fin_keys:
            if metrics_dict.get(key):
                metrics_dict[key] = convert_to_usd(metrics_dict[key], financial_currency)

    # --- Convert market-related items (market cap, EV) ---
    if needs_mkt_conversion:
        logger.info(f"  Converting market items from {mkt_currency_for_values} to USD")
        mkt_keys = ["market_cap", "enterprise_value"]
        for key in mkt_keys:
            if metrics_dict.get(key):
                metrics_dict[key] = convert_to_usd(metrics_dict[key], mkt_currency_for_values)

        # Price was already handled above for GBp; for other currencies convert now
        if mkt_currency_for_values not in ("GBP",) or trading_currency not in ("GBp", "GBX"):
            for key in ["current_price", "fifty_two_week_high"]:
                if metrics_dict.get(key):
                    metrics_dict[key] = convert_to_usd(metrics_dict[key], mkt_currency_for_values)

    return metrics_dict


def _validate_metrics(metrics_dict, ticker):
    """
    Sanity-check computed metrics and null out obviously broken values.
    Returns the dict with problematic values set to None.
    """
    ev = metrics_dict.get("enterprise_value")
    ntm_rev = metrics_dict.get("ntm_revenue")
    ntm_tev_rev = metrics_dict.get("ntm_tev_rev")
    market_cap = metrics_dict.get("market_cap")

    issues = []

    # Check 1: TEV sanity
    if ev is not None:
        ev_b = ev / 1e9
        if ev_b > MAX_REASONABLE_TEV_B:
            issues.append(f"TEV ${ev_b:.1f}B exceeds ${MAX_REASONABLE_TEV_B}B — likely FX error")
            metrics_dict["enterprise_value"] = None
            metrics_dict["ntm_tev_rev"] = None
            metrics_dict["ltm_tev_rev"] = None
            metrics_dict["ntm_tev_gp"] = None
            metrics_dict["ntm_tev_ebitda"] = None
        elif ev_b < MIN_REASONABLE_TEV_B and market_cap and market_cap / 1e9 > 1.0:
            issues.append(f"TEV ${ev_b:.1f}B seems too low vs mkt cap ${market_cap/1e9:.1f}B")

    # Check 2: NTM Revenue sanity
    if ntm_rev is not None and ntm_rev < MIN_REASONABLE_NTM_REV:
        issues.append(f"NTM Rev ${ntm_rev/1e6:.1f}M below ${MIN_REASONABLE_NTM_REV/1e6:.0f}M threshold")
        metrics_dict["ntm_revenue"] = None
        metrics_dict["ntm_tev_rev"] = None
        metrics_dict["ntm_revenue_growth"] = None

    # Check 3: Multiple sanity
    if ntm_tev_rev is not None:
        if ntm_tev_rev > MAX_REASONABLE_TEV_REV:
            issues.append(f"NTM TEV/Rev {ntm_tev_rev:.1f}x exceeds {MAX_REASONABLE_TEV_REV}x — nulling")
            metrics_dict["ntm_tev_rev"] = None
        elif ntm_tev_rev < 0:
            issues.append(f"NTM TEV/Rev {ntm_tev_rev:.1f}x is negative — nulling")
            metrics_dict["ntm_tev_rev"] = None

    # Check 4: Margin sanity (should be between -2.0 and 1.0)
    for margin_key in ("gross_margin", "ebitda_margin"):
        val = metrics_dict.get(margin_key)
        if val is not None and (val > 1.0 or val < -2.0):
            issues.append(f"{margin_key} = {val:.2f} out of range [-2.0, 1.0]")
            metrics_dict[margin_key] = None

    # Check 5: All-zero check (completely broken data)
    critical_fields = ["enterprise_value", "market_cap", "ltm_revenue"]
    all_zero = all((metrics_dict.get(k) or 0) == 0 for k in critical_fields)
    if all_zero:
        issues.append("All critical fields are zero/null — data fetch likely failed")

    if issues:
        for issue in issues:
            logger.warning(f"  VALIDATION [{ticker}]: {issue}")

    return metrics_dict


def compute_all_metrics(raw_data, company_info, fmp_metrics=None, factset_metrics=None):
    """
    Compute all derived metrics from raw yfinance data, optionally
    enhanced with FactSet (highest priority) and/or FMP data.

    Source priority for each field: FactSet > FMP > yfinance > computed.

    raw_data: dict with keys from yf_fetcher
    company_info: dict from company_registry
    fmp_metrics: optional dict from fmp_fetcher.parse_fmp_data()
    factset_metrics: optional dict from factset_rest.parse_factset_data()

    Returns: dict of all metric columns for company_snapshots table
    """
    info = raw_data.get("info", {})
    estimates = raw_data.get("estimates", {})
    growth = raw_data.get("growth", {})
    price_hist = raw_data.get("price_history")
    fmp = fmp_metrics or {}
    fs = factset_metrics or {}

    # Load manual overrides if available
    try:
        from config.data_overrides import get_overrides
        overrides = get_overrides(company_info.get("ticker", ""))
    except ImportError:
        overrides = {}

    # Helper: returns first non-None across (FactSet, FMP, yfinance) priority order.
    def prefer(*vals):
        for v in vals:
            if v is not None:
                return v
        return None

    # Raw values — FactSet is primary source for everything including market data.
    #
    # Period-end FF_MKT_VAL / FF_ENTRPR_VAL from FactSet fundamentals are in the
    # financial reporting currency.  For ADRs (price in USD, financials in DKK/EUR/etc.)
    # the FX conversion path treats market items as being in trading_currency, so
    # these period-end values would NOT be converted.  Only use them when the
    # financial and price currencies match; otherwise fall through to FMP/yfinance
    # or the live computation (price × shares) which runs after FX conversion.
    fs_currencies_match = (
        not fs.get("price_currency")
        or not fs.get("currency")
        or fs.get("price_currency") == fs.get("currency")
    )
    fs_mkt = fs.get("market_cap") if fs_currencies_match else None
    fs_ev = fs.get("enterprise_value") if fs_currencies_match else None

    market_cap = prefer(fs_mkt, fmp.get("market_cap"), info.get("marketCap"))
    current_price = prefer(
        fs.get("current_price"),
        fmp.get("current_price"),
        info.get("currentPrice") or info.get("regularMarketPrice"),
    )
    high_52wk = prefer(fs.get("fifty_two_week_high"), fmp.get("fifty_two_week_high"), info.get("fiftyTwoWeekHigh"))
    total_debt = prefer(fs.get("total_debt"), fmp.get("total_debt"), info.get("totalDebt"))
    total_cash = prefer(fs.get("total_cash"), fmp.get("total_cash"), info.get("totalCash"))
    shares = prefer(fs.get("shares_outstanding"), fmp.get("shares_outstanding"), info.get("sharesOutstanding"))
    currency = fs.get("currency") or fmp.get("currency") or info.get("currency", "USD")

    # EV: prefer live computation (happens after FX below); fall back to period-end.
    ev = prefer(fs_ev, fmp.get("enterprise_value"), info.get("enterpriseValue"))
    if not ev and market_cap:
        ev = calc_tev(market_cap, total_debt, total_cash)

    # Margins: FactSet computes from FY GP/EBITDA over Sales; FMP ratios-ttm; yfinance info.
    gross_margin = prefer(fs.get("gross_margin"), fmp.get("gross_margin"), info.get("grossMargins"))
    ebitda_margin = prefer(fs.get("ebitda_margin"), fmp.get("ebitda_margin"), info.get("ebitdaMargins"))

    # LTM financials
    ltm_revenue = prefer(fs.get("ltm_revenue"), fmp.get("ltm_revenue"), info.get("totalRevenue"))
    ltm_gross_profit = prefer(fs.get("ltm_gross_profit"), fmp.get("ltm_gross_profit"), info.get("grossProfits"))
    ltm_ebitda = prefer(fs.get("ltm_ebitda"), fmp.get("ltm_ebitda"), info.get("ebitda"))

    # Estimates
    current_fy_rev_est = prefer(fs.get("current_fy_rev_est"), fmp.get("current_fy_rev_est"), estimates.get("current_fy_rev"))
    next_fy_rev_est = prefer(fs.get("next_fy_rev_est"), fmp.get("next_fy_rev_est"), estimates.get("next_fy_rev"))
    current_fy_rev_growth = prefer(fs.get("current_fy_rev_growth"), estimates.get("current_fy_growth"))
    next_fy_rev_growth = prefer(fs.get("next_fy_rev_growth"), estimates.get("next_fy_growth"))
    five_year_growth = prefer(fs.get("five_year_growth_rate"), growth.get("five_year"))

    # EBITDA estimates
    current_fy_ebitda_est = prefer(fs.get("current_fy_ebitda_est"), fmp.get("current_fy_ebitda_est"))
    next_fy_ebitda_est = prefer(fs.get("next_fy_ebitda_est"), fmp.get("next_fy_ebitda_est"))

    # Track which sources contributed
    fs_fields_used = sum(1 for k, v in fs.items() if v is not None and k not in {"data_source", "currency", "price_currency", "price_history"})
    fmp_fields_used = sum(1 for v in fmp.values() if v is not None)
    if fs_fields_used >= 3:
        data_source = "factset"
    elif fmp_fields_used >= 3:
        data_source = "fmp+yfinance"
    else:
        data_source = "yfinance"

    # FY end month
    fy_end = company_info.get("fy_end_month", 12)
    if fy_end == 0:
        last_fy_end = info.get("lastFiscalYearEnd")
        if last_fy_end:
            from datetime import datetime as dt
            fy_end = dt.fromtimestamp(last_fy_end).month
        else:
            fy_end = 12

    # --- FX CONVERSION ---
    # Detect if financials are in a non-USD currency and convert.
    # FactSet returns the actual reporting currency on each row — prefer it when
    # FactSet contributed financials (its currency is the most authoritative
    # signal because it comes from the financial statement, not yfinance metadata).
    from fetcher.ticker_utils import detect_financial_currency
    fs_currency = fs.get("currency")
    if fs_currency and fs_currency not in (None, "", "LOCAL") and fs_fields_used >= 3:
        financial_currency = fs_currency
    else:
        financial_currency = detect_financial_currency(info, company_info)
    trading_currency = fs.get("price_currency") or info.get("currency") or fmp.get("currency") or "USD"

    if financial_currency != "USD" or trading_currency != "USD":
        raw_financials = {
            "ltm_revenue": ltm_revenue,
            "ltm_gross_profit": ltm_gross_profit,
            "ltm_ebitda": ltm_ebitda,
            "current_fy_rev_est": current_fy_rev_est,
            "next_fy_rev_est": next_fy_rev_est,
            "current_fy_ebitda_est": current_fy_ebitda_est,
            "next_fy_ebitda_est": next_fy_ebitda_est,
            "total_debt": total_debt,
            "total_cash": total_cash,
            "market_cap": market_cap,
            "enterprise_value": ev,
            "current_price": current_price,
            "fifty_two_week_high": high_52wk,
        }
        converted = _convert_financials_to_usd(raw_financials, financial_currency, trading_currency)
        ltm_revenue = converted["ltm_revenue"]
        ltm_gross_profit = converted["ltm_gross_profit"]
        ltm_ebitda = converted["ltm_ebitda"]
        current_fy_rev_est = converted["current_fy_rev_est"]
        next_fy_rev_est = converted["next_fy_rev_est"]
        current_fy_ebitda_est = converted["current_fy_ebitda_est"]
        next_fy_ebitda_est = converted["next_fy_ebitda_est"]
        total_debt = converted["total_debt"]
        total_cash = converted["total_cash"]
        market_cap = converted["market_cap"]
        ev = converted["enterprise_value"]
        current_price = converted["current_price"]
        high_52wk = converted["fifty_two_week_high"]

        # Recalculate EV if market cap was converted
        if trading_currency != "USD" and market_cap:
            ev = calc_tev(market_cap, total_debt, total_cash)

    # --- LIVE MARKET CAP & EV (after FX — all values now in USD) ---
    # FactSet period-end FF_MKT_VAL / FF_ENTRPR_VAL may be stale or in the wrong
    # currency for ADRs.  Compute live values from current_price × shares whenever
    # both are available.  Debt/cash are already USD-converted above.
    if current_price and shares:
        live_mkt = current_price * shares
        if live_mkt > 0:
            market_cap = live_mkt
            ev = calc_tev(market_cap, total_debt, total_cash)

    # --- APPLY MANUAL OVERRIDES (after FX conversion — overrides are always in USD) ---
    if overrides:
        _ticker = company_info.get("ticker", "?")
        logger.info(f"  Applying {len(overrides)} manual override(s) for {_ticker}")
        ev = overrides.get("enterprise_value", ev)
        market_cap = overrides.get("market_cap", market_cap)
        ltm_revenue = overrides.get("ltm_revenue", ltm_revenue)
        ltm_gross_profit = overrides.get("ltm_gross_profit", ltm_gross_profit)
        ltm_ebitda = overrides.get("ltm_ebitda", ltm_ebitda)
        current_fy_rev_est = overrides.get("current_fy_rev_est", current_fy_rev_est)
        next_fy_rev_est = overrides.get("next_fy_rev_est", next_fy_rev_est)
        current_fy_ebitda_est = overrides.get("current_fy_ebitda_est", current_fy_ebitda_est)
        next_fy_ebitda_est = overrides.get("next_fy_ebitda_est", next_fy_ebitda_est)
        total_debt = overrides.get("total_debt", total_debt)
        total_cash = overrides.get("total_cash", total_cash)
        gross_margin = overrides.get("gross_margin", gross_margin)
        ebitda_margin = overrides.get("ebitda_margin", ebitda_margin)
        current_price = overrides.get("current_price", current_price)
        high_52wk = overrides.get("fifty_two_week_high", high_52wk)

    # NTM Revenue (calendarized)
    ntm_revenue = calc_ntm_revenue(current_fy_rev_est, next_fy_rev_est, fy_end)

    # NTM EBITDA (calendarized from consensus estimates, if available)
    ntm_ebitda = calc_ntm_ebitda(current_fy_ebitda_est, next_fy_ebitda_est, fy_end)

    # NTM Revenue Growth (blended FY growth rates — avoids LTM vs NTM window mismatch)
    ntm_rev_growth = calc_ntm_revenue_growth(current_fy_rev_growth, next_fy_rev_growth, fy_end)

    # % of 52-Week High
    pct_52wk = calc_pct_52wk_high(current_price, high_52wk)

    # NTM Multiples
    ntm_tev_rev = calc_ntm_tev_rev(ev, ntm_revenue)
    ntm_tev_gp = calc_ntm_tev_gp(ev, ntm_revenue, gross_margin)
    ntm_tev_ebitda = calc_ntm_tev_ebitda(ev, ntm_ebitda, ntm_revenue, ebitda_margin)

    # LTM Multiples
    ltm_tev_rev = calc_ltm_tev_rev(ev, ltm_revenue)
    ltm_tev_gp = calc_ltm_tev_gp(ev, ltm_gross_profit)
    ltm_tev_ebitda = calc_ltm_tev_ebitda(ev, ltm_ebitda)

    # Growth-Adjusted Multiples
    growth_adj_rev = calc_growth_adj_multiple(ntm_tev_rev, ntm_rev_growth)
    growth_adj_gp = calc_growth_adj_multiple(ntm_tev_gp, ntm_rev_growth)

    # N3Y CAGR
    n3y_cagr = calc_n3y_cagr(five_year_growth, current_fy_rev_est, next_fy_rev_est)

    # Price Changes — prefer FactSet price history, fall back to yfinance
    fs_price_hist = fs.get("price_history")
    change_2w, change_2m = calc_price_changes(fs_price_hist or price_hist)

    result = {
        "name": company_info["name"],
        "segment": company_info["segment"],
        "sub_segment": company_info.get("sub_segment"),
        "current_price": current_price,
        "market_cap": market_cap,
        "enterprise_value": ev,
        "total_debt": total_debt,
        "total_cash": total_cash,
        "shares_outstanding": shares,
        "fifty_two_week_high": high_52wk,
        "currency": "USD",  # Always USD after conversion
        "fy_end_month": fy_end,
        "ltm_revenue": ltm_revenue,
        "ltm_gross_profit": ltm_gross_profit,
        "ltm_ebitda": ltm_ebitda,
        "gross_margin": gross_margin,
        "ebitda_margin": ebitda_margin,
        "current_fy_rev_est": current_fy_rev_est,
        "next_fy_rev_est": next_fy_rev_est,
        "current_fy_ebitda_est": current_fy_ebitda_est,
        "next_fy_ebitda_est": next_fy_ebitda_est,
        "current_fy_rev_growth": current_fy_rev_growth,
        "next_fy_rev_growth": next_fy_rev_growth,
        "five_year_growth_rate": five_year_growth,
        "ntm_revenue": ntm_revenue,
        "ntm_ebitda": ntm_ebitda,
        "ntm_revenue_growth": ntm_rev_growth,
        "pct_52wk_high": pct_52wk,
        "ntm_tev_rev": ntm_tev_rev,
        "ntm_tev_gp": ntm_tev_gp,
        "ntm_tev_ebitda": ntm_tev_ebitda,
        "ltm_tev_rev": ltm_tev_rev,
        "ltm_tev_gp": ltm_tev_gp,
        "ltm_tev_ebitda": ltm_tev_ebitda,
        "growth_adj_rev": growth_adj_rev,
        "growth_adj_gp": growth_adj_gp,
        "n3y_revenue_cagr": n3y_cagr,
        "price_change_2w": change_2w,
        "price_change_2m": change_2m,
        "data_source": data_source,
        "fetch_timestamp": date.today().isoformat(),
    }

    # --- VALIDATION ---
    ticker = company_info.get("ticker", "?")
    result = _validate_metrics(result, ticker)

    return result
