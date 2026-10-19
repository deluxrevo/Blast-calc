"""
utils/config.py
---------------
Static configuration: geology profiles and application-wide constants.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# GEOLOGY PROFILES
# ---------------------------------------------------------------------------

# Recommended B x S are sized so that rec_pf (kg/m³) can physically be loaded
# in the default hole (Ø 89 mm, H = 10 m, J = 1 m, T = 2.5 m, 2 kg booster):
# ~45 kg/hole max  ->  B x S x H x rec_pf must stay below that.
GEOLOGY_PROFILES: dict[str, dict[str, str | float]] = {
    "Gréso-Pélitique (Viséen)": {
        "rec_pf": 0.55,
        "rec_burden": 2.7,
        "rec_spacing": 3.0,
        "rock_hardness": "Moyenne/Dure",
        "abrasivity": "Moyenne",
        "density": 2.70,
        "quality_note": "Risque de fines argileuses (Scalpage requis).",
        "clay_risk": "MODÉRÉ",
    },
    "Psammites (Ordovicien)": {
        "rec_pf": 0.65,
        "rec_burden": 2.5,
        "rec_spacing": 2.7,
        "rock_hardness": "TRÈS DURE",
        "abrasivity": "Élevée (Usure foration)",
        "density": 2.75,
        "quality_note": "Excellent granulat (Béton HP).",
        "clay_risk": "FAIBLE",
    },
    "Calcaire Franc": {
        # rec_pf reduced from 0.45 → 0.25 kg/m³ to reflect a realistic first-step
        # target for the quarry based on field invoice analysis (Fév–Mars 2026).
        # At 0.25 kg/m³ the stemming column is raised by ~2 m vs. current practice
        # (~0.15 kg/m³), improving fragmentation without a large cost increase.
        "rec_pf": 0.25,
        "rec_burden": 3.5,
        "rec_spacing": 4.2,
        "rock_hardness": "Moyenne",
        "abrasivity": "Faible",
        "density": 2.65,
        "quality_note": "Standard.",
        "clay_risk": "NUL",
    },
    "Zone de Faille / Altérée": {
        "rec_pf": 0.50,
        "rec_burden": 2.8,
        "rec_spacing": 3.2,
        "rock_hardness": "Faible",
        "abrasivity": "Faible",
        "density": 2.50,
        "quality_note": "Matériau stérile probable.",
        "clay_risk": "ÉLEVÉ",
    },
}

# ---------------------------------------------------------------------------
# APPLICATION CONSTANTS
# ---------------------------------------------------------------------------

APP_TITLE = "SGT - Système de Gestion de Tir"
APP_SUBTITLE = "Tableau de Bord d'Ingénierie de Tir"
SITE_NAME = "Carrière Benslimane"

# Ammonix bulk density (kg/m³) used for linear charge capacity
AMMONIX_BULK_DENSITY: float = 850.0

# Emulsion (booster) density (kg/m³). Used only to estimate the length of hole
# occupied by the booster at the bottom of the column (assumed to fill the hole).
EMULSION_DENSITY: float = 1150.0

# Default emulsion booster charge per hole (kg) — 2 cartridges of Emulcad E5 1000 g
DEFAULT_EMULSION_KG: float = 2.0

# Default safety gap between stemming and main charge column (m).
# Set to 0.0 by default so the diagram matches standard field practice where
# stemming sits directly on top of the explosive column.
DEFAULT_SAFETY_GAP_M: float = 0.0
