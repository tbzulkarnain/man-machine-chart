import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(page_title="Multi-Machine Process Sheet Analyzer", layout="wide")

st.title("⚙️ Multi-Machine Process Sheet Analyzer")
st.caption("Aplikasi Industrial Engineering untuk Multi-Machine Handling & Export Excel Dinamis")

st.markdown("""
**Petunjuk Input:**
1. Atur **Jumlah Mesin** yang dipegang oleh 1 operator di sidebar atau input opsi.
2. Isi tabel urutan elemen kerja untuk 1 siklus produk.
3. Tabel Process Sheet & Export Excel akan otomatis me-layout kolom sesuai jumlah mesin yang kamu pilih!
""")

# --- CONFIGURASI JUMLAH MESIN ---
st.sidebar.header("⚙️ Konfigurasi Multi-Machine")
num_machines = st.sidebar.number_input("Jumlah Mesin (Manning Ratio)", min_value=1, max_value=10, value=3, step=1)
travel_time = st.sidebar.number_input("Waktu Pindah Antar Mesin (detik)", min_value=0.0, value=2.0, step=0.5)

# --- DEFAULT DATA ---
default_data = [
    {"Process": "Loading Material", "Duration": 15.0, "Actor": "Both"},
    {"Process": "Running Auto Process", "Duration": 60.0, "Actor": "Machine"},
    {"Process": "Prepare Next Lot", "Duration": 10.0, "Actor": "Man"},
    {"Process": "Unloading Material", "Duration": 10.0, "Actor": "Both"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

# --- TABEL INPUT DATA ---
st.subheader("📝 Element Process (1 Siklus Produk)")
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
    # --- LOGIKA MULTI-MACHINE PROCESS SHEET GENERATOR ---
    excel_rows = []
    current_time = 0.0

    # Menghitung durasi murni
    total_l = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Both"])
    total_m = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Machine"])
    total_man = sum([r["Duration"] for r in valid_rows if r["Actor"] == "Man"])

    # Generasi baris multi-mesin
    # Kita mensimulasikan alur sekuensial di mana operator menangani Mesin 1, pindah ke Mesin 2, dst.
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
            
            # Populate kolom tiap-tiap mesin
            for k in range(1, num_machines + 1):
                if k == m_idx:
                    if act in ["Both", "Machine"]:
                        row_dict[f"Process MC {k}"] = proc
                    else:
                        row_dict[f"Process MC {k}"] = f"idle (Man doing {proc})"
                else:
                    row_dict[f"Process MC {k}"] = "running / waiting operator"
                
                row_dict[f"MC {k} Time (s)"] = round(dur, 2)
                
            excel_rows.append(row_dict)
            
        # Tambahkan travel time jika pindah ke mesin berikutnya
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
    
    # 1. SUMMARY METRICS
    total_cycle_time = current_time
    man_active_time = (total_l * num_machines) + (total_man * num_machines) + (travel_time * (num_machines - 1))
    man_utilization = (man_active_time / total_cycle_time * 100) if total_cycle_time > 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Multi-Machine Cycle Time", f"{total_cycle_time:.2f} detik")
    c2.metric("Jumlah Mesin Terpasang", f"{num_machines} Mesin")
    c3.metric("Utilisasi Operator", f"{man_utilization:.1f}%")

    st.markdown("---")

    # 2. TABEL MULTI-MACHINE PROCESS SHEET
    st.subheader(f"📋 Process Sheet ({num_machines} Mesin Handling)")
    st.dataframe(sheet_df, use_container_width=True)

    # 3. EXPORT TO EXCEL
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        sheet_df.to_excel(writer, index=False, sheet_name=f"Process Sheet {num_machines} MC")
    excel_data = buffer.getvalue()

    st.download_button(
        label=f"📥 Download Process Sheet ({num_machines} Mesin) .xlsx",
        data=excel_data,
        file_name=f"Multi_Machine_Process_Sheet_{num_machines}MC.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Ketik nama proses dan durasi di tabel atas untuk membuat Multi-Machine Process Sheet.")
