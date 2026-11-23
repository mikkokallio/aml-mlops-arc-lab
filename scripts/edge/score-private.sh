#!/usr/bin/env bash
set -euo pipefail
python3 -c 'import ipaddress,os,socket; a={x[4][0] for x in socket.getaddrinfo(os.environ["LAB_VAULT_HOST"],443,family=socket.AF_INET)}; print("VAULT_PRIVATE_DNS",sorted(a)); assert a and all(ipaddress.ip_address(x).is_private for x in a), "Vault must resolve privately"'
directory=/var/lib/aml-arc-lab/training
install -d -m 700 "$directory/scripts"
printf '%s' "$LAB_COMPARE_CODE_BASE64" | base64 --decode > "$directory/scripts/compare_predictions.py"
printf '%s' "$LAB_SCORE_CODE_BASE64" | base64 --decode > "$directory/scripts/score_private.py"
"$directory/.venv/bin/python" "$directory/scripts/score_private.py"
