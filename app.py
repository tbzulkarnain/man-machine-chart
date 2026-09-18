import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(page_title="Multi-Machine Man-Machine Chart Analyzer", layout="wide")

st.title("⚙️ Multi-Machine Process Sheet Analyzer (Parallel Execution)")
st.caption("Aplikasi IE dengan Logika Interleaving / Preparation saat Mesin Running")

# --- INPUT PARAMETER ---
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=0.0, 
    step=0.5,
    help="Estimasi waktu operator berjalan dari 1 mesin ke mesin berikutnya"
)

# --- DEFAULT DATA (Sesuai Kasus Kamu) ---
default_data = [
    {"Process": "PLACING COMPONENT", "Duration": 15.02, "Actor": "Man"},
    {"Process": "LOADING-UNLOADING", "Duration": 4.48, "Actor": "Both"},
    {"Process": "STITCHING PROCESS", "Duration": 51.72, "Actor": "Machine"},
    {"Process": "LOADING-UNLOADING", "Duration": 4.48, "Actor": "Both"},
    {"Process": "TAKE RESULT", "Duration": 2.47, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

# --- TABEL INPUT DATA ---
st.subheader("📝 Elemen Proses (1 Siklus pada 1 Mesin)")
edited_df = st.data_editor(
    df_default,
    num_rows="dynamic",
    column_config={
        "Process": st.column_config.TextColumn("Nama Proses / Activity", width="large"),
        "Duration": st.column_config.NumberColumn("Waktu / Time (detik)", min_value=0.0, format="%.2f", width="medium"),
        "Actor": st.column_config.SelectboxColumn("Pelaku / Resource", options=["Man", "Machine", "Both"], width="medium")
    },
    hide_index=True,
    use_container_width=True
)

valid_rows = edited_df[
    (edited_df["Process"].str.strip() != "") & 
    (edited_df["Duration"] > 0)
].to_dict("records")

if valid_rows:
    # --- 1. ISOLASI ELEMEN KERJA ---
    # Service time (On-Machine Service): Both + Man pada Mesin
    # Internal prep: Man work yang bisa dikerjakan di luar mesin
    
    total_l = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Both"])
    total_m = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Machine"])
    total_man_only = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Man"])

    # Waktu mesin aktif 1 siklus
    mc_cycle_time = total_l + total_m
    
    # Total waktu kerja aktif Man untuk 1 unit/mesin
    man_work_per_mc = total_l + total_man_only

    # --- 2. HITUNG N MESIN IDEAL ---
    # N = (Waktu Mesin Running + Waktu Service) / (Waktu Kerja Man per Mesin + Travel Time)
    denom = man_work_per_mc + travel_time
    if denom > 0:
        n_raw = mc_cycle_time / denom
        num_machines = max(1, math.floor(n_raw))
    else:
        n_raw = 1.0
        num_machines = 1

    # --- 3. KALKULASI SUMMARY DENGAN METODE SIMULTAN / OVERLAPPING ---
    # System Cycle Time dibatasi oleh mana yang terpanjang antara Siklus Mesin atau Total Kerja Man
    total_man_work_all_mc = (man_work_per_mc * num_machines) + (travel_time * (num_machines - 1))
    
    # Total Cycle Time aktual per siklus stabil
    system_cycle_time = max(mc_cycle_time, total_man_work_all_mc)
    
    working_time_man = total_man_work_all_mc
    idle_time_man = max(0.0, system_cycle_time - working_time_man)
    utilization_man = (working_time_man / system_cycle_time * 100) if system_cycle_time > 0 else 0.0

    working_time_mc = mc_cycle_time
    idle_time_mc = max(0.0, system_cycle_time - working_time_mc)
    utilization_mc = (working_time_mc / system_cycle_time * 100) if system_cycle_time > 0 else 0.0

    # --- TABEL SUMMARY ---
    summary_data = [
        {"Resource": "Operator", "Working time": round(working_time_man, 2), "Idle time": round(idle_time_man, 2), "Total cycle time": round(system_cycle_time, 2), "Utilization": f"{utilization_man:.0f}%"},
        {"Resource": "Machine 1", "Working time": round(working_time_mc, 2), "Idle time": round(idle_time_mc, 2), "Total cycle time": round(system_cycle_time, 2), "Utilization": f"{utilization_mc:.0f}%"},
    ]
    
    for k in range(2, num_machines + 1):
        summary_data.append({
            "Resource": f"Machine {k}", 
            "Working time": round(working_time_mc, 2), 
            "Idle time": round(idle_time_mc, 2), 
            "Total cycle time": round(system_cycle_time, 2), 
            "Utilization": f"{utilization_mc:.0f}%"
        })

    summary_df = pd.DataFrame(summary_data)

    st.markdown("---")

    # --- 4. DISPLAY DASHBOARD SUMMARY ---
    st.subheader("📊 Summary (Sesuai Perhitungan Manual)")
    st.table(summary_df)

    # Export Ke Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
    excel_data = buffer.getvalue()

    st.download_button(
        label=f"📥 Download Summary (.xlsx)",
        data=excel_data,
        file_name=f"Summary_Man_Machine_{num_machines}MC.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Ketik nama proses dan durasi di tabel atas.")
