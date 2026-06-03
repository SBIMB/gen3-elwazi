# Repository Componentry Audit & Alignment Report

This document records the operational audit of the repository's root directories against the live configurations actively running on the single-node cluster as of May 2026.

---

## 1. Active & Verified Components

The following directories contain configurations that have been personally verified, updated, and tested live on the `gen3-dev` cluster:

* **`gen3/` (`values.yaml`):** The primary configuration engine for the active deployment. All core adjustments to applications, resource constraints, and database settings are driven exclusively through this Helm chart.
* **`test_data_dictionary/`:** Contains the 13 custom MADIVA clinical and phenotypic metadata schemas. These schemas have been compiled and pushed to the remote repository for cluster synchronisation.
* **`traefik/` (`050-gateway-api.yaml` & `051-httproute.yaml`):** Verified as the live edge boundary routing mechanism, successfully matching hostnames and passing traffic to the internal reverse proxy.

---

## 2. Inactive / Unapplied Repository Directories

The following folders exist within the repository infrastructure but **are not** currently active or deployed within the cluster environment. These represent inherited boilerplate architecture intended for future scaling or alternative deployment modes:

| Folder Name | Intended Function | Current Cluster Status |
| :--- | :--- | :--- |
| `metallb/` | Bare-metal LoadBalancer provider | **Inactive.** Cluster utilises native host routing. |
| `cert-manager/` | Automated TLS/SSL rotation engine | **Inactive.** Staging certificates are handled manually via offline fullchain configurations. |
| `rabbitmq/` | Asynchronous microservice message broker | **Inactive.** Not required by the current lightweight operational profile. |
| `grafana/` | Metrics visualisation dashboard | **Inactive.** System performance monitored via raw command-line tools. |

---

## 3. Script Directory Status

The automated configuration scripts found in `bash_scripts/` and `scripts/` (such as `create_fence_config.sh` and `create_useryaml_job.sh`) are preserved for disaster recovery purposes. 

To maintain strict operational security and prevent database configuration drift, these scripts are **not** run during routine schema updates. All active application updates are isolated to manual increments inside the core `gen3/values.yaml` manifest.