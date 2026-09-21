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
# 1. PARAMETER GLOBAL
# =============================================================================
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=0.0, 
    step=0.5,
    help="Waktu yang dibutuhkan operator untuk berpindah antar mesin."
)

# =============================================================================
# 2. TABEL ELEMEN KERJA STANDARD
# =============================================================================
default_data = [
    {"Seq": 1, "Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Seq": 2, "Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Seq": 3, "Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
    {"Seq": 4, "Process": "take result", "Duration": 2.47, "Actor": "Man"},
]

st.subheader("📝 Input Elemen Proses Standard (1 Siklus Master)")
st.caption("Kategori Aktor:\n• **Man**: Pekerjaan internal operator (mesin tidak terikat)\n• **Both**: Pekerjaan bersama operator & mesin (loading/unloading)\n• **Machine**: Mesin berjalan otomatis (St Process)")

edited_df = st.data_editor(
    pd.DataFrame(default_data),
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

valid_df = edited_df[
    (edited_df["Process"].astype(str).str.strip() != "") & 
    (edited_df["Duration"] > 0)
].sort_values(by="Seq")

valid_rows = valid_df.to_dict("records")

if valid_rows:
    man_work_per_mc = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Man", "Both"])
    mc_cycle_time = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Both", "Machine"])

    if man_work_per_mc > 0 and mc_cycle_time > 0:
        n_ideal_raw = mc_cycle_time / (man_work_per_mc + travel_time)
        n_recommended = max(1, math.floor(n_ideal_raw))

        st.markdown("---")
        col_rec1, col_rec2 = st.columns([1, 2])
        with col_rec1:
            st.metric(
                label="Rekomendasi Mesin Ideal (N)", 
                value=f"{n_recommended} Mesin",
                help=f"Perhitungan matematis: {n_ideal_raw:.2f} mesin"
            )
        
        with col_rec2:
            num_machines = st.number_input(
                "Jumlah Mesin yang Dioperasikan:",
                min_value=1, max_value=10, value=int(n_recommended), step=1
            )

        # ---------------------------------------------------------------------
        # SUMMARY ANALYSIS
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
        # 3. ENGINE SIMULASI TIME-BLOCK ACCURATE LOGIC
        # =====================================================================
        # Membangun timeline per aksi operator dan dampaknya ke status mesin
        timeline_events = []
        
        # Ekstrak elemen
        st_elem = next((r for r in valid_rows if r["Actor"] == "Machine"), None)
        st_duration = st_elem["Duration"] if st_elem else 0.0
        st_name = st_elem["Process"] if st_elem else "St Process"

        # Simpan state waktu selesai mesin
        mc_finish_at = {m: 0.0 for m in range(1, num_machines + 1)}
        current_time = 0.0

        # Kita jalankan 1 siklus lengkap stabil
        for m in range(1, num_machines + 1):
            for elem in valid_rows:
                act_type = elem["Actor"]
                proc_name = elem["Process"]
                dur = elem["Duration"]

                if act_type == "Man":
                    # Operator bekerja sendiri
                    start_t = current_time
                    end_t = start_t + dur
                    current_time = end_t
                    timeline_events.append({
                        "start": start_t, "end": end_t, "dur": dur,
                        "op_activity": f"{proc_name} (MC {m})",
                        "active_mc": m, "type": "MAN_ONLY"
                    })

                elif act_type == "Both":
                    # Cek apakah mesin m masih berproses dari siklus sebelumnya
                    if current_time < mc_finish_at[m]:
                        wait_dur = mc_finish_at[m] - current_time
                        start_t = current_time
                        end_t = current_time + wait_dur
                        current_time = end_t
                        timeline_events.append({
                            "start": start_t, "end": end_t, "dur": wait_dur,
                            "op_activity": f"Waiting MC {m}",
                            "active_mc": m, "type": "WAIT"
                        })

                    # Eksekusi kerja bersama
                    start_t = current_time
                    end_t = start_t + dur
                    current_time = end_t
                    
                    # Trigger mesin running otomatis
                    mc_finish_at[m] = end_t + st_duration
                    
                    timeline_events.append({
                        "start": start_t, "end": end_t, "dur": dur,
                        "op_activity": f"{proc_name} MC {m}",
                        "active_mc": m, "type": "BOTH"
                    })

            # Travel time ke mesin berikutnya
            if travel_time > 0 and m < num_machines:
                start_t = current_time
                end_t = start_t + travel_time
                current_time = end_t
                timeline_events.append({
                    "start": start_t, "end": end_t, "dur": travel_time,
                    "op_activity": "Travel to next MC",
                    "active_mc": None, "type": "TRAVEL"
                })

        # =====================================================================
        # 4. GENERASI TABEL PROCESS SHEET DENGAN KOLOM TERATUR
        # =====================================================================
        table_rows = []
        for ev in timeline_events:
            start_t = round(ev["start"], 2)
            end_t = round(ev["end"], 2)
            dur = round(ev["dur"], 2)
            act_mc = ev["active_mc"]
            ev_type = ev["type"]

            # Baris data terstruktur
            row = {
                "Time (s)": end_t,
                "Operator Activity": ev["op_activity"],
                "Op Time (s)": dur if ev_type in ["MAN_ONLY", "BOTH"] else 0.0
            }

            for m in range(1, num_machines + 1):
                if m == act_mc and ev_type == "BOTH":
                    row[f"Machine {m} Status"] = ev["op_activity"]
                    row[f"MC {m} Time (s)"] = dur
                elif start_t < mc_finish_at[m] and round(mc_finish_at[m] - start_t, 2) > 0:
                    row[f"Machine {m} Status"] = st_name
                    row[f"MC {m} Time (s)"] = dur
                else:
                    row[f"Machine {m} Status"] = "Idle / Waiting"
                    row[f"MC {m} Time (s)"] = 0.0

            table_rows.append(row)

        process_sheet_df = pd.DataFrame(table_rows)

        st.markdown("---")
        st.subheader(f"📋 Generated Man-Machine Process Sheet ({num_machines} Mesin)")
        st.dataframe(process_sheet_df, use_container_width=True)

        # =====================================================================
        # 5. EXPORT TO EXCEL
        # =====================================================================
        def build_excel_file():
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Process Sheet"
            ws.views.sheetView[0].showGridLines = True

            header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
            white_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            thin_border = Border(
                left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
                top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9')
            )

            headers = list(process_sheet_df.columns)
            ws.append(headers)

            for col_num in range(1, len(headers) + 1):
                cell = ws.cell(row=1, column=col_num)
                cell.fill = header_fill
                cell.font = white_font
                cell.alignment = Alignment(horizontal="center", vertical="center")

            for r_data in process_sheet_df.itertuples(index=False):
                ws.append(list(r_data))

            for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                for cell in row:
                    cell.border = thin_border
                    if isinstance(cell.value, (int, float)):
                        cell.alignment = Alignment(horizontal="right")
                    else:
                        cell.alignment = Alignment(horizontal="left")

            for col in ws.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = get_column_letter(col[0].column)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        st.download_button(
            label="📥 Download Laporan Excel (.xlsx)",
            data=build_excel_file(),
            file_name=f"Process_Sheet_{num_machines}_Machine.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
