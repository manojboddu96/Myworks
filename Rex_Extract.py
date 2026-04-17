import streamlit as st
import re
import pandas as pd
import io

def extract_clean_catalog(binary_data):
    # 1. Patterns specific to the screenshot provided
    # Pattern A: Likely Item Codes (Alphanumeric, often with dashes/dots)
    # Pattern B: Likely Prices (Digits followed by . or , and two decimals)
    item_pattern = rb'[A-Z0-9\-\.]{4,15}'
    price_pattern = rb'[0-9]{1,5}[\.,][0-9]{2}'
    
    # Combined pattern: Looking for an Item followed by a Price within a 50-byte window
    combined_regex = re.compile(item_pattern + rb'.{1,50}' + price_pattern)
    
    results = []
    
    # 2. Scanning the file
    matches = list(combined_regex.finditer(binary_data))
    
    for m in matches:
        raw_segment = m.group()
        # Clean the segment into readable parts
        parts = re.findall(r'[A-Za-z0-9\-\.,]{3,}', raw_segment.decode('utf-8', 'ignore'))
        
        if len(parts) >= 2:
            item = parts[0]
            price = parts[-1]
            
            # 3. Context Search: Look backwards from this match to find the Group/Finish
            # We look back 100 bytes to find the nearest descriptive word
            context_area = binary_data[max(0, m.start()-100) : m.start()]
            context_words = re.findall(rb'[A-Za-z\s]{4,}', context_area)
            
            group_name = context_words[-1].decode('utf-8', 'ignore').strip() if context_words else "Misc"
            
            results.append({
                "Group/Finish": group_name,
                "Item Code": item,
                "Price": price
            })
            
    return pd.DataFrame(results).drop_duplicates()

# Streamlit Interface
st.title("Catalog Deep-Structure Extractor")
uploaded = st.file_uploader("Upload KUMA3261.EXE", type='exe')

if uploaded:
    data = uploaded.read()
    df = extract_clean_catalog(data)
    
    if not df.empty:
        st.success(f"Extracted {len(df)} Clean Rows")
        st.dataframe(df)
        
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV for Excel", csv, "catalog_data.csv", "text/csv")
    else:
        st.error("No structured rows found. The data might be encoded in a non-standard byte format.")