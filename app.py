import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

st.set_page_config(page_title="Universal MMC Excel Generator", layout="wide")

st.title("⚙️ Universal Man-Machine Chart (MMC) Generator")
st.caption("Aplikasi IE untuk Menghasilkan Tabel MMC Real-Time & Export Excel Merged-Cell Standard")

# =============================================================================
# 1. INPUT PARAMETER & ELEMEN KERJA
# =============================================================================
st.sidebar.header("⚙️ Parameter Lapangan")
travel_time = st.sidebar.number_input("Travel Time antar Mesin (s)", min_value=0.0, value=0.0, step=0.5)
num_cycles = st.sidebar.slider("Jumlah Siklus Simulasi", min_value=1, max_value=5, value=2)

default_data = [
    {"Seq": 1, "Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Seq": 2, "Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Seq": 3, "Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
    {"Seq": 4, "Process": "take result", "Duration": 2.47, "Actor": "Man"},
]

st.subheader("📝 Input Elemen Proses Standard (1 Siklus Master)")
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

num_machines = st.number_input("Jumlah Mesin (N):", min_value=1, max_value=5, value=2, step=1)

# Validasi data
valid_df = edited_df[(edited_df["Process"].astype(str).str.strip() != "") & (edited_df["Duration"] > 0)].sort_values(by="Seq")
valid_rows = valid_df.to_dict("records")

# =============================================================================
# 2. SIMULATION ENGINE (GENERATING EXACT TIMELINE)
# =============================================================================
if valid_rows:
    st_elem = next((r for r in valid_rows if r["Actor"] == "Machine"), None)
    st_dur = st_elem["Duration"] if st_elem else 0.0
    st_name = st_elem["Process"] if st_elem else "St Process"

    op_elements = [r for r in valid_rows if r["Actor"] in ["Man", "Both"]]

    # Trackers
    current_time = 0.0
    mc_status = {m: {"state": "waiting", "finish_at": 0.0, "start_at": 0.0} for m in range(1, num_machines + 1)}
    
    # Store events: list of dicts
    events = []

    for cyc in range(num_cycles):
        for m in range(1, num_machines + 1):
            for elem in op_elements:
                p_name = elem["Process"]
                dur = elem["Duration"]
                act = elem["Actor"]

                # Cek jika operator harus menunggu mesin selesai berjalan
                if act == "Both" and current_time < mc_status[m]["finish_at"]:
                    idle_dur = mc_status[m]["finish_at"] - current_time
                    start_t = current_time
                    current_time += idle_dur
                    events.append({
                        "cum_time": round(current_time, 2),
                        "op_act": "idle",
                        "op_dur": round(idle_dur, 2),
                        "active_mc": m,
                        "action_type": "IDLE"
                    })

                # Jalankan Aktivitas Operator
                start_t = current_time
                current_time += dur
                
                evt_type = "BOTH" if act == "Both" else "MAN"
                events.append({
                    "cum_time": round(current_time, 2),
                    "op_act": p_name,
                    "op_dur": round(dur, 2),
                    "active_mc": m,
                    "action_type": evt_type
                })

                # Trigger Mesin Running
                if act == "Both":
                    mc_status[m]["state"] = "running"
                    mc_status[m]["start_at"] = current_time
                    mc_status[m]["finish_at"] = current_time + st_dur

            # Travel time
            if travel_time > 0 and (m < num_machines or cyc < num_cycles - 1):
                current_time += travel_time
                events.append({
                    "cum_time": round(current_time, 2),
                    "op_act": "Travel to next MC",
                    "op_dur": round(travel_time, 2),
                    "active_mc": None,
                    "action_type": "TRAVEL"
                })

    # Tampilkan Preview Data Frame di Streamlit
    preview_rows = []
    for ev in events:
        row = {
            "Time (s)": ev["cum_time"],
            "Operator": ev["op_act"],
            "Time (s) ": ev["op_dur"]
        }
        preview_rows.append(row)
        
    st.markdown("---")
    st.subheader("📋 Preview Line-by-Line Activity")
    st.dataframe(pd.DataFrame(preview_rows), use_container_width=True)

    # =========================================================================
    # 3. EXPORT TO EXCEL WITH EXACT MERGED CELLS LOGIC
    # =========================================================================
    def generate_excel():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "MMC Chart"
        ws.views.sheetView[0].showGridLines = True

        header_fill = PatternFill(start_color="9BC2E6", end_color="9BC2E6", fill_type="solid")
        idle_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
        bold_font = Font(name="Calibri", size=11, bold=True)
        regular_font = Font(name="Calibri", size=11)
        thin_border = Border(
            left=Side(style='thin', color='000000'), right=Side(style='thin', color='000000'),
            top=Side(style='thin', color='000000'), bottom=Side(style='thin', color='000000')
        )

        # Build Headers
        headers = ["Time (s)", "Operator", "Time (s)"]
        for m in range(1, num_machines + 1):
            headers.extend([f"Machine {m}", "Time (s)"])

        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = bold_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border

        # Tulis Baris Operator Pertama
        for ev in events:
            r_vals = [ev["cum_time"], ev["op_act"], ev["op_dur"]]
            for m in range(1, num_machines + 1):
                r_vals.extend(["", ""])
            ws.append(r_vals)

        # Logika Pengisian & Merge Cells untuk Mesin
        # Kita akan iterasi setiap mesin dan mencocokkan rentang waktu
        for m in range(1, num_machines + 1):
            col_mc = 4 + (m - 1) * 2
            col_dur = col_mc + 1

            # Melacak status per baris
            row_idx = 2
            while row_idx <= len(events) + 1:
                ev = events[row_idx - 2]
                cum_t = ev["cum_time"]
                prev_t = cum_t - ev["op_dur"]

                # Cek apakah di baris ini operator melakukan Loading/Unloading di mesin m
                if ev["active_mc"] == m and ev["action_type"] == "BOTH":
                    # Tulis Loading/Unloading
                    ws.cell(row=row_idx, column=col_mc, value=ev["op_act"])
                    ws.cell(row=row_idx, column=col_dur, value=ev["op_dur"])
                    row_idx += 1

                    # Setelah Both, Mesin m masuk St Process selama st_dur!
                    if st_dur > 0 and row_idx <= len(events) + 1:
                        st_start_row = row_idx
                        st_accum_time = 0.0
                        
                        while row_idx <= len(events) + 1 and round(st_accum_time, 2) < round(st_dur, 2):
                            curr_ev = events[row_idx - 2]
                            st_accum_time += curr_ev["op_dur"]
                            row_idx += 1

                        st_end_row = row_idx - 1

                        # Lakukan MERGE CELL jika mencakup lebih dari 1 baris
                        if st_end_row >= st_start_row:
                            if st_end_row > st_start_row:
                                ws.merge_cells(start_row=st_start_row, start_column=col_mc, end_row=st_end_row, end_column=col_mc)
                                ws.merge_cells(start_row=st_start_row, start_column=col_dur, end_row=st_end_row, end_column=col_dur)
                            
                            ws.cell(row=st_start_row, column=col_mc, value=st_name)
                            ws.cell(row=st_start_row, column=col_dur, value=st_dur)
                else:
                    # Jika mesin menganggur/waiting
                    if ws.cell(row=row_idx, column=col_mc).value is None or ws.cell(row=row_idx, column=col_mc).value == "":
                        ws.cell(row=row_idx, column=col_mc, value="waiting")
                        ws.cell(row=row_idx, column=col_dur, value=ev["op_dur"])
                    row_idx += 1

        # Formatting Akhir (Borders, Alignments, Idle Fills)
        for r in range(2, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                cell = ws.cell(row=r, column=c)
                cell.border = thin_border
                cell.font = regular_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
                if str(cell.value).lower() in ["idle", "waiting"]:
                    cell.fill = idle_fill

        # Auto-fit Column Widths
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    st.download_button(
        label="📥 Download MMC Excel Persis Format Sampel (.xlsx)",
        data=generate_excel(),
        file_name=f"MMC_Merged_Pattern_{num_machines}MC.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
