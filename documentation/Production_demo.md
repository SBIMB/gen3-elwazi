# MADIVA Gen3: Production Demo Readiness Roadmap

This document outlines the tactical engineering objectives for the upcoming month to transition the localized cluster from a development baseline into a secure, high-performance deployment tailored for the MADIVA demonstration use case.

---
## Phase 1: Implementing Guppy for Advanced Data Exploration

For the demo use case to succeed, users need a visual way to filter phenotypic metadata and explore cohorts. This requires deploying **Guppy**, Gen3's Elasticsearch based data discovery engine.

* **Objective:** Deploy and integrate Guppy to drive the interactive "Discovery Page" on the Data Portal UI.
* **Action Plan:**
    1. **Elasticsearch Configuration:** Provision and configure an Elasticsearch cluster pod within localised environment.
    2. **ETL Pipeline Setup:** Configure the `tube` microservice to extract data from the PostgreSQL database (Graph model), transform it into flat JSON arrays, and load it into Elasticsearch indexes. This will also enable users to use the `flat model` search mechanism.
    3. **Guppy Service Manifests:** Write the required configuration values in `values.yaml` to define indices, fields, and aggregation metrics for the MADIVA metadata schemas.

This is also dependant on the type of data available for the use-case, within the MADIVA project. Access must be granted to the MADIVA database to pick which cohort data would be most applicable to a demonstration.

---

## Phase 2: Routing Refinement & Proxy Optimisation

Building upon our successful Traefik Gateway API deployment, we will streamline network hops to improve latency and cluster manageability.

* **Objective:** Reduce infrastructure complexity by migrating path-routing logic directly onto the edge Traefik Gateway.
* **Action Plan:**
    1. **Deconstruct Legacy Logic:** Deconstruct the legacy configurations embedded within the internal `revproxy` pod.
    2. **Expand Edge Routing:** Expand `traefik/051-httproute.yaml` to include explicit, granular path prefixes for `/v0/submission/graphql` (Peregrine) and `/v0/submission` (Sheepdog) directly.
    3. **Proxy Deprecation:** Gradually deprecate the redundant internal Nginx proxy layer once direct-to-service routing is validated, reducing the platform's network footprint.

---
## Phase 3: Granular Role-Based Access Control (RBAC)

To prepare for external stakeholders, we must transition away from global administrative keys and enforce strict data-access boundaries.

* **Objective:** Define administrative, researcher, and data-steward roles within the Gen3 configuration matrix.
* **Action Plan:**
    1. **User Mapping:** Customise the `user.yaml` file to explicitly map individual Wits/MADIVA user accounts to specific project access privileges.
    2. **Scope Enforcement:** Implement distinct read/write/export scopes, ensuring demo users can explore data portals without modification capabilities.
    3. **Authentication Audit:** Audit the `fence` (authentication) service configurations to ensure secure token exchange via the Google OAuth provider.

---

## Timeline & Milestones

| Target Week | Objective | Success Metric |
| :--- | :--- | :--- |
| **Week 1** | Persistnt Storage and MinIO Setup with Longhorn| Successful orchestration of storage bucket and automatic block provisioning |
| **Week 2** | Elasticsearch Deployment & Indexing | Clean data extraction via the `tube` ETL pipeline. |
| **Week 3** | Guppy UI Integration & Final Smoke Test | Data Discovery panel fully interactive on the front-end portal. |
| **Week 4** | Traefik Direct-to-Service Routing Test | Successful `curl` responses bypassing the internal `revproxy`. |
| **Week 5** | RBAC Definition & `user.yaml` Audit | Unauthorised accounts blocked from data access endpoints. |
