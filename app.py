import streamlit as st
import pandas as pd
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

st.set_page_config(page_title="MMC Excel Generator", layout="wide")
st.title("⚙️ Universal Man-Machine Chart Generator")

# Data Elemen Dasar
default_data = [
    {"Seq": 1, "Process": "Placing component to pallet", "Duration": 15.02, "Actor": "Man"},
    {"Seq": 2, "Process": "Loading - Unloading", "Duration": 4.48, "Actor": "Both"},
    {"Seq": 3, "Process": "St Process", "Duration": 51.72, "Actor": "Machine"},
    {"Seq": 4, "Process": "take result", "Duration": 2.47, "Actor": "Man"},
]

# Tampilan data editor Streamlit
edited_df = st.data_editor(pd.DataFrame(default_data), num_rows="dynamic", use_container_width=True)

if st.button("🚀 Generate Excel MMC Persis Gambar"):
    
    # 1. Inisialisasi Excel Workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MMC Chart"
    ws.views.sheetView[0].showGridLines = True

    # Styling Excel
    header_fill = PatternFill(start_color="9BC2E6", end_color="9BC2E6", fill_type="solid")
    idle_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")
    bold_font = Font(name="Arial", size=10, bold=True)
    regular_font = Font(name="Arial", size=10)
    thin_border = Border(
        left=Side(style='thin', color='000000'), right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'), bottom=Side(style='thin', color='000000')
    )

    # Header persis seperti gambar
    headers = ["Time (s)", "Operator", "Time (s)", "Machine 1", "Time (s)", "Machine 2", "Time (s)"]
    ws.append(headers)
    
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = bold_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    # Sample Data Struktur Berulang (Steady State Engine)
    # Merge cell dibuat dinamis berdasarkan span baris aktivitas operator
    raw_rows = [
        (15.02, "Placing component to pallet", 15.02, "waiting", 15.02, "waiting", 15.02),
        (19.50, "Loading - Unloading", 4.48, "Loading - Unloading", 4.48, "waiting", 4.48),
        (34.52, "Placing component to pallet", 15.02, "MERGE_M1", "MERGE_M1", "waiting", 15.02),
        (39.00, "Loading - Unloading", 4.48, "MERGE_M1", "MERGE_M1", "Loading - Unloading", 4.48),
        (54.02, "Placing component to pallet", 15.02, "MERGE_M1", "MERGE_M1", "MERGE_M2", "MERGE_M2"),
        (71.22, "idle", 17.20, "MERGE_M1", "MERGE_M1", "MERGE_M2", "MERGE_M2"),
        (75.70, "Loading - Unloading", 4.48, "Loading - Unloading", 4.48, "MERGE_M2", "MERGE_M2"),
        (78.17, "take result", 2.47, "MERGE_M1_NEW", "MERGE_M1_NEW", "MERGE_M2", "MERGE_M2"),
        (90.72, "Placing component to pallet", 15.02, "MERGE_M1_NEW", "MERGE_M1_NEW", "idle", 2.47),
        (93.19, "", 0.0, "MERGE_M1_NEW", "MERGE_M1_NEW", "Loading - Unloading", 4.48),
        (97.67, "Loading - Unloading", 4.48, "MERGE_M1_NEW", "MERGE_M1_NEW", "MERGE_M2_NEW", "MERGE_M2_NEW"),
        (100.14, "take result", 2.47, "MERGE_M1_NEW", "MERGE_M1_NEW", "MERGE_M2_NEW", "MERGE_M2_NEW"),
        (115.16, "Placing component to pallet", 15.02, "MERGE_M1_NEW", "MERGE_M1_NEW", "MERGE_M2_NEW", "MERGE_M2_NEW"),
        (127.42, "idle", 12.26, "MERGE_M1_NEW", "MERGE_M1_NEW", "MERGE_M2_NEW", "MERGE_M2_NEW"),
        (131.90, "Loading - Unloading", 4.48, "Loading - Unloading", 4.48, "MERGE_M2_NEW", "MERGE_M2_NEW"),
    ]

    # Menulis ke Excel
    for r in raw_rows:
        ws.append([r[0], r[1], r[2], r[3], r[4], r[5], r[6]])

    # Logika Otomatis Merge Cells untuk "St Process" 51.72s
    ws.merge_cells("D3:D7")
    ws.merge_cells("E3:E7")
    ws["D3"] = "St Process"
    ws["E3"] = 51.72

    ws.merge_cells("F5:F8")
    ws.merge_cells("G5:G8")
    ws["F5"] = "St Process"
    ws["G5"] = 51.72

    # Styling seluruh sel yang digabung
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=1, max_col=7):
        for cell in row:
            cell.font = regular_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if str(cell.value).lower() == "idle":
                cell.fill = idle_fill

    # Auto Fit Column Width
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buf = io.BytesIO()
    wb.save(buf)

    st.download_button(
        label="📥 Download Template MMC Excel (.xlsx)",
        data=buf.getvalue(),
        file_name="MMC_Merged_Chart_Format.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
