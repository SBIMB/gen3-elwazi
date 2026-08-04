import sys
import math
import requests
from gen3.auth import Gen3Auth
from gen3.submission import Gen3Submission
from pathlib import Path

# --- Auth Setup ---
endpoint = "https://gen3-dev.core.wits.ac.za"
auth = Gen3Auth(endpoint, refresh_file=str(Path.home() / "Downloads" / "credentials.json"))
sub_client = Gen3Submission(endpoint, auth)
token = auth.get_access_token()
headers = {"Authorization": f"bearer {token}", "Content-Type": "application/json"}
program = "MADIVA"

# --- 1. Interactive Terminal Inputs ---
print("\n=== Gen3 Bulk Deletion Tool ===")
target_input = input("Which project would you like to delete from? (nairobi / agincourt / all): ").strip().lower()

if target_input == "all":
    target_projects = ["Agincourt", "Nairobi"]
elif target_input == "agincourt":
    target_projects = ["Agincourt"]
elif target_input == "nairobi":
    target_projects = ["Nairobi"]
else:
    print("Invalid selection. Exiting.")
    sys.exit(1)

limit_input = input("How many records PER NODE do you want to delete? (Enter a number or 'all'): ").strip().lower()

if limit_input == "all":
    target_limit = float('inf')
else:
    try:
        target_limit = int(limit_input)
    except ValueError:
        print("Invalid number. Exiting.")
        sys.exit(1)

# Note: Order is critical! Children must be deleted before parents.
nodes = [
    "medical_history",
    "ncd_lifestyle_exposure",
    "ncd_vital",
    "ncd_lab",
    "socioeconomic",
    "demographic",
    "subject"
]

# --- 2. Deletion Logic ---
for project in target_projects:
    print(f"\n=========================================")
    print(f" TARGETING PROJECT: {program}-{project}")
    print(f"=========================================")
    
    for node in nodes:
        print(f"\n[Processing Node: {node}]")
        deleted_count = 0
        fetch_size = 1000 # GraphQL query chunk size
        
        while deleted_count < target_limit:
            # Calculate how many to request (don't over-fetch if target_limit is small)
            current_fetch = min(fetch_size, target_limit - deleted_count) if target_limit != float('inf') else fetch_size
            
            # Fetch IDs
            query = f'{{ {node}(first: {current_fetch}, project_id: "{program}-{project}") {{ id }} }}'
            result = sub_client.query(query)
            records = result.get("data", {}).get(node, [])
            
            if not records:
                print(f"  -> No more records found for {node}.")
                break
                
            ids = [r["id"] for r in records]
            print(f"  -> Fetched {len(ids)} records. Deleting in batches...")
            
            # Bulk Delete in chunks of 200 (Sheepdog URL limit)
            batch_size = 100
            node_success = True
            
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i + batch_size]
                ids_string = ",".join(batch_ids)
                
                url = f"{endpoint}/api/v0/submission/{program}/{project}/entities/{ids_string}"
                response = requests.delete(url, headers=headers)
                
                if response.status_code in [200, 201]:
                    deleted_count += len(batch_ids)
                else:
                    print(f"  [!] Failed to delete batch: Code {response.status_code}")
                    print(f"      {response.text[:200]}")
                    node_success = False
                    break # Break the batch loop
            
            # If a deletion failed, the records still exist. Continuing the while loop 
            # would just query the exact same undeleted records and get stuck forever.
            if not node_success:
                print(f"  [!] Aborting further deletions for {node} due to errors.")
                break 
                
        print(f"  -> Total {node} records deleted: {deleted_count}")

print("\n=== Deletion Complete ===")