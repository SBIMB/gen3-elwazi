# Storage
---

## 1. Core Object Storage Architecture 
To ensure stability and keep concerns of storage and deployments separate, a standalone MinIO storage object engine is utilised. 
* **Deployement Method**: [Official MinIO helm chart](https://charts.min.io), which was used in place of older subcharts found on the repo.
* **Storage Backend**: An existing 3.6 Ti persistent volume on the cluster with 2 Ti reserved for Longhorn. Longhorn provisions space from the hsot server's dedicated `/mnt/gen3-storage` directory
* **Internal Routing**: The Gen3 `fence` microservice is reconfigured to bypass AWS enfpoints. All data streams are now routed locally via internal Kubernetes DNS http://gen3-minio.default.svc.cluster.local:9000

--- 
## 2. Expanding Physical Storage Capacity
As more data is added, the initial 2 Ti allocation will eventually become indadequate. Longhorn and Kubernetes support dynamic volume expansion, such that the storage can be scaled up while the database is still running. Note, as of 25 May 2026, this has not yet been necessary.
 To execute:
1. Ensure physical host machine has available raw disk space, formatted and mounted.
2. Verify Longhorn has recognised the new physical capacity using the Longhorn web UI:
        `kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80 --address 0.0.0.0`
        and navigate to:
        `http://146.141.240.78:8080` 
3. Use a Helm upgrade to pass in the new size to the MinIO deployment 
    ``` 
      helm upgrade gen3-minio minio/minio \
    --set rootUser=admin \
    --set rootPassword=Gen3StorageAdmin2026! \
    --set persistence.storageClass=longhorn \
    --set persistence.size=3.5Ti \
    --set mode=standalone 
    ```
 
 4. Longhorn will then expand this block layer, and this can be verfied by checking the minio status: `kubectl get pvc | grep minio` 
