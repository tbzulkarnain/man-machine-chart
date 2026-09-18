import streamlit as st
import pandas as pd
import math
import io
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

st.set_page_config(page_title="AI-Simulated Man-Machine Analyzer", layout="wide")

st.title("⚙️ AI-Simulated Multi-Machine Process Analyzer")
st.caption("Engine Simulasi Event-Based: Menggambarkan Kondisi Nyata Operator & Mesin Tanpa Overlap")

# --- PARAMETER LAPANGAN ---
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=0.0, 
    step=0.5
)

default_data = [
    {"Seq": 1, "Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Seq": 2, "Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Seq": 3, "Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
    {"Seq": 4, "Process": "take result", "Duration": 2.47, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

st.subheader("📝 Input Elemen Proses Standard (1 Siklus)")

edited_df = st.data_editor(
    df_default,
    num_rows="dynamic",
    column_config={
        "Seq": st.column_config.NumberColumn("No / Seq", width="small", default=1),
        "Process": st.column_config.TextColumn("Nama Proses / Activity", width="large"),
        "Duration": st.column_config.NumberColumn("Waktu (s)", min_value=0.0, format="%.2f", width="small"),
        "Actor": st.column_config.SelectboxColumn("Resource", options=["Man", "Machine", "Both"], width="small"),
    },
    hide_index=True,
    use_container_width=True
)

valid_df = edited_df[
    (edited_df["Process"].str.strip() != "") & 
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
            st.metric("Rekomendasi Mesin Ideal (N)", f"{n_recommended} Mesin")
        
        with col_rec2:
            num_machines = st.number_input(
                "Jumlah Mesin yang Dioperasikan:",
                min_value=1, max_value=10, value=int(n_recommended), step=1
            )

        # SUMMARY METRICS
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

        # =========================================================================
        # DISCRETE-EVENT SIMULATION ENGINE (REAL-TIME STATUS TRACKER)
        # =========================================================================
        events = []
        op_time = 0.0
        mc_finish_time = {m: 0.0 for m in range(1, num_machines + 1)}

        # Simulasi dijalankan 2 siklus
        for cycle in range(2):
            for m_idx in range(1, num_machines + 1):
                for elem in valid_rows:
                    proc = elem["Process"]
                    dur = elem["Duration"]
                    act = elem["Actor"]

                    if act == "Man":
                        # Operator Bekerja Sendiri (misal: Placing component to pallet)
                        start_t = op_time
                        end_t = start_t + dur
                        events.append({
                            "start": start_t, "end": end_t, "dur": dur,
                            "op_act": proc, "mc_target": m_idx, "mc_act": "idle"
                        })
                        op_time = end_t

                    elif act == "Both":
                        # Operator & Mesin Bekerja Bersama (misal: Loading - Unloading / Take Result)
                        # Jika mesin masih berjalan dari siklus sebelumnya, operator harus menunggu
                        if op_time < mc_finish_time[m_idx]:
                            wait_dur = mc_finish_time[m_idx] - op_time
                            events.append({
                                "start": op_time, "end": mc_finish_time[m_idx], "dur": wait_dur,
                                "op_act": "waiting", "mc_target": m_idx, "mc_act": "running"
                            })
                            op_time = mc_finish_time[m_idx]

                        start_t = op_time
                        end_t = start_t + dur
                        events.append({
                            "start": start_t, "end": end_t, "dur": dur,
                            "op_act": proc, "mc_target": m_idx, "mc_act": proc
                        })
                        op_time = end_t
                        mc_finish_time[m_idx] = end_t

                    elif act == "Machine":
                        # Mesin Bekerja Mandiri (misal: St Process)
                        start_t = op_time
                        end_t = start_t + dur
                        mc_finish_time[m_idx] = end_t
                        # Catat aktivitas mesin secara otomatis
                        events.append({
                            "start": start_t, "end": end_t, "dur": dur,
                            "op_act": "free", "mc_target": m_idx, "mc_act": proc
                        })

                # Jika ada travel time antar mesin
                if travel_time > 0:
                    start_t = op_time
                    end_t = start_t + travel_time
                    events.append({
                        "start": start_t, "end": end_t, "dur": travel_time,
                        "op_act": "traveling", "mc_target": None, "mc_act": "idle"
                    })
                    op_time = end_t

        # GENERATE TABLE BASED ON INTERVAL TIMELINE
        chart_rows = []
        for ev in events:
            # Lewati event khusus internal mesin jika waktunya sudah ter-cover oleh operator
            if ev["op_act"] == "free":
                continue

            t_stamp = round(ev["end"], 2)
            dur = round(ev["dur"], 2)

            row = {
                "Time (s)": t_stamp,
                "Operator": ev["op_act"],
                "Op Time": dur if ev["op_act"] not in ["waiting", "idle"] else 0.0
            }

            for m in range(1, num_machines + 1):
                if ev["mc_target"] == m:
                    row[f"Machine {m}"] = ev["mc_act"]
                    row[f"MC {m} Time"] = dur
                else:
                    # Cek status mesin lain pada interval waktu [ev['start'], ev['end']]
                    if ev["start"] < mc_finish_time[m]:
                        row[f"Machine {m}"] = "St Process"
                    else:
                        row[f"Machine {m}"] = "waiting"
                    row[f"MC {m} Time"] = dur

            chart_rows.append(row)

        process_sheet_df = pd.DataFrame(chart_rows)

        st.markdown("---")
        st.subheader(f"📋 AI-Simulated Man-Machine Process Sheet ({num_machines} Mesin)")
        st.dataframe(process_sheet_df, use_container_width=True)

        # EXPORT EXCEL
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
            file_name=f"AI_Simulated_MM_Analysis_{num_machines}MC.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
