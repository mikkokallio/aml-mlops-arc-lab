# AML MLOps Arc lab

A public, unbranded example of deploying a tracked tabular regression model
through Azure Machine Learning to Arc-enabled k3s.

**Current status: implementation in progress. No successful Arc scoring result
has been recorded yet.**

## Current acceptance target

1. Probe permissions, policy, regional capacity, and supported versions.
2. Provision isolated ML, edge, Fabric, and identity resource groups.
3. Bootstrap a private-IP-only Linux VM and an intentionally pinned k3s release.
4. Connect Arc, install AML's inference extension, and attach Kubernetes compute.
5. Train/log/register a small signature-bearing MLflow model.
6. Deploy with AML and compare real endpoint predictions with the same model.

Fabric integration, full training pipelines, release automation, monitoring, and
independent ownership drills are separate milestones, not implicitly passed by
this first probe.

## Documentation

- [Approved addendum](docs/plan-addendum.md)
- [Permission and roadblock register](docs/ROADBLOCKS.md)
- [Ownership evidence](docs/OWNERSHIP.md)
- [Version policy](docs/versions.md)
- [Measured results and unresolved checks](docs/evidence/current-run.md)

## Safety and evidence

The edge VM has no public IP. No public SSH or scoring NodePort is required.
Raw management outputs, credentials, account identifiers, model artifacts and
generated data stay in ignored local paths. Only sanitized evidence is published.

Tenant guardrails require private storage and Key Vault. Their public access
stays disabled; private endpoints/DNS provide the client data path. Storage
allows the single AML workspace resource instance for authenticated service-side
access. Training from the laptop cannot directly access these private endpoints;
the current probe invokes training inside the VNet under the DS identity.

Infrastructure is Bicep under `infra`. Preview each deployment with what-if.
Elevated role changes use the logged scripts under `scripts/admin`.
Permission to create resources is not permission to reuse unrelated resources.

The synthetic data generator includes campaign warm-up behavior and deliberately
forbidden post-outcome features. This is lab data, not a customer's process model.

## Running costs

The VM shutdown schedule does not stop NAT gateway, private endpoint, registry,
storage, logging, or other provisioned-service charges. Private connectivity
adds recurring costs. No measured total or cost ceiling is claimed yet.
The Fabric resource group is empty; no Fabric capacity has been provisioned.
Preserve the Arc compute's Azure Relay dependency during pauses; do not let a
VM janitor delete it.

## Local training validation

Use the isolated environment and exact dependencies in `requirements.txt`:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe .\src\train.py --output .\outputs\local
```

Select an AMD64 interpreter explicitly on Windows ARM machines. Workspace
tracking requires an actual AML tracking URI and authorized Azure credentials.
Do not treat local file-based MLflow tracking as an AML run.
