"""
FactSet ticker mapping for the Healthcare Multiples universe.

Maps between display tickers (used in company_registry.py and the DB)
and FactSet identifiers (TICKER-COUNTRY format).

Most US-listed companies use the simple TICKER-US format.
International companies need explicit country-suffix mappings.
"""

from config.company_registry import COMPANY_REGISTRY

# International companies that need explicit FactSet IDs.
# (all others default to TICKER-US — covers US listings + ADRs)
# Country codes: GB=UK, DE=Germany, CH=Switzerland, FR=France, JP=Japan,
# CA=Canada, IT=Italy, ES=Spain, FI=Finland, DK=Denmark, BE=Belgium,
# NL=Netherlands, IE=Ireland, AU=Australia, IN=India, HK=Hong Kong,
# CN=China (mainland), KR=Korea, BR=Brazil, SI=Slovenia.
_INTERNATIONAL_OVERRIDES = {
    # Pharma — Switzerland (SIX)
    "ROG":         "ROG-CH",       # Roche Holding
    "GALD":        "GALD-CH",      # Galderma
    "SDZ":         "SDZ-CH",       # Sandoz Group
    "IDIA":        "IDIA-CH",      # Idorsia
    # Pharma — Germany (Xetra)
    "BAYN":        "BAY-DE",       # Bayer
    "MRK GR":      "MRK-DE",       # Merck KGaA
    "BIO3":        "BIO3-DE",      # Biotest
    # Pharma — Japan (Tokyo)
    "4568":        "4568-JP",      # Daiichi Sankyo
    "4503":        "4503-JP",      # Astellas Pharma
    "4578":        "4578-JP",      # Otsuka Holdings
    "4523":        "4523-JP",      # Eisai
    "4519":        "4519-JP",      # Chugai Pharmaceutical
    "4151":        "4151-JP",      # Kyowa Kirin
    # Pharma — Italy
    "REC":         "REC-IT",       # Recordati
    # Pharma — France (Euronext Paris)
    "IPN":         "IPN-FR",       # Ipsen
    # Pharma — Finland
    "ORNBV":       "ORNBV-FI",     # Orion
    # Pharma — Denmark
    "LUN":         "LUN-DK",       # Lundbeck
    "ZEAL":        "ZEAL-DK",      # Zealand Pharma
    "BAVA":        "BAVA-DK",      # Bavarian Nordic
    # Pharma — Belgium
    "UCB":         "UCB-BE",       # UCB
    # Pharma — Spain
    "ALM":         "ALM-ES",       # Almirall
    # Pharma — India (NSE)
    "SUNPHARMA":   "SUNPHARMA-IN",
    "CIPLA":       "CIPLA-IN",
    "LUPIN":       "LUPIN-IN",
    "AUROPHARMA":  "AUROPHARMA-IN",
    "ZYDUSLIFE":   "ZYDUSLIFE-IN",
    "TORNTPHARM":  "TORNTPHARM-IN",
    "GLENMARK":    "GLENMARK-IN",
    # Pharma — UK (LSE)
    "HIK":         "HIK-GB",       # Hikma Pharmaceuticals
    # Pharma — Slovenia
    "KRKG":        "KRKG-SI",      # Krka
    # Pharma — Hong Kong
    "6185":        "6185-HK",      # CanSino Biologics
    # Pharma — Australia
    "CSL":         "CSL-AU",       # CSL Limited
    # Consumer Health — UK
    "RKT":         "RKT-GB",       # Reckitt Benckiser
    "PETS":        "PETS-GB",      # Pets at Home Group
    "CVSG":        "CVSG-GB",      # CVS Group
    # Consumer Health — Japan
    "4581":        "4581-JP",      # Taisho Pharmaceutical
    "4967":        "4967-JP",      # Kobayashi Pharmaceutical
    "4527":        "4527-JP",      # Rohto Pharmaceutical
    # Consumer Health — Brazil
    "HYPE3":       "HYPE3-BR",     # Hypera Pharma
    # Consumer Health — Ireland
    "GLB":         "GLB-IE",       # Glanbia
    # Consumer Health — France
    "VIRP":        "VIRP-FR",      # Virbac
    "VETO":        "VETO-FR",      # Vetoquinol
    # MedTech — Japan
    "7733":        "7733-JP",      # Olympus
    "7751":        "7751-JP",      # Canon Medical
    "4901":        "4901-JP",      # Fujifilm Holdings
    # MedTech — Denmark
    "COLO B":      "COLOB-DK",     # Coloplast
    # MedTech — UK
    "CTEC":        "CTEC-GB",      # Convatec Group
    # MedTech — Germany
    "SHL":         "SHL-DE",       # Siemens Healthineers (NOTE: SHL ticker
                                   # also used by Sonic Healthcare in AU; the
                                   # life_sci_tools entry is overridden below.)
    "AFX":         "AFX-DE",       # Carl Zeiss Meditec
    # MedTech — Netherlands
    "PHIA":        "PHIA-NL",      # Koninklijke Philips
    # MedTech — France/Italy (listed in Paris)
    "EL":          "EL-FR",        # EssilorLuxottica
    # MedTech — Switzerland
    "STMN":        "STMN-CH",      # Straumann Group
    # Life Sci Tools — Switzerland
    "TECN":        "TECN-CH",      # Tecan Group
    "BANB":        "BANB-CH",      # Bachem Holding
    # Life Sci Tools — France/Luxembourg/etc. (Paris)
    "ERF":         "ERF-FR",       # Eurofins Scientific (Luxembourg co.)
    "DIM":         "DIM-FR",       # Sartorius Stedim Biotech
    "BIM":         "BIM-FR",       # bioMérieux
    # Life Sci Tools — UK
    "SXS":         "SXS-GB",       # Spectris
    "HLMA":        "HLMA-GB",      # Halma
    # Life Sci Tools — Germany
    "SRT":         "SRT-DE",       # Sartorius AG
    "GXI":         "GXI-DE",       # Gerresheimer
    # Life Sci Tools — Italy
    "DIA":         "DIA-IT",       # Diasorin
    # Life Sci Tools — Australia (Sonic, Healius)
    # Note: Sonic Healthcare uses SHL ticker but listed in AU; can't disambiguate
    # in a flat dict from MedTech Siemens Healthineers. Best-effort: leave HLS only.
    "HLS":         "HLS-AU",       # Healius
    # Life Sci Tools — China (Shenzhen)
    "300760":      "300760-CN",    # Mindray Bio-Medical
    "000710":      "000710-CN",    # Berry Genomics
    # Services — Hong Kong
    "2359":        "2359-HK",      # WuXi AppTec
    "3759":        "3759-HK",      # Pharmaron Beijing
    # Services — China (Shenzhen)
    "300347 / 3347": "300347-CN",  # Tigermed
    # Services — India
    "INDEGENE":    "INDEGENE-IN",
    # CDMO — Switzerland
    "LONN":        "LONN-CH",      # Lonza Group
    "SFZN":        "SFZN-CH",      # Siegfried Holding
    # CDMO — Hong Kong
    "2269":        "2269-HK",      # WuXi Biologics
    # CDMO — South Korea
    "207940":      "207940-KR",    # Samsung Biologics
    # CDMO — China (Shenzhen)
    "002821":      "002821-CN",    # Asymchem Laboratories
    # CDMO — India
    "DIVISLAB":    "DIVISLAB-IN",
    "PPLPHARMA":   "PPLPHARMA-IN",
    "SUVENPHAR":   "SUVENPHAR-IN",
    "SYNGENE":     "SYNGENE-IN",
    "BIOCON":      "BIOCON-IN",
    # CDMO — Japan
    "8086":        "8086-JP",      # Nipro Corporation
    # Health Tech — Australia
    "PME":         "PME-AU",       # Pro Medicus
    # Health Tech — UK
    "IDOX":        "IDOX-GB",      # Idox
}


def display_to_factset(ticker: str) -> str:
    """Convert display ticker to FactSet identifier."""
    return _INTERNATIONAL_OVERRIDES.get(ticker, f"{ticker}-US")


def factset_to_display(fs_id: str) -> str:
    """Convert FactSet identifier to display ticker."""
    # Check reverse of international overrides first
    for display, fs in _INTERNATIONAL_OVERRIDES.items():
        if fs == fs_id:
            return display
    # Default: strip -US suffix
    return fs_id.replace("-US", "")


def get_all_factset_ids() -> list[str]:
    """Return FactSet IDs for all companies in the registry."""
    return [display_to_factset(c["ticker"]) for c in COMPANY_REGISTRY]


def get_factset_id_map() -> dict[str, str]:
    """Return dict mapping FactSet ID -> display ticker for all companies."""
    return {display_to_factset(c["ticker"]): c["ticker"] for c in COMPANY_REGISTRY}
