## Mocking Google Authentication
For testing purposes and for a quick setup of the Gen3 ecosystem, the authentication process can be mocked. The `fence` service is responsible for authenticating a user, so the `fence` config of the value file needs to be configured as follows:
```yaml
fence:
  enabled: true
  FENCE_CONFIG:
    MOCK_AUTH: true
```
This will automatically login a user with username "test". If all the Gen3 services are up and running, the portal can be accessed in the browser by making use of the machine's IP address and the node port of the `revproxy-service` (since the `revproxy-service` is a service of type **NodePort**), e.g.   

![User Endpoint for Mock Authentication](public/assets/images/user-endpoint-for-mock-login.png "User Endpoint for Mock Authentication")    

To upload a file to a custom AWS S3 bucket, the bucket name needs to be provided in the `fence` config of the `values.yaml` file:
```yaml
fence:
  enabled: true
  FENCE_CONFIG:
    AWS_CREDENTIALS:
      "gen3-user":
        aws_access_key_id: "accessKeyIdForGen3User"
        aws_secret_access_key: "secretAccessKeyForGen3User"
    S3_BUCKETS:
      # Name of the actual s3 bucket
      gen3-bucket:
        cred: "gen3-user"
        region: us-east-1
    # This is important for data upload.
    DATA_UPLOAD_BUCKET: "gen3-bucket"
```
The other `fence` endpoints can be found over [here](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/uc-cdis/fence/master/openapis/swagger.yaml). 