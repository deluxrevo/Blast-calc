import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Optimisation Carrière Benslimane (Géologie Calibrée)", layout="wide", page_icon="🪨")

# --- CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #FF4B4B; color: white; }
    .stAlert { font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- BARRE LATÉRALE : ENTRÉES ---
st.sidebar.title("🎛️ Paramètres de Tir")

st.sidebar.markdown("### 🏔️ Contexte Géologique")
geology_type = st.sidebar.selectbox(
    "Formation Dominante",
    ["Gréso-Pélitique (Viséen)", "Psammites (Ordovicien)", "Calcaire (Dévonien)", "Mixte (Argileux)"],
    index=0,
    help="Définit la dureté et le risque d'argile (Pélites)."
)

# Calibrage automatique basé sur la géologie
if geology_type == "Gréso-Pélitique (Viséen)":
    rec_pf = 0.55
    rec_burden = 3.0
    rock_desc = "Roche Mixte (Dure/Tendre). Risque de fines argileuses."
    abrasivity = "Moyenne"
elif geology_type == "Psammites (Ordovicien)":
    rec_pf = 0.65
    rec_burden = 2.8
    rock_desc = "Roche TRÈS DURE et Abrasive. Foration difficile."
    abrasivity = "Haute"
elif geology_type == "Calcaire (Dévonien)":
    rec_pf = 0.45
    rec_burden = 3.2
    rock_desc = "Roche compacte. Cassure franche."
    abrasivity = "Faible"
else:
    rec_pf = 0.50
    rec_burden = 3.0
    rock_desc = "Terrain variable."
    abrasivity = "Moyenne"

st.sidebar.info(f"ℹ️ **Info Roche:** {rock_desc}")

st.sidebar.header("1. Objectifs de Production")
target_tons = st.sidebar.number_input("Tonnage Cible (Tonnes)", min_value=1000, value=20000, step=500)
rock_density = st.sidebar.number_input("Densité (t/m3)", value=2.7, step=0.1)

st.sidebar.header("2. Géométrie de Foration")
st.sidebar.markdown(f"*Recommandé pour {geology_type} : {rec_burden}m x {rec_burden*1.2:.1f}m*")
burden = st.sidebar.number_input("Banquette (Burden) (m)", min_value=1.5, max_value=6.0, value=rec_burden, step=0.1)
spacing = st.sidebar.number_input("Espacement (Spacing) (m)", min_value=1.5, max_value=7.0, value=rec_burden*1.2, step=0.1)
bench_height = st.sidebar.slider("Hauteur de Gradin (m)", 6.0, 15.0, 10.0)
hole_diameter = st.sidebar.selectbox("Diamètre du Trou (mm)", [76, 89, 102], index=1)

st.sidebar.header("3. Plan de Chargement")
pf_target = st.sidebar.number_input(
    "Charge Spécifique Cible (kg/m3)", 
    min_value=0.15, max_value=1.0, 
    value=rec_pf, 
    step=0.01,
    help="Force de l'explosion. < 0.45 = Risque de Blocs en Grès."
)
sub_drill = st.sidebar.number_input("Surforation (m)", value=1.0, step=0.1)
stemming_m = st.sidebar.number_input("Bourrage (m)", value=2.5, step=0.1)

st.sidebar.header("4. Coûts Unitaires (HT)")
cost_drill_m = st.sidebar.number_input("Foration (DH/m)", value=28.0 if abrasivity != "Haute" else 35.0, help="Prix ajusté selon l'abrasivité (Psammite = +Cher)")
cost_ammonix = st.sidebar.number_input("Ammonix (DH/kg)", value=17.55)
cost_emulsion = st.sidebar.number_input("Émulsion (DH/kg)", value=46.00)
cost_detonator = st.sidebar.number_input("Détonateur (Unité)", value=68.00)
fixed_fees = st.sidebar.number_input("Frais Fixes (DH)", value=7000.0)

# --- MOTEUR DE CALCUL ---

# 1. Géométrie
hole_depth = bench_height + sub_drill
vol_solid_per_hole = burden * spacing * bench_height
tonnage_per_hole = vol_solid_per_hole * rock_density

# 2. Explosifs
total_explosive_target = vol_solid_per_hole * pf_target
emulsion_per_hole = 5.0
ammonix_per_hole = total_explosive_target - emulsion_per_hole

# Vérification Capacité
charge_length_available = hole_depth - stemming_m - 0.5 
linear_charge_density = (np.pi * ((hole_diameter/1000)/2)**2) * 850 
max_ammo_capacity = charge_length_available * linear_charge_density

capacity_warning = ""
if ammonix_per_hole > max_ammo_capacity:
    capacity_warning = f"⚠️ **Attention Diamètre:** Le trou de {hole_diameter}mm est trop petit pour contenir {ammonix_per_hole:.1f}kg (Max: {max_ammo_capacity:.1f}kg). Réduisez la maille ou augmentez le diamètre."

# 3. Flotte & Totaux
num_holes = int(np.ceil(target_tons / tonnage_per_hole))
total_drill_meters = num_holes * hole_depth
total_ammonix = num_holes * ammonix_per_hole
total_emulsion = num_holes * emulsion_per_hole
total_volume_rock = num_holes * vol_solid_per_hole

# 4. Qualité du Sable (Estimation Géologique)
sand_quality_score = "Bonne"
clay_risk = "Faible"
if "Pélitique" in geology_type or "Mixte" in geology_type:
    if pf_target < 0.50:
        sand_quality_score = "MÉDIOCRE (Sale)"
        clay_risk = "ÉLEVÉ (Boue)"
        quality_msg = "⚠️ **Risque Qualité :** Avec un PF faible (<0.50) dans les Pélites, l'argile ne sera pas pulvérisée. Le sable sera sale (ES < 60)."
    else:
        sand_quality_score = "Acceptable (Si scalpage)"
        clay_risk = "Moyen (Poussière)"
        quality_msg = "✅ **Optimisation :** Le PF élevé (>0.50) va aider à séparer l'argile des grès."
elif geology_type == "Psammites (Ordovicien)":
    sand_quality_score = "Excellente (Dureté)"
    clay_risk = "Nul"
    quality_msg = "💎 **Qualité Premium :** Le sable de Psammite est excellent pour le béton HP."
else:
    quality_msg = "Qualité standard."

# 5. Financier
c_drill = total_drill_meters * cost_drill_m
c_ammo = total_ammonix * cost_ammonix
c_emul = total_emulsion * cost_emulsion
c_acc = num_holes * (cost_detonator + 15)
total_ht = c_drill + c_ammo + c_emul + c_acc + fixed_fees
total_ttc = total_ht * 1.20
cost_per_ton = total_ht / target_tons

# --- GRAPHIQUES ---
def create_pattern_plot(rows, cols, num_holes, burden, spacing):
    fig, ax = plt.subplots(figsize=(6, 4))
    hole_count = 0
    x_coords = []
    y_coords = []
    for r in range(rows):
        for c in range(cols):
            if hole_count < num_holes:
                x = c * spacing
                y = r * burden * -1
                if r % 2 != 0: x += (spacing / 2)
                x_coords.append(x)
                y_coords.append(y)
                hole_count += 1
    ax.scatter(x_coords, y_coords, c='red', s=50, edgecolors='black', zorder=3)
    ax.axhline(y=burden*0.5, color='blue', linestyle='--', linewidth=2, label="Front Libre")
    ax.set_title(f"Plan de Tir : {burden}m x {spacing}m", fontsize=10)
    ax.set_xlabel("Largeur (m)")
    ax.set_ylabel("Recul (m)")
    ax.grid(True, linestyle=':', alpha=0.6)
    return fig

def create_hole_profile(depth, sub, stem, ammo_h):
    fig, ax = plt.subplots(figsize=(2, 6))
    width = 1
    ax.bar(0, sub, bottom=0, width=width, color='black', label='Surforation')
    ax.bar(0, 0.5, bottom=sub, width=width, color='red', label='Booster')
    ax.bar(0, ammo_h, bottom=sub+0.5, width=width, color='orange', label='Ammonix')
    ax.bar(0, stem, bottom=depth-stem, width=width, color='grey', hatch='//', label='Bourrage')
    ax.set_ylim(0, depth+1)
    ax.set_xlim(-1, 1)
    ax.set_ylabel("Mètres")
    ax.set_xticks([])
    ax.set_title("Coupe", fontsize=10)
    return fig

rows = int(np.ceil(np.sqrt(num_holes)))
cols = int(np.ceil(num_holes / rows)) + 1
fig_pattern = create_pattern_plot(rows, cols, num_holes, burden, spacing)
fig_profile = create_hole_profile(hole_depth, sub_drill, stemming_m, hole_depth - stemming_m - sub_drill - 0.5)

# --- GÉNÉRATION PDF ---
def generate_pdf(t_tons, geology, pf, burden, spacing, num_holes, hole_depth, drill_m, total_ht, total_ttc, sand_quality, clay_risk):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    
    # Titre
    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontSize=16, spaceAfter=10, textColor=colors.darkblue)
    elements.append(Paragraph("ORDRE DE TIR & ANALYSE GÉOLOGIQUE", title_style))
    elements.append(Paragraph(f"<b>Site :</b> Benslimane | <b>Formation :</b> {geology}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date :</b> {pd.Timestamp.now().strftime('%d/%m/%Y')} | <b>Cible :</b> {t_tons:,.0f} Tonnes", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    # Tableau Technique
    data = [
        ["PARAMÈTRE", "VALEUR", "ANALYSE QUALITÉ SABLE"],
        ["Maille (B x S)", f"{burden}m x {spacing}m", f"Qualité : {sand_quality}"],
        ["Charge Spécifique", f"{pf} kg/m³", f"Risque Argile : {clay_risk}"],
        ["Total Trous", f"{num_holes}", "Recommandation : Scalpage nécessaire" if "Pélitique" in geology else "Standard"],
    ]
    t = Table(data, colWidths=[120, 150, 200])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 15))
    
    # Coûts
    elements.append(Paragraph("<b>ESTIMATION FINANCIÈRE</b>", styles['Heading4']))
    cost_data = [
        ["Total Foration", f"{drill_m:,.0f} m"],
        ["Coût Total (HT)", f"{total_ht:,.0f} DH"],
        ["Coût Total (TTC)", f"{total_ttc:,.0f} DH"]
    ]
    t_cost = Table(cost_data, colWidths=[200, 150])
    t_cost.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 1, colors.black)]))
    elements.append(t_cost)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- DASHBOARD ---
st.title("🚀 Optimiseur Carrière Benslimane (Géologie)")
st.caption(f"Calibré pour : {geology_type}")

col1, col2, col3 = st.columns(3)
col1.metric("Production", f"{target_tons:,.0f} T")
col2.metric("Maille", f"{burden}m x {spacing}m")
col3.metric("Coût TTC", f"{total_ttc:,.0f} DH")

if capacity_warning:
    st.error(capacity_warning)
if geology_type == "Psammites (Ordovicien)" and hole_diameter < 89:
    st.warning("⚠️ **Psammite :** Foration en petit diamètre (76mm) très coûteuse en taillants. Préférez 89mm+.")

# Analyse Qualité
st.markdown("### 🧪 Prédiction Qualité du Produit (Sable)")
q1, q2 = st.columns(2)
q1.info(f"**Qualité Sable :** {sand_quality_score}")
q2.warning(f"**Risque Argile (Boue) :** {clay_risk}")
st.write(quality_msg)

tab1, tab2, tab3 = st.tabs(["📊 Plan & Coupe", "💰 Coûts Détaillés", "📄 Rapport PDF"])

with tab1:
    c1, c2 = st.columns([3, 1])
    with c1: st.pyplot(fig_pattern)
    with c2: st.pyplot(fig_profile)

with tab2:
    st.dataframe(pd.DataFrame({
        "Poste": ["Foration", "Ammonix", "Émulsion", "Accessoires", "Frais Fixes"],
        "Montant (HT)": [c_drill, c_ammo, c_emul, c_acc, fixed_fees]
    }).style.format({"Montant (HT)": "{:,.0f} DH"}))
    st.success(f"**Coût de Revient : {cost_per_ton:.2f} DH/tonne**")

with tab3:
    if st.button("📄 Générer Rapport Géologique"):
        pdf = generate_pdf(target_tons, geology_type, pf_target, burden, spacing, num_holes, hole_depth, total_drill_meters, total_ht, total_ttc, sand_quality_score, clay_risk)
        st.download_button("⬇️ Télécharger", pdf, "Rapport_Geologie.pdf", "application/pdf")
