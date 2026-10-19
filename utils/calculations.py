"""
utils/calculations.py
---------------------
Pure mathematical functions for blast design and cost estimation.
No Streamlit imports — keeps the calculation layer fully testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from utils.config import AMMONIX_BULK_DENSITY, EMULSION_DENSITY

# ---------------------------------------------------------------------------
# UNIT MODEL
# ---------------------------------------------------------------------------
#   hole diameter ........ mm          area per hole ........ m²
#   hole volume / metre .. m³/m        rock volume .......... m³
#   explosive mass ....... kg          rock density ......... t/m³
#   bulk density ......... kg/m³       PF ................... kg/t or kg/m³

PATTERN_RECTANGULAR = "rectangular"
PATTERN_STAGGERED = "staggered"
PATTERN_CENTER_HOLE = "center_hole"

PATTERN_FACTORS: dict[str, float] = {
    # holes per B x S cell
    PATTERN_RECTANGULAR: 1.0,
    PATTERN_STAGGERED: 1.0,    # offset rows, same B x S area per hole
    PATTERN_CENTER_HOLE: 2.0,  # extra hole in every B x S rectangle
}

PF_KG_PER_M3 = "kg/m³"
PF_KG_PER_T = "kg/t"
PF_UNITS = (PF_KG_PER_T, PF_KG_PER_M3)


# ---------------------------------------------------------------------------
# PURE FORMULA HELPERS
# ---------------------------------------------------------------------------

def area_per_hole(burden: float, spacing: float, pattern: str = PATTERN_RECTANGULAR) -> float:
    """
    Effective rock plan area drained by one hole (m²).

    area = B x S / holes_per_cell, where holes_per_cell is 1 for a rectangular
    or staggered (quinconce) grid and 2 when a centre hole is added in every
    B x S rectangle (doubled density, halved area per hole).
    """
    if burden <= 0 or spacing <= 0:
        raise ValueError("Burden and spacing must be strictly positive.")
    try:
        factor = PATTERN_FACTORS[pattern]
    except KeyError:
        raise ValueError(f"Unknown pattern '{pattern}'.") from None
    return burden * spacing / factor


def rock_volume_per_hole(area_m2: float, bench_height: float) -> float:
    """Blasted rock volume per hole (m³) = area per hole (m²) x bench height (m)."""
    return area_m2 * bench_height


def hole_area_m2(diameter_mm: float) -> float:
    """Cross-section area of a blast hole (m²) from its diameter in mm."""
    radius_m = diameter_mm / 1000 / 2
    return math.pi * radius_m ** 2


def hole_volume_per_meter(diameter_mm: float) -> float:
    """Volume of hole per metre drilled (m³/m); e.g. 89 mm -> 0.006221 m³/m."""
    return hole_area_m2(diameter_mm)


def total_hole_volume(diameter_mm: float, drilled_meters: float) -> float:
    """Total drilled hole volume (m³) = m³/m x drilled metres."""
    return hole_volume_per_meter(diameter_mm) * drilled_meters


def explosive_capacity_kg(hole_volume_m3: float, bulk_density_kg_m3: float) -> float:
    """Mass of explosive (kg) filling a hole volume at the given bulk density (kg/m³)."""
    return hole_volume_m3 * bulk_density_kg_m3


def rock_tonnage(volume_m3: float, density_t_m3: float) -> float:
    """Rock mass (t) = volume (m³) x density (t/m³)."""
    return volume_m3 * density_t_m3


def pf_per_tonne(explosive_kg: float, tonnage_t: float) -> float:
    """Powder factor in kg/t."""
    if tonnage_t <= 0:
        raise ValueError("Tonnage must be strictly positive.")
    return explosive_kg / tonnage_t


def pf_per_m3(explosive_kg: float, volume_m3: float) -> float:
    """Powder factor in kg/m³."""
    if volume_m3 <= 0:
        raise ValueError("Volume must be strictly positive.")
    return explosive_kg / volume_m3


def pf_kg_t_to_kg_m3(pf_kg_t: float, density_t_m3: float) -> float:
    """Convert PF from kg/t to kg/m³ (kg/m³ = kg/t x t/m³)."""
    return pf_kg_t * density_t_m3


def pf_kg_m3_to_kg_t(pf_kg_m3: float, density_t_m3: float) -> float:
    """Convert PF from kg/m³ to kg/t (kg/t = kg/m³ / t/m³)."""
    if density_t_m3 <= 0:
        raise ValueError("Density must be strictly positive.")
    return pf_kg_m3 / density_t_m3


def pf_in_unit(explosive_kg: float, volume_m3: float, density_t_m3: float, unit: str) -> float:
    """Actual PF computed directly in the requested unit ('kg/t' or 'kg/m³')."""
    if unit == PF_KG_PER_T:
        return pf_per_tonne(explosive_kg, rock_tonnage(volume_m3, density_t_m3))
    if unit == PF_KG_PER_M3:
        return pf_per_m3(explosive_kg, volume_m3)
    raise ValueError(f"Unknown PF unit '{unit}'.")


def target_pf_to_kg_m3(pf_target: float, unit: str, density_t_m3: float) -> float:
    """Normalise a target PF given in `unit` to kg/m³ for charge sizing."""
    if unit == PF_KG_PER_M3:
        return pf_target
    if unit == PF_KG_PER_T:
        return pf_kg_t_to_kg_m3(pf_target, density_t_m3)
    raise ValueError(f"Unknown PF unit '{unit}'.")


def pf_status(actual: float, target: float, tolerance: float = 0.10) -> str:
    """
    Compare actual and target PF — both MUST be in the same unit.

    Returns 'low' (< target x (1-tol)), 'high' (> target x (1+tol)) or 'ok'.
    """
    if actual < target * (1 - tolerance):
        return "low"
    if actual > target * (1 + tolerance):
        return "high"
    return "ok"


def validate_inputs(
    *,
    burden: float,
    spacing: float,
    bench_height: float,
    sub_drill: float,
    stemming_m: float,
    hole_diameter: float,
    density: float,
    pf_target: float,
    pf_unit: str,
    target_tons: float,
    safety_gap: float = 0.0,
) -> list[str]:
    """Return a list of blocking input errors (empty if inputs are usable)."""
    errors: list[str] = []
    for name, value in (
        ("Banquette (B)", burden), ("Espacement (S)", spacing),
        ("Hauteur de gradin (H)", bench_height), ("Diamètre", hole_diameter),
        ("Densité", density), ("Charge spécifique", pf_target),
        ("Tonnage cible", target_tons),
    ):
        if value is None or value <= 0:
            errors.append(f"{name} doit être strictement positif.")
    if sub_drill < 0 or stemming_m < 0 or safety_gap < 0:
        errors.append("Surforation, bourrage et tampon ne peuvent pas être négatifs.")
    if pf_unit not in PF_UNITS:
        errors.append(f"Unité de charge spécifique inconnue : {pf_unit}.")
    if not errors:
        if not 1.0 <= density <= 4.5:
            errors.append("Densité de roche irréaliste (attendu 1–4.5 t/m³).")
        if not 30 <= hole_diameter <= 250:
            errors.append("Diamètre de foration irréaliste (attendu 30–250 mm).")
        if stemming_m + safety_gap >= bench_height + sub_drill:
            errors.append(
                "Le bourrage (+ tampon) atteint ou dépasse la profondeur du trou : "
                "aucune longueur disponible pour la charge."
            )
    return errors


# ---------------------------------------------------------------------------
# DATA CLASSES
# ---------------------------------------------------------------------------

@dataclass
class BlastGeometry:
    """Geometric parameters describing a single blast hole and the bench."""
    bench_height: float          # m
    sub_drill: float             # m
    stemming_m: float            # m
    burden: float                # m
    spacing: float               # m
    hole_diameter: int           # mm
    safety_gap: float            # m — clearance between stemming and charge
    pattern: str = PATTERN_RECTANGULAR  # see PATTERN_FACTORS

    @property
    def hole_depth(self) -> float:
        return self.bench_height + self.sub_drill

    @property
    def area_per_hole(self) -> float:
        """Effective plan area per hole (m²)."""
        return area_per_hole(self.burden, self.spacing, self.pattern)

    @property
    def rock_volume_per_hole(self) -> float:
        """Rock volume per hole (m³) = effective area x bench height."""
        return rock_volume_per_hole(self.area_per_hole, self.bench_height)

    @property
    def charge_length_available(self) -> float:
        """Available length for the explosive column (m)."""
        return max(0.0, self.hole_depth - self.stemming_m - self.safety_gap)

    @property
    def linear_charge_density(self) -> float:
        """Maximum kg of Ammonix per metre for this hole diameter."""
        return explosive_capacity_kg(
            hole_volume_per_meter(self.hole_diameter), AMMONIX_BULK_DENSITY
        )

    @property
    def emulsion_linear_density(self) -> float:
        """kg of emulsion per metre of hole (booster assumed to fill the hole)."""
        return explosive_capacity_kg(
            hole_volume_per_meter(self.hole_diameter), EMULSION_DENSITY
        )

    def emulsion_length(self, emulsion_kg: float) -> float:
        """Length of hole (m) occupied by the bottom booster."""
        return emulsion_kg / self.emulsion_linear_density

    def ammonix_length(self, ammonix_kg: float) -> float:
        """Length of hole (m) occupied by a given Ammonix mass."""
        return ammonix_kg / self.linear_charge_density

    @property
    def max_ammonix_capacity(self) -> float:
        """Ammonix that would fit if the whole charge column were Ammonix (kg)."""
        return self.charge_length_available * self.linear_charge_density

    def ammonix_capacity(self, emulsion_kg: float) -> float:
        """Ammonix that physically fits above the booster, below the stemming (kg)."""
        free_length = self.charge_length_available - self.emulsion_length(emulsion_kg)
        return max(0.0, free_length) * self.linear_charge_density


@dataclass
class BlastCharges:
    """Explosive quantities per hole (loaded = what physically fits in the hole)."""
    total_explosive_per_hole: float   # kg — loaded (Ammonix + Émulsion)
    emulsion_per_hole: float          # kg
    ammonix_per_hole: float           # kg — loaded, capped at hole capacity
    target_explosive_per_hole: float = 0.0  # kg — required by the target PF
    ammonix_required: float = 0.0     # kg — Ammonix required by the target PF
    ammonix_capacity: float = 0.0     # kg — Ammonix that fits in the hole

    @property
    def capacity_limited(self) -> bool:
        """True when the hole cannot hold the Ammonix required by the target PF."""
        return self.ammonix_required > self.ammonix_capacity + 1e-9


@dataclass
class BlastFleet:
    """Fleet-level totals derived from geometry and charges."""
    num_holes: int
    total_drill_meters: float
    total_ammonix_kg: float
    total_emulsion_kg: float
    total_explosive_kg: float
    total_rock_volume: float
    total_tonnage: float = 0.0       # t — rock actually blasted (≥ target)


@dataclass
class CostBreakdown:
    """Detailed cost estimate for the blast operation."""
    cost_drilling: float
    cost_ammonix_total: float
    cost_emulsion_total: float
    cost_accessories: float
    fixed_fees: float
    total_cost_ht: float
    total_cost_ttc: float
    cost_per_ton: float


# ---------------------------------------------------------------------------
# CALCULATION FUNCTIONS
# ---------------------------------------------------------------------------

def compute_charges(
    geom: BlastGeometry,
    pf_target: float,
    emulsion_per_hole: float,
) -> BlastCharges:
    """
    Determine explosive quantities per hole.

    Parameters
    ----------
    geom:              BlastGeometry instance for the current design.
    pf_target:         Target powder factor in kg/m³ (convert kg/t first
                       with target_pf_to_kg_m3).
    emulsion_per_hole: Booster charge per hole (kg).  Set by the operator.

    The Ammonix actually loaded is capped at what physically fits between the
    booster and the stemming; the loaded total is therefore always consistent
    with the drawn column and the fleet totals.
    """
    target_explosive = geom.rock_volume_per_hole * pf_target
    ammonix_required = max(0.0, target_explosive - emulsion_per_hole)
    capacity = geom.ammonix_capacity(emulsion_per_hole)
    ammonix_per_hole = min(ammonix_required, capacity)
    return BlastCharges(
        total_explosive_per_hole=ammonix_per_hole + emulsion_per_hole,
        emulsion_per_hole=emulsion_per_hole,
        ammonix_per_hole=ammonix_per_hole,
        target_explosive_per_hole=target_explosive,
        ammonix_required=ammonix_required,
        ammonix_capacity=capacity,
    )


def compute_fleet(
    geom: BlastGeometry,
    charges: BlastCharges,
    density_val: float,
    target_tons: float,
) -> BlastFleet:
    """Compute fleet-level totals (number of holes, drill metres, explosive kg)."""
    if target_tons <= 0 or density_val <= 0:
        raise ValueError("Target tonnage and density must be strictly positive.")
    tonnage_per_hole = rock_tonnage(geom.rock_volume_per_hole, density_val)
    # round() guards against float noise turning an exact count (e.g. 58.0000001) into +1
    num_holes = max(1, int(math.ceil(round(target_tons / tonnage_per_hole, 9))))

    return BlastFleet(
        num_holes=num_holes,
        total_drill_meters=num_holes * geom.hole_depth,
        total_ammonix_kg=num_holes * charges.ammonix_per_hole,
        total_emulsion_kg=num_holes * charges.emulsion_per_hole,
        total_explosive_kg=num_holes * charges.total_explosive_per_hole,
        total_rock_volume=num_holes * geom.rock_volume_per_hole,
        total_tonnage=num_holes * tonnage_per_hole,
    )


def compute_costs(
    fleet: BlastFleet,
    charges: BlastCharges,
    target_tons: float,
    cost_drill_per_m: float,
    cost_ammonix_per_kg: float,
    cost_emulsion_per_kg: float,
    cost_detonator_each: float,
    fixed_fees: float,
) -> CostBreakdown:
    """
    Compute the full cost breakdown for the blast operation.

    Cost per tonne is based on the tonnage actually blasted by the drilled
    holes (fleet.total_tonnage, ≥ target because the hole count is rounded up);
    `target_tons` is only used as a fallback.
    """
    cost_drilling = fleet.total_drill_meters * cost_drill_per_m
    cost_ammonix_total = fleet.total_ammonix_kg * cost_ammonix_per_kg
    cost_emulsion_total = fleet.total_emulsion_kg * cost_emulsion_per_kg
    cost_accessories = fleet.num_holes * cost_detonator_each
    total_cost_ht = (
        cost_drilling + cost_ammonix_total + cost_emulsion_total
        + cost_accessories + fixed_fees
    )
    total_cost_ttc = total_cost_ht * 1.20
    tonnage = fleet.total_tonnage if fleet.total_tonnage > 0 else target_tons
    cost_per_ton = total_cost_ht / tonnage if tonnage > 0 else 0.0

    return CostBreakdown(
        cost_drilling=cost_drilling,
        cost_ammonix_total=cost_ammonix_total,
        cost_emulsion_total=cost_emulsion_total,
        cost_accessories=cost_accessories,
        fixed_fees=fixed_fees,
        total_cost_ht=total_cost_ht,
        total_cost_ttc=total_cost_ttc,
        cost_per_ton=cost_per_ton,
    )


def get_technical_alerts(
    geom: BlastGeometry,
    charges: BlastCharges,
) -> list[str]:
    """Return a list of technical warning messages for the current design."""
    alerts: list[str] = []

    available = geom.charge_length_available
    booster_len = geom.emulsion_length(charges.emulsion_per_hole)
    if booster_len > available:
        alerts.append(
            f"CRITIQUE: L'émulsion ({charges.emulsion_per_hole:.1f} kg, soit {booster_len:.2f} m) "
            f"dépasse la longueur de charge disponible ({available:.2f} m)."
        )
    elif charges.capacity_limited:
        alerts.append(
            f"CRITIQUE: Surcharge Explosive. Capacité Ammonix du trou "
            f"({charges.ammonix_capacity:.1f} kg) < Besoin ({charges.ammonix_required:.1f} kg). "
            f"Charge limitée à la capacité : réduire la maille, augmenter le diamètre "
            f"ou réduire le bourrage."
        )
    if geom.burden > geom.spacing:
        alerts.append(
            "GÉOMÉTRIE INCORRECTE: La Banquette (B) ne doit pas être supérieure à l'Espacement (S)."
        )
    if geom.stemming_m < geom.burden * 0.7:
        alerts.append("SÉCURITÉ: Bourrage insuffisant. Risque de projections.")

    return alerts
