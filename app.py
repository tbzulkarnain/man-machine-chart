import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(page_title="Industrial Engineering - Process Sheet & Summary", layout="wide")

st.title("⚙️ Multi-Machine Process Sheet & Summary Analyzer")
st.caption("Aplikasi Industrial Engineering untuk Analisis Waktu Kerja, Idle Time, Utilisasi, & Export Excel")

st.markdown("""
**Petunjuk Input:**
1. Isi elemen proses kerja untuk **1 produk / 1 mesin**.
2. Masukkan waktu pindah (*Travel Time*) antar mesin jika ada.
3. Aplikasi akan menghitung **Jumlah Mesin Ideal ($N$)** dan menghasilkan **Ringkasan Metrik (Summary)** serta **Process Sheet Multi-Mesin**.
""")

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
    # --- 1. KALKULASI MATHEMATICAL MANNING RATIO (N) ---
    total_l = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Both"])
    total_m = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Machine"])
    total_man_only = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Man"])

    # Rumus Manning Ratio: N = (l + m) / (l + w)
    denom = total_l + travel_time
    if denom > 0:
        n_raw = (total_l + total_m) / denom
        num_machines = max(1, math.floor(n_raw))
    else:
        n_raw = 1.0
        num_machines = 1

    # --- 2. LOGIKA GENERATOR PROCESS SHEET & SUMMARY TIME ---
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
            
        # Travel time antar mesin
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

    # --- 3. KALKULASI METRIK SUMMARY (INDUSTRIAL ENGINEERING) ---
    total_cycle_time = current_time
    
    # Total Man Time = Total Cycle Time Keseluruhan
    total_man_time = total_cycle_time
    # Total Machine Time = Total Cycle Time x Jumlah Mesin Terpasang
    total_mc_time = total_cycle_time * num_machines
    
    # Man Time (Waktu Kerja Aktif Man) = (Both + Man_only) * N + Travel Time
    man_time = ((total_l + total_man_only) * num_machines) + (travel_time * (num_machines - 1))
    man_idle_time = max(0.0, total_man_time - man_time)
    
    # Machine Time (Waktu Kerja Aktif Seluruh Mesin) = (Both + Machine) * N
    mc_time = (total_l + total_m) * num_machines
    mc_idle_time = max(0.0, total_mc_time - mc_time)
    
    # Utilitas
    utilitas_man = (man_time / total_man_time * 100) if total_man_time > 0 else 0.0
    utilitas_mc = (mc_time / total_mc_time * 100) if total_mc_time > 0 else 0.0

    # TABEL SUMMARY METRICS
    summary_data = [
        {"Metric Parameter": "Jumlah Mesin Ideal (N)", "Value": f"{num_machines} Mesin", "Unit": "MC"},
        {"Metric Parameter": "Man Time (Waktu Kerja Operator)", "Value": round(man_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Machine Time (Waktu Kerja Mesin)", "Value": round(mc_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Man Idle Time (Waktu Menganggur Operator)", "Value": round(man_idle_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Machine Idle Time (Waktu Menganggur Mesin)", "Value": round(mc_idle_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Total Man Time (Ketersediaan Operator)", "Value": round(total_man_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Total Machine Time (Ketersediaan Seluruh Mesin)", "Value": round(total_mc_time, 2), "Unit": "detik"},
        {"Metric Parameter": "Utilitas Man", "Value": f"{utilitas_man:.2f}%", "Unit": "%"},
        {"Metric Parameter": "Utilitas Machine", "Value": f"{utilitas_mc:.2f}%", "Unit": "%"},
    ]
    
    summary_df = pd.DataFrame(summary_data)

    st.markdown("---")

    # --- 4. TAMPILAN DASHBOARD METRICS SUMMARY ---
    st.subheader("📊 Ringkasan Metrik (Summary Report)")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Man Time", f"{total_man_time:.2f} s")
    c2.metric("Man Idle Time", f"{man_idle_time:.2f} s", delta=f"Utilitas {utilitas_man:.1f}%")
    c3.metric("Machine Idle Time", f"{mc_idle_time:.2f} s", delta=f"Utilitas {utilitas_mc:.1f}%")
    c4.metric("Mesin Ideal (N)", f"{num_machines} MC")

    st.table(summary_df)

    st.markdown("---")

    # --- 5. TAMPILAN PROCESS SHEET & EXPORT EXCEL ---
    st.subheader(f"📋 Process Sheet ({num_machines} Mesin)")
    st.dataframe(sheet_df, use_container_width=True)

    # Export Ke Excel dengan 2 Sheet (Summary & Process Sheet)
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
