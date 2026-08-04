import pandas as pd
import json

def split_ncd_by_templates(raw_tsv_path, template_mapping, id_column_name):
    # 1. Load the giant wide table
    df_raw = pd.read_csv(raw_tsv_path, sep='\t')
    df_raw = df_raw.head()
    print(f"Loaded master table with {len(df_raw)} records.\n" + "="*50)
    
    # --- NEW: Setup our tracking dictionaries ---
    successful_nodes = []
    skipped_nodes = {}
    
    # 2. Iterate through each target submission template
    for node_name, template_path in template_mapping.items():
        with open(template_path, 'r') as f:
            template = json.load(f)
            
        raw_keys = template.keys()
        dict_properties = set(k.replace('*', '') for k in raw_keys)
        
        # 3. Use Exact Matching 
        tsv_columns = set(df_raw.columns)
        exact_matches = list(dict_properties & tsv_columns)
        
        # Reason 1 for skipping: No matching columns
        if not exact_matches:
            skipped_nodes[node_name] = "No matching columns found in the database."
            continue
            
        # 4. Slice the dataframe
        columns_to_keep = list(dict.fromkeys(exact_matches + [id_column_name])) 
        df_subset = df_raw[columns_to_keep].copy()
        
        # Drop rows where ALL node-specific matched columns are empty
        df_subset = df_subset.dropna(subset=exact_matches, how='all')
        
        # Reason 2 for skipping: All rows were completely empty
        if len(df_subset) == 0:
            skipped_nodes[node_name] = f"Columns matched, but all {len(df_raw)} rows were completely blank for these fields."
            continue
        
        # 5. Apply the Graph Link Rules
        df_subset['subjects.submitter_id'] = df_subset[id_column_name]
        df_subset['submitter_id'] = f'{node_name}-' + df_subset[id_column_name].astype(str)
        df_subset['type'] = node_name
        
        # Clean up the original database ID
        df_subset = df_subset.drop(columns=[id_column_name])
        
        # 6. Export the perfectly mapped payload
        output_filename = f'payload_{node_name}.tsv'
        df_subset.to_csv(output_filename, sep='\t', index=False)
        
        # Log success
        successful_nodes.append(node_name)
    
    # ==========================================
    # FINAL ETL SUMMARY REPORT
    # ==========================================
    print("\n" + "="*50)
    print(" 📊 GEN3 ETL SUMMARY REPORT")
    print("="*50)
    
    print(f"\n✅ SUCCESSFULLY CREATED ({len(successful_nodes)}):")
    for node in successful_nodes:
        print(f"   - payload_{node}.tsv")
        
    print(f"\n⚠️ SKIPPED NODES ({len(skipped_nodes)}):")
    if not skipped_nodes:
        print("   (None! All templates successfully generated payloads.)")
    else:
        for node, reason in skipped_nodes.items():
            print(f"   - {node.upper()}: {reason}")
    print("\n" + "="*50)

# --- RUN THE DYNAMIC SPLITTER ---
my_templates = {
    'ncd_vital': 'submission_ncd_vital.json', 
    'ncd_lab': 'submission_ncd_lab.json',
    'medical_history': 'submission_medical_history.json', # Add any others here
    'lifestyle': 'submission_ncd_lifestyle.json'
}

split_ncd_by_templates('ncdindicators_raw.tsv', my_templates, 'individual_id')