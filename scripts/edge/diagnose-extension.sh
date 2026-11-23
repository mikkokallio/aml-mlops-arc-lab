#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
for deployment in amlarc-identity-controller amlarc-identity-proxy gateway; do
    echo "=== $deployment ==="
    kubectl logs -n azureml "deployment/$deployment" --tail=15
done
kubectl get events -n azureml --sort-by=.lastTimestamp | tail -12
