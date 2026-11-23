#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get deployment gateway -n azureml -o json | python3 -c 'import json,sys; d=json.load(sys.stdin); s=d["spec"]["template"]["spec"]; print(json.dumps({"containers":[{"name":c["name"],"args":c.get("args"),"volumeMounts":c.get("volumeMounts"),"envNames":[v["name"] for v in c.get("env",[])]} for c in s["containers"]],"volumes":s.get("volumes")},indent=2))'
kubectl get configmaps -n azureml
