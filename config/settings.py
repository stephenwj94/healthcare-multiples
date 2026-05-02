import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "healthcare_multiples.db"
EXCEL_OVERRIDE_PATH = DATA_DIR / "factset_overrides.xlsx"

# Ensure data directory exists
DATA_DIR.mkdir(exist_ok=True)

# API Keys
FMP_API_KEY = os.getenv("FMP_API_KEY", "")
USE_FMP = bool(FMP_API_KEY)

# FactSet credentials — read from Streamlit secrets when available, else env.
# st.secrets raises outside a Streamlit runtime, so wrap in try/except so the
# fetcher can run via `python -m fetcher.run_fetch` from the command line.
try:
    import streamlit as st  # type: ignore
    FACTSET_USERNAME_SERIAL = (
        st.secrets.get("FACTSET_USERNAME_SERIAL", "") or os.getenv("FACTSET_USERNAME_SERIAL", "")
    )
    FACTSET_API_KEY = (
        st.secrets.get("FACTSET_API_KEY", "") or os.getenv("FACTSET_API_KEY", "")
    )
except Exception:
    FACTSET_USERNAME_SERIAL = os.getenv("FACTSET_USERNAME_SERIAL", "")
    FACTSET_API_KEY = os.getenv("FACTSET_API_KEY", "")

# When run from CLI (no Streamlit runtime), fall back to parsing
# `.streamlit/secrets.toml` directly so we don't need duplicated env vars.
if not FACTSET_API_KEY:
    _secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if _secrets_path.exists():
        try:
            try:
                import tomllib  # py311+
            except ImportError:  # pragma: no cover
                import tomli as tomllib  # type: ignore
            with open(_secrets_path, "rb") as fh:
                _toml = tomllib.load(fh)
            FACTSET_USERNAME_SERIAL = FACTSET_USERNAME_SERIAL or _toml.get("FACTSET_USERNAME_SERIAL", "")
            FACTSET_API_KEY = FACTSET_API_KEY or _toml.get("FACTSET_API_KEY", "")
        except Exception:
            pass

USE_FACTSET = bool(FACTSET_API_KEY and FACTSET_USERNAME_SERIAL)

# Fetch settings
FETCH_DELAY_SECONDS = float(os.getenv("FETCH_DELAY_SECONDS", "0.5"))

# Segment display names
SEGMENT_DISPLAY = {
    "pharma":          "Pharma",
    "consumer_health": "Consumer Health",
    "medtech":         "MedTech",
    "life_sci_tools":  "LST / Dx",
    "services":        "Asset-Light Services",
    "cdmo":            "Asset-Heavy Services",
    "health_tech":     "Health Tech",
}

# Sub-segments pass through as-is for v1 (no display-name remapping)
SUB_SEGMENT_DISPLAY: dict[str, str] = {}

# Segment colors — canonical source is config.color_palette
from config.color_palette import SEGMENT_COLORS  # noqa: E402, F401
