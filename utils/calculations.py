"""
utils/calculations.py
---------------------
Pure mathematical functions for blast design and cost estimation.
No Streamlit imports — keeps the calculation layer fully testable.
"""

from __future__ import annotations

import math
import numpy as np
from dataclasses import dataclass

from utils.config import AMMONIX_BULK_DENSITY


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

    @property
    def hole_depth(self) -> float:
        return self.bench_height + self.sub_drill

    @property
    def rock_volume_per_hole(self) -> float:
        return self.burden * self.spacing * self.bench_height

    @property
    def charge_length_available(self) -> float:
        """Available length for the explosive column (m)."""
        return max(0.0, self.hole_depth - self.stemming_m - self.safety_gap)

    @property
    def linear_charge_density(self) -> float:
        """Maximum kg of Ammonix per metre for this hole diameter."""
        radius_m = (self.hole_diameter / 1000) / 2
        return math.pi * radius_m ** 2 * AMMONIX_BULK_DENSITY

    @property
    def max_ammonix_capacity(self) -> float:
        """Maximum Ammonix that physically fits in the charge column (kg)."""
        return self.charge_length_available * self.linear_charge_density


@dataclass
class BlastCharges:
    """Explosive quantities per hole."""
    total_explosive_per_hole: float   # kg
    emulsion_per_hole: float          # kg
    ammonix_per_hole: float           # kg


@dataclass
class BlastFleet:
    """Fleet-level totals derived from geometry and charges."""
    num_holes: int
    total_drill_meters: float
    total_ammonix_kg: float
    total_emulsion_kg: float
    total_explosive_kg: float
    total_rock_volume: float


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
    pf_target:         Target powder factor (kg/m³).
    emulsion_per_hole: Booster charge per hole (kg).  Set by the operator.
    """
    total_explosive_per_hole = geom.rock_volume_per_hole * pf_target
    ammonix_per_hole = max(0.0, total_explosive_per_hole - emulsion_per_hole)
    return BlastCharges(
        total_explosive_per_hole=total_explosive_per_hole,
        emulsion_per_hole=emulsion_per_hole,
        ammonix_per_hole=ammonix_per_hole,
    )


def compute_fleet(
    geom: BlastGeometry,
    charges: BlastCharges,
    density_val: float,
    target_tons: float,
) -> BlastFleet:
    """Compute fleet-level totals (number of holes, drill metres, explosive kg)."""
    tonnage_per_hole = geom.rock_volume_per_hole * density_val
    num_holes = int(math.ceil(target_tons / tonnage_per_hole))

    return BlastFleet(
        num_holes=num_holes,
        total_drill_meters=num_holes * geom.hole_depth,
        total_ammonix_kg=num_holes * charges.ammonix_per_hole,
        total_emulsion_kg=num_holes * charges.emulsion_per_hole,
        total_explosive_kg=num_holes * (charges.ammonix_per_hole + charges.emulsion_per_hole),
        total_rock_volume=num_holes * geom.rock_volume_per_hole,
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
    """Compute the full cost breakdown for the blast operation."""
    cost_drilling = fleet.total_drill_meters * cost_drill_per_m
    cost_ammonix_total = fleet.total_ammonix_kg * cost_ammonix_per_kg
    cost_emulsion_total = fleet.total_emulsion_kg * cost_emulsion_per_kg
    cost_accessories = fleet.num_holes * cost_detonator_each
    total_cost_ht = (
        cost_drilling + cost_ammonix_total + cost_emulsion_total
        + cost_accessories + fixed_fees
    )
    total_cost_ttc = total_cost_ht * 1.20
    cost_per_ton = total_cost_ht / target_tons if target_tons > 0 else 0.0

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

    if charges.ammonix_per_hole > geom.max_ammonix_capacity:
        alerts.append(
            f"CRITIQUE: Surcharge Explosive. Capacité trou ({geom.max_ammonix_capacity:.1f} kg) "
            f"< Besoin ({charges.ammonix_per_hole:.1f} kg)."
        )
    if geom.burden > geom.spacing:
        alerts.append(
            "GÉOMÉTRIE INCORRECTE: La Banquette (B) ne doit pas être supérieure à l'Espacement (S)."
        )
    if geom.stemming_m < geom.burden * 0.7:
        alerts.append("SÉCURITÉ: Bourrage insuffisant. Risque de projections.")

    return alerts
