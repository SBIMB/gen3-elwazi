### Cert Manager
The `cert-manager` manifest can be applied in order to install all the `cert-manager` resources:
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.2/cert-manager.yaml
```
To confirm that the pods are running, use the command:
```bash
kubectl get pods -n cert-manager
```
| NAME                                     | READY | STATUS   | RESTARTS | AGE |
| ---------------------------------------- | ----- | -------- | -------- | --- |
| cert-manager-cainjector-665cd78979-4vldh | 1/1   | Running  | 0        | 7m  |
| cert-manager-9f74c854d-t8gv2             | 1/1   | Running  | 0        | 7m  |
| cert-manager-webhook-65767c6f65-6drjt    | 1/1   | Running  | 0        | 7m  |   

We need to create a **ClusterIssuer** in order to issue certificates to the host domain that we configured in our ingress resource. We'll use the [Zero SSL](https://zerossl.com/) certificate authority because it provides TLS certificates that are free.    

We need to login to ZeroSSL and create an EAB key. This key needs to be added to the Kubernetes secret that will be created:
```yaml
apiVersion: v1
kind: Secret
metadata:
  namespace: cert-manager
  name: zerossl-eab-secret
stringData:
  secret: <YOUR-HMAC-KEY-HERE>

apiVersion: v1
kind: Secret
metadata:
  namespace: cert-manager
  name: zerossl-eab-secret
stringData:
  secret: pVmhxZfC7Cdy5_TSbPMraVRTIJAxtVFvhSrz62JtVKFSiH0C57hIYKwCu_xrTT2vx7vKjh6O72JWZ_r8NbU3vg
```
We need to create a _ClusterIssuer_ as follows:
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: zerossl-clusterissuer
spec:
  acme:
    server: https://acme.zerossl.com/v2/DV90
    externalAccountBinding:
      keyID: YOUR_EAB_KID
      keySecretRef:
        name: zerossl-eab-secret
        key: secret
      keyAlgorithm: HS256
    privateKeySecretRef:
      name: zerossl-production
    solvers:
    - http01:
        ingress:
          class: nginx

apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: zerossl-clusterissuer
spec:
  acme:
    server: https://acme.zerossl.com/v2/DV90
    externalAccountBinding:
      keyID: nEwxmb2CKEM0Ql7NxFIcqw
      keySecretRef:
        name: zerossl-eab-secret
        key: secret
      keyAlgorithm: HS256
    privateKeySecretRef:
      name: zerossl-production
    solvers:
    - http01:
        ingress:
          class: nginx
```
Then add the following annotation to the Ingress:
```yaml
cert-manager.io/cluster-issuer: zerossl-clusterissuer
```
INCOMPLETE...

Cert-manager can also be installed with Helm:
```bash
# Label the cert-manager namespace to disable resource validation
kubectl label namespace ingress-nginx cert-manager.io/disable-validation=true
# Add the Jetstack Helm repository
helm repo add jetstack https://charts.jetstack.io
# Update your local Helm chart repository cache
helm repo update
# Install CRDs with kubectl
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.11.0/cert-manager.crds.yaml
# Install the cert-manager Helm chart
helm install cert-manager jetstack/cert-manager \
  --namespace ingress-nginx \
  --version v1.11.0
```