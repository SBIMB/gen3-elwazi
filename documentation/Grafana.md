# Cluster Monitoring

To maintain observability over K3's resource consumption, thw `kube-prometheus-stack` has been deployed into a dedicated `monitoring` namespace. 

## The Package
* **Prometheus**: The database engine. It doesn't wait for logs to be sent to it; instead, it actively reaches out ("scrapes") your cluster every few seconds to pull hardware and software metrics.

* **Node Exporters**: Tiny, lightweight agents that Helm automatically scattered across your host machine. They monitor physical hardware stats like bare-metal CPU temperatures, RAM usage, and network bandwidth.

* **Grafana**: The visual front-end. It acts purely as a presentation layer that connects to Prometheus, pulling raw numerical data and turning it into clean graphs.

## Custom Value Override 
Bydefault, Prometheus saves metrics to a pod's temporary local storage, such that if the server reboots, historical data is lost. It also defaults to run on 3 pods, which using a single-node setup is not currently sustainable. 
This is all allocated in a custom mapping, `monitoring-values-grafana.yaml`.


## Customised Dashboards
* **Storage Allocation**: Prometheus and Grafana utilise 50 Gi and 10 Gi Longhorn volumes respectively, ensuring metric data is not lost if pods restart.
* **Refresh Rate Policy**: Default provisioned dashboards heavily query the Longhorn disk. To prevent unnecessary CPU/Disk I/O spikes, only critical dashboards (Cluster Resources, Persistent Volumes and Workloads), have been saved as copies. 
* **Operation**: These copies are set to a 5 minute auto-refresh rate. The 10 second refresh rate is for active, real-time deubgging, such as monitoring usage spikes during ingestion pipelines. Note, these settings should be manually updated using the JSON schema in the future. 

## Accessing the Dashboards 
All web-based UI's for Longhorn adn Grafana can be accessed for now using local port-forwarding techniques:
### **Grafana Metrics Centre**:
`kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 --address 0.0.0.0` 
and 
`http://146.141.240.78:3000`

### Longhorn Volume Manager 
`kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80 --address 0.0.0.0`
and navigate to:
`http://146.141.240.78:8080` 