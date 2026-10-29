import pandas as pd

# Load the raw TSV
df_ncd = pd.read_csv('raw/ncdindicators_raw.tsv', sep='\t')

# Calculate the sum of NaNs for every column
nan_counts = df_ncd.isna().sum()

# Filter to only show columns that actually have missing data
columns_with_nans = nan_counts[nan_counts > 0]

print(f"Total rows in file: {len(df_ncd)}")
print("Missing values per column:")
print(columns_with_nans)