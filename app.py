import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(page_title="Dynamic Multi-Machine Process Sheet Analyzer", layout="wide")

st.title("⚙️ Dynamic Multi-Machine Process Sheet Analyzer")
st.caption("Aplikasi Industrial Engineering untuk Kalkulasi Jumlah Mesin Otomatis & Export Excel Dinamis")

st.markdown("""
**Petunjuk Input:**
1. Isi daftar elemen proses kerja untuk **1 produk / 1 mesin**.
2. Masukkan estimasi waktu jalan/pindah (*Travel Time*) antar mesin jika ada.
3. Aplikasi akan **menghitung jumlah mesin ideal ($N$) secara otomatis**, lalu membuatkan tabel Process Sheet & file Excel sesuai jumlah mesin tersebut!
""")

# --- INPUT TRAVEL TIME ---
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=2.0, 
    step=0.5,
    help="Estimasi waktu operator berjalan dari 1 mesin ke mesin berikutnya"
)

# --- DEFAULT DATA (ELEMEN PROSES 1 MESIN) ---
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
    total_man = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Man"])

    # Rumus Manning Ratio: N = (l + m) / (l + w)
    denom = total_l + travel_time
    if denom > 0:
        n_raw = (total_l + total_m) / denom
        num_machines = max(1, math.floor(n_raw)) # Jumlah mesin bulat ideal (pembulatan ke bawah agar operator zero idle)
    else:
        n_raw = 1.0
        num_machines = 1

    st.markdown("---")
    
    # --- 2. SUMMARY METRICS ---
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Waktu Servis (l + w)", f"{denom:.2f} s")
    c2.metric("Waktu Running Mesin (m)", f"{total_m:.2f} s")
    c3.metric("Rasio Teoritis (N)", f"{n_raw:.2f} MC")
    c4.metric("🎯 Jumlah Mesin Ideal", f"{num_machines} Mesin", delta="Otomatis terhitung", delta_color="normal")

    # --- 3. LOGIKA GENERATOR PROCESS SHEET DENGAN N MESIN ---
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
            
            # Dinamis membentuk kolom untuk MC 1 sampai MC N
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
            
        # Tambahkan travel time antar mesin
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

    st.markdown("---")

    # --- 4. TAMPILAN TABEL DINAMIS & EXPORT EXCEL ---
    st.subheader(f"📋 Multi-Machine Process Sheet ({num_machines} Mesin Hasil Hitungan)")
    st.dataframe(sheet_df, use_container_width=True)

    # Export File Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sheet_df.to_excel(writer, index=False, sheet_name=f"Process Sheet {num_machines} MC")
    excel_data = buffer.getvalue()

    st.download_button(
        label=f"📥 Download Process Sheet ({num_machines} Mesin) .xlsx",
        data=excel_data,
        file_name=f"Man_Machine_Sheet_{num_machines}MC.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Ketik nama proses dan durasi di tabel atas untuk menghitung otomatis jumlah mesin & Process Sheet.")
