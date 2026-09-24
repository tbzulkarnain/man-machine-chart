import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

# ==========================================
# 1. LOGIKA SIMULASI MMC UNIVERSAL
# ==========================================
def run_universal_mmc_simulation(user_elements, num_machines, num_cycles):
    prep_elems = []
    mc_elems = []
    post_elems = []
    
    current_phase = "PREP"
    for el in user_elements:
        actor = el["Aktor"]
        if actor == "Machine":
            mc_elems.append(el)
            current_phase = "POST"
        elif current_phase == "PREP":
            prep_elems.append(el)
        else:
            post_elems.append(el)
            
    mc_total_dur = sum(float(el["Cycle Time (s)"]) for el in mc_elems)
    mc_main_name = " + ".join([str(el["Proses"]) for el in mc_elems]) if mc_elems else "Machine Process"

    mc_state = {m: 'READY_TO_LOAD' for m in range(1, num_machines + 1)}
    mc_finish_time = {m: 0.0 for m in range(1, num_machines + 1)}
    mc_cycles_done = {m: 0 for m in range(1, num_machines + 1)}

    current_time = 0.0
    raw_events = []

    while min(mc_cycles_done.values()) < num_cycles:
        # Update status mesin berdasarkan waktu saat ini
        for m in range(1, num_machines + 1):
            if mc_state[m] == 'RUNNING' and current_time >= mc_finish_time[m]:
                mc_state[m] = 'READY_TO_UNLOAD'

        # Prioritas 1: Unload mesin yang sudah matang/selesai
        unload_mc = None
        for m in range(1, num_machines + 1):
            if mc_state[m] == 'READY_TO_UNLOAD' and mc_cycles_done[m] < num_cycles:
                unload_mc = m
                break

        if unload_mc is not None:
            for el in post_elems:
                dur = float(el["Cycle Time (s)"])
                act_name = f"{el['Proses']} MC {unload_mc}" if num_machines > 1 else str(el['Proses'])
                raw_events.append({"start": current_time, "end": current_time + dur, "owner": "Op", "id": 0, "name": act_name})
                if el["Aktor"] == "Both":
                    raw_events.append({"start": current_time, "end": current_time + dur, "owner": "MC", "id": unload_mc, "name": str(el['Proses'])})
                current_time += dur
            
            mc_state[unload_mc] = 'READY_TO_LOAD'
            mc_cycles_done[unload_mc] += 1
            continue

        # Prioritas 2: Load mesin yang kosong
        load_mc = None
        for m in range(1, num_machines + 1):
            if mc_state[m] == 'READY_TO_LOAD' and mc_cycles_done[m] < num_cycles:
                load_mc = m
                break

        if load_mc is not None:
            for el in prep_elems:
                dur = float(el["Cycle Time (s)"])
                act_name = f"{el['Proses']} MC {load_mc}" if num_machines > 1 else str(el['Proses'])
                raw_events.append({"start": current_time, "end": current_time + dur, "owner": "Op", "id": 0, "name": act_name})
                if el["Aktor"] == "Both":
                    raw_events.append({"start": current_time, "end": current_time + dur, "owner": "MC", "id": load_mc, "name": str(el['Proses'])})
                current_time += dur

            if mc_elems:
                mc_state[load_mc] = 'RUNNING'
                mc_finish_time[load_mc] = current_time + mc_total_dur
                raw_events.append({"start": current_time, "end": current_time + mc_total_dur, "owner": "MC", "id": load_mc, "name": mc_main_name})
            else:
                mc_cycles_done[load_mc] += 1
            continue

        # Prioritas 3: Operator Idle (Menunggu semua mesin running)
        running_mcs = [m for m in range(1, num_machines + 1) if mc_state[m] == 'RUNNING' and mc_cycles_done[m] < num_cycles]
        if not running_mcs:
            break

        next_finish = min(mc_finish_time[m] for m in running_mcs)
        idle_dur = round(next_finish - current_time, 2)

        if idle_dur > 0:
            raw_events.append({"start": current_time, "end": next_finish, "owner": "Op", "id": 0, "name": "idle"})
            current_time = next_finish

        for m in range(1, num_machines + 1):
            if mc_state[m] == 'RUNNING' and current_time >= mc_finish_time[m]:
                mc_state[m] = 'READY_TO_UNLOAD'

    # Diskretisasi kisi waktu
    time_points = set([0.0])
    for act in raw_events:
        time_points.add(round(act["start"], 2))
        time_points.add(round(act["end"], 2))

    sorted_times = sorted(list(time_points))

    grid_rows = []
    for i in range(1, len(sorted_times)):
        t_start = sorted_times[i-1]
        t_end = sorted_times[i]
        dur = round(t_end - t_start, 2)
        if dur <= 0:
            continue

        op_act = "idle"
        for act in raw_events:
            if act["owner"] == "Op" and act["start"] <= t_start and act["end"] >= t_end:
                op_act = act["name"]
                break

        row_item = {
            "cum_time": t_end,
            "op_act": op_act,
            "op_dur": dur,
            "mc_data": {}
        }

        for m in range(1, num_machines + 1):
            mc_act = "waiting"
            for act in raw_events:
                if act["owner"] == "MC" and act["id"] == m and act["start"] <= t_start and act["end"] >= t_end:
                    mc_act = act["name"]
                    break
            row_item["mc_data"][m] = {"act": mc_act, "dur": dur}

        grid_rows.append(row_item)

    return grid_rows

# ==========================================
# 2. EXPORT EXCEL RAPI BERSATU SAMA STYLE
# ==========================================
def export_mmc_to_excel(grid_data, num_machines):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Man-Machine Chart"
    ws.views.sheetView[0].showGridLines = True

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    sub_header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
    idle_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    text_white = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    text_bold = Font(name="Calibri", size=11, bold=True)
    text_regular = Font(name="Calibri", size=11)
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    # Header Judul
    ws.cell(row=1, column=1, value="MAN-MACHINE CHART (MMC) REPORT").font = Font(name="Calibri", size=14, bold=True, color="1F4E79")

    # Super Header (Row 3)
    ws.cell(row=3, column=1, value="Time (s)").fill = header_fill
    ws.cell(row=3, column=1).font = text_white
    ws.merge_cells(start_row=3, start_column=2, end_row=3, end_column=3)
    ws.cell(row=3, column=2, value="OPERATOR").fill = header_fill
    ws.cell(row=3, column=2).font = text_white
    ws.cell(row=3, column=2).alignment = Alignment(horizontal="center")

    col_idx = 4
    for m in range(1, num_machines + 1):
        ws.merge_cells(start_row=3, start_column=col_idx, end_row=3, end_column=col_idx+1)
        c = ws.cell(row=3, column=col_idx, value=f"MACHINE {m}")
        c.fill = header_fill
        c.font = text_white
        c.alignment = Alignment(horizontal="center")
        col_idx += 2

    # Sub Header (Row 4)
    ws.cell(row=4, column=1, value="Cum Time").fill = sub_header_fill
    ws.cell(row=4, column=1).font = text_white
    ws.cell(row=4, column=2, value="Activity").fill = sub_header_fill
    ws.cell(row=4, column=2).font = text_white
    ws.cell(row=4, column=3, value="Time").fill = sub_header_fill
    ws.cell(row=4, column=3).font = text_white

    col_idx = 4
    for m in range(1, num_machines + 1):
        ws.cell(row=4, column=col_idx, value="Activity").fill = sub_header_fill
        ws.cell(row=4, column=col_idx).font = text_white
        ws.cell(row=4, column=col_idx+1, value="Time").fill = sub_header_fill
        ws.cell(row=4, column=col_idx+1).font = text_white
        col_idx += 2

    # Isi Data (Row 5+)
    start_row = 5
    for r_idx, r in enumerate(grid_data):
        curr_row = start_row + r_idx
        ws.cell(row=curr_row, column=1, value=r["cum_time"]).font = text_bold
        ws.cell(row=curr_row, column=2, value=r["op_act"]).font = text_regular
        ws.cell(row=curr_row, column=3, value=r["op_dur"]).font = text_regular

        if r["op_act"] == "idle":
            ws.cell(row=curr_row, column=2).fill = idle_fill
            ws.cell(row=curr_row, column=3).fill = idle_fill

        c_idx = 4
        for m in range(1, num_machines + 1):
            m_act = r["mc_data"][m]["act"]
            m_dur = r["mc_data"][m]["dur"]
            ws.cell(row=curr_row, column=c_idx, value=m_act).font = text_regular
            ws.cell(row=curr_row, column=c_idx+1, value=m_dur).font = text_regular
            if m_act in ["waiting", "idle"]:
                ws.cell(row=curr_row, column=c_idx).fill = idle_fill
                ws.cell(row=curr_row, column=c_idx+1).fill = idle_fill
            c_idx += 2

        for c in range(1, 4 + 2 * num_machines):
            ws.cell(row=curr_row, column=c).border = thin_border

    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output

# ==========================================
# 3. INTERFACE STREAMLIT
# ==========================================
st.set_page_config(page_title="Universal MMC Generator", layout="wide")

st.title("⚙️ Universal Man-Machine Chart (MMC) Generator")
st.markdown("Input urutan proses kerja secara bebas, tentukan durasi dan aktornya. Engine akan menyusun jadwal MMC multi-mesin secara otomatis.")

col_config1, col_config2 = st.columns(2)
with col_config1:
    num_machines = st.number_input("Jumlah Mesin", min_value=1, max_value=10, value=2, step=1)
with col_config2:
    num_cycles = st.number_input("Jumlah Siklus Simulasi", min_value=1, max_value=10, value=2, step=1)

st.subheader("1. Masukkan Urutan Proses Kerja")

default_data = pd.DataFrame([
    {"Proses": "Placing component vamp to MC", "Cycle Time (s)": 80.0, "Aktor": "Man"},
    {"Proses": "Loading", "Cycle Time (s)": 6.0, "Aktor": "Both"},
    {"Proses": "Hot Press MC", "Cycle Time (s)": 60.0, "Aktor": "Machine"},
    {"Proses": "Unloading / Take result", "Cycle Time (s)": 6.0, "Aktor": "Both"}
])

edited_df = st.data_editor(
    default_data,
    num_rows="dynamic",
    column_config={
        "Proses": st.column_config.TextColumn("Nama Elemen Proses", required=True),
        "Cycle Time (s)": st.column_config.NumberColumn("Cycle Time (Detik)", min_value=0.1, format="%.1f", required=True),
        "Aktor": st.column_config.SelectboxColumn("Aktor / Pemeran", options=["Man", "Machine", "Both"], required=True),
    },
    use_container_width=True
)

if st.button("🚀 Generate MMC Chart", type="primary"):
    user_elements = edited_df.to_dict(orient="records")
    
    if not user_elements:
        st.error("Proses tidak boleh kosong!")
    else:
        grid_res = run_universal_mmc_simulation(user_elements, int(num_machines), int(num_cycles))
        
        # Format dataframe untuk tampilan Streamlit
        st.subheader("2. Tampilan Hasil Man-Machine Chart")
        
        display_data = []
        for r in grid_res:
            row_dict = {
                "Time (s)": r["cum_time"],
                "Operator Activity": r["op_act"],
                "Op Time": r["op_dur"]
            }
            for m in range(1, int(num_machines) + 1):
                row_dict[f"MC {m} Activity"] = r["mc_data"][m]["act"]
                row_dict[f"MC {m} Time"] = r["mc_data"][m]["dur"]
            display_data.append(row_dict)
            
        df_display = pd.DataFrame(display_data)
        st.dataframe(df_display, use_container_width=True)
        
        # Hitung KPI
        total_time = grid_res[-1]["cum_time"] if grid_res else 0
        total_op_idle = sum(r["op_dur"] for r in grid_res if r["op_act"] == "idle")
        op_utilization = ((total_time - total_op_idle) / total_time * 100) if total_time > 0 else 0
        
        st.subheader("3. Ringkasan Kinerja (KPI Summary)")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total Waktu Siklus (Detik)", f"{total_time:.1f} s")
        kpi2.metric("Total Operator Idle", f"{total_op_idle:.1f} s")
        kpi3.metric("Operator Utilization Rate", f"{op_utilization:.1f} %")
        
        # Download Excel
        excel_data = export_mmc_to_excel(grid_res, int(num_machines))
        st.download_button(
            label="📥 Download Laporan Excel (.xlsx)",
            data=excel_data,
            file_name=f"MMC_Report_{num_machines}MC.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
