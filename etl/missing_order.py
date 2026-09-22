"""
build_missing_submission_order.py

Scans payloads/missing/ for whichever payload_<node>_missing.json files
exist, and writes submission_order_missing.yaml in the same node order
as your original submission_order.yaml — so upload_data.py can be pointed
at it without you hand-editing paths or risking wrong ordering.
"""

import yaml
from pathlib import Path

ORIGINAL_ORDER_PATH = "submission_order.yaml"
MISSING_DIR = Path("payloads/missing")
OUTPUT_PATH = "submission_order_missing.yaml"


def main():
    with open(ORIGINAL_ORDER_PATH) as f:
        original = yaml.safe_load(f)["submission_order"]

    missing_order = []
    for entry in original:
        node = entry["node"]
        if node == "project":
            continue
        candidate = MISSING_DIR / f"payload_{node}_missing.json"
        if candidate.exists():
            missing_order.append({"node": node, "path": str(candidate)})
            print(f"Included: {node} -> {candidate}")
        else:
            print(f"Skipped (fully synced, no missing file): {node}")

    if not missing_order:
        print("\nNothing to resubmit — no missing files found.")
        return

    with open(OUTPUT_PATH, "w") as f:
        yaml.safe_dump({"submission_order": missing_order}, f, sort_keys=False)

    print(f"\nWrote {OUTPUT_PATH} with {len(missing_order)} node(s) to resubmit.")


if __name__ == "__main__":
    main()