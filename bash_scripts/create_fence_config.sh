#!/bin/bash

kubectl delete secret fence-config
kubectl create secret generic fence-config --from-file=fence-config.yaml
sleep 5
kubectl rollout restart deployment fence-deployment