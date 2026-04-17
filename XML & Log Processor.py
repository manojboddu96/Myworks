import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO
import re

st.set_page_config(page_title="XML & Log Processor", layout="wide")
st.title("📂 XML and IDMLog Data Processor")

# --- UI: FILE UPLOADERS ---
col1, col2 = st.columns(2)
with col1:
    xml_upload = st.file_uploader("Upload XML File", type=['xml'])
with col2:
    log_upload = st.file_uploader("Upload Log/Text File", type=['txt', 'log'])

# --- REFINED LOG PARSING LOGIC ---
def parse_log_section_advanced(content, start_marker, end_marker, column_markers):
    """
    Parses sections using multiple markers to ensure correct column splitting .
    """
    lines = content.splitlines()
    record = False
    extracted_data = []
    
    for line in lines:
        if start_marker in line:
            record = True
            continue
        if record and "****************" in line:
            record = False
            break
        
        if record and line.strip():
            # Extract the leading Sr_No (e.g., '1)')
            sr_no_match = re.match(r'^(\d+)\)', line)
            sr_no = sr_no_match.group(1) if sr_no_match else ""
            
            row = {"Sr_No": sr_no}
            # Extract data between markers
            for i, marker in enumerate(column_markers):
                start_ptr = line.find(marker)
                if start_ptr != -1:
                    start_ptr += len(marker)
                    # Find where the next marker starts to determine the end of current value
                    end_ptr = len(line)
                    if i + 1 < len(column_markers):
                        next_marker_pos = line.find(column_markers[i+1])
                        if next_marker_pos != -1:
                            end_ptr = next_marker_pos
                    
                    val = line[start_ptr:end_ptr].strip()
                    # Clean up trailing separators if any
                    if val.endswith(':') or val.endswith(')'):
                        val = val[:-1].strip()
                    row[marker.replace('[','').replace(']','').replace(':','').strip()] = val
            
            if len(row) > 1:
                extracted_data.append(row)
                
    return pd.DataFrame(extracted_data)

# --- XML EXPORT LOGIC ---
def get_xml_deep_export(xml_content):
    root = ET.fromstring(xml_content)
    u_info, m_price, a_price, restr_tab, min_p = [], [], [], [], []

    for serie in root.findall('.//SERIE'):
        s_no = serie.get('SERIE_NO')
        for item in serie.findall('.//ITEM'):
            u_name = item.get('TYPE_NO')
            width = depth = height = "0"
            for param in item.findall('.//BASIC_SHAPE_PARAMETER'):
                name = param.get('BASIC_SHAPE_NAME', '').lower()
                val = param.get('BASIC_SHAPE_NOMINAL_VALUE', '0')
                if name == 'b': width = val
                elif name == 'h': height = val
                elif name == 't': depth = val

            u_info.append({
                "SERIE_NO": s_no, "TYPE_NO": u_name, "Width": width, "Depth": depth, "Height": height,
                "EDP_NUMBER": item.findtext('.//EDP_NUMBER') or "",
                "EAN_NUMBER": item.findtext('.//EAN_NUMBER') or "",
                "WEIGHT": item.findtext('.//WEIGHT') or "",
                "VOLUME": item.findtext('.//VOLUME') or "",
                "CONSTRUCTION_ID": item.findtext('.//CONSTRUCTION_ID') or "",
                "CLASSIFICATION_CODE": "|".join([c.findtext('CLASSIFICATION_CODE') for c in item.findall('.//CLASSIFICATION') if c.findtext('CLASSIFICATION_CODE')])
            })

            for group in item:
                if "PRICE_GROUP" in group.tag or "PRICE_FEATURE_GROUP" in group.tag:
                    group_ref = group.find('.//PRICE_FEATURE_GROUP_REF')
                    group_no = group.get('PRICE_FEATURE_GROUP_NO') or (group_ref.get('PRICE_FEATURE_GROUP_NO') if group_ref is not None else None)
                    is_additional = "ADDITIONAL" in group.tag.upper()
                    
                    for item_p in group.findall('.//ITEM_PRICE'):
                        p_data = {
                            "SERIE_NO": s_no, "TYPE_NO": u_name, "PRICE_FEATURE_GROUP_NO": group_no,
                            "PRICE_FIELD": item_p.findtext('PRICE_FIELD'), "PRICE": item_p.findtext('PRICE'),
                            "PRICE_TYPE_NO": group.get('PRICE_TYPE_NO') or "1"
                        }
                        if is_additional: a_price.append(p_data)
                        elif p_data["PRICE_TYPE_NO"] == "1": m_price.append(p_data)
                        else: a_price.append(p_data)

                        min_basic = item_p.findtext('PRICE_MINIMUM_BASIC')
                        if min_basic:
                            min_p.append({**p_data, "PRICE_MINIMUM_BASIC": min_basic, "BASIC_PRICE_UNIT": item_p.findtext('BASIC_PRICE_UNIT')})

            for r_cont in item.findall('.//RESTRICTIONS'):
                for r_ref in r_cont.findall('.//RESTRICTION_REF'):
                    restr_tab.append({"SERIE_NO": s_no, "TYPE_NO": u_name, "RESTRICTION_NO": r_ref.get('RESTRICTION_NO')})

    return {"Unit Info": pd.DataFrame(u_info), "Main Price": pd.DataFrame(m_price), "Additional Price": pd.DataFrame(a_price), "RESTRICTIONS": pd.DataFrame(restr_tab), "Minimum Price": pd.DataFrame(min_p)}

# --- UI EXECUTION ---
if xml_upload:
    st.subheader("🛠️ Option 1: XML Deep Export")
    if st.button("📊 Generate XML Export Excel"):
        xml_bytes = xml_upload.getvalue().decode("utf-8")
        sheets = get_xml_deep_export(xml_bytes)
        out = BytesIO()
        with pd.ExcelWriter(out, engine='xlsxwriter') as writer:
            for name, df in sheets.items(): df.to_excel(writer, sheet_name=name, index=False)
        st.download_button("📥 Download XML Export", out.getvalue(), "XML_Export.xlsx")

if xml_upload and log_upload:
    st.divider()
    st.subheader("🛠️ Option 2: IDM Log File Split")
    if st.button("🚀 Process Log Split"):
        xml_content = xml_upload.getvalue().decode("utf-8")
        log_content = log_upload.getvalue().decode("utf-8", errors="ignore")
        
        # XML for basic info
        root = ET.fromstring(xml_content)
        u_rows = [{"Series No": s.get('SERIE_NO'), "Product Code": i.get('TYPE_NO')} for s in root.findall('.//SERIE') for i in s.findall('.//ITEM')]
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pd.DataFrame(log_content.splitlines(), columns=["Raw Log Data"]).to_excel(writer, sheet_name='IDMLog', index=False)
            pd.DataFrame(u_rows).to_excel(writer, sheet_name='Unit Info', index=False)

            # Updated Section Parsers based on file analysis [cite: 70718, 70737, 61470, 63850, 65410]
            parse_log_section_advanced(log_content, "new products Added in Catalog", "*****", ["[Product Code]", "[Product Description]"]).to_excel(writer, sheet_name='NewProduct', index=False)
            parse_log_section_advanced(log_content, "products deleted from catalog", "*****", ["[Series]", "[Unit Name]", "[Order Code]", "[Description]"]).to_excel(writer, sheet_name='DeletedProduct', index=False)
            parse_log_section_advanced(log_content, "products usercode value  updated", "*****", ["[Old Usercode]", "[New UserCode]"]).to_excel(writer, sheet_name='CodeUpdated', index=False)
            parse_log_section_advanced(log_content, "new options Added in Catalog", "*****", ["[Feature Code]", "[Feature Description]", "[Option Code]", "[Option Description]"]).to_excel(writer, sheet_name='NewOptions', index=False)
            parse_log_section_advanced(log_content, "Added  new addon(s)", "*****", ["[UnitName]", "[Addons]"]).to_excel(writer, sheet_name='AddonsAddedToUnits', index=False)
            parse_log_section_advanced(log_content, "New Linkref Added on folllowing Products", "*****", ["[UnitName]", "[LinkRef]"]).to_excel(writer, sheet_name='LinkListAddedToUnit', index=False)

        st.success("✅ Log split completed!")
        st.download_button("📥 Download Final Worksheet", output.getvalue(), "Log_Split_Result.xlsx")