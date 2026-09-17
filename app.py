import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Man-Machine Chart Builder", layout="wide")

st.title("⚙️ Man-Machine Chart Builder")
st.caption("Aplikasi Industrial Engineering untuk analisis utilisasi Operator & Mesin")

# --- SIDEBAR: INPUT DATA ---
st.sidebar.header("Tambah Aktivitas")

if "tasks" not in st.session_state:
    st.session_state.tasks = [
        {"Actor": "Operator", "Task": "Load Material", "Start": 0, "Duration": 15, "Type": "Working"},
        {"Actor": "Machine", "Task": "Idle (Waiting Load)", "Start": 0, "Duration": 15, "Type": "Idle"},
        {"Actor": "Machine", "Task": "Auto Cutting", "Start": 15, "Duration": 60, "Type": "Working"},
        {"Actor": "Operator", "Task": "Prepare Next Lot", "Start": 15, "Duration": 30, "Type": "Working"},
        {"Actor": "Operator", "Task": "Idle (Waiting Machine)", "Start": 45, "Duration": 30, "Type": "Idle"},
        {"Actor": "Operator", "Task": "Unload Material", "Start": 75, "Duration": 15, "Type": "Working"},
        {"Actor": "Machine", "Task": "Idle (Waiting Unload)", "Start": 75, "Duration": 15, "Type": "Idle"},
    ]

with st.sidebar.form("add_task_form"):
    actor = st.selectbox("Aktor", ["Operator", "Machine"])
    task_name = st.text_input("Nama Aktivitas", "Proses Cepat")
    start_time = st.number_input("Waktu Mulai (detik)", min_value=0, value=0)
    duration = st.number_input("Durasi (detik)", min_value=1, value=10)
    task_type = st.selectbox("Tipe", ["Working", "Idle"])
    
    submitted = st.form_submit_button("Tambah ke Chart")
    if submitted:
        st.session_state.tasks.append({
            "Actor": actor,
            "Task": task_name,
            "Start": start_time,
            "Duration": duration,
            "Type": task_type
        })
        st.rerun()

if st.sidebar.button("Reset Data"):
    st.session_state.tasks = []
    st.rerun()

# --- KALKULASI LOGIKA IE ---
df = pd.DataFrame(st.session_state.tasks)

if not df.empty:
    df["Finish"] = df["Start"] + df["Duration"]
    cycle_time = df["Finish"].max()

    # Hitung Working Time
    op_work = df[(df["Actor"] == "Operator") & (df["Type"] == "Working")]["Duration"].sum()
    mc_work = df[(df["Actor"] == "Machine") & (df["Type"] == "Working")]["Duration"].sum()

    op_utilization = (op_work / cycle_time * 100) if cycle_time > 0 else 0
    mc_utilization = (mc_work / cycle_time * 100) if cycle_time > 0 else 0

    # --- DASHBOARD METRICS ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Cycle Time", f"{cycle_time} detik")
    col2.metric("Utilisasi Operator", f"{op_utilization:.1f}%")
    col3.metric("Utilisasi Mesin", f"{mc_utilization:.1f}%")

    st.markdown("---")

    # --- VISUALISASI CHART (PLOTLY GANTT) ---
    st.subheader("📊 Visualisasi Man-Machine Chart")
    
    # Custom warna: Working (Biru/Hijau), Idle (Merah/Abu)
    color_map = {"Working": "#2b5c8f", "Idle": "#d9534f"}
    
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Actor",
        color="Type",
        hover_data=["Task", "Duration"],
        color_discrete_map=color_map,
        title="Timeline Aktivitas Operator vs Mesin"
    )
    
    fig.update_yaxes(autorange="reversed") # Operator di atas, Mesin di bawah
    fig.update_layout(xaxis_title="Waktu (detik)", yaxis_title="Resource", height=350)
    
    st.plotly_chart(fig, use_container_width=True)

    # --- TABEL DATA ---
    with st.expander("Lihat Rincian Data Tabel"):
        st.dataframe(df[["Actor", "Task", "Start", "Finish", "Duration", "Type"]], use_container_width=True)
else:
    st.info("Belum ada data. Silakan isi form di sidebar untuk memulai.")
