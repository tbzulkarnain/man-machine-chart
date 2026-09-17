import streamlit as st
import pandas as pd
import plotly.express as px
import math

st.set_page_config(page_title="Man-Machine Chart Builder", layout="wide")

st.title("⚙️ Man-Machine Chart Builder")
st.caption("Aplikasi Industrial Engineering untuk analisis alur kerja & optimasi jumlah mesin per operator")

st.markdown("""
**Petunjuk:** 
1. Isi tabel di bawah ini secara langsung seperti di Excel.
2. Pilih pelaku: **Man**, **Machine**, atau **Both** (misal: Loading/Unloading).
3. Hasil kalkulasi utilisasi & estimasi jumlah mesin ideal akan dihitung otomatis.
""")

# --- PREPARE DEFAULT DATA ---
default_data = [
    {"Process": "Loading Material", "Duration": 10, "Actor": "Both"},
    {"Process": "Auto Cutting", "Duration": 40, "Actor": "Machine"},
    {"Process": "Prepare Next Lot", "Duration": 10, "Actor": "Man"},
    {"Process": "Unloading Material", "Duration": 10, "Actor": "Both"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
    {"Process": "", "Duration": 0, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

# --- TABEL INTERAKTIF ---
edited_df = st.data_editor(
    df_default,
    num_rows="dynamic",
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
valid_rows = edited_df[
    (edited_df["Process"].str.strip() != "") & 
    (edited_df["Duration"] > 0)
].to_dict("records")

if valid_rows:
    timeline_data = []
    current_time = 0
    
    # Inisialisasi variabel untuk rumus N
    total_l = 0  # Loading & Unloading (Both)
    total_m = 0  # Machine running alone
    total_manual_man = 0 # Man working alone
    
    for item in valid_rows:
        proc = item["Process"]
        dur = item["Duration"]
        act = item["Actor"]
        
        start = current_time
        finish = start + dur
        
        if act == "Both":
            timeline_data.append({"Actor": "Man", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
            timeline_data.append({"Actor": "Machine", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
            total_l += dur
        elif act == "Man":
            timeline_data.append({"Actor": "Man", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
            timeline_data.append({"Actor": "Machine", "Process": f"Idle ({proc})", "Start": start, "Finish": finish, "Duration": dur, "Type": "Idle"})
            total_manual_man += dur
        elif act == "Machine":
            timeline_data.append({"Actor": "Machine", "Process": proc, "Start": start, "Finish": finish, "Duration": dur, "Type": "Working"})
            timeline_data.append({"Actor": "Man", "Process": f"Idle ({proc})", "Start": start, "Finish": finish, "Duration": dur, "Type": "Idle"})
            total_m += dur
            
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
    
    # Konversi detik ke format datetime dummy agar Plotly timeline bisa baca dengan benar
    chart_df["Start_dt"] = pd.to_datetime(chart_df["Start"], unit="s", origin="2000-01-01")
    chart_df["Finish_dt"] = pd.to_datetime(chart_df["Finish"], unit="s", origin="2000-01-01")
    
    fig = px.timeline(
        chart_df,
        x_start="Start_dt",
        x_end="Finish_dt",
        y="Actor",
        color="Type",
        hover_data=["Process", "Duration"],
        color_discrete_map=color_map,
    )
    
    fig.update_yaxes(autorange="reversed")
    # Format sumbu X supaya nampilin angka detik, bukan tanggal
    fig.update_xaxes(tickformat="%S", title_text="Waktu (detik)")
    fig.update_layout(yaxis_title="Resource", height=300)
    
    st.plotly_chart(fig, use_container_width=True)

    # --- FITUR ADVANCED: ESTIMASI MESIN IDEAL ---
    st.markdown("---")
    st.subheader("🧮 Analisis Manning Ratio (Jumlah Mesin Ideal)")
    
    col_input, col_result = st.columns([1, 2])
    
    with col_input:
        travel_time = st.number_input(
            "Waktu Perpindahan Antar Mesin (detik)", 
            min_value=0, 
            value=2,
            help="Estimasi waktu operator berjalan/pindah dari mesin 1 ke mesin berikutnya"
        )
    
    # Rumus Man-Machine Ratio: N = (l + m) / (l + w)
    denominator = total_l + travel_time
    if denominator > 0:
        n_raw = (total_l + total_m) / denominator
        n_floor = math.floor(n_raw) # Pembulatan ke bawah (Max Machine tanpa idle operator)
        n_ceil = math.ceil(n_raw)   # Pembulatan ke atas
    else:
        n_raw = 1
        n_floor = 1
        n_ceil = 1

    with col_result:
        st.info(f"""
        **Hasil Perhitungan Man-Machine Ratio ($N$):**
        *   **Rasio Teoritis ($N$):** `{n_raw:.2f}` Mesin
        *   **Rekomendasi Jumlah Mesin Ideal:** **{n_floor} Mesin** per 1 Operator.
        
        *Catatan:* Jika memegang **{n_floor} mesin**, operator tidak akan menunggu mesin (*zero worker idle*). Jika memegang **{n_ceil} mesin**, utilisasi operator mencapai 100% namun mesin akan mengalami sedikit waktu tunggu.
        """)

else:
    st.info("Ketik nama proses dan durasi di tabel atas untuk melihat chart & analisis.")
