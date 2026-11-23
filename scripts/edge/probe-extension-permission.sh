#!/usr/bin/env bash
set -euo pipefail
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
export AZURE_CONFIG_DIR=/var/lib/aml-arc-lab/az-rgc
export AZURE_EXTENSION_DIR=/root/.azure/cliextensions
install -d -m 700 "$AZURE_CONFIG_DIR"
az login --identity --client-id "$LAB_RGC_CLIENT_ID" --output none
mkdir -p /var/lib/aml-arc-lab/evidence
if az k8s-extension create --name azureml --extension-type Microsoft.AzureML.Kubernetes --cluster-type connectedClusters --cluster-name arc-amlarclab --resource-group rg-amlarclab-edge --subscription "$LAB_SUBSCRIPTION" --scope cluster --release-namespace azureml --auto-upgrade-minor-version true --configuration-settings enableInference=True enableTraining=False inferenceRouterServiceType=nodePort allowInsecureConnections=True inferenceRouterHA=False > /var/lib/aml-arc-lab/evidence/rgc-extension-attempt.log 2>&1; then
    echo "UNEXPECTED: restricted RG-Contributor created an extension in edge RG."
    exit 1
fi
cat /var/lib/aml-arc-lab/evidence/rgc-extension-attempt.log
grep -q 'AuthorizationFailed' /var/lib/aml-arc-lab/evidence/rgc-extension-attempt.log
echo "EXPECTED_PERMISSION_DENIAL: P-RGC cannot administer the edge cluster."
