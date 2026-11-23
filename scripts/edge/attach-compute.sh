#!/usr/bin/env bash
set -euo pipefail
export AZURE_CONFIG_DIR=/var/lib/aml-arc-lab/az-rgc
export AZURE_EXTENSION_DIR=/root/.azure/cliextensions
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
az extension add --name ml --version 2.45.2 --yes
az login --identity --client-id "$LAB_RGC_CLIENT_ID" --output none
az ml compute attach --resource-group rg-amlarclab-ml --workspace-name mlw-amlarclab --name arc-k3s --type Kubernetes --resource-id "$LAB_CLUSTER_ID" --namespace aml-inference --identity-type UserAssigned --user-assigned-identities "$LAB_COMPUTE_ID" --subscription "$LAB_SUBSCRIPTION"
