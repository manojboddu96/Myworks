import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(page_title="XML & Log Processor", layout="wide")

st.title("📂 XML and IDMLog Data Processor")
st.write("Upload your files to generate deep XML data exports or the complete 11-tab log split.")

# --- UI: FILE UPLOADERS ---
col1, col2 = st.columns(2)
with col1:
    xml_upload = st.file_uploader("Upload XML File", type=['xml'])
with col2:
    log_upload = st.file_uploader("Upload Log/Text File", type=['txt', 'log'])

# --- HELPER FUNCTIONS: LOG PARSING ---
def parse_log_section(content, start_marker, end_marker, replacements, columns, delimiter=']'):
    """Replicates VBA logic for parsing sections of the log [cite: 25-43, 94-95]."""
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

# --- HELPER FUNCTIONS: XML PARSING ---
def get_xml_data_for_log(xml_content):
    """Parses Series and Unit info for core log-splitting tabs [cite: 6-16]."""
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

def get_xml_deep_export(xml_content):
    """Parses comprehensive XML data for the full export feature [cite: 6-18]."""
    root = ET.fromstring(xml_content)
    u_info, m_price, a_price, restr, min_p = [], [], [], [], []

    for serie in root.findall('.//SERIE'):
        s_no = serie.get('SERIE_NO')
        for item in serie.findall('.//ITEM'):
            u_name = item.get('TYPE_NO')
            dims = [p.get('BASIC_SHAPE_NOMINAL_VALUE', '0') for p in item.findall('.//BASIC_SHAPE_PARAMETER')]
            u_info.append({
                "Series": s_no, "Unit Name": u_name,
                "Width": dims[0] if len(dims) > 0 else 0,
                "Depth": dims[1] if len(dims) > 1 else 0,
                "Height": dims[2] if len(dims) > 2 else 0,
                "Exchange Number": item.findtext('EXCHANGE_NO'),
                "EAN Number": item.findtext('EAN_NO'),
                "Weight": item.findtext('WEIGHT'),
                "Volume": item.findtext('VOLUME'),
                "Classifications": "|".join([c.text for c in item.findall('.//CLASSIFICATION') if c.text])
            })
            for price in item.findall('.//PRICE'):
                p_data = {"Series": s_no, "Unit Name": u_name, "PRICE_FEATURE_GROUP_NO": price.get('PRICE_FEATURE_GROUP_NO'),
                          "PRICE_FIELD": price.get('PRICE_FIELD'), "PRICE": price.text, "PRICE_TYPE_NO": price.get('PRICE_TYPE_NO')}
                if p_data["PRICE_TYPE_NO"] == "1": m_price.append(p_data)
                else: a_price.append(p_data)
                if price.get('PRICE_MINIMUM_BASIC'):
                    p_min = p_data.copy()
                    p_min.update({"PRICE_MINIMUM_BASIC": price.get('PRICE_MINIMUM_BASIC'), "BASIC_PRICE_UNIT": price.get('BASIC_PRICE_UNIT')})
                    min_p.append(p_min)
            for r in item.findall('.//RESTRICTION'):
                restr.append({"Series": s_no, "Unit Name": u_name, "RESTRICTION_NO": r.get('RESTRICTION_NO')})
    return {"Unit Info": pd.DataFrame(u_info), "Main Price": pd.DataFrame(m_price), "Additional Price": pd.DataFrame(a_price), "RESTRICTIONS": pd.DataFrame(restr), "Minimum Price": pd.DataFrame(min_p)}

# --- EXECUTION LOGIC ---
if xml_upload:
    st.subheader("🛠️ Option 1: XML Deep Export")
    if st.button("📊 Generate XML Export Excel"):
        try:
            xml_content = xml_upload.getvalue().decode("utf-8")
            export_sheets = get_xml_deep_export(xml_content)
            out_xml = BytesIO()
            with pd.ExcelWriter(out_xml, engine='xlsxwriter') as writer:
                for s_name, df in export_sheets.items():
                    df.to_excel(writer, sheet_name=s_name, index=False)
            st.download_button("📥 Download XML Export excel file", out_xml.getvalue(), "XML_Export_Data.xlsx")
        except Exception as e: st.error(f"XML Export Error: {e}")

if xml_upload and log_upload:
    st.divider()
    st.subheader("🛠️ Option 2: IDM Log File Split")
    if st.button("🚀 Process Log Split"):
        try:
            xml_content = xml_upload.getvalue().decode("utf-8")
            log_content = log_upload.getvalue().decode("utf-8", errors="ignore")
            
            df_units, df_series = get_xml_data_for_log(xml_content)
            df_raw_log = pd.DataFrame(log_content.splitlines(), columns=["Raw Log Data"])
            
            out_log = BytesIO()
            with pd.ExcelWriter(out_log, engine='xlsxwriter') as writer:
                # Core Tabs
                df_raw_log.to_excel(writer, sheet_name='IDMLog', index=False)
                df_units.to_excel(writer, sheet_name='Unit Info', index=False)
                df_series.to_excel(writer, sheet_name='Series ID Info', index=False)
                
                # Requested Categorized Log Tabs [cite: 26-108]
                parse_log_section(log_content, "new products Added in Catalog", "*****", {"[Product Description": "", ")[Product Code": ""}, ["Sr_No", "Series ID", "Product Code", "Description"]).to_excel(writer, sheet_name='NewProduct', index=False)
                parse_log_section(log_content, "products deleted from catalog", "*****", {")[Series": "", ": [Unit Name": "", " :[Order Code": "", ":[Description": ""}, ["Sr_No", "Series No", "Product Code", "Order Code", "Description"]).to_excel(writer, sheet_name='DeletedProduct', index=False)
                parse_log_section(log_content, "usercode value  updated", "*****", {") [Old Usercode": "", " [New UserCode": ""}, ["Sr_No", "Old Product Code", "New Product Code", "Old Order Code", "New Order Code"]).to_excel(writer, sheet_name='CodeUpdated', index=False)
                parse_log_section(log_content, "new options Added in Catalog", "*****", {")[Feature Code": "", " [Feature Description": "", "[Option Code": "", " [Option Description": ""}, ["Sr_No", "Type ID", "Feature Code", "Feature Description", "Option Code", "Entry ID", "Option Description"]).to_excel(writer, sheet_name='NewOptions', index=False)
                parse_log_section(log_content, "new Features Added in Catalog", "*****", {") [Feature Code": "", "[Feature Description": ""}, ["Sr_No", "Type ID", "Feature Code/Order Code", "Feature Description/Type Name"]).to_excel(writer, sheet_name='NewFeatures', index=False)
                parse_log_section(log_content, "New Linkref Added on folllowing Products", "*****", {") [UnitName": "", " [LinkRef": ""}, ["Sr_No", "Unit Name", "Linkref Added"]).to_excel(writer, sheet_name='LinkListAddedToUnit', index=False)
                parse_log_section(log_content, "New LinkList Added in Catalog", "*****", {}, ["Sr_No", "Linkref Added", "Link List Name"], delimiter=")").to_excel(writer, sheet_name='LinkListAddedInLinks', index=False)
                parse_log_section(log_content, "Added  new addon(s)", "*****", {") [UnitName": "", "[Addons": ""}, ["Sr_No", "Unit Name", "Addons Added"]).to_excel(writer, sheet_name='AddonsAddedToUnits', index=False)

            st.success("✅ Log split processed!")
            st.download_button("📥 Download Final Data Worksheet", out_log.getvalue(), "Final_Data_Worksheet.xlsx")
        except Exception as e: st.error(f"Log Split Error: {e}")