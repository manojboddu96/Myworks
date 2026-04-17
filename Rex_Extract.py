import streamlit as st
import re
import pandas as pd
import io

def deep_binary_scan(binary_data):
    # 1. Define specific patterns based on the screenshot data
    # Item: 4-15 alphanumeric chars (allows dashes/dots)
    item_regex = rb'[A-Z0-9\-\.]{4,15}'
    # Price: Digits followed by a decimal point and two digits
    price_regex = rb'[0-9]{1,6}[\.,][0-9]{2}'
    
    # Combined: Look for Item + (up to 40 bytes of any data) + Price
    row_pattern = re.compile(item_regex + rb'.{1,40}' + price_regex)
    
    extracted_rows = []
    
    # 2. Iterate through matches
    for match in row_pattern.finditer(binary_data):
        raw_segment = match.group()
        
        # Clean the segment into readable text
        # We split by non-printable characters to isolate the 'columns'
        parts = re.findall(r'[A-Za-z0-9\-\.,]{3,}', raw_segment.decode('utf-8', 'ignore'))
        
        if len(parts) >= 2:
            item_code = parts[0]
            price = parts[-1]
            
            # 3. Fetch Category: Look back 120 bytes for the nearest descriptive word
            context_area = binary_data[max(0, match.start()-120) : match.start()]
            # Find words that look like 'Groups' or 'Finishes' (longer alpha strings)
            category_matches = re.findall(rb'[A-Za-z\s]{5,25}', context_area)
            category = category_matches[-1].decode('utf-8', 'ignore').strip() if category_matches else "Default"
            
            extracted_rows.append({
                "Group/Finish": category,
                "Item Code": item_code,
                "Price": price
            })
            
    return pd.DataFrame(extracted_rows).drop_duplicates()

# Streamlit UI
st.title("Binary Catalog Row Extractor")
st.write("Targeting structured data from EXE catalogs.")

uploaded = st.file_uploader("Upload EXE File", type='exe')

if uploaded:
    with st.spinner("Analyzing binary structure..."):
        raw_bytes = uploaded.read()
        df = deep_binary_scan(raw_bytes)
        
        if not df.empty:
            st.success(f"Found {len(df)} structured rows!")
            st.dataframe(df)
            
            # Export to CSV
            csv_data = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Download CSV for Excel", 
                csv_data, 
                "catalog_export.csv", 
                "text/csv"
            )
        else:
            st.error("No valid Item-Price pairs found. The file may be packed (compressed).")