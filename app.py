import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Man-Machine Chart Builder", layout="wide")

st.title("⚙️ Man-Machine Process Sheet & Costing")
st.caption("Aplikasi pembuatan Multi-Man-Machine Process Sheet & Export Excel")

st.markdown("""
**Petunjuk:** 
1. Isi tabel proses kerja di bawah ini.
2. Klik tombol **Download Process Sheet (.xlsx)** untuk mengunduh hasilnya dalam format tabel Excel rapi.
""")

# --- DEFAULT DATA ---
default_data = [
    {"Process": "Loading Component Mold 1#", "Duration": 29.86, "Actor": "Both"},
    {"Process": "Close Mold 1# & Loading Hot MC", "Duration": 12.19, "Actor": "Machine"},
    {"Process": "Heat Pressing Mold 1#", "Duration": 97.64, "Actor": "Machine"},
    {"Process": "Unloading & Move to Cold MC", "Duration": 6.99, "Actor": "Both"},
    {"Process": "Cold Pressing Mold 1#", "Duration": 59.59, "Actor": "Machine"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
    {"Process": "", "Duration": 0.0, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

# --- TABEL INTERAKTIF ---
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

# --- PROCESSING DATA FOR MULTI-COLUMN EXCEL ---
valid_rows = edited_df[
    (edited_df["Process"].str.strip() != "") & 
    (edited_df["Duration"] > 0)
].to_dict("records")

if valid_rows:
    excel_rows = []
    current_time = 0.0

    for item in valid_rows:
        proc = item["Process"]
        dur = item["Duration"]
        act = item["Actor"]
        
        current_time += dur
        
        # Logika pembagian kolom Man & Machine
        if act == "Both":
            man_proc = proc
            mc_proc = proc
        elif act == "Man":
            man_proc = proc
            mc_proc = "idle / waiting"
        elif act == "Machine":
            man_proc = "idle / waiting"
            mc_proc = proc

        excel_rows.append({
            "Time (Accumulated)": round(current_time, 2),
            "Operator Process": man_proc,
            "Operator Time (s)": dur,
            "Machine Process": mc_proc,
            "Machine Time (s)": dur
        })

    result_df = pd.DataFrame(excel_rows)

    st.markdown("---")
    st.subheader("📋 Hasil Process Sheet")
    st.dataframe(result_df, use_container_width=True)

    # --- FUNCTION EXPORT EXCEL ---
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        result_df.to_excel(writer, index=False, sheet_name="Man-Machine Sheet")
    
    excel_data = buffer.getvalue()

    # --- TOMBOL DOWNLOAD ---
    st.download_button(
        label="📥 Download Process Sheet (.xlsx)",
        data=excel_data,
        file_name="Man_Machine_Process_Sheet.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

else:
    st.info("Ketik nama proses dan durasi di tabel atas untuk membuat Process Sheet.")
