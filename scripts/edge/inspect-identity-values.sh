#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl get secrets -n "${LAB_HELM_NAMESPACE:-azureml}" -l "owner=helm,name=${LAB_HELM_RELEASE:-azureml}" -o json | python3 -c '
import base64,gzip,json,sys
items=json.load(sys.stdin)["items"]
latest=max(items,key=lambda x:int(x["metadata"]["labels"]["version"]))
r=json.loads(gzip.decompress(base64.b64decode(base64.b64decode(latest["data"]["release"]))))
print("release",r["version"],"chart",r["chart"]["metadata"]["version"],"appVersion",r["chart"]["metadata"].get("appVersion"),"status",r["info"]["status"],"lastDeployed",r["info"].get("last_deployed"))
for label,v in (("config",r["config"]),("defaults",r["chart"]["values"])):
    print(label,"Azure.Identity.Type",v.get("Azure",{}).get("Identity",{}).get("Type"))
    print(label,"global.azure.identity.type",v.get("global",{}).get("azure",{}).get("identity",{}).get("type"))
    print(label,"literal Azure.Identity.Type",v.get("Azure.Identity.Type"))
    print(label,"literal global.azure.identity.type",v.get("global.azure.identity.type"))
def inspect(chart):
    for t in chart.get("templates",[]):
        lines=base64.b64decode(t["data"]).decode().splitlines()
        for i,line in enumerate(lines):
            if "global.azure.identity" in line or ("set" in line and "\"Azure\"" in line):
                print(t["name"])
                print("\n".join(lines[max(0,i-2):i+5])[:700])
    for child in chart.get("dependencies",[]):
        inspect(child)
inspect(r["chart"])
'
