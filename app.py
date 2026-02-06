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
NOTES_FILE = "notes.json"

# --- HELPER: DATA CLEANING ---
def clean_dataframe(df, text_cols=[], num_cols=[]):
    if df.empty:
        return df
    for c in text_cols:
        if c in df.columns:
            df[c] = df[c].fillna("").astype(str)
    for c in num_cols:
        if c in df.columns:
            df[c] = df[c].fillna(0)
    return df

# --- DATA LOADING ---
def load_players():
    if os.path.exists(PLAYERS_FILE):
        try:
            df = pd.read_csv(PLAYERS_FILE)
            df['Date Added'] = pd.to_datetime(df['Date Added'], format='mixed')
            return clean_dataframe(df, text_cols=["Player Name", "Position"])
        except: pass
    return pd.DataFrame(columns=["Player Name", "Position", "Date Added"])

def load_matches():
    if os.path.exists(MATCHES_FILE):
        try:
            df = pd.read_csv(MATCHES_FILE)
            df = df.dropna(how='all')
            df['Date'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce')
            df = clean_dataframe(df, text_cols=["Opponent", "Venue", "Result", "Player", "Tournament"])
            if 'Tournament' not in df.columns: df['Tournament'] = ""
            return df
        except: pass
    return pd.DataFrame(columns=["Match ID", "Date", "Opponent", "Venue", "Result", "Player", "Tournament"])

def load_tournaments():
    if os.path.exists(TOURNAMENTS_FILE):
        try:
            df = pd.read_csv(TOURNAMENTS_FILE)
            df['Date Added'] = pd.to_datetime(df['Date Added'], format='mixed')
            return clean_dataframe(df, text_cols=["Name"])
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
                    for m in data:
                        if 'Timestamp' in m: m['Timestamp'] = datetime.fromisoformat(m['Timestamp'])
                    return data
        except: pass
    return []

def load_notes():
    if os.path.exists(NOTES_FILE):
        try:
            with open(NOTES_FILE, 'r') as f:
                data = json.load(f)
                cleaned = {}
                for k, v in data.items():
                    if isinstance(v, str):
                        cleaned[k] = {"content": v, "updated": datetime.now().isoformat()}
                    else:
                        cleaned[k] = v
                return cleaned
        except: pass
    return {}

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
    for m in data:
        mc = m.copy()
        if isinstance(mc.get('Timestamp'), datetime): mc['Timestamp'] = mc['Timestamp'].isoformat()
        d2s.append(mc)
    with open(MPRS_FILE, 'w') as f: json.dump(d2s, f)
def save_notes(data):
    with open(NOTES_FILE, 'w') as f: json.dump(data, f)

# --- CALCULATIONS ---
def calculate_cav(row):
    try:
        dq, eq = float(row.get('DQ', 5.5)), float(row.get('EQ', 5.5))
        cd, ta = float(row.get('CD', 5.5)), float(row.get('TA', 5.5))
        lop = float(row.get('LOP', 5.5))
        raw = (2 * dq + 2 * eq + 1.5 * cd + 1.5 * ta + 1 * lop) / 8
        m_type = row.get('Mistake Type', "None")
        cap = 4.0 if m_type == "Type A (Decision)" else 8.3 if m_type == "Type B (Execution)" else 7.0 if m_type == "Type C (Forced)" else 10.0
        return min(raw, cap)
    except: return 5.5

def get_calculated_om(p_name, m_id):
    if p_name == "None" or m_id is None: return 1.0
    k = f"{p_name}_m_{m_id}"
    if k in st.session_state.stats:
        g, a = st.session_state.stats[k].get("Goals", 0), st.session_state.stats[k].get("Assists", 0)
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
if 'notes' not in st.session_state: st.session_state.notes = load_notes()
if 'match_data' not in st.session_state:
    st.session_state.match_data = pd.DataFrame(columns=["Phase", "DQ", "EQ", "CD", "TA", "LOP", "Mistake Type"])

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚽ FPM")
    p_names = st.session_state.players["Player Name"].tolist() if not st.session_state.players.empty else []
    active_player = st.selectbox("👤 Player", ["None"] + p_names)
    t_names = st.session_state.tournaments["Name"].tolist() if not st.session_state.tournaments.empty else []
    active_tournament = st.selectbox("🏆 Tournament", ["All"] + t_names)
    
    m_label, active_m_id = "None", None
    if not st.session_state.matches.empty:
        df_m = st.session_state.matches.copy()
        if active_tournament != "All": df_m = df_m[df_m["Tournament"] == active_tournament]
        opts = []
        for _, r in df_m.iterrows():
            m_date = pd.to_datetime(r['Date'], errors='coerce')
            d_str = m_date.strftime('%m-%d') if pd.notnull(m_date) else "N/A"
            opts.append(f"{int(r['Match ID'])}: {r['Opponent']} ({d_str})")
        m_label = st.selectbox("📅 Match", ["None"] + opts)
        if m_label != "None": active_m_id = int(m_label.split(":")[0])

# --- TABS ---
t1, t2, t3, t4, t5, t6, t7, t8, t9, t10 = st.tabs([
    "Players", "Tournaments", "Matches", "Action Log", "Rating", 
    "History", "Stats Input", "Season", "Stats Log", "Match Notes" 
])

# --- TAB 1: PLAYERS ---
with t1:
    st.subheader("Manage Players")
    # Hidden Date Added Column for Editor
    ed_p = st.data_editor(st.session_state.players, column_order=("Player Name", "Position"), num_rows="dynamic", use_container_width=True, key="ed_p")
    if not ed_p.equals(st.session_state.players):
        st.session_state.players = ed_p
        save_players(ed_p); st.rerun()

    st.divider()
    st.markdown("##### 🗑️ Delete Players")
    p_to_del = st.multiselect("Select players to delete:", st.session_state.players["Player Name"].tolist(), key="del_p_sel")
    if st.button("Delete Selected Players"):
        if p_to_del:
            st.session_state.players = st.session_state.players[~st.session_state.players["Player Name"].isin(p_to_del)]
            save_players(st.session_state.players); st.success("Deleted."); st.rerun()

# --- TAB 2: TOURNAMENTS ---
with t2:
    st.subheader("Manage Tournaments")
    ed_t = st.data_editor(st.session_state.tournaments, column_order=("Tournament ID", "Name"), num_rows="dynamic", use_container_width=True, key="ed_t")
    if not ed_t.equals(st.session_state.tournaments):
        st.session_state.tournaments = ed_t
        save_tournaments(ed_t); st.rerun()
        
    st.divider()
    st.markdown("##### 🗑️ Delete Tournaments")
    t_to_del = st.multiselect("Select tournaments to delete:", st.session_state.tournaments["Name"].tolist(), key="del_t_sel")
    if st.button("Delete Selected Tournaments"):
        if t_to_del:
            st.session_state.tournaments = st.session_state.tournaments[~st.session_state.tournaments["Name"].isin(t_to_del)]
            save_tournaments(st.session_state.tournaments); st.success("Deleted."); st.rerun()

# --- TAB 3: MATCHES ---
with t3:
    st.subheader("Manage Matches")
    p_l = [x for x in st.session_state.players["Player Name"].tolist() if pd.notnull(x) and x != ""]
    t_l = [x for x in st.session_state.tournaments["Name"].tolist() if pd.notnull(x) and x != ""]
    ed_m = st.data_editor(st.session_state.matches, num_rows="dynamic", use_container_width=True, column_config={
            "Player": st.column_config.SelectboxColumn(options=p_l),
            "Tournament": st.column_config.SelectboxColumn(options=[""] + t_l),
            "Date": st.column_config.DateColumn()
        }, key="ed_m")
    if not ed_m.equals(st.session_state.matches):
        st.session_state.matches = ed_m
        save_matches(ed_m); st.rerun()

    st.divider()
    st.markdown("##### 🗑️ Delete Matches")
    if not st.session_state.matches.empty:
        del_opts = []
        for idx, row in st.session_state.matches.iterrows():
            d_s = pd.to_datetime(row['Date']).strftime('%m-%d') if pd.notnull(pd.to_datetime(row['Date'])) else "N/A"
            del_opts.append(f"{row['Match ID']}: {row['Opponent']} ({d_s})")
        m_to_del = st.multiselect("Select matches to delete:", del_opts, key="del_m_sel")
        if st.button("Delete Selected Matches"):
            if m_to_del:
                ids_to_del = [int(x.split(":")[0]) for x in m_to_del]
                st.session_state.matches = st.session_state.matches[~st.session_state.matches["Match ID"].isin(ids_to_del)]
                save_matches(st.session_state.matches); st.success("Deleted."); st.rerun()

# --- TAB 4: ACTION LOG ---
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
        c1, c2, c3 = st.columns(3)
        c1.metric("AQC", f"{aqc:.2f}"); c2.metric("HIS %", f"{his:.1f}%"); c3.metric("Actions", len(rdf))

# --- TAB 5: RATING ---
with t5:
    if active_player == "None": st.warning("Select Player.")
    else:
        role = st.selectbox("Role", list(ROLE_WEIGHTS.keys()))
        c1, c2 = st.columns(2)
        m_aqc = c1.number_input("AQC", 1.0, 10.0, float(st.session_state.get('calc_aqc', 5.5)))
        m_his = c1.number_input("HIS", 0.0, 100.0, float(st.session_state.get('calc_his', 20.0)))
        m_ec = c1.number_input("EC", 0.0, 100.0, 75.0)
        m_tii = c2.number_input("TII", 0.0, 100.0, 50.0)
        m_ibi = c2.number_input("IBI", 0.0, 100.0, 10.0)
        om = c2.number_input("OM", 0.5, 1.5, get_calculated_om(active_player, active_m_id))
        w = ROLE_WEIGHTS[role]
        final = (w['wAQC']*m_aqc*10 + w['wHIS']*m_his + w['wEC']*m_ec + w['wTII']*m_tii + w['wIBI']*m_ibi) * om
        st.metric("Final MPR", f"{final:.1f}")
        if st.button("💾 Save"):
            st.session_state.general_mprs.append({"Player": active_player, "Match": m_label, "MPR": final, "Timestamp": datetime.now(), "Role": role})
            save_mprs(st.session_state.general_mprs); st.success("Saved!")

# --- TAB 6: HISTORY ---
with t6:
    if st.session_state.general_mprs:
        hdf = pd.DataFrame(st.session_state.general_mprs)
        if active_player != "None": hdf = hdf[hdf["Player"] == active_player]
        # Only show relevant columns (Hide Timestamp if desired, but usually useful in history logs)
        st.dataframe(hdf[["Player", "Match", "MPR", "Role"]].sort_index(ascending=False), use_container_width=True)
        if st.button("Delete All"): st.session_state.general_mprs = []; save_mprs([]); st.rerun()

# --- TAB 7: STATS INPUT ---
with t7:
    if active_player == "None" or active_m_id is None: st.warning("Select player and match.")
    else:
        with st.form("sf"):
            c1, c2 = st.columns(2)
            g, a = c1.number_input("Goals",0), c1.number_input("Assists",0)
            b, d = c2.number_input("BCC",0), c2.number_input("Dribbles",0)
            if st.form_submit_button("Update"):
                mr = st.session_state.matches[st.session_state.matches["Match ID"]==active_m_id].iloc[0]
                t_n = mr['Tournament'] if mr['Tournament'] else "Unknown"
                st.session_state.stats[f"{active_player}_m_{active_m_id}"] = {
                    "Player":active_player, "Match ID":active_m_id, "Match":m_label, "Tournament":t_n,
                    "Goals":g, "Assists":a, "BCC":b, "Dribbles":d, "Timestamp":datetime.now()
                }
                save_stats(st.session_state.stats); st.rerun()

# --- TAB 8: SEASON ---
with t8:
    if active_player != "None" and st.session_state.general_mprs:
        sdf = pd.DataFrame([x for x in st.session_state.general_mprs if x.get("Player")==active_player])
        if not sdf.empty:
            st.metric("Avg MPR", f"{sdf['MPR'].mean():.1f}")
            st.line_chart(sdf.set_index("Timestamp")["MPR"])

# --- TAB 9: STATS LOG ---
with t9:
    if st.session_state.stats:
        sdf = pd.DataFrame(list(st.session_state.stats.values()))
        sdf = clean_dataframe(sdf, text_cols=["Tournament", "Match"])
        # Removed Timestamp from display columns
        disp_cols = ["Player", "Tournament", "Match", "Goals", "Assists", "BCC", "Dribbles"]
        st.dataframe(sdf[disp_cols], use_container_width=True)
        
        st.divider()
        st.markdown("##### 🗑️ Delete Stat Records")
        opts = [f"{v['Player']} - {v.get('Match','?')} (G:{v.get('Goals',0)})" for k,v in st.session_state.stats.items()]
        lbl_to_key = {f"{v['Player']} - {v.get('Match','?')} (G:{v.get('Goals',0)})": k for k,v in st.session_state.stats.items()}
        sel_stats = st.multiselect("Select stats to delete:", opts)
        if st.button("Delete Selected Stats"):
            for l in sel_stats:
                k = lbl_to_key[l]
                if k in st.session_state.stats: del st.session_state.stats[k]
            save_stats(st.session_state.stats); st.rerun()

# --- TAB 10: NOTES ---
with t10:
    st.subheader("📝 Match Notes")
    c_lst, c_edt = st.columns([1, 2])
    with c_lst:
        with st.expander("➕ New Notepad"):
            nn = st.text_input("Name")
            if st.button("Create") and nn:
                st.session_state.notes[nn] = {"content":"", "updated":datetime.now().isoformat()}
                save_notes(st.session_state.notes); st.rerun()
        st.divider()
        sch = st.text_input("🔍 Search").lower()
        all_n = sorted(list(st.session_state.notes.keys()))
        filt = [n for n in all_n if sch in n.lower()]
        sel = st.radio("Select:", filt) if filt else None
    
    with c_edt:
        if sel:
            obj = st.session_state.notes[sel]
            txt = obj["content"] if isinstance(obj, dict) else obj
            upd = st.text_area("Edit:", value=txt, height=400, key=f"e_{sel}")
            if upd != txt:
                st.session_state.notes[sel] = {"content":upd, "updated":datetime.now().isoformat()}
                save_notes(st.session_state.notes)
            if st.button(f"🗑️ Delete '{sel}'", type="primary"):
                del st.session_state.notes[sel]
                save_notes(st.session_state.notes); st.rerun()