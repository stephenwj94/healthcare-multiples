"""
config/color_palette.py
Centralised colour definitions for the entire app.

All segment colours, badge styles, and Plotly theme tokens live here.
Import from this module instead of defining colours locally.
"""

# ── Segment key → short display name ─────────────────────────────────────────
SEGMENT_SHORT: dict[str, str] = {
    "pharma":          "Pharma",
    "consumer_health": "Consumer Health",
    "medtech":         "MedTech",
    "life_sci_tools":  "LST/Dx",
    "services":        "Asset-Light Services",
    "cdmo":            "Asset-Heavy Services",
    "health_tech":     "Health Tech",
}

# ── Canonical segment colours (keyed by short display name) ──────────────────
SEG_COLOR_MAP: dict[str, str] = {
    "Pharma":                "#2563EB",   # Blue
    "Consumer Health":       "#059669",   # Green
    "MedTech":               "#DC2626",   # Red
    "LST/Dx":              "#7C3AED",   # Purple
    "Asset-Light Services":  "#F59E0B",   # Amber
    "Asset-Heavy Services":  "#EA580C",   # Orange
    "Health Tech":           "#0891B2",   # Cyan
    # Legacy aliases for backward compat
    "Life Sci Tools":  "#7C3AED",
    "Services":        "#F59E0B",
    "CDMOs":           "#EA580C",
}

# ── Segment colours keyed by internal segment key (for chart_builder compat) ─
SEGMENT_COLORS: dict[str, str] = {
    "pharma":          "#2563EB",
    "consumer_health": "#059669",
    "medtech":         "#DC2626",
    "life_sci_tools":  "#7C3AED",
    "services":        "#F59E0B",
    "cdmo":            "#EA580C",
    "health_tech":     "#0891B2",
}

# ── Badge styles (dark mode — solid opaque backgrounds) ──────────────────────
# bg = very dark tint of segment colour, fg = full-saturation segment colour
BADGE_STYLES: dict[str, tuple[str, str]] = {
    "Pharma":                ("#0F1F3D", "#2563EB"),
    "Consumer Health":       ("#0A2A1F", "#059669"),
    "MedTech":               ("#3D1515", "#DC2626"),
    "LST/Dx":              ("#231538", "#7C3AED"),
    "Asset-Light Services":  ("#3D2F0F", "#F59E0B"),
    "Asset-Heavy Services":  ("#3D1F0A", "#EA580C"),
    "Health Tech":           ("#0A2A33", "#0891B2"),
    "Life Sci Tools":  ("#231538", "#7C3AED"),
    "Services":        ("#3D2F0F", "#F59E0B"),
    "CDMOs":           ("#3D1F0A", "#EA580C"),
}

# ── Badge styles (light mode — solid light backgrounds) ──────────────────────
# bg ≈ 10% opacity of segment colour over white, fg = full-saturation segment colour
LIGHT_BADGE_STYLES: dict[str, tuple[str, str]] = {
    "Pharma":                ("#E9EFFC", "#1D4ED8"),
    "Consumer Health":       ("#E6F4EE", "#047857"),
    "MedTech":               ("#FCEAEA", "#B91C1C"),
    "LST/Dx":              ("#F1EAFB", "#6D28D9"),
    "Asset-Light Services":  ("#FEF3E2", "#B45309"),
    "Asset-Heavy Services":  ("#FDECE0", "#C2410C"),
    "Health Tech":           ("#E2F1F5", "#0E7490"),
    "Life Sci Tools":  ("#F1EAFB", "#6D28D9"),
    "Services":        ("#FEF3E2", "#B45309"),
    "CDMOs":           ("#FDECE0", "#C2410C"),
}

# ── Plotly theme tokens (light mode defaults — IS_LIGHT is always True) ──────
PLOTLY_BG:   str = "#FFFFFF"
PLOTLY_GRID: str = "#F3F4F6"
PLOTLY_TEXT:  str = "#64748B"

# ── Semantic accent colours (light mode) ─────────────────────────────────────
GREEN:        str = "#059669"
YELLOW:       str = "#D97706"
RED:          str = "#DC2626"
MUTED:        str = "#94A3B8"
TICKER_COLOR: str = "#1D4ED8"
