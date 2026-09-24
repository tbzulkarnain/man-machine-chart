import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

st.set_page_config(page_title="Discrete Time Grid MMC Generator", layout="wide")

st.title("⚙️ Man-Machine Chart (MMC) Generator - Discrete Time Grid")
st.caption("Aplikasi IE dengan Time-Slice Grid: Waktu Operator & Mesin Tidak Bertabrakan")

# =============================================================================
# 1. PARAMETER INPUT
# =============================================================================
st.sidebar.header("⚙️ Konfigurasi")
num_machines = st.sidebar.number_input("Jumlah Mesin (N):", min_value=1, max_value=5, value=2, step=1)
num_cycles = st.sidebar.slider("Jumlah Siklus Simulation:", min_value=1, max_value=5, value=2)

st.subheader("📝 Master Elemen Kerja (1 Siklus Master)")
default_data = [
    {"Seq": 1, "Process": "Placing component vamp to MC", "Duration": 80.0, "Actor": "Man"},
    {"Seq": 2, "Process": "Loading", "Duration": 6.0, "Actor": "Both"},
    {"Seq": 3, "Process": "Hot Press MC", "Duration": 60.0, "Actor": "Machine"},
    {"Seq": 4, "Process": "Unloading / Take result", "Duration": 6.0, "Actor": "Both"},
]

edited_df = st.data_editor(
    pd.DataFrame(default_data),
    num_rows="dynamic",
    column_config={
        "Seq": st.column_config.NumberColumn("No", width="small"),
        "Process": st.column_config.TextColumn("Nama Proses / Activity", width="large"),
        "Duration": st.column_config.NumberColumn("Waktu (s)", min_value=0.0, format="%.2f"),
        "Actor": st.column_config.SelectboxColumn("Aktor", options=["Man", "Both", "Machine"]),
    },
    hide_index=True,
    use_container_width=True
)

valid_rows = edited_df[(edited_df["Process"].astype(str).str.strip() != "") & (edited_df["Duration"] > 0)].sort_values(by="Seq").to_dict("records")

# =============================================================================
# 2. DISCRETE TIME GRID ENGINE
# =============================================================================
if valid_rows:
    # Memisahkan elemen
    machine_elem = next((r for r in valid_rows if r["Actor"] == "Machine"), None)
    st_dur = machine_elem["Duration"] if machine_elem else 0.0
    st_name = machine_elem["Process"] if machine_elem else "Process Machine"

    op_elems = [r for r in valid_rows if r["Actor"] in ["Man", "Both"]]

    # Struktur Lacak Event: [start_time, end_time, owner_type, owner_id, activity_name]
    raw_activities = []
    
    current_time = 0.0
    mc_free_time = {m: 0.0 for m in range(1, num_machines + 1)}

    for cyc in range(num_cycles):
        for m in range(1, num_machines + 1):
            for elem in op_elems:
                p_name = elem["Process"]
                dur = elem["Duration"]
                act = elem["Actor"]

                # Jika Operator harus nunggu Mesin m selesai
                if act == "Both" and current_time < mc_free_time[m]:
                    wait_dur = mc_free_time[m] - current_time
                    raw_activities.append({
                        "start": current_time, "end": current_time + wait_dur,
                        "owner": "Op", "id": 0, "name": "idle"
                    })
                    current_time += wait_dur

                # Aktivitas Operator
                op_name = f"{p_name} MC {m}#" if num_machines > 1 else p_name
                raw_activities.append({
                    "start": current_time, "end": current_time + dur,
                    "owner": "Op", "id": 0, "name": op_name
                })

                # Jika Loading/Both -> Mesin m juga aktif (Loading & Auto Run Machine)
                if act == "Both":
                    raw_activities.append({
                        "start": current_time, "end": current_time + dur,
                        "owner": "MC", "id": m, "name": p_name
                    })
                    
                    # Jika ini instruksi awal pengerjaan mesin (Loading), picu pengerjaan mesin
                    if "load" in p_name.lower() or "placing" in p_name.lower():
                        mc_start = current_time + dur
                        mc_end = mc_start + st_dur
                        raw_activities.append({
                            "start": mc_start, "end": mc_end,
                            "owner": "MC", "id": m, "name": st_name
                        })
                        mc_free_time[m] = mc_end

                current_time += dur

    # Ekstraksi Semua Point Waktu Unik (Grid Cut-off Points)
    time_points = set([0.0])
    for act in raw_activities:
        time_points.add(round(act["start"], 2))
        time_points.add(round(act["end"], 2))

    sorted_times = sorted(list(time_points))

    # Bentuk Interval/Slices
    grid_rows = []
    for i in range(1, len(sorted_times)):
        t_start = sorted_times[i-1]
        t_end = sorted_times[i]
        dur = round(t_end - t_start, 2)
        if dur <= 0:
            continue

        # Cari status Operator di interval [t_start, t_end]
        op_act = "idle"
        for act in raw_activities:
            if act["owner"] == "Op" and act["start"] <= t_start and act["end"] >= t_end:
                op_act = act["name"]
                break

        row_item = {
            "cum_time": t_end,
            "op_act": op_act,
            "op_dur": dur,
            "mc_data": {}
        }

        # Cari status Tiap Mesin di interval [t_start, t_end]
        for m in range(1, num_machines + 1):
            mc_act = "waiting"
            for act in raw_activities:
                if act["owner"] == "MC" and act["id"] == m and act["start"] <= t_start and act["end"] >= t_end:
                    mc_act = act["name"]
                    break
            row_item["mc_data"][m] = {"act": mc_act, "dur": dur}

        grid_rows.append(row_item)

    # Preview Streamlit
    st.markdown("---")
    st.subheader("📋 Preview Time Grid (Sejajar & Presisi)")
    
    table_preview = []
    for r in grid_rows:
        row_dict = {
            "Time (s)": r["cum_time"],
            "Operator Process": r["op_act"],
            "Time (s) ": r["op_dur"]
        }
        for m in range(1, num_machines + 1):
            row_dict[f"MC {m}"] = r["mc_data"][m]["act"]
            row_dict[f"Time (s) MC{m}"] = r["mc_data"][m]["dur"]
        table_preview.append(row_dict)

    st.dataframe(pd.DataFrame(table_preview), use_container_width=True)

    # =============================================================================
    # 3. EXPORT EXCEL GENERATOR
    # =============================================================================
    def generate_exact_excel():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "MMC Time Grid"
        ws.views.sheetView[0].showGridLines = True

        header_fill = PatternFill(start_color="9BC2E6", end_color="9BC2E6", fill_type="solid")
        idle_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        bold_font = Font(name="Calibri", size=10, bold=True)
        regular_font = Font(name="Calibri", size=10)
        thin_border = Border(
            left=Side(style='thin', color='000000'), right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'), bottom=Side(style='thin', color='000000')
        )

        headers = ["Time (s)", "Process Operator 1", "Time Second"]
        for m in range(1, num_machines + 1):
            headers.extend([f"MC {m}", "Time Second"])

        ws.append(headers)
        for col_i in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_i)
            cell.fill = header_fill
            cell.font = bold_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        for r in grid_rows:
            r_vals = [r["cum_time"], r["op_act"], r["op_dur"]]
            for m in range(1, num_machines + 1):
                r_vals.extend([r["mc_data"][m]["act"], r["mc_data"][m]["dur"]])
            ws.append(r_vals)

        # Formatting Cell & Highlight Idle/Waiting
        for row in range(2, ws.max_row + 1):
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=row, column=col)
                cell.font = regular_font
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center" if col != 2 else "left", vertical="center")
                
                if str(cell.value).lower() in ["idle", "waiting"]:
                    cell.fill = idle_fill

        # Auto Column Width
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    st.download_button(
        label="📥 Download Excel MMC Time Grid (.xlsx)",
        data=generate_exact_excel(),
        file_name="MMC_Discrete_Time_Grid.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
