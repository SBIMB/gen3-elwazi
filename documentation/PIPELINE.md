# Data Upload Pipeline

This document outlines the step-by-step procedure required to extract, clean, and submit a new batch of data to the Gen3 portal. 

## Execution Steps

1. **Copy Raw Data**
   Extract the latest raw `.tsv` files from the Postgres database and place them into the local `raw/` directory. *Ensure you have the required access permissions before handling this data.*

2. **Run Dictionary Updates**
   If there have been any upstream changes to the Gen3 data dictionary, pull the latest schemas into your environment so the ETL process reflects current definitions.

3. **Build the Enum Mapping Config**
   Execute the schema crawler to generate the `enum_mappings.yaml` file. This automatically extracts valid enums from `schema.json` and configures the global negative-sentinel rules.
   ```bash
   python build_mappings.py
   ```

4. **Run the Clean Data Script**
   Execute the main ETL script. This will normalize IDs, filter out orphan records, apply the enum mappings, and output the final TSVs to the `payloads/` directory.
   ```bash
   python all_cleanup.py
   ```

5. **Verify Submission Order**
   Check `submission_order.yaml` to ensure you have the correct parent-to-child upload sequence (e.g., Subjects must always be uploaded before Demographics or NCD Indicators).

6. **Submit the Data**
   Use the Python SDK upload script to post the generated payloads to Sheepdog according to the submission order.
   ```bash
   python data_upload.py
   ```

7. **Update the Frontend**
   As required, push any necessary configuration updates to GitOps, the portal services, or the ETL mappings to reflect the newly submitted data models.
