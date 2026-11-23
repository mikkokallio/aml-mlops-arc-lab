# Portable campaign model service

Build context is this directory (`scripts\serving`), not the repository root.
Before building, place the complete, privately downloaded MLflow artifacts at
`models\1\MLmodel` and `models\2\MLmodel` (with their referenced model files).
These artifacts are inputs, not source-controlled files. Override `BASE_IMAGE`
with a verified immutable Python 3.12 Debian image reference when building.
Dependencies and libgomp are installed at build time only; startup never runs pip.

Set `MODEL_VERSION` explicitly to `1` or `2`. When `AZUREML_MODEL_DIR` is present,
exactly one recursively discovered `MLmodel` is required there. Invalid or empty
mounts fail startup; they never fall back to the bundled `/opt/models/<version>`.
Otherwise only the selected bundled version is used. The deployment owns matching
the mounted model asset version to `MODEL_VERSION`; the content manifest provides
an independent identity check. Models load once before Gunicorn starts accepting
requests, under UID/GID 1000.

Listen on port 8080. For AML custom `inference_config`, use `/health` for both
liveness and readiness routes, and `/score` for the scoring route, all port 8080.
The same container runs without AML on VM, ACI, or ACA.

`POST /score` accepts only `{"input_data":{"columns":[...],"index":[...],"data":[...]}}`.
Columns must match the saved numeric signature exactly:
`item_position`, `setting_a`, `setting_b`. Accepts 1–500 rows; returns one flat
JSON array of finite predictions. Invalid payloads return JSON HTTP 400;
unexpected inference failures are logged and return Flask HTTP 500, not predictions.

`GET /health` reports the selected version, mounted/bundled source, sorted
model-file paths, sizes and SHA256 hashes, and an aggregate SHA256 of the compact
sorted-key JSON file manifest. Hashes cover the entire selected model directory
before loading. `SOURCE_GIT_SHA` (or `LAB_GIT_SHA`) and `MODEL_PROVENANCE` provide
explicit non-secret provenance labels. Never put secrets in these labels.
Startup emits the same safe snapshot as a single JSON `serving_ready` log event,
including both package-index results, so deployment container logs can supply
this evidence even when `/health` is only accessible to platform probes.

`PROBE_PACKAGE_INDEX=1` enables two startup-only HTTPS probes (five-second
timeout each): `pypi.org/simple/pip/` and `files.pythonhosted.org/`. Health reports
each result separately as `allowed` or `blocked`; any HTTP response, even an
error status, proves reachability. Network errors are explicitly logged.
Probe failure never prevents model loading and never installs anything.
A blocked result describes this request, not the cause of the network failure.
Unset the flag for no package-index requests.

## Disposable portable REST checks

The VM bootstrap `start-vm.sh` installs Docker, obtains an in-memory ACR login
with the VM's `AcrPull` identity, pulls an immutable image, logs out, and starts
version 2. Run it only on a fresh disposable VM, with `ACR_SERVER`, `IMAGE` and
`IDENTITY_CLIENT_ID` set. Its loopback check is readiness, not acceptance.
When using the Run Command wrapper, invoke this standalone script in a child
`bash` process; pasting it inline lets its exit0 skip the wrapper's final marker.

From a separate private client, run `python -m scripts.check_portable_serving`
with `--target vm|aci|aca`, `--url`, `--request`, `--reference`,
`--model-manifest-sha256` and `--output`. Inputs are the original 100-row request
and predictions saved during the registered-model image build. All resolved
addresses must be private and non-loopback, and curl is pinned to a verified
address. For ACA's internal ingress use its real HTTPS hostname plus
`--resolve-ip <environment-private-ip>`; this preserves TLS verification without
creating a permanent private DNS zone. The checker verifies actual readiness
identity and 100 REST predictions, not just provisioning state. These portable
checks do not establish AML-managed deployment acceptance.
Default curl configuration is disabled so implicit insecure/redirect options
cannot override the check.
