import pandas as pd
import json
import numpy as np
import hashlib
import yaml

# ==========================================
# 1. PARSE GEN3 YAML SCHEMA (DYNAMIC COLUMNS)
# ==========================================
# Load your massive Gen3 schema file
try:
    with open('your_schema_file.yaml', 'r') as f:
        schema = yaml.safe_load(f)

    yes_no_columns = []

    # Loop through every node in the schema
    for node_name, node_data in schema.items():
        if isinstance(node_data, dict) and 'properties' in node_data:
            for prop_name, prop_details in node_data['properties'].items():
                if isinstance(prop_details, dict) and 'enum' in prop_details:
                    enums = prop_details['enum']
                    if '0-no' in enums or '1-yes' in enums:
                        yes_no_columns.append(prop_name)

    # Deduplicate the list
    yes_no_columns = list(set(yes_no_columns))
    print(f"Dynamically found {len(yes_no_columns)} Yes/No columns in the schema.")
except FileNotFoundError:
    print("Schema file not found. Proceeding without dynamic Yes/No mapping.")
    yes_no_columns = []


# ==========================================
# 2. CORE CLEANING & MAPPING FUNCTIONS
# ==========================================
def anonymise_id(original_id, salt="secure_salt"):
    """Hashes the ID securely for anonymization."""
    if pd.isna(original_id) or str(original_id).strip() == "":
        return original_id
    
    salted_string = f"{str(original_id).strip()}_{salt}"
    return hashlib.sha256(salted_string.encode('utf-8')).hexdigest()[:10]


def clean_ids(df, id_column_name='individual_id'):
    """Handles ONLY structural cleaning and ID hashing."""
    # Standardize empty strings to NaN
    df = df.replace(r'^\s*$', np.nan, regex=True)

    # GUARANTEE ID MATCHING: Force to string, remove any .0 decimals
    df[id_column_name] = df[id_column_name].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df[id_column_name] = df[id_column_name].apply(anonymise_id)
    
    return df


def map_enums(df, yes_no_cols):
    """
    CENTRALIZED ENUM MAPPING.
    Add all new dictionary mappings to this function as you progress.
    """
    # --- A. GLOBAL FIXES (Applies to entire DataFrame) ---
    enum_fixes = {
        -333: '333-don\'t know', -333.0: 333, '-333': 333, '-333.0': 333, '-333.00': 333,
        -444: 444, -444.0: 444, '-444': 444, '-444.0': 444, '-444.00': 444,
        -777: 777, -777.0: 777, '-777': 777, '-777.0': 777, '-777.00': 777,
        -888: 888, -888.0: 888, '-888': 888, '-888.0': 888, '-888.00': 888,
        -999: 999, -999.0: 999, '-999': 999, '-999.0': 999, '-999.00': 999
    }
    df = df.replace(enum_fixes)

    # --- B. DYNAMIC YES/NO MAPPING ---
    yes_no_map = {
        0: '0-no', '0': '0-no', 0.0: '0-no', '0.0': '0-no',
        1: '1-yes', '1': '1-yes', 1.0: '1-yes', '1.0': '1-yes'
    }

    
    for col in yes_no_cols:
        if col in df.columns:
            # map() replaces non-matches with NaN, so we fillna with the original values to prevent data loss
            df[col] = df[col].map(yes_no_map).fillna(df[col])

    # --- C. SPECIFIC COLUMN MAPPINGS ---
    # Add to these dictionaries as you go through your data dictionary
    sex_mapping = {
        1: 'Female', 1.0: 'Female', '1': 'Female', '1.0': 'Female',
        2: 'Male', 2.0: 'Male', '2': 'Male', '2.0': 'Male',
        0: 'Other', 0.0: 'Other', '0': 'Other', '0.0': 'Other'
    }
    
    if 'sex' in df.columns:
        df['sex'] = df['sex'].map(sex_mapping).fillna(df['sex'])
        
    return df


# ==========================================
# 3. INTERSECTION CHECK (THE BOUNCER)
# ==========================================
# Finding matching records throughout
df_ind_raw = pd.read_csv('raw/individuals_raw.tsv', sep='\t', usecols=['individual_id'])
df_ncd_raw = pd.read_csv('raw/ncdindicators_raw.tsv', sep='\t', usecols=['individual_id'])

ids_ind = set(df_ind_raw['individual_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip())
ids_ncd = set(df_ncd_raw['individual_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip())

common_ids = ids_ind.intersection(ids_ncd)

print("--- Strict Intersection Check ---")
print(f"Total IDs in individuals table: {len(ids_ind)}")
print(f"Total IDs in NCD table:         {len(ids_ncd)}")
print(f"Exactly matched IDs kept:       {len(common_ids)}")
print("---------------------------------\n")

valid_ids_list = list(common_ids)


# ==========================================
# 4. NODE PROCESSING PIPELINES
# ==========================================
def process_individuals_table(raw_individuals_path, valid_ids, yes_no_cols):
    """Processes Subject and Demographic nodes."""
    df_raw = pd.read_csv(raw_individuals_path, sep='\t')

    # Filter invalid IDs before processing
    df_raw['individual_id'] = df_raw['individual_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_raw = df_raw[df_raw['individual_id'].isin(valid_ids)].copy()

    # 1. Structural cleaning
    df_clean = clean_ids(df_raw, 'individual_id')
    # 2. Centralized Enum Mapping
    df_clean = map_enums(df_clean, yes_no_cols)

    project_mapping = {
        'Agincourt': 'Agincourt',
        'Nairobi': 'Nairobi' 
    }

    # ==========================================
    # --- PARENT NODE: SUBJECT ---
    # ==========================================
    df_subject = df_clean[['individual_id', 'hdss_name', 'sex', 'dob', 'dod', 'date_into_dsa', 'date_out_of_dsa', 'father_id', 'mother_id']].copy()
    df_subject = df_subject.rename(columns={'individual_id': 'submitter_id'})
    
    df_subject['projects.code'] = df_subject['hdss_name'].map(project_mapping)
    df_subject['type'] = 'subject'

    # Apply universal fill LAST (protecting structural columns)
    subject_structural = ['submitter_id', 'father_id', 'mother_id']
    subject_clinical = [col for col in df_subject.columns if col not in subject_structural]
    df_subject[subject_clinical] = df_subject[subject_clinical].fillna('999-missing')

    df_subject.to_csv('payloads/payload_subject.tsv', sep='\t', index=False, float_format='%g')
    print(f"Created payload_subject.tsv with {len(df_subject)} records.")

    # ==========================================
    # --- CHILD NODE: DEMOGRAPHIC ---
    # ==========================================
    df_demographic = df_clean[['individual_id', 'ethnicity', 'sex', 'home_language', 'father_ethnicity', 'mother_ethnicity', 'father_home_language',
                               'mat_gfather_ethnicity', 'mat_gmother_ethnicity', 'mother_home_language']].copy()
    
    df_demographic['subjects.submitter_id'] = df_demographic['individual_id']
    df_demographic['submitter_id'] = 'demo-' + df_demographic['individual_id'].astype(str)
    df_demographic['type'] = 'demographic'
    
    demo_structural = ['submitter_id', 'subjects.submitter_id', 'individual_id']
    demo_clinical = [col for col in df_demographic.columns if col not in demo_structural]
    df_demographic[demo_clinical] = df_demographic[demo_clinical].fillna('999-missing')

    df_demographic = df_demographic.drop(columns=['individual_id'])
    df_demographic.to_csv('payloads/payload_demographic.tsv', sep='\t', index=False, float_format='%g')
    print(f"Created payload_demographic.tsv with {len(df_demographic)} records.")


def process_ses_table(raw_ses_path, valid_ids, yes_no_cols):
    """Processes Socioeconomic specific nodes."""
    df_socio_raw = pd.read_csv(raw_ses_path, sep='\t')

    # Bouncer Check
    df_socio_raw['individual_id'] = df_socio_raw['individual_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_socio = df_socio_raw[df_socio_raw['individual_id'].isin(valid_ids)].copy()

    # 1. Structural cleaning
    df_socio = clean_ids(df_socio, 'individual_id')
    # 2. Centralized Enum Mapping
    df_socio = map_enums(df_socio, yes_no_cols)

    # Float Trap fixes
    enum_columns = ['education_level', 'education_years', 'marital_status', 'currently_working']
    for col in enum_columns:
        if col in df_socio.columns:
            df_socio[col] = (df_socio[col]
                             .astype(str)
                             .str.replace(r'\.0$', '', regex=True)
                             .replace('nan', np.nan))

    # Graph Links
    df_socio['submitter_id'] = 'socioeconomic-' + df_socio['individual_id'] + '-' + df_socio.index.astype(str)
    df_socio['subjects.submitter_id'] = df_socio['individual_id']
    df_socio = df_socio.fillna('999-missing')

    df_socio.to_csv('payloads/payload_socioeconomic.tsv', sep='\t', index=False)
    print(f"Created payload_socioeconomic.tsv with {len(df_socio)} records.")


def process_template_nodes(raw_path, template_mapping, valid_ids, yes_no_cols):
    """Generic processor for template-driven payload creation."""
    df_raw = pd.read_csv(raw_path, sep='\t')

    df_raw['individual_id'] = df_raw['individual_id'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    df_raw = df_raw[df_raw['individual_id'].isin(valid_ids)].copy()

    # 1. Structural cleaning
    df_clean = clean_ids(df_raw, 'individual_id')
    # 2. Centralized Enum Mapping
    df_clean = map_enums(df_clean, yes_no_cols)

    # Double-check subjects exist in payloads
    master_subjects = pd.read_csv('payloads/payload_subject.tsv', sep='\t')
    valid_submitter_ids = master_subjects['submitter_id'].unique()

    initial_count = len(df_clean)
    df_clean = df_clean[df_clean['individual_id'].isin(valid_submitter_ids)].copy()
    dropped_count = initial_count - len(df_clean)

    if dropped_count > 0:
        print(f" Dropped {dropped_count} orphaned records that do not exist in the database")

    structural_columns = ['individual_id']
    clinical_columns = [col for col in df_clean.columns if col not in structural_columns]
    df_clean[clinical_columns] = df_clean[clinical_columns].fillna('999-missing')
    
    for node_name, template_path in template_mapping.items():
        try:
            with open(template_path, 'r') as f:
                template = json.load(f)
                
            dict_properties = set(k.replace('*', '') for k in template.keys())
            exact_matches = list(dict_properties & set(df_clean.columns))
            
            if not exact_matches:
                continue
                
            columns_to_keep = list(dict.fromkeys(exact_matches + ['individual_id'])) 
            df_subset = df_clean[columns_to_keep].copy()
            
            # Graph Links
            df_subset['subjects.submitter_id'] = df_subset['individual_id']
            df_subset['submitter_id'] = f'{node_name}-' + df_subset['individual_id'] + '-' + df_subset.index.astype(str)
            df_subset['type'] = node_name
            
            df_subset = df_subset.drop(columns=['individual_id'])
            df_subset.to_csv(f'payloads/payload_{node_name}.tsv', sep='\t', index=False, float_format='%g')
            print(f"Processed {node_name.upper()}: Created payload_{node_name}.tsv")
        except FileNotFoundError:
            print(f"Template {template_path} not found. Skipping {node_name}.")


# ==========================================
# 5. RUNNING THE PIPELINE
# ==========================================
if __name__ == "__main__":
    print("Starting Master ETL Pipeline...\n" + "="*40)

    # 1. Master Subject & Demographic nodes
    process_individuals_table('raw/individuals_raw.tsv', valid_ids_list, yes_no_columns)

    # 2. Template-driven child nodes (NCD)
    ncd_templates = {
        'ncd_vital': 'templates/submission_ncd_vital.json', 
        'ncd_lab': 'templates/submission_ncd_lab.json',
        'medical_history': 'templates/submission_medical_history.json',
        'lifestyle': 'templates/submission_ncd_lifestyle.json'
    }
    process_template_nodes('raw/ncdindicators_raw.tsv', ncd_templates, valid_ids_list, yes_no_columns)

    # 3. SES Nodes (Uncomment when files are ready)
    # process_ses_table('raw/individualsesindicators_raw.tsv', valid_ids_list, yes_no_columns)
    
    print("="*40 + "\nPipeline Complete! All IDs are aligned and enums are cleanly mapped.")