"""
Process FactSet MCP data and write to healthcare_multiples.db.

Reads raw FactSet JSON from data/factset_raw/, computes all derived
metrics using the existing calculators, and writes to both company_snapshots
and daily_multiples tables via db_manager.

Usage:
    python fetcher/factset_process.py --snapshot-date 2026-03-23
    python fetcher/factset_process.py  # defaults to today
"""

import argparse
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.company_registry import COMPANY_REGISTRY
from config.factset_registry import factset_to_display
from fetcher.calculators import (
    calc_growth_adj_multiple,
    calc_ltm_tev_ebitda,
    calc_ltm_tev_gp,
    calc_ltm_tev_rev,
    calc_n3y_cagr,
    calc_ntm_ebitda,
    calc_ntm_revenue,
    calc_ntm_revenue_growth,
    calc_ntm_tev_ebitda,
    calc_ntm_tev_gp,
    calc_ntm_tev_rev,
    calc_pct_52wk_high,
    calc_tev,
    _validate_metrics,
)
from fetcher.db_manager import DBManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

RAW_DIR = Path("data/factset_raw")
DB_PATH = Path("data/healthcare_multiples.db")

# Company registry keyed by display ticker
_REGISTRY = {c["ticker"]: c for c in COMPANY_REGISTRY}


# ---------------------------------------------------------------------------
# JSON loaders
# ---------------------------------------------------------------------------

def _load_json(filename: str) -> dict:
    """Load a JSON file from RAW_DIR, return empty dict if missing."""
    path = RAW_DIR / filename
    if not path.exists():
        logger.warning(f"Missing {path}")
        return {}
    with open(path) as f:
        return json.load(f)


def _load_estimates(filename: str) -> dict:
    """Load estimates JSON. Returns {fs_id: {0: mean, 1: mean, 2: mean, ...}} keyed by relativePeriod."""
    raw = _load_json(filename)
    if not raw:
        return {}
    records = raw.get("data", [])
    result = {}
    for r in records:
        fs_id = r.get("requestId", "")
        rp = r.get("relativePeriod")
        if rp is None:
            continue
        if fs_id not in result:
            result[fs_id] = {}
        result[fs_id][rp] = r.get("mean")
    return result


def _load_fundamentals(filename: str) -> dict:
    """Load fundamentals JSON. Returns {fs_id: {metric_code: value}}."""
    raw = _load_json(filename)
    if not raw:
        return {}
    records = raw.get("data", [])
    # Take the most recent period per company; group by requestId
    per_company = {}
    for r in records:
        fs_id = r.get("requestId", "")
        metric = r.get("metric", "")
        val = r.get("value")
        dt = r.get("date", "")
        if fs_id not in per_company:
            per_company[fs_id] = {"date": "", "metrics": {}}
        if dt >= per_company[fs_id]["date"]:
            if dt > per_company[fs_id]["date"]:
                per_company[fs_id] = {"date": dt, "metrics": {}}
            per_company[fs_id]["metrics"][metric] = val
    return {fs_id: d["metrics"] for fs_id, d in per_company.items()}


def _load_prices(filename: str) -> dict:
    """Load prices JSON. Returns {fs_id: {date, price, priceHigh, ...}}."""
    raw = _load_json(filename)
    if not raw:
        return {}
    records = raw.get("data", [])
    result = {}
    for r in records:
        fs_id = r.get("requestId", "")
        result[fs_id] = r
    return result


def _load_market_value(filename: str) -> dict:
    """Load market_value JSON. Returns {fs_id: marketValue}."""
    raw = _load_json(filename)
    if not raw:
        return {}
    records = raw.get("data", [])
    result = {}
    for r in records:
        fs_id = r.get("requestId", "")
        val = r.get("marketValue")
        if val is not None:
            result[fs_id] = val
    return result


def _load_shares(filename: str) -> dict:
    """Load shares_outstanding JSON. Returns {fs_id: sharesOutstanding}.

    Legacy format from GlobalPrices endpoint — basic shares, Class A only.
    """
    raw = _load_json(filename)
    if not raw:
        return {}
    records = raw.get("data", [])
    result = {}
    for r in records:
        fs_id = r.get("requestId", "")
        val = r.get("sharesOutstanding")
        if val is not None:
            result[fs_id] = val
    return result


def _load_diluted_shares(filename: str) -> dict:
    """Load diluted shares from FF_COM_SHS_OUT_EPS_DIL (preferred) with
    FF_COM_SHS_OUT fallback. Returns {fs_id: shares_in_millions}.

    This is the ground-truth share count used by FactSet's portal and
    matches the full-diluted share count including all share classes
    plus option/RSU dilution. Much more accurate than the legacy
    shares_outstanding endpoint which returns basic Class A only.
    """
    raw = _load_json(filename)
    if not raw:
        return {}
    records = raw.get("data", [])
    # Group by company
    by_id = {}
    for r in records:
        fs_id = r.get("requestId", "")
        metric = r.get("metric", "")
        val = r.get("value")
        if fs_id not in by_id:
            by_id[fs_id] = {}
        by_id[fs_id][metric] = val
    # Pick diluted if available, else basic
    result = {}
    for fs_id, metrics in by_id.items():
        diluted = metrics.get("FF_COM_SHS_OUT_EPS_DIL")
        basic = metrics.get("FF_COM_SHS_OUT")
        chosen = diluted if diluted is not None else basic
        if chosen is not None:
            result[fs_id] = chosen
    return result


def _load_price_history(filename: str) -> dict:
    """Load price history JSON. Returns {fs_id: [{date, price, priceHigh}, ...]}."""
    raw = _load_json(filename)
    if not raw:
        return {}
    records = raw.get("data", [])
    result = {}
    for r in records:
        fs_id = r.get("requestId", "")
        if fs_id not in result:
            result[fs_id] = []
        result[fs_id].append(r)
    # Sort by date
    for fs_id in result:
        result[fs_id].sort(key=lambda x: x.get("date", ""))
    return result


def _compute_price_metrics(history: list, current_price: float | None):
    """Compute 52-week high, 2-week change, 2-month change from daily history."""
    fifty_two_week_high = None
    change_2w = None
    change_2m = None

    if not history:
        return fifty_two_week_high, change_2w, change_2m

    # 52-week high = max of priceHigh across all records
    highs = [r.get("priceHigh") for r in history if r.get("priceHigh") is not None]
    if highs:
        fifty_two_week_high = max(highs)

    # Price changes from price series (history is weekly frequency)
    prices = [r.get("price") for r in history if r.get("price") is not None]
    if prices and current_price and current_price > 0:
        # 2-week ~ 2 weekly bars back (prices[-3] = 2 weeks prior)
        if len(prices) >= 3:
            p2w = prices[-3]
            if p2w and p2w > 0:
                change_2w = (current_price / p2w) - 1.0
        # 2-month ~ 8 weekly bars back (prices[-9] = ~8 weeks prior)
        if len(prices) >= 9:
            p2m = prices[-9]
            if p2m and p2m > 0:
                change_2m = (current_price / p2m) - 1.0

    return fifty_two_week_high, change_2w, change_2m


# ---------------------------------------------------------------------------
# Main processing
# ---------------------------------------------------------------------------

def process(snapshot_date: str, db_path: str = str(DB_PATH)):
    """Run the full FactSet data processing pipeline."""
    ref_date = datetime.strptime(snapshot_date, "%Y-%m-%d").date()

    # Load all FactSet data
    logger.info("Loading FactSet raw data...")
    sales = _load_estimates("estimates_sales.json")
    ebitda = _load_estimates("estimates_ebitda.json")
    prices = _load_prices("prices_current.json")
    mkt_val = _load_market_value("market_value.json")
    shares = _load_shares("shares_outstanding.json")
    diluted_shares = _load_diluted_shares("fundamentals_shares.json")
    history = _load_price_history("price_history.json")
    fund_ltm = _load_fundamentals("fundamentals_ltm.json")
    fund_bs = _load_fundamentals("fundamentals_bs.json")
    sales_fy3 = _load_estimates("estimates_sales_fy3.json")

    logger.info(
        f"Loaded: {len(sales)} sales, {len(ebitda)} ebitda, "
        f"{len(prices)} prices, {len(mkt_val)} mkt_val, "
        f"{len(diluted_shares)} diluted_shares, {len(shares)} basic_shares, "
        f"{len(history)} history, {len(fund_ltm)} ltm, {len(fund_bs)} bs"
    )

    db = DBManager(db_path)

    # Load existing DB data as fallback for fields not yet fetched from FactSet
    existing_db = {}
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for row in conn.execute(
            "SELECT * FROM company_snapshots WHERE snapshot_date = ("
            "SELECT MAX(snapshot_date) FROM company_snapshots)"
        ).fetchall():
            existing_db[row["ticker"]] = dict(row)
        conn.close()
        logger.info(f"Loaded {len(existing_db)} existing DB rows as fallback")
    except Exception as e:
        logger.warning(f"Could not load existing DB fallback: {e}")

    upserted = 0
    skipped = 0
    errors = []

    for fs_id, sales_periods in sales.items():
        ticker = factset_to_display(fs_id)
        reg = _REGISTRY.get(ticker)
        if not reg:
            skipped += 1
            continue

        try:
            # Prefer diluted shares; fall back to basic shares endpoint
            shares_in = diluted_shares.get(fs_id) or shares.get(fs_id)
            metrics = _process_one_company(
                fs_id, ticker, reg, ref_date,
                sales_periods, ebitda.get(fs_id, {}),
                prices.get(fs_id, {}), mkt_val.get(fs_id),
                shares_in, history.get(fs_id, []),
                fund_ltm.get(fs_id, {}), fund_bs.get(fs_id, {}),
                sales_fy3.get(fs_id, {}),
                existing_db.get(ticker, {}),
            )

            # Validate
            metrics = _validate_metrics(metrics, ticker)

            # Write snapshot
            db.upsert_snapshot(ticker, snapshot_date, metrics)

            # Write daily multiple
            db.upsert_daily_multiple(
                ticker, snapshot_date, reg["segment"],
                ntm_tev_rev=metrics.get("ntm_tev_rev"),
                ev=metrics.get("enterprise_value"),
                ntm_rev=metrics.get("ntm_revenue"),
                ntm_tev_ebitda=metrics.get("ntm_tev_ebitda"),
                ntm_ebitda=metrics.get("ntm_ebitda"),
                ntm_revenue_growth=metrics.get("ntm_revenue_growth"),
                gross_margin=metrics.get("gross_margin"),
                ebitda_margin=metrics.get("ebitda_margin"),
            )
            upserted += 1

        except Exception as e:
            errors.append(f"{ticker}: {e}")
            logger.error(f"Error processing {ticker}: {e}")

    # Log fetch to fetch_log table (so the website shows the correct date)
    db.log_fetch(
        total=len(sales),
        success=upserted,
        errors_count=len(errors),
        errors_list=[str(e) for e in errors[:20]],
    )

    logger.info(f"Done: {upserted} upserted, {skipped} skipped, {len(errors)} errors")
    if errors:
        for err in errors[:10]:
            logger.error(f"  {err}")

    return upserted, skipped, errors


def _process_one_company(
    fs_id, ticker, reg, ref_date,
    sales_periods, ebitda_periods,
    price_data, market_value, shares_out, price_hist,
    fund_ltm, fund_bs, sales_fy3_periods,
    existing=None,
):
    """Compute all metrics for one company. Returns metrics dict."""
    if existing is None:
        existing = {}
    fy_end = reg["fy_end_month"]
    segment = reg["segment"]
    sub_segment = reg.get("sub_segment")
    name = reg["name"]

    # --- Consensus estimates (in millions from FactSet, convert to raw) ---
    fy0_sales = _m_to_raw(sales_periods.get(0))
    fy1_sales = _m_to_raw(sales_periods.get(1))
    fy2_sales = _m_to_raw(sales_periods.get(2))
    fy1_ebitda = _m_to_raw(ebitda_periods.get(1))
    fy2_ebitda = _m_to_raw(ebitda_periods.get(2))
    fy3_sales = _m_to_raw(sales_fy3_periods.get(3))

    # --- Growth rates (computed from estimates) ---
    current_fy_rev_growth = None
    if fy0_sales and fy1_sales and fy0_sales > 0:
        current_fy_rev_growth = (fy1_sales / fy0_sales) - 1.0
    next_fy_rev_growth = None
    if fy1_sales and fy2_sales and fy1_sales > 0:
        next_fy_rev_growth = (fy2_sales / fy1_sales) - 1.0

    # --- Price ---
    current_price = price_data.get("price")

    # --- Market cap (from market_value endpoint, in USD millions) ---
    market_cap = None
    if market_value is not None:
        market_cap = market_value * 1e6

    # --- Shares outstanding (FactSet returns in millions) ---
    shares_outstanding = None
    if shares_out is not None:
        shares_outstanding = shares_out * 1e6
    elif existing.get("shares_outstanding"):
        shares_outstanding = existing["shares_outstanding"]

    # --- Fallback: compute market cap from price * shares if needed ---
    if market_cap is None and current_price and shares_outstanding:
        market_cap = current_price * shares_outstanding

    # --- 52-week high and price changes (fallback to existing DB) ---
    fifty_two_week_high, change_2w, change_2m = _compute_price_metrics(
        price_hist, current_price
    )
    if fifty_two_week_high is None and existing.get("fifty_two_week_high"):
        fifty_two_week_high = existing["fifty_two_week_high"]
    if change_2w is None and existing.get("price_change_2w") is not None:
        change_2w = existing["price_change_2w"]
    if change_2m is None and existing.get("price_change_2m") is not None:
        change_2m = existing["price_change_2m"]

    # --- LTM fundamentals (in millions, convert to raw) ---
    # Fallback: use FY0 actual SALES if FactSet fundamentals are null
    # (common for IFRS/international companies where FF_SALES is unavailable)
    ltm_revenue = _m_to_raw(fund_ltm.get("FF_SALES")) or fy0_sales
    ltm_gross_profit = _m_to_raw(fund_ltm.get("FF_GROSS_INC"))
    ltm_ebitda = _m_to_raw(fund_ltm.get("FF_EBITDA_OPER"))

    # --- Balance sheet (in millions, convert to raw) ---
    total_debt = _m_to_raw(fund_bs.get("FF_DEBT"))
    total_cash = _m_to_raw(fund_bs.get("FF_CASH_GENERIC"))

    # --- Enterprise value ---
    enterprise_value = calc_tev(market_cap, total_debt, total_cash)

    # --- Margins ---
    gross_margin = None
    if ltm_gross_profit and ltm_revenue and ltm_revenue > 0:
        gross_margin = ltm_gross_profit / ltm_revenue
    ebitda_margin = None
    if ltm_ebitda is not None and ltm_revenue and ltm_revenue > 0:
        ebitda_margin = ltm_ebitda / ltm_revenue

    # --- NTM calendarized values (reuse existing calculator functions) ---
    ntm_revenue = calc_ntm_revenue(fy1_sales, fy2_sales, fy_end)
    ntm_ebitda = calc_ntm_ebitda(fy1_ebitda, fy2_ebitda, fy_end)
    ntm_revenue_growth = calc_ntm_revenue_growth(
        current_fy_rev_growth, next_fy_rev_growth, fy_end
    )

    # --- Pct 52-week high ---
    pct_52wk_high = calc_pct_52wk_high(current_price, fifty_two_week_high)

    # --- Multiples ---
    ntm_tev_rev = calc_ntm_tev_rev(enterprise_value, ntm_revenue)
    ntm_tev_gp = calc_ntm_tev_gp(enterprise_value, ntm_revenue, gross_margin)
    ntm_tev_ebitda = calc_ntm_tev_ebitda(
        enterprise_value, ntm_ebitda, ntm_revenue, ebitda_margin
    )
    ltm_tev_rev = calc_ltm_tev_rev(enterprise_value, ltm_revenue)
    ltm_tev_gp = calc_ltm_tev_gp(enterprise_value, ltm_gross_profit)
    ltm_tev_ebitda = calc_ltm_tev_ebitda(enterprise_value, ltm_ebitda)

    # --- Growth-adjusted multiples ---
    growth_adj_rev = calc_growth_adj_multiple(ntm_tev_rev, ntm_revenue_growth)
    growth_adj_gp = calc_growth_adj_multiple(ntm_tev_gp, ntm_revenue_growth)

    # --- N3Y CAGR ---
    n3y_cagr = None
    if fy3_sales and fy1_sales and fy1_sales > 0:
        n3y_cagr = (fy3_sales / fy1_sales) ** (1.0 / 2.0) - 1.0
    elif current_fy_rev_growth is not None:
        n3y_cagr = current_fy_rev_growth

    return {
        "name": name,
        "segment": segment,
        "sub_segment": sub_segment,
        "current_price": current_price,
        "market_cap": market_cap,
        "enterprise_value": enterprise_value,
        "total_debt": total_debt,
        "total_cash": total_cash,
        "shares_outstanding": shares_outstanding,
        "fifty_two_week_high": fifty_two_week_high,
        "currency": "USD",
        "fy_end_month": fy_end,
        "ltm_revenue": ltm_revenue,
        "ltm_gross_profit": ltm_gross_profit,
        "ltm_ebitda": ltm_ebitda,
        "gross_margin": gross_margin,
        "ebitda_margin": ebitda_margin,
        "current_fy_rev_est": fy1_sales,
        "next_fy_rev_est": fy2_sales,
        "current_fy_ebitda_est": fy1_ebitda,
        "next_fy_ebitda_est": fy2_ebitda,
        "current_fy_rev_growth": current_fy_rev_growth,
        "next_fy_rev_growth": next_fy_rev_growth,
        "five_year_growth_rate": None,
        "ntm_revenue": ntm_revenue,
        "ntm_ebitda": ntm_ebitda,
        "ntm_revenue_growth": ntm_revenue_growth,
        "pct_52wk_high": pct_52wk_high,
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
        "data_source": "factset",
        "fetch_timestamp": str(ref_date),
    }


def _m_to_raw(val):
    """Convert millions to raw dollars. None-safe."""
    if val is None:
        return None
    return val * 1e6


def main():
    parser = argparse.ArgumentParser(description="Process FactSet MCP data")
    parser.add_argument(
        "--snapshot-date",
        default=date.today().isoformat(),
        help="Snapshot date (YYYY-MM-DD), defaults to today",
    )
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    upserted, skipped, errors = process(args.snapshot_date, args.db)
    print(f"\nResult: {upserted} upserted, {skipped} skipped, {len(errors)} errors")


if __name__ == "__main__":
    main()
