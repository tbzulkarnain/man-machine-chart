import streamlit as st
import pandas as pd

# ==========================================
# 1. KONFIGURASI HALAMAN & INPUT
# ==========================================
st.set_page_config(page_title="Universal MMC Generator", layout="wide")
st.title("⚙️ Universal Man-Machine Chart (MMC) Generator")

col1, col2 = st.columns(2)
with col1:
    num_machines = st.number_input("Jumlah Mesin", min_value=1, max_value=10, value=2, step=1)
with col2:
    num_cycles = st.number_input("Jumlah Siklus Simulasi", min_value=1, max_value=10, value=2, step=1)

st.subheader("1. Tabel Urutan Proses Kerja")

if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame([
        {"Proses": "Placing component to pallet", "Cycle Time (s)": 15.02, "Aktor": "Man"},
        {"Proses": "Loading - Unloading", "Cycle Time (s)": 4.48, "Aktor": "Both"},
        {"Proses": "take result", "Cycle Time (s)": 2.47, "Aktor": "Man"},
        {"Proses": "Stitch Process", "Cycle Time (s)": 51.72, "Aktor": "Machine"}
    ])

edited_df = st.data_editor(
    st.session_state.table_data,
    num_rows="dynamic",
    column_config={
        "Proses": st.column_config.TextColumn("Nama Elemen Proses", required=True),
        "Cycle Time (s)": st.column_config.NumberColumn("Cycle Time (s)", min_value=0.01, format="%.2f", required=True),
        "Aktor": st.column_config.SelectboxColumn("Aktor", options=["Man", "Machine", "Both"], required=True),
    },
    use_container_width=True
)

# ==========================================
# 2. SIMULATION ENGINE MMC (LOGIKA SEKUENSIAL)
# ==========================================

def run_universal_mmc(df_input, n_mc, n_cycles):
    df_clean = df_input.dropna(subset=["Proses", "Cycle Time (s)", "Aktor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    
    # Kelompokkan elemen kerja berdasarkan Aktor
    prep_steps = [s for s in steps if s["Aktor"] == "Man"]         # Contoh: Placing, Take Result
    load_steps = [s for s in steps if s["Aktor"] == "Both"]        # Contoh: Loading-Unloading
    machine_steps = [s for s in steps if s["Aktor"] == "Machine"]  # Contoh: Stitch / Hot Press
    
    # Identifikasi Placing (persiapan awal) dan Take Result (pengambilan hasil)
    placing_step = prep_steps[0] if prep_steps else None
    take_result_step = prep_steps[1] if len(prep_steps) > 1 else None
    loading_step = load_steps[0] if load_steps else None
    mc_step = machine_steps[0] if machine_steps else None

    op_free_at = 0.0
    mc_states = {m: {"free_at": 0.0, "is_running": False, "curr_act": "waiting"} for m in range(1, n_mc + 1)}
    
    events = []

    def get_mc_snapshot(active_mc, active_act, current_time):
        snapshot = {}
        for i in range(1, n_mc + 1):
            if i == active_mc and active_act:
                snapshot[i] = active_act
            elif mc_states[i]["is_running"] and mc_states[i]["free_at"] > current_time:
                snapshot[i] = mc_states[i]["curr_act"]
            else:
                snapshot[i] = "waiting"
        return snapshot

    # Iterasi berdasarkan Siklus Simulasi
    for cycle in range(n_cycles):
        for m in range(1, n_mc + 1):
            
            # --- ELEMEN 1: TAKE RESULT (Siklus ke-2 dst/setelah mesin selesai) ---
            if cycle > 0 and take_result_step:
                dur = float(take_result_step["Cycle Time (s)"])
                start_t = op_free_at
                end_t = start_t + dur
                
                events.append({
                    "start": start_t,
                    "end": end_t,
                    "op_act": f"{take_result_step['Proses']} MC {m}",
                    "mc_acts": get_mc_snapshot(m, take_result_step["Proses"], start_t)
                })
                op_free_at = end_t

            # --- ELEMEN 2: PLACING COMPONENT ---
            if placing_step:
                dur = float(placing_step["Cycle Time (s)"])
                start_t = op_free_at
                end_t = start_t + dur
                
                events.append({
                    "start": start_t,
                    "end": end_t,
                    "op_act": f"{placing_step['Proses']} MC {m}",
                    "mc_acts": get_mc_snapshot(m, None, start_t)
                })
                op_free_at = end_t

            # --- ELEMEN 3: IDLE OPERATOR (Jika Mesin Masih Jalan saat Operator Siap Loading) ---
            if mc_states[m]["is_running"] and mc_states[m]["free_at"] > op_free_at:
                idle_start = op_free_at
                idle_end = mc_states[m]["free_at"]
                
                events.append({
                    "start": idle_start,
                    "end": idle_end,
                    "op_act": "idle",
                    "mc_acts": get_mc_snapshot(None, None, idle_start)
                })
                op_free_at = idle_end
                mc_states[m]["is_running"] = False

            # --- ELEMEN 4: LOADING - UNLOADING (Both Man & Machine) ---
            if loading_step:
                dur = float(loading_step["Cycle Time (s)"])
                start_t = op_free_at
                end_t = start_t + dur
                
                events.append({
                    "start": start_t,
                    "end": end_t,
                    "op_act": f"{loading_step['Proses']} MC {m}",
                    "mc_acts": get_mc_snapshot(m, loading_step["Proses"], start_t)
                })
                op_free_at = end_t

            # --- ELEMEN 5: STITCH / HOT PRESS (Machine Process Auto Trigger) ---
            if mc_step:
                dur = float(mc_step["Cycle Time (s)"])
                mc_states[m]["is_running"] = True
                mc_states[m]["curr_act"] = mc_step["Proses"]
                mc_states[m]["free_at"] = op_free_at + dur

    # Formating Output DataFrame
    rows = []
    for ev in events:
        dur = round(ev["end"] - ev["start"], 2)
        r = {
            "Time (s)": round(ev["end"], 2),
            "Operator Activity": ev["op_act"],
            "Op Time": dur
        }
        for m in range(1, n_mc + 1):
            r[f"MC {m} Activity"] = ev["mc_acts"].get(m, "waiting")
            r[f"MC {m} Time"] = dur
        rows.append(r)
        
    return pd.DataFrame(rows)

# ==========================================
# 3. SUMMARY MATRIX (STEADY STATE 1 LOOP)
# ==========================================

def run_summary_matrix_steady_state(df_input, n_mc):
    df_clean = df_input.dropna(subset=["Proses", "Cycle Time (s)", "Aktor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    
    op_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Man", "Both"])
    mc_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Machine", "Both"])
    op_manual_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] == "Man")
    
    total_op_work_steady = op_work_per_mc * n_mc
    single_mc_cycle = mc_work_per_mc + op_manual_per_mc
    steady_cycle_time = max(total_op_work_steady, single_mc_cycle)

    op_idle_steady = max(0.0, steady_cycle_time - total_op_work_steady)
    op_util_steady = (total_op_work_steady / steady_cycle_time * 100) if steady_cycle_time > 0 else 0

    summary_dict = {
        "Summary": ["Working time", "Idle time", "Total cycle time", "Utilization in percent"],
        "Man Power": [
            f"{total_op_work_steady:.2f}",
            f"{op_idle_steady:.2f}",
            f"{steady_cycle_time:.2f}",
            f"{round(op_util_steady)}%"
        ]
    }

    for m in range(1, n_mc + 1):
        mc_idle_steady = max(0.0, steady_cycle_time - single_mc_cycle)
        mc_util_steady = (single_mc_cycle / steady_cycle_time * 100) if steady_cycle_time > 0 else 0
        
        summary_dict[f"MC {m}"] = [
            f"{single_mc_cycle:.2f}",
            f"{mc_idle_steady:.2f}",
            f"{steady_cycle_time:.2f}",
            f"{round(mc_util_steady)}%"
        ]

    return pd.DataFrame(summary_dict)

# ==========================================
# 4. RENDER HALAMAN STREAMLIT
# ==========================================
st.markdown("---")
st.subheader("2. Hasil Simulasi Man-Machine Chart (MMC)")

res_df = run_universal_mmc(edited_df, num_machines, num_cycles)
if not res_df.empty:
    st.dataframe(res_df, use_container_width=True)
else:
    st.warning("⚠️ Masukkan data proses pada tabel di atas untuk menampilkan hasil.")

st.markdown("---")
st.subheader("📊 Summary Performance Matrix (1 Loop Steady State)")

sum_df = run_summary_matrix_steady_state(edited_df, num_machines)
if not sum_df.empty:
    st.dataframe(sum_df, use_container_width=True, hide_index=True)
