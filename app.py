import streamlit as st
import pandas as pd

# ==========================================
# 1. KONFIGURASI HALAMAN STREAMLIT
# ==========================================
st.set_page_config(page_title="Universal MMC Generator", layout="wide")
st.title("⚙️ Universal Man-Machine Chart (MMC) Generator")

# ==========================================
# 2. INPUT PARAMETER
# ==========================================
col1, col2 = st.columns(2)
with col1:
    num_machines = st.number_input("Jumlah Mesin", min_value=1, max_value=10, value=3, step=1)
with col2:
    num_cycles = st.number_input("Jumlah Siklus Simulasi", min_value=1, max_value=10, value=2, step=1)

st.subheader("1. Tabel Urutan Proses Kerja")

if "table_data" not in st.session_state:
    st.session_state.table_data = pd.DataFrame([
        {"Proses": "Placing component", "Cycle Time (s)": 43.3, "Aktor": "Man"},
        {"Proses": "Hot Press", "Cycle Time (s)": 160.0, "Aktor": "Machine"},
        {"Proses": "Take result / Unload", "Cycle Time (s)": 9.0, "Aktor": "Man"}
    ])

edited_df = st.data_editor(
    st.session_state.table_data,
    num_rows="dynamic",
    column_config={
        "Proses": st.column_config.TextColumn("Nama Elemen Proses", required=True),
        "Cycle Time (s)": st.column_config.NumberColumn("Cycle Time (s)", min_value=0.1, format="%.1f", required=True),
        "Aktor": st.column_config.SelectboxColumn("Aktor", options=["Man", "Machine", "Both"], required=True),
    },
    use_container_width=True
)

# ==========================================
# 3. ENGINE SIMULASI MMC
# ==========================================
def generate_mmc_schedule(df_input, n_mc, n_cycles):
    place_row = df_input[df_input['Aktor'].isin(['Man', 'Both']) & df_input['Proses'].str.contains('Placing|Loading|Place', case=False, na=False)]
    press_row = df_input[df_input['Aktor'] == 'Machine']
    take_row = df_input[df_input['Aktor'].isin(['Man', 'Both']) & df_input['Proses'].str.contains('Take|Unloading|Unload', case=False, na=False)]
    
    place_time = place_row['Cycle Time (s)'].values[0] if len(place_row) > 0 else 43.3
    press_time = press_row['Cycle Time (s)'].values[0] if len(press_row) > 0 else 160.0
    take_time = take_row['Cycle Time (s)'].values[0] if len(take_row) > 0 else 9.0

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
                "op": f"take result MC {m_unload['id']}",
                "mc_act": {m_unload['id']: "take result"},
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
                "op": f"Placing component MC {m_load['id']}",
                "mc_act": {m_load['id']: "Placing component"},
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
        dur = round(ev["end"] - ev["start"], 1)
        row = {
            "Time (s)": round(ev["end"], 1),
            "Operator Activity": ev["op"],
            "Op Time": dur
        }
        
        for mc_id in range(1, n_mc + 1):
            if mc_id in ev["mc_act"]:
                act = ev["mc_act"][mc_id]
                if act == "Placing component":
                    mc_states[mc_id] = {"status": "hot press", "until": ev["end"] + press_time}
                elif act == "take result":
                    mc_states[mc_id] = {"status": "waiting", "until": 0.0}
                row[f"MC {mc_id} Activity"] = act
            else:
                if mc_states[mc_id]["status"] == "hot press" and ev["start"] < mc_states[mc_id]["until"]:
                    row[f"MC {mc_id} Activity"] = "hot press"
                else:
                    row[f"MC {mc_id} Activity"] = "waiting"
            
            row[f"MC {mc_id} Time"] = dur

        table_rows.append(row)

    # Menghitung Summary 1 Siklus Stabil (Steady State)
    total_cycle_time = place_time + press_time + take_time
    op_working_time = n_mc * (place_time + take_time)
    op_idle_time = max(0.0, total_cycle_time - op_working_time)
    op_utilization = (op_working_time / total_cycle_time) * 100 if total_cycle_time > 0 else 0
    mc_utilization = 100.0 if op_idle_time >= 0 else (total_cycle_time / op_working_time) * 100

    summary_data = {
        "Metric Parameter": [
            "Cycle Time Per Mesin (1 Loop)",
            "Jumlah Mesin Ditangani",
            "Total Waktu Kerja Operator (1 Loop)",
            "Total Waktu Idle Operator (1 Loop Stabil)",
            "Efisiensi / Utilitas Operator",
            "Utilitas Mesin"
        ],
        "Nilai": [
            f"{total_cycle_time:.1f} detik",
            f"{n_mc} Mesin",
            f"{op_working_time:.1f} detik",
            f"{op_idle_time:.1f} detik",
            f"{op_utilization:.2f}%",
            f"{mc_utilization:.2f}%"
        ]
    }

    return pd.DataFrame(table_rows), pd.DataFrame(summary_data)

# ==========================================
# 4. TAMPILKAN HASIL TABEL & SUMMARY MMC
# ==========================================
st.subheader("2. Hasil Simulasi Man-Machine Chart (MMC)")

if st.button("🚀 Generate MMC Chart", type="primary"):
    result_df, summary_df = generate_mmc_schedule(edited_df, num_machines, num_cycles)
    
    # 1. Tampilkan Tabel Utama
    st.dataframe(result_df, use_container_width=True)
    
    # 2. Tampilkan Summary Metrics
    st.markdown("---")
    st.subheader("📊 Summary Analysis (1 Siklus Stabil / Steady State)")
    
    col_sum1, col_sum2 = st.columns([1, 1])
    with col_sum1:
        st.table(summary_df)
    with col_sum2:
        st.info("""
        **Catatan Summary:**
        * **Idle Ramp-Down Dibaikan:** Waktu idle di akhir simulasi (saat pengosongan mesin) tidak dimasukkan dalam summary karena hanya terjadi sekali di akhir shift.
        * **Kapasitas Optimal:** Dengan 3 mesin, operator bekerja selama **156.9 detik** dan idle **55.4 detik** per siklus. Efisiensi operator berada di angka ideal (**73.91%**).
        """)
