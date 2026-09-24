import streamlit as st
import pandas as pd

# ==========================================
# FUNGSI MEMBUAT TABEL SUMMARY COMPACT & DYNAMIC
# ==========================================
def generate_summary_table(df_input, n_mc):
    # Ambil durasi elemen proses dari input
    place_row = df_input[df_input['Aktor'].isin(['Man', 'Both']) & df_input['Proses'].str.contains('Placing|Loading|Place', case=False, na=False)]
    press_row = df_input[df_input['Aktor'] == 'Machine']
    take_row = df_input[df_input['Aktor'].isin(['Man', 'Both']) & df_input['Proses'].str.contains('Take|Unloading|Unload', case=False, na=False)]
    
    place_t = place_row['Cycle Time (s)'].values[0] if len(place_row) > 0 else 43.33
    press_t = press_row['Cycle Time (s)'].values[0] if len(press_row) > 0 else 160.0
    take_t = take_row['Cycle Time (s)'].values[0] if len(take_row) > 0 else 9.0

    # Perhitungan Per Mesin (1 Siklus)
    mc_working_time = place_t + press_t + take_t  # Mesin bekerja terus selama siklus (Placing + Hot Press + Take)
    mc_idle_time = 0.0                             # Mesin tidak idle karena operator melayani tepat waktu
    mc_total_cycle = mc_working_time + mc_idle_time
    mc_utilization = 100.0

    # Perhitungan Operator (Man Power)
    op_working_time = n_mc * (place_t + take_t)
    # Total cycle time acuan adalah waktu siklus terbesar (mesin)
    total_cycle = max(mc_total_cycle, op_working_time)
    op_idle_time = max(0.0, total_cycle - op_working_time)
    op_utilization = (op_working_time / total_cycle) * 100 if total_cycle > 0 else 0.0

    # Konstruksi Struktur Baris Matriks
    summary_dict = {
        "Summary": [
            "Working time (s)",
            "Idle time (s)",
            "Total cycle time (s)",
            "Utilization (%)"
        ],
        "Man Power": [
            f"{op_working_time:.2f}",
            f"{op_idle_time:.2f}",
            f"{total_cycle:.2f}",
            f"{op_utilization:.0f}%"
        ]
    }

    # Tambahkan kolom secara dinamis berdasarkan jumlah mesin (MC 1, MC 2, dst.)
    for i in range(1, n_mc + 1):
        summary_dict[f"MC {i}"] = [
            f"{mc_working_time:.2f}",
            f"{mc_idle_time:.2f}",
            f"{total_cycle:.2f}",
            f"{mc_utilization:.0f}%"
        ]

    return pd.DataFrame(summary_dict)


# ==========================================
# PENAMPILAN DI STREAMLIT
# ==========================================
# Di bagian bawah setelah tabel utama MMC di-generate:

st.markdown("---")
st.subheader("📊 Summary Performance Matrix (1 Loop Steady State)")

# Panggil fungsi generator summary
summary_df = generate_summary_table(edited_df, num_machines)

# Tampilkan dengan st.dataframe agar tampilan rapi, bersih, dan gampang dibaca
st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True
)
