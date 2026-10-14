# Gen3 Bulk Data Upload: Standard Operating Procedure (SOP)

This document outlines the end-to-end process for uploading large-scale datasets (e.g., Terabytes of FASTQ files) from a high-performance computing (HPC) cluster into a Gen3 Data Commons.

This guide assumes you are working in a Linux terminal and using the SLURM job scheduler.

## Prerequisites: Configuring the `gen3-client`

Before you can upload any data, you must authenticate the `gen3-client` with your specific Gen3 Data Commons environment. This is done by downloading an API key and creating a local profile.

### 1. Download Your API Key

1. Log into your Gen3 Data Portal via your web browser (e.g., `https://gen3-dev.core.wits.ac.za`).
2. Navigate to the **Profile** page (usually found in the top right corner menu).
3. Click **Create API Key**.
4. A prompt will appear with your Key ID and API Key. Click **Download json** to save the file to your computer. It will download as `credentials.json`.
5. Transfer this `credentials.json` file to your HPC cluster (e.g., into your `gen3-elwazi` folder) using SCP, SFTP, or your cluster's web interface.

### 2. Configure the Client Profile

In your cluster terminal, use the downloaded `credentials.json` to configure a profile. A profile securely stores your authentication tokens so you don't have to provide the key every time you run a command.

Run the following configuration command in the directory where your `gen3-client` executable is located:

```bash
./gen3-client configure --profile=madiva --cred=credentials.json --apiendpoint=https://gen3-dev.core.wits.ac.za
```
*(Note: Replace `madiva` with whatever you want to name your profile, and update the `--apiendpoint` to match your specific Gen3 portal URL).*

**Success Indicator:** The terminal will confirm that your profile has been successfully configured. The client will securely store this configuration in a hidden folder at `~/.gen3/`.

---

## Phase 1: Generating the Data Manifest

Before uploading data to Gen3, you must calculate the exact file size and MD5 hash for every file. This metadata is required later to link the files to clinical subjects in the Gen3 graph database (Sheepdog).

Because calculating MD5 hashes for massive files takes a long time, we use a bash script to parallelize the work and submit it to a compute node.

### 1. Create the Manifest Script

Create a script named `generate_manifest.sh` that will scan your data directory and calculate hashes in parallel.


#### Find all files and process them using multiple CPU cores


Make the script executable:

```bash
chmod +x generate_manifest.sh
```

### 2. Submit the Manifest Job to SLURM

Create a wrapper script to run the manifest generation on a compute node so it doesn't overload your user interface (UI) node.

```bash
nano submit_manifest.sh
```

Paste the following SLURM configuration. **Note:** Ensure `--cpus-per-task` matches the `CORES` variable in your script.


Submit the job and monitor it:

```bash
sbatch submit_manifest.sh
squeue -u $USER
tail -f manifest.csv
```

## Phase 2: Testing the `gen3-client`

Before submitting a multi-terabyte upload, always test a single small file to ensure your `gen3-client` is authenticated and the network paths are open.

Run the `gen3-client` `upload` command, pointing it directly to one file. You must include `./` before the command if the executable is in your current folder.

```bash
./gen3-client upload --profile=madiva --upload-path=/path/to/your/data/test_file.fastq.gz
```

**Success Indicators:**

1. The terminal displays a progress bar reaching 100%.
2. The terminal prints a success message containing a newly minted GUID (e.g., `PREFIX/1234-abcd-...`).
3. You can find the file listed as "Ready" in the Gen3 Data Portal.

## Phase 3: The Bulk Data Upload

Once the test is successful, you can upload the entire directory. The `gen3-client` is designed in Go, meaning it automatically manages its own multi-threading and file chunking.

### 1. Create the Upload Job Script

Create a new SLURM script for the bulk upload.

```bash
nano submit_upload.sh
```

Paste the following configuration. We request 2 CPUs, which is plenty for the network management threads.


### 2. Submit and Monitor the Upload

Submit the job to the cluster:

```bash
sbatch submit_upload.sh
```

You can monitor the live upload progress bars by tailing the SLURM output file:

```bash
tail -f upload_progress_<JOB_ID>.out
```

## Phase 4: Extracting GUIDs for Metadata Mapping

When files upload successfully, they sit in the storage bucket as "orphans." The Gen3 frontend portal will show their file sizes as "generating..." until you link these files to clinical patients using a Data Node TSV.

To build this TSV, you need the permanent GUIDs that the system generated during the upload. The `gen3-client` saves these securely in a hidden file called `succeeded_log.json`.

### 1. Parse the JSON Log

Use the `jq` command-line tool to extract just the filenames and their new GUIDs, saving them to a clean text file:

```bash
jq -r '.[] | [.file_name, .object_id] | @tsv' ~/.gen3/succeeded_log.json > extracted_guids.tsv
```

### 2. Build the Sheepdog TSV

You now have two critical files:

1. `manifest.csv` (Contains `file_name`, `file_size`, and `md5`)
2. `extracted_guids.tsv` (Contains `file_name` and `object_id`/GUID)

**Next Steps:**

1. Download both files to your local computer.
2. Merge them in Excel (or Python/R) matching by the `file_name`.
3. Add a column for your clinical IDs (e.g., `samples.submitter_id`).
4. Add a column for the Gen3 node type (e.g., `type: submitted_unaligned_reads`).
5. Save as a TSV and upload it to the Data Submission portal (Sheepdog).

Once Sheepdog processes the TSV, your files are officially linked to the clinical data, and the Gen3 frontend will update to display the correct file sizes and hashes!