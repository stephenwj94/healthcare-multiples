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

# Fetch settings
FETCH_DELAY_SECONDS = float(os.getenv("FETCH_DELAY_SECONDS", "0.5"))

# Segment display names
SEGMENT_DISPLAY = {
    "pharma":          "Pharma",
    "consumer_health": "Consumer Health",
    "medtech":         "MedTech",
    "life_sci_tools":  "Life Sci Tools / Dx / Bioprocessing",
    "services":        "Asset-Light Services",
    "cdmo":            "CDMOs",
    "health_tech":     "Health Tech",
}

# Sub-segments pass through as-is for v1 (no display-name remapping)
SUB_SEGMENT_DISPLAY: dict[str, str] = {}

# Segment colors — canonical source is config.color_palette
from config.color_palette import SEGMENT_COLORS  # noqa: E402, F401
