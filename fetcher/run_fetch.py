"""
Main fetch orchestrator. Run via: python -m fetcher.run_fetch
Fetches data for all companies using FMP (where available) + yfinance hybrid approach.
"""

import sys
import time
import logging
from datetime import date, datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    DB_PATH,
    FETCH_DELAY_SECONDS,
    FMP_API_KEY,
    USE_FMP,
    EXCEL_OVERRIDE_PATH,
    FACTSET_USERNAME_SERIAL,
    FACTSET_API_KEY,
    USE_FACTSET,
)
from config.company_registry import COMPANY_REGISTRY
from config.factset_registry import display_to_factset
from fetcher.db_manager import DBManager
from fetcher.yf_fetcher import fetch_company_data
from fetcher.calculators import compute_all_metrics
from fetcher.excel_override import load_multiples_history

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def run_fetch(tickers=None):
    """
    Fetch data for all companies (or a subset) and store in SQLite.
    Uses FMP for profile data (market cap, price) + premium endpoints where available,
    then yfinance for estimates, growth, and price history.

    Args:
        tickers: Optional list of display tickers to fetch. If None, fetches all.
    """
    db = DBManager(DB_PATH)
    db.init_schema()

    # ── Ingest Excel history first ────────────────────────────────────────────
    # Reads weekly multiple history from factset_overrides.xlsx and bulk-inserts
    # into daily_multiples using INSERT OR IGNORE (live-fetched rows are kept).
    try:
        history_rows = load_multiples_history(EXCEL_OVERRIDE_PATH)
        if history_rows:
            db.bulk_upsert_daily_multiples(history_rows)
            logger.info(f"Ingested {len(history_rows)} history rows from Excel")
        else:
            logger.info("No Excel history rows found (file missing or no history sheets)")
    except Exception as exc:
        logger.warning(f"Excel history ingest failed (non-fatal): {exc}")

    # Conditionally import FMP fetcher
    fmp_available = USE_FMP
    if fmp_available:
        from fetcher.fmp_fetcher import fetch_company_data_fmp, parse_fmp_data
        logger.info(f"FMP API key detected — FMP enabled")
    else:
        logger.info("No FMP API key — FMP disabled")

    # Conditionally import FactSet fetcher
    factset_available = USE_FACTSET
    if factset_available:
        from fetcher.factset_rest import fetch_company_data_factset, parse_factset_data
        logger.info("FactSet credentials detected — using FactSet > FMP > yfinance hybrid")
    else:
        logger.info("No FactSet credentials — falling back to FMP/yfinance")

    registry = COMPANY_REGISTRY
    if tickers:
        registry = [c for c in registry if c["ticker"] in tickers]

    total = len(registry)
    success_count = 0
    errors = []
    today = date.today()
    fmp_hit_count = 0
    factset_hit_count = 0

    logger.info(f"Starting fetch for {total} companies...")
    start_time = datetime.now()

    for i, company in enumerate(registry, 1):
        ticker = company["ticker"]
        yahoo_ticker = company["yahoo_ticker"]

        try:
            logger.info(f"[{i}/{total}] Fetching {ticker} ({yahoo_ticker})...")

            # Step 1: FactSet data (primary source — fundamentals + estimates + prices)
            factset_metrics = None
            factset_complete = False
            if factset_available:
                try:
                    fs_id = company.get("factset_id") or display_to_factset(ticker)
                    fs_raw = fetch_company_data_factset(
                        ticker,
                        factset_id=fs_id,
                        username_serial=FACTSET_USERNAME_SERIAL,
                        api_key=FACTSET_API_KEY,
                    )
                    factset_metrics = parse_factset_data(fs_raw, company)
                    fs_fields = sum(
                        1 for k, v in factset_metrics.items()
                        if v is not None and k not in {"data_source", "currency", "price_currency", "price_history"}
                    )
                    if fs_fields > 0:
                        factset_hit_count += 1
                        logger.info(f"  FactSet: {fs_fields} fields populated ({factset_metrics.get('currency')})")
                    # Consider FactSet "complete" if it provided price + shares + revenue
                    # (live market cap / EV are computed in calculators from price × shares)
                    factset_complete = all(factset_metrics.get(k) for k in ("current_price", "shares_outstanding", "ltm_revenue"))
                except Exception as e:
                    logger.warning(f"  FactSet failed for {ticker}: {e}")
                    factset_metrics = None

            # Step 2: FMP data (fallback — skip if FactSet provided everything)
            fmp_metrics = None
            if fmp_available and not factset_complete:
                try:
                    fmp_ticker = company.get("fmp_ticker") or company.get("yahoo_ticker", ticker)
                    fmp_data = fetch_company_data_fmp(fmp_ticker, FMP_API_KEY)
                    fmp_metrics = parse_fmp_data(fmp_data, company)
                    fmp_fields = sum(1 for v in fmp_metrics.values() if v is not None)
                    if fmp_fields > 0:
                        fmp_hit_count += 1
                        logger.info(f"  FMP: {fmp_fields} fields populated")
                except Exception as e:
                    logger.warning(f"  FMP failed for {ticker}: {e}")
                    fmp_metrics = None

            # Step 3: yfinance data (fallback — skip if FactSet provided prices)
            if factset_complete:
                # FactSet has everything; provide empty raw_data shell
                raw_data = {"info": {}, "estimates": {}, "growth": {}, "price_history": None}
                logger.info("  Skipping yfinance (FactSet complete)")
            else:
                raw_data = fetch_company_data(yahoo_ticker)

            # Step 4: Compute all metrics (FactSet > FMP > yfinance)
            metrics = compute_all_metrics(
                raw_data,
                company,
                fmp_metrics=fmp_metrics,
                factset_metrics=factset_metrics,
            )

            # Store snapshot
            db.upsert_snapshot(ticker, today, metrics)

            # Store daily multiple for time-series
            db.upsert_daily_multiple(
                ticker=ticker,
                dt=today,
                segment=company["segment"],
                ntm_tev_rev=metrics.get("ntm_tev_rev"),
                ev=metrics.get("enterprise_value"),
                ntm_rev=metrics.get("ntm_revenue"),
                ntm_tev_ebitda=metrics.get("ntm_tev_ebitda"),
                ntm_ebitda=metrics.get("ntm_ebitda"),
                ntm_revenue_growth=metrics.get("ntm_revenue_growth"),
                gross_margin=metrics.get("gross_margin"),
                ebitda_margin=metrics.get("ebitda_margin"),
            )

            success_count += 1

            # Log key metrics
            ev_b = (metrics.get("enterprise_value") or 0) / 1e9
            ntm_rev = metrics.get("ntm_tev_rev")
            src = metrics.get("data_source", "yfinance")
            logger.info(
                f"  -> TEV: ${ev_b:.1f}B | NTM TEV/Rev: {ntm_rev:.1f}x | src: {src}"
                if ntm_rev
                else f"  -> TEV: ${ev_b:.1f}B | NTM TEV/Rev: N/A | src: {src}"
            )

        except Exception as e:
            logger.error(f"  -> FAILED: {e}")
            errors.append({"ticker": ticker, "error": str(e)})

        # Rate limiting
        if i < total:
            time.sleep(FETCH_DELAY_SECONDS)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Log the fetch
    db.log_fetch(total, success_count, len(errors), errors)

    logger.info(f"\nFetch complete in {duration:.0f}s")
    logger.info(f"  Success: {success_count}/{total}")
    logger.info(f"  Errors: {len(errors)}/{total}")
    if factset_available:
        logger.info(f"  FactSet data used for: {factset_hit_count}/{total} companies")
    if fmp_available:
        logger.info(f"  FMP data used for: {fmp_hit_count}/{total} companies")
    if errors:
        for e in errors[:10]:
            logger.info(f"    - {e['ticker']}: {e['error']}")

    return success_count, errors


if __name__ == "__main__":
    # Allow fetching a subset via command line args
    subset = sys.argv[1:] if len(sys.argv) > 1 else None
    run_fetch(subset)
