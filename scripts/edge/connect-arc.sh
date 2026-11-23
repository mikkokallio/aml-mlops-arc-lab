#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
export AZURE_CONFIG_DIR=/var/lib/aml-arc-lab/az-onboarding
export AZURE_EXTENSION_DIR=/root/.azure/cliextensions
install -d -m 700 "$AZURE_CONFIG_DIR"
az login --identity --client-id "$LAB_ONBOARDING_CLIENT_ID" --output none
az connectedk8s connect --name "${LAB_CLUSTER_NAME:-arc-amlarclab}" --resource-group rg-amlarclab-edge --location "${LAB_CLUSTER_LOCATION:-swedencentral}" --subscription "$LAB_SUBSCRIPTION" --kube-config "$KUBECONFIG"
kubectl wait --for=condition=Ready pod --all -n azure-arc --timeout=300s
kubectl get pods -n azure-arc
az connectedk8s show --name "${LAB_CLUSTER_NAME:-arc-amlarclab}" --resource-group rg-amlarclab-edge --subscription "$LAB_SUBSCRIPTION" --query '{state:provisioningState,connectivity:connectivityStatus,agentVersion:agentVersion,kubernetesVersion:kubernetesVersion}' -o json
