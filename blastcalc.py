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
    density_val = 2.7
elif geology_type == "Psammites (Ordovicien)":
    rec_pf = 0.65
    rec_burden = 2.8
    rock_desc = "Roche TRÈS DURE et Abrasive. Foration difficile."
    abrasivity = "Haute"
    density_val = 2.75
elif geology_type == "Calcaire (Dévonien)":
    rec_pf = 0.45
    rec_burden = 3.2
    rock_desc = "Roche compacte. Cassure franche."
    abrasivity = "Faible"
    density_val = 2.65
else:
    rec_pf = 0.50
    rec_burden = 3.0
    rock_desc = "Terrain variable."
    abrasivity = "Moyenne"
    density_val = 2.6

st.sidebar.info(f"ℹ️ **Info Roche:** {rock_desc}")

st.sidebar.header("1. Objectifs de Production")
target_tons = st.sidebar.number_input("Tonnage Cible (Tonnes)", min_value=1000, value=20000, step=500)
rock_density = st.sidebar.number_input("Densité (t/m3)", value=density_val, step=0.01)

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
        sand_quality_score = "SALE (Boueux)"
        clay_risk = "ÉLEVÉ"
        quality_msg = "⚠️ **Risque Qualité :** Avec un PF faible (<0.50) dans les Pélites, l'argile ne sera pas pulvérisée. Le sable sera sale (ES < 60)."
    else:
        sand_quality_score = "Acceptable (Scalpage Requis)"
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

# --- GÉNÉRATION PDF (SINGLE PAGE FIX) ---
def generate_pdf(t_tons, geology, pf, burden, spacing, num_holes, hole_depth, drill_m, total_ht, total_ttc, sand_quality, clay_risk):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    
    # 1. EN-TÊTE COMPACT
    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontSize=14, spaceAfter=5, textColor=colors.darkblue)
    elements.append(Paragraph("ORDRE DE TIR & ANALYSE GÉOLOGIQUE", title_style))
    elements.append(Paragraph(f"<b>Site :</b> Benslimane | <b>Formation :</b> {geology} | <b>Date :</b> {pd.Timestamp.now().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    # 2. GRILLE DE SYNTHÈSE (GEOLOGIE INCLUSE)
    summary_data = [
        ["PARAMÈTRE", "VALEUR", "PARAMÈTRE", "VALEUR"],
        ["Production Cible", f"{t_tons:,.0f} T", "Qualité Sable", sand_quality],
        ["Maille (B x S)", f"{burden}m x {spacing}m", "Risque Argile", clay_risk],
        ["Charge Spécifique", f"{pf} kg/m³", "Total Trous", f"{num_holes}"],
        ["Profondeur", f"{hole_depth} m", "Densité Roche", f"{rock_density} t/m³"]
    ]
    t_summary = Table(summary_data, colWidths=[110, 110, 110, 150])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('SIZE', (0,0), (-1,-1), 8), # Police plus petite pour tout faire tenir
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 10))

    # 3. IMAGES CÔTE À CÔTE
    img_buf1 = BytesIO()
    fig_pattern.savefig(img_buf1, format='png', dpi=90, bbox_inches='tight') # DPI réduit pour la taille
    img_buf1.seek(0)
    
    img_buf2 = BytesIO()
    fig_profile.savefig(img_buf2, format='png', dpi=90, bbox_inches='tight')
    img_buf2.seek(0)
    
    img1 = Image(img_buf1, width=300, height=200)
    img2 = Image(img_buf2, width=80, height=200)
    
    img_data = [[img1, img2]]
    t_images = Table(img_data, colWidths=[350, 100])
    t_images.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_images)
    
    # 4. INSTRUCTIONS CONCISES
    instr_text = f"""
    <font size=10><b>INSTRUCTIONS :</b></font><br/>
    • <b>Surforation :</b> {sub_drill} m (Critique Pieds)<br/>
    • <b>Charge :</b> {hole_depth - stemming_m - sub_drill - 0.5:.1f} m Ammonix + 1 Cartouche Emulsion<br/>
    • <b>Bourrage :</b> {stemming_m} m (Gravette Propre). <b>SCALPAGE REQUIS AVANT CONCASSAGE.</b>
    """
    elements.append(Paragraph(instr_text, styles['Normal']))
    elements.append(Spacer(1, 10))

    # 5. TABLEAU DES COÛTS (COMPACT)
    elements.append(Paragraph("<b>ESTIMATION FINANCIÈRE (DEVIS)</b>", styles['Heading4']))
    cost_data = [
        ["POSTE", "UNITÉ", "PRIX U.", "TOTAL (HT)"],
        ["Foration", f"{drill_m:,.0f} m", f"{cost_drill_m}", f"{c_drill:,.0f}"],
        ["Explosifs", f"{total_ammonix+total_emulsion:,.0f} kg", "Mix", f"{c_ammo+c_emul:,.0f}"],
        ["Accessoires", f"{num_holes} u", "Var", f"{c_acc:,.0f}"],
        ["Frais Fixes", "1", f"{fixed_fees}", f"{fixed_fees:,.0f}"],
        ["<b>TOTAL HT</b>", "", "", f"<b>{total_ht:,.0f} DH</b>"],
        ["<b>TOTAL TTC</b>", "", "", f"<b>{total_ttc:,.0f} DH</b>"]
    ]
    t_cost = Table(cost_data, colWidths=[120, 80, 80, 120])
    t_cost.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,5), (-1,6), colors.lightblue),
        ('FONTNAME', (0,5), (-1,6), 'Helvetica-Bold'),
        ('SIZE', (0,0), (-1,-1), 9),
    ]))
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
    st.write("### 📄 Rapport Officiel (Une Page)")
    if st.button("Générer le PDF"):
        pdf = generate_pdf(target_tons, geology_type, pf_target, burden, spacing, num_holes, hole_depth, total_drill_meters, total_ht, total_ttc, sand_quality_score, clay_risk)
        st.download_button("⬇️ Télécharger l'Ordre de Tir", pdf, "Ordre_Geologie_Benslimane.pdf", "application/pdf")
