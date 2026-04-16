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

# --- HELPER FUNCTIONS: XML DEEP EXPORT ---
def get_xml_deep_export(xml_content):
    root = ET.fromstring(xml_content)
    u_info, m_price, a_price, restr_tab, min_p = [], [], [], [], []

    for serie in root.findall('.//SERIE'):
        s_no = serie.get('SERIE_NO')
        for item in serie.findall('.//ITEM'):
            u_name = item.get('TYPE_NO')
            
            # 1. Unit Info Tab - Added CLASSIFICATION_CODE
            dims = [p.get('BASIC_SHAPE_NOMINAL_VALUE', '0') for p in item.findall('.//BASIC_SHAPE_PARAMETER')]
            u_info.append({
                "SERIE_NO": s_no,
                "TYPE_NO": u_name,
                "Width": dims[0] if len(dims) > 0 else 0,
                "Depth": dims[1] if len(dims) > 1 else 0,
                "Height": dims[2] if len(dims) > 2 else 0,
                "EDP_NUMBER": item.findtext('EDP_NUMBER'),
                "EAN_NUMBER": item.findtext('EAN_NUMBER'),
                "WEIGHT": item.findtext('WEIGHT'),
                "VOLUME": item.findtext('VOLUME'),
                "CONSTRUCTION_ID": item.findtext('CONSTRUCTION_ID'),
                "CLASSIFICATIONS": "|".join([c.text for c in item.findall('.//CLASSIFICATION') if c.text]),
                "CLASSIFICATION_CODE": "|".join([c.get('CLASSIFICATION_CODE', '') for c in item.findall('.//CLASSIFICATION')])
            })

            # 2. Prices - Deep Nesting Logic
            # Main and Additional Price usually under PRICE_FEATURE_GROUP_REF
            for p_ref in item.findall('.//PRICE_FEATURE_GROUP_REF'):
                for price_node in p_ref.findall('.//PRICE'):
                    p_data = {
                        "SERIE_NO": s_no,
                        "TYPE_NO": u_name,
                        "PRICE_FEATURE_GROUP_NO": p_ref.get('PRICE_FEATURE_GROUP_NO'),
                        "PRICE_FIELD": price_node.get('PRICE_FIELD'),
                        "PRICE": price_node.text,
                        "PRICE_TYPE_NO": price_node.get('PRICE_TYPE_NO')
                    }
                    if p_data["PRICE_TYPE_NO"] == "1":
                        m_price.append(p_data)
                    else:
                        a_price.append(p_data)

            # Minimum Price - Under PRICE_FEATURE_GROUP_BASE_PRICE_REF
            for p_base in item.findall('.//PRICE_FEATURE_GROUP_BASE_PRICE_REF'):
                for item_p in p_base.findall('.//ITEM_PRICE'):
                    for price_n in item_p.findall('.//PRICE'):
                        min_p.append({
                            "SERIE_NO": s_no,
                            "TYPE_NO": u_name,
                            "ITEM_PRICE": item_p.get('ITEM_PRICE_NO'),
                            "PRICE_FIELD": price_n.get('PRICE_FIELD'),
                            "PRICE": price_n.text,
                            "PRICE_MINIMUM_BASIC": price_n.get('PRICE_MINIMUM_BASIC'),
                            "BASIC_PRICE_UNIT": price_n.get('BASIC_PRICE_UNIT')
                        })

            # 3. RESTRICTIONS - Under RESTRICTION_REF
            for r_ref in item.findall('.//RESTRICTION_REF'):
                for r_node in r_ref.findall('.//RESTRICTION'):
                    restr_tab.append({
                        "SERIE_NO": s_no,
                        "TYPE_NO": u_name,
                        "RESTRICTION_NO": r_node.get('RESTRICTION_NO')
                    })

    return {
        "Unit Info": pd.DataFrame(u_info),
        "Main Price": pd.DataFrame(m_price),
        "Additional Price": pd.DataFrame(a_price),
        "RESTRICTIONS": pd.DataFrame(restr_tab),
        "Minimum Price": pd.DataFrame(min_p)
    }

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
        except Exception as e:
            st.error(f"XML Export Error: {e}")

if xml_upload and log_upload:
    st.divider()
    st.subheader("🛠️ Option 2: IDM Log File Split")
    if st.button("🚀 Process Log Split"):
        try:
            xml_content = xml_upload.getvalue().decode("utf-8")
            log_content = log_upload.getvalue().decode("utf-8", errors="ignore")
            
            root = ET.fromstring(xml_content)
            unit_rows, series_rows = [], []
            for serie in root.findall('.//SERIE'):
                s_no = serie.get('SERIE_NO')
                series_rows.append({"Series No": s_no, "Series Name": serie.findtext('.//TEXT') or ""})
                for item in serie.findall('.//ITEM'):
                    p_code = item.get('TYPE_NO')
                    dims = [p.get('BASIC_SHAPE_NOMINAL_VALUE', '0') for p in item.findall('.//BASIC_SHAPE_PARAMETER')]
                    unit_rows.append({"Series No": s_no, "Product Code": p_code, "ConSNO_PCode": f"{s_no}_{p_code}", "Width": dims[0] if len(dims)>0 else 0, "Depth": dims[1] if len(dims)>1 else 0, "Height": dims[2] if len(dims)>2 else 0})

            df_units, df_series = pd.DataFrame(unit_rows), pd.DataFrame(series_rows)
            df_raw_log = pd.DataFrame(log_content.splitlines(), columns=["Raw Log Data"])
            
            out_log = BytesIO()
            with pd.ExcelWriter(out_log, engine='xlsxwriter') as writer:
                df_raw_log.to_excel(writer, sheet_name='IDMLog', index=False)
                df_units.to_excel(writer, sheet_name='Unit Info', index=False)
                df_series.to_excel(writer, sheet_name='Series ID Info', index=False)
                
                # Tab Splitting
                parse_log_section(log_content, "new products Added", "*****", {"[Product Description": ""}, ["Sr_No", "Series", "Code", "Desc"]).to_excel(writer, sheet_name='NewProduct', index=False)
                parse_log_section(log_content, "products deleted", "*****", {":[Order Code": ""}, ["Sr_No", "Series", "Code", "Order", "Desc"]).to_excel(writer, sheet_name='DeletedProduct', index=False)
                parse_log_section(log_content, "usercode updated", "*****", {}, ["Sr_No", "Old_P", "New_P", "Old_O", "New_O"]).to_excel(writer, sheet_name='CodeUpdated', index=False)
                parse_log_section(log_content, "new options Added", "*****", {}, ["Sr_No", "Type", "F_Code", "F_Desc", "O_Code", "ID", "O_Desc"]).to_excel(writer, sheet_name='NewOptions', index=False)
                parse_log_section(log_content, "new Features Added", "*****", {}, ["Sr_No", "Type", "F_Code", "F_Desc"]).to_excel(writer, sheet_name='NewFeatures', index=False)
                parse_log_section(log_content, "New Linkref Added", "*****", {}, ["Sr_No", "Unit", "Link"]).to_excel(writer, sheet_name='LinkListAddedToUnit', index=False)
                parse_log_section(log_content, "New LinkList Added", "*****", {}, ["Sr_No", "Link", "Name"], delimiter=")").to_excel(writer, sheet_name='LinkListAddedInLinks', index=False)
                parse_log_section(log_content, "Added  new addon", "*****", {}, ["Sr_No", "Unit", "Addon"]).to_excel(writer, sheet_name='AddonsAddedToUnits', index=False)

            st.success("✅ Log split processed!")
            st.download_button("📥 Download Final Data Worksheet", out_log.getvalue(), "Final_Data_Worksheet.xlsx")
        except Exception as e:
            st.error(f"Log Split Error: {e}")