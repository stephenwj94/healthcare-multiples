"""
Shared news filtering — quality gate and healthcare relevance filter.

Used by Home, News & Earnings, M&A Activity pages.
"""

# Sources to exclude — low-quality, clickbait, or paywalled aggregators
BLOCKED_SOURCES = {
    "barrons",
    "barron's",
    "motley fool",
    "the motley fool",
    "fool.com",
    "investorplace",
    "investor place",
    "24/7 wall st",
    "24/7 wall street",
    "wall st",
    "tipranks",
    "insidermonkey",
    "insider monkey",
    "benzinga",
    "yahoo finance video",
    "simply wall st",
    "zacks",
    "zacks investment",
    "zacks equity research",
    "seeking alpha",
    "stocknews",
    "stocknews.com",
    "thestreet",
    "the street",
    "marketbeat",
    "gurufocus",
    "investopedia",
    "smarteranalyst",
}

# Healthcare-relevant keywords for filtering ETF-sourced news
# (company-specific news from individual tickers doesn't need this)
HC_KEYWORDS = {
    # Industry terms
    "pharma", "pharmaceutical", "biotech", "biotechnology", "medtech",
    "medical device", "medical devices", "life science", "life sciences",
    "healthcare", "health care", "health tech", "healthtech", "cdmo",
    "diagnostics", "therapeutic", "therapeutics", "biosimilar",
    "generic drug", "specialty pharma",
    # Clinical / regulatory
    "fda", "ema", "clinical trial", "phase 1", "phase 2", "phase 3",
    "phase i", "phase ii", "phase iii", "approval", "approved",
    "drug approval", "nda", "bla", "510k", "510(k)", "pma",
    "regulatory", "cms", "medicare", "medicaid", "aca",
    # Products / science
    "drug", "therapy", "treatment", "vaccine", "antibody",
    "oncology", "cancer", "diabetes", "cardiovascular", "cardio",
    "neurology", "immunology", "rare disease", "gene therapy",
    "cell therapy", "mrna", "peptide", "biologic",
    # M&A / deals
    "acquisition", "acquire", "acquired", "merger", "merge", "merged",
    "buyout", "takeover", "deal", "divest", "divestiture", "spin-off",
    "spinoff", "ipo", "listing",
    # Financial / company events
    "earnings", "revenue", "guidance", "outlook", "forecast",
    "fda approval", "pipeline", "patent", "exclusivity",
    # Major companies (catch relevant articles)
    "pfizer", "johnson & johnson", "j&j", "abbvie", "merck",
    "lilly", "eli lilly", "novo nordisk", "roche", "novartis",
    "astrazeneca", "sanofi", "gsk", "glaxo", "bms",
    "bristol-myers", "amgen", "gilead", "regeneron", "moderna",
    "biogen", "vertex", "danaher", "thermo fisher", "agilent",
    "medtronic", "stryker", "edwards", "intuitive surgical",
    "unitedhealth", "elevance", "cigna", "humana", "anthem",
    "hca", "hospital", "insurer", "payer", "payor",
}


def is_source_blocked(source: str) -> bool:
    """Return True if the source is in the blocklist."""
    if not source:
        return False
    s = source.strip().lower()
    return s in BLOCKED_SOURCES


def is_healthcare_relevant(title: str) -> bool:
    """Return True if the title contains healthcare-relevant keywords.

    Use this for ETF-sourced news where articles may be generic market commentary.
    Do NOT use this for company-specific news (fetched by individual ticker).
    """
    if not title:
        return False
    t = title.lower()
    return any(kw in t for kw in HC_KEYWORDS)


def filter_news(articles: list[dict], require_hc_relevance: bool = True) -> list[dict]:
    """Filter a list of news articles.

    Args:
        articles: List of dicts with at least 'title' and 'source'/'provider' keys.
        require_hc_relevance: If True, also filter for healthcare keyword relevance.
            Set to False for company-specific news (already targeted).

    Returns:
        Filtered list.
    """
    result = []
    for a in articles:
        source = a.get("source", "") or a.get("provider", "") or ""
        if is_source_blocked(source):
            continue
        if require_hc_relevance and not is_healthcare_relevant(a.get("title", "")):
            continue
        result.append(a)
    return result
