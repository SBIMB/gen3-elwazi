#!/bin/bash

# delete the old job that ran during the Helm deployment
kubectl delete job useryaml

# update the fence config map
kubectl delete configmap fence
kubectl create configmap fence --from-file user.yaml

# create a new job from the useryaml-job.yaml manifest found in this repo
kubectl apply -f useryaml-job.yaml