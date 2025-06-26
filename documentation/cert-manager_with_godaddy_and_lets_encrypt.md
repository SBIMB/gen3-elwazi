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


We will be using the [GoDaddy Webhook](https://github.com/snowdrop/godaddy-webhook) to participate in Let's Encrypt's ACME challenges. First, we should clone the [Github repository](https://github.com/snowdrop/godaddy-webhook.git) with
```bash
git clone https://github.com/snowdrop/godaddy-webhook.git
```
After entering the directory of the cloned project, we will perform a Helm deployment with
```bash
export DOMAIN=gen3-sbimb.com
helm install -n cert-manager godaddy-webhook ./deploy/charts/godaddy-webhook --set groupName=$DOMAIN
```
A Kubernetes secret needs to be created that stores the GoDaddy API key and secret:
```yaml
cat <<EOF > godaddy-api-key-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: godaddy-api-key
type: Opaque
stringData:
  token: <GODADDY_API_KEY:GODADDY_SECRET_KEY>
EOF

cat <<EOF > godaddy-api-key-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: godaddy-api-key
type: Opaque
stringData:
  token: 3mM44UdBzaKptA_GL6huDGJuZgUwxUMcX4VNz:Jiwx7mTUJJJfyfuh6kuuFF
EOF
```
Then this secret needs to be deployed (in the `default` namespace, since that's where Gen3 is deployed):
```bash
kubectl apply -f godaddy-api-key-secret.yaml
```
Next, we need to create a _ClusterIssuer_:
```yaml
cat <<EOF > clusterissuer.yaml 
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    # ACME Server
    # prod : https://acme-v02.api.letsencrypt.org/directory
    # staging : https://acme-staging-v02.api.letsencrypt.org/directory
    server: https://acme-v02.api.letsencrypt.org/directory
    # ACME Email address
    email: a0045661@wits.ac.za
    privateKeySecretRef:
      name: letsencrypt-prod # staging or production
    solvers:
    - selector:
        dnsZones:
        - 'gen3-sbimb.com'
      dns01:
        webhook:
          config:
            apiKeySecretRef:
              name: godaddy-api-key
              key: token
            production: true
            ttl: 600
          groupName: gen3-sbimb.com
          solverName: godaddy
EOF
```
The install it on the Kubernetes cluster:
```bash
kubectl apply -f clusterissuer.yaml
```
Now we need to create a certificate resource for each domain that requires a signed certificate:
```yaml
cat <<EOF > certificate.yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: gen3-sbimb-com
spec:
  secretName: gen3-sbimb-com-tls
  renewBefore: 240h
  dnsNames:
  - '*.gen3-sbimb.com'
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
EOF
```
Deploy this certificate resource:
```bash
kubectl apply -f certificate.yaml
```
Modify the ingress accordingly:
```bash
kubectl edit ingress revproxy-dev
```
by adding the following to the ingress manifest:
```yaml
spec:
  tls:
  - hosts:
    - '*.gen3-sbimb.com'
    secretName: gen3-sbimb-com-tls
  rules:
  - host: gen3-sbimb.com
    http:
      paths:
      - path: /
        backend:
          serviceName: revproxy-service
          servicePort: 80
```

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