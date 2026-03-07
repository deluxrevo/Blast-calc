import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Optimisation Carrière Benslimane", layout="wide", page_icon="💥")

# --- CSS PERSONNALISÉ ---
st.markdown("""
    <style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #FF4B4B; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- BARRE LATÉRALE : ENTRÉES ---
st.sidebar.title("🎛️ Paramètres de Tir")

st.sidebar.header("1. Objectifs de Production")
target_tons = st.sidebar.number_input("Tonnage Cible (Tonnes)", min_value=1000, value=20000, step=500)
rock_density = st.sidebar.number_input("Densité de la Roche (t/m3)", value=2.7, step=0.1)

st.sidebar.header("2. Géométrie de Foration")
# Valeurs par défaut pour une maille serrée
burden = st.sidebar.number_input("Banquette (Burden) (m)", min_value=1.5, max_value=6.0, value=3.0, step=0.1, help="Distance au front libre. Garder serré pour la roche dure !")
spacing = st.sidebar.number_input("Espacement (Spacing) (m)", min_value=1.5, max_value=7.0, value=3.0, step=0.1, help="Distance entre les trous. Idéalement 1.0x à 1.3x la Banquette.")
bench_height = st.sidebar.slider("Hauteur de Gradin (m)", 6.0, 15.0, 10.0, help="10-12m est optimal. 6m est inefficace.")
hole_diameter = st.sidebar.selectbox("Diamètre du Trou (mm)", [76, 89, 102], index=1)

st.sidebar.header("3. Plan de Chargement")
pf_target = st.sidebar.number_input("Charge Spécifique Cible (kg/m3)", min_value=0.15, max_value=1.0, value=0.55, step=0.01, help="0.55 = Standard. 0.45 = Éco (Schiste). 0.65 = Dur (Dolérite).")
sub_drill = st.sidebar.number_input("Surforation (m)", value=1.0, step=0.1, help="Généralement 1.0m. Augmenter à 1.2m pour les pieds durs.")
stemming_m = st.sidebar.number_input("Bourrage (m)", value=2.5, step=0.1, help="Gravette propre uniquement. Environ 20-30x le diamètre.")

st.sidebar.header("4. Coûts Unitaires (HT)")
cost_drill_m = st.sidebar.number_input("Foration (DH/m)", value=28.0)
cost_ammonix = st.sidebar.number_input("Ammonix (DH/kg)", value=17.55)
cost_emulsion = st.sidebar.number_input("Émulsion (DH/kg)", value=46.00)
cost_detonator = st.sidebar.number_input("Détonateur (Unité)", value=68.00)

st.sidebar.header("5. Frais Fixes")
fixed_fees = st.sidebar.number_input("Transport/Gardiennage (DH)", value=7000.0)

# --- MOTEUR DE CALCUL ---

# 1. Calculs Géométriques
hole_depth = bench_height + sub_drill
vol_solid_per_hole = burden * spacing * bench_height  # Volume RÉEL par trou
tonnage_per_hole = vol_solid_per_hole * rock_density

# 2. Calcul de Charge Explosive
total_explosive_target = vol_solid_per_hole * pf_target # Total kg nécessaire par trou
emulsion_per_hole = 5.0 # Booster fixe (approx 1 cartouche + charge de fond)
ammonix_per_hole = total_explosive_target - emulsion_per_hole

# Vérification de la capacité du trou
# Vol Cylindre - bourrage - booster
charge_length_available = hole_depth - stemming_m - 0.5 
# Densité linéary approx pour trou 89mm (kg/m) ~ 5-6 kg/m selon densité vrac
linear_charge_density = (np.pi * ((hole_diameter/1000)/2)**2) * 850 # 0.85 g/cc densité Ammonix
max_ammo_capacity = charge_length_available * linear_charge_density

# Alerte si besoin > capacité
capacity_warning = ""
if ammonix_per_hole > max_ammo_capacity:
    capacity_warning = f"⚠️ Attention : Diamètre {hole_diameter}mm trop petit pour PF {pf_target}. Capacité max {max_ammo_capacity:.1f}kg vs Besoin {ammonix_per_hole:.1f}kg."

# 3. Flotte & Totaux
num_holes = int(np.ceil(target_tons / tonnage_per_hole))
total_drill_meters = num_holes * hole_depth
total_ammonix = num_holes * ammonix_per_hole
total_emulsion = num_holes * emulsion_per_hole
total_volume_rock = num_holes * vol_solid_per_hole

# 4. Financier
c_drill = total_drill_meters * cost_drill_m
c_ammo = total_ammonix * cost_ammonix
c_emul = total_emulsion * cost_emulsion
c_acc = num_holes * (cost_detonator + 15) # +15 pour fil
total_ht = c_drill + c_ammo + c_emul + c_acc + fixed_fees
total_ttc = total_ht * 1.20
cost_per_ton = total_ht / target_tons

# --- FONCTIONS GRAPHIQUES ---

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
                if r % 2 != 0: x += (spacing / 2) # Quinconce
                x_coords.append(x)
                y_coords.append(y)
                hole_count += 1
                
    ax.scatter(x_coords, y_coords, c='red', s=50, edgecolors='black', zorder=3)
    # Front Libre
    ax.axhline(y=burden*0.5, color='blue', linestyle='--', linewidth=2, label="Front Libre")
    ax.set_title(f"Plan de Tir : {burden}m x {spacing}m", fontsize=10)
    ax.set_xlabel("Largeur de Front (m)")
    ax.set_ylabel("Recul (m)")
    ax.grid(True, linestyle=':', alpha=0.6)
    return fig

def create_hole_profile(depth, sub, stem, ammo_h):
    fig, ax = plt.subplots(figsize=(2, 6))
    width = 1
    # Couches
    ax.bar(0, sub, bottom=0, width=width, color='black', label='Surforation')
    ax.bar(0, 0.5, bottom=sub, width=width, color='red', label='Booster')
    ax.bar(0, ammo_h, bottom=sub+0.5, width=width, color='orange', label='Ammonix')
    ax.bar(0, stem, bottom=depth-stem, width=width, color='grey', hatch='//', label='Bourrage')
    
    ax.set_ylim(0, depth+1)
    ax.set_xlim(-1, 1)
    ax.set_ylabel("Mètres")
    ax.set_xticks([])
    ax.set_title("Coupe Trou", fontsize=10)
    return fig

# Génération des graphiques
rows = int(np.ceil(np.sqrt(num_holes)))
cols = int(np.ceil(num_holes / rows)) + 1
fig_pattern = create_pattern_plot(rows, cols, num_holes, burden, spacing)
fig_profile = create_hole_profile(hole_depth, sub_drill, stemming_m, hole_depth - stemming_m - sub_drill - 0.5)

# --- GÉNÉRATION PDF ---
def generate_pdf(pattern_fig, profile_fig, num_holes, burden, spacing, hole_depth, 
                 sub_drill, stemming, ammo_kg, emul_kg, drill_m, total_ht, total_ttc, pf, t_tons):
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    
    # 1. EN-TÊTE
    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontSize=16, spaceAfter=10, textColor=colors.darkblue)
    elements.append(Paragraph("ORDRE DE TIR (BLASTING ORDER)", title_style))
    elements.append(Paragraph(f"<b>Projet :</b> Carrière Benslimane | <b>Conception Technique</b>", styles['Normal']))
    elements.append(Paragraph(f"<b>Date :</b> {pd.Timestamp.now().strftime('%d/%m/%Y')} | <b>Objectif :</b> {t_tons:,.0f} Tonnes", styles['Normal']))
    elements.append(Spacer(1, 15))

    # 2. MÉTRIQUES CLÉS
    summary_data = [
        ["TOTAL TROUS", "PROFONDEUR", "MAILLE (B x S)", "CHARGE SPÉCIFIQUE"],
        [f"{num_holes}", f"{hole_depth} m", f"{burden}m x {spacing}m", f"{pf} kg/m³"]
    ]
    t_summary = Table(summary_data, colWidths=[120, 100, 120, 120])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('SIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 15))

    # 3. IMAGES
    img_buf1 = BytesIO()
    pattern_fig.savefig(img_buf1, format='png', dpi=100, bbox_inches='tight')
    img_buf1.seek(0)
    
    img_buf2 = BytesIO()
    profile_fig.savefig(img_buf2, format='png', dpi=100, bbox_inches='tight')
    img_buf2.seek(0)
    
    img1 = Image(img_buf1, width=320, height=220)
    img2 = Image(img_buf2, width=100, height=220)
    
    img_data = [[img1, img2]]
    t_images = Table(img_data, colWidths=[350, 150])
    t_images.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'CENTER'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_images)
    
    # 4. INSTRUCTIONS
    instr_text = f"""
    <font size=11><b>INSTRUCTIONS DE CHARGEMENT :</b></font><br/>
    1. <b>Surforation :</b> {sub_drill} m <font color=red>(Critique pour le pied !)</font><br/>
    2. <b>Amorçage :</b> 1 Cartouche d'Émulsion en fond de trou.<br/>
    3. <b>Colonne Explosive :</b> {hole_depth - stemming - sub_drill - 0.5:.1f} m d'Ammonix.<br/>
    4. <b>Bourrage :</b> {stemming} m <font color=red><b>(GRAVETTE PROPRE UNIQUEMENT)</b></font>
    """
    elements.append(Paragraph(instr_text, styles['Normal']))
    elements.append(Spacer(1, 15))

    # 5. COÛTS
    elements.append(Paragraph("<b>ESTIMATION BUDGÉTAIRE (DEVIS)</b>", styles['Heading4']))
    cost_data = [
        ["POSTE", "QUANTITÉ", "PRIX UNITAIRE", "TOTAL (HT)"],
        ["Foration", f"{drill_m:,.0f} m", f"{cost_drill_m} DH", f"{c_drill:,.0f}"],
        ["Ammonix", f"{ammo_kg:,.0f} kg", f"{cost_ammonix} DH", f"{c_ammo:,.0f}"],
        ["Émulsion", f"{emul_kg:,.0f} kg", f"{cost_emulsion} DH", f"{c_emul:,.0f}"],
        ["Accessoires", f"{num_holes} u", "Var", f"{c_acc:,.0f}"],
        ["Frais Fixes", "1", f"{fixed_fees} DH", f"{fixed_fees:,.0f}"],
        ["<b>TOTAL HT</b>", "", "", f"<b>{total_ht:,.0f} DH</b>"],
        ["<b>TOTAL TTC</b>", "", "", f"<b>{total_ttc:,.0f} DH</b>"]
    ]
    t_cost = Table(cost_data, colWidths=[140, 100, 100, 120])
    t_cost.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,6), (-1,7), colors.lightblue),
        ('FONTNAME', (0,6), (-1,7), 'Helvetica-Bold'),
    ]))
    elements.append(t_cost)

    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- MISE EN PAGE PRINCIPALE ---
st.title("🚀 Optimiseur de Tir Carrière")
st.caption("Mode Conception Technique Avancée")

# Métriques Supérieures
m1, m2, m3, m4 = st.columns(4)
m1.metric("Production", f"{target_tons:,.0f} T")
m2.metric("Maille", f"{burden}m x {spacing}m")
m3.metric("Explosifs", f"{total_ammonix+total_emulsion:,.0f} kg")
m4.metric("Coût TTC", f"{total_ttc:,.0f} DH")

# Avertissements
if capacity_warning:
    st.error(capacity_warning)
if bench_height < 9.0:
    st.warning("⚠️ Hauteur de gradin < 9m. L'efficacité chute en dessous de 10m.")
if burden > 3.5:
    st.warning("⚠️ Alerte Maille Large : Banquette > 3.5m risque de blocs en roche dure.")
if pf_target < 0.35:
    st.error("⛔ DANGER : Charge Spécifique < 0.35. Blocs et Pieds garantis.")

# Onglets
tab1, tab2, tab3 = st.tabs(["📊 Plan Visuel", "💰 Détail des Coûts", "📄 Rapport PDF"])

with tab1:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.pyplot(fig_pattern)
    with c2:
        st.pyplot(fig_profile)
        st.info(f"**Stats Rapides :**\n\n- Trous : {num_holes}\n- Mètres : {total_drill_meters:,.0f}m\n- Charge Spécifique : {pf_target} kg/m³")

with tab2:
    st.dataframe(pd.DataFrame({
        "Catégorie": ["Foration", "Ammonix", "Émulsion", "Accessoires", "Frais Fixes"],
        "Coût (HT)": [c_drill, c_ammo, c_emul, c_acc, fixed_fees],
        "% du Budget": [c_drill/total_ht*100, c_ammo/total_ht*100, c_emul/total_ht*100, c_acc/total_ht*100, fixed_fees/total_ht*100]
    }).style.format({"Coût (HT)": "{:,.0f} DH", "% du Budget": "{:.1f}%"}))
    
    st.success(f"**Coût Unitaire : {cost_per_ton:.2f} DH/tonne**")

with tab3:
    st.write("### Générer le Rapport Officiel")
    st.write("Cliquez ci-dessous pour télécharger l'Ordre de Tir.")
    
    if st.button("📄 Générer le PDF (Ordre de Tir)", key="pdf_btn"):
        pdf_file = generate_pdf(fig_pattern, fig_profile, num_holes, burden, spacing, 
                                hole_depth, sub_drill, stemming_m, total_ammonix, 
                                total_emulsion, total_drill_meters, total_ht, total_ttc, pf_target, target_tons)
        
        st.download_button(
            label="⬇️ Télécharger l'Ordre de Tir",
            data=pdf_file,
            file_name=f"Ordre_Tir_{burden}x{spacing}_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
