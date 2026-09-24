# ==========================================
# FIXED SIMULATION ENGINE
# ==========================================

def run_universal_mmc(df_input, n_mc, n_cycles):
    df_clean = df_input.dropna(subset=["Process Step", "Cycle Time (s)", "Actor"]).copy()
    if df_clean.empty:
        return pd.DataFrame()

    steps = df_clean.to_dict('records')
    op_free_at = 0.0
    
    # Cari waktu durasi mesin (Machine process)
    mc_dur = 0.0
    mc_step_name = "Machine Process"
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
                
                # Abaikan elemen 'Machine' standalone dalam loop karena otomatis dipicu setelah 'Both'
                if actor == "Machine":
                    continue

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
                    # Cek jika operator harus tunggu mesin yang sedang berjalan
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

                    # PERBAIKAN: Mesin LANGSUNG JALAN otomatis setelah Loading & Unloading selesai!
                    if mc_dur > 0:
                        mc_states[m]["is_running"] = True
                        mc_states[m]["curr_act"] = mc_step_name
                        mc_states[m]["free_at"] = op_free_at + mc_dur

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
