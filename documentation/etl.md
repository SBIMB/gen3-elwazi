# Gen3 ETL Pipeline Documentation
This document outlines the ETL transformation process for the raw Postgres Madiva database. The script `all_cleanup.py`, formats some discrepancies and exports TSV files into Gen3-submission ready payloads, with ID normalisation and enum cleanup.

NB: This database is strictly access controlled and should only be accessed with adequate permissions.

---

## 1. Pipeline Overview

```
raw/individuals_raw.tsv ──► process_individuals_table() ──┬──► payloads/payload_subject.tsv
                                                            └──► payloads/payload_demographic.tsv

raw/ncdindicators_raw.tsv ──► process_template_nodes() ───┬──► payloads/payload_ncd_vital.tsv
        (driven by templates/*.json)                       ├──► payloads/payload_ncd_lab.tsv
                                                             ├──► payloads/payload_medical_history.tsv
                                                             └──► payloads/payload_lifestyle.tsv
```

All tables pass through a shared cleaning step (`clean_enums_and_ids`) before node-specific logic is applied, so ID formatting and negative-sentinel enum values can be handled the same throughout.

---

## 2. Core Cleaning: `clean_enums_and_ids(df, id_column_name='individual_id')`

Applied to every raw table before it's split into nodes. Two jobs:

- **ID normalisation:** casts the ID column to string and strips a trailing `.0` (a side effect of pandas reading numeric-looking IDs as floats). This is so IDs match consistently across all derived nodes when they're used as foreign keys (`subjects.submitter_id`, etc.).
- **Enum sentinel repair:** HDSS raw data encodes "missing"-type categories as negatives (`-333`, `-444`, `-777`, `-888`, `-999`), which sometimes arrive as ints, floats, or strings depending on how a column was typed. The fix maps every representation (`-999`, `-999.0`, `'-999'`, `'-999.00'`) to the corresponding positive Gen3 enum value (`999`).

This is a global `df.replace()`, so it runs across **all columns**, not just a named one, which is useful for catching the sentinel in whichever column it shows up in, but worth being aware of (see Limitations).

---

## 3. Parent Table: `process_individuals_table(raw_individuals_path)`

Reads `raw/individuals_raw.tsv` and produces two linked Gen3 nodes.

### Subject node → `payload_subject.tsv`
Columns kept: `individual_id, hdss_name, sex, dob, dod, date_into_dsa, date_out_of_dsa, father_id, mother_id`

- `individual_id` → renamed to `submitter_id`
- `hdss_name` → mapped to `projects.code` via `project_mapping` (currently `Agincourt`, `Nairobi` — **must match the Gen3 project codes exactly**)
- `sex` → mapped from numeric codes to Gen3 enum strings: `1→Female`, `2→Male`, `0→Other`
- `type` set to `'subject'`

### Demographic node → `payload_demographic.tsv`
Columns kept: `individual_id, ethnicity, sex, home_language, father_ethnicity, mother_ethnicity, father_home_language, mat_gfather_ethnicity, mat_gmother_ethnicity, mother_home_language`

- Linked to Subject via `subjects.submitter_id = individual_id`
- Own `submitter_id` generated as `demo-{individual_id}` (avoids collision with the Subject node's ID)
- `sex` mapped the same way as Subject
- `ethnicity` / `home_language` nulls filled with `'Unknown'` (required string fields in the dictionary can't be blank YET)
- `type` set to `'demographic'`

---

## 4. Template-Driven Nodes: `process_template_nodes(raw_path, template_mapping)`

A generic function that builds child nodes from a single raw file, using each node's Gen3 dictionary schema (as JSON) to decide which columns belong to it. This is what lets NCD vitals, labs, medical history, and lifestyle all come from the same `ncdindicators_raw.tsv` without four different scripts. This was how the data dictionary was structured, given that some categories in the codebook are quite long.

For each `(node_name, template_path)` pair:

1. Load the node's JSON schema template and strip `*` (required-field markers) from key names.
2. Intersect the schema's property names with the raw dataframe's columns → `exact_matches`.
3. Skip the node entirely if there's no overlap.
4. Keep only the matched columns (+ `individual_id`), drop rows where **all** matched fields are null (`dropna(how='all')`), skip the node if nothing remains.
5. Link to Subject via `subjects.submitter_id`.
6. Build a unique `submitter_id` as `{node_name}-{individual_id}-{row_index}` — the row index suffix allows multiple records per individual (e.g. repeated vitals over time).
7. Write out `payloads/payload_{node_name}.tsv`.

Currently wired up for the NCD templates:
```python
ncd_templates = {
    'ncd_vital': 'templates/submission_ncd_vital.json',
    'ncd_lab': 'templates/submission_ncd_lab.json',
    'medical_history': 'templates/submission_medical_history.json',
    'lifestyle': 'templates/submission_ncd_lifestyle.json'
}
```

---

## 5. Execution Order

```python
process_individuals_table(raw_individuals_path='raw/individuals_raw.tsv')

process_template_nodes(
    raw_path='raw/ncdindicators_raw.tsv',
    template_mapping=ncd_templates
)

# Commented out — not yet run:
# process_template_nodes('individualsesindicators_raw.tsv', ses_templates)
# process_template_nodes('ncdindicators_raw.tsv', ncd_templates)
```

Output payloads land in `payloads/`, ready for Sheepdog submission (`.tsv`, tab-separated, `%g` float formatting to avoid stray decimals in IDs/enums).

---

## 6. Known Limitations / Things to Check Before Production Run

These are dev-time artifacts currently baked into the script that are worth resolving before this runs against the full dataset:

- **Row limits are still active.**
  - `process_individuals_table` calls `df_raw.head()` (default = 5 rows) — the whole Subject/Demographic run is currently only processing **5 individuals**, per the inline `# NOTE: Remove this line` comment.
- **Hardcoded relative paths** (`raw/...`, `templates/...`, `payloads/...`) assume the script is run from a specific working directory.
- **Global `.replace()` for enum fixes** in `clean_enums_and_ids` runs across *every* column in the dataframe, not just designated enum columns. This is convenient but means any column that legitimately contains the number `-999` (unlikely, but e.g. a genuine numeric measurement) would get silently rewritten to `999`.
- **`project_mapping` is a strict allow-list.** Any `hdss_name` value not in `{'Agincourt', 'Nairobi'}` will map to `NaN` for `projects.code`, which will fail Sheepdog's project-link validation rather than raising an obvious error earlier in the script. Need to add an assertion/warning for unmapped site names.
- **No logging of dropped rows.** The `dropna(subset=exact_matches, how='all')` step in the template function silently discards fully-empty records — useful to know the count for QA, especially before a demo.

---

## 7. Output Summary

| Node | Output File | Linked Via |
|---|---|---|
| Subject | `payloads/payload_subject.tsv` | `projects.code` |
| Demographic | `payloads/payload_demographic.tsv` | `subjects.submitter_id` |
| NCD Vital | `payloads/payload_ncd_vital.tsv` | `subjects.submitter_id` |
| NCD Lab | `payloads/payload_ncd_lab.tsv` | `subjects.submitter_id` |
| Medical History | `payloads/payload_medical_history.tsv` | `subjects.submitter_id` |
| Lifestyle | `payloads/payload_lifestyle.tsv` | `subjects.submitter_id` |
| Socioeconomic *(pending)* | *not yet generated* | `subjects.submitter_id` |
# HDSS → Gen3 ETL Pipeline Documentation

**Script:** `all_cleanup.py`
**Purpose:** Transforms raw HDSS (Health and Demographic Surveillance System) TSV exports into Gen3-submission-ready node payloads (Subject, Demographic, and template-driven clinical/socioeconomic nodes), with ID normalisation and enum cleanup applied consistently across every table.

---

## 1. Pipeline Overview

```
raw/individuals_raw.tsv ──► process_individuals_table() ──┬──► payloads/payload_subject.tsv
                                                            └──► payloads/payload_demographic.tsv

raw/ncdindicators_raw.tsv ──► process_template_nodes() ───┬──► payloads/payload_ncd_vital.tsv
        (driven by templates/*.json)                       ├──► payloads/payload_ncd_lab.tsv
                                                             ├──► payloads/payload_medical_history.tsv
                                                             └──► payloads/payload_lifestyle.tsv
```

All tables pass through a shared cleaning step (`clean_enums_and_ids`) before node-specific logic is applied, so ID formatting and negative-sentinel enum values are handled identically everywhere.

---

## 2. Core Cleaning: `clean_enums_and_ids(df, id_column_name='individual_id')`

Applied to every raw table before it's split into nodes. Two jobs:

- **ID normalisation:** casts the ID column to string and strips a trailing `.0` (a side effect of pandas reading numeric-looking IDs as floats). This guarantees IDs match consistently across all derived nodes when they're used as foreign keys (`subjects.submitter_id`, etc.).
- **Enum sentinel repair:** HDSS raw data encodes "missing"-type categories as negative sentinels (`-333`, `-444`, `-777`, `-888`, `-999`), which sometimes arrive as ints, floats, or strings depending on how a column was typed. The fix maps every representation (`-999`, `-999.0`, `'-999'`, `'-999.00'`) to the corresponding positive Gen3 enum value (`999`).

This is a global `df.replace()`, so it runs across **all columns**, not just a named one — useful for catching the sentinel in whichever column it shows up in, but worth being aware of (see Limitations).

---

## 3. Parent Table: `process_individuals_table(raw_individuals_path)`

Reads `raw/individuals_raw.tsv` and produces two linked Gen3 nodes.

### Subject node → `payload_subject.tsv`
Columns kept: `individual_id, hdss_name, sex, dob, dod, date_into_dsa, date_out_of_dsa, father_id, mother_id`

- `individual_id` → renamed to `submitter_id`
- `hdss_name` → mapped to `projects.code` via `project_mapping` (currently `Agincourt`, `Nairobi` — **must match your Gen3 project codes exactly**)
- `sex` → mapped from numeric codes to Gen3 enum strings: `1→Female`, `2→Male`, `0→Other`
- `type` set to `'subject'`

### Demographic node → `payload_demographic.tsv`
Columns kept: `individual_id, ethnicity, sex, home_language, father_ethnicity, mother_ethnicity, father_home_language, mat_gfather_ethnicity, mat_gmother_ethnicity, mother_home_language`

- Linked to Subject via `subjects.submitter_id = individual_id`
- Own `submitter_id` generated as `demo-{individual_id}` (avoids collision with the Subject node's ID)
- `sex` mapped the same way as Subject
- `ethnicity` / `home_language` nulls filled with `'Unknown'` (required string fields in the dictionary presumably can't be blank)
- `type` set to `'demographic'`

---

## 4. Template-Driven Nodes: `process_template_nodes(raw_path, template_mapping)`

A generic function that builds any number of child nodes from a single raw file, using each node's Gen3 dictionary schema (as JSON) to decide which columns belong to it. This is what lets NCD vitals, labs, medical history, and lifestyle all come from the same `ncdindicators_raw.tsv` without four bespoke scripts.

For each `(node_name, template_path)` pair:

1. Load the node's JSON schema template and strip `*` (required-field markers) from key names.
2. Intersect the schema's property names with the raw dataframe's columns → `exact_matches`.
3. Skip the node entirely if there's no overlap.
4. Keep only the matched columns (+ `individual_id`), drop rows where **all** matched fields are null (`dropna(how='all')`), skip the node if nothing remains.
5. Link to Subject via `subjects.submitter_id`.
6. Build a unique `submitter_id` as `{node_name}-{individual_id}-{row_index}` — the row index suffix allows multiple records per individual (e.g. repeated vitals over time).
7. Write out `payloads/payload_{node_name}.tsv`.

Currently wired up for the NCD templates:
```python
ncd_templates = {
    'ncd_vital': 'templates/submission_ncd_vital.json',
    'ncd_lab': 'templates/submission_ncd_lab.json',
    'medical_history': 'templates/submission_medical_history.json',
    'lifestyle': 'templates/submission_ncd_lifestyle.json'
}
```

A second set (`ses_templates`, socioeconomic) is defined but **not yet invoked** — see Limitations below.

---

## 5. Execution Order

```python
process_individuals_table(raw_individuals_path='raw/individuals_raw.tsv')

process_template_nodes(
    raw_path='raw/ncdindicators_raw.tsv',
    template_mapping=ncd_templates
)

# Commented out — not yet run:
# process_template_nodes('individualsesindicators_raw.tsv', ses_templates)
# process_template_nodes('ncdindicators_raw.tsv', ncd_templates)
```

Output payloads land in `payloads/`, ready for Sheepdog submission (`.tsv`, tab-separated, `%g` float formatting to avoid stray decimals in IDs/enums).

---

## 6. Known Limitations / Things to Check Before Production Run

These are dev-time artifacts currently baked into the script that are worth resolving before this runs against the full dataset:

- **Row limits are still active.**
  - `process_individuals_table` calls `df_raw.head()` (default = 5 rows) — the whole Subject/Demographic run is currently only processing **5 individuals**, per the inline `# NOTE: Remove this line` comment.
  - `process_template_nodes` calls `df_raw.head(100)` — capped at 100 rows, with no corresponding removal note. Both will need to go before a real submission.
- **Hardcoded relative paths** (`raw/...`, `templates/...`, `payloads/...`) assume the script is run from a specific working directory — worth double-checking against wherever this runs in your k3s/CI context.
- **`ses_templates` path is inconsistent** with the NCD templates — it points to `'submission_socioeconomic.json'` (no `templates/` prefix), and the corresponding `process_template_nodes()` call is commented out, so socioeconomic nodes aren't generated yet.
- **Global `.replace()` for enum fixes** in `clean_enums_and_ids` runs across *every* column in the dataframe, not just designated enum columns. This is convenient but means any column that legitimately contains the number `-999` (unlikely, but e.g. a genuine numeric measurement) would get silently rewritten to `999`.
- **`project_mapping` is a strict allow-list.** Any `hdss_name` value not in `{'Agincourt', 'Nairobi'}` will map to `NaN` for `projects.code`, which will likely fail Sheepdog's project-link validation rather than raising an obvious error earlier in the script. Worth adding an assertion/warning for unmapped site names.
- **Sex mapping only covers `0/1/2`.** Any other/missing value will come through as `NaN` in the Gen3 enum field, which may trip required-field validation depending on your dictionary.
- **No logging of dropped rows.** The `dropna(subset=exact_matches, how='all')` step in the template function silently discards fully-empty records — useful to know the count for QA, especially before a demo.
- Some standardisations have been assumed and do not directly match the codebook, namely in the handling of `null` values.
---
