# Deployment Issues 
This is a dump file discussing potential improvements for production grade deployment.

### Routing
Since the current state of the cluster, (**26/05/2026**), has all necessary services for deployment ready, no major changes
are going to be made to the deployment.
Particularly, the `gateway` routing, which exists in both `default` and `kube-system` namespaces. This is likely
because a default helm chart was deployed, overlaying both deployments.
1. **Modify the Engine**: We edit the master traefik-gateway in the kube-system namespace, explicitly adding an allowedRoutes block to permit the default and monitoring namespaces to talk to it.
2. **Break the Portal**: We delete the duplicate traefik-gateway in the default namespace. (The moment we do this, Gen3 goes completely offline).
3. **Rewire Gen3**: We intercept the gen3-core-route and rewrite its YAML to point across the cluster boundary directly at the kube-system namespace.
4. **Wire Grafana**: We deploy the Grafana route, pointing it to kube-system as well.

**27/05/2026**
* Grafana dashboard now points to a local host on the same IP: 146.141.240.78.
* This needs to get routed via an *A Record* but this should be contacted through Wits ICT
* Security must be added such that we have `HTTPS` - this can be the `wits-tls-secret` on the cluster, which is the same certifications for the webiste. Grafana dashboard should be tied to Gen3 access.
