import streamlit as st
import pandas as pd
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Football Performance Model",
    page_icon="⚽",
    layout="wide"
)

# --- ROLE PRESETS (Section 7) ---
ROLE_WEIGHTS = {
    "CF / Striker": {"wAQC": 0.15, "wHIS": 0.35, "wEC": 0.10, "wTII": 0.10, "wIBI": 0.30},
    "Winger":       {"wAQC": 0.20, "wHIS": 0.30, "wEC": 0.15, "wTII": 0.10, "wIBI": 0.25},
    "AM / 10":      {"wAQC": 0.25, "wHIS": 0.25, "wEC": 0.15, "wTII": 0.15, "wIBI": 0.20},
    "CM / 8":       {"wAQC": 0.30, "wHIS": 0.15, "wEC": 0.30, "wTII": 0.20, "wIBI": 0.05},
    "DM / 6":       {"wAQC": 0.35, "wHIS": 0.10, "wEC": 0.35, "wTII": 0.25, "wIBI": 0.00},
}

# --- HELPER FUNCTIONS ---
def calculate_cav(row):
    """Calculates CAV based on Section 2.2 and applies Mistake Caps from Section 3.1"""
    # Base Formula
    # CAV = (2·DQ + 2·EQ + 1.5·CD + 1.5·TA + 1·LOP) ÷ 8
    raw_score = (2 * row['DQ'] + 2 * row['EQ'] + 1.5 * row['CD'] + 1.5 * row['TA'] + 1 * row['LOP']) / 8
    
    # Mistake Doctrine (Caps)
    mistake = row['Mistake Type']
    cap = 10.0
    if mistake == "Type A (Decision)":
        cap = 4.0 # Cap for Incorrect decision
    elif mistake == "Type B (Execution)":
        cap = 8.3 # Cap for Correct decision, failed execution
    elif mistake == "Type C (Forced)":
        cap = 7.0 # Cap for Forced/contextual error
        
    return min(raw_score, cap)

# --- APP HEADER ---
st.title("Mat's Footy Model")
st.markdown("""
**Framework Basis**: Prioritizing decision quality, contextual correctness, and role responsibility.
""")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["1. Action Log (CAV)", "2. Match Rating (MPR)", "3. Season (CSR)"])

# --- TAB 1: ACTION LOGGING (Multiple Rows) ---
with tab1:
    st.header("Match Action Log")
    st.markdown("Log every meaningful decision point to generate match aggregates.")

    # Initialize Session State for Dataframe if not exists
    if 'match_data' not in st.session_state:
        # Default starting data
        st.session_state.match_data = pd.DataFrame([
            {"Phase": "Build-up", "DQ": 7.0, "EQ": 8.0, "CD": 5.0, "TA": 6.0, "LOP": 4.0, "Mistake Type": "None"},
            {"Phase": "Attacking Transition", "DQ": 9.0, "EQ": 9.0, "CD": 8.0, "TA": 9.0, "LOP": 7.0, "Mistake Type": "None"},
            {"Phase": "Final Third", "DQ": 4.0, "EQ": 5.0, "CD": 6.0, "TA": 5.0, "LOP": 6.0, "Mistake Type": "Type A (Decision)"}
        ])

    # Config for Data Editor
    column_config = {
        "Phase": st.column_config.SelectboxColumn(
            "Phase / Transition",
            options=["Build-up", "Final Third", "Attacking Transition", "Defensive Transition", "Set Piece"],
            required=True
        ),
        "DQ": st.column_config.NumberColumn("DQ (Decision)", min_value=1, max_value=10, step=0.5),
        "EQ": st.column_config.NumberColumn("EQ (Execution)", min_value=1, max_value=10, step=0.5),
        "CD": st.column_config.NumberColumn("CD (Difficulty)", min_value=1, max_value=10, step=0.5),
        "TA": st.column_config.NumberColumn("TA (Tactical)", min_value=1, max_value=10, step=0.5),
        "LOP": st.column_config.NumberColumn("LOP (Pressure)", min_value=1, max_value=10, step=0.5),
        "Mistake Type": st.column_config.SelectboxColumn(
            "Mistake Type",
            options=["None", "Type A (Decision)", "Type B (Execution)", "Type C (Forced)"],
            required=True
        )
    }

    # EDITABLE DATAFRAME
    edited_df = st.data_editor(
        st.session_state.match_data,
        column_config=column_config,
        num_rows="dynamic",
        use_container_width=True,
        key="editor"
    )

    # Calculate CAV for all rows
    if not edited_df.empty:
        # Apply calculation row by row
        edited_df['CAV'] = edited_df.apply(calculate_cav, axis=1)
        
        # Display aggregated metrics
        st.divider()
        st.subheader("Match Aggregates (Auto-Calculated)")
        
        col_a, col_b, col_c = st.columns(3)
        
        # 1. AQC (Average Quality of Choices)
        aqc_val = edited_df['CAV'].mean()
        
        # 2. HIS (High-Impact Share) - % of actions >= 7.0
        high_impact_count = edited_df[edited_df['CAV'] >= 7.0].shape[0]
        total_actions = edited_df.shape[0]
        his_val = high_impact_count / total_actions if total_actions > 0 else 0.0
        
        # 3. Simple Consistency metric (for reference)
        # Using 1 - (StdDev / 10) as a proxy for EC
        std_dev = edited_df['CAV'].std()
        ec_est = 1.0 - (std_dev / 5.0) if total_actions > 1 else 1.0 # arbitrary scaling for visual reference
        ec_est = max(0.0, min(1.0, ec_est))

        col_a.metric("AQC (Avg CAV)", f"{aqc_val:.2f}", help="Mean of all CAVs (1-10)")
        col_b.metric("HIS (High Impact)", f"{his_val:.1%}", help="% of actions with CAV ≥ 7.0")
        col_c.metric("Actions Logged", f"{total_actions}")
        
        # Save to session state for Tab 2
        st.session_state.calculated_aqc = aqc_val
        st.session_state.calculated_his = his_val

# --- TAB 2: MATCH RATING (MPR) ---
with tab2:
    st.header("Match Performance Rating (MPR)")
    
    # Role Selection
    selected_role = st.selectbox("Select Role for Weighting", list(ROLE_WEIGHTS.keys()))
    weights = ROLE_WEIGHTS[selected_role]
    
    col_inputs, col_results = st.columns([1, 1])
    
    with col_inputs:
        st.subheader("1. Metric Inputs")
        
        # Auto-fill from Tab 1 if available
        def_aqc = st.session_state.get('calculated_aqc', 6.5)
        def_his = st.session_state.get('calculated_his', 0.15) * 100 # Convert to 0-100 scale for input
        
        # Inputs (Normalized to 0-100 scale where applicable per Section 6.2)
        aqc_in = st.number_input("AQC (Average Quality) [1-10]", value=float(def_aqc), min_value=1.0, max_value=10.0, format="%.2f")
        his_in = st.number_input("HIS (High Impact %) [0-100]", value=float(def_his), min_value=0.0, max_value=100.0)
        ec_in = st.number_input("EC (Consistency %) [0-100]", value=85.0, min_value=0.0, max_value=100.0, help="1 - Normalized Variance")
        tii_in = st.number_input("TII (Tactical Influence) [0-100]", value=60.0, step=5.0)
        ibi_in = st.number_input("IBI (Individual Brilliance) [0-100]", value=10.0, step=5.0)
        
        st.subheader("2. Modifiers")
        sci_in = st.slider("SCI (Stability Modifier)", 1.0, 1.08, 1.0, help="Capped at +8%")
        om_in = st.number_input("OM (Outcome Multiplier)", 0.5, 1.5, 1.0, step=0.1, help="Goal/Assist Context")
        pi_in = st.number_input("PI (Presence Index)", 0.5, 1.5, 1.0, step=0.1, help="Off-ball Gravity")

    # Calculations
    # Normalize AQC to 0-100 for Weighted Formula (Section 6.2: AQCn = AQC * 10)
    aqc_n = aqc_in * 10
    # Others are already 0-100
    
    # Weighted MPR Formula (Section 6.3)
    weighted_sum = (
        weights['wAQC'] * aqc_n +
        weights['wHIS'] * his_in +
        weights['wEC'] * (ec_in * sci_in) +
        weights['wTII'] * tii_in +
        weights['wIBI'] * ibi_in
    )
    
    final_mpr = weighted_sum * om_in * pi_in

    with col_results:
        st.subheader("Match Results")
        st.metric(f"Weighted MPR ({selected_role})", f"{final_mpr:.1f}", delta="Role Specific")
        
        # Breakdown Chart
        st.markdown("#### Contribution Breakdown")
        chart_data = pd.DataFrame({
            "Component": ["AQC", "HIS", "EC", "TII", "IBI"],
            "Score Contribution": [
                weights['wAQC'] * aqc_n,
                weights['wHIS'] * his_in,
                weights['wEC'] * (ec_in * sci_in),
                weights['wTII'] * tii_in,
                weights['wIBI'] * ibi_in
            ]
        })
        st.bar_chart(chart_data, x="Component", y="Score Contribution")

# --- TAB 3: SEASON EVALUATION (CSR) ---
with tab3:
    st.header("Contextual Season Rating (CSR)")
    st.markdown("Evaluates consistency, ceiling, and transferability (Section 8).")
    
    c1, c2 = st.columns(2)
    
    with c1:
        avg_mpr = st.number_input("Avg_MPR (Mean Weighted Rating)", value=75.0, help="Average of all Weighted MPRs")
        repeatability = st.number_input("Repeatability % (Matches ≥ 70)", value=60.0, help="% of matches with Rating >= 70")
    
    with c2:
        peak5 = st.number_input("Peak5 (Avg of Top 5 Matches)", value=85.0, help="Average rating of best 5 games")
        role_transfer = st.number_input("Role Transferability Score (0-100)", value=70.0, help="Scalability across systems/opponents")

    # CSR Formula (Section 8.2)
    # CSR = 0.45·Avg_MPR + 0.20·Repeatability + 0.15·RoleTransfer + 0.20·Peak5
    csr_score = (0.45 * avg_mpr) + (0.20 * repeatability) + (0.15 * role_transfer) + (0.20 * peak5)

    st.divider()
    st.metric("Final CSR Score", f"{csr_score:.1f}")
    
    st.info("""
    **Interpretation:**
    * **Avg_MPR (45%)**: The floor (Consistency).
    * **Repeatability (20%)**: Reliability threshold.
    * **Peak5 (20%)**: The ceiling (Dominance).
    * **RoleTransfer (15%)**: Context independence.
    """)