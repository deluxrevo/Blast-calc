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
    PATTERN_RECTANGULAR,
    PATTERN_STAGGERED,
    PATTERN_CENTER_HOLE,
    PF_KG_PER_T,
    PF_UNITS,
    pf_in_unit,
    pf_kg_m3_to_kg_t,
    pf_status,
    target_pf_to_kg_m3,
    validate_inputs,
    compute_charges,
    compute_fleet,
    compute_costs,
    get_technical_alerts,
)
from utils.plots import plot_blast_pattern, plot_hole_cross_section
from utils.report import ReportData, build_technical_report

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
PATTERN_OPTIONS = {
    "Grille rectangulaire (B × S)": PATTERN_RECTANGULAR,
    "Quinconce (rangées décalées, B × S)": PATTERN_STAGGERED,
    "Grille + trou central (densité × 2)": PATTERN_CENTER_HOLE,
}
pattern_label: str = st.sidebar.selectbox(
    "Type de Maille",
    list(PATTERN_OPTIONS.keys()),
    help=(
        "Surface par trou = B × S pour une grille rectangulaire ou un quinconce. "
        "Si un trou supplémentaire est foré au centre de chaque rectangle B × S, "
        "la densité est doublée et la surface par trou est divisée par 2 "
        "(ex. 5 × 5,5 = 27,5 m² → 13,75 m²/trou). Ce n'est PAS une maille 2,5 × 2,75 "
        "(6,875 m²/trou)."
    ),
)
pattern: str = PATTERN_OPTIONS[pattern_label]
bench_height: float = st.sidebar.slider("Hauteur de Gradin (H) [m]", 6.0, 15.0, 10.0)
hole_diameter: int = st.sidebar.selectbox("Diamètre Foration [mm]", [76, 89, 102], index=1)

# ── 4. Charge design ─────────────────────────────────────────────────────────
st.sidebar.header("4. Plan de Chargement")
pf_unit: str = st.sidebar.radio(
    "Unité de la Charge Spécifique",
    PF_UNITS,
    help=(
        "kg/t : masse d'explosif par tonne de roche abattue (dépend de la densité). "
        "kg/m³ : masse d'explosif par m³ de roche en place. "
        "kg/m³ = kg/t × densité (t/m³). Cible et valeur réelle sont toujours "
        "comparées dans l'unité choisie."
    ),
)
if pf_unit == PF_KG_PER_T:
    pf_target: float = st.sidebar.number_input(
        "Charge Spécifique cible (q) [kg/t]", 0.020, 0.600,
        round(pf_kg_m3_to_kg_t(rec_pf, density_val), 3), 0.005,
        format="%.3f",
        key=f"pf_{geology_type}_kgt",
        help=f"Recommandation : {rec_pf:.2f} kg/m³ = "
             f"{pf_kg_m3_to_kg_t(rec_pf, density_val):.3f} kg/t (densité {density_val} t/m³).",
    )
else:
    pf_target = st.sidebar.number_input(
        "Charge Spécifique cible (q) [kg/m³]", 0.05, 1.50, rec_pf, 0.01,
        format="%.3f",
        key=f"pf_{geology_type}_kgm3",
        help=f"Recommandation : {rec_pf:.2f} kg/m³.",
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
    pattern=pattern,
)

input_errors = validate_inputs(
    burden=burden, spacing=spacing, bench_height=bench_height,
    sub_drill=sub_drill, stemming_m=stemming_m, hole_diameter=hole_diameter,
    density=density_val, pf_target=pf_target, pf_unit=pf_unit,
    target_tons=target_tons, safety_gap=safety_gap,
)
if input_errors:
    for err in input_errors:
        st.error(f"⛔ {err}")
    st.stop()

pf_target_kg_m3 = target_pf_to_kg_m3(pf_target, pf_unit, density_val)
charges = compute_charges(geom, pf_target_kg_m3, emulsion_per_hole)
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

# Actual PF is computed from the loaded charge, in the SAME unit as the target.
pf_actual: float = pf_in_unit(
    fleet.total_explosive_kg, fleet.total_rock_volume, density_val, pf_unit,
)
pf_state: str = pf_status(pf_actual, pf_target)

# ---------------------------------------------------------------------------
# DIAGRAMS (generated once, reused in tabs and PDF)
# ---------------------------------------------------------------------------

fig_plan = plot_blast_pattern(fleet.num_holes, burden, spacing, pattern)
fig_hole = plot_hole_cross_section(geom, charges)

# ---------------------------------------------------------------------------
# PDF REPORT GENERATION
# ---------------------------------------------------------------------------


def generate_technical_report() -> BytesIO:
    """Build and return a BytesIO buffer containing the full PDF technical report."""
    return build_technical_report(ReportData(
        site_name=SITE_NAME,
        geology_type=geology_type,
        rock_hardness=rock_hardness,
        quality_note=quality_note,
        clay_risk=clay_risk,
        density=density_val,
        target_tons=target_tons,
        pattern_label=pattern_label,
        geom=geom,
        charges=charges,
        fleet=fleet,
        costs=costs,
        pf_target=pf_target,
        pf_actual=pf_actual,
        pf_unit=pf_unit,
        pf_state=pf_state,
        cost_drill_per_m=cost_drill_per_m,
        cost_ammonix_per_kg=cost_ammonix_per_kg,
        cost_emulsion_per_kg=cost_emulsion_per_kg,
        cost_detonator_each=cost_detonator_each,
        fig_plan=fig_plan,
        fig_hole=fig_hole,
        alerts=alerts,
    ))


# ---------------------------------------------------------------------------
# MAIN DASHBOARD
# ---------------------------------------------------------------------------

st.title(f"⚒️ {APP_TITLE}")
st.markdown(f"### {APP_SUBTITLE}")
st.caption(f"Site : {SITE_NAME}  |  Faciès : **{geology_type}**  |  Ø {hole_diameter} mm")

st.markdown("---")

# ── Top KPI metrics ──────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric(
    "🎯 Production Cible", f"{target_tons / 1000:.1f} kT",
    f"Abattu : {fleet.total_tonnage / 1000:.2f} kT",
    delta_color="off",
    help="Tonnage réellement abattu = nombre de trous (arrondi au supérieur) × tonnage par trou.",
)
m2.metric(
    "📐 Maille de Tir", f"{burden:.2f} × {spacing:.2f} m",
    f"{geom.area_per_hole:.2f} m²/trou · {geom.rock_volume_per_hole:.1f} m³/trou",
    delta_color="off",
    help="Surface effective par trou et volume de roche par trou (surface × hauteur de gradin).",
)
m3.metric(
    f"💥 Charge Spécifique réelle [{pf_unit}]", f"{pf_actual:.3f}",
    f"Cible {pf_target:.3f} {pf_unit}",
    delta_color="off",
    help="Explosif chargé (Ammonix + Émulsion) / roche abattue, dans l'unité choisie.",
)
m4.metric("🕳️ Nombre de Trous", f"{fleet.num_holes}")
m5.metric(
    "💰 Coût Unitaire", f"{costs.cost_per_ton:.2f} DH/T",
    help="Coût total HT / tonnage abattu.",
)

st.markdown("---")

# ── Technical alerts ─────────────────────────────────────────────────────────
if pf_state == "low":
    reason = (
        " — le trou ne peut pas contenir la charge requise (charge limitée à sa capacité)."
        if charges.capacity_limited else "."
    )
    st.warning(
        f"⚠️ Charge spécifique réelle ({pf_actual:.3f} {pf_unit}) inférieure à la cible "
        f"({pf_target:.3f} {pf_unit}){reason}"
    )
elif pf_state == "high":
    st.warning(
        f"⚠️ Charge spécifique réelle ({pf_actual:.3f} {pf_unit}) supérieure à la cible "
        f"({pf_target:.3f} {pf_unit}) — l'émulsion seule dépasse la charge cible."
    )
else:
    st.success(
        f"✅ Charge spécifique conforme : {pf_actual:.3f} {pf_unit} "
        f"(cible {pf_target:.3f} {pf_unit})."
    )
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
        help=(
            f"Charge requise par la cible : {charges.target_explosive_per_hole:.2f} kg/trou. "
            f"Capacité Ammonix du trou : {charges.ammonix_capacity:.2f} kg."
        ),
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
    fin_col3.metric(
        "📦 Coût / Tonne (HT)", f"{costs.cost_per_ton:.2f} DH/T",
        f"sur {fleet.total_tonnage:,.0f} t abattues", delta_color="off",
    )

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
