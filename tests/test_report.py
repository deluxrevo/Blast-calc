import matplotlib

matplotlib.use("Agg")

from utils.calculations import (  # noqa: E402
    BlastGeometry,
    PATTERN_CENTER_HOLE,
    PF_KG_PER_T,
    compute_charges,
    compute_costs,
    compute_fleet,
    get_technical_alerts,
    pf_in_unit,
    pf_status,
    target_pf_to_kg_m3,
)
from utils.plots import plot_blast_pattern, plot_hole_cross_section  # noqa: E402
from utils.report import ReportData, build_technical_report  # noqa: E402


def test_pdf_builds_with_alerts_and_markup_characters():
    geom = BlastGeometry(10, 1, 2.5, 5, 5.5, 89, 0.0, PATTERN_CENTER_HOLE)
    charges = compute_charges(geom, target_pf_to_kg_m3(0.25, PF_KG_PER_T, 2.5), 2.0)
    fleet = compute_fleet(geom, charges, 2.5, 20000)
    costs = compute_costs(fleet, charges, 20000, 28, 17.55, 46, 85, 7000)
    pf_actual = pf_in_unit(fleet.total_explosive_kg, fleet.total_rock_volume, 2.5, PF_KG_PER_T)
    alerts = get_technical_alerts(geom, charges)
    assert any("<" in a for a in alerts)  # must be escaped in the PDF
    data = ReportData(
        site_name="Site", geology_type="Calcaire", rock_hardness="Moyenne",
        quality_note="Standard.", clay_risk="NUL", density=2.5, target_tons=20000,
        pattern_label="Grille + trou central", geom=geom, charges=charges, fleet=fleet,
        costs=costs, pf_target=0.25, pf_actual=pf_actual, pf_unit=PF_KG_PER_T,
        pf_state=pf_status(pf_actual, 0.25), cost_drill_per_m=28,
        cost_ammonix_per_kg=17.55, cost_emulsion_per_kg=46, cost_detonator_each=85,
        fig_plan=plot_blast_pattern(fleet.num_holes, 5, 5.5, PATTERN_CENTER_HOLE),
        fig_hole=plot_hole_cross_section(geom, charges), alerts=alerts,
    )
    pdf = build_technical_report(data).getvalue()
    assert pdf.startswith(b"%PDF")
