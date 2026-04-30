"""
Historical multiples backfill using FMP daily market cap data.

Reconstructs daily NTM TEV/Revenue for the past 12 months:
  Daily TEV = Daily Market Cap + Total Debt - Total Cash
  Daily NTM TEV/Rev = Daily TEV / NTM Revenue

Debt/cash are from the most recent balance sheet (they change slowly).
NTM revenue uses today's analyst consensus (reasonable for ~12 months).
"""

import sys
import time
import logging
import requests
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import DB_PATH, FMP_API_KEY
from config.company_registry import COMPANY_REGISTRY
from fetcher.db_manager import DBManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

BASE_URL = "https://financialmodelingprep.com"
REQUEST_TIMEOUT = 15


def _fmp_get(endpoint, params):
    """Make an FMP API request."""
    params["apikey"] = FMP_API_KEY
    url = f"{BASE_URL}/stable/{endpoint}"
    try:
        r = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200 and r.text.strip():
            return r.json()
        return None
    except Exception:
        return None


def get_historical_market_caps(ticker, from_date):
    """Get daily market caps from FMP."""
    data = _fmp_get("historical-market-capitalization", {
        "symbol": ticker,
        "from": from_date,
    })
    if isinstance(data, list):
        return data
    return []


def get_balance_sheet_latest(ticker):
    """Get latest quarterly balance sheet for debt/cash."""
    data = _fmp_get("balance-sheet-statement", {
        "symbol": ticker,
        "period": "quarter",
        "limit": 1,
    })
    if isinstance(data, list) and data:
        bs = data[0]
        debt = bs.get("totalDebt") or 0
        cash = bs.get("cashAndCashEquivalents") or bs.get("cashAndShortTermInvestments") or 0
        return {"total_debt": debt, "total_cash": cash}
    return None


def backfill_company(ticker, segment, db, from_date, ntm_revenue=None):
    """
    Backfill daily multiples for a single company.

    Returns number of days inserted.
    """
    # Get daily market caps
    mcaps = get_historical_market_caps(ticker, from_date)
    if not mcaps:
        return 0

    # Get debt/cash from latest balance sheet
    bs = get_balance_sheet_latest(ticker)
    ebitda_margin = None
    if bs is None:
        # Fall back to snapshot data in DB
        snapshots = db.get_latest_snapshots_for_ticker(ticker)
        if snapshots:
            s = snapshots[0]
            bs = {
                "total_debt": s.get("total_debt") or 0,
                "total_cash": s.get("total_cash") or 0,
            }
            ebitda_margin = s.get("ebitda_margin")
        else:
            bs = {"total_debt": 0, "total_cash": 0}

    debt = bs["total_debt"]
    cash = bs["total_cash"]

    # Get NTM revenue and EBITDA margin from current snapshot if not provided
    if ntm_revenue is None or ebitda_margin is None:
        snapshots = db.get_latest_snapshots_for_ticker(ticker)
        if snapshots:
            if ntm_revenue is None and snapshots[0].get("ntm_revenue"):
                ntm_revenue = snapshots[0]["ntm_revenue"]
            if ebitda_margin is None:
                ebitda_margin = snapshots[0].get("ebitda_margin")
        if ntm_revenue is None:
            return 0

    # Calculate daily TEV and NTM TEV/Rev
    count = 0
    for day_data in mcaps:
        mcap = day_data.get("marketCap")
        dt = day_data.get("date")
        if not mcap or not dt:
            continue

        tev = mcap + debt - cash
        if tev <= 0 or ntm_revenue <= 0:
            continue

        ntm_tev_rev = tev / ntm_revenue

        # Compute EBITDA multiple if margin available
        ntm_tev_ebitda = None
        if ebitda_margin and ebitda_margin > 0:
            ntm_ebitda = ntm_revenue * ebitda_margin
            if ntm_ebitda > 0:
                ntm_tev_ebitda = tev / ntm_ebitda
                # Filter unreasonable EBITDA multiples
                if ntm_tev_ebitda > 200 or ntm_tev_ebitda < 0:
                    ntm_tev_ebitda = None

        # Only store reasonable values (filter outliers)
        if 0.1 < ntm_tev_rev < 100:
            db.upsert_daily_multiple(
                ticker=ticker,
                dt=dt,
                segment=segment,
                ntm_tev_rev=ntm_tev_rev,
                ev=tev,
                ntm_rev=ntm_revenue,
                ntm_tev_ebitda=ntm_tev_ebitda,
            )
            count += 1

    return count


def run_backfill(months_back=12, tickers=None):
    """
    Backfill historical daily multiples for all companies.
    """
    db = DBManager(DB_PATH)
    db.init_schema()

    from_date = (date.today() - timedelta(days=months_back * 31)).isoformat()

    registry = COMPANY_REGISTRY
    if tickers:
        registry = [c for c in registry if c["ticker"] in tickers]

    total = len(registry)
    total_days = 0
    errors = []

    logger.info(f"Starting historical backfill from {from_date} for {total} companies...")

    for i, company in enumerate(registry, 1):
        ticker = company["ticker"]
        segment = company["segment"]

        try:
            days = backfill_company(ticker, segment, db, from_date)
            total_days += days
            if days > 0:
                logger.info(f"[{i}/{total}] {ticker}: {days} days backfilled")
            else:
                logger.warning(f"[{i}/{total}] {ticker}: no data available")
        except Exception as e:
            logger.error(f"[{i}/{total}] {ticker}: FAILED - {e}")
            errors.append({"ticker": ticker, "error": str(e)})

        # Rate limiting - FMP allows 300/min on Starter, be conservative
        if i < total:
            time.sleep(0.25)

    logger.info(f"\nBackfill complete: {total_days} total day-records across {total} companies")
    if errors:
        logger.info(f"Errors: {len(errors)}")
        for e in errors[:10]:
            logger.info(f"  - {e['ticker']}: {e['error']}")

    return total_days, errors


if __name__ == "__main__":
    subset = sys.argv[1:] if len(sys.argv) > 1 else None
    run_backfill(months_back=12, tickers=subset)
