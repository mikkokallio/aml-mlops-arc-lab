umask 077
cd /var/lib/aml-arc-lab
export AZURE_CONFIG_DIR=/var/lib/aml-arc-lab/az-fabric-p-ci
export LAB_FABRIC_EVIDENCE="/var/lib/aml-arc-lab/.local/fabric/$LAB_FABRIC_RUN"
install -d -m 700 "$AZURE_CONFIG_DIR" "$LAB_FABRIC_EVIDENCE"
timeout 90 az login --identity --client-id "$LAB_CI_CLIENT_ID" --allow-no-subscriptions --output none \
    > "$LAB_FABRIC_EVIDENCE/login.stdout" 2> "$LAB_FABRIC_EVIDENCE/login.stderr"
printf '%s' "$LAB_FABRIC_PROBE_BASE64" | base64 --decode > "$LAB_FABRIC_EVIDENCE/probe.py"
timeout 420 python3 "$LAB_FABRIC_EVIDENCE/probe.py"
