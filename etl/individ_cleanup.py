import pandas as pd
import json

def split_individuals_to_graph(raw_individuals_path, project_code):
    # 1. Load the wide database table
    df_raw = pd.read_csv(raw_individuals_path, sep='\t')
    df_raw = df_raw.head()

 # PARENT NODE: SUBJECT 
    # Extract only the columns meant for the subject node
    df_subject = df_raw[['individual_id', 'hdss_name', 'sex', 'dob', 'dod', 'date_into_dsa', 'date_out_of_dsa', 'father_id', 'mother_id']].copy()
    
    # Rename the ID to satisfy Gen3
    df_subject = df_subject.rename(columns={'individual_id': 'submitter_id' })
    
    # Create the mandatory link to the administrative project and add node type
    df_subject['projects.code'] = project_code
    df_subject['type'] = 'subject'

    # Save the Subject payload
    df_subject.to_csv('payload_subject.tsv', sep='\t', index=False)
    print(f"Created payload_subject.tsv with {len(df_subject)} records.")

# CHILD NODE: DEMOGRAPHIC 

    # Extract only the columns meant for your custom demographic node
    # We MUST bring the individual_id along so we know who this belongs to!
    df_demographic = df_raw[['individual_id', 'ethnicity', 'sex', 'home_language', 'father_ethnicity', 'mother_ethnicity', 'father_home_language'
                              ,'mat_gfather_ethnicity', 'mat_gmother_ethnicity', 'mother_home_language']].copy()
    
    # 1. Create the link pointing back to the Subject node
    df_demographic['subjects.submitter_id'] = df_demographic['individual_id']
    
    # 2. Create a brand new, unique ID for this specific demographic node and add node type 
    df_demographic['submitter_id'] = 'demo-' + df_demographic['individual_id'].astype(str)
    df_demographic['type'] = 'demographic'
    
    # 3. Drop the original database ID since we don't need it anymore
    df_demographic = df_demographic.drop(columns=['individual_id'])
    
    # Save the Demographic payload
    df_demographic.to_csv('payload_demographic.tsv', sep='\t', index=False)
    print(f"Created payload_demographic.tsv with {len(df_demographic)} records.")

# SPLITTING INDIVIDUALS TO SUBJECTS AND DEMOGRAPHICS 
split_individuals_to_graph(
    raw_individuals_path='individuals_raw.tsv', 
    project_code='Agincourt'
)

# def clean_gen3_payload(raw_tsv_path, json_dict_path, clean_tsv_output, id_column_name):
#     # 1. Load the raw data and the dictionary
#     df = pd.read_csv(raw_tsv_path, sep='\t')
    
#     with open(json_dict_path, 'r') as f:
#         schema = json.load(f)
        
#     # Get all valid properties from your dictionary
#     valid_properties = set(schema.get('properties', {}).keys())
    
#     # ==========================================
#     # TASK 1: REMOVE COLUMNS NOT IN DICTIONARY
#     # ==========================================
#     # Keep only columns that exist in the dictionary (plus the original ID column if it's named differently)
#     valid_properties.add(id_column_name) 
#     columns_to_keep = [col for col in df.columns if col in valid_properties]
    
#     # Create a fresh copy to avoid pandas warnings
#     df_clean = df[columns_to_keep].copy() 
    
#     print(f"Dropped {len(df.columns) - len(df_clean.columns)} columns that were not in the dictionary.")

#     # ==========================================
#     # TASK 2: CHANGE THE IDS
#     # ==========================================
#     # Gen3 strictly requires the primary key to be named 'submitter_id'
#     if id_column_name in df_clean.columns:
#         df_clean = df_clean.rename(columns={id_column_name: 'submitter_id'})
    
#     # Ensure IDs are strings (Gen3 rejects integer IDs)
#     df_clean['submitter_id'] = df_clean['submitter_id'].astype(str)
    
#     # Optional: If you need to add a prefix to ensure uniqueness (e.g., 'sub-1234')
#     # df_clean['submitter_id'] = 'sub-' + df_clean['submitter_id']

#     # ==========================================
#     # TASK 3: FIX NEGATIVE ENUM CODES
#     # ==========================================
#     # Gen3 will treat -333 as a mathematical integer rather than an enum string/category.
#     # We replace common negative survey codes with their positive counterparts.
#     enum_fixes = {
#         -333: 333,
#         -777: 777,
#         -888: 888,
#         -999: 999
#     }
#     # This safely replaces these specific values across the entire dataframe
#     df_clean = df_clean.replace(enum_fixes)

#     # ==========================================
#     # EXPORT THE CLEAN PAYLOAD
#     # ==========================================
#     # Gen3 likes TSVs without index numbers
#     df_clean.to_csv(clean_tsv_output, sep='\t', index=False)
#     print(f"Clean payload saved successfully to: {clean_tsv_output}")
    
#     return df_clean

# # --- RUN THE FUNCTION ---
# # Replace 'individual_id' with whatever the actual ID column is named in your raw TSVs
# clean_data = clean_gen3_payload(
#     raw_tsv_path='individualsesindicators_raw.tsv',
#     json_dict_path='schema.json',
#     clean_tsv_output='individualsesindicators_clean.tsv',
#     id_column_name='individual_id' 
# )

# # Preview the first few rows to verify
# display(clean_data.head())