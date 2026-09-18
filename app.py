import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(page_title="Multi-Machine Process Sheet Analyzer", layout="wide")

st.title("⚙️ Multi-Machine Process Sheet & Summary Analyzer")
st.caption("Aplikasi Dynamic Industrial Engineering Man-Machine Chart (Fleksibel & Otomatis)")

# --- INPUT PARAMETER ---
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=0.0, 
    step=0.5,
    help="Estimasi waktu operator berjalan dari 1 mesin ke mesin berikutnya"
)

# --- DEFAULT DATA ---
default_data = [
    {"Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
    {"Process": "TAKE RESULT", "Duration": 2.47, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

# --- TABEL INPUT DATA ELEMEN PROSES ---
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
    # --- 1. HITUNG ELEMEN UTAMA DARI TABEL INPUT ---
    # Man Work (Man only & Both)
    man_work = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Man", "Both"])
    
    # Machine Automatic Work (Machine only)
    machine_auto = sum(r["Duration"] for r in valid_rows if r["Actor"] == "Machine")
    
    # Total Machine Cycle Time (Both + Machine)
    machine_cycle = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Both", "Machine"])

    if man_work > 0 and machine_cycle > 0:
        # --- 2. PERHITUNGAN N MESIN IDEAL (MANNING RATIO) ---
        # Rumus N = (Waktu Mesin Auto + Waktu Kerja Man pada Mesin) / (Waktu Kerja Man + Travel Time)
        n_ideal_raw = (machine_cycle) / (man_work + travel_time)
        n_recommended = max(1, math.floor(n_ideal_raw))

        st.markdown("---")
        col_rec1, col_rec2 = st.columns([1, 2])
        with col_rec1:
            st.metric("Rekomendasi Mesin (Ideal)", f"{n_recommended} Mesin", help=f"Hasil kalkulasi N raw = {n_ideal_raw:.2f}")
        
        with col_rec2:
            # Pilihan Pengguna Mau Pegang Berapa Mesin
            num_machines = st.number_input(
                "Jumlah Mesin yang Ditangani Operator (Bisa Diubah Manual):",
                min_value=1,
                max_value=10,
                value=int(n_recommended),
                step=1,
                help="Kamu bisa menentukan berapa banyak mesin yang dioperasikan oleh 1 operator."
            )

        # --- 3. KALKULASI SUMMARY DENGAN N MESIN PILIHAN ---
        # System Cycle Time ditentukan oleh bottlenecks (apakah Man terbatas atau Machine terbatas)
        system_cycle_time = max(machine_cycle, (man_work + travel_time) * num_machines)
        
        # Total waktu kerja Man & Idle Man per siklus sistem
        total_man_work = man_work * num_machines
        man_idle = max(0.0, system_cycle_time - total_man_work - (travel_time * num_machines))
        man_util = (total_man_work / system_cycle_time) * 100

        # Summary Table Data
        summary_rows = []
        summary_rows.append({
            "Resource": "Operator",
            "Working time (s)": round(total_man_work, 2),
            "Idle time (s)": round(man_idle, 2),
            "Total cycle time (s)": round(system_cycle_time, 2),
            "Utilization (%)": f"{round(man_util, 1)}%"
        })

        for i in range(1, num_machines + 1):
            mc_work = machine_cycle
            mc_idle = max(0.0, system_cycle_time - mc_work)
            mc_util = (mc_work / system_cycle_time) * 100
            summary_rows.append({
                "Resource": f"Machine {i}",
                "Working time (s)": round(mc_work, 2),
                "Idle time (s)": round(mc_idle, 2),
                "Total cycle time (s)": round(system_cycle_time, 2),
                "Utilization (%)": f"{round(mc_util, 1)}%"
            })

        summary_df = pd.DataFrame(summary_rows)

        st.subheader("📊 Summary Performance")
        st.dataframe(summary_df, use_container_width=True)

        # --- 4. ALGORITMA SCHEDULING TIMELINE (DINAMIS UNTUK SEGALA INPUT DATA & N MESIN) ---
        # Kita memetakan event-event utama secara kronologis berdasarkan waktu
        timeline_events = []
        
        # Identifikasi elemen internal man (preparation) vs external man (load/unload/take)
        man_prep_elements = [r for r in valid_rows if r["Actor"] == "Man"]
        man_mc_elements = [r for r in valid_rows if r["Actor"] in ["Both", "Machine"]]

        # Kita buat simulasi waktu berjalan (Simulation Engine)
        current_time = 0.0
        # Setiap mesin memiliki status waktu selesai prosesnya
        mc_available_time = {i: 0.0 for i in range(1, num_machines + 1)}
        mc_status = {i: "Waiting" for i in range(1, num_machines + 1)}

        # Generasi Process Sheet untuk 1.5 - 2 Siklus agar terlihat kontinuitasnya
        records = []
        
        # Tentukan urutan pekerjaan operator di mesin 1, 2, ..., N
        cycle_steps = []
        for mc_id in range(1, num_machines + 1):
            # Prep work (misal: placing component to pallet)
            for prep in man_prep_elements:
                cycle_steps.append({"type": "prep", "mc_id": mc_id, "name": prep["Process"], "dur": prep["Duration"]})
            # Load / Unload work
            for mc_elem in [r for r in valid_rows if r["Actor"] == "Both"]:
                cycle_steps.append({"type": "load", "mc_id": mc_id, "name": mc_elem["Process"], "dur": mc_elem["Duration"]})

        # Jalankan siklus simulasi 2x loop untuk menggambarkan stabilitas rantai proses
        sim_time = 0.0
        mc_timeline = {i: [] for i in range(1, num_machines + 1)}
        
        for loop in range(2):
            for step in cycle_steps:
                mc_id = step["mc_id"]
                dur = step["dur"]
                act_name = step["name"]
                
                start_t = sim_time
                end_t = sim_time + dur
                
                # Update status operator & mesin target
                row = {
                    "Accumulated Time (s)": round(end_t, 2),
                    "Operator Activity": f"[{f'MC {mc_id}'}] {act_name}",
                    "Op Duration (s)": round(dur, 2)
                }
                
                for m in range(1, num_machines + 1):
                    if m == mc_id and step["type"] == "load":
                        row[f"Machine {m}"] = act_name
                    elif end_t <= mc_available_time[m]:
                        row[f"Machine {m}"] = "Running / Process"
                    else:
                        row[f"Machine {m}"] = "Idle / Waiting"

                # Jika langkah ini menyalakan mesin
                if step["type"] == "load":
                    mc_available_time[mc_id] = end_t + machine_auto

                records.append(row)
                sim_time = end_t
                
                if travel_time > 0 and step["type"] == "load":
                    sim_time += travel_time

        process_sheet_df = pd.DataFrame(records)

        st.markdown("---")
        st.subheader("📋 Dynamic Man-Machine Process Sheet")
        st.dataframe(process_sheet_df, use_container_width=True)

        # Download Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            summary_df.to_excel(writer, index=False, sheet_name="Summary")
            process_sheet_df.to_excel(writer, index=False, sheet_name="Process Sheet")
        
        st.download_button(
            label="📥 Download Laporan Excel (.xlsx)",
            data=buffer.getvalue(),
            file_name="Man_Machine_Dynamic_Analysis.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.warning("Mohon pastikan durasi elemen proses Man dan Machine diisi dengan angka > 0.")
else:
    st.info("Masukkan elemen proses pada tabel di atas.")
