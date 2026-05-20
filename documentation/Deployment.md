
---

# MADIVA Gen3 Deployment & Routing Guide

This document records the infrastructure layout, ingress routing architecture, and deployment procedures for the localized single-node Gen3 cluster.

---

## 1. Network Topology & Ingress Architecture

Our cluster is a lightweight, single-node Kubernetes deployment hosted internally at the SBIMB. To handle external incoming requests securely and route them to the correct backend microservice (e.g., Portal, Sheepdog, Peregrine), we utilise an advanced ingress routing layer.

### The Gateway API Migration (In Progress)

We are actively modernising our cluster's entry point, moving away from standard Nginx configurations toward the decoupled **Kubernetes Gateway API** model. This decision comes from Kubernetes ending support for Nginx as of March 2026. Gateway API is the recommended switch.

* **The Routing Engine:** Driven by custom definitions in `traefik/050-gateway-api.yaml` and `traefik/051-httproute.yaml`.
* **Why the Shift?** The Gateway API separates infrastructure management (the Gateway) from application-level routing (the HTTPRoutes), allowing us to cleanly map paths like `/v0/submission/graphql` directly to their respective pods without complex Nginx controller overrides.

---

## 2. Core Traffic Paths

All traffic hitting `https://gen3-dev.core.wits.ac.za/` is managed through the following routing logic:

| Incoming Path | Target Microservice | Component Function |
| --- | --- | --- |
| `/` | `portal-service` | The front-end React web interface |
| `/v0/submission/graphql` | `peregrine-service` | GraphQL engine for database queries |
| `/v0/submission/` | `sheepdog-service` | REST API for data validation and ingestion |
| `/query` | `peregrine-service` | Direct GraphiQL query playground |

---

## 3. Local Cluster Scratchpad & System State

To maintain a clean, production-grade repository Git history, live credentials and temporary migration scripts are strictly isolated outside of the active `gen3-elwazi` codebase.

The following secure folder is maintained in the server's root home directory:
`~/cluster_scratchpad/`

### Critical Files Stored Offline:

* **`values.yaml.secrets`:** Contains the live Google OAuth Client ID and Secret required by the application's authentication module (`fence`). **CRITICAL: Never commit these keys to GitHub.**
* **`values.yaml.backup_*`:** Historically cached versions of cluster variables preserved during core migrations.
* **`cert-staging/` & `fullchain.cer`:** Live SSL/TLS certificates and staging configurations used to handle secure HTTPS terminations at the cluster edge.

---

## 4. Disaster Recovery: Spinning Up From Scratch

If the single-node environment needs to be completely rebuilt, use the following sequence to clone and restore the platform state safely:

```bash
# 1. Clone the repository and immediately pivot to the active development track
git clone https://github.com/SBIMB/gen3-elwazi.git
cd gen3-elwazi
git checkout dev

# 2. Re-link your secure offline secrets back into gen3/values.yaml

# 3. Apply the infrastructure routing definitions
kubectl apply -f traefik/050-gateway-api.yaml
kubectl apply -f traefik/051-httproute.yaml

# 4. Initialise the localised environment using standard Helm charts
# Ensure values.yaml references the correct remote schema.json URL
helm upgrade --install gen3 ./gen3 -f gen3/values.yaml

```

