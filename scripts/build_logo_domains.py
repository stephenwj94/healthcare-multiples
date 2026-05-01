"""
Auto-generate healthcare ticker → company domain mapping for components/logos.py.

For each company in the registry, looks up `Ticker.info["website"]` via yfinance,
strips it to a bare domain, and emits a Python dict literal.

Usage:
    python scripts/build_logo_domains.py        # prints the dict
    python scripts/build_logo_domains.py --write # also rewrites components/logos.py

Failures (no website returned, lookup error) are skipped — the logo helper
already returns None for unmapped tickers.
"""
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yfinance as yf
from config.company_registry import COMPANY_REGISTRY

LOGOS_PY = Path(__file__).resolve().parent.parent / "components" / "logos.py"


def normalize_domain(website: str | None) -> str | None:
    if not website:
        return None
    website = website.strip()
    if not website:
        return None
    if "://" not in website:
        website = "https://" + website
    try:
        host = urlparse(website).hostname or ""
    except Exception:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        return None
    return host


def fetch_domain(yahoo_ticker: str) -> str | None:
    try:
        info = yf.Ticker(yahoo_ticker).info or {}
    except Exception:
        return None
    return normalize_domain(info.get("website"))


def main() -> None:
    write = "--write" in sys.argv
    domains: dict[str, str] = {}
    total = len(COMPANY_REGISTRY)

    for i, c in enumerate(COMPANY_REGISTRY, 1):
        ticker = c["ticker"]
        yt = c["yahoo_ticker"]
        d = fetch_domain(yt)
        status = d or "—"
        print(f"[{i}/{total}] {ticker:>10}  {yt:>14}  {status}")
        if d:
            domains[ticker] = d

    print(f"\nResolved {len(domains)}/{total} domains.")

    # Emit dict literal sorted alphabetically by ticker.
    lines = ["_TICKER_DOMAINS: dict[str, str] = {"]
    for t in sorted(domains.keys()):
        lines.append(f'    {t!r:<14}: {domains[t]!r},')
    lines.append("}")
    rendered = "\n".join(lines)

    if write:
        src = LOGOS_PY.read_text()
        new_src = re.sub(
            r"_TICKER_DOMAINS: dict\[str, str\] = \{[\s\S]*?^\}",
            rendered,
            src,
            count=1,
            flags=re.MULTILINE,
        )
        if new_src == src:
            print("ERROR: failed to find _TICKER_DOMAINS block in logos.py", file=sys.stderr)
            sys.exit(1)
        LOGOS_PY.write_text(new_src)
        print(f"Wrote {LOGOS_PY}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
