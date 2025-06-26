## Updating Metadata with SSJ Dispatcher and Amazon SQS and SNS

In the Amazon console, an SNS topic (let's call it `ssj-topic`) should be created and have the following access policy:
```json
{
  "Version": "2012-10-17",
  "Id": "example-ID",
  "Statement": [
    {
      "Sid": "Example SNS topic policy",
      "Effect": "Allow",
      "Principal": {
        "Service": "s3.amazonaws.com"
      },
      "Action": [
        "SNS:Subscribe",
        "SNS:Receive",
        "SNS:Publish",
        "SNS:ListSubscriptionsByTopic",
        "SNS:GetTopicAttributes"
      ],
      "Resource": "arn:aws:sns:us-east-1:ownerId:ssj-topic",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "ownerId"
        },
        "ArnLike": {
          "aws:SourceArn": "arn:aws:s3:*:*:gen3-bucket"
        }
      }
    }
  ]
}
```
The SNS topic is configured to wait for an upload event from the S3 bucket, `gen3-bucket`.

In the Amazon console, a queue (let's call it `Gen3Queue`) should be created and have the following access policy:
```json
{
  "Version": "2012-10-17",
  "Id": "__default_policy_ID",
  "Statement": [
    {
      "Sid": "__owner_statement",
      "Effect": "Allow",
      "Principal": {
        "AWS": "*"
      },
      "Action": "SQS:*",
      "Resource": "arn:aws:sqs:us-east-1:ownerId:Gen3Queue",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "arn:aws:sns:us-east-1:ownerId:ssj-topic"
        }
      }
    }
  ]
}
```
The SQS queue receives notifications from the SNS topic. When an upload occurs with the `gen3-client`, the message received by the queue should trigger the `ssjdispatcher` to create a Kubernetes job that will update the index of the uploaded file inside the `metadata` database (I think this is what's going on). Consequently, some additional updates needs to be made to some of the `gen3` resources.   

Create a file called `credentials.json` with the following content:
```json
{
    "AWS": {
        "region": "us-east-1",
        "aws_access_key_id": "",
        "aws_secret_access_key": ""
    },
    "SQS": {
        "url": "https://sqs.us-east-1.amazonaws.com/938659344479/Gen3Queue"
    },
    "JOBS": [
        {
            "name": "indexing",
            "pattern": "s3://gen3-bucket/*",
            "imageConfig": {
                "url": "http://indexd-service/index",
                "username": "fence",
                "password": "fence password taken from indexd-service-creds secret",
                "metadataService": {
                    "url": "http://revproxy-service/mds",
                    "username": "gateway",
                    "password": "gateway password taken from metadata.env inside metadata-g3auto secret"
                }
            },
            "RequestCPU": "500m",
            "RequestMem": "0.5Gi"
        }
    ]
}
```
This `credentials.json` file needs to be added as a key in the secret `ssjdispatcher-creds`. This can be done as follows:
```bash
kubectl delete secret ssjdispatcher-creds
kubectl create secret generic ssjdispatcher-creds --from-file=credentials.json
```
After doing this, we also need to create a few resources for the `ssjdispatcher`. Create a file called `ssjdispatcher-rolebinding.yaml` and fill it with the following:
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: ssjdispatcher-job-sa
  namespace: default
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ssjdispatcher-binding
  namespace: default
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: admin
subjects:
- kind: ServiceAccount
  name: ssjdispatcher-service-account`
```
To create these resources, apply the manifest with
```bash
kubectl apply -f ssjdispatcher-rolebinding.yaml
```
We also need to create a service account called `ssjdispatcher-job-sa` with 
```bash
kubectl create sa ssjdispatcher-job-sa
```
The last thing to be done is to manually update the image referenced inside the `manifest-ssjdispatcher` config map:
```bash 
kubectl edit cm manifest-ssjdispatcher
```
Replace the `data` field with the following:
```yaml
data:
  job_images: |-
    {
      "indexing": "quay.io/cdis/indexs3client:2022.08"
    }
```
It would probably be a good idea to restart the `ssjdispatcher` deployment with
```bash
kubectl rollout restart deployment ssjdispatcher
```
Now whenever a file is uploaded to the `gen3-bucket`, a message will be sent to the SNS and SQS services that will then trigger the creation of a job which will then update the `metadata` database with the relevant metadata.   

![Uploaded File in READY State](public/assets/images/uploaded-file-in-ready-state.png "Uploaded File in READY State")   

The above upload process works with an Amazon S3 bucket. We'd like to use a local bucket (with MinIO). To see how to setup a MinIO server on an Ubuntu machine, please refer to [this document](documentation/minio_on_single_linux_node.md).  