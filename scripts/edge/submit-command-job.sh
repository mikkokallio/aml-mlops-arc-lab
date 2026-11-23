#!/usr/bin/env bash
set -euo pipefail
umask 077
export AZURE_CONFIG_DIR=/var/lib/aml-arc-lab/az-ds
export AZURE_EXTENSION_DIR=/root/.azure/cliextensions
export AZURE_CLIENT_ID="$LAB_DS_CLIENT_ID"
export PYTHONIOENCODING=utf-8
python=/var/lib/aml-arc-lab/training/.venv/bin/python
if [[ ! -x "$python" ]]; then
    echo "The validated private training environment is required." >&2
    exit 1
fi
install -d -m 700 "$AZURE_CONFIG_DIR" /var/lib/aml-arc-lab/command-jobs
az login --identity --client-id "$LAB_DS_CLIENT_ID" --output none
directory="$(mktemp -d /var/lib/aml-arc-lab/command-jobs/job-XXXXXXXX)"
export LAB_JOB_DIRECTORY="$directory"
printf '%s' "$LAB_JOB_SOURCE_BASE64" | base64 --decode > "$directory/source.zip"
"$python" -m zipfile -e "$directory/source.zip" "$directory/source"
"$python" - <<'PY'
import os
from pathlib import Path

import yaml

directory = Path(os.environ["LAB_JOB_DIRECTORY"])
source = directory / "source"
job = yaml.safe_load((source / "config/training-job.yml").read_text())
job["code"] = str(source)
job["environment_variables"] = {
    "MLFLOW_TRACKING_URI": os.environ["LAB_TRACKING_URI"],
    "LAB_GIT_SHA": os.environ["LAB_GIT_SHA"],
}
job["tags"] = {"source_sha": os.environ["LAB_GIT_SHA"]}
(directory / "job.runtime.yml").write_text(yaml.safe_dump(job))
PY
az ml job create --file "$directory/job.runtime.yml" --resource-group rg-amlarclab-ml --workspace-name mlw-amlarclab --output json > "$directory/submission.json"
job="$("$python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$directory/submission.json")"
printf '%s\n' "$job" > "$directory/job-name"
ln -sfn "$directory" /var/lib/aml-arc-lab/command-jobs/latest
echo "SUBMITTED_AS_P_DS $job"
echo "SOURCE_SHA $LAB_GIT_SHA"
az ml job show --name "$job" --resource-group rg-amlarclab-ml --workspace-name mlw-amlarclab --query '{name:name,status:status,compute:compute,experiment:experiment_name}' --output json
