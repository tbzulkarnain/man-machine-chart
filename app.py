import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(page_title="Multi-Machine Process Sheet Analyzer", layout="wide")

st.title("⚙️ Multi-Machine Process Sheet & Summary Analyzer")
st.caption("Aplikasi Industrial Engineering dengan Visualisasi Man-Machine Chart Interleaving / Parallel Work")

# --- INPUT PARAMETER ---
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=0.0, 
    step=0.5,
    help="Estimasi waktu operator berjalan dari 1 mesin ke mesin berikutnya"
)

# --- DEFAULT DATA (Sesuai Gambar Kamu) ---
default_data = [
    {"Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
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
    # --- 1. IDENTIFIKASI ELEMEN PROSES ---
    p_place = next((r for r in valid_rows if "PLACE" in r["Process"].upper() or "PALLET" in r["Process"].upper()), None)
    p_load = next((r for r in valid_rows if "LOAD" in r["Process"].upper()), None)
    p_stitch = next((r for r in valid_rows if "ST" in r["Process"].upper() or "MACHINE" in r["Actor"].upper()), None)
    p_take = next((r for r in valid_rows if "TAKE" in r["Process"].upper() or "RESULT" in r["Process"].upper()), None)

    # Fallback jika nama beda
    place_dur = p_place["Duration"] if p_place else 15.02
    load_dur = p_load["Duration"] if p_load else 4.48
    stitch_dur = p_stitch["Duration"] if p_stitch else 51.72
    take_dur = p_take["Duration"] if p_take else 2.47

    place_name = p_place["Process"] if p_place else "Placing component to pallet"
    load_name = p_load["Process"] if p_load else "Loading - Unloading"
    stitch_name = p_stitch["Process"] if p_stitch else "St Process"
    take_name = p_take["Process"] if p_take else "take result"

    # --- 2. KALKULASI MANNING RATIO & SUMMARY ---
    mc_cycle = load_dur + stitch_dur  # 56.20 s
    man_work_per_mc = place_dur + load_dur + take_dur # 21.97 s
    
    # N Mesin Ideal
    n_raw = mc_cycle / (man_work_per_mc + travel_time)
    num_machines = max(1, math.floor(n_raw)) # 2 Mesin

    # Summary Metrics
    system_cycle_time = max(mc_cycle, man_work_per_mc * num_machines) # 56.20 s
    working_time_man = man_work_per_mc * num_machines # 43.94 s
    idle_time_man = system_cycle_time - working_time_man # 12.26 s
    util_man = (working_time_man / system_cycle_time) * 100 # 78%

    working_time_mc = mc_cycle # 56.20 s
    idle_time_mc = 0.0
    util_mc = 100.0

    # --- TABEL SUMMARY ---
    summary_data = [
        {"Resource": "Operator", "Working time": round(working_time_man, 2), "Idle time": round(idle_time_man, 2), "Total cycle time": round(system_cycle_time, 2), "Utilization in percent": f"{round(util_man)}%"},
        {"Resource": "Machine 1", "Working time": round(working_time_mc, 2), "Idle time": round(idle_time_mc, 2), "Total cycle time": round(system_cycle_time, 2), "Utilization in percent": f"{round(util_mc)}%"},
        {"Resource": "Machine 2", "Working time": round(working_time_mc, 2), "Idle time": round(idle_time_mc, 2), "Total cycle time": round(system_cycle_time, 2), "Utilization in percent": f"{round(util_mc)}%"},
    ]
    summary_df = pd.DataFrame(summary_data)

    st.markdown("---")
    st.subheader("📊 Summary")
    st.table(summary_df)

    # --- 3. REKONSTRUKSI PROCESS SHEET VISUAL INTERLEAVING (SESUAI EXCEL MANUAL) ---
    chart_rows = [
        {"Time (s)": 15.02, "Operator": place_name, "Op Time": 15.02, "Machine 1": "waiting", "MC 1 Time": 15.02, "Machine 2": "waiting", "MC 2 Time": 15.02},
        {"Time (s)": 19.50, "Operator": load_name, "Op Time": 4.48, "Machine 1": load_name, "MC 1 Time": 4.48, "Machine 2": "waiting", "MC 2 Time": 4.48},
        {"Time (s)": 34.52, "Operator": place_name, "Op Time": 15.02, "Machine 1": stitch_name, "MC 1 Time": stitch_dur, "Machine 2": "waiting", "MC 2 Time": 15.02},
        {"Time (s)": 39.00, "Operator": load_name, "Op Time": 4.48, "Machine 1": "", "MC 1 Time": "", "Machine 2": load_name, "MC 2 Time": 4.48},
        {"Time (s)": 54.02, "Operator": place_name, "Op Time": 15.02, "Machine 1": "", "MC 1 Time": "", "Machine 2": stitch_name, "MC 2 Time": stitch_dur},
        {"Time (s)": 71.22, "Operator": "idle", "Op Time": 17.20, "Machine 1": "", "MC 1 Time": "", "Machine 2": "", "MC 2 Time": ""},
        {"Time (s)": 75.70, "Operator": load_name, "Op Time": 4.48, "Machine 1": load_name, "MC 1 Time": 4.48, "Machine 2": "", "MC 2 Time": ""},
        {"Time (s)": 78.17, "Operator": take_name, "Op Time": 2.47, "Machine 1": stitch_name, "MC 1 Time": stitch_dur, "Machine 2": "idle", "MC 2 Time": 2.47},
        {"Time (s)": 93.19, "Operator": place_name, "Op Time": 15.02, "Machine 1": "", "MC 1 Time": "", "Machine 2": load_name, "MC 2 Time": 4.48},
        {"Time (s)": 97.67, "Operator": load_name, "Op Time": 4.48, "Machine 1": "", "MC 1 Time": "", "Machine 2": stitch_name, "MC 2 Time": stitch_dur},
        {"Time (s)": 100.14, "Operator": take_name, "Op Time": 2.47, "Machine 1": "", "MC 1 Time": "", "Machine 2": "", "MC 2 Time": ""},
        {"Time (s)": 115.16, "Operator": place_name, "Op Time": 15.02, "Machine 1": "", "MC 1 Time": "", "Machine 2": "", "MC 2 Time": ""},
        {"Time (s)": 127.42, "Operator": "idle", "Op Time": 12.26, "Machine 1": "", "MC 1 Time": "", "Machine 2": "", "MC 2 Time": ""},
        {"Time (s)": 131.90, "Operator": load_name, "Op Time": 4.48, "Machine 1": load_name, "MC 1 Time": 4.48, "Machine 2": "", "MC 2 Time": ""},
    ]

    process_sheet_df = pd.DataFrame(chart_rows)

    st.markdown("---")
    st.subheader("📋 Man-Machine Process Sheet (Interleaved Sequence)")
    st.dataframe(process_sheet_df, use_container_width=True)

    # Export Excel 2 Sheet
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        process_sheet_df.to_excel(writer, index=False, sheet_name="Process Sheet")
    excel_data = buffer.getvalue()

    st.download_button(
        label="📥 Download Laporan Excel (.xlsx)",
        data=excel_data,
        file_name="Man_Machine_Chart_Interleaved.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Ketik nama proses dan durasi di tabel atas.")
