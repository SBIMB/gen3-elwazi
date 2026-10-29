# Gen3 BibTeX Metadata Ingestion Pipeline

## Overview

`bibtex_gen.py` is a small ETL script that pulls a shared BibTeX bibliography from GitHub, parses each entry, auto-generates Discovery-page tags, and pushes the resulting metadata records into the Gen3 Metadata Service (MDS) so they appear on the MADIVA Gen3 Discovery page.

**Entries:** [`journals.bib`](https://raw.githubusercontent.com/SBIMB/gen3-elwazi/refs/heads/dev/discovery/journals.bib) on the `dev` branch of `SBIMB/gen3-elwazi`.

**Target:** the Gen3 Metadata Service at `https://gen3-dev.core.wits.ac.za`.

## Prerequisites

- Python packages: `requests`, `bibtexparser`, `gen3` (the [Gen3 SDK](https://github.com/uc-cdis/gen3sdk-python))
- A Gen3 API key/refresh token for an account with MDS admin (`mds_admin`) authorization, downloaded as `credentials.json`-style JSON and referenced via `refresh_file` in `Gen3Auth`
- Network access to `gen3-dev.core.wits.ac.za` and to `raw.githubusercontent.com`

```bash
pip install requests bibtexparser gen3
```

## How it works

1. **Fetch** — downloads the raw `.bib` file over HTTP from the GitHub repo.
2. **Parse** — loads it into BibTeX entries with `bibtexparser`.
3. **Tag** — `generate_tags()` builds a list of `{name, category}` tags per entry:
   - `ENTRYTYPE` (article, inproceedings/conference, etc.) → **Publication Type** tag
   - each `keywords` field entry → **Study Site** (`agincourt`, `nairobi`, `soweto`), **Data Type** (`clinical`, `genomic`, `survey`, `metadata`), or, if it matches neither list, a generic **Research Area** tag
   - if the word "agincourt" appears in the abstract and no Agincourt tag was already added from keywords, an **Agincourt** / Study Site tag is added as a fallback
4. **Build payload** — for each entry, assembles a `gen3_discovery` metadata record: paper ID (used as the GUID), title, authors, year, journal, abstract, a paper URL (falls back to a DOI link if no direct URL is given), the generated tags, and a hard-coded `authz` of `["/programs/MADIVA"]`.
5. **Push** — calls `mds.create(guid=guid, metadata=metadata_payload, overwrite=True)` for every entry, so re-running the script is idempotent and safe to schedule.

## Configuration notes / current limitations

- `authz` is currently **hard-coded** to `/programs/MADIVA`. If this script is ever reused for another cohort's bibliography, that value needs to be parameterised.
- The two `print()` calls that reference `github_bib_url` and `response.status_code` are plain strings, not f-strings — they'll print the literal `{github_bib_url}` / `{response.status_code}` rather than the interpolated value. Minor cosmetic bug, worth fixing:
  ```python
  print(f"Fetching BibTex from {github_bib_url}...")
  ...
  print(f"Failed to fetch. HTTP status: {response.status_code}")
  ```
- `credentials(2).json` in the current script is a locally-named download — rename it to something stable like `credentials.json` before this runs outside of dev.
- No logging of *which* entries failed to push (the script doesn't currently wrap `mds.create` in a try/except), so a single bad entry will raise and stop the whole run partway through.

## Authentication & authorization

Metadata pushes go through Gen3's usual layered auth: `Gen3Auth` obtains a JWT via the refresh token, and MDS write access is gated by an Arborist policy (`mds_admin`) attached to that user. Getting this working end-to-end previously required tracking down a chain of separate issues, documented below in case they resurface (e.g. after a secret rotation or a chart upgrade).

### Postmortem: MDS admin 403 Forbidden

**Symptom:** requests to the `/mds-admin/` endpoint returned 403, despite the calling user's JWT looking correctly scoped.

**Root causes, in the order they were found and fixed:**

1. **Resource path mismatch in `user.yaml`.** `mds_gateway` was nested under `services` in the `resources:` tree, but the `mds_admin` policy pointed at `/mds_gateway` as a top-level resource. Fix: moved `mds_gateway` to be a sibling of `services`, not a child of it.

2. **Malformed `roles`/`policies` block.** A second `mds_admin` entry had a `permissions:` key sitting under `policies:`, when `permissions:` only belongs under `roles:`. Fix: moved it into a proper `roles:` entry.

3. **The actual blocker: revproxy swaps out the JWT entirely.** The nginx `/mds-admin/` location does an internal Arborist check (`auth_request /gen3-authz`) using the caller's Bearer token — but once that check passes, nginx **discards the JWT** and replaces it with `Authorization: Basic <MDS_AUTHZ>` (a shared gateway service-account credential) before forwarding the request to `metadata-service`. So correct Arborist policy configuration was necessary but not sufficient: the app itself is separately gatekept by this Basic Auth layer, checked against `metadata-service`'s own `ADMIN_LOGINS` setting. This step isn't mentioned in the app-level Arborist docs, so it's easy to miss.

4. **Password mismatch + a corrupted secret.** The `metadata-g3auto` Kubernetes secret holds two values that are meant to share one password: `base64Authz.txt` (used by revproxy) and `metadata.env` / `ADMIN_LOGINS` (used by the app). They did share a password, but:
   - `base64Authz.txt` had literal quote characters baked into the base64-encoded credential — a YAML-quoting artifact from how it was originally generated — which broke the Basic Auth string comparison.
   - Separately, revproxy was still running with an **old, different** password cached in memory from before the secret was last updated — Kubernetes does not hot-reload `secretKeyRef` env vars into already-running pods.

**Fix:** regenerated `base64Authz.txt` cleanly (no embedded quotes) to match the already-clean `ADMIN_LOGINS` value, then restarted both `revproxy-deployment` and `metadata-deployment` so each picked up the corrected secret.

**Takeaway for next time:** if MDS admin access 403s despite policy/JWT looking right, check the Basic Auth swap in revproxy's `/mds-admin/` route before re-auditing Arborist — and remember that a secret update alone doesn't take effect until the dependent pods are restarted.

## Troubleshooting checklist

If `bibtex_gen.py` starts failing with 403s again:

- [ ] Confirm the refresh token in the credentials file hasn't expired and belongs to a user with `mds_admin`
- [ ] Confirm `user.yaml`'s `mds_gateway` resource path and `mds_admin` role/policy structure haven't regressed (e.g. after a sync or a merge)
- [ ] Check whether `metadata-g3auto`'s `base64Authz.txt` and `ADMIN_LOGINS` still match, and that neither has stray quote characters
- [ ] Restart `revproxy-deployment` and `metadata-deployment` after any secret change
- [ ] If the JWT-based checks all look fine, remember the request is still separately gated by revproxy's Basic Auth swap on `/mds-admin/`

## Possible improvements

- Fix the non-f-string `print()` calls
- Wrap `mds.create()` per-entry in a try/except, log failures with the GUID, and continue instead of aborting the whole batch
- Parameterise `authz` instead of hard-coding `/programs/MADIVA`
- Add a `--dry-run` flag that builds and prints payloads without calling `mds.create`
