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
    """Refined parser to handle ADDITIONAL_PRICE_GROUP logic explicitly."""
    root = ET.fromstring(xml_content)
    u_info, m_price, a_price, restr_tab, min_p = [], [], [], [], []

    for serie in root.findall('.//SERIE'):
        s_no = serie.get('SERIE_NO')
        for item in serie.findall('.//ITEM'):
            u_name = item.get('TYPE_NO')
            
            # 1. Dimensions and Unit Info
            width = depth = height = "0"
            for param in item.findall('.//BASIC_SHAPE_PARAMETER'):
                name = param.get('BASIC_SHAPE_NAME', '').lower()
                val = param.get('BASIC_SHAPE_NOMINAL_VALUE', '0')
                if name == 'b': width = val
                elif name == 'h': height = val
                elif name == 't': depth = val

            u_info.append({
                "SERIE_NO": s_no, "TYPE_NO": u_name,
                "Width": width, "Depth": depth, "Height": height,
                "EDP_NUMBER": item.findtext('.//EDP_NUMBER') or "",
                "EAN_NUMBER": item.findtext('.//EAN_NUMBER') or "",
                "WEIGHT": item.findtext('.//WEIGHT') or "",
                "VOLUME": item.findtext('.//VOLUME') or "",
                "CONSTRUCTION_ID": item.findtext('.//CONSTRUCTION_ID') or "",
                "CLASSIFICATION_CODE": "|".join([c.findtext('CLASSIFICATION_CODE') for c in item.findall('.//CLASSIFICATION') if c.findtext('CLASSIFICATION_CODE')])
            })

            # 2. Prices - Logic for Main vs Additional based on Tag Name
            # Iterate through all children of ITEM to find price containers
            for group in item:
                tag_name = group.tag
                if "PRICE_GROUP" in tag_name or "PRICE_FEATURE_GROUP" in tag_name:
                    
                    # Find Group ID (PRICE_FEATURE_GROUP_NO)
                    group_ref = group.find('.//PRICE_FEATURE_GROUP_REF')
                    group_no = group.get('PRICE_FEATURE_GROUP_NO') or (group_ref.get('PRICE_FEATURE_GROUP_NO') if group_ref is not None else None)
                    
                    # Determine Price Type based on tag name first, then attribute
                    is_additional = "ADDITIONAL" in tag_name.upper()
                    type_ref = group.find('.//PRICE_TYPE_REF')
                    p_type_val = group.get('PRICE_TYPE_NO') or (type_ref.get('PRICE_TYPE_NO') if type_ref is not None else "1")

                    for item_p in group.findall('.//ITEM_PRICE'):
                        field = item_p.findtext('PRICE_FIELD')
                        price_val = item_price_text = item_p.findtext('PRICE')
                        
                        p_data = {
                            "SERIE_NO": s_no, "TYPE_NO": u_name,
                            "PRICE_FEATURE_GROUP_NO": group_no,
                            "PRICE_FIELD": field, "PRICE": price_val,
                            "PRICE_TYPE_NO": p_type_val
                        }

                        # Explicit Routing: If it's in an ADDITIONAL tag, force to Additional tab
                        if is_additional:
                            a_price.append(p_data)
                        elif p_type_val == "1":
                            m_price.append(p_data)
                        else:
                            a_price.append(p_data)

                        # Minimum Price (Check child tags)
                        min_basic = item_p.findtext('PRICE_MINIMUM_BASIC')
                        if min_basic:
                            p_min = p_data.copy()
                            p_min.update({
                                "PRICE_MINIMUM_BASIC": min_basic,
                                "BASIC_PRICE_UNIT": item_p.findtext('BASIC_PRICE_UNIT')
                            })
                            min_p.append(p_min)

            # 3. RESTRICTIONS
            for rest_container in item.findall('.//RESTRICTIONS'):
                for r_ref in rest_container.findall('.//RESTRICTION_REF'):
                    restr_tab.append({
                        "SERIE_NO": s_no, "TYPE_NO": u_name,
                        "RESTRICTION_NO": r_ref.get('RESTRICTION_NO')
                    })

    return {
        "Unit Info": pd.DataFrame(u_info),
        "Main Price": pd.DataFrame(m_price),
        "Additional Price": pd.DataFrame(a_price),
        "RESTRICTIONS": pd.DataFrame(restr_tab),
        "Minimum Price": pd.DataFrame(min_p)
    }

# --- LOG SPLITTER PARSER ---
def parse_log_section(content, start_marker, end_marker, replacements, columns, delimiter=']'):
    extracted = []
    record = False
    for line in content.splitlines():
        if start_marker in line: record = True; continue
        if end_marker in line and record: record = False; break
        if record and line.strip():
            clean = line.strip()
            for old, new in replacements.items(): clean = clean.replace(old, new)
            extracted.append(clean)
    if not extracted: return pd.DataFrame(columns=columns)
    df = pd.DataFrame([l.split(delimiter) for l in extracted])
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
                # ... Add other log tabs here ...
            st.success("✅ Log split completed!")
            st.download_button("📥 Download Log Split", out_log.getvalue(), "Final_Worksheet.xlsx")
        except Exception as e: st.error(f"Error: {e}")