import math

import pytest

from utils.calculations import (
    BlastGeometry,
    PATTERN_CENTER_HOLE,
    PATTERN_RECTANGULAR,
    PATTERN_STAGGERED,
    PF_KG_PER_M3,
    PF_KG_PER_T,
    area_per_hole,
    compute_charges,
    compute_fleet,
    explosive_capacity_kg,
    hole_volume_per_meter,
    pf_in_unit,
    pf_kg_m3_to_kg_t,
    pf_kg_t_to_kg_m3,
    pf_status,
    rock_volume_per_hole,
    target_pf_to_kg_m3,
    total_hole_volume,
    validate_inputs,
)


def test_area_per_hole_patterns():
    assert area_per_hole(5, 5.5, PATTERN_RECTANGULAR) == pytest.approx(27.5)
    assert area_per_hole(5, 5.5, PATTERN_STAGGERED) == pytest.approx(27.5)
    assert area_per_hole(5, 5.5, PATTERN_CENTER_HOLE) == pytest.approx(13.75)
    # centre-hole pattern is NOT a true 2.5 x 2.75 grid
    assert area_per_hole(2.5, 2.75) == pytest.approx(6.875)
    assert 13.75 != pytest.approx(6.875)


def test_area_per_hole_invalid():
    with pytest.raises(ValueError):
        area_per_hole(0, 4)
    with pytest.raises(ValueError):
        area_per_hole(3, 4, "unknown")


def test_volume_conversions():
    assert rock_volume_per_hole(13.75, 10) == pytest.approx(137.5)
    assert hole_volume_per_meter(89) == pytest.approx(0.0062211, rel=1e-4)
    assert total_hole_volume(89, 520) == pytest.approx(3.235, rel=1e-3)
    assert explosive_capacity_kg(3.234992, 1000) == pytest.approx(3234.99)


def test_pf_conversions_roundtrip():
    assert pf_kg_t_to_kg_m3(0.25, 2.5) == pytest.approx(0.625)
    assert pf_kg_m3_to_kg_t(0.625, 2.5) == pytest.approx(0.25)
    assert target_pf_to_kg_m3(0.55, PF_KG_PER_M3, 2.7) == 0.55
    assert target_pf_to_kg_m3(0.25, PF_KG_PER_T, 2.5) == pytest.approx(0.625)


def test_pf_in_both_units_consistent():
    vol, dens, kg = 7150.0, 2.5, 2000.0
    kg_t = pf_in_unit(kg, vol, dens, PF_KG_PER_T)
    kg_m3 = pf_in_unit(kg, vol, dens, PF_KG_PER_M3)
    assert kg_t == pytest.approx(0.111888, rel=1e-4)
    assert kg_m3 == pytest.approx(kg_t * dens)
    with pytest.raises(ValueError):
        pf_in_unit(kg, 0, dens, PF_KG_PER_T)
    with pytest.raises(ValueError):
        pf_in_unit(kg, vol, dens, "lb/yd3")


def test_regression_target_025_kg_per_t_actual_below_target():
    """Row of the field sheet: 520 m drilled, 13.75 m²/hole, 2.5 t/m³, 2000 kg."""
    volume = 520 * area_per_hole(5, 5.5, PATTERN_CENTER_HOLE)
    assert volume == pytest.approx(7150)
    target_kg = volume * 2.5 * 0.25
    assert target_kg == pytest.approx(4468.75)
    actual = pf_in_unit(2000, volume, 2.5, PF_KG_PER_T)
    assert actual < 0.25
    assert pf_status(actual, 0.25) == "low"
    assert pf_status(0.25, 0.25) == "ok"
    assert pf_status(0.40, 0.25) == "high"


def test_charges_and_fleet_match_target_pf():
    geom = BlastGeometry(
        bench_height=10, sub_drill=1, stemming_m=2.5, burden=5, spacing=5.5,
        hole_diameter=89, safety_gap=0, pattern=PATTERN_CENTER_HOLE,
    )
    assert geom.area_per_hole == pytest.approx(13.75)
    pf_m3 = target_pf_to_kg_m3(0.25, PF_KG_PER_T, 2.5)
    charges = compute_charges(geom, pf_m3, emulsion_per_hole=2.0)
    fleet = compute_fleet(geom, charges, 2.5, 20000)
    actual = pf_in_unit(fleet.total_explosive_kg, fleet.total_rock_volume, 2.5, PF_KG_PER_T)
    assert actual == pytest.approx(0.25)
    assert fleet.num_holes == math.ceil(20000 / (137.5 * 2.5))


def test_validation():
    ok = dict(burden=3.5, spacing=4, bench_height=10, sub_drill=1, stemming_m=2.5,
              hole_diameter=89, density=2.65, pf_target=0.25, pf_unit=PF_KG_PER_T,
              target_tons=20000)
    assert validate_inputs(**ok) == []
    assert validate_inputs(**{**ok, "burden": -1})
    assert validate_inputs(**{**ok, "density": 0.2})
    assert validate_inputs(**{**ok, "stemming_m": 20})
    assert validate_inputs(**{**ok, "pf_unit": "x"})
