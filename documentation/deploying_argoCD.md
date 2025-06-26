### Deploying ArgoCD
[ArgoCD](https://argo-cd.readthedocs.io/en/stable/) is a useful GitOps tool that allows for continuous delivery by automating application deployments to Kubernetes. It is open-source. Automated rollbacks, automatic synchronisation of deployed applications with a Git repository, and a web-based UI to manage the deployed applications are some of the features that are offered by ArgoCD.   

Let us proceed to install ArgoCD on our cluster. First, we shall create a namespace:
```bash
kubectl create namespace
```
Then perform a `helm` deployment:
```bash
helm install argocd argo/argo-cd --namespace argocd
```
If the `helm` deployment completes successfully, the following message should be displayed:
```bash
NAME: argocd
LAST DEPLOYED: Thu Feb 22 17:05:44 2024
NAMESPACE: argocd
STATUS: deployed
REVISION: 1
TEST SUITE: None
NOTES:
In order to access the server UI you have the following options:

1. kubectl port-forward service/argocd-server -n argocd 8080:443

    and then open the browser on http://localhost:8080 and accept the certificate

2. enable ingress in the values file `server.ingress.enabled` and either
      - Add the annotation for ssl passthrough: https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/#option-1-ssl-passthrough
      - Set the `configs.params."server.insecure"` in the values file and terminate SSL at your ingress: https://argo-cd.readthedocs.io/en/stable/operator-manual/ingress/#option-2-multiple-ingress-objects-and-hosts


After reaching the UI the first time you can login with username: admin and the random password generated during the installation. You can find the password by running:

kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

(You should delete the initial secret afterwards as suggested by the Getting Started Guide: https://argo-cd.readthedocs.io/en/stable/getting_started/#4-login-using-the-cli)
```