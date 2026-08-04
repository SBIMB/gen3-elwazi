#!/usr/bin/env python3
"""
TSV vs Dictionary Property Comparator
Compares TSV column headers against MADIVA dictionary YAML property names.
Flags exact matches, close matches (fuzzy), and unmatched columns.
"""

import os
import yaml
import csv
from pathlib import Path
from difflib import get_close_matches

DICTIONARY_DIR = os.path.expanduser("~/my-dictionary")
TSV_DIR = os.path.expanduser("~/etl")  # update to wherever your TSVs are

SKIP_PROPS = {
    "type", "id", "project_id", "state", "created_datetime",
    "updated_datetime", "submitter_id", "subjects", "projects"
}

def load_dictionary_properties(dictionary_dir):
    """Load all property names from every node YAML, keyed by node id."""
    node_props = {}
    all_props = set()

    for fname in os.listdir(dictionary_dir):
        if not fname.endswith(".yaml") or fname.startswith("_"):
            continue
        fpath = os.path.join(dictionary_dir, fname)
        with open(fpath) as f:
            try:
                schema = yaml.safe_load(f)
            except yaml.YAMLError:
                continue
        if not isinstance(schema, dict) or "id" not in schema:
            continue
        if schema["id"] in ("project", "program"):
            continue

        props = set(schema.get("properties", {}).keys()) - SKIP_PROPS
        node_props[schema["id"]] = props
        all_props.update(props)

    return node_props, all_props


def load_tsv_headers(tsv_path):
    """Extract column headers from a TSV file."""
    with open(tsv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter="\t")
        headers = next(reader)
    return [h.strip().lower() for h in headers if h.strip()]


def compare(tsv_headers, node_props, all_props):
    """Compare TSV headers against dictionary properties."""
    # Lowercase everything for comparison
    all_props_lower = {p.lower(): p for p in all_props}
    node_props_lower = {
        node: {p.lower(): p for p in props}
        for node, props in node_props.items()
    }

    exact_matches = []
    close_matches = []
    no_matches = []

    for col in tsv_headers:
        col_lower = col.lower()

        # Exact match
        if col_lower in all_props_lower:
            # Find which node(s) it belongs to
            nodes = [
                node for node, props in node_props_lower.items()
                if col_lower in props
            ]
            exact_matches.append({
                "tsv_col": col,
                "dict_prop": all_props_lower[col_lower],
                "nodes": nodes
            })

        else:
            # Fuzzy match
            close = get_close_matches(col_lower, all_props_lower.keys(), n=3, cutoff=0.6)
            if close:
                close_matches.append({
                    "tsv_col": col,
                    "suggestions": [all_props_lower[c] for c in close]
                })
            else:
                no_matches.append(col)

    return exact_matches, close_matches, no_matches


def main():
    print(f"Loading dictionary from {DICTIONARY_DIR}...")
    node_props, all_props = load_dictionary_properties(DICTIONARY_DIR)
    print(f"Found {len(all_props)} properties across {len(node_props)} nodes\n")

    tsv_files = list(Path(TSV_DIR).glob("*.tsv"))
    if not tsv_files:
        print(f"No TSV files found in {TSV_DIR}")
        return

    for tsv_path in tsv_files:
        print(f"\n{'='*60}")
        print(f"FILE: {tsv_path.name}")
        print(f"{'='*60}")

        try:
            headers = load_tsv_headers(str(tsv_path))
        except Exception as e:
            print(f"  ERROR reading file: {e}")
            continue

        print(f"Columns in TSV: {len(headers)}")
        exact, close, none = compare(headers, node_props, all_props)

        print(f"\nEXACT MATCHES ({len(exact)}/{len(headers)}):")
        for m in exact:
            print(f"  {m['tsv_col']:30} -> {m['dict_prop']:30} [{', '.join(m['nodes'])}]")

        print(f"\n CLOSE MATCHES ({len(close)}/{len(headers)}) - likely need renaming:")
        for m in close:
            suggestions = " | ".join(m['suggestions'])
            print(f"  {m['tsv_col']:30} ~> {suggestions}")

        print(f"\n NO MATCH ({len(none)}/{len(headers)}) - not in dictionary:")
        for col in none:
            print(f"  {col}")

        print(f"\nSUMMARY: {len(exact)} exact | {len(close)} close | {len(none)} unmatched "
              f"out of {len(headers)} columns")


if __name__ == "__main__":
    main()