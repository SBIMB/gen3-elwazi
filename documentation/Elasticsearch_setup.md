# Elasticsearch, Tube & Guppy Setup — MADIVA-Agincourt Gen3

This document covers the setup of the visualisation pipeline for the MADIVA Gen3 portal:
**Elasticsearch → Tube (ETL) → Guppy → Portal Explorer**.

---

## Architecture Overview

```
Postgres (sheepdog/peregrine)
        ↓
      Tube (ETL job)
        ↓
  Elasticsearch (index store)
        ↓
      Guppy (GraphQL API)
        ↓
   Portal Explorer page
```

Tube reads data from the Gen3 graph database (Postgres), flattens it according to `etlMapping.yaml`, and writes flat documents into Elasticsearch. Guppy serves those documents to the portal's Exploration page via GraphQL.

---

## Key Decision: Elasticsearch as a Separate Helm Release

The Gen3 Helm chart (`gen3-0.3.x`) bundles an Elasticsearch deployment behind the `global.dev: true` flag, but this mode:
- Disables persistence (data lost on pod restart)
- Is documented as CI/development only
- Overwrites custom configurations

We deploy Elasticsearch as an independent Helm release (`gen3-elasticsearch`), as with the approach used for Minio (`gen3-minio`). This gives full control over persistence, image, and config without touching the main ```gen3 values.yaml```.

---

## Prerequisites

Confirm these are healthy before proceeding:

```bash
kubectl get pods -n default | grep -E "sheepdog|peregrine"
kubectl top nodes  # confirm available memory > 10Gi
free -h            # confirm available column > 10Gi (more reliable than kubectl top)
```

> **Note on memory:** `kubectl top nodes` reports page cache as "used" — this is misleading. The `available` column in `free -h` is the true measure of free memory. A node at 75% in `kubectl top` may still have 30Gi+ actuallyavailable.

---

## Step 1: Deploy Elasticsearch

### Add the Elastic Helm repo

```bash
helm repo add elastic https://helm.elastic.co
helm repo update
```

### Create `elasticsearch-values.yaml`

Store this alongside your main `values.yaml` in the repo. This is the single source of truth for the ES deployment — do not use `--set` flags for one-off changes that should persist.

```yaml
# elasticsearch-values.yaml

clusterName: gen3-elasticsearch
replicas: 1
minimumMasterNodes: 1
singleNode: true

# Required for single-node clusters — green status is impossible with one node
# (no replica shards can be placed), so the readiness probe must check for yellow.
clusterHealthCheckParams: "wait_for_status=yellow&timeout=1s"

esConfig:
  elasticsearch.yml: |
    xpack.security.enabled: false
    xpack.security.http.ssl.enabled: false
    xpack.security.transport.ssl.enabled: false
extraEnvs:
  - name: ELASTIC_USERNAME
    value: "elastic"
  - name: ELASTIC_PASSWORD
    value: "dummy-password"

readinessProbe:
  failureThreshold: 3
  initialDelaySeconds: 10
  periodSeconds: 10
  successThreshold: 3
  timeoutSeconds: 5
  exec:
    command:
      - sh
      - -c
      - "curl -s -f http://127.0.0.1:9200/_cluster/health?wait_for_status=yellow&timeout=1s"

protocol: http

persistence:
  enabled: true
  size: 10Gi
  storageClassName: longhorn

resources:
  requests:
    cpu: "500m"
    memory: "1Gi"
  limits:
    cpu: "1"
    memory: "2Gi"
```

In ```versions.yaml```, the current working image is appended:
```yaml
#versions.yaml

# Use the official Elastic image, NOT quay.io/cdis/elasticsearch
# The CDIS image has xpack security hardcoded and ignores elasticsearch.yml config,
# causing "received plaintext http traffic on an https channel" errors.
image: "docker.elastic.co/elasticsearch/elasticsearch"
imageTag: "7.10.2"
```

### Install

```bash
helm install gen3-elasticsearch elastic/elasticsearch \
  --namespace default \
  -f elasticsearch-values.yaml
```

### Common Issues

**`vm.max_map_count` too low** — the most common issue on bare metal / k3s:
```bash
cat /proc/sys/vm/max_map_count
# If less than 262144:
sudo sysctl -w vm.max_map_count=262144
```
The Elastic Helm chart includes a `configure-sysctl` init container that sets this automatically — confirm it ran in pod init logs.

**Readiness probe failing with `wait_for_status=green`** — single-node clusters can never reach `green`. Ensure `clusterHealthCheckParams` is set to `yellow` in `elasticsearch-values.yaml`.

**"received plaintext http traffic on an https channel"** — caused by using the `quay.io/cdis/elasticsearch` image, which has xpack security baked in via environment variables that override `elasticsearch.yml`. Switch to `docker.elastic.co/elasticsearch/elasticsearch:7.10.2`.

### Upgrading ES config

All future changes go in `elasticsearch-values.yaml`, then:
```bash
helm upgrade gen3-elasticsearch elastic/elasticsearch \
  --namespace default \
  -f elasticsearch-values.yaml
```

---

## Step 2: Configure the Gen3 Chart to Use Elasticsearch

In your main `values.yaml`, set only the endpoint — do **not** add an `elasticsearch:` block (that is for the bundled dev mode only and will conflict with the separate release):

```yaml
global:
  esEndpoint: "http://gen3-elasticsearch-master:9200"
```

Then upgrade the main gen3 release:

```bash
helm upgrade gen3-dev gen3/gen3 \
  -f values.yaml \
  --namespace default
```

---

## Step 3: Enable Tube and Guppy

Added to main `values.yaml`:

```yaml
tube:
  enabled: true
  resources:
    requests:
      cpu: "250m"
      memory: "256Mi"
    limits:
      cpu: "500m"
      memory: "512Mi"

guppy:
  enabled: true
  esEndpoint: "http://gen3-elasticsearch-master:9200"
  indices:
    - index: subject
      type: subject
  configIndex: "subject-array-config"
  authFilterField: "auth_resource_path"
  resources:
    requests:
      cpu: "100m"
      memory: "128Mi"
    limits:
      cpu: "250m"
      memory: "256Mi"
```

---

## Step 4: Write `etlMapping.yaml`

This is in progress. All subsequent steps are to be followed accordingly. 

---

## Step 5: Run the ETL Job

Tube runs as a Kubernetes CronJob. Trigger it manually after initial setup or any data changes:

```bash
kubectl create job --from=cronjob/etl-cronjob manual-etl-run -n default
kubectl logs job/manual-etl-run -n default -f
```

Watch for errors in the log — field name mismatches between `etlMapping.yaml` and the actual dictionary properties will surface here.

### Verify Elasticsearch has data

```bash
kubectl exec -it gen3-elasticsearch-master-0 -n default -- \
  curl -s localhost:9200/subject/_count
# Should return: {"count": 21, ...}
```

---

## Step 6: Restart Order

After any dictionary, ETL, or Guppy config change, always restart in this order:

```bash
kubectl delete pod -l app=sheepdog -n default
# wait for 1/1 Running
kubectl delete pod -l app=peregrine -n default
# wait for 1/1 Running
kubectl delete pod -l app=guppy -n default
# wait for 1/1 Running
kubectl delete pod -l app=portal -n default
```

Peregrine caches the schema at startup. Portal's relay compiler validates against the live Peregrine schema. Guppy must be healthy before the portal starts or the Explorer page will fail to load.

---

## Step 7: Configure the Portal Explorer

Once Guppy has data, update the `explorerConfig` in your gitops JSON (`values.yaml` portal section):

Only fields that appear in `etlMapping.yaml` under `flatten_props` or `props` are available here — Guppy can only serve what Tube indexed.

---

## Helm Release Summary

| Release | Chart | Purpose |
|---|---|---|
| `gen3-dev` | `gen3/gen3` | Core Gen3 services |
| `gen3-db` | `bitnami/postgresql` | Postgres (graph DB) |
| `gen3-minio` | `minio/minio` | Object storage |
| `gen3-elasticsearch` | `elastic/elasticsearch` | Search index for Guppy |

---

## Troubleshooting Quick Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Guppy: "elasticsearch cluster is down" | Wrong `esEndpoint` or ES not ready | Check `kubectl get svc | grep elastic` for exact service name |
| ES readiness probe failing (green) | Single-node can't reach green | Set `clusterHealthCheckParams: "wait_for_status=yellow&timeout=1s"` |
| ES: "plaintext http on https channel" | Using CDIS image with hardcoded xpack | Switch to `docker.elastic.co/elasticsearch/elasticsearch:7.10.2` |
| Portal Explorer shows no data | Tube ETL hasn't run | Run ETL job manually, verify ES `_count` > 0 |
| ETL field not found error | Field name mismatch in etlMapping | Check actual property names in node YAML |
| Portal relay compiler error on field | Field not in Peregrine schema | Check node table exists in Postgres, restart sheepdog → peregrine → portal |
