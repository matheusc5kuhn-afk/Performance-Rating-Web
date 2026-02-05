import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import os
import json

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="Football Performance Model",
    page_icon="⚽",
    layout="wide"
)

# --- DATA FILES ---
PLAYERS_FILE = "players.csv"
MATCHES_FILE = "matches.csv"
MPRS_FILE = "mprs.json"
TOURNAMENTS_FILE = "tournaments.csv"
STATS_FILE = "stats.json"

# --- DATA LOADING ---
def load_players():
    if os.path.exists(PLAYERS_FILE):
        try:
            df = pd.read_csv(PLAYERS_FILE)
            df['Date Added'] = pd.to_datetime(df['Date Added'], format='mixed')
            return df
        except: pass
    return pd.DataFrame(columns=["Player Name", "Position", "Date Added"])

def load_matches():
    if os.path.exists(MATCHES_FILE):
        try:
            df = pd.read_csv(MATCHES_FILE)
            df['Date'] = pd.to_datetime(df['Date'], format='mixed')
            if 'Tournament' not in df.columns: df['Tournament'] = ""
            return df
        except: pass
    return pd.DataFrame(columns=["Match ID", "Date", "Opponent", "Venue", "Result", "Player", "Tournament"])

def load_tournaments():
    if os.path.exists(TOURNAMENTS_FILE):
        try:
            df = pd.read_csv(TOURNAMENTS_FILE)
            df['Date Added'] = pd.to_datetime(df['Date Added'], format='mixed')
            return df
        except: pass
    return pd.DataFrame(columns=["Tournament ID", "Name", "Date Added"])

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, 'r') as f:
                data = json.load(f)
                for k in data:
                    if 'Timestamp' in data[k]: data[k]['Timestamp'] = datetime.fromisoformat(data[k]['Timestamp'])
                return data
        except: pass
    return {}

def load_mprs():
    if os.path.exists(MPRS_FILE):
        try:
            with open(MPRS_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for mpr in data:
                        if isinstance(mpr, dict) and 'Timestamp' in mpr:
                            mpr['Timestamp'] = datetime.fromisoformat(mpr['Timestamp'])
                    return data
        except: pass
    return []

# --- SAVING FUNCTIONS ---
def save_players(df): df.to_csv(PLAYERS_FILE, index=False)
def save_matches(df): df.to_csv(MATCHES_FILE, index=False)
def save_tournaments(df): df.to_csv(TOURNAMENTS_FILE, index=False)
def save_stats(data):
    d2s = {}
    for k, v in data.items():
        d2s[k] = v.copy()
        if 'Timestamp' in d2s[k]: d2s[k]['Timestamp'] = d2s[k]['Timestamp'].isoformat()
    with open(STATS_FILE, 'w') as f: json.dump(d2s, f)
def save_mprs(data):
    d2s = []
    for mpr in data:
        m = mpr.copy()
        if isinstance(m.get('Timestamp'), datetime): m['Timestamp'] = m['Timestamp'].isoformat()
        d2s.append(m)
    with open(MPRS_FILE, 'w') as f: json.dump(d2s, f)

# --- CALCULATIONS ---
def calculate_cav(row):
    try:
        dq = float(row.get('DQ', 5.5) or 5.5)
        eq = float(row.get('EQ', 5.5) or 5.5)
        cd = float(row.get('CD', 5.5) or 5.5)
        ta = float(row.get('TA', 5.5) or 5.5)
        lop = float(row.get('LOP', 5.5) or 5.5)
        raw_score = (2 * dq + 2 * eq + 1.5 * cd + 1.5 * ta + 1 * lop) / 8
        mistake = row.get('Mistake Type', "None")
        cap = 10.0
        if mistake == "Type A (Decision)": cap = 4.0
        elif mistake == "Type B (Execution)": cap = 8.3
        elif mistake == "Type C (Forced)": cap = 7.0
        return min(raw_score, cap)
    except: return 5.5

def get_calculated_om(p_name, m_id):
    if p_name == "None" or m_id is None: return 1.0
    k = f"{p_name}_m_{m_id}"
    if k in st.session_state.stats:
        g = st.session_state.stats[k].get("Goals", 0)
        a = st.session_state.stats[k].get("Assists", 0)
        return min(1.0 + (g * 0.1) + (a * 0.05), 1.5)
    return 1.0

ROLE_WEIGHTS = {
    "CF / Striker": {"wAQC": 0.15, "wHIS": 0.35, "wEC": 0.10, "wTII": 0.10, "wIBI": 0.30},
    "Winger":       {"wAQC": 0.20, "wHIS": 0.30, "wEC": 0.15, "wTII": 0.10, "wIBI": 0.25},
    "AM / 10":      {"wAQC": 0.25, "wHIS": 0.25, "wEC": 0.15, "wTII": 0.15, "wIBI": 0.20},
    "CM / 8":       {"wAQC": 0.30, "wHIS": 0.15, "wEC": 0.30, "wTII": 0.20, "wIBI": 0.05},
    "DM / 6":       {"wAQC": 0.35, "wHIS": 0.10, "wEC": 0.35, "wTII": 0.25, "wIBI": 0.00},
}

# --- INIT STATE ---
if 'players' not in st.session_state: st.session_state.players = load_players()
if 'matches' not in st.session_state: st.session_state.matches = load_matches()
if 'tournaments' not in st.session_state: st.session_state.tournaments = load_tournaments()
if 'stats' not in st.session_state: st.session_state.stats = load_stats()
if 'general_mprs' not in st.session_state: st.session_state.general_mprs = load_mprs()
if 'match_data' not in st.session_state:
    st.session_state.match_data = pd.DataFrame(columns=["Phase", "DQ", "EQ", "CD", "TA", "LOP", "Mistake Type"])

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ FPM Context")
    p_names = st.session_state.players["Player Name"].tolist() if not st.session_state.players.empty else []
    active_player = st.selectbox("👤 Player", ["None"] + p_names)
    t_names = st.session_state.tournaments["Name"].tolist() if not st.session_state.tournaments.empty else []
    active_tournament = st.selectbox("🏆 Tournament", ["All"] + t_names)
    
    m_label = "None"
    active_m_id = None
    if not st.session_state.matches.empty:
        df_m = st.session_state.matches
        if active_tournament != "All": df_m = df_m[df_m["Tournament"] == active_tournament]
        if not df_m.empty:
            opts = [f"{r['Match ID']}: {r['Opponent']} ({pd.to_datetime(r['Date']).strftime('%m-%d')})" for _, r in df_m.iterrows()]
            m_label = st.selectbox("📅 Match", ["None"] + opts)
            if m_label != "None": active_m_id = int(m_label.split(":")[0])

# --- TABS ---
t1, t2, t3, t4, t5, t6, t7, t8, t9 = st.tabs(["Players", "Tournaments", "Matches", "Action Log", "Rating", "History", "Stats Input", "Season", "Stats Log"])

with t1:
    st.subheader("Manage Players")
    ed_p = st.data_editor(st.session_state.players, num_rows="dynamic", use_container_width=True, key="ed_p")
    if len(ed_p) > len(st.session_state.players): ed_p["Date Added"] = ed_p["Date Added"].fillna(datetime.now())
    if not ed_p.equals(st.session_state.players):
        st.session_state.players = ed_p
        save_players(ed_p)
        st.rerun()

with t2:
    st.subheader("Manage Tournaments")
    ed_t = st.data_editor(st.session_state.tournaments, num_rows="dynamic", use_container_width=True, key="ed_t")
    if len(ed_t) > len(st.session_state.tournaments):
        ed_t["Date Added"] = ed_t["Date Added"].fillna(datetime.now())
        mid = int(st.session_state.tournaments["Tournament ID"].max() if not st.session_state.tournaments.empty else 0)
        new_rows = ed_t[ed_t["Tournament ID"].isna()].index
        for i, idx in enumerate(new_rows): ed_t.at[idx, "Tournament ID"] = mid + 1 + i
    if not ed_t.equals(st.session_state.tournaments):
        st.session_state.tournaments = ed_t
        save_tournaments(ed_t)
        st.rerun()

with t3:
    st.subheader("Manage Matches")
    p_l = st.session_state.players["Player Name"].tolist() if not st.session_state.players.empty else []
    t_l = st.session_state.tournaments["Name"].tolist() if not st.session_state.tournaments.empty else []
    ed_m = st.data_editor(st.session_state.matches, num_rows="dynamic", use_container_width=True, column_config={
        "Player": st.column_config.SelectboxColumn(options=p_l),
        "Tournament": st.column_config.SelectboxColumn(options=[""] + t_l),
        "Date": st.column_config.DateColumn()
    }, key="ed_m")
    if len(ed_m) > len(st.session_state.matches):
        mid = int(st.session_state.matches["Match ID"].max() if not st.session_state.matches.empty else 0)
        new_rows = ed_m[ed_m["Match ID"].isna()].index
        for i, idx in enumerate(new_rows): 
            ed_m.at[idx, "Match ID"] = mid + 1 + i
            if active_player != "None": ed_m.at[idx, "Player"] = active_player
    if not ed_m.equals(st.session_state.matches):
        st.session_state.matches = ed_m
        save_matches(ed_m)
        st.rerun()

with t4:
    st.subheader(f"Action Log: {active_player}")
    if st.button("Clear Log"):
        st.session_state.match_data = pd.DataFrame(columns=["Phase", "DQ", "EQ", "CD", "TA", "LOP", "Mistake Type"])
        st.rerun()
    ed_cav = st.data_editor(st.session_state.match_data, num_rows="dynamic", use_container_width=True, key="ed_cav")
    st.session_state.match_data = ed_cav
    if not ed_cav.empty:
        rdf = ed_cav.copy()
        rdf['CAV'] = rdf.apply(calculate_cav, axis=1)
        aqc, his = rdf['CAV'].mean(), (len(rdf[rdf['CAV'] >= 7.0]) / len(rdf)) * 100
        st.session_state.calc_aqc, st.session_state.calc_his = aqc, his
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("Calculated AQC", f"{aqc:.2f}"); c2.metric("HIS %", f"{his:.1f}%"); c3.metric("Total Actions", len(rdf))

with t5:
    if active_player == "None": st.warning("Please select a player in the sidebar.")
    else:
        start_aqc = max(1.0, float(st.session_state.get('calc_aqc', 5.5)))
        start_his = float(st.session_state.get('calc_his', 20.0))
        c1, c2 = st.columns(2)
        with c1:
            role = st.selectbox("Role", list(ROLE_WEIGHTS.keys()))
            m_aqc = st.number_input("AQC Rating (1-10)", 1.0, 10.0, start_aqc)
            m_his = st.number_input("HIS Rating %", 0.0, 100.0, start_his)
            m_ec = st.number_input("EC %", 0.0, 100.0, 75.0)
        with c2:
            m_tii = st.number_input("TII %", 0.0, 100.0, 50.0)
            m_ibi = st.number_input("IBI %", 0.0, 100.0, 10.0)
            sci = st.slider("SCI", 1.0, 1.08, 1.0)
            om = st.number_input("Outcome Multiplier (OM)", 0.5, 1.5, get_calculated_om(active_player, active_m_id))
        w = ROLE_WEIGHTS[role]
        final_mpr = (w['wAQC']*m_aqc*10 + w['wHIS']*m_his + w['wEC']*m_ec*sci + w['wTII']*m_tii + w['wIBI']*m_ibi) * om
        st.metric("Final MPR Score", f"{final_mpr:.1f}")
        if st.button("💾 Save to History"):
            st.session_state.general_mprs.append({"Player": active_player, "Match": m_label, "MPR": final_mpr, "Timestamp": datetime.now(), "Role": role, "AQC": m_aqc, "OM": om})
            save_mprs(st.session_state.general_mprs); st.success("Match Rating Saved!")

with t6:
    if st.session_state.general_mprs:
        hdf = pd.DataFrame(st.session_state.general_mprs)
        if active_player != "None": hdf = hdf[hdf["Player"] == active_player]
        st.dataframe(hdf.sort_values("Timestamp", ascending=False), use_container_width=True)
        if st.button("Delete All Records"): st.session_state.general_mprs = []; save_mprs([]); st.rerun()
    else: st.info("No history found.")

with t7:
    st.subheader("Stats Input")
    if active_player == "None" or active_m_id is None: st.warning("Select player and match in sidebar")
    else:
        with st.form("stats_form"):
            c1, c2, c3, c4 = st.columns(4)
            sg = c1.number_input("Goals", 0); sa = c2.number_input("Assists", 0)
            sb = c3.number_input("BCC", 0); sd = c4.number_input("Dribbles", 0)
            if st.form_submit_button("Update Stats"):
                # Ensure we find the match details for the log
                match_row = st.session_state.matches[st.session_state.matches["Match ID"] == active_m_id].iloc[0]
                m_name = f"{match_row['Opponent']} ({pd.to_datetime(match_row['Date']).strftime('%m-%d')})"
                t_name = match_row['Tournament'] if match_row['Tournament'] else "No Tournament"
                
                st.session_state.stats[f"{active_player}_m_{active_m_id}"] = {
                    "Player": active_player, 
                    "Match ID": active_m_id, 
                    "Match": m_name,
                    "Tournament": t_name, 
                    "Goals": sg, "Assists": sa, 
                    "BCC": sb, "Dribbles": sd, "Timestamp": datetime.now()
                }
                save_stats(st.session_state.stats); st.rerun()

with t8:
    st.subheader("Season Summary (CSR)")
    if active_player != "None" and st.session_state.general_mprs:
        sdf = pd.DataFrame([x for x in st.session_state.general_mprs if x.get("Player") == active_player])
        if not sdf.empty:
            avg_mpr, peak5 = sdf['MPR'].mean(), sdf.sort_values("MPR", ascending=False).head(5)['MPR'].mean()
            st.line_chart(sdf.set_index("Timestamp")["MPR"])
            c_s1, c_s2 = st.columns(2)
            c_s1.metric("Season Average", f"{avg_mpr:.1f}"); c_s2.metric("Peak-5 Average", f"{peak5:.1f}")
            st.metric("📊 Final CSR Score", f"{(0.5 * avg_mpr) + (0.5 * peak5):.1f}")

# --- TAB 9: STATS LOG ---
with t9:
    st.subheader("Statistical History Log")
    if st.session_state.stats:
        # Convert dictionary to DataFrame
        sdf = pd.DataFrame(list(st.session_state.stats.values()))
        
        # FIX: Handle cases where old data doesn't have the Tournament/Match columns yet
        if "Tournament" not in sdf.columns: sdf["Tournament"] = "Unknown"
        if "Match" not in sdf.columns: sdf["Match"] = "Unknown"
        
        # Display Columns
        cols = ["Timestamp", "Player", "Tournament", "Match", "Goals", "Assists", "BCC", "Dribbles"]
        
        # Filtering UI
        log_col1, log_col2 = st.columns(2)
        with log_col1:
            f_player = st.selectbox("Filter Log by Player", ["All"] + p_names, key="f_p")
        with log_col2:
            f_tourn = st.selectbox("Filter Log by Tournament", ["All"] + t_names, key="f_t")
            
        filtered_sdf = sdf.copy()
        if f_player != "All": filtered_sdf = filtered_sdf[filtered_sdf["Player"] == f_player]
        if f_tourn != "All": filtered_sdf = filtered_sdf[filtered_sdf["Tournament"] == f_tourn]

        st.dataframe(
            filtered_sdf[cols].sort_values("Timestamp", ascending=False), 
            use_container_width=True
        )
    else:
        st.info("No stats recorded yet.")