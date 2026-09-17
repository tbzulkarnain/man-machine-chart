import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Man-Machine Chart Builder", layout="wide")

st.title("⚙️ Man-Machine Chart Builder")
st.caption("Aplikasi simpel Industrial Engineering untuk analisis alur kerja Operator & Mesin")

st.markdown("""
**Petunjuk:** 
1. Isi tabel di bawah ini secara langsung seperti di Excel.
2. Pilih pelaku: **Man**, **Machine**, atau **Both** (keduanya).
3. Kamu bisa menambah baris baru di bagian bawah tabel jika 10 baris kurang.
""")

# --- PREPARE DEFAULT DATA (10 BARIS) ---
default_data = [
    {"Process": "Loading Material", "Duration": 10, "Actor": "Both"},
    {"Process": "Auto Cutting", "Duration": 40, "Actor": "Machine"},
    {"Process": "Prepare Next Lot", "Duration": 20, "Actor": "Man"},
    {"Process": "Unloading Material", "Duration": 10, "Actor": "Both"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

# --- TABEL INTERAKTIF (BISA DI-EDIT LANGSUNG) ---
edited_df = st.data_editor(
    df_default,
    num_rows="dynamic", # Memungkinkan user menambah/menghapus baris sesuka hati
    column_config={
        "Process": st.column_config.TextColumn(
            "Nama Proses",
            help="Isi nama langkah/proses kerja",
            width="large"
        ),
        "Duration": st.column_config.NumberColumn(
            "Waktu (detik)",
            help="Durasi proses dalam detik",
            min_value=0,
            default=0,
            width="medium"
        ),
        "Actor": st.column_config.SelectboxColumn(
            "Pelaku",
            help="Pilih siapa yang melakukan proses",
            options=["Man", "Machine", "Both"],
            default="Man",
            width="medium"
        )
    },
    hide_index=True,
    use_container_width=True
)

# --- FILTER & HITUNG LOGIKA IE ---
# Hanya ambil baris yang nama prosesnya diisi dan durasinya > 0
valid_rows = edited_df[
    (edited_df["Process"].str.strip() != "") & 
    (edited_df["Duration"] > 0)
].to_dict("records")

if valid_rows:
    timeline_data = []
    current_time = 0
    
    for item in valid_rows:
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
            timeline_data.append({"Actor": "Machine", "Process": f"Idle ({proc})", "Start": start, "Finish": finish, "Duration": dur, "Type": "Idle"})
        elif act == "Machine":
            timeline_data.append({"Actor": "Machine", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
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
    st.info("Ketik nama proses dan durasi di tabel atas untuk melihat chart.")
