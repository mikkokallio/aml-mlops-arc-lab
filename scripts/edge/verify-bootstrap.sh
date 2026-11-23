#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl wait --for=create node/amlarclab-edge --timeout=180s
kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl get nodes -o wide
k3s --version
az version
systemctl is-active k3s
