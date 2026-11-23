#!/usr/bin/env bash
set -euo pipefail
umask 077
export AZURE_CONFIG_DIR=/var/lib/aml-arc-lab/az-ds
export AZURE_EXTENSION_DIR=/root/.azure/cliextensions
directory="$(readlink -f /var/lib/aml-arc-lab/command-jobs/latest)"
export LAB_INSPECT_JOB="$(cat "$directory/job-name")"
export LAB_ARTIFACT_CONTAINER="$(az ml datastore show --name workspaceartifactstore --resource-group rg-amlarclab-ml --workspace-name mlw-amlarclab --query container_name --output tsv)"
/var/lib/aml-arc-lab/training/.venv/bin/python - "$directory/download" <<'PY'
import os
from pathlib import Path
import sys

from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient

root = Path(sys.argv[1])
client = BlobServiceClient(
    account_url="https://" + os.environ["LAB_STORAGE_HOST"],
    credential=ManagedIdentityCredential(client_id=os.environ["LAB_COMPUTE_CLIENT_ID"]),
)
container = client.get_container_client(os.environ["LAB_ARTIFACT_CONTAINER"])
prefix = "ExperimentRun/dcid." + os.environ["LAB_INSPECT_JOB"] + "/"
print("LOG_READ_IDENTITY compute UAMI with existing Storage Blob Data Reader")
for blob in container.list_blobs(name_starts_with=prefix):
    relative = Path(blob.name[len(prefix):])
    if ".." in relative.parts:
        raise ValueError("Unexpected job artifact path")
    if relative.suffix in (".txt", ".log", ".json"):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(container.download_blob(blob.name).readall())
logs = list(root.rglob("std_log.txt"))
if logs:
    for path in logs:
        print("USER_LOG", path.relative_to(root))
        print(path.read_text(errors="replace")[-2400:])
else:
    print("NO_USER_STD_LOG")
    for path in sorted(root.rglob("*")):
        if path.is_file():
            print("DOWNLOADED_FILE", path.relative_to(root))
    for path in root.rglob("data-capability.log"):
        lines = path.read_text(errors="replace").splitlines()
        errors = [i for i, line in enumerate(lines) if line.startswith("ERROR ")]
        if errors:
            print("DATA_CAPABILITY_FIRST_ERROR")
            print("\n".join(lines[errors[0]:errors[0]+12])[:2200])
    for name in ("execution-wrapper.log", "lifecycler.log"):
        for path in root.rglob(name):
            print("SYSTEM_LOG", path.relative_to(root))
            print(path.read_text(errors="replace")[-400:])
PY
