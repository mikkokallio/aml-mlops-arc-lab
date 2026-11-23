#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl create namespace aml-inference --dry-run=client -o yaml | kubectl apply -f -
kubectl wait --for=create crd/instancetypes.amlarc.azureml.com --timeout=600s
kubectl wait --for=condition=Established crd/instancetypes.amlarc.azureml.com --timeout=60s
printf '%s' "$LAB_INSTANCE_TYPES_BASE64" | base64 --decode | kubectl apply -f -
kubectl get pods -n azureml
kubectl get instancetypes
