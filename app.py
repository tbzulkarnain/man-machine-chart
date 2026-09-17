import streamlit as st
import pandas as pd
import plotly.express as px
import math
import io

st.set_page_config(page_title="Man-Machine Process Sheet & Analyzer", layout="wide")

st.title("⚙️ Multi Man-Machine Process Sheet & Analyzer")
st.caption("Aplikasi Industrial Engineering untuk pembuatan Process Sheet, Analisis Utilisasi, dan Manning Ratio")

st.markdown("""
**Petunjuk Input:** 
1. Isi daftar proses pada tabel di bawah ini.
2. Pilih pelaku: **Man** (Operator), **Machine** (Mesin), atau **Both** (Keduanya, misal: Loading/Unloading).
3. Tabel hasil di bawah akan otomatis memisahkan alur proses Man vs Machine beserta analisis lengkapnya.
""")

# --- DEFAULT DATA (DAPAT DI-EDIT USER) ---
default_data = [
    {"Process": "Placing component mold 1#", "Duration": 29.86, "Actor": "Both"},
    {"Process": "Close mold 1# & loading to Hot MC 1", "Duration": 12.19, "Actor": "Machine"},
    {"Process": "Heat press Mold 1#", "Duration": 97.64, "Actor": "Machine"},
    {"Process": "Unloading mold 1# & move to cold MC 1", "Duration": 6.99, "Actor": "Both"},
    {"Process": "Cold press Mold 1#", "Duration": 59.59, "Actor": "Machine"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

# --- TABEL INPUT DATA ---
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

# --- FILTER DATA VALID ---
valid_rows = edited_df[
    (edited_df["Process"].str.strip() != "") & 
    (edited_df["Duration"] > 0)
].to_dict("records")

if valid_rows:
    excel_rows = []
    timeline_data = []
    current_time = 0.0

    total_l = 0.0  # Waktu Both (Loading/Unloading)
    total_m = 0.0  # Waktu Machine Murni
    
    for item in valid_rows:
        proc = item["Process"]
        dur = item["Duration"]
        act = item["Actor"]
        
        start_t = current_time
        finish_t = current_time + dur
        current_time = finish_t
        
        # Logika pemisahan Process Sheet
        if act == "Both":
            man_p, mc_p = proc, proc
            timeline_data.append({"Actor": "Man", "Process": proc, "Start": start_t, "Finish": finish_t, "Duration": dur, "Type": "Working"})
            timeline_data.append({"Actor": "Machine", "Process": proc, "Start": start_t, "Finish": finish_t, "Duration": dur, "Type": "Working"})
            total_l += dur
        elif act == "Man":
            man_p, mc_p = proc, "idle / waiting"
            timeline_data.append({"Actor": "Man", "Process": proc, "Start": start_t, "Finish": finish_t, "Duration": dur, "Type": "Working"})
            timeline_data.append({"Actor": "Machine", "Process": f"Idle ({proc})", "Start": start_t, "Finish": finish_t, "Duration": dur, "Type": "Idle"})
        elif act == "Machine":
            man_p, mc_p = "idle / waiting", proc
            timeline_data.append({"Actor": "Machine", "Process": proc, "Start": start_t, "Finish": finish_t, "Duration": dur, "Type": "Working"})
            timeline_data.append({"Actor": "Man", "Process": f"Idle ({proc})", "Start": start_t, "Finish": finish_t, "Duration": dur, "Type": "Idle"})
            total_m += dur

        excel_rows.append({
            "Accumulated Time (s)": round(current_time, 2),
            "Process Operator": man_p,
            "Operator Time (s)": round(dur, 2),
            "Process Machine": mc_p,
            "Machine Time (s)": round(dur, 2)
        })

    sheet_df = pd.DataFrame(excel_rows)
    chart_df = pd.DataFrame(timeline_data)
    total_cycle_time = current_time

    # --- KALKULASI METRIK IE ---
    man_work = chart_df[(chart_df["Actor"] == "Man") & (chart_df["Type"] == "Working")]["Duration"].sum()
    mc_work = chart_df[(chart_df["Actor"] == "Machine") & (chart_df["Type"] == "Working")]["Duration"].sum()

    man_util = (man_work / total_cycle_time * 100) if total_cycle_time > 0 else 0
    mc_util = (mc_work / total_cycle_time * 100) if total_cycle_time > 0 else 0

    st.markdown("---")
    
    # 1. DASHBOARD SUMMARY
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Cycle Time", f"{total_cycle_time:.2f} detik")
    c2.metric("Utilisasi Operator (Man)", f"{man_util:.1f}%")
    c3.metric("Utilisasi Mesin (Machine)", f"{mc_util:.1f}%")

    st.markdown("---")

    # 2. HASIL PROCESS SHEET (EXCEL FORMAT TABLE)
    st.subheader("📋 Multi-Resource Process Sheet")
    st.dataframe(sheet_df, use_container_width=True)

    # FITUR DOWNLOAD EXCEL
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sheet_df.to_excel(writer, index=False, sheet_name="Process Sheet")
    excel_data = buffer.getvalue()

    st.download_button(
        label="📥 Download Process Sheet (.xlsx)",
        data=excel_data,
        file_name="Man_Machine_Process_Sheet.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("---")

    # 3. ANALISIS MANNING RATIO (JUMLAH MESIN IDEAL)
    st.subheader("🧮 Analisis Manning Ratio (Jumlah Mesin Ideal)")
    col_input, col_result = st.columns([1, 2])
    
    with col_input:
        travel_time = st.number_input(
            "Waktu Pindah Antar Mesin (detik)", 
            min_value=0.0, 
            value=2.0,
            help="Estimasi waktu operator berjalan dari 1 mesin ke mesin lainnya"
        )
    
    denom = total_l + travel_time
    if denom > 0:
        n_raw = (total_l + total_m) / denom
        n_floor = math.floor(n_raw)
        n_ceil = math.ceil(n_raw)
    else:
        n_raw, n_floor, n_ceil = 1, 1, 1

    with col_result:
        st.info(f"""
        **Hasil Perhitungan Man-Machine Ratio ($N$):**
        *   **Rasio Teoritis ($N$):** `{n_raw:.2f}` Mesin
        *   **Rekomendasi Mesin Ideal:** **{n_floor} Mesin** per 1 Operator.
        
        *Penjelasan:* Jika memegang **{n_floor} mesin**, operator tidak akan mengalami *idle time*.
        """)

else:
    st.info("Ketik nama proses dan durasi di tabel atas untuk menampilkan Process Sheet & Analisis.")
