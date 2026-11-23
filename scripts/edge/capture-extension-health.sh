#!/usr/bin/env bash
set -euo pipefail
umask 077
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
directory="/var/lib/aml-arc-lab/extension-diagnostics-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$directory"
kubectl get deployments -n azure-arc -o json | python3 -c '
import json,sys
for d in json.load(sys.stdin)["items"]:
    name=d["metadata"]["name"]
    if "extension" in name or name in ("config-agent","clusterconnect-agent"):
        print("ARC_AGENT",name,"ready",d["status"].get("readyReplicas",0))
        for c in d["spec"]["template"]["spec"]["containers"]:
            print("IMAGE",c["image"])
'
map_names="$(kubectl get configmaps -n azureml -o jsonpath='{.items[*].metadata.name}')"
if [[ " $map_names " == *" arcml-healthcheck "* ]]; then
    kubectl get configmap arcml-healthcheck -n azureml -o json > "$directory/arcml-healthcheck.json"
    python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print("HEALTHCHECK_REPORT_KEYS",sorted(d.get("data",{})))' "$directory/arcml-healthcheck.json"
else
    echo "HEALTHCHECK_REPORT_ABSENT"
fi
kubectl get pods -n azureml -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}' > "$directory/pod-phases.txt"
count=0
while IFS=$'\t' read -r name phase; do
    if [[ "$name" == *healthcheck* ]]; then
        echo "HEALTHCHECK_POD $name $phase"
        kubectl logs -n azureml "$name" --all-containers=true > "$directory/$name.log"
        count=$((count + 1))
    fi
done < "$directory/pod-phases.txt"
if [[ "$count" -eq 0 ]]; then
    echo "HEALTHCHECK_POD_ABSENT"
fi
echo "PRIVATE_DIAGNOSTICS $directory"
