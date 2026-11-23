#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl wait --for=condition=Available deployment --all -n azureml --timeout=600s
kubectl rollout status statefulset/prometheus-prom-prometheus -n azureml --timeout=180s
kubectl get pods -n azureml
kubectl create namespace aml-inference --dry-run=client -o yaml | kubectl apply -f -
