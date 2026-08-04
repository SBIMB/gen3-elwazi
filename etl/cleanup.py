import pandas as pd
import json
import numpy as np
import hashlib
import yaml
import os

# ============================================================
# SECTION 1: ID UTILITIES
# ============================================================

def normalise_id(raw_id):
    """Force ID to clean string — strips floats, whitespace."""
    return str(raw_id).replace(r'\.0$', '').strip()


def anonymise_id(original_id, salt="secure_salt"):
    """One-way hash of a subject ID. Consistent across runs given same salt."""
    if pd.isna(original_id) or str(original_id).strip() in ("", "nan"):
        return original_id
    salted = f"{str(original_id).strip()}_{salt}"
    return hashlib.sha256(salted.encode("utf-8")).hexdigest()[:10]


def clean_ids(df, id_column="individual_id"):
    """Normalise and anonymise the ID column."""
    df = df.copy()
    df[id_column] = (
        df[id_column]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .apply(anonymise_id)
    )
    return df


# ============================================================
# SECTION 2: MAPPING UTILITIES (CONFIG-DRIVEN)
# ============================================================

# Structural mapping (Not standard enums, kept in-script)
PROJECT_MAP = {
    "Agincourt": "Agincourt",
    "Nairobi":   "Nairobi",
}

def load_enum_mappings(mapping_path="enum_mappings.yaml"):
    """Loads the auto-generated YAML mappings."""
    with open(mapping_path) as f:
        return yaml.safe_load(f)


def apply_enum_mappings(df, node_name, mappings):
    df = df.copy()

    # 1. Global missing codes
    global_missing = mappings.get("global", {}).get("missing_codes", {})
    if global_missing:
        df = df.replace(global_missing)

    # 2. Smart Node Lookup
    nodes_dict = mappings.get("nodes", {})
    
    # Attempt 1: Exact match (e.g., "ncd_vital")
    node_mappings = nodes_dict.get(node_name)
    
    # Attempt 2: Try adding .yaml (e.g., "ncd_vital" -> "ncd_vital.yaml")
    if not node_mappings:
        node_mappings = nodes_dict.get(f"{node_name}.yaml")
        
    # Attempt 3: Try adding 's.yaml' (e.g., "demographic" -> "demographics.yaml")
    if not node_mappings:
        node_mappings = nodes_dict.get(f"{node_name}s.yaml")

    # 3. Apply mappings if a valid dictionary was found
    if node_mappings:
        for col, col_map in node_mappings.items():
            if col in df.columns and col_map:
                expanded = {}
                for raw, gen3 in col_map.items():
                    expanded[raw] = gen3
                    expanded[float(raw)] = gen3 if isinstance(raw, int) else gen3
                    expanded[str(raw)] = gen3
                    expanded[f"{float(raw):.1f}"] = gen3
                df[col] = df[col].replace(expanded)
    else:
        print(f"  [Warning] No YAML mapping dictionary found for node: {node_name}")

    return df


def strip_whitespace_and_blanks(df):
    """Replace blank strings with NaN so fillna works correctly downstream."""
    return df.replace(r"^\s*$", np.nan, regex=True)


# ============================================================
# SECTION 3: ID OVERLAP / VALID ID RESOLUTION
# ============================================================

def get_valid_ids(*tsv_paths, id_col="individual_id"):
    """Return the intersection of subject IDs across multiple TSV files."""
    id_sets = []
    for path in tsv_paths:
        df = pd.read_csv(path, sep="\t", usecols=[id_col], dtype=str)
        ids = set(
            df[id_col]
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
            .dropna()
        )
        id_sets.append(ids)
        print(f"  {os.path.basename(path):40} {len(ids):>7,} IDs")

    result = id_sets[0]
    for s in id_sets[1:]:
        result = result & s

    print(f"\n  Intersection (valid IDs): {len(result):,}")
    return result


# ============================================================
# SECTION 4: NODE PROCESSING FUNCTIONS
# ============================================================

def process_individuals_table(raw_path, valid_ids, mappings):
    """Process the master individuals TSV into subject and demographic payloads."""
    print(f"\nProcessing individuals table: {raw_path}")
    df_raw = pd.read_csv(raw_path, sep="\t")

    # Filter to valid IDs before any cleaning
    df_raw["individual_id"] = (
        df_raw["individual_id"].astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    df_raw = df_raw[df_raw["individual_id"].isin(valid_ids)].copy()
    print(f"  Loaded {len(df_raw):,} records after ID filter")

    # --- Structural Cleaning ---
    df = strip_whitespace_and_blanks(df_raw)
    df = clean_ids(df, "individual_id")

    # ---- SUBJECT NODE ----
    subject_cols = [
        "individual_id", "hdss_name", "sex", "dob", "dod",
        "date_into_dsa", "date_out_of_dsa", "father_id", "mother_id"
    ]
    df_subject = df[[c for c in subject_cols if c in df.columns]].copy()
    
    # Apply node-specific mappings dynamically
    df_subject = apply_enum_mappings(df_subject, "subject", mappings)

    df_subject = df_subject.rename(columns={"individual_id": "submitter_id"})
    df_subject["projects.code"] = df_subject["hdss_name"].map(PROJECT_MAP)
    df_subject["type"] = "subject"

    structural = ["submitter_id", "father_id", "mother_id"]
    fillable = [c for c in df_subject.columns if c not in structural]
    df_subject[fillable] = df_subject[fillable].fillna("999-missing")

    os.makedirs("payloads", exist_ok=True)
    df_subject.to_json("payloads/payload_subject.json", orient="records", indent=2)
    print(f"  -> payload_subject.json: {len(df_subject):,} records")


    # ---- DEMOGRAPHIC NODE ----
    demo_cols = [
        "individual_id", "ethnicity", "sex", "home_language",
        "father_ethnicity", "mother_ethnicity", "father_home_language",
        "mat_gfather_ethnicity", "mat_gmother_ethnicity", "mother_home_language"
    ]
    df_demo = df[[c for c in demo_cols if c in df.columns]].copy()
    
    # Apply node-specific mappings dynamically
    df_demo = apply_enum_mappings(df_demo, "demographic.yaml", mappings)

    df_demo["subjects.submitter_id"] = df_demo["individual_id"]
    df_demo["submitter_id"] = "demo-" + df_demo["individual_id"].astype(str)
    df_demo["type"] = "demographic"

    structural_demo = ["submitter_id", "subjects.submitter_id", "individual_id"]
    fillable_demo = [c for c in df_demo.columns if c not in structural_demo]
    df_demo[fillable_demo] = df_demo[fillable_demo].fillna("999-missing")
    df_demo = df_demo.drop(columns=["individual_id"])

    df_demo.to_json("payloads/payload_demographic.json", orient="records", indent=2)
    print(f"  -> payload_demographic.json: {len(df_demo):,} records")


def process_template_nodes(raw_path, template_mapping, valid_ids, mappings):
    """Process a raw TSV into one or more child node payloads using Gen3 templates."""
    print(f"\nProcessing template nodes from: {raw_path}")
    df_raw = pd.read_csv(raw_path, sep="\t")

    df_raw["individual_id"] = (
        df_raw["individual_id"].astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    df_raw = df_raw[df_raw["individual_id"].isin(valid_ids)].copy()
    print(f"  Loaded {len(df_raw):,} records after ID filter")

    # --- Structural Cleaning ---
    df = strip_whitespace_and_blanks(df_raw)
    df = clean_ids(df, "individual_id")

    # Cross-check against the already-generated subject payload
    master_subjects = pd.read_csv("payloads/payload_subject.tsv", sep="\t")
    valid_subject_ids = set(master_subjects["submitter_id"].astype(str))

    initial = len(df)
    df = df[df["individual_id"].isin(valid_subject_ids)].copy()
    dropped = initial - len(df)
    if dropped > 0:
        print(f"  Dropped {dropped:,} orphaned records (not in subject payload)")

    for node_name, template_path in template_mapping.items():
        with open(template_path) as f:
            template = json.load(f)

        dict_props = set(k.replace("*", "") for k in template.keys())
        matched_cols = list(dict_props & set(df.columns))

        if not matched_cols:
            print(f"  WARNING: no matching columns for node '{node_name}' — skipping")
            continue

        cols_to_keep = list(dict.fromkeys(matched_cols + ["individual_id"]))
        df_node = df[cols_to_keep].copy()

        # --- Apply node-specific mappings dynamically ---
        df_node = apply_enum_mappings(df_node, node_name, mappings)

        # Fill remaining missing/blank values with the standard 999 code
        fillable_cols = [c for c in df_node.columns if c != "individual_id"]
        df_node[fillable_cols] = df_node[fillable_cols].fillna("999-missing")

        # Create structural links
        df_node["subjects.submitter_id"] = df_node["individual_id"]
        df_node["submitter_id"] = (
            f"{node_name}-" + df_node["individual_id"] + "-" + df_node.index.astype(str)
        )
        df_node["type"] = node_name
        df_node = df_node.drop(columns=["individual_id"])

        out_path = f"payloads/payload_{node_name}.json"
        df_node.to_json(out_path, orient="records", indent=2)
        print(f"  -> payload_{node_name}.json: {len(df_node):,} records")


# ============================================================
# SECTION 5: PIPELINE ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("MADIVA Data Cleanup Pipeline")
    print("=" * 50)

    # --- Load Configuration ---
    print("\nLoading enum mappings from configuration...")
    try:
        mappings = load_enum_mappings("enum_mappings.yaml")
        print("Configuration loaded successfully.")
    except FileNotFoundError:
        print("ERROR: enum_mappings.yaml not found. Please run the schema crawler first.")
        exit(1)

    # --- Resolve valid IDs (intersection across source files) ---
    print("\nResolving valid subject IDs...")
    valid_ids = get_valid_ids(
        "raw/individuals_raw.tsv",
        "raw/ncdindicators_raw.tsv",
        "raw/individualsesindicators_raw.tsv",
        id_col="individual_id"
    )

    # --- Process master individuals table (subject + demographic) ---
    process_individuals_table(
        raw_path="raw/individuals_raw.tsv",
        valid_ids=valid_ids,
        mappings=mappings,
    )

    # --- Process NCD indicators table (labs, vitals, lifestyle, medical history) ---
    ncd_templates = {
        "ncd_vital":        "templates/submission_ncd_vital_template.json",
        "ncd_lab":          "templates/submission_ncd_lab_template.json",
        "medical_history":  "templates/submission_medical_history_template.json",
        "ncd_lifestyle": "templates/submission_ncd_lifestyle_exposure_template.json",
    }
    process_template_nodes(
        raw_path="raw/ncdindicators_raw.tsv",
        template_mapping=ncd_templates,
        valid_ids=valid_ids,
        mappings=mappings,
    )

    # --- Process SES table ---
    ses_templates = {
        "socioeconomic": "templates/submission_socioeconomic_template.json",
    }
    process_template_nodes(
        raw_path="raw/individualsesindicators_raw.tsv",
        template_mapping=ses_templates,
        valid_ids=valid_ids,
        mappings=mappings,
    )

    print("\n" + "=" * 50)
    print("Pipeline complete. Payloads written to payloads/")
    print("=" * 50)