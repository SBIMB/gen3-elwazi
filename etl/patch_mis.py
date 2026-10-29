import pandas as pd

file_path = "payloads/missing/payload_ncd_lifestyle_exposure_missing.json"
df_missing = pd.read_json(file_path)

if 'tobac_age_stp' in df_missing.columns:
    numeric_ages = pd.to_numeric(df_missing['tobac_age_stp'], errors='coerce')
    df_missing['tobac_age_stp'] = numeric_ages.fillna(df_missing['tobac_age_stp'])

df_missing.to_json(file_path, orient="records", indent=2)
print("Patched!")