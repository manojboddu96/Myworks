import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(page_title="XML & Log Processor", layout="wide")

st.title("📂 XML and IDMLog Data Processor")
st.write("Generate Deep XML Exports or the 11-Tab Final Data Worksheet.")

# --- UI: FILE UPLOADERS ---
col1, col2 = st.columns(2)
with col1:
    xml_upload = st.file_uploader("Upload XML File", type=['xml'])
with col2:
    log_upload = st.file_uploader("Upload Log/Text File", type=['txt', 'log'])

# --- LOG SPLITTING LOGIC (AS PROVIDED) ---
def parse_log_section(content, start_marker, end_marker, replacements, columns, delimiter=']'):
    """Replicates VBA Do-Loop, Replace, and Split logic."""
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

# --- XML DEEP EXPORT LOGIC (FIXED VERSION) ---
def get_xml_deep_export(xml_content):
    root = ET.fromstring(xml_content)
    u_info, m_price, a_price, restr_tab, min_p = [], [], [], [], []

    for serie in root.findall('.//SERIE'):
        s_no = serie.get('SERIE_NO')
        for item in serie.findall('.//ITEM'):
            u_name = item.get('TYPE_NO')
            
            # Dimensions
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

            # Prices logic
            for group in item:
                tag_name = group.tag
                if "PRICE_GROUP" in tag_name or "PRICE_FEATURE_GROUP" in tag_name:
                    group_ref = group.find('.//PRICE_FEATURE_GROUP_REF')
                    group_no = group.get('PRICE_FEATURE_GROUP_NO') or (group_ref.get('PRICE_FEATURE_GROUP_NO') if group_ref is not None else None)
                    is_additional = "ADDITIONAL" in tag_name.upper()
                    
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
                            p_min = p_data.copy()
                            p_min.update({"PRICE_MINIMUM_BASIC": min_basic, "BASIC_PRICE_UNIT": item_p.findtext('BASIC_PRICE_UNIT')})
                            min_p.append(p_min)

            # Restrictions
            for rest_container in item.findall('.//RESTRICTIONS'):
                for r_ref in rest_container.findall('.//RESTRICTION_REF'):
                    restr_tab.append({"SERIE_NO": s_no, "TYPE_NO": u_name, "RESTRICTION_NO": r_ref.get('RESTRICTION_NO')})

    return {"Unit Info": pd.DataFrame(u_info), "Main Price": pd.DataFrame(m_price), "Additional Price": pd.DataFrame(a_price), "RESTRICTIONS": pd.DataFrame(restr_tab), "Minimum Price": pd.DataFrame(min_p)}

# --- EXECUTION LOGIC ---
if xml_upload:
    st.subheader("🛠️ Option 1: XML Deep Export")
    if st.button("📊 Generate XML Export Excel"):
        try:
            xml_bytes = xml_upload.getvalue().decode("utf-8")
            export_sheets = get_xml_deep_export(xml_bytes)
            out_xml = BytesIO()
            with pd.ExcelWriter(out_xml, engine='xlsxwriter') as writer:
                for s_name, df in export_sheets.items():
                    df.to_excel(writer, sheet_name=s_name, index=False)
            st.download_button("📥 Download XML Export", out_xml.getvalue(), "XML_Export_Data.xlsx")
        except Exception as e: st.error(f"Error: {e}")

if xml_upload and log_upload:
    st.divider()
    st.subheader("🛠️ Option 2: IDM Log File Split")
    if st.button("🚀 Process Log Split (Final Data Worksheet)"):
        try:
            xml_content = xml_upload.getvalue().decode("utf-8")
            log_content = log_upload.getvalue().decode("utf-8", errors="ignore")
            
            # XML for Log tabs
            root = ET.fromstring(xml_content)
            unit_rows, series_rows = [], []
            for serie in root.findall('.//SERIE'):
                s_no = serie.get('SERIE_NO')
                series_rows.append({"Series No": s_no, "Series Name": serie.findtext('.//TEXT') or ""})
                for item in serie.findall('.//ITEM'):
                    p_code = item.get('TYPE_NO')
                    dims = [p.get('BASIC_SHAPE_NOMINAL_VALUE', '0') for p in item.findall('.//BASIC_SHAPE_PARAMETER')]
                    unit_rows.append({"Series No": s_no, "Product Code": p_code, "ConSNO_PCode": f"{s_no}_{p_code}", "Width": dims[0] if len(dims)>0 else 0, "Depth": dims[1] if len(dims)>1 else 0, "Height": dims[2] if len(dims)>2 else 0})

            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                pd.DataFrame(log_content.splitlines(), columns=["Raw Log Data"]).to_excel(writer, sheet_name='IDMLog', index=False)
                pd.DataFrame(unit_rows).to_excel(writer, sheet_name='Unit Info', index=False)
                pd.DataFrame(series_rows).to_excel(writer, sheet_name='Series ID Info', index=False)

                # Applying your specific parse logic
                parse_log_section(log_content, "new products Added in Catalog", "*****", {"[Product Description": "", ")[Product Code": ""}, ["Sr_No", "Series ID", "Product Code", "Description"]).to_excel(writer, sheet_name='NewProduct', index=False)
                parse_log_section(log_content, "products deleted from catalog", "*****", {")[Series": "", ": [Unit Name": "", " :[Order Code": "", ":[Description": ""}, ["Sr_No", "Series No", "Product Code", "Order Code", "Description"]).to_excel(writer, sheet_name='DeletedProduct', index=False)
                parse_log_section(log_content, "usercode value  updated", "*****", {") [Old Usercode": "", " [New UserCode": ""}, ["Sr_No", "Old Product Code", "New Product Code", "Old Order Code", "New Order Code"]).to_excel(writer, sheet_name='CodeUpdated', index=False)
                parse_log_section(log_content, "new options Added in Catalog", "*****", {")[Feature Code": "", " [Feature Description": "", "[Option Code": "", " [Option Description": ""}, ["Sr_No", "Type ID", "Feature Code", "Feature Description", "Option Code", "Entry ID", "Option Description"]).to_excel(writer, sheet_name='NewOptions', index=False)
                parse_log_section(log_content, "new Features Added in Catalog", "*****", {") [Feature Code": "", "[Feature Description": ""}, ["Sr_No", "Type ID", "Feature Code/Order Code", "Feature Description/Type Name"]).to_excel(writer, sheet_name='NewFeatures', index=False)
                parse_log_section(log_content, "New Linkref Added on folllowing Products", "*****", {") [UnitName": "", " [LinkRef": ""}, ["Sr_No", "Unit Name", "Linkref Added"]).to_excel(writer, sheet_name='LinkListAddedToUnit', index=False)
                parse_log_section(log_content, "New LinkList Added in Catalog", "*****", {}, ["Sr_No", "Linkref Added", "Link List Name"], delimiter=")").to_excel(writer, sheet_name='LinkListAddedInLinks', index=False)
                parse_log_section(log_content, "Added  new addon(s)", "*****", {") [UnitName": "", "[Addons": ""}, ["Sr_No", "Unit Name", "Addons Added"]).to_excel(writer, sheet_name='AddonsAddedToUnits', index=False)
                parse_log_section(log_content, "new colorString Added", "*****", {")Id ": "", "  Sort Order ": "", "   Material ID": "", ":": ""}, ["Sr_No", "ID", "Sort Code", "Description", "Material ID"]).to_excel(writer, sheet_name='NewColorStringAdded', index=False)

            st.success("✅ Log Split Success!")
            st.download_button("📥 Download Final Data Worksheet", output.getvalue(), "Final_Data_Worksheet.xlsx")
        except Exception as e: st.error(f"Error: {e}")