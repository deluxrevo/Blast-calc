"""
app.py
------
SGT — Système de Gestion de Tir
Carrière Benslimane — Professional Blast Planning & Reporting Tool

Entry point for the Streamlit application.  All mathematical logic lives in
utils/calculations.py, all chart code in utils/plots.py, and geology data in
utils/config.py.  This file is responsible only for the UI layer.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

from utils.config import (
    GEOLOGY_PROFILES,
    APP_TITLE,
    APP_SUBTITLE,
    SITE_NAME,
    DEFAULT_EMULSION_KG,
    DEFAULT_SAFETY_GAP_M,
)
from utils.calculations import (
    BlastGeometry,
    compute_charges,
    compute_fleet,
    compute_costs,
    get_technical_alerts,
)
from utils.plots import plot_blast_pattern, plot_hole_cross_section

# ---------------------------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    page_icon="⚒️",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False


def check_password() -> bool:
    """Display PIN login screen and return True when authenticated."""

    def _on_password_entered() -> None:
        if st.session_state["password"] == "1999":
            st.session_state.authenticated = True
            del st.session_state["password"]
        else:
            st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown(
            "<style>.stTextInput > div > div > input "
            "{text-align: center; font-size: 20px;}</style>",
            unsafe_allow_html=True,
        )
        st.header("🔒 Accès Restreint")
        st.write("Veuillez saisir le code PIN opérateur.")
        st.text_input(
            "Code PIN", type="password",
            on_change=_on_password_entered, key="password",
        )
        return False
    return True


if not check_password():
    st.stop()

# ---------------------------------------------------------------------------
# GLOBAL CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    h1, h2, h3 { color: #2c3e50; font-family: 'Segoe UI', sans-serif; }
    div[data-testid="stMetricValue"] { font-size: 24px; color: #004085; }
    .stButton>button {
        background-color: #004085;
        color: white;
        border-radius: 4px;
        border: none;
        height: 3em;
        font-weight: bold;
    }
    .stButton>button:hover { background-color: #0056b3; }
    .stAlert { border-radius: 4px; border-left: 5px solid #ffc107; }
    div[data-testid="stSidebar"] { background-color: #f0f4f8; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# SIDEBAR — INPUT PARAMETERS
# ---------------------------------------------------------------------------

st.sidebar.title("⚙️ Paramètres Techniques")
st.sidebar.caption(f"Site : {SITE_NAME}")

# ── 1. Geology ───────────────────────────────────────────────────────────────
st.sidebar.header("1. Caractérisation Géologique")
geology_type: str = st.sidebar.selectbox(
    "Faciès Dominant",
    list(GEOLOGY_PROFILES.keys()),
    index=0,
)
profile = GEOLOGY_PROFILES[geology_type]

rec_pf: float = profile["rec_pf"]
rec_burden: float = profile["rec_burden"]
rec_spacing: float = profile["rec_spacing"]
rock_hardness: str = profile["rock_hardness"]
abrasivity: str = profile["abrasivity"]
density_val: float = profile["density"]
quality_note: str = profile["quality_note"]
clay_risk: str = profile["clay_risk"]

st.sidebar.info(
    f"**Dureté :** {rock_hardness}  \n"
    f"**Densité :** {density_val} t/m³  \n"
    f"**Abrasivité :** {abrasivity}  \n"
    f"**Risque Argile :** {clay_risk}"
)

# ── 2. Production target ─────────────────────────────────────────────────────
st.sidebar.header("2. Objectifs de Production")
target_tons: float = st.sidebar.number_input(
    "Cible Tonnage (T)", min_value=1000, value=20000, step=500,
)

# ── 3. Blast geometry ────────────────────────────────────────────────────────
st.sidebar.header("3. Géométrie de Foration")
st.sidebar.caption(f"Recommandation : {rec_burden} m × {rec_spacing} m")
burden: float = st.sidebar.number_input(
    "Banquette (B) [m]", min_value=1.5, max_value=6.0, value=rec_burden, step=0.1,
)
spacing: float = st.sidebar.number_input(
    "Espacement (S) [m]", min_value=1.5, max_value=7.0, value=rec_spacing, step=0.1,
)
bench_height: float = st.sidebar.slider("Hauteur de Gradin (H) [m]", 6.0, 15.0, 10.0)
hole_diameter: int = st.sidebar.selectbox("Diamètre Foration [mm]", [76, 89, 102], index=1)

# ── 4. Charge design ─────────────────────────────────────────────────────────
st.sidebar.header("4. Plan de Chargement")
pf_target: float = st.sidebar.number_input(
    "Charge Spécifique (q) [kg/m³]", 0.15, 1.2, rec_pf, 0.01,
)
sub_drill: float = st.sidebar.number_input("Surforation (J) [m]", 0.0, 2.0, 1.0, 0.1)
stemming_m: float = st.sidebar.number_input("Bourrage (T) [m]", 1.0, 5.0, 2.5, 0.1)

emulsion_per_hole: float = st.sidebar.slider(
    "Émulsion par trou (kg)",
    min_value=1.0, max_value=10.0,
    value=DEFAULT_EMULSION_KG, step=0.5,
    help="Charge d'amorçage (booster) au fond du trou. Recommandé : 2 cartouches = 2 kg.",
)

safety_gap: float = st.sidebar.slider(
    "Air Deck / Tampon (m)",
    min_value=0.0, max_value=2.0,
    value=DEFAULT_SAFETY_GAP_M, step=0.1,
    help=(
        "Espace libre entre le bourrage et la colonne d'explosif. "
        "0.0 m = explosif directement contre le bourrage (pratique terrain standard)."
    ),
)

# ── 5. Economics ─────────────────────────────────────────────────────────────
with st.sidebar.expander("💰 Paramètres Économiques (Coûts)"):
    default_drill_cost = 35.0 if abrasivity == "Élevée (Usure foration)" else 28.0
    cost_drill_per_m: float = st.number_input("Foration (DH/m)", value=default_drill_cost)
    cost_ammonix_per_kg: float = st.number_input("Ammonix (DH/kg)", value=17.55)
    cost_emulsion_per_kg: float = st.number_input("Émulsion (DH/kg)", value=46.00)
    cost_detonator_each: float = st.number_input("Accessoires (Unité)", value=85.00)
    fixed_fees: float = st.number_input("Frais Fixes (DH)", value=7000.0)

# ---------------------------------------------------------------------------
# CALCULATION ENGINE
# ---------------------------------------------------------------------------

geom = BlastGeometry(
    bench_height=bench_height,
    sub_drill=sub_drill,
    stemming_m=stemming_m,
    burden=burden,
    spacing=spacing,
    hole_diameter=hole_diameter,
    safety_gap=safety_gap,
)

charges = compute_charges(geom, pf_target, emulsion_per_hole)
fleet = compute_fleet(geom, charges, density_val, target_tons)
costs = compute_costs(
    fleet=fleet,
    charges=charges,
    target_tons=target_tons,
    cost_drill_per_m=cost_drill_per_m,
    cost_ammonix_per_kg=cost_ammonix_per_kg,
    cost_emulsion_per_kg=cost_emulsion_per_kg,
    cost_detonator_each=cost_detonator_each,
    fixed_fees=fixed_fees,
)
alerts = get_technical_alerts(geom, charges)

# ---------------------------------------------------------------------------
# DIAGRAMS (generated once, reused in tabs and PDF)
# ---------------------------------------------------------------------------

fig_plan = plot_blast_pattern(fleet.num_holes, burden, spacing)
fig_hole = plot_hole_cross_section(geom, charges)

# ---------------------------------------------------------------------------
# PDF REPORT GENERATION
# ---------------------------------------------------------------------------


def generate_technical_report() -> BytesIO:
    """Build and return a BytesIO buffer containing the full PDF technical report."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2 * cm, leftMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
    )
    elements = []
    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle(
        "CellText", parent=styles["Normal"], fontSize=9, leading=11, wordWrap="CJK",
    )

    # ── Header ──────────────────────────────────────────────────────────────
    elements.append(Paragraph("RAPPORT TECHNIQUE DE TIR", styles["Title"]))
    elements.append(Paragraph(
        f"<b>Site :</b> {SITE_NAME} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Date :</b> {pd.Timestamp.now().strftime('%d/%m/%Y')}",
        styles["Normal"],
    ))
    elements.append(Paragraph(
        f"<b>Opérateur :</b> Admin &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Ref :</b> BL-{pd.Timestamp.now().strftime('%Y%m%d')}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 1 * cm))

    # ── Section 1: Technical Summary ────────────────────────────────────────
    elements.append(Paragraph("<b>SYNTHÈSE TECHNIQUE</b>", styles["Heading3"]))
    data_synth = [
        ["PARAMÈTRE", "VALEUR", "NOTES TECHNIQUE"],
        ["Objectif Tonnage",
         Paragraph(f"{target_tons:,.0f} T", cell_style),
         Paragraph(f"Densité retenue : {density_val} t/m³", cell_style)],
        ["Géométrie (B × S)",
         Paragraph(f"{burden} m × {spacing} m", cell_style),
         Paragraph(f"Maille : {burden * spacing:.1f} m²", cell_style)],
        ["Charge Spécifique",
         Paragraph(f"{pf_target:.2f} kg/m³", cell_style),
         Paragraph(f"Dureté : {rock_hardness}", cell_style)],
        ["Foration Totale",
         Paragraph(f"{fleet.total_drill_meters:,.0f} m", cell_style),
         Paragraph(f"{fleet.num_holes} Trous (Ø {hole_diameter} mm)", cell_style)],
        ["Qualité Attendue",
         Paragraph(quality_note, cell_style),
         Paragraph(f"Risque Argile : {clay_risk}", cell_style)],
    ]
    t_synth = Table(data_synth, colWidths=[4 * cm, 7 * cm, 6 * cm])
    t_synth.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#004085"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_synth)
    elements.append(Spacer(1, 1 * cm))

    # ── Section 2: Explosive Quantities Detail ───────────────────────────────
    elements.append(Paragraph("<b>DÉTAIL DES QUANTITÉS D'EXPLOSIFS</b>", styles["Heading3"]))
    data_expl = [
        ["EXPLOSIF", "QUANTITÉ / TROU", "QUANTITÉ TOTALE", "COÛT UNITAIRE", "COÛT TOTAL (HT)"],
        [
            Paragraph("<b>Ammonix (ANFO)</b>", cell_style),
            Paragraph(f"{charges.ammonix_per_hole:.2f} kg/trou", cell_style),
            Paragraph(f"<b>{fleet.total_ammonix_kg:,.1f} kg</b>", cell_style),
            Paragraph(f"{cost_ammonix_per_kg:.2f} DH/kg", cell_style),
            Paragraph(f"{costs.cost_ammonix_total:,.0f} DH", cell_style),
        ],
        [
            Paragraph("<b>Émulsion (Booster)</b>", cell_style),
            Paragraph(f"{charges.emulsion_per_hole:.2f} kg/trou", cell_style),
            Paragraph(f"<b>{fleet.total_emulsion_kg:,.1f} kg</b>", cell_style),
            Paragraph(f"{cost_emulsion_per_kg:.2f} DH/kg", cell_style),
            Paragraph(f"{costs.cost_emulsion_total:,.0f} DH", cell_style),
        ],
        [
            Paragraph("<b>TOTAL EXPLOSIFS</b>", cell_style),
            Paragraph(f"{charges.total_explosive_per_hole:.2f} kg/trou", cell_style),
            Paragraph(f"<b>{fleet.total_explosive_kg:,.1f} kg</b>", cell_style),
            "",
            Paragraph(
                f"<b>{costs.cost_ammonix_total + costs.cost_emulsion_total:,.0f} DH</b>",
                cell_style,
            ),
        ],
    ]
    t_expl = Table(data_expl, colWidths=[4 * cm, 3.5 * cm, 3.5 * cm, 3 * cm, 3 * cm])
    t_expl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#17375e"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("BACKGROUND", (0, 3), (-1, 3), "#dce6f1"),
    ]))
    elements.append(t_expl)
    elements.append(Spacer(1, 1 * cm))

    # ── Section 3: Blast Pattern Diagram ─────────────────────────────────────
    img_buf = BytesIO()
    fig_plan.savefig(img_buf, format="png", dpi=100, bbox_inches="tight")
    img_buf.seek(0)
    elements.append(Image(img_buf, width=14 * cm, height=10 * cm))
    elements.append(Spacer(1, 1 * cm))

    # ── Section 4: Hole Cross-Section ────────────────────────────────────────
    elements.append(Paragraph("<b>COUPE TRANSVERSALE DU TROU DE TIR</b>", styles["Heading3"]))
    hole_img_buf = BytesIO()
    fig_hole.savefig(hole_img_buf, format="png", dpi=120, bbox_inches="tight")
    hole_img_buf.seek(0)
    elements.append(Image(hole_img_buf, width=8 * cm, height=16 * cm))
    elements.append(Spacer(1, 1 * cm))

    # ── Section 5: Budget Estimate ────────────────────────────────────────────
    elements.append(Paragraph("<b>ESTIMATION BUDGÉTAIRE PRÉVISIONNELLE</b>", styles["Heading3"]))
    data_cost = [
        ["POSTE DE DÉPENSE", "DÉTAIL QUANTITÉ", "MONTANT (HT)", "% DU TOTAL"],
        [
            "Foration",
            Paragraph(
                f"{fleet.total_drill_meters:,.0f} m @ {cost_drill_per_m:.0f} DH/m",
                cell_style,
            ),
            Paragraph(f"{costs.cost_drilling:,.0f} DH", cell_style),
            f"{costs.cost_drilling / costs.total_cost_ht * 100:.1f}%",
        ],
        [
            Paragraph("<b>Ammonix (ANFO)</b>", cell_style),
            Paragraph(
                f"{fleet.total_ammonix_kg:,.1f} kg @ {cost_ammonix_per_kg:.2f} DH/kg",
                cell_style,
            ),
            Paragraph(f"{costs.cost_ammonix_total:,.0f} DH", cell_style),
            f"{costs.cost_ammonix_total / costs.total_cost_ht * 100:.1f}%",
        ],
        [
            Paragraph("<b>Émulsion (Booster)</b>", cell_style),
            Paragraph(
                f"{fleet.total_emulsion_kg:,.1f} kg @ {cost_emulsion_per_kg:.2f} DH/kg",
                cell_style,
            ),
            Paragraph(f"{costs.cost_emulsion_total:,.0f} DH", cell_style),
            f"{costs.cost_emulsion_total / costs.total_cost_ht * 100:.1f}%",
        ],
        [
            "Accessoires & Frais Fixes",
            Paragraph(f"{fleet.num_holes} détonateurs + fixes", cell_style),
            Paragraph(f"{costs.cost_accessories + costs.fixed_fees:,.0f} DH", cell_style),
            f"{(costs.cost_accessories + costs.fixed_fees) / costs.total_cost_ht * 100:.1f}%",
        ],
        [
            Paragraph("<b>TOTAL HT</b>", cell_style),
            "",
            Paragraph(f"<b>{costs.total_cost_ht:,.0f} DH</b>", cell_style),
            "100%",
        ],
        [
            "COÛT UNITAIRE",
            "",
            Paragraph(f"{costs.cost_per_ton:.2f} DH/T", cell_style),
            "—",
        ],
    ]
    t_cost = Table(data_cost, colWidths=[4.5 * cm, 5.5 * cm, 3.5 * cm, 3.5 * cm])
    t_cost.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), "#e9ecef"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 5), (-1, 6), "#d4edda"),
    ]))
    elements.append(t_cost)

    # ── Footer ────────────────────────────────────────────────────────────────
    elements.append(Spacer(1, 1 * cm))
    elements.append(Paragraph(
        "<i>Document généré automatiquement par le système SGT. Validé pour exécution.</i>",
        styles["Italic"],
    ))

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# MAIN DASHBOARD
# ---------------------------------------------------------------------------

st.title(f"⚒️ {APP_TITLE}")
st.markdown(f"### {APP_SUBTITLE}")
st.caption(f"Site : {SITE_NAME}  |  Faciès : **{geology_type}**  |  Ø {hole_diameter} mm")

st.markdown("---")

# ── Top KPI metrics ──────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("🎯 Production Cible", f"{target_tons / 1000:.1f} kT")
m2.metric("📐 Maille de Tir", f"{burden} × {spacing} m")
m3.metric("💥 Charge Spécifique", f"{pf_target:.2f} kg/m³", f"Rec. {rec_pf:.2f}")
m4.metric("🕳️ Nombre de Trous", f"{fleet.num_holes}")
m5.metric("💰 Coût Unitaire", f"{costs.cost_per_ton:.2f} DH/T", delta_color="inverse")

st.markdown("---")

# ── Technical alerts ─────────────────────────────────────────────────────────
for alert in alerts:
    st.error(f"⚠️ {alert}")

# ── Content tabs ─────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📊 Analyse Technique",
    "💰 Analyse Financière",
    "📄 Rapport & Export",
])

with tab1:
    col_graph, col_data = st.columns([2, 1])

    with col_graph:
        st.subheader("Plan de Tir (Vue en Plan)")
        st.pyplot(fig_plan)
        st.info(f"**Qualité attendue ({geology_type}) :** {quality_note}")

    with col_data:
        st.subheader("Coupe du Trou de Tir")
        st.pyplot(fig_hole)

    st.markdown("---")
    st.subheader("Récapitulatif des Quantités d'Explosifs")

    exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)
    exp_col1.metric(
        "Ammonix (ANFO) / Trou",
        f"{charges.ammonix_per_hole:.2f} kg",
        f"Total : {fleet.total_ammonix_kg:,.0f} kg",
    )
    exp_col2.metric(
        "Émulsion (Booster) / Trou",
        f"{charges.emulsion_per_hole:.2f} kg",
        f"Total : {fleet.total_emulsion_kg:,.0f} kg",
    )
    exp_col3.metric(
        "Charge Totale / Trou",
        f"{charges.total_explosive_per_hole:.2f} kg",
        f"Total : {fleet.total_explosive_kg:,.0f} kg",
    )
    exp_col4.metric(
        "Foration Totale",
        f"{fleet.total_drill_meters:,.0f} m",
        f"{fleet.num_holes} trous × {geom.hole_depth:.1f} m",
    )

    st.markdown("---")
    df_explosives = pd.DataFrame({
        "Explosif": ["Ammonix (ANFO)", "Émulsion (Booster)", "TOTAL"],
        "kg / Trou": [
            charges.ammonix_per_hole,
            charges.emulsion_per_hole,
            charges.total_explosive_per_hole,
        ],
        "Total (kg)": [fleet.total_ammonix_kg, fleet.total_emulsion_kg, fleet.total_explosive_kg],
        "Coût (DH)": [
            costs.cost_ammonix_total,
            costs.cost_emulsion_total,
            costs.cost_ammonix_total + costs.cost_emulsion_total,
        ],
    })
    st.dataframe(
        df_explosives.style.format({
            "kg / Trou": "{:.2f}",
            "Total (kg)": "{:,.1f}",
            "Coût (DH)": "{:,.0f}",
        }),
        hide_index=True,
        use_container_width=True,
    )

with tab2:
    st.subheader("Ventilation des Coûts de Tir")

    fin_col1, fin_col2, fin_col3 = st.columns(3)
    fin_col1.metric("💵 Total HT", f"{costs.total_cost_ht:,.0f} DH")
    fin_col2.metric("🧾 Total TTC (TVA 20%)", f"{costs.total_cost_ttc:,.0f} DH")
    fin_col3.metric("📦 Coût / Tonne", f"{costs.cost_per_ton:.2f} DH/T")

    st.markdown("---")
    df_costs = pd.DataFrame({
        "Poste de Dépense": ["Foration", "Ammonix (ANFO)", "Émulsion (Booster)",
                             "Accessoires (Détonateurs)", "Frais Fixes"],
        "Montant (DH)": [
            costs.cost_drilling,
            costs.cost_ammonix_total,
            costs.cost_emulsion_total,
            costs.cost_accessories,
            costs.fixed_fees,
        ],
        "Part (%)": [
            costs.cost_drilling / costs.total_cost_ht * 100,
            costs.cost_ammonix_total / costs.total_cost_ht * 100,
            costs.cost_emulsion_total / costs.total_cost_ht * 100,
            costs.cost_accessories / costs.total_cost_ht * 100,
            costs.fixed_fees / costs.total_cost_ht * 100,
        ],
    })
    st.dataframe(
        df_costs.style.format({"Montant (DH)": "{:,.0f}", "Part (%)": "{:.1f}%"}),
        hide_index=True,
        use_container_width=True,
    )

with tab3:
    st.subheader("Génération de Rapport Technique PDF")
    st.write(
        "Ce module génère un rapport PDF standardisé incluant le plan de tir, "
        "la coupe du trou, le bilan explosifs et l'estimation budgétaire."
    )

    recap_col1, recap_col2, recap_col3 = st.columns(3)
    recap_col1.metric(
        "Ammonix (ANFO)", f"{fleet.total_ammonix_kg:,.1f} kg",
        f"{charges.ammonix_per_hole:.2f} kg/trou",
    )
    recap_col2.metric(
        "Émulsion (Booster)", f"{fleet.total_emulsion_kg:,.1f} kg",
        f"{charges.emulsion_per_hole:.2f} kg/trou",
    )
    recap_col3.metric(
        "Total Explosifs", f"{fleet.total_explosive_kg:,.1f} kg",
        f"{charges.total_explosive_per_hole:.2f} kg/trou",
    )

    st.markdown("---")

    if st.button("📋 Générer le Rapport Technique (PDF)"):
        pdf_file = generate_technical_report()
        st.download_button(
            label="⬇️ Télécharger le Rapport Officiel",
            data=pdf_file,
            file_name=f"Rapport_Tir_BL_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
        )
