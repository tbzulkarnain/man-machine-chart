import streamlit as st
import pandas as pd
import math
import io
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

st.set_page_config(page_title="Universal Multi-Machine IE Analyzer", layout="wide")

st.title("⚙️ Universal Multi-Machine Process Analyzer")
st.caption("Aplikasi IE Universal: Simulasi Linimasa Real-Time & Rekomendasi Mesin Dinamis")

# =============================================================================
# 1. PARAMETER GLOBAL (KONDISI LAPANGAN)
# =============================================================================
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=0.0, 
    step=0.5,
    help="Waktu yang dibutuhkan operator untuk berpindah dari satu mesin ke mesin berikutnya."
)

# =============================================================================
# 2. TABEL ELEMEN KERJA STANDARD (ELEMENT SEQUENCE MASTER)
# =============================================================================
default_data = [
    {"Seq": 1, "Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Seq": 2, "Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Seq": 3, "Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
    {"Seq": 4, "Process": "take result", "Duration": 2.47, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

st.subheader("📝 Input Elemen Proses Standard (1 Siklus Master)")
st.write("Masukkan daftar elemen kerja untuk **1 mesin**. Kategori Aktor:")
st.caption("• **Man**: Pekerjaan persiapan/internal operator (mesin tidak terikat)\n• **Both**: Interaksi bersama operator & mesin (loading/unloading/setup)\n• **Machine**: Otomatisasi mesin berjalan sendiri (St Process/Machining time)")

edited_df = st.data_editor(
    df_default,
    num_rows="dynamic",
    column_config={
        "Seq": st.column_config.NumberColumn("No / Seq", width="small", default=1),
        "Process": st.column_config.TextColumn("Nama Proses / Activity", width="large"),
        "Duration": st.column_config.NumberColumn("Waktu (s)", min_value=0.0, format="%.2f", width="small"),
        "Actor": st.column_config.SelectboxColumn("Aktor / Resource", options=["Man", "Both", "Machine"], width="small"),
    },
    hide_index=True,
    use_container_width=True
)

# Filter & validasi data input
valid_df = edited_df[
    (edited_df["Process"].astype(str).str.strip() != "") & 
    (edited_df["Duration"] > 0)
].sort_values(by="Seq")

valid_rows = valid_df.to_dict("records")

if valid_rows:
    # Perhitungan parameter dasar IE
    man_work_per_mc = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Man", "Both"])
    mc_cycle_time = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Both", "Machine"])

    if man_work_per_mc > 0 and mc_cycle_time > 0:
        # Rumus IE: N = MC / (Man + Travel)
        n_ideal_raw = mc_cycle_time / (man_work_per_mc + travel_time)
        n_recommended = max(1, math.floor(n_ideal_raw))

        st.markdown("---")
        col_rec1, col_rec2 = st.columns([1, 2])
        with col_rec1:
            st.metric(
                label="Rekomendasi Mesin Ideal (N)", 
                value=f"{n_recommended} Mesin",
                help=f"Hasil perhitungan matematis presisi: {n_ideal_raw:.2f} mesin"
            )
        
        with col_rec2:
            num_machines = st.number_input(
                "Jumlah Mesin yang Dioperasikan (Bisa Disesuaikan):",
                min_value=1, max_value=10, value=int(n_recommended), step=1
            )

        # ---------------------------------------------------------------------
        # SUMMARY ANALYSIS METRICS
        # ---------------------------------------------------------------------
        total_man_work = man_work_per_mc * num_machines
        system_cycle_time = max(mc_cycle_time, (man_work_per_mc + travel_time) * num_machines)
        man_idle = max(0.0, system_cycle_time - total_man_work - (travel_time * num_machines))
        man_util = (total_man_work / system_cycle_time) * 100 if system_cycle_time > 0 else 0

        summary_dict = {
            "Metric": ["Working time", "Idle time", "Total cycle time", "Utilization in percent"],
            "Operator": [f"{total_man_work:.2f}", f"{man_idle:.2f}", f"{system_cycle_time:.2f}", f"{round(man_util)}%"]
        }

        for m in range(1, num_machines + 1):
            mc_work = mc_cycle_time
            mc_idle = max(0.0, system_cycle_time - mc_work)
            mc_util = (mc_work / system_cycle_time) * 100 if system_cycle_time > 0 else 0
            summary_dict[f"Machine {m}"] = [f"{mc_work:.2f}", f"{mc_idle:.2f}", f"{system_cycle_time:.2f}", f"{round(mc_util)}%"]

        summary_df = pd.DataFrame(summary_dict)

        st.subheader(f"📊 Summary Analysis ({num_machines} Mesin)")
        st.table(summary_df)

        # =====================================================================
        # 3. ENGINE SIMULASI EVENT-BASED (LOGIKA CORE MMC UNIVERSAL)
        # =====================================================================
        # Ambil elemen 'Machine' (St Process/Machining) jika ada
        machine_elem = next((r for r in valid_rows if r["Actor"] == "Machine"), None)
        st_proc_dur = machine_elem["Duration"] if machine_elem else 0.0
        st_proc_name = machine_elem["Process"] if machine_elem else "Machine Process"

        # Elemen yang membutuhkan interaksi operator
        op_sequence = [r for r in valid_rows if r["Actor"] in ["Man", "Both"]]

        # Tracking status waktu
        op_time = 0.0
        mc_finish_time = {m: 0.0 for m in range(1, num_machines + 1)}
        events = []

        # Simulasi berjalan selama 2 siklus penuh untuk mendapatkan pola steady-state
        for cycle in range(2):
            for m_idx in range(1, num_machines + 1):
                for elem in op_sequence:
                    proc = elem["Process"]
                    dur = elem["Duration"]
                    act = elem["Actor"]

                    if act == "Man":
                        # Elemen persiapan operator (misal: Placing component)
                        start_t = op_time
                        end_t = start_t + dur
                        op_time = end_t
                        events.append({
                            "start": start_t, "end": end_t, "dur": dur,
                            "op_act": proc, "target_mc": m_idx, "mc_act": "idle"
                        })

                    elif act == "Both":
                        # Elemen interaksi (misal: Loading - Unloading)
                        # CEK: Apakah mesin target masih berproses dari siklus sebelumnya?
                        if op_time < mc_finish_time[m_idx]:
                            wait_dur = round(mc_finish_time[m_idx] - op_time, 2)
                            start_t = op_time
                            end_t = mc_finish_time[m_idx]
                            op_time = end_t
                            events.append({
                                "start": start_t, "end": end_t, "dur": wait_dur,
                                "op_act": "waiting", "target_mc": m_idx, "mc_act": "running"
                            })

                        # Eksekusi pekerjaan bersama
                        start_t = op_time
                        end_t = start_t + dur
                        op_time = end_t
                        events.append({
                            "start": start_t, "end": end_t, "dur": dur,
                            "op_act": proc, "target_mc": m_idx, "mc_act": proc
                        })

                        # TRIGGER OTOMATIS: Jika ini elemen loading/pemicu, mesin langsung RUNNING
                        if st_proc_dur > 0 and ("load" in proc.lower() or elem == op_sequence[-1]):
                            mc_finish_time[m_idx] = end_t + st_proc_dur

                # Pindah antar mesin (Travel Time)
                if travel_time > 0:
                    start_t = op_time
                    end_t = start_t + travel_time
                    op_time = end_t
                    events.append({
                        "start": start_t, "end": end_t, "dur": travel_time,
                        "op_act": "traveling", "target_mc": None, "mc_act": "idle"
                    })

        # =====================================================================
        # 4. GENERASI TABEL PROCESS SHEET PER INTERVAL
        # =====================================================================
        chart_rows = []
        for ev in events:
            start_t = ev["start"]
            end_t = ev["end"]
            dur = round(ev["dur"], 2)
            t_stamp = round(end_t, 2)

            row = {
                "Time (s)": t_stamp,
                "Operator": ev["op_act"],
                "Op Time": dur if ev["op_act"] not in ["waiting", "idle", "traveling"] else 0.0
            }

            for m in range(1, num_machines + 1):
                if ev["target_mc"] == m:
                    row[f"Machine {m}"] = ev["mc_act"]
                    row[f"MC {m} Time"] = dur
                else:
                    # Cek kondisi riil mesin lain pada interval [start_t, end_t]
                    if start_t < mc_finish_time[m]:
                        row[f"Machine {m}"] = st_proc_name
                    else:
                        row[f"Machine {m}"] = "waiting"
                    row[f"MC {m} Time"] = dur

            chart_rows.append(row)

        process_sheet_df = pd.DataFrame(chart_rows)

        st.markdown("---")
        st.subheader(f"📋 Generated Man-Machine Process Sheet ({num_machines} Mesin)")
        st.dataframe(process_sheet_df, use_container_width=True)

        # =====================================================================
        # 5. EXPORT TO EXCEL FUNCTION (.XLSX)
        # =====================================================================
        def build_excel_file():
            wb = openpyxl.Workbook()
            ws_sheet = wb.active
            ws_sheet.title = "Process Sheet"
            ws_sheet.views.sheetView[0].showGridLines = True

            header_fill = PatternFill(start_color="9BC2E6", end_color="9BC2E6", fill_type="solid")
            bold_font = Font(name="Calibri", size=11, bold=True)
            thin_border = Border(
                left=Side(style='thin', color='000000'), right=Side(style='thin', color='000000'),
                top=Side(style='thin', color='000000'), bottom=Side(style='thin', color='000000')
            )

            headers = ["Time (s)", "Operator", "Time (s)"]
            for m in range(1, num_machines + 1):
                headers.extend([f"Machine {m}", "Time (s)"])
            
            ws_sheet.append(headers)
            for c_idx, h in enumerate(headers, 1):
                cell = ws_sheet.cell(row=1, column=c_idx)
                cell.fill = header_fill
                cell.font = bold_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = thin_border

            for row_data in chart_rows:
                r_vals = [row_data.get("Time (s)"), row_data.get("Operator"), row_data.get("Op Time")]
                for m in range(1, num_machines + 1):
                    r_vals.extend([row_data.get(f"Machine {m}", ""), row_data.get(f"MC {m} Time", "")])
                ws_sheet.append(r_vals)

            ws_sum = wb.create_sheet(title="Summary")
            ws_sum.views.sheetView[0].showGridLines = True
            ws_sum.append(["Summary"])
            ws_sum.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(summary_df.columns))
            ws_sum.cell(row=1, column=1).fill = header_fill
            ws_sum.cell(row=1, column=1).font = bold_font
            ws_sum.cell(row=1, column=1).alignment = Alignment(horizontal="center")

            ws_sum.append(list(summary_df.columns))
            for r in summary_df.itertuples(index=False):
                ws_sum.append(list(r))

            for sheet in [ws_sheet, ws_sum]:
                for col in sheet.columns:
                    max_l = max(len(str(cell.value or '')) for cell in col)
                    col_letter = get_column_letter(col[0].column)
                    sheet.column_dimensions[col_letter].width = max(max_l + 3, 12)

            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        st.download_button(
            label="📥 Download Laporan Excel (.xlsx)",
            data=build_excel_file(),
            file_name=f"Universal_MM_Analysis_{num_machines}MC.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
