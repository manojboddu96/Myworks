import re
import csv

def extract_all_binary_data(input_file, output_csv):
    # Regex for sequences of printable characters (length 3 to 100)
    # This will catch markers we don't know yet, plus their values
    universal_pattern = re.compile(rb'[\x20-\x7E]{3,100}')
    
    # Common markers we already know (used for categorization)
    known_markers = [
        b'SUPPLIER', b'GROUPS', b'MODELS', b'FINISHES', 
        b'PRODUCTS', b'DESCRIPTION', b'PRICES', b'CODEPICS',
        b'UNITS', b'EAN', b'VAT', b'DISCOUNT', b'DIMENSIONS'
    ]

    extracted_data = []
    current_category = "HEADER/UNKNOWN"

    try:
        with open(input_file, 'rb') as f:
            content = f.read()
            matches = universal_pattern.finditer(content)

            for match in matches:
                raw_val = match.group()
                
                # Check if this string is actually a new category marker
                is_marker = False
                for km in known_markers:
                    if km in raw_val.upper():
                        current_category = km.decode('utf-8')
                        is_marker = True
                        break
                
                # If it's not a marker, it's data belonging to the last marker found
                if not is_marker:
                    try:
                        decoded_val = raw_val.decode('utf-8').strip()
                        if decoded_val:
                            extracted_data.append({
                                'Found_Under_Category': current_category,
                                'Data_Value': decoded_val,
                                'Byte_Position': match.start()
                            })
                    except:
                        continue

        # Save to CSV
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Found_Under_Category', 'Data_Value', 'Byte_Position'])
            writer.writeheader()
            writer.writerows(extracted_data)
            
        print(f"Extraction complete. Found {len(extracted_data)} data points.")

    except Exception as e:
        print(f"Error: {e}")

extract_all_binary_data('KUMA3261.EXE', 'total_extraction.csv')