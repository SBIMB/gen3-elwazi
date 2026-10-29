import os
import yaml
import json
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
import time

def load_submission_sequence(config_path="submission_order.yaml"):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config["submission_order"]

def refresh_token(credentials_path, endpoint):
    try:
        with open(credentials_path, 'r') as f:
            credentials = json.load(f)

        api_key = credentials.get("api_key")
        token_url = f"{endpoint}/user/credentials/api/access_token"

        response = requests.post(token_url, json={"api_key": api_key})
        response.raise_for_status()

        print("         [System] Successfully generated new Gen3 token.")
        return response.json().get("access_token")

    except Exception as e:
        print(f"CRITICAL ERROR: Failed to refresh token. Check credentials.json :) with error: {e}")
        exit(1)


def build_subject_routing_map(sub_client, program, active_projects):
    """Preload submitter_id -> project mapping straight from Gen3, using
    paginated (non-sorted, cheap) queries. This works regardless of
    whether 'subject' is included in this run's submission order -- it
    does NOT depend on processing a local subject payload file, unlike
    the old approach of building the map only while uploading subjects.

    IMPORTANT: explicitly retries on an 'error' response instead of
    treating it as end-of-data. A transient Sheepdog/Peregrine hiccup
    (restart, service failure, DB under load) returns a dict with no
    'data' key -- silently reading that as "[]" stops pagination early
    and truncates the map, which then makes every subsequent child-node
    upload wrongly report real subjects as 'not found in routing map'."""
    print("\nBuilding subject routing map from existing Gen3 records...")
    routing_map = {}
    page_size = 1000
    max_retries = 5

    for proj in active_projects:
        project_id = f"{program}-{proj}"
        offset = 0
        total = 0
        print(f"Fetching subjects for {project_id}...")
        while True:
            gql_query = f'''
            {{
              subject (project_id: "{project_id}", first: {page_size}, offset: {offset}, order_by_asc: "submitter_id") {{
                submitter_id
              }}
            }}
            '''

            page = None
            for attempt in range(max_retries):
                result = sub_client.query(gql_query)

                if "error" in result:
                    wait = 5 * (attempt + 1)
                    print(f"    [retry] subject offset={offset} -> {result['error']} "
                          f"(attempt {attempt + 1}/{max_retries}, waiting {wait}s)")
                    time.sleep(wait)
                    continue

                if "data" not in result or result["data"].get("subject") is None:
                    wait = 5 * (attempt + 1)
                    print(f"    [retry] subject offset={offset} -> unexpected response {result} "
                          f"(attempt {attempt + 1}/{max_retries}, waiting {wait}s)")
                    time.sleep(wait)
                    continue

                page = result["data"]["subject"]
                break

            if page is None:
                raise RuntimeError(
                    f"Giving up building routing map for {project_id} at offset={offset} "
                    f"after {max_retries} failed attempts. Refusing to proceed with a "
                    f"partial routing map -- check Sheepdog/Peregrine health first."
                )

            if not page:
                break

            for r in page:
                routing_map[r["submitter_id"]] = proj
            total += len(page)
            offset += len(page)  # advance by actual returned count, not
                                   # requested page_size -- Peregrine can
                                   # cap 'first' server-side below what's
                                   # requested, and comparing to page_size
                                   # here would stop pagination early.
            if total % 5000 == 0:
                print(f"  ...retrieved {total} subjects so far...")
        print(f"-> Successfully loaded a total of {total} existing subjects for {proj}")

    return routing_map


def submit_batch_with_isolation(submission_url, headers, batch, credentials_path, endpoint, failed_records, depth=0):
    """Submit a batch. If it fails with a non-transient error (bad data,
    duplicate key, etc.), split it in half and retry each half separately
    to isolate exactly which record(s) are the problem, rather than
    aborting every remaining chunk in the node. Good records still get
    uploaded even when one bad record is buried in the batch."""
    max_retry = 3

    for attempt in range(max_retry):
        try:
            response = requests.put(submission_url, headers=headers, json=batch, timeout=120)

            if response.status_code in (200, 201):
                print(f"     Success: uploaded {len(batch)} records.")
                return True

            if response.status_code in (401, 403):
                print("         Token expired, fetching new one...")
                new_token = refresh_token(credentials_path, endpoint)
                headers["Authorization"] = f"bearer {new_token}"
                continue  # retry same batch with fresh token

            if response.status_code == 400:
                try:
                    error_data = response.json()
                except Exception:
                    print(f"        -> Raw response: {response.text}")
                    error_data = {}

                entities = error_data.get("entities", [])
                invalid_entities = [e for e in entities if not e.get("valid")]
                is_transactional_crash = error_data.get("transactional_error_count", 0) > 0
                is_duplicate = "duplicate key" in json.dumps(error_data).lower() or \
                                "uniqueviolation" in json.dumps(error_data).lower()

                if invalid_entities:
                    for entity in invalid_entities:
                        unique_keys = entity.get("unique_keys") or [{}]
                        bad_id = unique_keys[0].get("submitter_id", "Unknown")
                        print(f"       -> Broken Record ID: {bad_id}")
                        print(f"       -> Error: {entity.get('errors')}")

                if is_transactional_crash or is_duplicate or invalid_entities:
                    if len(batch) == 1:
                        # Isolated the exact offending record -- log and move on.
                        rec_id = batch[0].get("submitter_id", "Unknown")
                        reason = "duplicate key" if is_duplicate else "validation/transactional error"
                        print(f"       -> Skipping record {rec_id} ({reason}), continuing.")
                        if not invalid_entities:
                            # This path (transactional crash / duplicate) doesn't
                            # get the entity-level error print above -- surface
                            # the raw response so failures are diagnosable
                            # instead of silently swallowed.
                            print(f"       -> Raw error detail: {json.dumps(error_data, indent=2)}")
                        failed_records.append(batch[0])
                        return True  # not transient -- don't retry, don't abort node
                    else:
                        # Split and isolate.
                        mid = len(batch) // 2
                        print(f"       -> Splitting batch of {len(batch)} to isolate the problem "
                              f"record(s) ({'  ' * depth}depth {depth})...")
                        left_ok = submit_batch_with_isolation(
                            submission_url, headers, batch[:mid], credentials_path, endpoint, failed_records, depth + 1
                        )
                        right_ok = submit_batch_with_isolation(
                            submission_url, headers, batch[mid:], credentials_path, endpoint, failed_records, depth + 1
                        )
                        return left_ok and right_ok

                # Unrecognized 400 shape -- log and retry (could be transient)
                print("        -> Gen3 Error Detail:")
                print(f"        {json.dumps(error_data, indent=2)}")
                time.sleep(3)
                continue

            print(f"     WARNING: Batch failed (Code: {response.status_code})")
            time.sleep(3)

        except requests.exceptions.Timeout:
            print(f"     WARNING: Batch timed out (Attempt {attempt+1}/{max_retry}). Retrying...")
            time.sleep(10)
            continue

        except requests.exceptions.RequestException as e:
            print(f"     WARNING: Network error: {e}")
            time.sleep(10)
            continue

    # Exhausted retries without a clean success or a clean isolation
    print(f"     Batch of {len(batch)} could not be uploaded after {max_retry} attempts. "
          f"Logging and continuing.")
    failed_records.extend(batch)
    return False


def main():
    endpoint = "https://gen3-dev.core.wits.ac.za"
    program = "MADIVA"
    active_projects = ["Agincourt", "Nairobi"]

    ONE_TO_ONE_NODES = {"demographic"}
    credentials_path = Path("credentials(2).json")

    print("Authenticating with Gen3 API...")
    auth = Gen3Auth(endpoint, refresh_file=str(credentials_path))
    sub_client = Gen3Submission(endpoint, auth)

    try:
        token = auth.get_access_token()
    except Exception as e:
        print(f"CRITICAL: Failed to retrieve access token: {e}")
        return

    headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json"
    }

    print("\nQuerying system graph to find internal UUIDs for all projects...")
    project_uuids = {}
    for proj in active_projects:
        gql_query = f'{{ project (code: "{proj}") {{ id }} }}'
        try:
            query_response = sub_client.query(gql_query)
            project_records = query_response.get("data", {}).get("project", [])
            if project_records:
                project_uuids[proj] = project_records[0]["id"]
                print(f"-> Resolved '{proj}' to UUID: {project_uuids[proj]}")
            else:
                print(f"WARNING: Project '{proj}' could not be resolved. It may not exist in Gen3.")
        except Exception as gql_error:
            print(f"CRITICAL: GraphQL query failed for {proj}: {gql_error}")
            return

    # Built from Gen3 directly -- works whether or not 'subject' is part
    # of this run's submission order.
    subject_routing_map = build_subject_routing_map(sub_client, program, active_projects)

    print(f"\nRouting map sanity check: {len(subject_routing_map)} total subjects loaded.")
    print("If this number looks low compared to what you expect from the portal, "
          "STOP and investigate before uploading -- child nodes will silently "
          "skip against an incomplete map rather than erroring loudly.")

    try:
        files_to_submit = load_submission_sequence("submission_order.yaml")
    except FileNotFoundError:
        print("CRITICAL: submission_order.yaml is missing.")
        return

    failed_records = []

    print(f"\nStarting sequential graph database Ingestion...")
    for target in files_to_submit:
        node_name = target["node"]
        file_path = Path(target["path"])

        if node_name == "project":
            continue

        print(f"\n[Processing] Node '{node_name}' from {file_path}")

        if not file_path.exists():
            print(f"Aborting: payload file missing at path: {file_path}")
            break

        try:
            with open(file_path, 'r') as f:
                records = json.load(f)

            payloads_by_project = {proj: [] for proj in active_projects}

            for record in records:
                if node_name == "subject":
                    target_project = record.pop("projects.code", None)

                    if target_project and target_project in project_uuids:
                        record["projects"] = {"id": project_uuids[target_project]}
                        subject_id = record.get("submitter_id")
                        if subject_id:
                            subject_routing_map[subject_id] = target_project
                        payloads_by_project[target_project].append(record)
                    else:
                        print(f"Warning: Subject {record.get('submitter_id')} mapped to unknown project '{target_project}'.")
                        failed_records.append(record)

                else:
                    parent_id = record.pop("subjects.submitter_id", None)

                    if not parent_id:
                        print(f"Skipping a {node_name} record: No parent subject ID found.")
                        continue

                    if node_name in ONE_TO_ONE_NODES:
                        record["subjects"] = {"submitter_id": parent_id}
                    else:
                        record["subjects"] = [{"submitter_id": parent_id}]

                    target_project = subject_routing_map.get(parent_id)

                    if target_project and target_project in payloads_by_project:
                        payloads_by_project[target_project].append(record)
                    else:
                        print(f"Warning: Subject {parent_id} not found in routing map. Skipping child node.")
                        failed_records.append(record)

            CHUNK_SIZE = 200

            for proj, project_payload in payloads_by_project.items():
                if not project_payload:
                    continue

                total_records = len(project_payload)
                print(f"  -> Submitting {total_records} records to {proj} endpoint in chunks of {CHUNK_SIZE}...")
                submission_url = f"{endpoint}/api/v0/submission/{program}/{proj}/"

                for i in range(0, total_records, CHUNK_SIZE):
                    batch = project_payload[i:i + CHUNK_SIZE]
                    batch_num = (i // CHUNK_SIZE) + 1
                    print(f"     Batch {batch_num}:")
                    submit_batch_with_isolation(
                        submission_url, headers, batch, credentials_path, endpoint, failed_records
                    )
                    time.sleep(2)  # standard throttle between batches

        except Exception as error:
            print(f"CRITICAL ERROR processing node '{node_name}': {error}")
            print(f"Skipping to next node rather than aborting the entire run "
                  f"-- check failed_records.json and the log above for what went wrong "
                  f"with '{node_name}'.")
            continue

    if failed_records:
        out_path = "failed_records.json"
        with open(out_path, "w") as f:
            json.dump(failed_records, f, indent=2)
        print(f"\n{len(failed_records)} records could not be uploaded (bad data, duplicates, "
              f"or repeated transient failures). Saved to {out_path} for review.")
    else:
        print("\nAll records uploaded successfully with no failures.")


if __name__ == "__main__":
    main()