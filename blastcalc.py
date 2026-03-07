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

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Benslimane Quarry Master", layout="wide", page_icon="💥")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .big-font { font-size:20px !important; font-weight: bold; }
    .stButton>button { width: 100%; border-radius: 5px; background-color: #FF4B4B; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: INPUTS ---
st.sidebar.title("🎛️ Blast Parameters")

st.sidebar.header("1. Production Targets")
target_tons = st.sidebar.number_input("Target Tonnage (Tons)", min_value=1000, value=20000, step=500)
rock_density = st.sidebar.number_input("Rock Density (t/m3)", value=2.7, step=0.1)

st.sidebar.header("2. Drill Pattern (Geometry)")
# Default values set to your "Standard" 3x3
burden = st.sidebar.number_input("Burden (m)", min_value=1.5, max_value=6.0, value=3.0, step=0.1, help="Distance from free face. Keep tight for hard rock!")
spacing = st.sidebar.number_input("Spacing (m)", min_value=1.5, max_value=7.0, value=3.0, step=0.1, help="Distance between holes. Should be 1.0x to 1.3x Burden.")
bench_height = st.sidebar.slider("Bench Height (m)", 6.0, 15.0, 10.0, help="10m-12m is best. 6m is inefficient.")
hole_diameter = st.sidebar.selectbox("Hole Diameter (mm)", [76, 89, 102], index=1)

st.sidebar.header("3. Loading Design")
pf_target = st.sidebar.number_input("Target Powder Factor (kg/m3)", min_value=0.15, max_value=1.0, value=0.55, step=0.01, help="0.55 = Standard. 0.45 = Economy (Schist). 0.65 = Hard (Dolerite).")
sub_drill = st.sidebar.number_input("Sub-Drill (Surforation) (m)", value=1.0, step=0.1, help="Usually 1.0m. Increase to 1.2m for hard toes.")
stemming_m = st.sidebar.number_input("Stemming Height (m)", value=2.5, step=0.1, help="Gravel at top. Usually 20-30x Diameter.")

st.sidebar.header("4. Unit Costs (HT)")
cost_drill_m = st.sidebar.number_input("Drilling (MAD/m)", value=28.0)
cost_ammonix = st.sidebar.number_input("Ammonix (MAD/kg)", value=17.55)
cost_emulsion = st.sidebar.number_input("Emulsion (MAD/kg)", value=46.00)
cost_detonator = st.sidebar.number_input("Detonator (Unit)", value=68.00)

st.sidebar.header("5. Fixed Fees")
fixed_fees = st.sidebar.number_input("Transport/Guard/Service (MAD)", value=7000.0)

# --- LOGIC ENGINE ---

# 1. Geometry Calculations
hole_depth = bench_height + sub_drill
vol_solid_per_hole = burden * spacing * bench_height  # This is the REAL volume per hole
tonnage_per_hole = vol_solid_per_hole * rock_density

# 2. Explosive Load Calculation
total_explosive_target = vol_solid_per_hole * pf_target # Total kg needed per hole
emulsion_per_hole = 5.0 # Fixed booster (approx 1 cartridge + bottom load)
ammonix_per_hole = total_explosive_target - emulsion_per_hole

# Check if hole can physically hold this much explosive
# Cylinder vol - stemming - booster
charge_length_available = hole_depth - stemming_m - 0.5 
# Approx linear density for 89mm hole (kg/m) ~ 5-6 kg/m depending on density
linear_charge_density = (np.pi * ((hole_diameter/1000)/2)**2) * 850 # 0.85 g/cc density for Ammonix roughly
max_ammo_capacity = charge_length_available * linear_charge_density

# If calculated need > capacity, warn user
capacity_warning = ""
if ammonix_per_hole > max_ammo_capacity:
    capacity_warning = f"⚠️ Warning: Hole diameter {hole_diameter}mm is too small for {pf_target} PF. Can only fit {max_ammo_capacity:.1f}kg vs {ammonix_per_hole:.1f}kg needed."

# 3. Fleet & Totals
num_holes = int(np.ceil(target_tons / tonnage_per_hole))
total_drill_meters = num_holes * hole_depth
total_ammonix = num_holes * ammonix_per_hole
total_emulsion = num_holes * emulsion_per_hole
total_volume_rock = num_holes * vol_solid_per_hole

# 4. Financials
c_drill = total_drill_meters * cost_drill_m
c_ammo = total_ammonix * cost_ammonix
c_emul = total_emulsion * cost_emulsion
c_acc = num_holes * (cost_detonator + 15) # +15 for wire
total_ht = c_drill + c_ammo + c_emul + c_acc + fixed_fees
total_ttc = total_ht * 1.20
cost_per_ton = total_ht / target_tons

# --- PLOTTING FUNCTIONS ---

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
                if r % 2 != 0: x += (spacing / 2) # Staggered
                x_coords.append(x)
                y_coords.append(y)
                hole_count += 1
                
    ax.scatter(x_coords, y_coords, c='red', s=50, edgecolors='black', zorder=3)
    # Draw Free Face
    ax.axhline(y=burden*0.5, color='blue', linestyle='--', linewidth=2, label="Free Face")
    ax.set_title(f"Drill Pattern: {burden}m x {spacing}m", fontsize=10)
    ax.set_xlabel("Face Width (m)")
    ax.set_ylabel("Distance Back (m)")
    ax.grid(True, linestyle=':', alpha=0.6)
    return fig

def create_hole_profile(depth, sub, stem, ammo_h):
    fig, ax = plt.subplots(figsize=(2, 6))
    width = 1
    # Layers
    ax.bar(0, sub, bottom=0, width=width, color='black', label='Sub-drill')
    ax.bar(0, 0.5, bottom=sub, width=width, color='red', label='Booster')
    ax.bar(0, ammo_h, bottom=sub+0.5, width=width, color='orange', label='Ammonix')
    ax.bar(0, stem, bottom=depth-stem, width=width, color='grey', hatch='//', label='Gravel')
    
    ax.set_ylim(0, depth+1)
    ax.set_xlim(-1, 1)
    ax.set_ylabel("Meters")
    ax.set_xticks([])
    ax.set_title("Hole", fontsize=10)
    return fig

# Generate Plots
rows = int(np.ceil(np.sqrt(num_holes)))
cols = int(np.ceil(num_holes / rows)) + 1
fig_pattern = create_pattern_plot(rows, cols, num_holes, burden, spacing)
fig_profile = create_hole_profile(hole_depth, sub_drill, stemming_m, hole_depth - stemming_m - sub_drill - 0.5)

# --- PDF GENERATION FUNCTION ---
def generate_pdf(pattern_fig, profile_fig, num_holes, burden, spacing, hole_depth, 
                 sub_drill, stemming, ammo_kg, emul_kg, drill_m, total_ht, total_ttc, pf, t_tons):
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()
    
    # 1. HEADER
    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontSize=16, spaceAfter=10, textColor=colors.darkblue)
    elements.append(Paragraph("BLAST ENGINEERING ORDER (ORDRE DE TIR)", title_style))
    elements.append(Paragraph(f"<b>Project:</b> Benslimane Quarry | <b>Custom Design</b>", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {pd.Timestamp.now().strftime('%Y-%m-%d')} | <b>Target:</b> {t_tons:,.0f} Tons", styles['Normal']))
    elements.append(Spacer(1, 15))

    # 2. KEY METRICS BOX
    summary_data = [
        ["TOTAL HOLES", "HOLE DEPTH", "PATTERN", "POWDER FACTOR"],
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
    <font size=11><b>LOADING INSTRUCTIONS (INSTRUCTIONS DE CHARGEMENT):</b></font><br/>
    1. <b>Sub-Drill (Surforation):</b> {sub_drill} m <font color=red>(Critical for Floor!)</font><br/>
    2. <b>Booster:</b> 1 Emulsion Cartridge at bottom.<br/>
    3. <b>Explosive Column:</b> {hole_depth - stemming - sub_drill - 0.5:.1f} m of Ammonix.<br/>
    4. <b>Stemming (Bourrage):</b> {stemming} m <font color=red><b>(CLEAN GRAVEL ONLY)</b></font>
    """
    elements.append(Paragraph(instr_text, styles['Normal']))
    elements.append(Spacer(1, 15))

    # 5. COSTS
    elements.append(Paragraph("<b>ESTIMATED COST BREAKDOWN (DEVIS)</b>", styles['Heading4']))
    cost_data = [
        ["ITEM", "QUANTITY", "UNIT PRICE", "TOTAL (HT)"],
        ["Drilling (Forage)", f"{drill_m:,.0f} m", f"{cost_drill_m} DH", f"{c_drill:,.0f}"],
        ["Ammonix", f"{ammo_kg:,.0f} kg", f"{cost_ammonix} DH", f"{c_ammo:,.0f}"],
        ["Emulsion", f"{emul_kg:,.0f} kg", f"{cost_emulsion} DH", f"{c_emul:,.0f}"],
        ["Accessories", f"{num_holes} u", "Var", f"{c_acc:,.0f}"],
        ["Fixed Fees", "1", f"{fixed_fees} DH", f"{fixed_fees:,.0f}"],
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

# --- MAIN DASHBOARD LAYOUT ---
st.title("🚀 Quarry Blast Optimizer")
st.caption("Advanced Custom Design Mode")

# Top Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Production", f"{target_tons:,.0f} T")
m2.metric("Pattern", f"{burden}m x {spacing}m")
m3.metric("Explosives", f"{total_ammonix+total_emulsion:,.0f} kg")
m4.metric("Cost TTC", f"{total_ttc:,.0f} MAD")

# Warnings
if capacity_warning:
    st.error(capacity_warning)
if bench_height < 9.0:
    st.warning("⚠️ Bench Height < 9m. Efficiency drops significantly below 10m.")
if burden > 3.5:
    st.warning("⚠️ Wide Pattern Alert: Burden > 3.5m risks boulders in hard rock.")
if pf_target < 0.35:
    st.error("⛔ DANGER: Powder Factor < 0.35. Guaranteed Boulders/Toes.")

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Visual Plan", "💰 Cost Breakdown", "📄 PDF Report"])

with tab1:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.pyplot(fig_pattern)
    with c2:
        st.pyplot(fig_profile)
        st.info(f"**Quick Stats:**\n\n- Holes: {num_holes}\n- Meters: {total_drill_meters:,.0f}m\n- PF: {pf_target} kg/m³")

with tab2:
    st.dataframe(pd.DataFrame({
        "Category": ["Drilling", "Ammonix", "Emulsion", "Accessories", "Fixed Fees"],
        "Cost (HT)": [c_drill, c_ammo, c_emul, c_acc, fixed_fees],
        "% of Budget": [c_drill/total_ht*100, c_ammo/total_ht*100, c_emul/total_ht*100, c_acc/total_ht*100, fixed_fees/total_ht*100]
    }).style.format({"Cost (HT)": "{:,.0f} MAD", "% of Budget": "{:.1f}%"}))
    
    st.success(f"**Unit Cost: {cost_per_ton:.2f} MAD/ton**")

with tab3:
    st.write("### Generate Official Report")
    st.write("Click below to download the Order.")
    
    if st.button("📄 Generate PDF Report", key="pdf_btn"):
        pdf_file = generate_pdf(fig_pattern, fig_profile, num_holes, burden, spacing, 
                                hole_depth, sub_drill, stemming_m, total_ammonix, 
                                total_emulsion, total_drill_meters, total_ht, total_ttc, pf_target, target_tons)
        
        st.download_button(
            label="⬇️ Download Custom Order",
            data=pdf_file,
            file_name=f"Blast_Order_{burden}x{spacing}_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
