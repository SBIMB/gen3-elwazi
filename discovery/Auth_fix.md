1. Resource path in user.yaml
mds_gateway was nested under services in your resources: tree, but your mds_admin policy pointed at /mds_gateway (top-level). Fixed by moving mds_gateway to be a sibling of services, not a child of it.

2. Malformed roles/policies block
A second mds_admin entry had a permissions: key sitting under policies: — that key only belongs under roles:. Fixed by moving it to a proper roles: entry.

3. The real blocker: revproxy's /mds-admin/ route doesn't use your JWT at all
This was the big one. The /mds-admin/ nginx location does an internal Arborist check (auth_request /gen3-authz) using your Bearer token — but once that passes, nginx discards your token entirely and replaces it with Authorization: Basic <MDS_AUTHZ>, a shared "gateway" service-account credential, before forwarding to metadata-service. So all your correct Arborist policy work was necessary but not sufficient — the app was actually gatekept by this separate Basic Auth layer, matched against metadata-service's own ADMIN_LOGINS setting.

4. Password mismatch + corrupted secret

The metadata-g3auto Kubernetes secret had two related values (base64Authz.txt for revproxy, metadata.env/ADMIN_LOGINS for the app) that were supposed to share one password — and did — but base64Authz.txt had literal quote characters baked into the encoded credential (a YAML-quoting artifact from however it was originally generated), which broke the Basic Auth string comparison.
Separately, revproxy was still running with an old, completely different password cached in memory from before the secret was last updated, since Kubernetes doesn't hot-reload secretKeyRef env vars into already-running pods.

Fix: regenerated base64Authz.txt cleanly (no embedded quotes) to match the already-clean ADMIN_LOGINS value in metadata.env, then restarted both revproxy-deployment and metadata-deployment so they'd actually pick up the corrected secret.

Nice bit of distributed-systems detective work — that Basic Auth swap step in revproxy is a genuinely easy thing to miss since nothing in the app-level Arborist docs mentions it.


