import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(page_title="Industrial Engineering - Process Sheet & Summary", layout="wide")

st.title("⚙️ Multi-Machine Process Sheet & Summary Analyzer")
st.caption("Aplikasi Industrial Engineering dengan Formulasi Utilisasi & Idle Time Presisi")

# --- INPUT PARAMETER ---
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=2.0, 
    step=0.5,
    help="Estimasi waktu operator berjalan dari 1 mesin ke mesin berikutnya"
)

# --- DEFAULT DATA ---
default_data = [
    {"Process": "Loading / Placement Mold 1#", "Duration": 29.86, "Actor": "Both"},
    {"Process": "Close Mold & Start Machine", "Duration": 12.19, "Actor": "Machine"},
    {"Process": "Auto Heat Pressing", "Duration": 97.64, "Actor": "Machine"},
    {"Process": "Unloading / Move Mold", "Duration": 6.99, "Actor": "Both"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
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
    # --- 1. IDENTIFIKASI WAKTU DASAR ---
    total_l = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Both"])
    total_m = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Machine"])
    total_man_only = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Man"])

    # Waktu Pelayanan Man per Mesin
    service_time_per_mc = total_l + total_man_only

    # Rumus Manning Ratio Ideal (N)
    denom = service_time_per_mc + travel_time
    if denom > 0:
        n_raw = (total_l + total_m) / denom
        num_machines = max(1, math.floor(n_raw))
    else:
        n_raw = 1.0
        num_machines = 1

    # --- 2. RUMUS SUMMARY IE PRESISI ---
    single_mc_cycle = total_l + total_m + total_man_only
    total_man_active = (service_time_per_mc * num_machines) + (travel_time * (num_machines - 1))
    
    # Cycle Time Sistem (Penentu Bottleneck)
    system_cycle_time = max(single_mc_cycle, total_man_active)

    # Kalkulasi Idle Time & Utilisasi
    man_idle_time = max(0.0, system_cycle_time - total_man_active)
    utilitas_man = (total_man_active / system_cycle_time * 100) if system_cycle_time > 0 else 0.0

    mc_active_time = total_l + total_m
    mc_idle_time = max(0.0, system_cycle_time - mc_active_time)
    utilitas_mc = (mc_active_time / system_cycle_time * 100) if system_cycle_time > 0 else 0.0

    # --- 3. GENERATOR PROCESS SHEET TABLE ---
    excel_rows = []
    current_time = 0.0

    for m_idx in range(1, num_machines + 1):
        for item in valid_rows:
            proc = item["Process"]
            dur = item["Duration"]
            act = item["Actor"]
            
            current_time += dur
            
            row_dict = {
                "Accumulated Time (s)": round(current_time, 2),
                "Process Operator": f"{proc} (MC {m_idx})",
                "Operator Time (s)": round(dur, 2)
            }
            
            for k in range(1, num_machines + 1):
                if k == m_idx:
                    if act in ["Both", "Machine"]:
                        row_dict[f"Process MC {k}"] = proc
                    else:
                        row_dict[f"Process MC {k}"] = f"idle (doing {proc})"
                else:
                    row_dict[f"Process MC {k}"] = "running / waiting"
                
                row_dict[f"MC {k} Time (s)"] = round(dur, 2)
                
            excel_rows.append(row_dict)
            
        if m_idx < num_machines and travel_time > 0:
            current_time += travel_time
            row_dict = {
                "Accumulated Time (s)": round(current_time, 2),
                "Process Operator": f"Walk to Machine {m_idx + 1}",
                "Operator Time (s)": round(travel_time, 2)
            }
            for k in range(1, num_machines + 1):
                row_dict[f"Process MC {k}"] = "running / idle"
                row_dict[f"MC {k} Time (s)"] = round(travel_time, 2)
            excel_rows.append(row_dict)

    sheet_df = pd.DataFrame(excel_rows)

    # TABEL METRIK REVISI
    summary_data = [
        {"Metric Parameter": "Jumlah Mesin Ideal (N)", "Value": f"{num_machines} Mesin", "Unit": "MC"},
        {"Metric Parameter": "System Cycle Time (Total Waktu Siklus)", "Value": round(system_cycle_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Man Time (Waktu Kerja Aktif Operator)", "Value": round(total_man_active, 2), "Unit": "detik"},
        {"Metric Parameter": "Man Idle Time (Waktu Operator Menganggur)", "Value": round(man_idle_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Utilitas Man", "Value": f"{utilitas_man:.2f}%", "Unit": "%"},
        {"Metric Parameter": "Machine Active Time (per Mesin)", "Value": round(mc_active_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Machine Idle Time (per Mesin)", "Value": round(mc_idle_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Utilitas Machine (Rata-rata per Mesin)", "Value": f"{utilitas_mc:.2f}%", "Unit": "%"},
    ]
    
    summary_df = pd.DataFrame(summary_data)

    st.markdown("---")

    # --- 4. TAMPILAN DASHBOARD METRICS SUMMARY ---
    st.subheader("📊 Ringkasan Metrik (Summary Report - Corrected)")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("System Cycle Time", f"{system_cycle_time:.2f} s")
    c2.metric("Utilitas Man", f"{utilitas_man:.1f}%", delta=f"Idle: {man_idle_time:.1f} s")
    c3.metric("Utilitas Machine", f"{utilitas_mc:.1f}%", delta=f"Idle: {mc_idle_time:.1f} s")
    c4.metric("Mesin Ideal (N)", f"{num_machines} MC")

    st.table(summary_df)

    st.markdown("---")

    # --- 5. TAMPILAN PROCESS SHEET & EXPORT EXCEL ---
    st.subheader(f"📋 Process Sheet ({num_machines} Mesin)")
    st.dataframe(sheet_df, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary & Metrics")
        sheet_df.to_excel(writer, index=False, sheet_name=f"Process Sheet ({num_machines} MC)")
    excel_data = buffer.getvalue()

    st.download_button(
        label=f"📥 Download Laporan Lengkap (.xlsx)",
        data=excel_data,
        file_name=f"Man_Machine_Analysis_{num_machines}MC.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Ketik nama proses dan durasi di tabel atas untuk menghitung Summary & Process Sheet.")
