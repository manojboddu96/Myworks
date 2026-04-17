import streamlit as st
import re
import pandas as pd
import io

st.title("Catalog Binary Extractor")
st.write("Upload your .EXE file to convert the catalog into a structured format.")

uploaded_file = st.file_uploader("Choose a file", type=['exe'])

if uploaded_file is not None:
    # Read the binary content
    content = uploaded_file.read()
    
    # 1. Configuration
    markers = [
        b'SUPPLIER', b'GROUPS', b'MODELS', b'FINISHES', 
        b'PRODUCTS', b'DESCRIPTION', b'PRICES', b'CODEPICS',
        b'UNITS', b'DIMENSIONS', b'EAN'
    ]
    data_pattern = re.compile(rb'[A-Za-z0-9\s\.,\-\/]{3,100}')
    
    extracted_records = []
    
    # 2. Processing with Streamlit Progress Bar
    progress_bar = st.progress(0)
    st.info("Scanning binary structures...")
    
    # Find all marker positions
    marker_positions = []
    for marker in markers:
        for match in re.finditer(marker, content):
            marker_positions.append((match.start(), marker.decode()))
    
    marker_positions.sort()

    # 3. Data Extraction Loop
    total = len(marker_positions)
    for i in range(total):
        start_pos, category = marker_positions[i]
        end_pos = marker_positions[i+1][0] if i+1 < total else len(content)
        
        segment = content[start_pos:end_pos]
        matches = data_pattern.findall(segment)
        
        for m in matches:
            value = m.decode('utf-8', errors='ignore').strip()
            if value and value.upper() != category.upper():
                extracted_records.append({"Category": category, "Value": value})
        
        # Update progress bar to prevent "Black Screen" / Timeout
        progress_bar.progress((i + 1) / total)

    # 4. Display and Download
    if extracted_records:
        df = pd.DataFrame(extracted_records)
        st.success(f"Successfully extracted {len(df)} records!")
        
        # Show a preview
        st.dataframe(df.head(50))
        
        # Convert to CSV for download
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="Download Full CSV",
            data=csv_buffer.getvalue(),
            file_name="extracted_catalog.csv",
            mime="text/csv"
        )
    else:
        st.warning("No structured data found. Try adjusting the markers.")