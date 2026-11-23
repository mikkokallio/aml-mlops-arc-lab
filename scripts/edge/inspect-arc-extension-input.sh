#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
resources="$(kubectl api-resources --api-group=clusterconfig.azure.com -o name)"
printf 'ARC_CONFIG_RESOURCE_TYPES\n%s\n' "$resources"
for resource in $resources; do
    if [[ "$resource" == *extension* ]]; then
        kubectl get "$resource" --all-namespaces -o json | python3 -c '
import json,sys
def walk(value,path):
    if isinstance(value,dict):
        for key,child in value.items():
            if "protected" not in key.lower():
                walk(child,path+"."+key)
    elif isinstance(value,list):
        for i,child in enumerate(value):
            walk(child,path+"."+str(i))
    elif isinstance(value,str):
        if value in ("SystemAssigned","UserAssigned","AKSCreated"):
            print("IDENTITY_ENUM",path,value)
        elif value.startswith("{") and value.endswith("}"):
            try:
                decoded=json.loads(value)
            except json.JSONDecodeError:
                print("NON_JSON_OBJECT_STRING",path)
            else:
                walk(decoded,path+"[json]")
for item in json.load(sys.stdin)["items"]:
    print("ARC_CONFIG_OBJECT",item["kind"],item["metadata"].get("namespace"),item["metadata"]["name"])
    print("SPEC_KEYS",sorted(item.get("spec",{})))
    walk(item.get("spec",{}),"spec")
'
    fi
done
kubectl get nodes -o json | python3 -c 'import json,sys; [print("NODE_ALLOCATABLE",n["metadata"]["name"],n["status"]["allocatable"]) for n in json.load(sys.stdin)["items"]]'
