#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
helm_path="$(find /root/.azure /var/lib/aml-arc-lab -maxdepth 4 -type f -name helm -print -quit)"
test -n "$helm_path"
"$helm_path" list -n azureml --output json | python3 -c 'import json,sys; print([(x["name"],x["chart"],x["status"]) for x in json.load(sys.stdin)])'
"$helm_path" get values azureml -n azureml --all --output json | python3 -c '
import json,sys
def walk(value,path):
    if isinstance(value,dict):
        for key,child in value.items():
            walk(child,path+"."+str(key))
    elif not isinstance(value,list) and ("clustertype" in path.lower() or path.startswith(".global")):
        print(path, value if "type" in path.lower() else "<redacted>")
walk(json.load(sys.stdin),"")
'
