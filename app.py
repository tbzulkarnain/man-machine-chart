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
# 2. DYNAMIC MMC SIMULATION ENGINE
# ==========================================

def run_universal_mmc(df_input, n_mc, n_cycles):
    df_clean = df_input.dropna(subset=["Proses", "Cycle Time (s)", "Aktor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    op_free_at = 0.0
    
    # Track status tiap mesin
    mc_states = {m: {"free_at": 0.0, "is_running": False, "curr_act": "waiting", "cycle": 0} for m in range(1, n_mc + 1)}
    
    events = []

    def get_mc_snapshot(active_mc, active_act, current_t):
        snapshot = {}
        for i in range(1, n_mc + 1):
            if i == active_mc and active_act:
                snapshot[i] = active_act
            elif mc_states[i]["is_running"] and mc_states[i]["free_at"] > current_t:
                snapshot[i] = mc_states[i]["curr_act"]
            else:
                snapshot[i] = "waiting"
        return snapshot

    # Eksekusi simulasi sekuensial berdasarkan urutan siklus dan mesin
    for c in range(n_cycles):
        for m in range(1, n_mc + 1):
            for step in steps:
                aktor = step["Aktor"]
                dur = float(step["Cycle Time (s)"])
                proses_name = step["Proses"]
                
                if aktor == "Man":
                    start_t = op_free_at
                    end_t = start_t + dur
                    
                    events.append({
                        "start": start_t,
                        "end": end_t,
                        "op_act": f"{proses_name} MC {m}",
                        "mc_acts": get_mc_snapshot(None, None, start_t)
                    })
                    op_free_at = end_t
                    
                elif aktor == "Both":
                    # Cek apakah operator harus idle menunggu mesin selesai beroperasi
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
                    
                    start_t = op_free_at
                    end_t = start_t + dur
                    
                    events.append({
                        "start": start_t,
                        "end": end_t,
                        "op_act": f"{proses_name} MC {m}",
                        "mc_acts": get_mc_snapshot(m, proses_name, start_t)
                    })
                    op_free_at = end_t
                    
                elif aktor == "Machine":
                    # Picu proses mesin berjalan otomatis setelah elemen Both/Man selesai
                    mc_states[m]["is_running"] = True
                    mc_states[m]["curr_act"] = proses_name
                    mc_states[m]["free_at"] = op_free_at + dur

    # Merapikan tabel hasil simulasi
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
# 3. SUMMARY MATRIX
# ==========================================

def run_summary_matrix_steady_state(df_input, n_mc):
    df_clean = df_input.dropna(subset=["Proses", "Cycle Time (s)", "Aktor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    
    op_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Man", "Both"])
    mc_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Machine", "Both"])
    op_manual_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] == "Man")
    
    total_op_work = op_work_per_mc * n_mc
    single_mc_cycle = mc_work_per_mc + op_manual_per_mc
    
    # Menghitung cycle time aktual berdasar bottleneck
    cycle_time = max(total_op_work, single_mc_cycle)
    op_idle = max(0.0, cycle_time - total_op_work)
    op_util = (total_op_work / cycle_time * 100) if cycle_time > 0 else 0

    summary_dict = {
        "Summary": ["Working time", "Idle time", "Total cycle time", "Utilization in percent"],
        "Man Power": [
            f"{total_op_work:.2f}",
            f"{op_idle:.2f}",
            f"{cycle_time:.2f}",
            f"{round(op_util)}%"
        ]
    }

    for m in range(1, n_mc + 1):
        mc_idle = max(0.0, cycle_time - single_mc_cycle)
        mc_util = (single_mc_cycle / cycle_time * 100) if cycle_time > 0 else 0
        
        summary_dict[f"MC {m}"] = [
            f"{single_mc_cycle:.2f}",
            f"{mc_idle:.2f}",
            f"{cycle_time:.2f}",
            f"{round(mc_util)}%"
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
st.subheader("📊 Summary Performance Matrix")

sum_df = run_summary_matrix_steady_state(edited_df, num_machines)
if not sum_df.empty:
    st.dataframe(sum_df, use_container_width=True, hide_index=True)
