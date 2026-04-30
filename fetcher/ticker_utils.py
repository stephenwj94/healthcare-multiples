"""
International ticker resolution and FX conversion utilities.
"""

import yfinance as yf
import logging

logger = logging.getLogger(__name__)

# Currencies that need conversion to USD
# London Stock Exchange prices are in GBP pence (divide by 100 for GBP)
FX_PAIRS = {}  # Cached exchange rates


def get_fx_rate(from_currency, to_currency="USD"):
    """Get exchange rate, cached for the session."""
    if from_currency == to_currency:
        return 1.0

    pair_key = f"{from_currency}{to_currency}"
    if pair_key in FX_PAIRS:
        return FX_PAIRS[pair_key]

    try:
        fx_ticker = yf.Ticker(f"{from_currency}{to_currency}=X")
        rate = fx_ticker.info.get("regularMarketPrice") or fx_ticker.info.get("previousClose")
        if rate and rate > 0:
            FX_PAIRS[pair_key] = rate
            logger.info(f"  FX rate {pair_key}: {rate:.4f}")
            return rate
    except Exception as e:
        logger.warning(f"FX rate fetch failed for {pair_key}: {e}")

    # Fallback rates (approximate, as of early 2026)
    fallbacks = {
        "GBPUSD": 1.27,
        "GBXUSD": 0.0127,  # GBP pence
        "GBpUSD": 0.0127,  # GBP pence (yfinance format)
        "AUDUSD": 0.65,
        "CADUSD": 0.74,
        "EURUSD": 1.08,
        "JPYUSD": 0.0067,
        "CHFUSD": 1.13,
        "SEKUSD": 0.095,
        "NOKUSD": 0.094,
        "DKKUSD": 0.145,
        "ILSUSD": 0.28,
        "KRWUSD": 0.00074,
        "NZDUSD": 0.58,
    }
    rate = fallbacks.get(pair_key, 1.0)
    FX_PAIRS[pair_key] = rate
    if rate != 1.0:
        logger.info(f"  FX rate {pair_key}: {rate:.4f} (fallback)")
    return rate


def convert_to_usd(value, currency):
    """Convert a value from its native currency to USD."""
    if value is None:
        return None
    if currency == "USD":
        return value

    # London Stock Exchange: prices in GBp (pence), financials in GBP
    if currency in ("GBp", "GBX"):
        # Price is in pence; convert to GBP first then to USD
        return value / 100.0 * get_fx_rate("GBP", "USD")

    return value * get_fx_rate(currency, "USD")


def detect_financial_currency(yf_info, company_info):
    """
    Detect the currency used for financial statements.
    yfinance exposes 'financialCurrency' separately from 'currency' (trading currency).
    For ADRs: currency=USD but financialCurrency may be EUR/JPY/CHF etc.
    For foreign-listed: both may be in local currency.

    Returns the currency that financial items (revenue, debt, etc.) are denominated in.
    """
    # Explicit override from company registry takes highest priority
    reporting_ccy = company_info.get("reporting_currency")
    if reporting_ccy:
        return reporting_ccy

    # yfinance provides financialCurrency for this purpose
    fin_ccy = yf_info.get("financialCurrency")
    if fin_ccy:
        return fin_ccy

    # Fall back to trading currency
    return yf_info.get("currency", "USD")


def is_foreign_ticker(yahoo_ticker):
    """Check if a ticker is non-US (has exchange suffix)."""
    return "." in yahoo_ticker and not yahoo_ticker.endswith(".US")
