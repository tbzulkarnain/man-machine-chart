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
        {"Proses": "placing component to palet", "Cycle Time (s)": 15.02, "Aktor": "Man"},
        {"Proses": "loading unloading 1", "Cycle Time (s)": 4.48, "Aktor": "Both"},
        {"Proses": "stitching process", "Cycle Time (s)": 51.72, "Aktor": "Machine"},
        {"Proses": "loading unloading 2", "Cycle Time (s)": 4.48, "Aktor": "Both"},
        {"Proses": "take result", "Cycle Time (s)": 2.47, "Aktor": "Man"}
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
# 2. SIMULATION ENGINE UNIVERSAL SEJATI
# ==========================================

def run_universal_mmc(df_steps, n_mc, n_cycles):
    steps = df_steps.to_dict('records')
    
    # Inisialisasi State
    op_free_at = 0.0
    mc_states = {m: {"free_at": 0.0, "step_idx": 0, "cycle": 0, "curr_act": "waiting"} for m in range(1, n_mc + 1)}
    
    # Event Log
    events = [] # list of {start, end, actor_type, mc_id, act_name}
    
    # Loop Simulasi
    while any(mc_states[m]["cycle"] < n_cycles for m in range(1, n_mc + 1)):
        # Cari aksi berikutnya yang bisa dieksekusi oleh Operator atau Mesin
        # Prioritas: Unloading/Both/Man yang pending -> Loading/Both -> Machine Automatic
        
        candidates = []
        for m in range(1, n_mc + 1):
            if mc_states[m]["cycle"] >= n_cycles:
                continue
            
            idx = mc_states[m]["step_idx"]
            step = steps[idx]
            
            if step["Aktor"] in ["Man", "Both"]:
                ready_time = max(op_free_at, mc_states[m]["free_at"])
                candidates.append({
                    "mc_id": m,
                    "ready_time": ready_time,
                    "step_idx": idx,
                    "step": step
                })
        
        if candidates:
            # Pilih candidate dengan waktu paling awal
            candidates.sort(key=lambda x: (x["ready_time"], x["mc_id"]))
            chosen = candidates[0]
            
            m = chosen["mc_id"]
            step = chosen["step"]
            start_t = chosen["ready_time"]
            
            # Jika operator harus menunggu sebelum mulai
            if start_t > op_free_time:
                events.append({
                    "start": op_free_time,
                    "end": start_t,
                    "op_act": "idle",
                    "mc_acts": {i: "waiting" if mc_states[i]["free_at"] <= op_free_time else mc_states[i]["curr_act"] for i in range(1, n_mc + 1)}
                })
            
            end_t = start_t + float(step["Cycle Time (s)"])
            
            # Catat aktivitas
            mc_acts_snapshot = {}
            for i in range(1, n_mc + 1):
                if i == m:
                    mc_acts_snapshot[i] = step["Proses"]
                else:
                    mc_acts_snapshot[i] = mc_states[i]["curr_act"] if mc_states[i]["free_at"] > start_t else "waiting"
            
            events.append({
                "start": start_t,
                "end": end_t,
                "op_act": f"{step['Proses']} MC {m}",
                "mc_acts": mc_acts_snapshot
            })
            
            # Update State
            op_free_at = end_t
            mc_states[m]["free_at"] = end_t
            mc_states[m]["curr_act"] = step["Proses"]
            
            # Advance step
            mc_states[m]["step_idx"] += 1
            if mc_states[m]["step_idx"] >= len(steps):
                mc_states[m]["step_idx"] = 0
                mc_states[m]["cycle"] += 1
                
            # Jika step berikutnya adalah "Machine" murni, langsung trigger otomatis!
            if mc_states[m]["cycle"] < n_cycles:
                next_idx = mc_states[m]["step_idx"]
                next_step = steps[next_idx]
                if next_step["Aktor"] == "Machine":
                    mc_states[m]["curr_act"] = next_step["Proses"]
                    mc_states[m]["free_at"] = end_t + float(next_step["Cycle Time (s)"])
                    mc_states[m]["step_idx"] += 1
                    if mc_states[m]["step_idx"] >= len(steps):
                        mc_states[m]["step_idx"] = 0
                        mc_states[m]["cycle"] += 1
        else:
            # Jika tidak ada aktivitas operator, majukan waktu ke event mesin selesai paling awal
            active_mcs = [mc_states[i]["free_at"] for i in range(1, n_mc + 1) if mc_states[i]["cycle"] < n_cycles]
            if not active_mcs:
                break
            next_mc_finish = min(active_mcs)
            if next_mc_finish > op_free_at:
                mc_acts_snapshot = {}
                for i in range(1, n_mc + 1):
                    mc_acts_snapshot[i] = mc_states[i]["curr_act"] if mc_states[i]["free_at"] > op_free_at else "waiting"
                
                events.append({
                    "start": op_free_at,
                    "end": next_mc_finish,
                    "op_act": "idle",
                    "mc_acts": mc_acts_snapshot
                })
                op_free_at = next_mc_finish

    # Format ke DataFrame
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


def run_summary_matrix(df_steps, n_mc):
    steps = df_steps.to_dict('records')
    
    man_time = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Man", "Both"])
    mc_time = sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] in ["Machine", "Both"])
    
    total_op_work = man_time * n_mc
    single_mc_work = mc_time + sum(float(s["Cycle Time (s)"]) for s in steps if s["Aktor"] == "Man")
    
    total_cycle = max(single_mc_work, total_op_work)
    
    op_idle = max(0.0, total_cycle - total_op_work)
    op_util = (total_op_work / total_cycle) * 100 if total_cycle > 0 else 0.0
    
    mc_idle = max(0.0, total_cycle - single_mc_work)
    mc_util = (single_mc_work / total_cycle) * 100 if total_cycle > 0 else 0.0
    
    summary_dict = {
        "Summary": ["Working time", "Idle time", "Total cycle time", "Utilization in percent"],
        "Man Power": [f"{total_op_work:.2f}", f"{op_idle:.2f}", f"{total_cycle:.2f}", f"{op_util:.0f}%"]
    }
    
    for i in range(1, n_mc + 1):
        summary_dict[f"MC {i}"] = [f"{single_mc_work:.2f}", f"{mc_idle:.2f}", f"{total_cycle:.2f}", f"{mc_util:.0f}%"]
        
    return pd.DataFrame(summary_dict)

# ==========================================
# 3. RENDER HASIL
# ==========================================
st.markdown("---")
st.subheader("2. Hasil Simulasi Man-Machine Chart (MMC)")

res_df = run_universal_mmc(edited_df, num_machines, num_cycles)
st.dataframe(res_df, use_container_width=True)

st.markdown("---")
st.subheader("📊 Summary Performance Matrix (1 Loop Steady State)")

sum_df = run_summary_matrix(edited_df, num_machines)
st.dataframe(sum_df, use_container_width=True, hide_index=True)
