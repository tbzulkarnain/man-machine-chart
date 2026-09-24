import streamlit as st
import pandas as pd
import io
import json
import urllib.request

# ==========================================
# 1. PAGE CONFIGURATION & STYLING
# ==========================================
st.set_page_config(
    page_title="Footwear Line MMC Simulator",
    page_icon="👞",
    layout="wide"
)

# Custom CSS for polished LinkedIn portfolio look & clean footer
st.markdown("""
    <style>
    .main-title {
        font-size: 32px;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 5px;
    }
    .sub-title {
        font-size: 16px;
        color: #4B5563;
        margin-bottom: 25px;
    }
    .guide-box {
        background-color: #F0F9FF;
        border-left: 5px solid #0284C7;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 25px;
    }
    .footer-text {
        text-align: center;
        color: #6B7280;
        font-size: 13px;
        padding-top: 20px;
        padding-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. VISITOR COUNTER ENGINE
# ==========================================
def get_global_visitor_count():
    try:
        url = "https://api.counterapi.dev/v1/footwear-mmc-simulator-tz/visits/up"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            return data.get('count', '1+')
    except Exception:
        return "1+"

# ==========================================
# 3. HEADER & USER GUIDE
# ==========================================
st.markdown('<div class="main-title">👞 Footwear Manufacturing: Man-Machine Chart (MMC) Simulator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Industrial Engineering Tool for Multi-Machine Workstation Optimization & Idle Time Analysis</div>', unsafe_allow_html=True)

with st.container():
    st.markdown("""
    <div class="guide-box">
        <h4>📌 Quick User Guide</h4>
        <ol>
            <li><b>Configure Simulation Parameters:</b> Set the number of active machines and simulation cycles on the control panel below.</li>
            <li><b>Set Process Sequence:</b> Edit the cycle times, process steps, and actor assignment in the table (Default data represents Shoe Upper Stitching Process).</li>
            <li><b>Analyze Dynamic MMC Output:</b> Review the step-by-step Gantt simulation timeline to spot operator idle times and machine bottlenecks.</li>
            <li><b>Download Excel Report:</b> Click the <b>Download MMC Result (Excel)</b> button to export the simulation data for further engineering analysis.</li>
        </ol>
    </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. CONTROL PANEL & PROCESS INPUT TABLE
# ==========================================
st.subheader("⚙️ 1. Workstation & Process Configuration")

col1, col2 = st.columns(2)
with col1:
    num_machines = st.number_input("Number of Machines (Workstations)", min_value=1, max_value=10, value=2, step=1)
with col2:
    num_cycles = st.number_input("Simulation Cycles", min_value=1, max_value=10, value=2, step=1)

# Reset & auto-heal session_state jika terjadi bentrok nama kolom
if "table_data" not in st.session_state or "Process Step" not in st.session_state.table_data.columns:
    st.session_state.table_data = pd.DataFrame([
        {"Process Step": "Placing upper component to pallet", "Cycle Time (s)": 15.02, "Actor": "Man"},
        {"Process Step": "Loading & Unloading Shoe Upper", "Cycle Time (s)": 4.48, "Actor": "Both"},
        {"Process Step": "Take finished upper & inspect", "Cycle Time (s)": 2.47, "Actor": "Man"},
        {"Process Step": "Automatic Upper Stitching", "Cycle Time (s)": 51.72, "Actor": "Machine"}
    ])

edited_df = st.data_editor(
    st.session_state.table_data,
    num_rows="dynamic",
    column_config={
        "Process Step": st.column_config.TextColumn("Process Element Name", required=True),
        "Cycle Time (s)": st.column_config.NumberColumn("Cycle Time (sec)", min_value=0.01, format="%.2f", required=True),
        "Actor": st.column_config.SelectboxColumn("Assigned Actor", options=["Man", "Machine", "Both"], required=True),
    },
    use_container_width=True
)

# ==========================================
# 5. SIMULATION ENGINE
# ==========================================

def run_universal_mmc(df_input, n_mc, n_cycles):
    df_clean = df_input.dropna(subset=["Process Step", "Cycle Time (s)", "Actor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    op_free_at = 0.0
    
    mc_states = {m: {"free_at": 0.0, "is_running": False, "curr_act": "waiting", "cycle": 0} for m in range(1, n_mc + 1)}
    events = []

    def get_mc_snapshot(active_mc, active_act, current_t):
        snapshot = {}
        for i in range(1, n_mc + 1):
            if i == active_mc and active_act:
                snapshot[i] = active_act
            elif mc_states[i]["is_running"] and mc_states[i]["free_at"] > current_t:
                snapshot[i] = mc_states[i]["curr_act"]
            else:
                snapshot[i] = "waiting"
        return snapshot

    for c in range(n_cycles):
        for m in range(1, n_mc + 1):
            for step in steps:
                actor = step["Actor"]
                dur = float(step["Cycle Time (s)"])
                process_name = step["Process Step"]
                
                if actor == "Man":
                    start_t = op_free_at
                    end_t = start_t + dur
                    
                    events.append({
                        "start": start_t,
                        "end": end_t,
                        "op_act": f"{process_name} (MC {m})",
                        "mc_acts": get_mc_snapshot(None, None, start_t)
                    })
                    op_free_at = end_t
                    
                elif actor == "Both":
                    if mc_states[m]["is_running"] and mc_states[m]["free_at"] > op_free_at:
                        idle_start = op_free_at
                        idle_end = mc_states[m]["free_at"]
                        
                        events.append({
                            "start": idle_start,
                            "end": idle_end,
                            "op_act": "Operator Idle (Waiting Machine)",
                            "mc_acts": get_mc_snapshot(None, None, idle_start)
                        })
                        op_free_at = idle_end
                        mc_states[m]["is_running"] = False
                    
                    start_t = op_free_at
                    end_t = start_t + dur
                    
                    events.append({
                        "start": start_t,
                        "end": end_t,
                        "op_act": f"{process_name} (MC {m})",
                        "mc_acts": get_mc_snapshot(m, process_name, start_t)
                    })
                    op_free_at = end_t
                    
                elif actor == "Machine":
                    mc_states[m]["is_running"] = True
                    mc_states[m]["curr_act"] = process_name
                    mc_states[m]["free_at"] = op_free_at + dur

    rows = []
    for ev in events:
        dur = round(ev["end"] - ev["start"], 2)
        r = {
            "Timestamp (s)": round(ev["end"], 2),
            "Operator Activity": ev["op_act"],
            "Op Duration (s)": dur
        }
        for m in range(1, n_mc + 1):
            r[f"MC {m} Activity"] = ev["mc_acts"].get(m, "waiting")
            r[f"MC {m} Duration (s)"] = dur
        rows.append(r)
        
    return pd.DataFrame(rows)

# ==========================================
# 6. SUMMARY PERFORMANCE MATRIX
# ==========================================

def run_summary_matrix_steady_state(df_input, n_mc):
    df_clean = df_input.dropna(subset=["Process Step", "Cycle Time (s)", "Actor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    
    op_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Actor"] in ["Man", "Both"])
    mc_work_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Actor"] in ["Machine", "Both"])
    op_manual_per_mc = sum(float(s["Cycle Time (s)"]) for s in steps if s["Actor"] == "Man")
    
    total_op_work = op_work_per_mc * n_mc
    single_mc_cycle = mc_work_per_mc + op_manual_per_mc
    
    cycle_time = max(total_op_work, single_mc_cycle)
    op_idle = max(0.0, cycle_time - total_op_work)
    op_util = (total_op_work / cycle_time * 100) if cycle_time > 0 else 0

    summary_dict = {
        "Performance Metric": ["Working Time (s)", "Idle Time (s)", "Total Cycle Time (s)", "Utilization (%)"],
        "Operator / Manpower": [
            f"{total_op_work:.2f}",
            f"{op_idle:.2f}",
            f"{cycle_time:.2f}",
            f"{round(op_util, 1)}%"
        ]
    }

    for m in range(1, n_mc + 1):
        mc_idle = max(0.0, cycle_time - single_mc_cycle)
        mc_util = (single_mc_cycle / cycle_time * 100) if cycle_time > 0 else 0
        
        summary_dict[f"Machine {m}"] = [
            f"{single_mc_cycle:.2f}",
            f"{mc_idle:.2f}",
            f"{cycle_time:.2f}",
            f"{round(mc_util, 1)}%"
        ]

    return pd.DataFrame(summary_dict)

# Helper function untuk konversi DataFrame ke Excel Binary
def convert_df_to_excel(df_timeline, df_summary):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_timeline.to_excel(writer, sheet_name='MMC Timeline', index=False)
        df_summary.to_excel(writer, sheet_name='Performance Summary', index=False)
    return output.getvalue()

# ==========================================
# 7. RENDER OUTPUT & VISUALS
# ==========================================
st.markdown("---")
st.subheader("📊 2. Dynamic Man-Machine Simulation Timeline")

res_df = run_universal_mmc(edited_df, num_machines, num_cycles)

if not res_df.empty:
    st.dataframe(res_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📈 3. Steady-State Workstation Performance Matrix")
    
    sum_df = run_summary_matrix_steady_state(edited_df, num_machines)
    
    if not sum_df.empty:
        # Display key metrics at top of summary
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total Cycle Time", f"{sum_df.iloc[2, 1]} s")
        with col_m2:
            st.metric("Operator Utilization", f"{sum_df.iloc[3, 1]}")
        with col_m3:
            st.metric("Operator Idle Time", f"{sum_df.iloc[1, 1]} s")

        st.dataframe(sum_df, use_container_width=True, hide_index=True)

        # Download Excel Section
        st.markdown("<br>", unsafe_allow_html=True)
        excel_data = convert_df_to_excel(res_df, sum_df)
        st.download_button(
            label="📥 Download MMC Result (Excel .xlsx)",
            data=excel_data,
            file_name=f"MMC_Simulation_{num_machines}MC_{num_cycles}Cycles.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
else:
    st.warning("⚠️ Please provide valid process steps in the table above to run the simulation.")

# ==========================================
# 8. FOOTER WITH SUBTLE VISITOR COUNTER
# ==========================================
st.markdown("---")
visitor_count = get_global_visitor_count()
st.markdown(
    f'<div class="footer-text">Footwear Man-Machine Chart Simulator | Industrial Engineering Portfolio | 👁️ Total Visitors: <b>{visitor_count}</b></div>', 
    unsafe_allow_html=True
)
