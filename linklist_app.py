import streamlit as st
import pandas as pd
import re
import os
from io import BytesIO
import time

st.set_page_config(page_title="Rex2Fusion Linklist Tool", layout="wide")

st.title("🔗 Rex2Fusion Linklist Processor")
st.write("Enter settings, upload your file, and download the converted Excel workbooks.")

# --- SETTINGS UI ---
with st.sidebar:
    st.header("Settings")
    linklist_start_number = st.number_input("Linklist Start Number", min_value=1, value=50, step=1)

# --- FILE UPLOADER ---
uploaded_file = st.file_uploader("Upload your source file", type=['csv','txt', 'log', 'dat'])

def process_linklist(file_content, start_no):
    # --- PART A: ROBUST READING ---
    try:
        content = file_content.decode('utf-8-sig', errors='ignore')
    except:
        content = file_content.decode('latin-1', errors='ignore')

    content = content.replace('\x00', '')
    lines = content.splitlines()

    # --- PART B: PARSE DATA ---
    collections = []
    unit_map = {}
    parsed_collections = []
    processing_id = start_no

    name_pattern = re.compile(r"^#([^;]+)")
    code_pattern = re.compile(r"#([^\[;#]+)\[([\d\.,]+)\]")

    for line in lines:
        line = line.strip()
        if not line: continue

        if line.startswith("#"):
            name_match = name_pattern.search(line)
            coll_name = name_match.group(1).strip() if name_match else line.split(";")[0].replace("#", "").strip()
            found_codes = code_pattern.findall(line)
            coll_units = []

            for code, qty_str in found_codes:
                qty_str = qty_str.replace(",", ".")
                try:
                    qty = float(qty_str)
                    loop_count = int(qty) if qty.is_integer() else 1
                except:
                    loop_count = 1

                for _ in range(loop_count):
                    collections.append({
                        "Linklist ID": processing_id,
                        "Linklist Name": coll_name,
                        "Linklist Units": code.strip(),
                        "Number of Units": "[1.000]",
                        "Series ID": 0
                    })
                    coll_units.append(code.strip())

            parsed_collections.append({
                "id": processing_id,
                "name": coll_name,
                "units": coll_units
            })
            processing_id += 1

        elif line.startswith(";#"):
            unit_name = line.replace(";", "").replace("#", "").strip()
            if unit_name:
                active_id = processing_id - 1
                if unit_name not in unit_map: unit_map[unit_name] = []
                unit_map[unit_name].append(active_id)

    # --- PART C: GENERATE DF1 ---
    df1 = pd.DataFrame(collections)
    unit_data_list = []
    for u_name, id_list in unit_map.items():
        link_str = "<" + "|".join([f"{idx+1}~1~{linked_id}" for idx, linked_id in enumerate(id_list)]) + "|>"
        unit_data_list.append({"Unit Name": u_name, "Linked Lists": link_str})
    
    df1_units = pd.DataFrame(unit_data_list)
    df1_final = pd.concat([df1.reset_index(drop=True), df1_units.reset_index(drop=True)], axis=1).fillna("")

    # --- PART D: GENERATE DF2 ---
    static_vals = {
        "Add OR Delete": "A", "Series ID": 0, "Catalogue ID": 0, "Use Unit Dims": True,
        "UDX": 0, "UDY": 0, "UDZ": 0, "Use Unit Cursor Moves": True,
        "PREDISTX:": 0, "PREMETHODX:": "SpecifiedDist", "PREDISTY:": 0, "PREMETHODY:": "SpecifiedDist",
        "PREDISTZ:": 0, "PREMETHODZ:": "SpecifiedDist", "PREROT:": 0, "POSTDISTX:": 0,
        "POSTMETHOSX:": "UnitDistPos", "POSTDISTY:": 0, "POSTMETHODSTY:": "SpecifiedDist",
        "POSTDISTZ:": 0, "POSTMETHODZ:": "SpecifiedDist", "POSTROT": 0,
        "Clash With Parent": False, "Handing": "None", "Status": "Compulsory",
        "Lock Linked Unit Attributes": True
    }

    tab2_rows = []
    for col_data in parsed_collections:
        for i, u_code in enumerate(col_data["units"]):
            row = static_vals.copy()
            row.update({"Link List ID": col_data["id"], "Link List Name": col_data["name"], "Unit Number": i + 1, "UnitName": u_code})
            tab2_rows.append(row)
    
    df2_final = pd.DataFrame(tab2_rows)
    return df1_final, df2_final

if uploaded_file:
    if st.button("🚀 Process Linklist"):
        with st.spinner("Processing data..."):
            df1, df2 = process_linklist(uploaded_file.read(), linklist_start_number)
            
            # Create download buffers
            buf1 = BytesIO()
            buf2 = BytesIO()
            
            with pd.ExcelWriter(buf1, engine='xlsxwriter') as writer:
                df1.to_excel(writer, index=False)
            with pd.ExcelWriter(buf2, engine='xlsxwriter') as writer:
                df2.to_excel(writer, index=False)
            
            st.success("✅ Files generated successfully!")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button("📥 CopyLinklist.xlsx", data=buf1.getvalue(), file_name="CopyLinklist.xlsx")
            with col_b:
                st.download_button("📥 Import_Linklist.xlsx", data=buf2.getvalue(), file_name="Import_Linklist.xlsx")