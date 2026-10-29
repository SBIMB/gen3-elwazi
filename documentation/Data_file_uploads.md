# Gen3 Bulk Data Upload

This document outlines the end-to-end process for uploading large-scale datasets (e.g., Terabytes of FASTQ/BAM files) from the cluster into Gen3. 

Specifically, this file looks at the custom process for interfacing with the local storage bucket, using the **AWIGEN-Microbiome** dataset.

## Prerequisites: Configuring the `gen3-client`

Before uploading any data, authenticating the `gen3-client` is required - this is likely to have been completed already if any metadata is uploaded.

### 1. Download API Key

1. Log into the Gen3 Data Portal via a web browser.
2. Navigate to the **Profile** page.
3. Click **Create API Key**.
4. Click **Download json** to save the file (`credentials.json`).
5. Transfer this `credentials.json` file to cluster using ```scp``` or ```rsync```.

### 2. Configure the Client Profile

In cluster terminal, use the downloaded `credentials.json` to configure a secure profile:

```bash
./gen3-client configure --profile=madiva --cred=credentials.json --apiendpoint=https://gen3-dev.core.wits.ac.za
```

*(Note: Replace `madiva` with relevant preferred profile name, and update the `--apiendpoint` to match the portal URL).*

## Phase 1: Dictionary Configuration 

*(Note: This step is being included as it was part of the latest deployment process - typical structures of deplpoyment would have this planned out and configured already.)*

Before generating metadata, the Gen3 data dictionary must be configured to accept the exact properties you intend to submit.

1. **Update Dictionary YAML:** Open `data_file.yaml` and ensure `file_name`, `file_size`, `md5sum`, and `object_id` are explicitly defined within the `properties` block.
2. **Recompile and Upload:** Go about the normal process of pushing to Github and redeploying the `sheepdog` and `peregrine` deployments. This process is described in detail in **Data_dictionary.md**.

## Phase 2: Generating the Data Manifest

Before mapping data in Gen3, the MD5 hash and exact file size must be calculated. This step is necessary since AWS services automatically do this and feed it into the Gen3 client. The local bucket does not.

*Note: For multipart uploads to local MinIO storage (like our 1.4 TB dataset), the MinIO `ETag` is NOT a valid MD5 hash. You must compute the true MD5 hash on the HPC cluster using the raw files.*

### 1. Create the Manifest Script
Use`generate_manifest.sh` to parallelise MD5 hashing. This script handles spaces in filenames securely.

```bash
#!/bin/bash
# Find all files and process them using multiple CPU cores on a single node
find /path/to/data -type f -name "*.fastq.gz" -print0 | xargs -0 -n 1 -P 8 -I {} sh -c 'echo "\"{}\",$(stat -c%s \"{}\"),$(md5sum \"{}\" | cut -d" " -f1)"' > manifest.csv
```
Make the script executable: `chmod +x generate_manifest.sh`

### 2. Submit the Manifest Job to SLURM

Submit the script via a SLURM wrapper (`sbatch submit_manifest.sh`). 

## Phase 3: Testing & Bulk Data Upload

### 1. Test the Network Path

Always test a single file to ensure valid `gen3-client` authentication:

```bash
./gen3-client upload --profile=madiva --upload-path=/path/to/your/data/test_file.fastq.gz
```
*Success Indicator:* The terminal prints a newly minted GUID (e.g., `PREFIX/1234-abcd-...`). **Note: `PREFIX/` is the literal prefix string configured in Indexd, not a placeholder.**

### 2. The Bulk Upload
This is necessary to push the physical files into local MinIO storage and generate their corresponding placeholder records in the Indexd database.

Submit a SLURM job to upload the entire directory. 

```bash
./gen3-client upload-multiple --profile=madiva --upload-path=/path/to/your/data/
```


## Phase 3: Clinical ID Mapping & Orphan Handling
Link the newly generated file IDs to their corresponding clinical patient records, and safely separate out any unmapped files.

Run the  custom Python mapping script `tsv_gen.py` to parse Awigen IDs from the FASTQ filenames and perform an inner join against the stage2 clinical metadata.

* Mapped Files: Proceed to Phase 4.

* Orphan Files: Files lacking clinical metadata (e.g., 717 unmapped files) must be isolated. Do not submit these to Sheepdog, as they will cause database validation errors. Leave their Indexd records as-is for future archival, or explicitly delete them via the Indexd API.

## Phase 4: Extracting GUIDs & Mapping Clinical Data

When files upload successfully to local MinIO storage, Indexd generates "blank" database records. This step fills in the missing hashes and file sizes in the database, for Sheepdog to accept them.

### 1. Extract the GUIDs

The `gen3-client` saves permanent GUIDs in a hidden log. Extract them (verify the JSON structure of ghd `succeeded_log.json` first, as it may be a map keyed by file path rather than a flat array):

```bash
# Example jq for flat array structure
jq -r '.[] | [.file_name, .object_id] | @tsv' ~/.gen3/succeeded_log.json > extracted_guids.tsv
```

### 2. Map to Clinical IDs & Handle Orphans (`tsv_gen.py`)

Using a custom Python script, perform an inner join between the `manifest.csv` (sizes/hashes), `extracted_guids.tsv` (Indexd GUIDs), and the clinical metadata mapping sheet (e.g., `stage2`).

*   **Mapped Files:** Generate a JSON array for files with matching clinical IDs. Format parent links correctly (e.g., `"subjects": [{"submitter_id": "AWIGEN_ID"}]`). Save as `submission_files_node.json`. (JSON is preferred over TSV to bypass frontend parser issues with empty `type` columns and dot-notation link failures).
*   **Orphan Files:** Files lacking clinical metadata (e.g., the 717 unmapped files from the Microbiome data) will remain in MinIO with blank Indexd records. **Do not attempt to submit orphans to Sheepdog**, as this will trigger graph validation errors. 

Need to document project's policy for archiving or deleting these records!

## Phase 5: Patching Indexd Blank Records

On local k3s clusters without AWS Lambda triggers, Indexd records remain in a "blank" state (`size: null`, `hashes: {}`). Sheepdog will reject the JSON payload until these fields are populated.

### Execution Strategy: The Indexd `PUT` Update

Run a Python script utilising the Gen3 internal API to populate the blank records.

**Critical Requirements for the Script:**
1.  **Record Revision (`rev`):** Query the Indexd record first to obtain its current `rev` string. The update request must be formatted as `PUT /index/blank/<guid>?rev=<rev>`.
2.  **Authorisation (`authz`):** Explicitly set the field (e.g., `["/programs/MADIVA/projects/Agincourt"]`). If `authz` is left empty (`[]`), subsequent file downloads via Fence will fail due to lacking permissions.
3.  **URL Encoding:** The Gen3 API router breaks on the unencoded forward slash in the GUID. You must URL-encode the GUID (`urllib.parse.quote(guid, safe="")`) for all API requests.

### Verification Gate (CRITICAL)
Before proceeding to Sheepdog submission, verify that exactly zero blank records remain among your mapped GUIDs. Run an automated check comparing your submission GUID list against the Indexd database to confirm `hashes` and `size` are populated. Proceeding with a single blank record will crash the submission.


## Phase 6: API Sheepdog Submission

Use the Sheepdog API directly via a Python script (`submit_metadata.py`) rather than the Data Portal UI. This is to avoid overwhelming the frontend and ensuring no data submission errors. Sheepdog will now link the correct subjects to the correct file IDs.

### Direct API Submission

Submit the `submission_files_node.json` payload using HTTP `PUT` requests. `PUT` acts idempotently, updating existing nodes safely. 

```python
submit_url = f"{COMMONS_URL}/api/v0/submission/{PROGRAM}/{PROJECT}/"
# WARNING: Do not use verify=False in production. Point to your institutional CA bundle.
requests.put(submit_url, headers=headers, json=chunk, verify='/path/to/ca-bundle.crt')
```
*Note: The access token generated from your credentials expires quickly. For long, chunked submissions, ensure your script includes logic to refresh the token dynamically.* CHECK!

## Phase 7: ETL & Frontend Configuration

Even though the files are successfully mapped in the PostgreSQL graph, the frontend Data Explorer (Guppy) cannot see them until the data is flattened into Elasticsearch and explicitly whitelisted.

### 1. Update ETL Mappings (`etl-mappings-v2.yaml`)

Add the new data node to the ETL mappings. The `root` property must perfectly match the literal node ID defined in the data dictionary (e.g., `submitted_unaligned_reads`).

### 2. Whitelist in Guppy (`values.yaml`)

*   Add the new index to Guppy's `indices` array in `values.yaml`.
*   Append the array config to the `configIndex` string. **Do not use spaces after commas** (e.g., `"subject-array-config,unaligned_reads-array-config"`).

### 3. Update Portal UI (`gitops.json`)

Append a new configuration block to the `explorerConfig` array in the`gitops` section of `values.yaml` to render the actual "Data Files" tab.

### 4. Final Rollout

Restart the frontend services to clear cached schemas and render the new data:

```bash
kubectl rollout restart deployment/guppy
kubectl rollout restart deployment/portal-deployment
```