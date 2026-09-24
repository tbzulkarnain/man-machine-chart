import pandas as pd

def generate_correct_mmc(num_machines, num_cycles, process_list):
    """
    process_list contoh:
    [
        {"Proses": "Placing component", "Cycle Time (s)": 43.3, "Aktor": "Both"}, # Atau Man/Both
        {"Proses": "hot press", "Cycle Time (s)": 160.0, "Aktor": "Machine"},
        {"Proses": "take result", "Cycle Time (s)": 9.0, "Aktor": "Both"}
    ]
    """
    # Dapatkan durasi elemen proses
    place_time = next(p["Cycle Time (s)"] for p in process_list if "Placing" in p["Proses"] or p["Aktor"] in ["Man", "Both"])
    press_time = next(p["Cycle Time (s)"] for p in process_list if "press" in p["Proses"].lower() or p["Aktor"] == "Machine")
    take_time = next(p["Cycle Time (s)"] for p in process_list if "take" in p["Proses"].lower() or "Unloading" in p["Proses"])

    # State Mesin: status ('idle_empty', 'loading', 'pressing', 'finished_waiting_unload', 'unloading')
    # State Operator: available_time
    machines = [{"id": i+1, "status": "idle_empty", "next_free_time": 0.0, "cycle_count": 0} for i in range(num_machines)]
    
    current_time = 0.0
    op_free_time = 0.0
    timeline = []

    # Eksekusi simulasi sampai semua mesin menyelesaikan jumlah siklus
    while any(m["cycle_count"] < num_cycles for m in machines):
        
        # 1. Cari aksi terbaik untuk operator pada current_time / op_free_time
        # Prioritas A: Unload Mesin yang sudah selesai press
        m_to_unload = None
        for m in machines:
            if m["status"] == "finished_waiting_unload" and m["cycle_count"] < num_cycles:
                m_to_unload = m
                break
        
        # Prioritas B: Load Mesin yang masih kosong/idle
        m_to_load = None
        if not m_to_unload:
            for m in machines:
                if m["status"] == "idle_empty" and m["cycle_count"] < num_cycles:
                    m_to_load = m
                    break
                    
        # Jika ada yang bisa di-Unload oleh Operator
        if m_to_unload:
            start_t = max(op_free_time, m_to_unload["next_free_time"])
            duration = take_time
            end_t = start_t + duration
            
            # Catat log event
            op_free_time = end_t
            m_to_unload["status"] = "idle_empty"
            m_to_unload["cycle_count"] += 1
            m_to_unload["next_free_time"] = end_t
            
        # Jika ada yang bisa di-Load oleh Operator
        elif m_to_load:
            start_t = op_free_time
            duration = place_time
            end_t = start_t + duration
            
            op_free_time = end_t
            m_to_load["status"] = "pressing"
            # Mesin mulai pressing tepat setelah di-load
            m_to_load["next_free_time"] = end_t + press_time 
            
        else:
            # Jika semua mesin sedang pressing, operator IDLE sampai mesin pertama selesai pressing
            next_event_time = min(m["next_free_time"] for m in machines if m["status"] == "pressing")
            if next_event_time > op_free_time:
                op_free_time = next_event_time
            
            # Update status mesin yang selesai pressing
            for m in machines:
                if m["status"] == "pressing" and m["next_free_time"] <= op_free_time:
                    m["status"] = "finished_waiting_unload"

    # [Bagian ini memformat hasil simulasi ke dalam DataFrame tabel MMC seperti yang kamu tampilkan di UI]
    # ...
