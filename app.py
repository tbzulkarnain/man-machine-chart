import streamlit as st
import pandas as pd

# ==========================================
# 1. KONFIGURASI HALAMAN
# ==========================================
st.set_page_config(page_title="Universal MMC Generator", layout="wide")
st.title("⚙️ Universal Man-Machine Chart (MMC) Generator")

# ==========================================
# 2. INPUT PARAMETER
# ==========================================
col1, col2 = st.columns(2)
with col1:
    num_machines = st.number_input("Jumlah Mesin", min_value=1, max_value=10, value=5, step=1)
with col2:
    num_cycles = st.number_input("Jumlah Siklus Simulasi", min_value=1, max_value=10, value=2, step=1)

st.subheader("1. Tabel Urutan Proses Kerja")

if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame([
        {"Proses": "Placing component", "Cycle Time (s)": 43.33, "Aktor": "Man"},
        {"Proses": "Hot Press", "Cycle Time (s)": 160.0, "Aktor": "Machine"},
        {"Proses": "Take result / Unload", "Cycle Time (s)": 9.0, "Aktor": "Man"}
    ])

# Tabel input interaktif
edited_df = st.data_editor(
    st.session_state.table_data,
    num_rows="dynamic",
    column_config={
        "Proses": st.column_config.TextColumn("Nama Elemen Proses", required=True),
        "Cycle Time (s)": st.column_config.NumberColumn("Cycle Time (s)", min_value=0.1, format="%.2f", required=True),
        "Aktor": st.column_config.SelectboxColumn("Aktor", options=["Man", "Machine", "Both"], required=True),
    },
    use_container_width=True
)

# ==========================================
# 3. ENGINE UNIVERSAL (MEMBACA DINAMIS TANPA HARDCODE)
# ==========================================

def get_process_times(df):
    """Membaca waktu proses secara universal dari tabel input"""
    # Mencari waktu Load (Man sebelum Machine)
    man_tasks = df[df['Aktor'].isin(['Man', 'Both'])]
    mc_tasks = df[df['Aktor'] == 'Machine']
    
    # Ambil durasi berdasarkan urutan baris
    place_t = man_tasks.iloc[0]['Cycle Time (s)'] if len(man_tasks) > 0 else 10.0
    press_t = mc_tasks.iloc[0]['Cycle Time (s)'] if len(mc_tasks) > 0 else 60.0
    take_t = man_tasks.iloc[1]['Cycle Time (s)'] if len(man_tasks) > 1 else (man_tasks.iloc[0]['Cycle Time (s)'] if len(man_tasks) > 0 else 5.0)
    
    # Nama aktivitas
    place_name = man_tasks.iloc[0]['Proses'] if len(man_tasks) > 0 else "Loading"
    press_name = mc_tasks.iloc[0]['Proses'] if len(mc_tasks) > 0 else "Processing"
    take_name = man_tasks.iloc[1]['Proses'] if len(man_tasks) > 1 else "Unloading"
    
    return place_t, press_t, take_t, place_name, press_name, take_name


def generate_mmc_schedule(df_input, n_mc, n_cycles):
    place_time, press_time, take_time, place_name, press_name, take_name = get_process_times(df_input)

    machines = [{"id": i+1, "status": "idle_empty", "next_free_time": 0.0, "cycle_count": 0} for i in range(n_mc)]
    op_free_time = 0.0
    events = []

    while any(m["cycle_count"] < n_cycles for m in machines):
        m_unload = next((m for m in machines if m["status"] == "finished_waiting_unload" and m["cycle_count"] < n_cycles), None)
        m_load = next((m for m in machines if m["status"] == "idle_empty" and m["cycle_count"] < n_cycles), None)
        
        if m_unload:
            start_t = max(op_free_time, m_unload["next_free_time"])
            end_t = start_t + take_time
            events.append({
                "start": start_t, "end": end_t,
                "op": f"{take_name} MC {m_unload['id']}",
                "mc_act": {m_unload['id']: take_name},
                "type": "unload"
            })
            op_free_time = end_t
            m_unload["status"] = "idle_empty"
            m_unload["cycle_count"] += 1
            m_unload["next_free_time"] = end_t

        elif m_load:
            start_t = op_free_time
            end_t = start_t + place_time
            events.append({
                "start": start_t, "end": end_t,
                "op": f"{place_name} MC {m_load['id']}",
                "mc_act": {m_load['id']: place_name},
                "type": "load"
            })
            op_free_time = end_t
            m_load["status"] = "pressing"
            m_load["next_free_time"] = end_t + press_time

        else:
            next_event = min(m["next_free_time"] for m in machines if m["status"] == "pressing")
            if next_event > op_free_time:
                events.append({
                    "start": op_free_time, "end": next_event,
                    "op": "idle",
                    "mc_act": {},
                    "type": "idle"
                })
                op_free_time = next_event
            
            for m in machines:
                if m["status"] == "pressing" and m["next_free_time"] <= op_free_time:
                    m["status"] = "finished_waiting_unload"

    table_rows = []
    mc_states = {i+1: {"status": "waiting", "until": 0.0} for i in range(n_mc)}

    for ev in events:
        dur = round(ev["end"] - ev["start"], 2)
        row = {
            "Time (s)": round(ev["end"], 2),
            "Operator Activity": ev["op"],
            "Op Time": dur
        }
        
        for mc_id in range(1, n_mc + 1):
            if mc_id in ev["mc_act"]:
                act = ev["mc_act"][mc_id]
                if act == place_name:
                    mc_states[mc_id] = {"status": press_name, "until": ev["end"] + press_time}
                elif act == take_name:
                    mc_states[mc_id] = {"status": "waiting", "until": 0.0}
                row[f"MC {mc_id} Activity"] = act
            else:
                if mc_states[mc_id]["status"] == press_name and ev["start"] < mc_states[mc_id]["until"]:
                    row[f"MC {mc_id} Activity"] = press_name
                else:
                    row[f"MC {mc_id} Activity"] = "waiting"
            
            row[f"MC {mc_id} Time"] = dur

        table_rows.append(row)

    return pd.DataFrame(table_rows)


def generate_summary_table(df_input, n_mc):
    place_t, press_t, take_t, _, _, _ = get_process_times(df_input)

    # Kalkulasi Dinamis IE
    mc_pure_work = place_t + press_t + take_t
    op_pure_work = n_mc * (place_t + take_t)

    total_cycle = max(mc_pure_work, op_pure_work)

    op_idle_time = max(0.0, total_cycle - op_pure_work)
    op_utilization = (op_pure_work / total_cycle) * 100 if total_cycle > 0 else 0.0

    mc_idle_time = max(0.0, total_cycle - mc_pure_work)
    mc_utilization = (mc_pure_work / total_cycle) * 100 if total_cycle > 0 else 0.0

    summary_dict = {
        "Summary": [
            "Working time",
            "Idle time",
            "Total cycle time",
            "Utilization in percent"
        ],
        "Man Power": [
            f"{op_pure_work:.2f}",
            f"{op_idle_time:.2f}",
            f"{total_cycle:.2f}",
            f"{op_utilization:.0f}%"
        ]
    }

    for i in range(1, n_mc + 1):
        summary_dict[f"MC {i}"] = [
            f"{mc_pure_work:.2f}",
            f"{mc_idle_time:.2f}",
            f"{total_cycle:.2f}",
            f"{mc_utilization:.0f}%"
        ]

    return pd.DataFrame(summary_dict)


# ==========================================
# 4. TAMPILKAN HASIL OTOMATIS BERUBAH (REACTIVE)
# ==========================================
st.markdown("---")
st.subheader("2. Hasil Simulasi Man-Machine Chart (MMC)")

result_df = generate_mmc_schedule(edited_df, num_machines, num_cycles)
st.dataframe(result_df, use_container_width=True)

st.markdown("---")
st.subheader("📊 Summary Performance Matrix (1 Loop Steady State)")

summary_df = generate_summary_table(edited_df, num_machines)
st.dataframe(summary_df, use_container_width=True, hide_index=True)
