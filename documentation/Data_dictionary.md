# MADIVA Gen3 Data Dictionary Management Guide

This document outlines the architecture, compilation, deployment, and validation workflows for the custom MADIVA data dictionaries on our localised single-node cluster.

---

## 1. Directory Structure & Architecture

The dictionary schemas are managed on the `dev` branch as individual YAML files before being compiled into a unified schema. Note that '_definitions.yaml', '_settings.yaml' and '_terms.yaml' are taken from "https://github.com/uc-cdis/datadictionary/tree/develop/gdcdictionary/schemas"

```text
~/gen3-elwazi/test_data_dictionary/
├── _definitions.yaml          # Global property definitions and reusable blocks
├── _settings.yaml             # Dictionary-wide configurations (submittable types)
├── _terms.yaml                # Property descriptions and link definitions
├── program.yaml               # Administrative root node
├── project.yaml               # Study-level organisation node
├── subject.yaml               # Core participant node linked to projects
├── demographics.yaml          # Participant metadata
├── clinical_history.yaml      # Baseline clinical evaluations
├── vital_signs.yaml           # Physical clinical metrics
├── labs.yaml                  # Laboratory and assay results
├── lifestyle.yaml             # Behavioral and environmental metrics
└── ses.yaml                   # Socioeconomic status tracking

```

### The Graph Hierarchy

Gen3 utilises a strict graph database model. Nodes cannot exist in isolation; they must form explicit upstream links. For example, the `subject` node requires a direct structural edge pointing back to a valid `project` node code.

---

## 2. Compilation and Remote Hosting

Because our localised deployment optimises system resources by stripping out a standalone data dictionary compilation container, the system relies on a pre-compiled JSON blueprint hosted remotely.

1. **Local Compilation:** Modify or create individual node YAML files on your local development machine. Compile them into a single `schema.json` file using the Gen3 dictionary utilities and command `python3 compile_dictionary.py`.
2. **The Cloud Source of Truth:** The compiled `schema.json` is pushed to the `main` branch of the remote repository (`https://github.com/SBIMB/gen3-elwazi/test_data_dictionary`).
3. **Cluster Reference:** The cluster’s `values.yaml` file contains a direct tracking link to this remote file. When microservices scale or restart, they pull the latest JSON blueprint directly from this URL.

---

## 3. The Deployment Pipeline ("The Hard Reset")

Simply updating the `schema.json` file in GitHub **will not** instantly update the active cluster. Gen3 microservices aggressively cache the data dictionary at boot time to maintain high performance.

To force the system to drop its old cache and read new MADIVA dictionary schemas, execute a targeted restart of the core microservices in this exact sequence:

### Step 1: Drain and Rebuild the Backend Graphs

The data ingestion engine (`sheepdog`) and the GraphQL query translation layer (`peregrine`) must be forced to re-read the schema first to establish internal database edges.

```bash
kubectl delete pods -l app=sheepdog
kubectl delete pods -l app=peregrine

```

*Action: Wait 30–60 seconds. Verify the new pods reach a status of `Running` via `kubectl get pods` or the `k9s` dashboard before moving to the next step.*

### Step 2: Flush the Front-End Portal UI

Once the data APIs are operating on the new schema, restart the user interface so it can dynamically generate fresh TSV upload templates matching your fields. This will typically only run without errors within 2 minutes.

```bash
kubectl delete pods -l app=portal

```

---

## 4. Validation & Smoke Testing Strategies

Before verifying your data dictionary updates with live research data, execute these structural validation checks:

* **The Template Check:** Open the Data Portal website in an **Incognito Browser Window** (to bypass local browser storage). Navigate to the submission dashboard and attempt to download the TSV template for a newly created node (e.g., `vital_signs.yaml`). If the spreadsheet contains your custom columns, the schema is successfully live.
* **GraphiQL Verification:** Navigate to `https://gen3-dev.core.wits.ac.za/query` and run an empty schema check. Confirm that your newly added nodes appear in the autocomplete data model options on the left-hand editor panel. Ensure that the query is using the `**Graph Model**` and not the `**Flat Model**`.

---

