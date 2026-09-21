import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

st.set_page_config(page_title="Universal MMC Generator", layout="wide")
st.title("⚙️ Universal Man-Machine Chart (MMC) Generator")

# =============================================================================
# 1. INPUT SETUP
# =============================================================================
st.sidebar.header("⚙️ Setting Simulasi")
num_machines = st.sidebar.number_input("Jumlah Mesin (N):", min_value=1, max_value=5, value=2, step=1)
travel_time = st.sidebar.number_input("Travel Time (detik):", min_value=0.0, value=0.0, step=0.5)
num_cycles = st.sidebar.slider("Siklus Simulasi:", min_value=1, max_value=4, value=2)

st.subheader("📝 Master Elemen Proses")
default_data = [
    {"Seq": 1, "Process": "Placing component vamp to MC", "Duration": 80.0, "Actor": "Man"},
    {"Seq": 2, "Process": "Loading", "Duration": 80.0, "Actor": "Both"},
    {"Seq": 3, "Process": "Hot Press MC", "Duration": 60.0, "Actor": "Machine"},
    {"Seq": 4, "Process": "Take result / Unloading", "Duration": 6.0, "Actor": "Both"},
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
# 2. EVENT-BOUNDED SIMULATION ENGINE
# =============================================================================
if valid_rows:
    st_elem = next((r for r in valid_rows if r["Actor"] == "Machine"), None)
    st_dur = st_elem["Duration"] if st_elem else 0.0
    st_name = st_elem["Process"] if st_elem else "Machine Process"

    # Engine melacak interval waktu persis
    events = []
    current_time = 0.0
    mc_finish = {m: 0.0 for m in range(1, num_machines + 1)}

    op_sequence = [r for r in valid_rows if r["Actor"] in ["Man", "Both"]]

    for cyc in range(num_cycles):
        for m in range(1, num_machines + 1):
            for elem in op_sequence:
                p_name = elem["Process"]
                dur = elem["Duration"]
                act = elem["Actor"]

                # Cek jika Operator harus Menunggu (Idle)
                if act == "Both" and current_time < mc_finish[m]:
                    wait_time = mc_finish[m] - current_time
                    events.append({
                        "start": current_time,
                        "end": current_time + wait_time,
                        "dur": round(wait_time, 2),
                        "op_act": "idle",
                        "target_mc": m,
                        "type": "IDLE"
                    })
                    current_time += wait_time

                # Eksekusi Kerja Operator
                events.append({
                    "start": current_time,
                    "end": current_time + dur,
                    "dur": round(dur, 2),
                    "op_act": f"{p_name} MC {m}#" if num_machines > 1 else p_name,
                    "target_mc": m,
                    "type": act
                })
                current_time += dur

                # Trigger Mesin Running
                if act == "Both" and "load" in p_name.lower():
                    mc_finish[m] = current_time + st_dur

            # Travel Time
            if travel_time > 0:
                events.append({
                    "start": current_time,
                    "end": current_time + travel_time,
                    "dur": round(travel_time, 2),
                    "op_act": "Travel / Move",
                    "target_mc": None,
                    "type": "TRAVEL"
                })
                current_time += travel_time

    # =========================================================================
    # 3. BUILD EXCEL WITH EXACT ALIGNED FORMAT
    # =========================================================================
    def export_excel():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "MMC Process Sheet"
        ws.views.sheetView[0].showGridLines = True

        header_fill = PatternFill(start_color="9BC2E6", end_color="9BC2E6", fill_type="solid")
        idle_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        bold_font = Font(name="Calibri", size=10, bold=True)
        regular_font = Font(name="Calibri", size=10)
        thin_border = Border(
            left=Side(style='thin', color='000000'), right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'), bottom=Side(style='thin', color='000000')
        )

        # Header
        headers = ["Time", "Process Operator 1", "Time Second"]
        for m in range(1, num_machines + 1):
            headers.extend([f"MC {m}", "Time Second"])

        ws.append(headers)
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=c)
            cell.fill = header_fill
            cell.font = bold_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        # Isikan Data Per Baris Kejadian (Align Sejajar)
        for ev in events:
            cum_t = round(ev["end"], 2)
            op_act = ev["op_act"]
            op_dur = ev["dur"]
            start_t = ev["start"]
            target_mc = ev["target_mc"]

            row_data = [cum_t, op_act, op_dur]

            # Evaluasi Status Mesin di Interval [start_t, end_t]
            for m in range(1, num_machines + 1):
                col_mc = 4 + (m - 1) * 2
                
                if target_mc == m and ev["type"] == "Both":
                    mc_act = op_act.split(" MC")[0]
                    mc_dur = op_dur
                elif start_t < mc_finish[m] and round(mc_finish[m] - start_t, 2) > 0:
                    mc_act = st_name
                    mc_dur = op_dur
                else:
                    mc_act = "idle" if start_t >= mc_finish[m] else "Waiting"
                    mc_dur = op_dur

                row_data.extend([mc_act, mc_dur])

            ws.append(row_data)

        # Formatting Cell Border & Alignment
        for r in range(2, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(row=r, column=c)
                cell.font = regular_font
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center" if c != 2 else "left", vertical="center")
                if str(cell.value).lower() in ["idle", "waiting"]:
                    cell.fill = idle_fill

        # Auto Width
        for col in ws.columns:
            max_l = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_l + 3, 12)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    st.markdown("---")
    st.download_button(
        label="📥 Download Excel MMC Presisi (.xlsx)",
        data=export_excel(),
        file_name="MMC_Exact_Reference_Format.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
