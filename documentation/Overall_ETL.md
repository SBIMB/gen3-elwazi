# MADIVA Gen3 ETL Pipeline Documentation

**Scripts:** `all_cleanup.py`, `build_mappings.py`
**Purpose:** Transforms raw Postgres database TSV exports into Gen3-submission-ready node payloads (Subject, Demographic, and template-driven clinical/socioeconomic nodes). The pipeline handles automated schema-driven enum mapping, global negative-sentinel repair, and ID anonymisation.

---

## 1. Pipeline Overview

The ETL process relies on dynamically generated mappings and cross-file ID validation before building the payloads.

```text
schema.json ──► build_mappings.py ──► enum_mappings.yaml

raw/individuals_raw.tsv ──► process_individuals_table() ──┬──► payload_subject.tsv
                                                            └──► payload_demographic.tsv

raw/ncdindicators_raw.tsv ──► process_template_nodes() ───┬──► payload_ncd_vital.tsv
        (driven by json)                                   ├──► payload_ncd_lab.tsv
                                                             ├──► payload_medical_history.tsv
                                                             └──► payload_ncd_lifestyle.tsv

raw/individualsesindicators_raw.tsv ──► process_template_nodes() ──► payload_socioeconomic.tsv
```

---

## 2. Configuration & Mappings: `enum_mappings.yaml`

Instead of hardcoding translations, the pipeline automatically derives valid Gen3 enums directly from the `schema.json`. 

- **Dynamic Extraction:** The mapping script hunts for `enum` lists within the schema properties (including nested `anyOf`/`oneOf` structures). It extracts the leading numbers from Gen3 string enums (e.g., mapping `333` to `"333-don't know"`).
- **Global Sentinels:** Standard negative missing codes (`-333`, `-444`, `-777`, `-888`, `-999`, `-111`, `-222`) are converted to their positive counterparts globally before node-specific mappings are applied.

---

## 3. Core Cleaning & Valid ID Resolution

Before any node processing occurs, the data is standardized:
- **Whitespace Stripping:** Blank strings are replaced with `NaN` to ensure correct `fillna()` application downstream.
- **ID Normalisation:** Float artifacts (e.g., `.0`) and whitespace are stripped from the `individual_id` column.
- **Anonymisation:** The normalise ID undergoes a one-way SHA256 hash with a configured salt, outputting a consistent 10-character string across runs.
- **Valid ID Intersection:** `get_valid_ids()` computes the intersection of subjects across `individuals_raw.tsv`, `ncdindicators_raw.tsv`, and `individualsesindicators_raw.tsv`. Only records belonging to this intersected valid ID set are processed.

---

## 4. Parent Table: `process_individuals_table()`

Reads `raw/individuals_raw.tsv` and produces two linked Gen3 nodes. Unmapped or missing values are filled with the standard `"999-missing"` code.

### Subject node → `payload_subject.tsv`
- `individual_id` → renamed to `submitter_id`.
- `hdss_name` → mapped to `projects.code` via `PROJECT_MAP` (currently `Agincourt` and `Nairobi`).
- `type` set to `'subject'`.

### Demographic node → `payload_demographic.tsv`
- Linked to Subject via `subjects.submitter_id = individual_id`.
- Own `submitter_id` generated as `demo-{individual_id}`.
- `type` set to `'demographic'`.

---

## 5. Template-Driven Nodes: `process_template_nodes()`

Builds child nodes from raw files using JSON dictionary schemas to map columns. 

1. Validates records against the intersected `valid_ids` list and drops any orphaned records that don't exist in the generated `payload_subject.tsv`.
2. Keeps only columns that overlap between the raw dataframe and the template's properties.
3. Applies the node-specific enum translations from `enum_mappings.yaml`.
4. Builds a unique `submitter_id` as `{node_name}-{individual_id}-{row_index}`.
5. Outputs NCD nodes (`ncd_vital`, `ncd_lab`, `medical_history`, `ncd_lifestyle`) and the SES node (`socioeconomic`).

---

## 6. Known Limitations

- **Hardcoded Relative Paths:** The pipeline assumes strict working directory structures (`raw/`, `templates/`, `payloads/`).
- **Strict Project Allow-List:** `PROJECT_MAP` only contains `Agincourt` and `Nairobi`. Unmapped sites will return `NaN` and fail Gen3 validation.
