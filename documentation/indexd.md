for u in fence sheepdog ssj gateway; do
  PASS=$(kubectl get secret indexd-service-creds -o jsonpath="{.data.$u}" | base64 -d)
  kubectl exec deploy/indexd-deployment -- python /indexd/bin/index_admin.py create --username "$u" --password "$PASS"
done