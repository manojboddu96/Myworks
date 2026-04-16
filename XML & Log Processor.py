import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(page_title="XML & Log Processor", layout="wide")

st.title("📂 XML and IDMLog Data Processor")

# --- UI: FILE UPLOADERS ---
col1, col2 = st.columns(2)
with col1:
    xml_upload = st.file_uploader("Upload XML File", type=['xml'])
with col2:
    log_upload = st.file_uploader("Upload Log/Text File", type=['txt', 'log'])

def get_xml_deep_export(xml_content):
    """Specific parser for IDM nested structure using your provided snippets."""
    root = ET.fromstring(xml_content)
    u_info, m_price, a_price, restr_tab, min_p = [], [], [], [], []

    for serie in root.findall('.//SERIE'):
        s_no = serie.get('SERIE_NO')
        for item in serie.findall('.//ITEM'):
            u_name = item.get('TYPE_NO')
            
            # 1. Unit Info & Classifications
            u_info.append({
                "SERIE_NO": s_no,
                "TYPE_NO": u_name,
                "Width": next((p.get('BASIC_SHAPE_NOMINAL_VALUE') for p in item.findall('.//BASIC_SHAPE_PARAMETER') if p.get('BASIC_SHAPE_PARAMETER_NO') == "1"), "0"),
                "EDP_NUMBER": item.findtext('.//EDP_NUMBER') or "",
                "EAN_NUMBER": item.findtext('.//EAN_NUMBER') or "",
                "WEIGHT": item.findtext('.//WEIGHT') or "",
                "VOLUME": item.findtext('.//VOLUME') or "",
                "CONSTRUCTION_ID": item.findtext('.//CONSTRUCTION_ID') or "",
                "CLASSIFICATION_CODE": "|".join([c.findtext('CLASSIFICATION_CODE') for c in item.findall('.//CLASSIFICATION') if c.findtext('CLASSIFICATION_CODE')])
            })

            # 2. Prices - Logic for ADDITIONAL_PRICE_GROUP / PRICE_FEATURE_GROUP_BASE_PRICE_REF
            # We look for any container that might have price data
            for group in item.findall(".//*"):
                if "PRICE_GROUP" in group.tag or "PRICE_FEATURE_GROUP" in group.tag:
                    # Get group metadata
                    # Some groups have the NO directly, others have it in a REF child
                    group_ref = group.find('.//PRICE_FEATURE_GROUP_REF')
                    group_no = group.get('PRICE_FEATURE_GROUP_NO') or (group_ref.get('PRICE_FEATURE_GROUP_NO') if group_ref is not None else None)
                    
                    # Get price type (Main vs Additional)
                    type_ref = group.find('.//PRICE_TYPE_REF')
                    p_type = group.get('PRICE_TYPE_NO') or (type_ref.get('PRICE_TYPE_NO') if type_ref is not None else "1")
                    
                    # Look for ITEM_PRICE blocks
                    for item_price in group.findall('.//ITEM_PRICE'):
                        field = item_price.findtext('PRICE_FIELD')
                        price_val = item_price.findtext('PRICE')
                        
                        p_data = {
                            "SERIE_NO": s_no,
                            "TYPE_NO": u_name,
                            "PRICE_FEATURE_GROUP_NO": group_no,
                            "PRICE_FIELD": field,
                            "PRICE": price_val,
                            "PRICE_TYPE_NO": p_type
                        }

                        if p_type == "1":
                            m_price.append(p_data)
                        else:
                            a_price.append(p_data)

                        # Minimum Price check
                        min_val = item_price.get('PRICE_MINIMUM_BASIC')
                        if min_val:
                            p_min = p_data.copy()
                            p_min.update({"PRICE_MINIMUM_BASIC": min_val, "BASIC_PRICE_UNIT": item_price.get('BASIC_PRICE_UNIT')})
                            min_p.append(p_min)

            # 3. RESTRICTIONS
            # Looking for RESTRICTION_REF inside RESTRICTIONS tag
            for rest_container in item.findall('.//RESTRICTIONS'):
                for r_ref in rest_container.findall('.//RESTRICTION_REF'):
                    restr_tab.append({
                        "SERIE_NO": s_no,
                        "TYPE_NO": u_name,
                        "RESTRICTION_NO": r_ref.get('RESTRICTION_NO')
                    })

    return {
        "Unit Info": pd.DataFrame(u_info),
        "Main Price": pd.DataFrame(m_price),
        "Additional Price": pd.DataFrame(a_price),
        "RESTRICTIONS": pd.DataFrame(restr_tab),
        "Minimum Price": pd.DataFrame(min_p)
    }

def parse_log_section(content, start_marker, end_marker, replacements, columns, delimiter=']'):
    extracted_lines = []
    record = False
    for line in content.splitlines():
        if start_marker in line: record = True; continue
        if end_marker in line and record: record = False; break
        if record and line.strip():
            clean_line = line.strip()
            for old, new in replacements.items(): clean_line = clean_line.replace(old, new)
            extracted_lines.append(clean_line)
    if not extracted_lines: return pd.DataFrame(columns=columns)
    data = [line.split(delimiter) for line in extracted_lines]
    df = pd.DataFrame(data)
    df.columns = columns[:df.shape[1]]
    return df

# --- UI EXECUTION ---
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
            st.download_button("📥 Download XML Export", out_xml.getvalue(), "XML_Export_Data.xlsx")
        except Exception as e: st.error(f"Error: {e}")

if xml_upload and log_upload:
    st.divider()
    st.subheader("🛠️ Option 2: IDM Log File Split")
    if st.button("🚀 Process Log Split"):
        try:
            xml_content = xml_upload.getvalue().decode("utf-8")
            log_content = log_upload.getvalue().decode("utf-8", errors="ignore")
            root = ET.fromstring(xml_content)
            u_rows = [{"Series No": s.get('SERIE_NO'), "Product Code": i.get('TYPE_NO')} 
                      for s in root.findall('.//SERIE') for i in s.findall('.//ITEM')]
            
            out_log = BytesIO()
            with pd.ExcelWriter(out_log, engine='xlsxwriter') as writer:
                pd.DataFrame(u_rows).to_excel(writer, sheet_name='Unit Info', index=False)
                parse_log_section(log_content, "new products Added", "*****", {}, ["Sr_No", "Series", "Code", "Desc"]).to_excel(writer, sheet_name='NewProduct', index=False)
                parse_log_section(log_content, "products deleted", "*****", {}, ["Sr_No", "Series", "Code", "Order", "Desc"]).to_excel(writer, sheet_name='DeletedProduct', index=False)
            
            st.success("✅ Log split completed!")
            st.download_button("📥 Download Log Split", out_log.getvalue(), "Final_Data_Worksheet.xlsx")
        except Exception as e: st.error(f"Error: {e}")