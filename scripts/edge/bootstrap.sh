#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export NO_PROXY="localhost,127.0.0.1,169.254.169.254,168.63.129.16,10.82.1.0/24,10.42.0.0/16,10.43.0.0/16,.svc,.cluster.local"
export no_proxy="$NO_PROXY"
for host in management.azure.com pypi.org mcr.microsoft.com; do
    curl --connect-timeout 5 --max-time 20 --silent --output /dev/null "https://$host"
    echo "LAB_EGRESS_PROBE $host REACHABLE"
done
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor --yes -o /etc/apt/keyrings/microsoft.gpg
chmod go+r /etc/apt/keyrings/microsoft.gpg
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/repos/azure-cli/ noble main" > /etc/apt/sources.list.d/azure-cli.list
apt-get update -qq
apt-get install -y -qq azure-cli=2.93.0-1~noble
az extension add --name connectedk8s --version 1.11.6 --yes
az extension add --name k8s-extension --version 1.9.5 --yes
curl --fail --location --silent --show-error https://get.k3s.io -o /tmp/install-k3s.sh
INSTALL_K3S_VERSION='v1.35.9+k3s1' sh /tmp/install-k3s.sh server --disable traefik --disable servicelb --write-kubeconfig-mode 600
rm /tmp/install-k3s.sh
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
kubectl wait --for=create node/amlarclab-edge --timeout=180s
timeout 180 kubectl wait --for=condition=Ready node --all
kubectl get nodes -o wide
az version
k3s --version
printf 'NO_PROXY=%s\n' "$NO_PROXY"
