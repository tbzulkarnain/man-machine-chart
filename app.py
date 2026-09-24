def run_universal_mmc(df_steps, n_mc, n_cycles):
    steps = df_steps.to_dict('records')
    
    # Inisialisasi State
    op_free_at = 0.0
    mc_states = {m: {"free_at": 0.0, "step_idx": 0, "cycle": 0, "curr_act": "waiting"} for m in range(1, n_mc + 1)}
    
    # Event Log
    events = []
    
    # Loop Simulasi
    while any(mc_states[m]["cycle"] < n_cycles for m in range(1, n_mc + 1)):
        candidates = []
        for m in range(1, n_mc + 1):
            if mc_states[m]["cycle"] >= n_cycles:
                continue
            
            idx = mc_states[m]["step_idx"]
            step = steps[idx]
            
            if step["Aktor"] in ["Man", "Both"]:
                ready_time = max(op_free_at, mc_states[m]["free_at"])
                candidates.append({
                    "mc_id": m,
                    "ready_time": ready_time,
                    "step_idx": idx,
                    "step": step
                })
        
        if candidates:
            # Pilih candidate dengan waktu paling awal
            candidates.sort(key=lambda x: (x["ready_time"], x["mc_id"]))
            chosen = candidates[0]
            
            m = chosen["mc_id"]
            step = chosen["step"]
            start_t = chosen["ready_time"]
            
            # PERBAIKAN: Menggunakan op_free_at secara konsisten
            if start_t > op_free_at:
                events.append({
                    "start": op_free_at,
                    "end": start_t,
                    "op_act": "idle",
                    "mc_acts": {i: "waiting" if mc_states[i]["free_at"] <= op_free_at else mc_states[i]["curr_act"] for i in range(1, n_mc + 1)}
                })
            
            end_t = start_t + float(step["Cycle Time (s)"])
            
            # Catat aktivitas
            mc_acts_snapshot = {}
            for i in range(1, n_mc + 1):
                if i == m:
                    mc_acts_snapshot[i] = step["Proses"]
                else:
                    mc_acts_snapshot[i] = mc_states[i]["curr_act"] if mc_states[i]["free_at"] > start_t else "waiting"
            
            events.append({
                "start": start_t,
                "end": end_t,
                "op_act": f"{step['Proses']} MC {m}",
                "mc_acts": mc_acts_snapshot
            })
            
            # Update State
            op_free_at = end_t
            mc_states[m]["free_at"] = end_t
            mc_states[m]["curr_act"] = step["Proses"]
            
            # Advance step
            mc_states[m]["step_idx"] += 1
            if mc_states[m]["step_idx"] >= len(steps):
                mc_states[m]["step_idx"] = 0
                mc_states[m]["cycle"] += 1
                
            # Jika step berikutnya adalah "Machine" murni, langsung trigger otomatis
            if mc_states[m]["cycle"] < n_cycles:
                next_idx = mc_states[m]["step_idx"]
                next_step = steps[next_idx]
                if next_step["Aktor"] == "Machine":
                    mc_states[m]["curr_act"] = next_step["Proses"]
                    mc_states[m]["free_at"] = end_t + float(next_step["Cycle Time (s)"])
                    mc_states[m]["step_idx"] += 1
                    if mc_states[m]["step_idx"] >= len(steps):
                        mc_states[m]["step_idx"] = 0
                        mc_states[m]["cycle"] += 1
        else:
            active_mcs = [mc_states[i]["free_at"] for i in range(1, n_mc + 1) if mc_states[i]["cycle"] < n_cycles]
            if not active_mcs:
                break
            next_mc_finish = min(active_mcs)
            if next_mc_finish > op_free_at:
                mc_acts_snapshot = {}
                for i in range(1, n_mc + 1):
                    mc_acts_snapshot[i] = mc_states[i]["curr_act"] if mc_states[i]["free_at"] > op_free_at else "waiting"
                
                events.append({
                    "start": op_free_at,
                    "end": next_mc_finish,
                    "op_act": "idle",
                    "mc_acts": mc_acts_snapshot
                })
                op_free_at = next_mc_finish

    # Format ke DataFrame
    rows = []
    for ev in events:
        dur = round(ev["end"] - ev["start"], 2)
        r = {
            "Time (s)": round(ev["end"], 2),
            "Operator Activity": ev["op_act"],
            "Op Time": dur
        }
        for m in range(1, n_mc + 1):
            r[f"MC {m} Activity"] = ev["mc_acts"].get(m, "waiting")
            r[f"MC {m} Time"] = dur
        rows.append(r)
        
    return pd.DataFrame(rows)
