#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get secret sh.helm.release.v1.azureml.v1 -n azureml -o json | python3 -c '
import base64,gzip,json,sys
secret=json.load(sys.stdin)
release=json.loads(gzip.decompress(base64.b64decode(base64.b64decode(secret["data"]["release"]))))
print("CLUSTER_METADATA", {k: v for k,v in release["config"]["global"]["azure"]["cluster"].items() if k in ("resourceId","infrastructure","distribution","type")})
printed=0
for template in release["chart"]["templates"]:
    lines=base64.b64decode(template["data"]).decode().splitlines()
    for i,line in enumerate(lines):
        if "clusterType" in line and printed < 35:
            print(template["name"])
            print("\n".join(lines[max(0,i-3):i+8]))
            printed+=1
'
