"""
SGT - Système de Gestion de Tir (Blast Management System)
Carrière Benslimane — Technical Blast Planning & Reporting Tool
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SGT - Système de Gestion de Tir",
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
            "<style>.stTextInput > div > div > input {text-align: center; font-size: 20px;}</style>",
            unsafe_allow_html=True,
        )
        st.header("🔒 Accès Restreint")
        st.write("Veuillez saisir le code PIN opérateur.")
        st.text_input("Code PIN", type="password", on_change=_on_password_entered, key="password")
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
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# GEOLOGY PROFILES
# ---------------------------------------------------------------------------

GEOLOGY_PROFILES: dict[str, dict[str, str | float]] = {
    "Gréso-Pélitique (Viséen)": {
        "rec_pf": 0.55,
        "rec_burden": 3.5,
        "rec_spacing": 4.0,
        "rock_hardness": "Moyenne/Dure",
        "abrasivity": "Moyenne",
        "density": 2.70,
        "quality_note": "Risque de fines argileuses (Scalpage requis).",
        "clay_risk": "MODÉRÉ",
    },
    "Psammites (Ordovicien)": {
        "rec_pf": 0.65,
        "rec_burden": 3.2,
        "rec_spacing": 3.8,
        "rock_hardness": "TRÈS DURE",
        "abrasivity": "Élevée (Usure foration)",
        "density": 2.75,
        "quality_note": "Excellent granulat (Béton HP).",
        "clay_risk": "FAIBLE",
    },
    "Calcaire Franc": {
        "rec_pf": 0.45,
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
        "rec_burden": 3.5,
        "rec_spacing": 4.0,
        "rock_hardness": "Faible",
        "abrasivity": "Faible",
        "density": 2.50,
        "quality_note": "Matériau stérile probable.",
        "clay_risk": "ÉLEVÉ",
    },
}

# ---------------------------------------------------------------------------
# SIDEBAR — INPUT PARAMETERS
# ---------------------------------------------------------------------------

st.sidebar.title("Paramètres Techniques")
st.sidebar.caption("Site : Carrière Benslimane")

# 1. Geology
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

st.sidebar.text(f"Densité Ref: {density_val} t/m³")

# 2. Production target
st.sidebar.header("2. Objectifs de Production")
target_tons: float = st.sidebar.number_input("Cible Tonnage (T)", min_value=1000, value=20000, step=500)

# 3. Blast geometry
st.sidebar.header("3. Géométrie de Foration")
st.sidebar.caption(f"Recommandation : {rec_burden}m x {rec_spacing}m")
burden: float = st.sidebar.number_input("Banquette (B) [m]", min_value=1.5, max_value=6.0, value=rec_burden, step=0.1)
spacing: float = st.sidebar.number_input("Espacement (S) [m]", min_value=1.5, max_value=7.0, value=rec_spacing, step=0.1)
bench_height: float = st.sidebar.slider("Hauteur de Gradin (H) [m]", 6.0, 15.0, 10.0)
hole_diameter: int = st.sidebar.selectbox("Diamètre Foration [mm]", [76, 89, 102], index=1)

# 4. Charge design
st.sidebar.header("4. Plan de Chargement")
pf_target: float = st.sidebar.number_input("Charge Spécifique (q) [kg/m³]", 0.15, 1.2, rec_pf, 0.01)
sub_drill: float = st.sidebar.number_input("Surforation (J) [m]", 0.0, 2.0, 1.0, 0.1)
stemming_m: float = st.sidebar.number_input("Bourrage (T) [m]", 1.0, 5.0, 2.5, 0.1)

# 5. Economics
with st.sidebar.expander("Paramètres Économiques (Coûts)"):
    default_drill_cost = 35.0 if abrasivity == "Élevée (Usure foration)" else 28.0
    cost_drill_per_m: float = st.number_input("Foration (DH/m)", value=default_drill_cost)
    cost_ammonix_per_kg: float = st.number_input("Ammonix (DH/kg)", value=17.55)
    cost_emulsion_per_kg: float = st.number_input("Émulsion (DH/kg)", value=46.00)
    cost_detonator_each: float = st.number_input("Accessoires (Unité)", value=85.00)
    fixed_fees: float = st.number_input("Frais Fixes (DH)", value=7000.0)

# ---------------------------------------------------------------------------
# CALCULATION ENGINE
# ---------------------------------------------------------------------------

# Hole geometry
hole_depth: float = bench_height + sub_drill
rock_volume_per_hole: float = burden * spacing * bench_height      # m³ of rock per hole
tonnage_per_hole: float = rock_volume_per_hole * density_val       # tonnes per hole

# Explosive quantities per hole
#   - Emulsion acts as a bottom-hole booster (fixed standard quantity)
#   - Ammonix (ANFO) fills the remainder of the required charge column
total_explosive_per_hole: float = rock_volume_per_hole * pf_target # kg total per hole
emulsion_per_hole: float = 5.0                                 # kg — standard booster charge
ammonix_per_hole: float = max(0.0, total_explosive_per_hole - emulsion_per_hole)

# Physical capacity check
charge_length_available: float = hole_depth - stemming_m - 0.5            # m
linear_charge_density: float = (np.pi * ((hole_diameter / 1000) / 2) ** 2) * 850  # kg/m
max_ammonix_capacity: float = charge_length_available * linear_charge_density       # kg

# Fleet totals
num_holes: int = int(np.ceil(target_tons / tonnage_per_hole))
total_drill_meters: float = num_holes * hole_depth
total_ammonix_kg: float = num_holes * ammonix_per_hole         # total Ammonix in kg
total_emulsion_kg: float = num_holes * emulsion_per_hole       # total Emulsion in kg
total_explosive_kg: float = total_ammonix_kg + total_emulsion_kg
total_rock_volume: float = num_holes * rock_volume_per_hole    # m³

# Cost breakdown
cost_drilling: float = total_drill_meters * cost_drill_per_m
cost_ammonix_total: float = total_ammonix_kg * cost_ammonix_per_kg
cost_emulsion_total: float = total_emulsion_kg * cost_emulsion_per_kg
cost_accessories: float = num_holes * cost_detonator_each
total_cost_ht: float = cost_drilling + cost_ammonix_total + cost_emulsion_total + cost_accessories + fixed_fees
total_cost_ttc: float = total_cost_ht * 1.20
cost_per_ton: float = total_cost_ht / target_tons

# ---------------------------------------------------------------------------
# TECHNICAL ALERTS
# ---------------------------------------------------------------------------

alerts: list[str] = []
if ammonix_per_hole > max_ammonix_capacity:
    alerts.append(
        f"CRITIQUE: Surcharge Explosive. Capacité trou ({max_ammonix_capacity:.1f} kg) "
        f"< Besoin ({ammonix_per_hole:.1f} kg)."
    )
if burden > spacing:
    alerts.append("GÉOMÉTRIE INCORRECTE: La Banquette (B) ne doit pas être supérieure à l'Espacement (S).")
if stemming_m < burden * 0.7:
    alerts.append("SÉCURITÉ: Bourrage insuffisant. Risque de projections.")

# ---------------------------------------------------------------------------
# BLAST PATTERN PLOT
# ---------------------------------------------------------------------------


def plot_blast_pattern(num_holes: int, burden: float, spacing: float) -> plt.Figure:
    """Generate a top-view staggered blast pattern diagram."""
    rows = int(np.ceil(np.sqrt(num_holes)))
    cols = int(np.ceil(num_holes / rows)) + 1

    x_coords: list[float] = []
    y_coords: list[float] = []
    hole_count = 0

    for r in range(rows):
        for c in range(cols):
            if hole_count >= num_holes:
                break
            x = c * spacing + (spacing / 2 if r % 2 != 0 else 0)
            y = r * burden * -1
            x_coords.append(x)
            y_coords.append(y)
            hole_count += 1

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.scatter(
        x_coords, y_coords,
        c="white", s=60, edgecolors="#004085", linewidth=2, zorder=3, label="Trou de Foration",
    )
    ax.axhline(y=burden * 0.5, color="#d9534f", linestyle="--", linewidth=2, label="Front Libre (Théorique)")
    ax.set_title(f"Plan de Tir : Maille {burden}m × {spacing}m (Quinconce)", fontsize=10, pad=10)
    ax.set_xlabel("Espacement (m)", fontsize=8)
    ax.set_ylabel("Banquette (m)", fontsize=8)
    ax.grid(True, linestyle="--", alpha=0.5, color="grey")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_aspect("equal")
    return fig


fig_plan = plot_blast_pattern(num_holes, burden, spacing)

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
    cell_style = ParagraphStyle("CellText", parent=styles["Normal"], fontSize=9, leading=11, wordWrap="CJK")

    # ── Header ──────────────────────────────────────────────────────────────
    elements.append(Paragraph("RAPPORT TECHNIQUE DE TIR", styles["Title"]))
    elements.append(Paragraph(
        f"<b>Site :</b> Carrière Benslimane &nbsp;&nbsp;|&nbsp;&nbsp; "
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
         Paragraph(f"{total_drill_meters:,.0f} m", cell_style),
         Paragraph(f"{num_holes} Trous (Ø {hole_diameter} mm)", cell_style)],
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
            Paragraph(f"{ammonix_per_hole:.2f} kg/trou", cell_style),
            Paragraph(f"<b>{total_ammonix_kg:,.1f} kg</b>", cell_style),
            Paragraph(f"{cost_ammonix_per_kg:.2f} DH/kg", cell_style),
            Paragraph(f"{cost_ammonix_total:,.0f} DH", cell_style),
        ],
        [
            Paragraph("<b>Émulsion (Booster)</b>", cell_style),
            Paragraph(f"{emulsion_per_hole:.2f} kg/trou", cell_style),
            Paragraph(f"<b>{total_emulsion_kg:,.1f} kg</b>", cell_style),
            Paragraph(f"{cost_emulsion_per_kg:.2f} DH/kg", cell_style),
            Paragraph(f"{cost_emulsion_total:,.0f} DH", cell_style),
        ],
        [
            Paragraph("<b>TOTAL EXPLOSIFS</b>", cell_style),
            Paragraph(f"{total_explosive_per_hole:.2f} kg/trou", cell_style),
            Paragraph(f"<b>{total_explosive_kg:,.1f} kg</b>", cell_style),
            "",
            Paragraph(f"<b>{cost_ammonix_total + cost_emulsion_total:,.0f} DH</b>", cell_style),
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
        ("BACKGROUND", (0, 3), (-1, 3), "#dce6f1"),  # Total row highlight
    ]))
    elements.append(t_expl)
    elements.append(Spacer(1, 1 * cm))

    # ── Section 3: Blast Pattern Diagram ────────────────────────────────────
    img_buf = BytesIO()
    fig_plan.savefig(img_buf, format="png", dpi=100, bbox_inches="tight")
    img_buf.seek(0)
    elements.append(Image(img_buf, width=14 * cm, height=10 * cm))
    elements.append(Spacer(1, 1 * cm))

    # ── Section 4: Budget Estimate ───────────────────────────────────────────
    elements.append(Paragraph("<b>ESTIMATION BUDGÉTAIRE PRÉVISIONNELLE</b>", styles["Heading3"]))
    data_cost = [
        ["POSTE DE DÉPENSE", "DÉTAIL QUANTITÉ", "MONTANT (HT)", "% DU TOTAL"],
        [
            "Foration",
            Paragraph(f"{total_drill_meters:,.0f} m @ {cost_drill_per_m:.0f} DH/m", cell_style),
            Paragraph(f"{cost_drilling:,.0f} DH", cell_style),
            f"{cost_drilling / total_cost_ht * 100:.1f}%",
        ],
        [
            Paragraph("<b>Ammonix (ANFO)</b>", cell_style),
            Paragraph(f"{total_ammonix_kg:,.1f} kg @ {cost_ammonix_per_kg:.2f} DH/kg", cell_style),
            Paragraph(f"{cost_ammonix_total:,.0f} DH", cell_style),
            f"{cost_ammonix_total / total_cost_ht * 100:.1f}%",
        ],
        [
            Paragraph("<b>Émulsion (Booster)</b>", cell_style),
            Paragraph(f"{total_emulsion_kg:,.1f} kg @ {cost_emulsion_per_kg:.2f} DH/kg", cell_style),
            Paragraph(f"{cost_emulsion_total:,.0f} DH", cell_style),
            f"{cost_emulsion_total / total_cost_ht * 100:.1f}%",
        ],
        [
            "Accessoires & Frais Fixes",
            Paragraph(f"{num_holes} détonateurs + fixes", cell_style),
            Paragraph(f"{cost_accessories + fixed_fees:,.0f} DH", cell_style),
            f"{(cost_accessories + fixed_fees) / total_cost_ht * 100:.1f}%",
        ],
        [
            Paragraph("<b>TOTAL HT</b>", cell_style),
            "",
            Paragraph(f"<b>{total_cost_ht:,.0f} DH</b>", cell_style),
            "100%",
        ],
        [
            "COÛT UNITAIRE",
            "",
            Paragraph(f"{cost_per_ton:.2f} DH/T", cell_style),
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
        ("BACKGROUND", (0, 5), (-1, 6), "#d4edda"),  # Green highlight for totals
    ]))
    elements.append(t_cost)

    # ── Footer ───────────────────────────────────────────────────────────────
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

st.title("Système de Gestion de Tir (SGT)")
st.markdown("### Tableau de Bord Technique")

# Top metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Production Cible", f"{target_tons / 1000:.1f} kT")
m2.metric("Maille", f"{burden}×{spacing}", delta="Géométrie")
m3.metric("Charge Spécifique", f"{pf_target} kg/m³")
m4.metric("Coût Unitaire", f"{cost_per_ton:.2f} DH/T", delta_color="inverse")

# Technical alerts
for alert in alerts:
    st.error(f"⚠️ {alert}")

# Content tabs
tab1, tab2 = st.tabs(["📈 Analyse Technique & Financière", "📄 Rapport & Export"])

with tab1:
    col_graph, col_data = st.columns([2, 1])

    with col_graph:
        st.subheader("Plan de Tir (Vue Dessus)")
        st.pyplot(fig_plan)
        st.info(f"**Analyse Qualité ({geology_type}):**\n{quality_note}")

    with col_data:
        # Explosive quantities summary
        st.subheader("Quantités d'Explosifs")
        df_explosives = pd.DataFrame({
            "Explosif": ["Ammonix (ANFO)", "Émulsion (Booster)", "TOTAL"],
            "kg / Trou": [ammonix_per_hole, emulsion_per_hole, total_explosive_per_hole],
            "Total (kg)": [total_ammonix_kg, total_emulsion_kg, total_explosive_kg],
            "Coût (DH)": [cost_ammonix_total, cost_emulsion_total, cost_ammonix_total + cost_emulsion_total],
        })
        st.dataframe(
            df_explosives.style.format({
                "kg / Trou": "{:.2f}",
                "Total (kg)": "{:,.1f}",
                "Coût (DH)": "{:,.0f}",
            }),
            hide_index=True,
        )

        st.markdown("---")

        # Full cost breakdown
        st.subheader("Détail des Coûts")
        df_costs = pd.DataFrame({
            "Poste": ["Foration", "Ammonix", "Émulsion", "Accessoires", "Frais Fixes"],
            "Coût (DH)": [cost_drilling, cost_ammonix_total, cost_emulsion_total, cost_accessories, fixed_fees],
        })
        st.dataframe(df_costs.style.format({"Coût (DH)": "{:,.0f}"}), hide_index=True)
        st.markdown(f"**Total HT :** {total_cost_ht:,.0f} DH")
        st.markdown(f"**Total TTC :** {total_cost_ttc:,.0f} DH")

with tab2:
    st.subheader("Génération de Rapport")
    st.write("Ce module génère un PDF standardisé pour les équipes techniques et la direction.")

    # Pre-export summary of explosive quantities
    st.markdown("#### Récapitulatif des Quantités d'Explosifs")
    recap_col1, recap_col2, recap_col3 = st.columns(3)
    recap_col1.metric("Ammonix (ANFO)", f"{total_ammonix_kg:,.1f} kg", f"{ammonix_per_hole:.2f} kg/trou")
    recap_col2.metric("Émulsion (Booster)", f"{total_emulsion_kg:,.1f} kg", f"{emulsion_per_hole:.2f} kg/trou")
    recap_col3.metric("Total Explosifs", f"{total_explosive_kg:,.1f} kg", f"{total_explosive_per_hole:.2f} kg/trou")

    st.markdown("---")

    if st.button("Générer le Rapport Technique (PDF)"):
        pdf_file = generate_technical_report()
        st.download_button(
            label="⬇️ Télécharger le Rapport Officiel",
            data=pdf_file,
            file_name=f"Rapport_Tir_BL_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
        )
