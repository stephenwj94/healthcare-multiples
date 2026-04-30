# Healthcare Public Market Comps

Streamlit dashboard tracking public-market trading multiples for ~318 healthcare companies across 7 sub-sectors. Forked from [`jamesmaycher/tech-multiples`](https://github.com/jamesmaycher/tech-multiples) — same architecture, healthcare universe.

**Live site:** _(set up via Streamlit Cloud — password-protected)_

## Sub-sectors covered

| Segment | Count | Examples |
|---|---|---|
| Pharma | 122 | LLY, JNJ, ABBV, MRK, NVS, ROG, AZN |
| Consumer Health | 29 | KVUE, HLN, RB, ZTS |
| MedTech | 58 | MDT, BSX, SYK, EW, ABT, ISRG |
| Life Sci Tools / Dx / Bioprocessing | 52 | TMO, DHR, A, MTD, IDXX |
| Asset-Light Services | 17 | IQV, ICLR, MEDP |
| CDMOs | 13 | LZAGY, WuXi |
| Health Tech | 27 | VEEV, DOCS, HQY, PHR |

Universe sourced from `Permira_HC_Public_Universe_v2.xlsx` (filtered for ≥$150M cap, public, no active definitive agreements).

## Local setup

```bash
# 1. Install deps in a venv (one-time)
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure secrets (one-time) — set the app password
cat > .streamlit/secrets.toml <<EOF
APP_PASSWORD = "permirahc"
EOF

# 3. Refresh data (yfinance — free, ~5 min for 318 names)
python -m fetcher.run_fetch

# 4. Run locally
streamlit run app.py
```

Default password: `permirahc` (override via `.streamlit/secrets.toml` or Streamlit Cloud secrets UI).

## Updating the company universe

The registry lives at `config/company_registry.py` and is generated from the xlsx. To regenerate after editing the source spreadsheet:

```bash
python scripts/build_registry.py
```

## Daily refresh

Re-running `python -m fetcher.run_fetch` overwrites the latest snapshot for each company. The `daily_multiples` table accumulates one row per company per day for time-series views (Valuation Lookback, Regression).

## Layout

```
app.py                       # Streamlit entrypoint + login gate
config/
  company_registry.py        # 318-company universe (auto-generated)
  factset_registry.py        # Display ticker → FactSet ID overrides
  settings.py, color_palette.py
components/
  comp_table.py              # Sticky-header HTML comp table
  formatters.py, sidebar.py, chart_builder.py, logos.py
fetcher/
  yf_fetcher.py              # Yahoo Finance pull (default)
  fmp_fetcher.py             # Financial Modeling Prep (set FMP_API_KEY in .env to enable)
  factset_process.py         # FactSet pipeline (requires API credentials — TODO)
  calculators.py, db_manager.py, run_fetch.py
views/
  01_Winners_and_Losers.py
  02_Valuation_Lookback.py
  03_Valuation_Regression.py
  04_Pharma.py … 10_Health_Tech.py     # one per segment
  11_Scenario_Screener.py
  12_Comp_Set_Builder.py
data/
  healthcare_multiples.db    # SQLite — committed; refresh via run_fetch
scripts/
  build_registry.py          # Regenerate company_registry.py from the xlsx
```

## Data source roadmap

- **v1 (current):** yfinance — free, sufficient for prices/EV/LTM. Some flakiness on small-caps and intl tickers.
- **v2 (planned):** FactSet REST API. Stephen has account 1865795 and needs to create an API key at https://developer.factset.com/api-authentication. Add credentials to `.streamlit/secrets.toml` once available.
