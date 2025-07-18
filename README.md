# k3s Setup and Configuration on Ubuntu 22.04
## Introduction
We will be using a virtual machine with operating system _Ubuntu 22.04.2 LTS_, kernel _GNU/Linux 5.15.0-73-generic_, and architecture _x86-64_ to setup and configure a Kubernetes cluster using the [k3s distribution](https://docs.k3s.io/). We'll go with a K3s single-server setup (we might expand at a later date).        
![K3s Single Server Setup](/public/assets/images/k3s-architecture.png "K3s Single Server Setup")   

The ultimate goal for having this cluster up and running is to administer and orchestrate the [Gen3 stack](https://gen3.org/resources/operator/index.html), which consists of over a dozen containerised microservices.   

## Installation
### K3s 
The installation script for K3s, with default load balancer `servicelb` (also known as `klipper`) and default ingress controller `traefik` can be used as follows:
```bash
sudo curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644
```
However, if we wish to use a different load balancer or different ingress controller, then the default ones can be disabled when running the installation script. In our case, we'd like to use the [metallb load balancer](https://metallb.universe.tf/) and the [nginx ingress controller](https://docs.nginx.com/nginx-ingress-controller/installation/installing-nic/). The following command uses the installation script, but disables the default load balancer and ingress controller:
```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable servicelb --disable traefik" sh -s - --write-kubeconfig-mode 644
```   
The installation includes additional utilities such as `kubectl`, `crictl`, `ctr`, `k3s-killall.sh`, and `k3s-uninstall.sh`. `kubectl` will automatically use the `kubeconfig` file that gets written to `/etc/rancher/k3s/k3s.yaml` after the installation. By default, the container runtime that K3s uses is `containerd`.    

Docker is not needed, but can be installed if desired. To use Docker as the container runtime, the following command should be run:
```bash
curl https://releases.rancher.com/install-docker/20.10.sh | sh
```
This will let K3s use Docker instead of Containerd.     

We might encounter some permissions issues when trying to use the `kubectl` command line tool. This can be resolved by creating a `.kube` directory which contains the cluster config file. We can achieve this by running the following commands:
```bash
mkdir ~/.kube
sudo k3s kubectl config view --raw | tee ~/.kube/config
chmod 600 ~/.kube/config
export KUBECONFIG=~/.kube/config
```
For these updates to persist upon reboot, the `.profile` and `.bashrc` files should be updated with `export KUBECONFIG=~/.kube/config`.   

After about a minute or so, the following command can be run to see if the cluster is in good shape:
```bash
kubectl get all -n kube-system
```
![Resources in kube-system Namespace](/public/assets/images/kube-system-resources.png "Resources in kube-system Namespace")   

It's very important to configure the `coredns` pods after a new installation of a K3s cluster. The cluster needs to resolve the DNS in the same way as the host node. To do this, a custom `resolv.conf` file named `/etc/k3s-resolv.conf` needs to be created that will contain the upstream DNS server for any external domains. The contents of this file should be identical to that of the host's `/etc/resolv.conf` file, with the addition of the router's IP address, which is usually `192.168.1.1`. So in our case, it would look like this:
```bash
nameserver 192.168.1.1
nameserver 146.141.8.16
nameserver 146.141.15.210
nameserver 8.8.8.8
search core.wits.ac.za
```
We need to update the `/etc/rancher/k3s/config.yaml` file by appending the kubelet arg, i.e. 
```bash
echo 'kubelet-arg:' | sudo tee -a /etc/rancher/k3s/config.yaml
echo '- "resolv-conf=/etc/k3s-resolv.conf"' | sudo tee -a /etc/rancher/k3s/config.yaml
```
This is done so that K3s will automatically read the DNS config at startup. A K3s stop-and-start will be needed for the changes to be reflected, so the following commands should be run:
```bash
sudo systemctl stop k3s
sleep 10
sudo systemctl start k3s
systemctl status k3s
```
The `coredns` pod in the `kube-system` namespace should be deleted (it will be recreated immediately and should read the updated configuration).

If something is not quite right and there is a desire to re-install K3s with some other features enabled/disabled, it can be fully uninstalled with:
```bash
/usr/local/bin/k3s-uninstall.sh
```
In such a case, remember to delete the `.kube` directory so that there aren't any certificate issues with a fresh re-install.   

The above process installs and configures a single-node cluster. This single node acts as both a master and a worker node. To add additional worker nodes, please read [this document](documentation/adding_and_removing_a_worker_node.md) for more details.   

### Helm
To successfully deploy the Gen3 services, we need to use [Helm](https://helm.sh/), which is a package manager for Kubernetes. Details for installing Helm can be found in this repo over [here](documentation/installing_helm.md).   

### Installing MetalLB Load Balancer with Helm
Using Helm, we begin with:
```bash
helm repo add stable https://charts.helm.sh/stable
```
In the past, `metallb` used to be configured using config maps because that’s traditionally where configs were placed. However, now it uses custom resources (CRs). We'll create a namespace called `metallb-system` and then perform a Helm deployment for all the `metallb` resources:
```bash
kubectl create ns metallb-system
helm repo add metallb https://metallb.github.io/metallb
helm install metallb metallb/metallb --namespace metallb-system
```
Now we need to create two additional resources, an address pool and a layer two advertisement, which instructs `metallb` to use the address pool. Here are the manifests of the two resources (saved inside the `metallb` directory):
**IPAddressPool.yaml**   
```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: k3s-gen3-dev-pool
  namespace: metallb-system
spec:
  addresses:
  - 146.141.240.78/32
```
**L2Advertisement.yaml**   
```yaml
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: k3s-gen3-dev-l2advertisment
  namespace: metallb-system
spec:
  ipAddressPools:
  - k3s-gen3-dev-pool
```
To create these resources, we need to run the `kubectl apply -f` command:
```bash
kubectl -n metallb-system apply -f metallb/IPAddressPool.yaml
kubectl -n metallb-system apply -f metallb/L2Advertisement.yaml
```
To see if the resources have been created, we can run:
```bash
kubectl get pods -n metallb-system
```
and should get an output that looks similar to:   

| NAME                                | READY | STATUS   | RESTARTS   | AGE |
| ----------------------------------- | ----- | -------- | ---------- | --- |
| metallb-speaker-dzcks               | 4/4   | Running  | 0          | 20m |
| metallb-controller-6cb58c6c9b-p9dqz | 1/1   | Running  | 1 (9m ago) | 20m |

### Installing NGINX Ingress with Helm
Using Helm, we can install the `ingress-nginx` controller as follows:
```bash
helm upgrade --install ingress-nginx ingress-nginx \
--repo https://kubernetes.github.io/ingress-nginx \
--namespace ingress-nginx --create-namespace
```
Instead of using Helm, the NGINX ingress controller can be created directly from a manifest:
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/baremetal/deploy.yaml
```
(This manifest file has been copied and saved to this repository, `ingress-nginx-controller/ingress-nginx-controller-v1.7.1.yaml`).   

After a short while, we can run the following command to see if the pods are up and running:
```bash
kubectl get pods --namespace=ingress-nginx
```
The service, `ingress-nginx-controller`, should be edited to be of type `LoadBalancer` instead of `NodePort`. This will result in an external IP being exposed for the service.   

A local port can be forwarded to the ingress controller:
```bash
kubectl port-forward --namespace=ingress-nginx service/ingress-nginx-controller 8080:80
```

Here is an example Ingress that makes use of the controller: 
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: example
  namespace: foo
spec:
  ingressClassName: nginx
  rules:
    - host: www.example.com
      http:
        paths:
          - pathType: Prefix
            backend:
              service:
                name: exampleService
                port:
                  number: 80
            path: /
  # This section is only required if TLS is to be enabled for the Ingress
  tls:
    - hosts:
      - www.example.com
      secretName: example-tls

# If TLS is enabled for the Ingress, a Secret containing the certificate and key must also be provided:
apiVersion: v1
kind: Secret
metadata:
  name: example-tls
  namespace: foo
data:
  tls.crt: <base64 encoded cert>
  tls.key: <base64 encoded key>
type: kubernetes.io/tls
```
When we install `gen3`, the `revproxy-service` will be the ingress of the Gen3 stack, and the `gen3-certs` will be the secret.   

**NOTE:** The test `my-deployment` resources can be deleted after confirming that the ingress controller is working as desired:
```bash
kubectl delete deployment my-deployment
kubectl delete service my-deployment
kubectl delete ingress my-deployment-ingress
```   

### Installing Gen3 Microservices with Helm
The Helm charts for the Gen3 services can be found in the [uc-cdis/gen3-helm repository](https://github.com/uc-cdis/gen3-helm.git). We'd like to add the Gen3 Helm chart repository. To do this, we run:  

```bash
helm repo add gen3 http://helm.gen3.org
helm repo update
```
The Gen3 Helm chart repository contains the templates for all the microservices making up the Gen3 stack. For the `elastic-search-deployment` to run in a Linux host machine, we need to increase the max virtual memory areas by running:
```bash
sudo sysctl -w vm.max_map_count=262144
``` 
This setting will only last for the duration of the session. The host machine will be reset to the original value if it gets rebooted. For this change to be set permanently on the host machine, the `/etc/sysctl.conf` file needs to be edited with `vm.max_map_count=262144`. To see the current value, run `/sbin/sysctl vm.max_map_count`. More details can be found on the [official Elasticsearch website](https://www.elastic.co/guide/en/elasticsearch/reference/current/vm-max-map-count.html).   

Some of the microservices require the `uwsgi-plugin` for Python 3. To install it, run the following:
```bash
sudo apt update  
sudo apt install uwsgi-plugin-python3 
```

Before performing a `helm install`, we need to create a `values.yaml` file that can be used to override default values specified in the Gen3 Helm templates. The Helm installation can begin by running:
```bash
helm upgrade --install gen3-dev gen3/gen3 -f gen3/values.yaml 
```
In the above command, `gen3-dev` is the name of the release of the helm deployment. If the installation is successful, then a message similar to the following should be displayed in the terminal:
```bash
NAME: gen3-dev
LAST DEPLOYED: Tue Nov 14 13:27:49 2023
NAMESPACE: default
STATUS: deployed
REVISION: 1
```
If the default `traefik` ingress controller was used and all went well, we should see the `revproxy-dev` deployment up and running with the following command:
```bash
kubectl get ingress
```
The output should look similar to this:
| NAME          | CLASS   | HOSTS                   | ADDRESS        | PORTS   | AGE |
| ------------- | ------- | ----------------------- | -------------- | ------- | --- |
| revproxy-dev  | traefik | cloud08.core.wits.ac.za | 146.141.240.78 | 80, 443 | 34s |    

However, if the `nginx` ingress controller has been used instead, then the `revproxy-dev` ingress manifest needs to be edited. To edit the resource, run:
```bash
kubectl edit ingress revproxy-dev
```
This will open a `vim` editor. The following line, `ingressClassName: nginx`, should be added under the `spec` section of the YAML file and then the changes should be saved. Checking the ingress now should yield:
```bash
kubectl get ingress
```
The output should look similar to this:
| NAME          | CLASS   | HOSTS                   | ADDRESS        | PORTS   | AGE |
| ------------- | ------- | ----------------------- | -------------- | ------- | --- |
| revproxy-dev  | nginx   | cloud08.core.wits.ac.za | 146.141.240.78 | 80, 443 | 10m | 

Additional changes need to be made to the ingress manifest. Since an external service is going to be used for [external authentication](https://github.com/kubernetes/ingress-nginx/blob/main/docs/user-guide/nginx-configuration/annotations.md#external-authentication), the following annotation needs to be added to the ingress manifest:
```bash
nginx.ingress.kubernetes.io/auth-url: "URL to the authentication service"
```   

The list of deployments can be seen by running:
```bash
kubectl get deployments
```    
![Gen3 services deployed with NGINX](public/assets/images/gen3-deployments.png "Gen3 services deployed with NGINX")   

The `portal-deployment` is normally the last deployment to be ready. In particular, it is dependent on both the `peregrine-deployment` and the `sheepdog-deployment`. It may struggle (by constantly restarting) to run while waiting for the other deployments to be ready. If that happens, then the following command should be run once the `peregrine-deployment` and the `sheepdog-deployment` are up and running:
```bash
kubectl rollout restart deployment portal-deployment
```
This command restarts the deployment. Alternatively, the `portal-deployment` pod can simply be deleted. The replicaset will ensure that another pod is spun up immediately.   

Information about the Gen3 helm release can be found with the command:
```bash
helm list
```
and we should see a table that looks similar to this:
| NAME          | NAMESPACE | REVISION  | UPDATED                                  | STATUS   | CHART       | APP VERSION |
| ------------- | --------- | --------- | ---------------------------------------- | -------- | ----------- | ----------- |
| gen3-dev      | default   | 1         | 2024-01-16 13:35:01.712355152 +0200 SAST | deployed | gen3-0.1.21 | master      |

To verify that the correct custom values are being used, the following command can be run:
```bash
helm get values <name-of-release>
```
In our case, the name of the release is `gen3-dev`. The output will be a reproduction of the `values.yaml` file with the first line being **USER-SUPPLIED VALUES:**. There may exist the requirement to edit values in the `values.yaml` _without_ upgrading the version of the release. In that case, the following commands could be used if the values from the previous release need to be used again (this is because, by default, the `helm upgrade` command resets the values to those baked into the chart):
```bash
helm upgrade --reuse-values -f gen3/updated-values.yaml gen3-dev gen3/gen3
helm upgrade --reuse-values -f values.yaml gen3-dev gen3/gen3
```
or 
```bash
helm upgrade --reuse-values --set key1=newValue1,key2=newValue2 gen3-dev gen3/gen3
```   

### Cert Manager
Cert-Manager can be used to manage certificates in the Kubernetes cluster. However, this may not necessarily be needed if the number of certificates and/or clusters are small. In our case, we are only managing one cluster, so using `cert-manager` might be an example of "over-engineering". For those interested in looking at how we can use `cert-manager`, we have in this repo some documentation discussing [cert-manager with GoDaddy and Let's Encrypt](documentation/cert-manager_with_godaddy_and_lets_encrypt.md) and [cert-manager with ZeroSSL](documentation/cert-manager_with_zero_ssl.md).   

Whether using `cert-manager` or not, the ingress manifest needs to be modified such that the following block appears underneath the `spec`:
```bash
  tls:
  - hosts:
    - cloud08.core.wits.ac.za
    secretName: cloud08-tls-secret
```
After editing the ingress manifest, the certificate creation events can be seen when running the command:
```bash
kubectl describe ingress
```
Details of the certificate can be seen with:
```bash
kubectl describe certificate
```
The following command can be run to test if the connection to HTTPS is possible:
```bash
wget --save-headers -O- cloud08.core.wits.ac.za
```
The response should state that the domain name has been resolved and a connection has been established, however, there should be an error stating that the certificate could not be verified and that the flag `--no-check-certificate` can be used. If such is the case, then it's time to change the annotation in the ingress to `letsencrypt-prod`:
```bash
cert-manager.io/cluster-issuer: "letsencrypt-prod"
```
It may take a few minutes for the certificate to be issued.     

#### Google Authentication
The `fence-service` is mainly responsible for Gen3 authentication. There are a variety of authentication providers. If [Google is to be used for authentication](https://github.com/uc-cdis/fence/blob/master/docs/google_architecture.md), then a project needs to be created in the [Google Cloud Console](https://console.cloud.google.com/). This project will need to be part of an organisation. In our case, the organisation is **wits.ac.za**, and the project is called **gen3-dev**.    

The Google project needs to be setup correctly. The project needs to be a _web application_, it needs to be _external_, the authorised redirect uri needs to be configured as the `${hostname}/user/login/google/login/, and the following scopes are required:
- openid
- email
- profile

![Google OAuth App Setup](public/assets/images/google-oauth-app-setup.png "Google OAuth App Setup")   

If the correct values are provided, and the Google authentication and the ingress is setup correctly, then the `fence` authentication should work properly:   

![Gen3 Login](public/assets/images/gen3-login.png "Gen3 Login")   

#### Uploading of Files
A detailed description of how the upload process works in Gen3 can be found over [here](https://gen3.org/resources/user/gen3-client/). The data client SDK can be downloaded for Linux, MacOS, or Windows. It is in `.zip` format, and can be extracted into a folder and used accordingly. For convenience, all three `.zip` files have been included in this repository in the `/public/assets/sdk` directory (there is no guarantee that the `.zip` files in this directory are the most recent. Please check the website directly).   

The `gen3-client` SDK is used to upload files to a bucket, and `indexd` is used to label the files with the appropriate metadata (like GUIDs).  

![Gen3-Client Upload Architecture](public/assets/images/gen3-client-upload-architecture.png "Gen3-Client Upload Architecture")    

If an Amazon S3 bucket is used for uploading, then the required configuration values need to be provided to the `fence-deployment`. For instance, suppose there exists a bucket named `gen3-bucket` and an IAM user named `gen3-user`, then this user will need AWS credentials in order to access the bucket. These credentials need to be provided in the `values.yaml` file under the `fence` section. These values will then be populated inside the `fence-config` secret in the `default` namespace. An example of what the IAM policy for uploading to an S3 bucket is the following:
```json
{
    "Version": "2012-10-17",
    "Id": "Gen3BucketPolicy01",
    "Statement": [
        {
            "Sid": "Gen3Upload",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::someId:user/gen3-user"
            },
            "Action": [
                "s3:GetObject",
                "s3:GetBucketLocation",
                "s3:ListBucket",
                "s3:PutObject"
            ],
            "Resource": [
                "arn:aws:s3:::gen3-bucket/*",
                "arn:aws:s3:::gen3-bucket"
            ]
        }
    ]
}
```
For all S3 actions to be allowed for a user, the following policy can be used:
```json
{
    "Version": "2012-10-17",
    "Id": "Gen3BucketPolicy01",
    "Statement": [
        {
            "Sid": "Gen3Upload",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::someId:user/gen3-user"
            },
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::gen3-bucket/*",
                "arn:aws:s3:::gen3-bucket"
            ]
        }
    ]
}
```
The command to list objects inside the bucket is the following:
```bash
aws s3 ls s3://gen3-bucket
```
If the `aws` CLI tool is installed and configured correctly, then a list of files/objects should appear in the terminal. To upload a single file from inside a folder to the `gen3-bucket`, the following command can be used:
```bash
aws s3 cp local-folder/folder-where-file-exists s3://gen3-bucket/ --recursive
```
If these `aws` CLI commands work properly, then it is safe to assume that the bucket and credentials are correct and working.   

Regarding Gen3, if a **403 Unauthorized** error is returned when trying to upload a file, it is likely that the `usersync` job that ran during the Helm deployment did not update the `useryaml` config map to have the necessary permissions for uploading. This can be remedied manually by doing the following:   
```bash
# delete the old job that ran during the Helm deployment
kubectl delete job useryaml

# update the fence config map
kubectl delete configmap fence
kubectl create configmap fence --from-file user.yaml

# create a new job from the useryaml-job.yaml manifest found in this repo
kubectl apply -f useryaml-job.yaml
```   

The above process can be done more quickly by using a Bash script found in this repo over [here](bash_scripts/create_useryaml_job.sh).   

To see if the roles and policies have been updated, restart the `arborist` deployment with
```bash
kubectl rollout restart deployment arborist-deployment
```
and then check the logs from the `arborist-deployment` with
```bash
kubectl logs <arborist-pod-name>
```
![Arborist Logs](public/assets/images/arborist-logs-for-user-roles.png "Arborist Logs") 

#### Authorising the gen3-client Command Line Tool
To authorise the `gen3-client` for uploading to the data commons, the following command needs to be run:
```bash
gen3-client configure --profile=gen3-user --cred=gen3-credentials.json --apiendpoint=https://cloud08.core.wits.ac.za/
```
This command might fail due to certificate issues. It may complain that the self-signed certificate is not trusted. To trust the self-signed certificate, copy the contents of `cloud08.core.wits.ac.za.key` and `cloud08.core.wits.ac.za.crt` to `cloud08.core.wits.ac.za.pem`, and have this `.pem` file moved to the `/usr/local/share/certificates/` (or `/usr/local/share/ca-certificates/`) directory. Then when the following command is run
```bash
sudo update-ca-certificates
```
the self-signed certificate will be trusted.   

![gen3-client Authorised](public/assets/images/gen3-client-authorised.png "gen3-client Authorised") 
To upload a file with the `gen3-client`, the following command can be used:
```bash
gen3-client upload --profile=gen3-user --upload-path=/path/to/file
```
If the `gen3-client` still does not work, then we can try other methods (use the API directly). The goal here is to obtain an access token. This access token will be used as a bearer token under the _Authorization_ header when making requests to the data commons. To get an access token, a POST request needs to be made to this endpoint:
```bash
https://cloud08.core.wits.ac.za/user/credentials/cdis/access_token
```
The POST request can be made using a tool like Postman, or directly from the terminal as follows:
```bash
curl --location 'https://cloud08.core.wits.ac.za/user/credentials/cdis/access_token' \
--header 'Content-Type: text/plain' \
--data '{ "api_key": "apiKeyGeneratedByGen3Portal", "key_id": "f8fb4da3-4983-435e-8fd9-14eb854ee79a" }'
```
![Obtain Access Token](public/assets/images/generate-access-token-with-postman.png "Obtain Access Token") 

Once the access token has been obtained, then additional requests can be made using the access token as a bearer token inside the header of requests, e.g.
```bash
--header 'Authorization: Bearer accessTokenReceivedFromPreviousRequest' \
```   

#### Programs and Projects
Before a file can be uploaded, a program and a project needs to be created. To create a program, append `/_root` to the base url of the data commons, i.e. 
```bash
https://cloud08.core.wits.ac.za/_root
```
On the UI, select the form submission option and search for _program_ in the dropdown list. The **dbgap_accession_number** and **name** fields need to be filled in ("123" can be used for the former, and "Program1" for the latter). At this point, the "Upload submission json from form" option can be selected and then the "Submit" button clicked.   

![Program Creation](public/assets/images/program-creation.png "Program Creation") 

If the creation is unsuccessful, the `sheepdog` logs can be looked at for more details. The programs and projects get stored in the `sheepdog` database (/datadictionary), so _that_ can also be checked to ensure that the program was actually created. If the newly created program is in the data dictionary, then the next step will be to create a project.   

To create a project, visit `https://cloud08.core.wits.ac.za/<program_name>`, where `program_name` is the program under which the project will be created. This time, search for _project_ in the dropdown list and then fill in the fields. We can use "P1" as **code**, "phs1" as **dbgap_accession_number**, and "project1" as **name**. The "Upload submission json from form" should then be clicked, and then "Submit". Once again, the `sheepdog` database can be checked to see if creation was successful.   

As an example, suppose there exists a program called `program1`. Then visiting the url `https://cloud08.core.wits.ac.za/ReganTestProgram` will provide a page on the UI where a project can be created. By filling in the fields mentioned above, the following project JSON will get generated:
```json
{
  "type": "project",
  "code": "P1",
  "dbgap_accession_number": "phs1",
  "name": "ReganTestProject"
}
```
and a green banner with **Succeeded: 200** will be displayed.   

![Successful Project Creation](public/assets/images/successful-project-creation.png "Successful Project Creation")    

The url for adding nodes to the project is found at `https://cloud08.core.wits.ac.za/<program_name>/<project_code>`. The `administrative` node data can be added directly by filling in the form and submitting in JSON format.   

To test the uploading of data, the data needs to match the data dictionary. There exists a repository called [data-simulator](https://github.com/uc-cdis/data-simulator) that can be used for generating mock, or test, data.   

When trying to upload data using the submission endpoint, an error is thrown by the `sheepdog-deployment`. The error is about parsing JSON. We need to investigate this error further.

![JSON Parse Error](public/assets/images/sheepdog-parse-json-error.png "JSON Parse Error")    

When using a tool like Postman to make a PUT request to the submission endpoint (where program name is `gen3Program502` and project code is `P502`), i.e.
```bash
https://cloud08.core.wits.ac.za/api/v0/submission/gen3Program502/P502
```
the request is successful when the body is submitted as raw JSON. However, when using a JSON file, the parsing error persists.   

![Successful PUT Request with Raw JSON](public/assets/images/successful-put-request.png "Successful PUT Request with Raw JSON")    

Uploading/Submitting is successful when using raw JSON or when using the UI directly. However, the files remain in a `Generating...` state in the UI. This is probably due to some database record not being updated when the upload occurs. The metadata would then need to be manually updated.   

![Gen3 Files in Generating State](public/assets/images/gen3-files-in-generating-state.png "Gen3 Files in Generating State")  

To successfully upload with the `gen3-client`, and have the metadata updated when the upload occurs, the `ssjdispatcher` needs to be configured to work with Amazon SQS and SNS, respectively. More information about using AMazon SQS and Amazon SNS with the `ssjdispatcher` can be found insided this repo over [here](documentation/updating_metadata_with_ssjdispatcher_with_Amazon_SQS_and_SNS.md).

## Acknowledgements
![eLwazi](public/assets/images/elwazi_logo.png "eLwazi")   

The _eLwazi_ Open Data Science Platform is supported by the Office Of The Director, National Institutes Of Health (OD), National Institution of Biomedical Imaging and Bioengineering, and NIH award number 1 U2C EB 032224 . This work is solely the responsibility of the authors and does not necessarily represent the official views of the National Institutes of Health.   