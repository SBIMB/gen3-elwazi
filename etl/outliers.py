import pandas as pd
import numpy as np

def identify_clinical_outliers(df, node_name):
    """
    Filters a DataFrame for biologically implausible values based on defined clinical ranges.
    Returns a DataFrame containing only the outlier records and a reason column.
    """
    
    # Define hard clinical thresholds (Min, Max)
    # Adjust these ranges based on the specific population in the MADIVA study
    thresholds = {
        'ncd_vital': {
            'height_cm': (50, 250),      # Minimum 50cm, Maximum 2.5m
            'weight_kg': (20, 300),      # Minimum 20kg, Maximum 300kg
            'waist_cm': (30, 250),
            'hip_cm': (30, 250),
            'bmi': (10, 100),            # BMI > 100 is highly unlikely
            'pulse': (30, 250),          # HR < 30 or > 250 is medical emergency/error
            'bp_sys': (50, 250),         # Systolic BP 
            'bp_dia': (30, 150)          # Diastolic BP
        },
        'ncd_lab': {
            'poc_hb': (2, 25),           # Hemoglobin g/dl
            'insulin_fasting': (0.1, 1000), 
            'bg_mmol_fst': (1, 40),      # Fasting Blood Glucose mmol/L
            'bg_mmol_random': (1, 50),
            'ldl_mmol': (0.1, 20),
            'hdl_mmol': (0.1, 10),
            'trigs_mmol': (0.1, 50)
        }
    }
    
    if node_name not in thresholds:
        return pd.DataFrame() # No thresholds defined for this node
        
    node_thresholds = thresholds[node_name]
    
    # Create an empty list to store records that flag as outliers
    outlier_records = []
    
    for index, row in df.iterrows():
        is_outlier = False
        outlier_reasons = []
        
        for col, (min_val, max_val) in node_thresholds.items():
            if col in df.columns:
                val = row[col]
                
                # Skip NaN, None, or string enum values (like "999-missing")
                if pd.isna(val) or isinstance(val, str):
                    continue
                    
                # Check if it's a numeric value outside our threshold
                try:
                    num_val = float(val)
                    if num_val < min_val or num_val > max_val:
                        is_outlier = True
                        outlier_reasons.append(f"{col}: {num_val} (Allowed: {min_val}-{max_val})")
                except (ValueError, TypeError):
                    pass # Ignore if it can't be coerced to a float
                    
        # If any column flagged as an outlier, save the entire row
        if is_outlier:
            row_dict = row.to_dict()
            row_dict['_outlier_reason'] = " | ".join(outlier_reasons)
            outlier_records.append(row_dict)
            
    return pd.DataFrame(outlier_records)

# Load your JSON payload
df_labs = pd.read_json("payloads/payload_ncd_lab.json")

# Extract the outliers
df_outliers = identify_clinical_outliers(df_labs, "ncd_lab")

# Save them to a CSV for manual review
if not df_outliers.empty:
    df_outliers.to_csv("investigate_lab_outliers.csv", index=False)
    print(f"Found {len(df_outliers)} records with impossible clinical values!")
else:
    print("No clinical outliers found.")