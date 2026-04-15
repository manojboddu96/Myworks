import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(page_title="XML & Log Processor", layout="wide")

st.title("📂 XML and IDMLog Data Processor")
st.write("Upload your files below to generate the Final Data Worksheet exactly like the Excel Macro.")

# --- UI: FILE UPLOADERS ---
col1, col2 = st.columns(2)
with col1:
    xml_upload = st.file_uploader("Upload XML File", type=['xml'])
with col2:
    log_upload = st.file_uploader("Upload Log/File (IDMLog.txt)", type=['txt', 'log'])

def parse_log_section(content, start_marker, end_marker, replacements, columns, delimiter=']'):
    """Replicates VBA Do-Loop, Replace, and Split logic [cite: 25-30, 94-95]."""
    extracted_lines = []
    record = False
    for line in content.splitlines():
        if start_marker in line:
            record = True
            continue
        if end_marker in line and record:
            record = False
            break
        if record and line.strip():
            clean_line = line.strip()
            for old, new in replacements.items():
                clean_line = clean_line.replace(old, new)
            extracted_lines.append(clean_line)
    
    if not extracted_lines: return pd.DataFrame(columns=columns)
    data = [line.split(delimiter) for line in extracted_lines]
    df = pd.DataFrame(data)
    actual_count = df.shape[1]
    header_list = columns[:actual_count]
    if actual_count > len(columns):
        for i in range(len(columns), actual_count):
            header_list.append(f"Extra_Col_{i+1}")
    df.columns = header_list
    return df

def process_xml_data(xml_content):
    """Replicates Power Query steps for Unit Info and Series ID [cite: 6-11, 14-16]."""
    root = ET.fromstring(xml_content)
    unit_rows, series_rows = [], []
    for serie in root.findall('.//SERIE'):
        s_no = serie.get('SERIE_NO')
        s_name = serie.findtext('.//TEXT') or ""
        series_rows.append({"Series No": s_no, "Series Name": s_name})
        for item in serie.findall('.//ITEM'):
            p_code = item.get('TYPE_NO')
            dims = [p.get('BASIC_SHAPE_NOMINAL_VALUE', '0') for p in item.findall('.//BASIC_SHAPE_PARAMETER')]
            unit_rows.append({
                "Series No": s_no, "Product Code": p_code,
                "ConSNO_PCode": f"{s_no}_{p_code}",
                "Width": dims[0] if len(dims) > 0 else 0,
                "Depth": dims[1] if len(dims) > 1 else 0,
                "Height": dims[2] if len(dims) > 2 else 0
            })
    return pd.DataFrame(unit_rows), pd.DataFrame(series_rows)

if xml_upload and log_upload:
    if st.button("🚀 Process and Generate Excel"):
        try:
            xml_content = xml_upload.read().decode("utf-8")
            log_content = log_upload.read().decode("utf-8", errors="ignore")
            
            df_units, df_series_id = process_xml_data(xml_content)
            df_raw_log = pd.DataFrame(log_content.splitlines(), columns=["Raw Log Data"])

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # 1. XML TABS
                df_raw_log.to_excel(writer, sheet_name='IDMLog', index=False)
                df_units.to_excel(writer, sheet_name='Unit Info', index=False)
                df_series_id.to_excel(writer, sheet_name='Series ID Info', index=False)

                # 2. PRODUCT TABS [cite: 26-43]
                parse_log_section(log_content, "new products Added in Catalog", "*****", 
                    {"[Product Description": "", ")[Product Code": ""}, 
                    ["Sr_No", "Series ID", "Product Code", "Description"]).to_excel(writer, sheet_name='NewProduct', index=False)
                
                parse_log_section(log_content, "products deleted from catalog", "*****", 
                    {")[Series": "", ": [Unit Name": "", " :[Order Code": "", ":[Description": ""}, 
                    ["Sr_No", "Series No", "Product Code", "Order Code", "Description"]).to_excel(writer, sheet_name='DeletedProduct', index=False)
                    
                parse_log_section(log_content, "usercode value  updated", "*****", 
                    {") [Old Usercode": "", " [New UserCode": ""}, 
                    ["Sr_No", "Old Product Code", "New Product Code", "Old Order Code", "New Order Code"]).to_excel(writer, sheet_name='CodeUpdated', index=False)

                # 3. OPTIONS & FEATURES [cite: 44-55]
                parse_log_section(log_content, "new options Added in Catalog", "*****", 
                    {")[Feature Code": "", " [Feature Description": "", "[Option Code": "", " [Option Description": ""},
                    ["Sr_No", "Type ID", "Feature Code", "Feature Description", "Option Code", "Entry ID", "Option Description"]).to_excel(writer, sheet_name='NewOptions', index=False)

                parse_log_section(log_content, "new Features Added in Catalog", "*****", 
                    {") [Feature Code": "", "[Feature Description": ""},
                    ["Sr_No", "Type ID", "Feature Code/Order Code", "Feature Description/Type Name"]).to_excel(writer, sheet_name='NewFeatures', index=False)

                # 4. LINKS & ADDONS [cite: 56-61, 79-95]
                parse_log_section(log_content, "New Linkref Added on folllowing Products", "*****", 
                    {") [UnitName": "", " [LinkRef": ""}, ["Sr_No", "Unit Name", "Linkref Added"]).to_excel(writer, sheet_name='LinkListAddedToUnit', index=False)

                parse_log_section(log_content, "New LinkList Added in Catalog", "*****", 
                    {}, ["Sr_No", "Linkref Added", "Link List Name"], delimiter=")").to_excel(writer, sheet_name='LinkListAddedInLinks', index=False)

                parse_log_section(log_content, "Added  new addon(s)", "*****", 
                    {") [UnitName": "", "[Addons": ""}, ["Sr_No", "Unit Name", "Addons Added"]).to_excel(writer, sheet_name='AddonsAddedToUnits', index=False)

                # 5. MATERIALS [cite: 96-108]
                parse_log_section(log_content, "new colorString Added", "*****", 
                    {")Id ": "", "  Sort Order ": "", "   Material ID": "", ":": ""},
                    ["Sr_No", "ID", "Sort Code", "Description", "Material ID"]).to_excel(writer, sheet_name='NewColorStringAdded', index=False)

            st.success("✅ Success! Your file is ready.")
            st.download_button(label="📥 Download Final Data Worksheet", data=output.getvalue(), file_name="Final_Data_Worksheet.xlsx", mime="application/vnd.ms-excel")
        except Exception as e:
            st.error(f"Processing Error: {e}")