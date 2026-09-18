import streamlit as st
import pandas as pd
import math
import io
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

st.set_page_config(page_title="Multi-Machine Process Sheet Analyzer", layout="wide")

st.title("⚙️ Multi-Machine Process Sheet & Summary Analyzer")
st.caption("Aplikasi IE - Visualisasi Man-Machine Chart Interleaved & Summary Dinamis")

# --- INPUT PARAMETER ---
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input(
    "Waktu Pindah Antar Mesin / Travel Time (detik)", 
    min_value=0.0, 
    value=0.0, 
    step=0.5
)

# --- DEFAULT DATA ---
default_data = [
    {"Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
    {"Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Process": "take result", "Duration": 2.47, "Actor": "Man"},
]

df_default = pd.DataFrame(default_data)

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
    # 1. HITUNG ELEMEN UTAMA DARI INPUT DATA
    man_work_per_mc = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Man", "Both"])
    mc_cycle_time = sum(r["Duration"] for r in valid_rows if r["Actor"] in ["Both", "Machine"])

    if man_work_per_mc > 0 and mc_cycle_time > 0:
        # Hitung N Ideal (Manning Ratio)
        n_ideal_raw = mc_cycle_time / (man_work_per_mc + travel_time)
        n_recommended = max(1, math.floor(n_ideal_raw))

        st.markdown("---")
        col_rec1, col_rec2 = st.columns([1, 2])
        with col_rec1:
            st.metric("Rekomendasi Mesin Ideal (N)", f"{n_recommended} Mesin", help=f"Hasil kalkulasi N raw = {n_ideal_raw:.2f}")
        
        with col_rec2:
            num_machines = st.number_input(
                "Jumlah Mesin yang Dioperasikan (Bisa Diubah Manual):",
                min_value=1,
                max_value=10,
                value=int(n_recommended),
                step=1
            )

        # 2. KALKULASI SUMMARY DINAMIS BERDASARKAN N MESIN
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
            
            summary_dict[f"Machine {m}"] = [
                f"{mc_work:.2f}",
                f"{mc_idle:.2f}",
                f"{system_cycle_time:.2f}",
                f"{round(mc_util)}%"
            ]

        summary_df = pd.DataFrame(summary_dict)

        # TAMPILAN VISUAL SUMMARY LANGSUNG DI WEB
        st.subheader(f"📊 Summary ({num_machines} Mesin)")
        st.table(summary_df)

        # 3. GENERATOR EVENT PROCESS SHEET DINAMIS (FULL SIMULASI)
        chart_rows = []
        op_tasks = [r for r in valid_rows if r["Actor"] in ["Man", "Both"]]

        curr_time = 0.0
        mc_finish_time = {m: 0.0 for m in range(1, num_machines + 1)}

        # Simulasi 2 Siklus Kerja
        for cycle in range(2):
            for m in range(1, num_machines + 1):
                # A. Cek Waktu Tunggu Operator (Idle)
                if curr_time < mc_finish_time[m]:
                    idle_dur = round(mc_finish_time[m] - curr_time, 2)
                    if idle_dur > 0:
                        curr_time = round(curr_time + idle_dur, 2)
                        row_idle = {
                            "Time (s)": curr_time,
                            "Operator": "idle",
                            "Op Time": idle_dur
                        }
                        for k in range(1, num_machines + 1):
                            row_idle[f"Machine {k}"] = ""
                            row_idle[f"MC {k} Time"] = ""
                        chart_rows.append(row_idle)

                # B. Eksekusi Aktivitas Operator di Mesin m
                for task in op_tasks:
                    curr_time = round(curr_time + task["Duration"], 2)
                    row_task = {
                        "Time (s)": curr_time,
                        "Operator": task["Process"],
                        "Op Time": task["Duration"]
                    }
                    
                    for k in range(1, num_machines + 1):
                        if k == m:
                            row_task[f"Machine {k}"] = task["Process"] if task["Actor"] == "Both" else "St Process"
                            row_task[f"MC {k} Time"] = task["Duration"]
                        else:
                            row_task[f"Machine {k}"] = ""
                            row_task[f"MC {k} Time"] = ""
                    
                    chart_rows.append(row_task)
                
                # Update waktu selesai mesin m secara realistis
                mc_finish_time[m] = round(curr_time + mc_cycle_time - man_work_per_mc, 2)

        process_sheet_df = pd.DataFrame(chart_rows)

        # TAMPILAN VISUAL PROCESS SHEET LANGSUNG DI WEB
        st.markdown("---")
        st.subheader(f"📋 Man-Machine Process Sheet ({num_machines} Mesin)")
        st.dataframe(process_sheet_df, use_container_width=True)

        # 4. EXPORT FILE EXCEL DENGAN OPENPYXL
        def build_excel_file():
            wb = openpyxl.Workbook()
            
            # Sheet Process Sheet
            ws_sheet = wb.active
            ws_sheet.title = "Process Sheet"
            ws_sheet.views.sheetView[0].showGridLines = True

            header_fill = PatternFill(start_color="9BC2E6", end_color="9BC2E6", fill_type="solid")
            bold_font = Font(name="Calibri", size=11, bold=True)
            thin_border = Border(
                left=Side(style='thin', color='000000'), right=Side(style='thin', color='000000'),
                top=Side(style='thin', color='000000'), bottom=Side(style='thin', color='000000')
            )

            # Headers
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

            # Rows
            for row_data in chart_rows:
                r_vals = [row_data.get("Time (s)"), row_data.get("Operator"), row_data.get("Op Time")]
                for m in range(1, num_machines + 1):
                    r_vals.extend([row_data.get(f"Machine {m}", ""), row_data.get(f"MC {m} Time", "")])
                ws_sheet.append(r_vals)

            # Sheet Summary
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
            file_name=f"Man_Machine_Analysis_{num_machines}MC.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
