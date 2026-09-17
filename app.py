import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Man-Machine Chart Builder", layout="wide")

st.title("⚙️ Man-Machine Chart Builder")
st.caption("Aplikasi simpel untuk analisis alur kerja Operator & Mesin")

# Inisialisasi data di session_state
if "raw_processes" not in st.session_state:
    # Contoh data awal sederhana
    st.session_state.raw_processes = [
        {"Process": "Loading Material", "Duration": 10, "Actor": "Both"},
        {"Process": "Auto Cutting", "Duration": 40, "Actor": "Machine"},
        {"Process": "Prepare Next Lot", "Duration": 20, "Actor": "Man"},
        {"Process": "Unloading Material", "Duration": 10, "Actor": "Both"},
    ]

# --- SIDEBAR: FORM INPUT SIMPEL ---
st.sidebar.header("➕ Tambah Proses Baru")

with st.sidebar.form("add_process_form"):
    process_name = st.text_input("1. Nama Proses", placeholder="Contoh: Loading Material")
    duration = st.number_input("2. Waktu (detik)", min_value=1, value=10)
    actor = st.selectbox("3. Pelaku", ["Man", "Machine", "Both"])
    
    submitted = st.form_submit_button("Tambah Proses")
    if submitted:
        if process_name.strip() == "":
            st.sidebar.error("Nama proses tidak boleh kosong!")
        else:
            st.session_state.raw_processes.append({
                "Process": process_name,
                "Duration": duration,
                "Actor": actor
            })
            st.rerun()

if st.sidebar.button("🗑️ Reset Semua Data"):
    st.session_state.raw_processes = []
    st.rerun()

# --- TAMPILKAN TABEL INPUT USER ---
st.subheader("📋 Daftar Proses Kerja")

if st.session_state.raw_processes:
    input_df = pd.DataFrame(st.session_state.raw_processes)
    
    # Tampilkan tabel input
    st.dataframe(input_df, use_container_width=True)
    
    # --- LOGIKA OTOMATIS GENERATE TIMELINE ---
    timeline_data = []
    current_time_man = 0
    current_time_machine = 0
    
    # Hitung waktu secara sekuensial berdasarkan urutan input
    current_time = 0
    for item in st.session_state.raw_processes:
        proc = item["Process"]
        dur = item["Duration"]
        act = item["Actor"]
        
        start = current_time
        finish = start + dur
        
        if act == "Both":
            timeline_data.append({"Actor": "Man", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
            timeline_data.append({"Actor": "Machine", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
        elif act == "Man":
            timeline_data.append({"Actor": "Man", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
            # Mesin idle saat Man bekerja sendiri
            timeline_data.append({"Actor": "Machine", "Process": f"Idle ({proc})", "Start": start, "Finish": finish, "Duration": dur, "Type": "Idle"})
        elif act == "Machine":
            timeline_data.append({"Actor": "Machine", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
            # Man idle saat Machine bekerja sendiri
            timeline_data.append({"Actor": "Man", "Process": f"Idle ({proc})", "Start": start, "Finish": finish, "Duration": dur, "Type": "Idle"})
            
        current_time = finish

    chart_df = pd.DataFrame(timeline_data)
    total_cycle_time = current_time

    # --- KALKULASI METRIK ---
    man_work = chart_df[(chart_df["Actor"] == "Man") & (chart_df["Type"] == "Working")]["Duration"].sum()
    mc_work = chart_df[(chart_df["Actor"] == "Machine") & (chart_df["Type"] == "Working")]["Duration"].sum()

    man_util = (man_work / total_cycle_time * 100) if total_cycle_time > 0 else 0
    mc_util = (mc_work / total_cycle_time * 100) if total_cycle_time > 0 else 0

    st.markdown("---")
    
    # --- DASHBOARD METRICS ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Cycle Time", f"{total_cycle_time} detik")
    c2.metric("Utilisasi Man", f"{man_util:.1f}%")
    c3.metric("Utilisasi Machine", f"{mc_util:.1f}%")

    # --- VISUALISASI CHART ---
    st.subheader("📊 Man-Machine Chart (Otomatis)")
    
    color_map = {"Working": "#1f77b4", "Idle": "#d62728"}
    
    fig = px.timeline(
        chart_df,
        x_start="Start",
        x_end="Finish",
        y="Actor",
        color="Type",
        hover_data=["Process", "Duration"],
        color_discrete_map=color_map,
    )
    
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(xaxis_title="Waktu (detik)", yaxis_title="Resource", height=300)
    
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Belum ada data proses. Silakan isi form di sidebar kiri untuk menambahkan proses.")
