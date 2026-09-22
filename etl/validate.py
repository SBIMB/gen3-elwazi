import json
import pandas as pd
import os

# ==========================================
# CONFIGURATION
# ==========================================
SCHEMA_FILE = "schema.json"  

# Your exact submission list
SUBMISSION_ORDER = [
    {"node": "subject.yaml", "path": "payloads/payload_subject.json"},
    {"node": "demographic.yaml", "path": "payloads/payload_demographic.json"},
    {"node": "ncd_lab.yaml", "path": "payloads/payload_ncd_lab.json"},
    {"node": "socioeconomic.yaml", "path": "payloads/payload_socioeconomic.json"},
    {"node": "ncd_lifestyle.yaml", "path": "payloads/payload_ncd_lifestyle.json"},
    {"node": "ncd_vital.yaml", "path": "payloads/payload_ncd_vital.json"},
    {"node": "medical_history.yaml", "path": "payloads/payload_medical_history.json"}
]

def validate_enums():
    """Scans specific JSON payloads against the local dictionary schema."""
    
    # 1. Load the entire schema into memory once
    try:
        with open(SCHEMA_FILE, "r") as f:
            master_schema = json.load(f)
    except FileNotFoundError:
        print(f" Error: Could not find '{SCHEMA_FILE}'. Please check the path.")
        return

    total_errors = 0
    
    # 2. Iterate only through the defined submission order
    for step in SUBMISSION_ORDER:
        node_name = step["node"]
        file_path = step["path"]
        
        print(f"\n🔍 Scanning node: {node_name}")
        
        if not os.path.exists(file_path):
            print(f"  ⚠️ Warning: File '{file_path}' not found. Skipping.")
            continue
            
        # Load local payload data
        with open(file_path, "r") as f:
            data = json.load(f)
            
        if not data:
            print("  ⚠️ Payload is empty. Skipping.")
            continue
            
        df = pd.DataFrame(data)
        
        # 3. Find this specific node's rules inside the master schema
        node_schema = master_schema.get(node_name)
        if not node_schema:
            print(f"  Warning: Node '{node_name}' not found in {SCHEMA_FILE}. Skipping.")
            print(f"  -> FYI, here are the exact names I see in the schema: {list(master_schema.keys())}")
            continue
            
        properties = node_schema.get("properties", {})
        node_has_errors = False
        
        # 4. Check every column in the payload against the schema rules
        for col in df.columns:
            if col in properties and "enum" in properties[col]:
                valid_options = set(properties[col]["enum"])
                
                # Find any values in the dataframe that aren't in the schema's valid options
                invalid_mask = ~df[col].isin(valid_options) & df[col].notna()
                invalid_rows = df[invalid_mask]
                
                if not invalid_rows.empty:
                    node_has_errors = True
                    bad_vals = invalid_rows[col].unique().tolist()
                    print(f"   Column '{col}' contains invalid codes: {bad_vals}")
                    total_errors += 1
                    
        if not node_has_errors:
            print(f"  Perfect! All categorical codes match the local schema.")

    print(f"\n========================================")
    if total_errors == 0:
        print("PASSED. Safe to run sbatch submit_etl.sh.")
    else:
        print(f"FAILED: Found {total_errors} columns with unharmonized codes. Fix data before upload.")
    print(f"========================================\n")

if __name__ == "__main__":
    validate_enums()