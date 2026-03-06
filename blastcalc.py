import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Benslimane Quarry Blast Master", layout="wide")

# --- CSS FOR PROFESSIONAL LOOK ---
st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #2E86C1; }
    .metric-box { border: 1px solid #ddd; padding: 15px; border-radius: 5px; background-color: #f9f9f9; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: INPUTS ---
st.sidebar.header("1. Production Targets")
target_tons = st.sidebar.number_input("Target Tonnage (Tons)", min_value=1000, value=12000, step=500)
rock_type = st.sidebar.selectbox("Rock Condition", 
                                 ["Mix: Schist/Quartzite (Standard)", "Hard: Dolerite/Basalt (Tough)"])

st.sidebar.header("2. Bench Geometry")
bench_height = st.sidebar.number_input("Bench Height (m)", value=10.0)
hole_diameter = st.sidebar.selectbox("Hole Diameter (mm)", [76, 89, 102], index=1)
rock_density = st.sidebar.number_input("Rock Density (t/m3)", value=2.7, step=0.1)

st.sidebar.header("3. Costs (MAD - HT)")
cost_drill_m = st.sidebar.number_input("Drilling Cost (MAD/m)", value=28.0)
cost_ammonix = st.sidebar.number_input("Ammonix Price (MAD/kg)", value=17.55)
cost_emulsion = st.sidebar.number_input("Emulsion Price (MAD/kg)", value=46.00)
cost_detonator = st.sidebar.number_input("Detonator Unit Price (MAD)", value=68.00)

# --- LOGIC ENGINE ---

# 1. Set Parameters based on Rock Type (The "Secret Sauce")
if rock_type == "Mix: Schist/Quartzite (Standard)":
    burden = 3.0
    spacing = 3.0
    pf_target = 0.55  # kg/m3
    stemming = 2.5
    sub_drill = 1.0
else: # Hard Dolerite
    burden = 2.8
    spacing = 3.0
    pf_target = 0.65  # kg/m3 (Needs more power)
    stemming = 2.2
    sub_drill = 1.2

# 2. Geometry Calculations
hole_depth = bench_height + sub_drill
vol_per_hole_solid = burden * spacing * bench_height
mass_per_hole = vol_per_hole_solid * rock_density

# 3. Explosive Calculations
total_explosive_needed_per_hole = vol_per_hole_solid * pf_target
# Bottom charge (Emulsion) is usually fixed amount for booster
emulsion_per_hole = 5.0 # kg (1 cartridge/bag)
# Column charge (Ammonix) is the rest
ammonix_per_hole = total_explosive_needed_per_hole - emulsion_per_hole

# 4. Fleet Calculations
num_holes = int(np.ceil(target_tons / mass_per_hole))
total_drill_meters = num_holes * hole_depth
total_ammonix = num_holes * ammonix_per_hole
total_emulsion = num_holes * emulsion_per_hole

# 5. Financials
cost_total_drilling = total_drill_meters * cost_drill_m
cost_total_ammonix = total_ammonix * cost_ammonix
cost_total_emulsion = total_emulsion * cost_emulsion
cost_total_accessories = num_holes * (cost_detonator + 15) # +15 for wire/connectors
total_blast_cost = cost_total_drilling + cost_total_ammonix + cost_total_emulsion + cost_total_accessories
cost_per_ton = total_blast_cost / target_tons

# --- MAIN DASHBOARD ---

st.title("💥 Quarry Blast Optimizer")
st.markdown("### Optimized for Benslimane Geology (Schist/Quartzite Mix)")

# TOP METRICS ROW
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Holes Needed", f"{num_holes} Holes")
with col2:
    st.metric("Total Drilling", f"{total_drill_meters:,.0f} m")
with col3:
    st.metric("Powder Factor", f"{pf_target} kg/m³")
with col4:
    st.metric("EST. COST PER TON", f"{cost_per_ton:.2f} MAD", delta_color="inverse")

# --- TABS FOR DETAILS ---
tab1, tab2, tab3 = st.tabs(["📊 Drill Pattern (Blueprint)", "🧪 Loading Recipe", "💰 Financial Report"])

with tab1:
    st.subheader(f"Pattern: {burden}m x {spacing}m Staggered (Quinconce)")
    
    # GENERATE PATTERN PLOT
    rows = int(np.ceil(np.sqrt(num_holes)))
    cols = int(np.ceil(num_holes / rows))
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    hole_count = 0
    x_coords = []
    y_coords = []
    
    for r in range(rows):
        for c in range(cols):
            if hole_count < num_holes:
                # Logic for Quinconce (Staggered)
                x = c * spacing
                y = r * burden * -1 # Negative to draw downwards
                
                if r % 2 != 0: # Odd rows shift right by half spacing
                    x += (spacing / 2)
                
                x_coords.append(x)
                y_coords.append(y)
                hole_count += 1
                
                # Draw Free Face line at top
                if r == 0:
                    ax.add_patch(patches.Rectangle((x-1, 1), 2, 0.5, edgecolor='red', facecolor='none', ls='--'))

    ax.scatter(x_coords, y_coords, c='red', s=100, label='Drill Hole', zorder=3)
    ax.set_title(f"Top View: {num_holes} Holes ({rows} Rows approx.)", fontsize=14)
    ax.set_xlabel("Spacing (Meters)")
    ax.set_ylabel("Burden (Meters)")
    ax.grid(True, linestyle='--', alpha=0.6)
    ax.set_aspect('equal', adjustable='box')
    
    # Annotations
    ax.text(min(x_coords), 2, "FREE FACE / FRONT DE TAILLE", color='red', fontsize=12, fontweight='bold')
    
    st.pyplot(fig)
    st.info("NOTE: Odd rows (1, 3, 5) are standard. Even rows (2, 4) are shifted by 1.5m to create the Triangle effect.")

with tab2:
    col_a, col_b = st.columns([1, 2])
    
    with col_a:
        st.subheader("Hole Profile")
        # Draw Side View
        fig2, ax2 = plt.subplots(figsize=(4, 8))
        
        # Draw the Hole
        hole_width = 1.0
        
        # Subdrill (Yellow)
        ax2.add_patch(patches.Rectangle((0, 0), hole_width, sub_drill, edgecolor='black', facecolor='yellow', label='Sub-drill'))
        # Booster (Black)
        ax2.add_patch(patches.Rectangle((0, sub_drill), hole_width, 0.5, edgecolor='black', facecolor='black', label='Booster'))
        # Ammonix (Orange)
        col_height = hole_depth - stemming - sub_drill - 0.5
        ax2.add_patch(patches.Rectangle((0, sub_drill+0.5), hole_width, col_height, edgecolor='black', facecolor='orange', label='Ammonix'))
        # Stemming (Grey)
        ax2.add_patch(patches.Rectangle((0, hole_depth-stemming), hole_width, stemming, edgecolor='black', facecolor='grey', hatch='///', label='Gravel Stemming'))
        
        ax2.set_xlim(-1, 2)
        ax2.set_ylim(0, hole_depth + 1)
        ax2.set_ylabel("Depth (m)")
        ax2.set_xticks([])
        ax2.legend(loc='upper right')
        ax2.set_title(f"Single Hole: {hole_depth}m")
        st.pyplot(fig2)
        
    with col_b:
        st.subheader("Loading Instructions per Hole")
        st.markdown(f"""
        *   **Total Depth:** {hole_depth} m
        *   **Sub-Drill (Surforation):** {sub_drill} m
        *   **Stemming (Gravette):** {stemming} m (Top)
        *   **Explosive Column:** {hole_depth - stemming:.1f} m
        """)
        
        st.divider()
        
        st.subheader("Explosives Order")
        order_df = pd.DataFrame({
            "Item": ["Ammonix", "Emulsion (Booster)", "Detonators"],
            "Per Hole": [f"{ammonix_per_hole:.1f} kg", f"{emulsion_per_hole:.1f} kg", "1 unit"],
            "Total for Blast": [f"{total_ammonix:,.0f} kg", f"{total_emulsion:,.0f} kg", f"{num_holes + 5} units"]
        })
        st.table(order_df)

with tab3:
    st.subheader("Estimated Invoice (Devis Estimatif)")
    
    invoice_data = {
        "Description": ["Drilling (Forage)", "Ammonix", "Emulsion", "Accessories (Det/Fil)"],
        "Quantity": [f"{total_drill_meters:.0f} m", f"{total_ammonix:.0f} kg", f"{total_emulsion:.0f} kg", f"{num_holes} u"],
        "Unit Price": [f"{cost_drill_m} MAD", f"{cost_ammonix} MAD", f"{cost_emulsion} MAD", "~83 MAD"],
        "Total (HT)": [cost_total_drilling, cost_total_ammonix, cost_total_emulsion, cost_total_accessories]
    }
    
    df_inv = pd.DataFrame(invoice_data)
    st.table(df_inv)
    
    st.success(f"**GRAND TOTAL (HT): {total_blast_cost:,.2f} MAD**")
    st.warning(f"**GRAND TOTAL (TTC - 20%): {total_blast_cost * 1.2:,.2f} MAD**")

# --- DOWNLOAD BUTTON ---
report_text = f"""
BLAST REPORT - BENSLIMANE QUARRY
--------------------------------
Target: {target_tons} Tons
Pattern: {burden}m x {spacing}m (Staggered)
Total Holes: {num_holes}
Depth: {hole_depth}m

EXPLOSIVES:
Ammonix: {total_ammonix:.0f} kg
Emulsion: {total_emulsion:.0f} kg

ESTIMATED COST (TTC): {total_blast_cost * 1.2:,.2f} MAD
"""
st.sidebar.download_button("Download Plan Text", report_text, file_name="blast_plan.txt")
