"""
utils/report.py
---------------
PDF technical report (ReportLab).  No Streamlit imports: the report can be
built and tested from plain calculation results and matplotlib figures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from utils.calculations import BlastCharges, BlastFleet, BlastGeometry, CostBreakdown

PAGE_MARGIN = 2 * cm
CONTENT_WIDTH = A4[0] - 2 * PAGE_MARGIN          # 17 cm
CONTENT_HEIGHT = A4[1] - 2 * PAGE_MARGIN         # 25.7 cm

_PF_STATE_LABELS = {"ok": "conforme", "low": "inférieure à la cible", "high": "supérieure à la cible"}


@dataclass
class ReportData:
    """Everything the PDF needs, already computed by the calculation layer."""
    site_name: str
    geology_type: str
    rock_hardness: str
    quality_note: str
    clay_risk: str
    density: float                 # t/m³
    target_tons: float             # t
    pattern_label: str
    geom: BlastGeometry
    charges: BlastCharges
    fleet: BlastFleet
    costs: CostBreakdown
    pf_target: float
    pf_actual: float
    pf_unit: str
    pf_state: str
    cost_drill_per_m: float
    cost_ammonix_per_kg: float
    cost_emulsion_per_kg: float
    cost_detonator_each: float
    fig_plan: plt.Figure
    fig_hole: plt.Figure
    alerts: list[str] = field(default_factory=list)
    date: datetime = field(default_factory=datetime.now)


def _fig_to_image(fig: plt.Figure, max_w: float, max_h: float, dpi: int = 150) -> Image:
    """Render a figure as a ReportLab Image scaled to fit max_w x max_h, keeping its aspect ratio."""
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    px_w, px_h = ImageReader(buf).getSize()
    buf.seek(0)
    scale = min(max_w / px_w, max_h / px_h)
    return Image(buf, width=px_w * scale, height=px_h * scale)


def _pct(part: float, total: float) -> str:
    return f"{part / total * 100:.1f}%" if total > 0 else "—"


def build_technical_report(d: ReportData) -> BytesIO:
    """Build and return a BytesIO buffer containing the full PDF technical report."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=PAGE_MARGIN, leftMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN, bottomMargin=PAGE_MARGIN,
        title="Rapport Technique de Tir", author="SGT",
    )
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("CellText", parent=styles["Normal"], fontSize=9, leading=11)
    head = ParagraphStyle(
        "CellHead", parent=cell, fontName="Helvetica-Bold", textColor=colors.white,
    )
    head_dark = ParagraphStyle("CellHeadDark", parent=head, textColor=colors.black)
    alert_style = ParagraphStyle(
        "Alert", parent=cell, textColor=colors.HexColor("#a71d2a"), leftIndent=6,
    )

    def P(text: str, style: ParagraphStyle = cell) -> Paragraph:
        return Paragraph(text, style)

    def E(text: str) -> str:
        return escape(str(text))

    base_style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]

    geom, charges, fleet, costs = d.geom, d.charges, d.fleet, d.costs
    unit = E(d.pf_unit)
    elements: list = []

    # ── Header ──────────────────────────────────────────────────────────────
    elements.append(Paragraph("RAPPORT TECHNIQUE DE TIR", styles["Title"]))
    elements.append(P(
        f"<b>Site :</b> {E(d.site_name)} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Date :</b> {d.date.strftime('%d/%m/%Y')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Ref :</b> BL-{d.date.strftime('%Y%m%d')} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Faciès :</b> {E(d.geology_type)}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 0.5 * cm))

    # ── Section 1: Technical Summary ────────────────────────────────────────
    pf_note = f"Réel {d.pf_actual:.3f} {unit} — {_PF_STATE_LABELS.get(d.pf_state, d.pf_state)}"
    data_synth = [
        [P("PARAMÈTRE", head), P("VALEUR", head), P("NOTES TECHNIQUES", head)],
        [P("Objectif Tonnage"), P(f"{d.target_tons:,.0f} t"),
         P(f"Abattu : {fleet.total_tonnage:,.0f} t — densité {d.density:.2f} t/m³")],
        [P("Maille (B × S)"), P(f"{geom.burden:.2f} m × {geom.spacing:.2f} m"),
         P(E(d.pattern_label))],
        [P("Surface / Volume par trou"),
         P(f"{geom.area_per_hole:.2f} m² — {geom.rock_volume_per_hole:.1f} m³"),
         P(f"{geom.rock_volume_per_hole * d.density:.1f} t/trou")],
        [P("Trou de tir"),
         P(f"Ø {geom.hole_diameter} mm — profondeur {geom.hole_depth:.1f} m"),
         P(f"H = {geom.bench_height:.1f} m, J = {geom.sub_drill:.1f} m, "
           f"bourrage min. {geom.stemming_m:.1f} m, tampon {geom.safety_gap:.1f} m")],
        [P("Charge Spécifique"), P(f"Cible {d.pf_target:.3f} {unit}"), P(pf_note)],
        [P("Foration Totale"), P(f"{fleet.total_drill_meters:,.0f} m"),
         P(f"{fleet.num_holes} trous × {geom.hole_depth:.1f} m")],
        [P("Qualité Attendue"), P(E(d.quality_note)),
         P(f"Dureté : {E(d.rock_hardness)} — Risque argile : {E(d.clay_risk)}")],
    ]
    t_synth = Table(data_synth, colWidths=[4 * cm, 6 * cm, 7 * cm])
    t_synth.setStyle(TableStyle(base_style + [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#004085")),
    ]))
    elements.append(Paragraph("<b>SYNTHÈSE TECHNIQUE</b>", styles["Heading3"]))
    elements.append(t_synth)

    # ── Alerts ───────────────────────────────────────────────────────────────
    if d.alerts or d.pf_state != "ok":
        alert_lines = [P(f"• {E(a)}", alert_style) for a in d.alerts]
        if d.pf_state != "ok":
            alert_lines.append(P(
                f"• Charge spécifique réelle ({d.pf_actual:.3f} {unit}) "
                f"{_PF_STATE_LABELS[d.pf_state]} ({d.pf_target:.3f} {unit}).",
                alert_style,
            ))
        elements.append(KeepTogether(
            [Paragraph("<b>ALERTES TECHNIQUES</b>", styles["Heading3"])] + alert_lines
        ))

    # ── Section 2: Explosive Quantities Detail ───────────────────────────────
    data_expl = [
        [P("EXPLOSIF", head), P("QUANTITÉ / TROU", head), P("QUANTITÉ TOTALE", head),
         P("COÛT UNITAIRE", head), P("COÛT TOTAL (HT)", head)],
        [P("<b>Ammonix (ANFO)</b>"), P(f"{charges.ammonix_per_hole:.2f} kg"),
         P(f"<b>{fleet.total_ammonix_kg:,.1f} kg</b>"),
         P(f"{d.cost_ammonix_per_kg:.2f} DH/kg"), P(f"{costs.cost_ammonix_total:,.0f} DH")],
        [P("<b>Émulsion (Booster)</b>"), P(f"{charges.emulsion_per_hole:.2f} kg"),
         P(f"<b>{fleet.total_emulsion_kg:,.1f} kg</b>"),
         P(f"{d.cost_emulsion_per_kg:.2f} DH/kg"), P(f"{costs.cost_emulsion_total:,.0f} DH")],
        [P("<b>TOTAL EXPLOSIFS</b>"), P(f"<b>{charges.total_explosive_per_hole:.2f} kg</b>"),
         P(f"<b>{fleet.total_explosive_kg:,.1f} kg</b>"), P(""),
         P(f"<b>{costs.cost_ammonix_total + costs.cost_emulsion_total:,.0f} DH</b>")],
    ]
    t_expl = Table(data_expl, colWidths=[4 * cm, 3.25 * cm, 3.25 * cm, 3.25 * cm, 3.25 * cm])
    t_expl.setStyle(TableStyle(base_style + [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17375e")),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#dce6f1")),
    ]))
    expl_block = [Paragraph("<b>DÉTAIL DES QUANTITÉS D'EXPLOSIFS</b>", styles["Heading3"]), t_expl]
    if charges.capacity_limited:
        expl_block.append(P(
            f"<i>Charge limitée par la capacité du trou : besoin "
            f"{charges.ammonix_required:.1f} kg d'Ammonix/trou, capacité "
            f"{charges.ammonix_capacity:.1f} kg/trou.</i>"
        ))
    elements.append(KeepTogether(expl_block))

    # ── Section 3: Blast Pattern Diagram ─────────────────────────────────────
    elements.append(KeepTogether([
        Paragraph("<b>PLAN DE TIR (VUE EN PLAN)</b>", styles["Heading3"]),
        _fig_to_image(d.fig_plan, CONTENT_WIDTH, 9.5 * cm),
    ]))

    # ── Section 4: Hole Cross-Section + loading sheet ────────────────────────
    hole_img = _fig_to_image(d.fig_hole, 8.5 * cm, 13 * cm)
    stemming_eff = geom.hole_depth - geom.safety_gap - (
        geom.emulsion_length(charges.emulsion_per_hole)
        + geom.ammonix_length(charges.ammonix_per_hole)
    )
    loading = [
        [P("CHARGEMENT / TROU", head), P("VALEUR", head)],
        [P("Profondeur forée"), P(f"{geom.hole_depth:.1f} m")],
        [P("Bourrage effectif"), P(f"{max(0.0, stemming_eff):.1f} m (min. {geom.stemming_m:.1f} m)")],
        [P("Tampon / air deck"), P(f"{geom.safety_gap:.1f} m")],
        [P("Colonne Ammonix"),
         P(f"{geom.ammonix_length(charges.ammonix_per_hole):.1f} m — {charges.ammonix_per_hole:.1f} kg")],
        [P("Émulsion (fond)"),
         P(f"{geom.emulsion_length(charges.emulsion_per_hole):.2f} m — {charges.emulsion_per_hole:.1f} kg")],
        [P("Charge linéaire Ammonix"), P(f"{geom.linear_charge_density:.2f} kg/m")],
        [P("Capacité Ammonix"), P(f"{charges.ammonix_capacity:.1f} kg")],
        [P("<b>Charge totale</b>"), P(f"<b>{charges.total_explosive_per_hole:.1f} kg</b>")],
    ]
    t_loading = Table(loading, colWidths=[4 * cm, 4.2 * cm])
    t_loading.setStyle(TableStyle(base_style + [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17375e")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#dce6f1")),
    ]))
    side = Table([[hole_img, t_loading]], colWidths=[CONTENT_WIDTH - 8.3 * cm, 8.3 * cm])
    side.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(KeepTogether([
        Paragraph("<b>COUPE TRANSVERSALE DU TROU DE TIR</b>", styles["Heading3"]),
        side,
    ]))

    # ── Section 5: Budget Estimate ────────────────────────────────────────────
    total = costs.total_cost_ht
    data_cost = [
        [P("POSTE DE DÉPENSE", head_dark), P("DÉTAIL QUANTITÉ", head_dark),
         P("MONTANT (HT)", head_dark), P("% DU TOTAL", head_dark)],
        [P("Foration"),
         P(f"{fleet.total_drill_meters:,.0f} m @ {d.cost_drill_per_m:.2f} DH/m"),
         P(f"{costs.cost_drilling:,.0f} DH"), P(_pct(costs.cost_drilling, total))],
        [P("Ammonix (ANFO)"),
         P(f"{fleet.total_ammonix_kg:,.1f} kg @ {d.cost_ammonix_per_kg:.2f} DH/kg"),
         P(f"{costs.cost_ammonix_total:,.0f} DH"), P(_pct(costs.cost_ammonix_total, total))],
        [P("Émulsion (Booster)"),
         P(f"{fleet.total_emulsion_kg:,.1f} kg @ {d.cost_emulsion_per_kg:.2f} DH/kg"),
         P(f"{costs.cost_emulsion_total:,.0f} DH"), P(_pct(costs.cost_emulsion_total, total))],
        [P("Accessoires (détonateurs)"),
         P(f"{fleet.num_holes} × {d.cost_detonator_each:.2f} DH"),
         P(f"{costs.cost_accessories:,.0f} DH"), P(_pct(costs.cost_accessories, total))],
        [P("Frais fixes"), P("Forfait"),
         P(f"{costs.fixed_fees:,.0f} DH"), P(_pct(costs.fixed_fees, total))],
        [P("<b>TOTAL HT</b>"), P(""), P(f"<b>{total:,.0f} DH</b>"), P("100%")],
        [P("<b>TOTAL TTC (TVA 20%)</b>"), P(""), P(f"<b>{costs.total_cost_ttc:,.0f} DH</b>"), P("—")],
        [P("<b>COÛT UNITAIRE (HT)</b>"), P(f"sur {fleet.total_tonnage:,.0f} t abattues"),
         P(f"<b>{costs.cost_per_ton:.2f} DH/t</b>"), P("—")],
    ]
    t_cost = Table(data_cost, colWidths=[4.5 * cm, 5.5 * cm, 3.5 * cm, 3.5 * cm])
    t_cost.setStyle(TableStyle(base_style + [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9ecef")),
        ("BACKGROUND", (0, 6), (-1, 8), colors.HexColor("#d4edda")),
    ]))
    elements.append(KeepTogether([
        Paragraph("<b>ESTIMATION BUDGÉTAIRE PRÉVISIONNELLE</b>", styles["Heading3"]),
        t_cost,
    ]))

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 0.6 * cm))
    if d.alerts or d.pf_state != "ok":
        footer = ("<i>Document généré automatiquement par le système SGT. "
                  "Des alertes techniques sont présentes : plan à revoir avant exécution.</i>")
    else:
        footer = "<i>Document généré automatiquement par le système SGT. Validé pour exécution.</i>"
    elements.append(Paragraph(footer, styles["Italic"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer
