#!/usr/bin/env bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export AZURE_CONFIG_DIR=/var/lib/aml-arc-lab/az-ds
export AZURE_EXTENSION_DIR=/root/.azure/cliextensions
export AZURE_CLIENT_ID="$LAB_DS_CLIENT_ID"
export PYTHONIOENCODING=utf-8
install -d -m 700 "$AZURE_CONFIG_DIR"
python3 -c 'import ipaddress,os,socket; addresses={x[4][0] for x in socket.getaddrinfo(os.environ["LAB_STORAGE_HOST"],443,family=socket.AF_INET)}; print("BLOB_PRIVATE_DNS",sorted(addresses)); assert addresses and all(ipaddress.ip_address(x).is_private for x in addresses), "Blob must resolve privately"'
az login --identity --client-id "$LAB_DS_CLIENT_ID" --output none
apt-get update -qq
apt-get install -y -qq python3-venv
directory=/var/lib/aml-arc-lab/training
install -d -m 700 "$directory/src" "$directory/config"
printf '%s' "$LAB_TRAIN_CODE_BASE64" | base64 --decode > "$directory/src/train.py"
printf '%s' "$LAB_FEATURES_BASE64" | base64 --decode > "$directory/config/features.yaml"
printf '%s' "$LAB_REQUIREMENTS_BASE64" | base64 --decode > "$directory/requirements.txt"
python3 -m venv "$directory/.venv"
"$directory/.venv/bin/python" -m pip install --quiet -r "$directory/requirements.txt"
"$directory/.venv/bin/python" -m pip check
cd "$directory"
output="$directory/outputs/$(date -u +%Y%m%dT%H%M%SZ)"
"$directory/.venv/bin/python" src/train.py --output "$output" --tracking-uri "$LAB_TRACKING_URI" --register
ln -sfn "$output" "$directory/latest-output"
