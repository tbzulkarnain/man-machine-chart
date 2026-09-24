import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

st.set_page_config(page_title="Queue Engine MMC Generator", layout="wide")

st.title("⚙️ Man-Machine Chart (MMC) Generator - Queue Engine")
st.caption("Prinsip Utama: Operator Tidak Idle Selama Ada Mesin Siap Dikerjakan")

# =============================================================================
# 1. INPUT PARAMETER
# =============================================================================
st.sidebar.header("⚙️ Konfigurasi Mesin & Simulasi")
num_machines = st.sidebar.number_input("Jumlah Mesin (N):", min_value=1, max_value=5, value=2, step=1)
num_cycles = st.sidebar.slider("Jumlah Siklus Simulasi:", min_value=1, max_value=5, value=2)

st.subheader("📝 Master Elemen Proses")
default_data = [
    {"Seq": 1, "Process": "Placing & Loading component", "Duration": 80.0, "Actor": "Both"},
    {"Seq": 2, "Process": "Hot Press MC", "Duration": 60.0, "Actor": "Machine"},
    {"Seq": 3, "Process": "Unloading / Take result", "Duration": 6.0, "Actor": "Both"},
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
# 2. DYNAMIC QUEUE SIMULATION ENGINE
# =============================================================================
if valid_rows:
    load_elem = next((r for r in valid_rows if r["Actor"] == "Both" and "load" in r["Process"].lower()), None)
    mc_elem = next((r for r in valid_rows if r["Actor"] == "Machine"), None)
    unload_elem = next((r for r in valid_rows if r["Actor"] == "Both" and ("unload" in r["Process"].lower() or "take" in r["Process"].lower())), None)

    load_dur = load_elem["Duration"] if load_elem else 10.0
    load_name = load_elem["Process"] if load_elem else "Loading"
    
    mc_dur = mc_elem["Duration"] if mc_elem else 60.0
    mc_name = mc_elem["Process"] if mc_elem else "Machine Running"
    
    unload_dur = unload_elem["Duration"] if unload_elem else 5.0
    unload_name = unload_elem["Process"] if unload_elem else "Unloading"

    mc_status = {m: 'EMPTY' for m in range(1, num_machines + 1)}
    mc_finish_time = {m: 0.0 for m in range(1, num_machines + 1)}
    mc_cycle_count = {m: 0 for m in range(1, num_machines + 1)}

    current_time = 0.0
    raw_events = []

    while min(mc_cycle_count.values()) < num_cycles:
        for m in range(1, num_machines + 1):
            if mc_status[m] == 'RUNNING' and current_time >= mc_finish_time[m]:
                mc_status[m] = 'DONE'

        target_mc = None
        action_type = None

        # Prioritas 1: Unload mesin yang sudah selesai running
        for m in range(1, num_machines + 1):
            if mc_status[m] == 'DONE' and mc_cycle_count[m] < num_cycles:
                target_mc = m
                action_type = 'UNLOAD'
                break

        # Prioritas 2: Load mesin yang kosong
        if target_mc is None:
            for m in range(1, num_machines + 1):
                if mc_status[m] == 'EMPTY' and mc_cycle_count[m] < num_cycles:
                    target_mc = m
                    action_type = 'LOAD'
                    break

        # Prioritas 3: Jika tidak ada mesin siap, Operator IDLE sampai ada mesin selesai
        if target_mc is None:
            running_mcs = [m for m in range(1, num_machines + 1) if mc_status[m] == 'RUNNING' and mc_cycle_count[m] < num_cycles]
            if not running_mcs:
                break
            
            next_finish = min(mc_finish_time[m] for m in running_mcs)
            idle_dur = round(next_finish - current_time, 2)
            
            if idle_dur > 0:
                raw_events.append({
                    "start": current_time, "end": next_finish, "dur": idle_dur,
                    "owner": "Op", "id": 0, "name": "idle"
                })
                current_time = next_finish

            for m in range(1, num_machines + 1):
                if mc_status[m] == 'RUNNING' and current_time >= mc_finish_time[m]:
                    mc_status[m] = 'DONE'
            continue

        # Eksekusi Aktivitas Operator & Mesin
        if action_type == 'UNLOAD':
            raw_events.append({
                "start": current_time, "end": current_time + unload_dur, "dur": unload_dur,
                "owner": "Op", "id": 0, "name": f"{unload_name} MC {target_mc}" if num_machines > 1 else unload_name
            })
            raw_events.append({
                "start": current_time, "end": current_time + unload_dur, "dur": unload_dur,
                "owner": "MC", "id": target_mc, "name": unload_name
            })
            current_time += unload_dur
            mc_status[target_mc] = 'EMPTY'
            mc_cycle_count[target_mc] += 1

        elif action_type == 'LOAD':
            raw_events.append({
                "start": current_time, "end": current_time + load_dur, "dur": load_dur,
                "owner": "Op", "id": 0, "name": f"{load_name} MC {target_mc}" if num_machines > 1 else load_name
            })
            raw_events.append({
                "start": current_time, "end": current_time + load_dur, "dur": load_dur,
                "owner": "MC", "id": target_mc, "name": load_name
            })
            current_time += load_dur
            
            mc_status[target_mc] = 'RUNNING'
            mc_finish_time[target_mc] = current_time + mc_dur
            raw_events.append({
                "start": current_time, "end": current_time + mc_dur, "dur": mc_dur,
                "owner": "MC", "id": target_mc, "name": mc_name
            })

    # =============================================================================
    # 3. MENGUBAH KE GRID TIME SLICE (DISCRETE INTERVALS)
    # =============================================================================
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

    # Preview Dataframe
    st.markdown("---")
    st.subheader("📋 Output Tabel Discrete Time Grid")
    
    table_preview = []
    for r in grid_rows:
        row_dict = {
            "Time (s)": r["cum_time"],
            "Operator Process": r["op_act"],
            "Time (s) Op": r["op_dur"]
        }
        for m in range(1, num_machines + 1):
            row_dict[f"MC {m}"] = r["mc_data"][m]["act"]
            row_dict[f"Time (s) MC{m}"] = r["mc_data"][m]["dur"]
        table_preview.append(row_dict)

    st.dataframe(pd.DataFrame(table_preview), use_container_width=True)

    # Export Excel Generator
    def generate_exact_excel():
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "MMC Output"
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

        for row in range(2, ws.max_row + 1):
            for col in range(1, ws.max_column + 1):
                cell = ws.cell(row=row, column=col)
                cell.font = regular_font
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center" if col != 2 else "left", vertical="center")
                
                if str(cell.value).lower() in ["idle", "waiting"]:
                    cell.fill = idle_fill

        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    st.download_button(
        label="📥 Download Excel MMC (.xlsx)",
        data=generate_exact_excel(),
        file_name="MMC_Optimized_Queue.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
