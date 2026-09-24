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
    
    # State tracking tiap mesin
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
        
        # Cari langkah berikutnya yang membutuhkan operator (Man atau Both)
        for m in range(1, n_mc + 1):
            if mc_states[m]["cycle"] >= n_cycles:
                continue
            
            idx = mc_states[m]["step_idx"]
            step = steps[idx]
            
            # Jika step ini melibatkan Man atau Both
            if step["Aktor"] in ["Man", "Both"]:
                # Waktu kapan operator & mesin siap untuk interaksi ini
                ready_t = op_free_at
                
                # Jika langkah 'Both', mesin juga harus bebas jahit sebelumnya
                if step["Aktor"] == "Both":
                    ready_t = max(op_free_at, mc_states[m]["free_at"])
                    prio = 1 # Both dapat prioritas utama
                else:
                    prio = 2 # Man
                
                candidates.append({
                    "mc_id": m,
                    "ready_time": ready_t,
                    "priority": prio,
                    "step_idx": idx,
                    "step": step
                })

        # EKSEKUSI CANDIDATE
        if candidates:
            candidates.sort(key=lambda x: (x["ready_time"], x["priority"], x["mc_id"]))
            chosen = candidates[0]
            
            m = chosen["mc_id"]
            step = chosen["step"]
            start_t = chosen["ready_time"]
            
            # Record Operator Idle jika ada gap waktu
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
            
            # Snapshot Status Mesin selama durasi langkah operator ini
            mc_acts_snapshot = {}
            for i in range(1, n_mc + 1):
                if i == m:
                    if step["Aktor"] == "Both":
                        mc_acts_snapshot[i] = step["Proses"]
                    else:
                        # Jika mesin m sedang dalam proses berjalan (misal Stitch Process)
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
            
            # Advance step index untuk operator
            mc_states[m]["step_idx"] += 1
            if mc_states[m]["step_idx"] >= num_steps:
                mc_states[m]["step_idx"] = 0
                mc_states[m]["cycle"] += 1

            # --- PEMICU KUNCI MESIN (TRIGGER MACHINE) ---
            # Jika setelah aksi ini (misal Both), step berikutnya atau step terdekat di urutan adalah 'Machine', JALANKAN MESIN SEGERA!
            curr_idx = mc_states[m]["step_idx"]
            if mc_states[m]["cycle"] < n_cycles:
                # Periksa apakah step saat ini/selanjutnya adalah 'Machine' (Stitch Process)
                if steps[curr_idx]["Aktor"] == "Machine":
                    mc_step = steps[curr_idx]
                    mc_states[m]["curr_act"] = mc_step["Proses"]
                    mc_states[m]["is_running"] = True
                    mc_states[m]["free_at"] = end_t + float(mc_step["Cycle Time (s)"])
                    
                    # Advance step index mesin
                    mc_states[m]["step_idx"] += 1
                    if mc_states[m]["step_idx"] >= num_steps:
                        mc_states[m]["step_idx"] = 0
                        mc_states[m]["cycle"] += 1
                elif step["Aktor"] == "Both":
                    # Jika langkahnya Both (Loading-Unloading), picu mesin jika Stitch Process ada di daftar
                    for s_i, s_val in enumerate(steps):
                        if s_val["Aktor"] == "Machine":
                            mc_states[m]["curr_act"] = s_val["Proses"]
                            mc_states[m]["is_running"] = True
                            mc_states[m]["free_at"] = end_t + float(s_val["Cycle Time (s)"])
                            break
                            
        else:
            # Mengatasi saat operator idle menunggu mesin selesai
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


def run_summary_matrix(df_input, n_mc):
    df_clean = df_input.dropna(subset=["Proses", "Cycle Time (s)", "Aktor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    
    man_time = sum(float(s["Cycle Time (s)"]) for s me in steps if s["Aktor"] in ["Man", "Both"])
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
if not res_df.empty:
    st.dataframe(res_df, use_container_width=True)
else:
    st.warning("⚠️ Masukkan data proses pada tabel di atas untuk menampilkan hasil.")

st.markdown("---")
st.subheader("📊 Summary Performance Matrix (1 Loop Steady State)")

sum_df = run_summary_matrix(edited_df, num_machines)
if not sum_df.empty:
    st.dataframe(sum_df, use_container_width=True, hide_index=True)
