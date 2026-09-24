# ==========================================
# 5. FIXED SIMULATION ENGINE (NO EMPTY SCREEN)
# ==========================================

def run_universal_mmc(df_input, n_mc, n_cycles):
    df_clean = df_input.dropna(subset=["Process Step", "Cycle Time (s)", "Actor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    op_free_at = 0.0
    
    # Ambil durasi & nama proses mesin jika ada
    mc_dur = 0.0
    mc_step_name = "Machine Stitching"
    for s in steps:
        if s["Actor"] == "Machine":
            mc_dur = float(s["Cycle Time (s)"])
            mc_step_name = s["Process Step"]
            break

    mc_states = {m: {"free_at": 0.0, "is_running": False, "curr_act": "waiting"} for m in range(1, n_mc + 1)}
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
                    # Cek apakah operator harus tunggu mesin selesai jalan
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

                    # Mesin LANGSUNG JALAN tepat setelah Loading & Unloading selesai!
                    if mc_dur > 0:
                        mc_states[m]["is_running"] = True
                        mc_states[m]["curr_act"] = mc_step_name
                        mc_states[m]["free_at"] = op_free_at + mc_dur

                elif actor == "Machine":
                    # Jika proses mesin berdiri sendiri (tanpa pemicu Both)
                    if not mc_states[m]["is_running"]:
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
# 6. RENDERING TABEL & OUTPUT
# ==========================================
st.markdown("---")
st.subheader("📊 2. Dynamic Man-Machine Simulation Timeline")

res_df = run_universal_mmc(edited_df, num_machines, num_cycles)

if res_df is not None and not res_df.empty:
    st.dataframe(res_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("📈 3. Steady-State Workstation Performance Matrix")
    
    sum_df = run_summary_matrix_steady_state(edited_df, num_machines)
    
    if sum_df is not None and not sum_df.empty:
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total Cycle Time", f"{sum_df.iloc[2, 1]} s")
        with col_m2:
            st.metric("Operator Utilization", f"{sum_df.iloc[3, 1]}")
        with col_m3:
            st.metric("Operator Idle Time", f"{sum_df.iloc[1, 1]} s")

        st.dataframe(sum_df, use_container_width=True, hide_index=True)

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
    st.error("⚠️ Tabel simulasi kosong. Pastikan data pada 'Workstation & Process Configuration' sudah terisi lengkap.")
