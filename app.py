def generate_summary_table(df_input, n_mc):
    # 1. Ambil durasi elemen proses dari tabel input
    place_row = df_input[df_input['Aktor'].isin(['Man', 'Both']) & df_input['Proses'].str.contains('Placing|Loading|Place', case=False, na=False)]
    press_row = df_input[df_input['Aktor'] == 'Machine']
    take_row = df_input[df_input['Aktor'].isin(['Man', 'Both']) & df_input['Proses'].str.contains('Take|Unloading|Unload', case=False, na=False)]
    
    place_t = place_row['Cycle Time (s)'].values[0] if len(place_row) > 0 else 43.33
    press_t = press_row['Cycle Time (s)'].values[0] if len(press_row) > 0 else 160.0
    take_t = take_row['Cycle Time (s)'].values[0] if len(take_row) > 0 else 9.0

    # 2. Kalkulasi Waktu Kerja Murni (Pure Working Time)
    mc_pure_work = place_t + press_t + take_t   # 212.33s per mesin
    op_pure_work = n_mc * (place_t + take_t)     # Total waktu operator melayani N mesin

    # 3. Tentukan Waktu Siklus Sistem (Total Cycle Time)
    # Diambil dari mana yang lebih lama: Waktu Siklus Mesin vs Waktu Siklus Operator
    total_cycle = max(mc_pure_work, op_pure_work)

    # 4. Hitung Idle Time & Utilization yang Sebenarnya
    # Operator
    op_idle_time = max(0.0, total_cycle - op_pure_work)
    op_utilization = (op_pure_work / total_cycle) * 100 if total_cycle > 0 else 0.0

    # Mesin
    mc_idle_time = max(0.0, total_cycle - mc_pure_work)
    mc_utilization = (mc_pure_work / total_cycle) * 100 if total_cycle > 0 else 0.0

    # 5. Susun Matriks Summary
    summary_dict = {
        "Summary": [
            "Working time",
            "Idle time",
            "Total cycle time",
            "Utilization in percent"
        ],
        "Man Power": [
            f"{op_pure_work:.2f}",
            f"{op_idle_time:.2f}",
            f"{total_cycle:.2f}",
            f"{op_utilization:.0f}%"
        ]
    }

    # Isi nilai untuk tiap mesin (MC 1 s/d MC N)
    for i in range(1, n_mc + 1):
        summary_dict[f"MC {i}"] = [
            f"{mc_pure_work:.2f}",
            f"{mc_idle_time:.2f}",
            f"{total_cycle:.2f}",
            f"{mc_utilization:.0f}%"
        ]

    return pd.DataFrame(summary_dict)
