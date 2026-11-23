#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get configmaps amlarc-identity-config gateway-config -n azureml -o json | python3 -c '
import json,sys,yaml
def walk(value,path):
    if isinstance(value,dict):
        for key,child in value.items():
            walk(child,path+"."+str(key))
    elif isinstance(value,list):
        for i,child in enumerate(value):
            walk(child,path+"."+str(i))
    else:
        allowed=("clusterType","cluster_type","ClusterType","clusterResourceId","location","region","cloud","cloudType")
        print(path, value if path.rsplit(".",1)[-1] in allowed else "<redacted>")
for item in json.load(sys.stdin)["items"]:
    for key,text in item["data"].items():
        walk(yaml.safe_load(text),item["metadata"]["name"]+"."+key)
'
