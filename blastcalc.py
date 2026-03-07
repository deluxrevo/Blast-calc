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

st.sidebar.subheader("1. Geology & Production")
target_tons = st.sidebar.number_input("Target Tonnage (Tons)", min_value=1000, value=12000, step=500)
rock_condition = st.sidebar.selectbox("Rock Type", 
                                 ["Mix: Schist/Quartzite (Standard)", "HARD: Dolerite/Basalt (Tough)"],
                                 help="Select HARD if you are seeing black rock and breakage.")

st.sidebar.subheader("2. Bench Geometry")
bench_height = st.sidebar.slider("Bench Height (m)", 6.0, 15.0, 10.0, help="10m-12m is best. 6m is inefficient.")
hole_diameter = st.sidebar.selectbox("Hole Diameter (mm)", [76, 89, 102], index=1)
rock_density = st.sidebar.number_input("Rock Density (t/m3)", value=2.7, step=0.1)

st.sidebar.subheader("3. Unit Costs (HT)")
cost_drill_m = st.sidebar.number_input("Drilling (MAD/m)", value=28.0)
cost_ammonix = st.sidebar.number_input("Ammonix (MAD/kg)", value=17.55)
cost_emulsion = st.sidebar.number_input("Emulsion (MAD/kg)", value=46.00)
cost_detonator = st.sidebar.number_input("Detonator (Unit)", value=68.00)

st.sidebar.subheader("4. Fixed Fees (Per Blast)")
fixed_fees = st.sidebar.number_input("Transport/Guard/Service (MAD)", value=7000.0, help="Add Prestation, Transport, CIS here.")

# --- LOGIC ENGINE ---

# Geology Logic
if rock_condition == "Mix: Schist/Quartzite (Standard)":
    burden = 3.0
    spacing = 3.0
    pf_target = 0.55  # kg/m3
    stemming_m = 2.5
    sub_drill = 1.0
    rock_note = "Standard Pattern (3x3). Good for Mix."
else: # Hard Dolerite
    burden = 2.7  # Tighter!
    spacing = 3.0
    pf_target = 0.65  # Higher Energy!
    stemming_m = 2.2
    sub_drill = 1.2
    rock_note = "Tight Pattern (2.7x3.0). Required for Hard Black Rock."

# Calculations
hole_depth = bench_height + sub_drill
vol_solid_per_hole = burden * spacing * bench_height
mass_per_hole = vol_solid_per_hole * rock_density

# Explosives
total_explosive_target = vol_solid_per_hole * pf_target
emulsion_per_hole = 5.0 # Fixed booster
ammonix_per_hole = total_explosive_target - emulsion_per_hole

# Fleet
num_holes = int(np.ceil(target_tons / mass_per_hole))
total_drill_meters = num_holes * hole_depth
total_ammonix = num_holes * ammonix_per_hole
total_emulsion = num_holes * emulsion_per_hole
total_volume_rock = num_holes * vol_solid_per_hole

# Financials
c_drill = total_drill_meters * cost_drill_m
c_ammo = total_ammonix * cost_ammonix
c_emul = total_emulsion * cost_emulsion
c_acc = num_holes * (cost_detonator + 15) # +15 for wire
total_ht = c_drill + c_ammo + c_emul + c_acc + fixed_fees
total_ttc = total_ht * 1.20
cost_per_ton = total_ht / target_tons

# --- PLOTTING FUNCTIONS ---

def create_pattern_plot(rows, cols, num_holes, burden, spacing):
    fig, ax = plt.subplots(figsize=(8, 5))
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
                
    ax.scatter(x_coords, y_coords, c='red', s=80, edgecolors='black', zorder=3)
    # Draw Free Face
    ax.axhline(y=burden*0.5, color='blue', linestyle='--', linewidth=2, label="Free Face")
    ax.set_title(f"Drill Pattern: {burden}m x {spacing}m (Staggered)", fontsize=10)
    ax.set_xlabel("Face Width (m)")
    ax.set_ylabel("Distance Back (m)")
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()
    return fig

def create_hole_profile(depth, sub, stem, ammo_h):
    fig, ax = plt.subplots(figsize=(3, 6))
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
    ax.legend(loc='upper right', fontsize='small')
    ax.set_title("Hole Charge", fontsize=10)
    return fig

# Generate Plots
rows = int(np.ceil(np.sqrt(num_holes)))
cols = int(np.ceil(num_holes / rows)) + 1
fig_pattern = create_pattern_plot(rows, cols, num_holes, burden, spacing)
fig_profile = create_hole_profile(hole_depth, sub_drill, stemming_m, hole_depth - stemming_m - sub_drill - 0.5)

# --- REPLACE THE ENTIRE generate_pdf FUNCTION WITH THIS ---

def generate_pdf(pattern_fig, profile_fig, num_holes, burden, spacing, hole_depth, 
                 sub_drill, stemming, ammo_kg, emul_kg, drill_m, total_ht, total_ttc):
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    
    # 1. HEADER (Title & Project Info)
    title_style = ParagraphStyle('TitleCustom', parent=styles['Title'], fontSize=18, spaceAfter=12)
    elements.append(Paragraph("BLAST ENGINEERING ORDER (ORDRE DE TIR)", title_style))
    elements.append(Paragraph(f"<b>Project:</b> Benslimane Quarry | <b>Rock:</b> {rock_condition}", styles['Normal']))
    elements.append(Paragraph(f"<b>Date:</b> {pd.Timestamp.now().strftime('%Y-%m-%d')} | <b>Target:</b> {target_tons:,.0f} Tons", styles['Normal']))
    elements.append(Spacer(1, 20))

    # 2. KEY METRICS (Top Summary Box)
    summary_data = [
        ["TOTAL HOLES", "HOLE DEPTH", "PATTERN", "POWDER FACTOR"],
        [f"{num_holes}", f"{hole_depth} m", f"{burden}m x {spacing}m", f"{pf_target} kg/m³"]
    ]
    t_summary = Table(summary_data, colWidths=[120, 100, 120, 120])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('SIZE', (0,0), (-1,-1), 10),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 20))

    # 3. IMAGES (Side-by-Side: Pattern Left | Profile Right)
    # Convert Plots to Images
    img_buf1 = BytesIO()
    pattern_fig.savefig(img_buf1, format='png', dpi=100, bbox_inches='tight')
    img_buf1.seek(0)
    
    img_buf2 = BytesIO()
    profile_fig.savefig(img_buf2, format='png', dpi=100, bbox_inches='tight')
    img_buf2.seek(0)
    
    # Create a Table to hold images side-by-side
    img_table_data = [[Image(img_buf1, width=300, height=200), Image(img_buf2, width=150, height=250)]]
    t_images = Table(img_table_data, colWidths=[320, 180])
    t_images.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),  # Align Pattern Left
        ('ALIGN', (1,0), (1,0), 'RIGHT') # Align Profile Right
    ]))
    elements.append(t_images)
    elements.append(Spacer(1, 10))

    # 4. LOADING INSTRUCTIONS (Text under the Profile)
    instr_style = ParagraphStyle('Instr', parent=styles['Normal'], fontSize=10, leading=14)
    instructions = f"""
    <b>LOADING INSTRUCTIONS:</b><br/>
    • <b>Sub-Drill (Surforation):</b> {sub_drill} m (Essential for Toe)<br/>
    • <b>Stemming (Bourrage):</b> {stemming} m (GRAVEL ONLY - NO DIRT)<br/>
    • <b>Explosive Column:</b> {hole_depth - stemming - sub_drill - 0.5:.1f} m<br/>
    • <b>Booster:</b> 1 Emulsion Cartridge at Bottom.<br/>
    • <b>Main Charge:</b> {ammo_kg / num_holes:.1f} kg Ammonix per hole.
    """
    elements.append(Paragraph(instructions, instr_style))
    elements.append(Spacer(1, 20))

    # 5. FINANCIAL TABLE (Bottom)
    elements.append(Paragraph("<b>ESTIMATED COST BREAKDOWN (DEVIS)</b>", styles['Heading4']))
    cost_data = [
        ["ITEM", "QUANTITY", "UNIT PRICE", "TOTAL (HT)"],
        ["Drilling (Forage)", f"{drill_m:,.0f} m", f"{cost_drill_m} DH", f"{c_drill:,.0f}"],
        ["Ammonix", f"{ammo_kg:,.0f} kg", f"{cost_ammonix} DH", f"{c_ammo:,.0f}"],
        ["Emulsion", f"{emul_kg:,.0f} kg", f"{cost_emulsion} DH", f"{c_emul:,.0f}"],
        ["Accessories (Det/Fil)", f"{num_holes} u", "Var", f"{c_acc:,.0f}"],
        ["Fixed Fees (Transport/CIS)", "1", f"{fixed_fees} DH", f"{fixed_fees:,.0f}"],
        ["<b>TOTAL HT</b>", "", "", f"<b>{total_ht:,.0f} DH</b>"],
        ["<b>TOTAL TTC (20%)</b>", "", "", f"<b>{total_ttc:,.0f} DH</b>"]
    ]
    t_cost = Table(cost_data, colWidths=[140, 100, 100, 120])
    t_cost.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,6), (-1,7), colors.lightblue), # Highlight Totals
        ('FONTNAME', (0,6), (-1,7), 'Helvetica-Bold'),
    ]))
    elements.append(t_cost)

    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- UPDATE THE BUTTON CALL IN MAIN APP ---
if st.button("📄 Generate PDF Report"):
    pdf_file = generate_pdf(fig_pattern, fig_profile, num_holes, burden, spacing, 
                            hole_depth, sub_drill, stemming_m, total_ammonix, 
                            total_emulsion, total_drill_meters, total_ht, total_ttc)
    
    st.download_button(
        label="⬇️ Download Official Order",
        data=pdf_file,
        file_name=f"Blast_Order_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf"
    )

# --- MAIN DASHBOARD LAYOUT ---
st.title("🚀 Quarry Blast Optimizer")
st.caption("Professional Engineering Tool for Schist/Quartzite/Dolerite Mix")

# Top Metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Production", f"{target_tons:,.0f} T")
m2.metric("Drill Pattern", f"{burden}m x {spacing}m")
m3.metric("Explosives", f"{total_ammonix+total_emulsion:,.0f} kg")
m4.metric("Cost TTC", f"{total_ttc:,.0f} MAD")

# Warning Logic
if bench_height < 9.0:
    st.error("⚠️ WARNING: Bench Height < 9m. Shallow holes (6m) waste 40% of energy. Drill deeper!")
if rock_condition == "HARD: Dolerite/Basalt (Tough)" and burden > 2.8:
    st.warning("⚠️ High Risk: Burden > 2.8m in Dolerite creates Boulders.")

# Tabs
tab1, tab2, tab3 = st.tabs(["📊 Visual Plan", "💰 Cost Breakdown", "📄 PDF Report"])

with tab1:
    c1, c2 = st.columns([3, 1])
    with c1:
        st.pyplot(fig_pattern)
    with c2:
        st.pyplot(fig_profile)
        st.info(f"**Instructions:**\n\n1. Drill {hole_depth}m.\n2. Stemming: {stemming_m}m (Gravel only).\n3. Paint spots {burden}m apart.")

with tab2:
    st.dataframe(pd.DataFrame({
        "Category": ["Drilling", "Ammonix", "Emulsion", "Accessories", "Fixed Fees"],
        "Cost (HT)": [c_drill, c_ammo, c_emul, c_acc, fixed_fees],
        "% of Budget": [c_drill/total_ht*100, c_ammo/total_ht*100, c_emul/total_ht*100, c_acc/total_ht*100, fixed_fees/total_ht*100]
    }).style.format({"Cost (HT)": "{:,.0f} MAD", "% of Budget": "{:.1f}%"}))
    
    st.success(f"**Cost Per Ton: {cost_per_ton:.2f} MAD/ton**")

with tab3:
    st.write("### Generate Official Report")
    st.write("Click below to download the PDF. You can email this file directly to your team.")
    
    if st.button("📄 Generate PDF Report"):
        pdf_file = generate_pdf()
        st.download_button(
            label="⬇️ Download PDF",
            data=pdf_file,
            file_name="Blast_Plan_Benslimane.pdf",
            mime="application/pdf"
        )
