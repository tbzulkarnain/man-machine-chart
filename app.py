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
# 2. SIMULATION ENGINE MMC
# ==========================================

def run_universal_mmc(df_input, n_mc, n_cycles):
    df_clean = df_input.dropna(subset=["Proses", "Cycle Time (s)", "Aktor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    num_steps = len(steps)
    
    op_free_at = 0.0
    
    mc_states = {}
    for m in range(1, n_mc + 1):
        mc_states[m] = {
            "free_at": 0.0,
            "step_idx": 0,
            "cycle": 0,
            "curr_act": "waiting",
            "is_running": False
        }
        
    events = []
    max_steps = 1500
    step_count = 0

    while any(mc_states[m]["cycle"] < n_cycles for m in range(1, n_mc + 1)) and step_count < max_steps:
        step_count += 1
        
        candidates = []
        
        for m in range(1, n_mc + 1):
            if mc_states[m]["cycle"] >= n_cycles:
                continue
            
            idx = mc_states[m]["step_idx"]
            step = steps[idx]
            
            if step["Aktor"] in ["Man", "Both"]:
                ready_t = op_free_at
                
                if step["Aktor"] == "Both":
                    ready_t = max(op_free_at, mc_states[m]["free_at"])
                    prio = 1
                else:
                    prio = 2
                
                candidates.append({
                    "mc_id": m,
                    "ready_time": ready_t,
                    "priority": prio,
                    "step_idx": idx,
                    "step": step
                })

        if candidates:
            candidates.sort(key=lambda x: (x["ready_time"], x["priority"], x["mc_id"]))
            chosen = candidates[0]
            
            m = chosen["mc_id"]
            step = chosen["step"]
            start_t = chosen["ready_time"]
            
            if start_t > op_free_at:
                mc_snapshot_idle = {}
                for i in range(1, n_mc + 1):
                    if mc_states[i]["is_running"] and mc_states[i]["free_at"] > op_free_at:
                        mc_snapshot_idle[i] = mc_states[i]["curr_act"]
                    else:
                        mc_snapshot_idle[i] = "waiting"
                        
                events.append({
                    "start": op_free_at,
                    "end": start_t,
                    "op_act": "idle",
                    "mc_acts": mc_snapshot_idle
                })
            
            end_t = start_t + float(step["Cycle Time (s)"])
            
            mc_acts_snapshot = {}
            for i in range(1, n_mc + 1):
                if i == m:
                    if step["Aktor"] == "Both":
                        mc_acts_snapshot[i] = step["Proses"]
                    else:
                        if mc_states[i]["is_running"] and mc_states[i]["free_at"] > start_t:
                            mc_acts_snapshot[i] = mc_states[i]["curr_act"]
                        else:
                            mc_acts_snapshot[i] = "waiting"
                else:
                    if mc_states[i]["is_running"] and mc_states[i]["free_at"] > start_t:
                        mc_acts_snapshot[i] = mc_states[i]["curr_act"]
                    else:
                        mc_acts_snapshot[i] = "waiting"
            
            op_label = step['Proses']
            if n_mc > 1 and "MC" not in op_label:
                op_label = f"{step['Proses']} MC {m}"
                
            events.append({
                "start": start_t,
                "end": end_t,
                "op_act": op_label,
                "mc_acts": mc_acts_snapshot
            })
            
            op_free_at = end_t
            
            mc_states[m]["step_idx"] += 1
            if mc_states[m]["step_idx"] >= num_steps:
                mc_states[m]["step_idx"] = 0
                mc_states[m]["cycle"] += 1

            # Trigger Mesin Otomatis (Stitch Process) Setelah Loading-Unloading
            curr_idx = mc_states[m]["step_idx"]
            if mc_states[m]["cycle"] < n_cycles:
                if steps[curr_idx]["Aktor"] == "Machine":
                    mc_step = steps[curr_idx]
                    mc_states[m]["curr_act"] = mc_step["Proses"]
                    mc_states[m]["is_running"] = True
                    mc_states[m]["free_at"] = end_t + float(mc_step["Cycle Time (s)"])
                    
                    mc_states[m]["step_idx"] += 1
                    if mc_states[m]["step_idx"] >= num_steps:
                        mc_states[m]["step_idx"] = 0
                        mc_states[m]["cycle"] += 1
                elif step["Aktor"] == "Both":
                    for s_val in steps:
                        if s_val["Aktor"] == "Machine":
                            mc_states[m]["curr_act"] = s_val["Proses"]
                            mc_states[m]["is_running"] = True
                            mc_states[m]["free_at"] = end_t + float(s_val["Cycle Time (s)"])
                            break
                            
        else:
            future_times = [mc_states[i]["free_at"] for i in range(1, n_mc + 1) if mc_states[i]["cycle"] < n_cycles and mc_states[i]["free_at"] > op_free_at]
            if future_times:
                next_t = min(future_times)
                mc_snapshot_idle = {}
                for i in range(1, n_mc + 1):
                    if mc_states[i]["is_running"] and mc_states[i]["free_at"] > op_free_at:
                        mc_snapshot_idle[i] = mc_states[i]["curr_act"]
                    else:
                        mc_snapshot_idle[i] = "waiting"
                        
                events.append({
                    "start": op_free_at,
                    "end": next_t,
                    "op_act": "idle",
                    "mc_acts": mc_snapshot_idle
                })
                op_free_at = next_t
            else:
                break

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
    
    # Perhitungan Durasi per Mesin
    op_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Man", "Both"])
    mc_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Machine", "Both"])
    op_manual_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] == "Man")
    
    # Total Waktu Kerja Operator Dalam 1 Loop Steady State
    total_op_work_steady = op_work_per_mc * n_mc
    
    # Cycle Time 1 Mesin (Waktu Mesin + Waktu Manual Operator untuk Mesin Tersebut)
    single_mc_cycle = mc_work_per_mc + op_manual_per_mc
    
    # Bottleneck Cycle Time 1 Loop Steady State
    steady_cycle_time = max(total_op_work_steady, single_mc_cycle)

    # 1. Man Power Performance
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

    # 2. Machine Performance
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
