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
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# --- CONFIGURATION INITIALE ---
st.set_page_config(
    page_title="SGT - Système de Gestion de Tir", 
    layout="wide", 
    page_icon="⚒️",
    initial_sidebar_state="expanded"
)

# --- SÉCURITÉ (PASSWORD) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

def check_password():
    def password_entered():
        if st.session_state["password"] == "2024":  # <--- CHANGEZ LE MOT DE PASSE ICI
            st.session_state.authenticated = True
            del st.session_state["password"]
        else:
            st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown(
            """
            <style>
            .stTextInput > div > div > input {text-align: center; font-size: 20px;}
            </style>
            """, unsafe_allow_html=True)
        st.header("🔒 Accès Restreint")
        st.write("Veuillez saisir le code PIN opérateur.")
        st.text_input("Code PIN", type="password", on_change=password_entered, key="password")
        return False
    return True

if not check_password():
    st.stop()

# --- CSS PROFESSIONNEL ---
st.markdown("""
    <style>
    /* Titres */
    h1, h2, h3 { color: #2c3e50; font-family: 'Segoe UI', sans-serif; }
    /* Métriques */
    div[data-testid="stMetricValue"] { font-size: 24px; color: #004085; }
    /* Boutons */
    .stButton>button { 
        background-color: #004085; 
        color: white; 
        border-radius: 4px; 
        border: none;
        height: 3em;
        font-weight: bold;
    }
    .stButton>button:hover { background-color: #0056b3; }
    /* Alertes */
    .stAlert { border-radius: 4px; border-left: 5px solid #ffc107; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR : PARAMÈTRES TECHNIQUES ---
st.sidebar.title("Paramètres Techniques")
st.sidebar.caption("Site : Carrière Benslimane")

# 1. Caractérisation du Massif
st.sidebar.header("1. Caractérisation Géologique")
geology_type = st.sidebar.selectbox(
    "Faciès Dominant",
    ["Gréso-Pélitique (Viséen)", "Psammites (Ordovicien)", "Calcaire Franc", "Zone de Faille / Altérée"],
    index=0
)

# Calibrage Technique (Hard-coded Logic)
if geology_type == "Gréso-Pélitique (Viséen)":
    rec_pf = 0.55
    rec_burden = 3.5
    rec_spacing = 4.0
    rock_hardness = "Moyenne/Dure"
    abrasivity = "Moyenne"
    density_val = 2.70
    quality_note = "Risque de fines argileuses (Scalpage requis)."
    clay_risk = "MODÉRÉ"
elif geology_type == "Psammites (Ordovicien)":
    rec_pf = 0.65
    rec_burden = 3.2
    rec_spacing = 3.8
    rock_hardness = "TRÈS DURE"
    abrasivity = "Élevée (Usure foration)"
    density_val = 2.75
    quality_note = "Excellent granulat (Béton HP)."
    clay_risk = "FAIBLE"
elif geology_type == "Calcaire Franc":
    rec_pf = 0.45
    rec_burden = 3.5
    rec_spacing = 4.2
    rock_hardness = "Moyenne"
    abrasivity = "Faible"
    density_val = 2.65
    quality_note = "Standard."
    clay_risk = "NUL"
else: # Zone Altérée
    rec_pf = 0.50
    rec_burden = 3.5
    rec_spacing = 4.0
    rock_hardness = "Faible"
    abrasivity = "Faible"
    density_val = 2.50
    quality_note = "Matériau stérile probable."
    clay_risk = "ÉLEVÉ"

st.sidebar.text(f"Densité Ref: {density_val} t/m³")

# 2. Objectifs
st.sidebar.header("2. Objectifs de Production")
target_tons = st.sidebar.number_input("Cible Tonnage (T)", min_value=1000, value=20000, step=500)

# 3. Design de Tir
st.sidebar.header("3. Géométrie de Foration")
st.sidebar.caption(f"Recommandation : {rec_burden}m x {rec_spacing}m")
burden = st.sidebar.number_input("Banquette (B) [m]", min_value=1.5, max_value=6.0, value=rec_burden, step=0.1)
spacing = st.sidebar.number_input("Espacement (S) [m]", min_value=1.5, max_value=7.0, value=rec_spacing, step=0.1)
bench_height = st.sidebar.slider("Hauteur de Gradin (H) [m]", 6.0, 15.0, 10.0)
hole_diameter = st.sidebar.selectbox("Diamètre Foration [mm]", [76, 89, 102], index=1)

# 4. Chargement
st.sidebar.header("4. Plan de Chargement")
pf_target = st.sidebar.number_input("Charge Spécifique (q) [kg/m³]", 0.15, 1.2, rec_pf, 0.01)
sub_drill = st.sidebar.number_input("Surforation (J) [m]", 0.0, 2.0, 1.0, 0.1)
stemming_m = st.sidebar.number_input("Bourrage (T) [m]", 1.0, 5.0, 2.5, 0.1)

# 5. Économie
with st.sidebar.expander("Paramètres Économiques (Coûts)"):
    cost_drill_m = st.number_input("Foration (DH/m)", value=35.0 if abrasivity == "Élevée (Usure foration)" else 28.0)
    cost_ammonix = st.number_input("Ammonix (DH/kg)", value=17.55)
    cost_emulsion = st.number_input("Émulsion (DH/kg)", value=46.00)
    cost_detonator = st.number_input("Accessoires (Unité)", value=85.00)
    fixed_fees = st.number_input("Frais Fixes (DH)", value=7000.0)

# --- CALCULATEUR (ENGINE) ---
hole_depth = bench_height + sub_drill
vol_solid_per_hole = burden * spacing * bench_height
tonnage_per_hole = vol_solid_per_hole * density_val

# Explosifs
total_explosive_target = vol_solid_per_hole * pf_target
emulsion_per_hole = 5.0 # Standard booster
ammonix_per_hole = total_explosive_target - emulsion_per_hole

# Contraintes Physiques
charge_length_available = hole_depth - stemming_m - 0.5 
linear_charge_density = (np.pi * ((hole_diameter/1000)/2)**2) * 850 
max_ammo_capacity = charge_length_available * linear_charge_density

# Flotte
num_holes = int(np.ceil(target_tons / tonnage_per_hole))
total_drill_meters = num_holes * hole_depth
total_ammonix = num_holes * ammonix_per_hole
total_emulsion = num_holes * emulsion_per_hole
total_vol = num_holes * vol_solid_per_hole

# Finance
c_drill = total_drill_meters * cost_drill_m
c_ammo = total_ammonix * cost_ammonix
c_emul = total_emulsion * cost_emulsion
c_acc = num_holes * cost_detonator
total_ht = c_drill + c_ammo + c_emul + c_acc + fixed_fees
total_ttc = total_ht * 1.20
cost_per_ton = total_ht / target_tons

# Alertes Techniques
alerts = []
if ammonix_per_hole > max_ammo_capacity:
    alerts.append(f"CRITIQUE: Surcharge Explosive. Capacité trou ({max_ammo_capacity:.1f}kg) < Besoin ({ammonix_per_hole:.1f}kg).")
if burden > spacing:
    alerts.append("GÉOMÉTRIE INCORRECTE: La Banquette (B) ne doit pas être supérieure à l'Espacement (S).")
if stemming_m < burden * 0.7:
    alerts.append("SÉCURITÉ: Bourrage insuffisant. Risque de projections.")

# --- VISUALISATION (MATPLOTLIB PRO) ---
def plot_pattern_technical(rows, cols, num_holes, B, S):
    fig, ax = plt.subplots(figsize=(8, 4))
    hole_count = 0
    x_coords, y_coords = [], []
    for r in range(rows):
        for c in range(cols):
            if hole_count < num_holes:
                x = c * S
                y = r * B * -1
                if r % 2 != 0: x += (S / 2)
                x_coords.append(x)
                y_coords.append(y)
                hole_count += 1
    
    ax.scatter(x_coords, y_coords, c='white', s=60, edgecolors='#004085', linewidth=2, zorder=3, label="Trou Foration")
    ax.axhline(y=B*0.5, color='#d9534f', linestyle='--', linewidth=2, label="Front Libre (Théorique)")
    
    ax.set_title(f"Plan de Tir : Maille {B}m x {S}m (Quinconce)", fontsize=10, pad=10)
    ax.set_xlabel("Espacement (m)", fontsize=8)
    ax.set_ylabel("Banquette (m)", fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.5, color='grey')
    ax.legend(loc='upper right', fontsize=8)
    ax.set_aspect('equal')
    return fig

rows = int(np.ceil(np.sqrt(num_holes)))
cols = int(np.ceil(num_holes / rows)) + 1
fig_plan = plot_pattern_technical(rows, cols, num_holes, burden, spacing)

# --- GÉNÉRATION PDF (RAPPORT TECHNIQUE) ---
def generate_technical_report():
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    styles = getSampleStyleSheet()
    
    # Custom Table Styles to Fix Text Overlap
    style_table_text = ParagraphStyle('TableText', parent=styles['Normal'], fontSize=9, leading=11, wordWrap='CJK')
    
    # Header
    elements.append(Paragraph("RAPPORT TECHNIQUE DE TIR", styles['Title']))
    elements.append(Paragraph(f"<b>Site :</b> Carrière Benslimane &nbsp;&nbsp;|&nbsp;&nbsp; <b>Date :</b> {pd.Timestamp.now().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(Paragraph(f"<b>Opérateur :</b> Admin &nbsp;&nbsp;|&nbsp;&nbsp; <b>Ref :</b> BL-{pd.Timestamp.now().strftime('%Y%m%d')}", styles['Normal']))
    elements.append(Spacer(1, 1*cm))
    
    # Section 1: Synthèse
    # We use Paragraph objects inside the table to allow text wrapping!
    p_tonnage = Paragraph(f"{target_tons:,.0f} T", style_table_text)
    p_density = Paragraph(f"Densité retenue : {density_val}", style_table_text)
    p_geo = Paragraph(f"{burden}m x {spacing}m", style_table_text)
    p_maille = Paragraph(f"Maille : {burden*spacing:.1f} m²", style_table_text)
    p_pf = Paragraph(f"{pf_target:.2f} kg/m³", style_table_text)
    p_hard = Paragraph(f"Dureté : {rock_hardness}", style_table_text)
    p_drill = Paragraph(f"{total_drill_meters:,.0f} m", style_table_text)
    p_holes = Paragraph(f"{num_holes} Trous ({hole_diameter}mm)", style_table_text)
    p_quality = Paragraph(quality_note, style_table_text)
    p_risk = Paragraph(f"Risque Argile : {clay_risk}", style_table_text)

    data_synth = [
        ["PARAMÈTRE", "VALEUR", "NOTES TECHNIQUE"],
        ["Objectif Tonnage", p_tonnage, p_density],
        ["Géométrie (B x S)", p_geo, p_maille],
        ["Charge Spécifique", p_pf, p_hard],
        ["Foration Totale", p_drill, p_holes],
        ["Qualité Attendue", p_quality, p_risk]
    ]
    
    # Adjusted Column Widths to give more space for text
    t_synth = Table(data_synth, colWidths=[4*cm, 7*cm, 6*cm])
    t_synth.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), '#004085'),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), # Vertically center
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('PADDING', (0,0), (-1,-1), 8), # More padding to avoid smashed look
    ]))
    elements.append(t_synth)
    elements.append(Spacer(1, 1*cm))
    
    # Section 2: Image Plan
    img_buf = BytesIO()
    fig_plan.savefig(img_buf, format='png', dpi=100, bbox_inches='tight')
    img_buf.seek(0)
    elements.append(Image(img_buf, width=14*cm, height=10*cm))
    elements.append(Spacer(1, 1*cm))
    
    # Section 3: Économie
    elements.append(Paragraph("<b>ESTIMATION BUDGÉTAIRE PRÉVISIONNELLE</b>", styles['Heading3']))
    
    p_drill_cost = Paragraph(f"{c_drill:,.0f} DH", style_table_text)
    p_expl_cost = Paragraph(f"{c_ammo+c_emul:,.0f} DH", style_table_text)
    p_acc_cost = Paragraph(f"{c_acc+fixed_fees:,.0f} DH", style_table_text)
    p_total_cost = Paragraph(f"<b>{total_ht:,.0f} DH</b>", style_table_text)
    
    data_cost = [
        ["POSTE DE DÉPENSE", "MONTANT (HT)", "% DU TOTAL"],
        ["Foration", p_drill_cost, f"{c_drill/total_ht*100:.1f}%"],
        ["Explosifs (Ammonix + Emulsion)", p_expl_cost, f"{(c_ammo+c_emul)/total_ht*100:.1f}%"],
        ["Accessoires & Fixes", p_acc_cost, f"{(c_acc+fixed_fees)/total_ht*100:.1f}%"],
        ["TOTAL HT", p_total_cost, "100%"],
        ["COÛT UNITAIRE", f"{cost_per_ton:.2f} DH/T", "-"],
    ]
    t_cost = Table(data_cost, colWidths=[8*cm, 4*cm, 4*cm])
    t_cost.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), '#e9ecef'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,4), (-1,5), '#d4edda'), # Green tint for totals
    ]))
    elements.append(t_cost)
    
    # Footer
    elements.append(Spacer(1, 1*cm))
    elements.append(Paragraph("<i>Document généré automatiquement par le système SGT. Validé pour exécution.</i>", styles['Italic']))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- INTERFACE PRINCIPALE ---
st.title("Système de Gestion de Tir (SGT)")
st.markdown("### Tableau de Bord Technique")

# Top Metrics Row
c1, c2, c3, c4 = st.columns(4)
c1.metric("Production Cible", f"{target_tons/1000:.1f} kT")
c2.metric("Maille", f"{burden}x{spacing}", delta="Géométrie")
c3.metric("Charge Spécifique", f"{pf_target} kg/m³")
c4.metric("Coût Unitaire", f"{cost_per_ton:.2f} DH/T", delta_color="inverse")

# Alertes
for alert in alerts:
    st.error(f"⚠️ {alert}")

# Onglets Contenu
tab1, tab2 = st.tabs(["📈 Analyse Technique & Financière", "📄 Rapport & Export"])

with tab1:
    col_graph, col_data = st.columns([2, 1])
    
    with col_graph:
        st.subheader("Plan de Tir (Vue Dessus)")
        st.pyplot(fig_plan)
        st.info(f"**Analyse Qualité ({geology_type}):**\n{quality_note}")
        
    with col_data:
        st.subheader("Détail des Coûts")
        df_costs = pd.DataFrame({
            "Poste": ["Foration", "Explosifs", "Accessoires", "Frais Fixes"],
            "Coût (DH)": [c_drill, c_ammo+c_emul, c_acc, fixed_fees]
        })
        st.dataframe(df_costs.style.format({"Coût (DH)": "{:,.0f}"}), hide_index=True)
        st.markdown("---")
        st.markdown(f"**Total TTC :** {total_ttc:,.0f} DH")

with tab2:
    st.subheader("Génération de Rapport")
    st.write("Ce module génère un PDF standardisé pour les équipes techniques et la direction.")
    
    if st.button("Générer le Rapport Technique (PDF)"):
        pdf_file = generate_technical_report()
        st.download_button(
            label="⬇️ Télécharger le Rapport Officiel",
            data=pdf_file,
            file_name=f"Rapport_Tir_BL_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
