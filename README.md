# AML MLOps Arc lab

A public, unbranded example of deploying a tracked tabular regression model
through Azure Machine Learning to Arc-enabled k3s.

**Current status: training and a private AML managed-online serving lifecycle
have passed within the recorded boundaries. Arc scoring remains blocked;
Fabric is explicitly deferred. All five alternative-target serving tests passed.
All temporary serving targets, their owned infrastructure and the private
client worker are removed, with deletion verified.**

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
adds recurring costs. No measured total invoice is claimed for the original lab.
The Fabric resource group is empty; no Fabric capacity has been provisioned.
Preserve the Arc compute's Azure Relay dependency during pauses; do not let a
VM janitor delete it.

The separate disposable-serving matrix has a EUR30 incremental working ceiling,
not an Azure billing cap. Targets are tested sequentially and removed after
evidence capture; the original Arc infrastructure is preserved.

## Disposable inference alternatives

The primary private **AML managed online endpoint** passed real scoring,
blue/green promotion and rollback, primary-key rotation with stale-key rejection
and unchanged-secondary scoring, package-index-denied startup, a real Fired
inference-failure alert, and a 9,489-row comparison against the live champion.
Its endpoint and temporary inference alert were then deleted and independently
verified absent; the registry was restored from temporary Premium to Basic.

Native **AML-on-AKS** also passed extension installation, compute attachment,
registered-model deployment and actual private REST scoring: 100 predictions
with zero reference error. This used a private HTTP NodePort for the lab, not
production TLS or a restricted-persona deployment drill.

The separate **private VM container** also passed real worker-to-VM health,
exact registered-model hashes and 100 REST predictions with zero reference
error. It has no public IP; this is portable HTTP serving, not AML management.

**Private ACI** also passed real health/model hashes and 100 REST predictions
with zero reference error, then its group/subnet were removed.

**Internal Container Apps** also passed real private HTTPS scoring with verified
TLS, exact model hashes and 100 predictions with zero reference error.

All five selected targets passed their scoped tests.
Provisioning is not a REST pass. VM/ACI/ACA
tests establish portable serving only, not AML-managed deployment acceptance.
The [portable service instructions](scripts/serving/README.md) describe the
common container and strict 100-row cross-network comparison.
Disposable templates are under `infra/serving`; always inspect what-if, use
separate owned subnets, and remove owned targets before proceeding.

These are operator-orchestrated tests, not GitHub model-release acceptance,
fresh-checkout training-code packaging, independent approval, drift monitoring,
or external notification delivery. See the [measured evidence](docs/evidence/current-run.md)
and [permission findings](docs/ROADBLOCKS.md) for precise acceptance boundaries.

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

## GitHub main-branch controls

A repository administrator applies the versioned ruleset to a new lab repository:

```powershell
$Repo = gh repo view --json nameWithOwner --jq .nameWithOwner
gh api --method POST "repos/$Repo/rulesets" --input .github\main-ruleset.json
```

For an existing ruleset, use PUT on `repos/$Repo/rulesets/<ruleset-id>` instead.
This requires GitHub repository administration permission, not Azure Owner.
The rules require PRs and the actual GitHub Actions contract check, including
for administrators; force-push and deletion are forbidden. This single-person
lab requires zero PR approvals because GitHub prohibits approving one's own PR.
Independent code review is therefore not demonstrated. The separate production
environment gate permits recorded lab self-approval; see measured evidence for
its execution status.

## GitHub OIDC bootstrap

After the identity deployment outputs exist in the ignored local directory,
the authorized identity administrator runs:

```powershell
.\scripts\admin\Initialize-LabOidc.ps1
```

The helper reads this lab repository's actual GitHub subject policy and stable
owner/repository IDs. It supports explicitly reported immutable or legacy
default subjects and rejects unknown/custom policy. Do not copy a name-only
subject from an older tutorial into a repository using immutable subjects.

For the exact previously created train/prod legacy credentials, an explicitly
requested correction is:

```powershell
.\scripts\admin\Initialize-LabOidc.ps1 -ReplaceLegacySubjects
```

Replacement mode preserves issuer, audience, environment restrictions and
unrelated credentials; it cannot create a missing credential. Writes require
federatedIdentityCredentials/write at the P-CI identity, not merely Managed
Identity Operator or AML-RG Contributor. Attempts/results stay in the private
admin log. Mocked boundary/idempotency tests also run in required PR CI:

```powershell
.\tests\Test-LabOidc.ps1
```

The actual OIDC/approval probe has passed, but does not deploy a model.
Fabric integration is explicitly deferred in this lab and remains untested.

## GitHub-launched reference-only training

The manual `train-registered-pipeline.yml` workflow uses the existing P-CI
identity in the train environment. It submits and polls ARM management APIs;
the GitHub-hosted runner does not upload source/data or access private MLflow,
artifact or storage endpoints:

```powershell
gh workflow run train-registered-pipeline.yml --ref main
```

This lab-specific proof requires the recorded successful baseline job and its
registered f563 components, environment 2, data 2 and synthetic reference model
2. The helper validates those references before submission and forces component
execution rather than cached reuse. It records the actual component source SHA
separately from the workflow/orchestrator SHA.

This deliberately reuses registered assets; it is not fresh-checkout code
packaging, Fabric integration, deployed-champion selection or model deployment.
A Completed pipeline can legitimately produce NOT_REGISTERED. Its private gate
artifacts are not read by this workflow.
[Actual run 45230564606](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45230564606)
passed and all five AML child jobs independently read back Completed.
See the measured-results document for exact provenance and remaining boundaries.

## Azure-only training-failure alerts

The operator chose Azure-only alert verification, with no email, webhook or
action-group receiver. Customer setup must explicitly ask notification and
response-owner preferences instead of inheriting that lab choice.

The monitoring templates reference only the existing lab AML/Log Analytics
workspaces. They add a separate diagnostic setting, leaving tenant-governance
settings untouched:

```powershell
.\scripts\Deploy-Group.ps1 -ResourceGroup rg-amlarclab-ml `
  -Template infra\monitoring\diagnostics.bicep -DeploymentName lab-training-diagnostics
```

Verify that the destination accepts an `AmlRunStatusChangedEvent` query before
deploying the alert; query validation is deliberately not skipped:

```powershell
.\scripts\Deploy-Group.ps1 -ResourceGroup rg-amlarclab-ml `
  -Template infra\monitoring\failed-job-alert.bicep -DeploymentName lab-training-failed-alert
```

The controlled `failure_fixture.py` command supports execution and quality
failure cases. Run it in an AML command job with the registered f563 code root,
environment 2, mounted data 2 and a real committed fixture SHA. Base64/compile/exec
bootstrapping is supported so the fixture can be supplied through the ARM command
without source upload. The quality case saves/logs a deliberately bad constant
model and runs the unchanged evaluator/policy; it logs metrics/decision and
raises QUALITY_GATE_FAILED. Neither case registers a model.

The unchanged evaluator finishes its MLflow metrics run before raising a failed
quality decision. That evaluation run can legitimately be FINISHED while the
enclosing AML command job is Failed. Do not reopen it or force another terminal
status: AML rejects that transition and masks the intended quality-gate error.

Both AML jobs must actually fail for their intended reasons, verified from logs.
Acceptance additionally requires ingested
failure events and Fired alert instances matching both exact RunIds, not just
successful template deployment. A passing negative-test verification must never
be described as successful production training. External notification delivery
is a separate, untested boundary in this Azure-only lab.

For readback, query the owned Log Analytics workspace for the exact RunIds and
`Status == 'Failed'`. ARM normalized `logAnalyticsDestinationType` to null in
this lab, but actual events arrived in `AmlRunStatusChangedEvent`; configuration
readback alone does not establish their destination or successful ingestion.

List actual alert instances through the owned resource group's
`Microsoft.AlertsManagement/alerts` API (2019-03-01), using `includeContext=true`,
`timeRange=1h` and `pageCount=25`, following any `nextLink`. The `alertRule` filter
requires the **full scheduled-query-rule ARM ID**, not `aml-training-failed`.
For each expected job, verify `properties.essentials.monitorCondition == 'Fired'`
and its exact RunId in
`properties.context.context.condition.allOf[].dimensions[]`.
Neither an empty result from an incorrect filter nor an unrelated Fired alert
establishes the outcome. On Windows, preserve the complete URL's query string
when passing it through the Azure CLI wrapper.

Actual cloud verification passed for execution job
`aml-alert-execution-52b2cc0` and corrected quality job
`aml-alert-quality-b36ee32`: intended failure reasons, persisted quality evidence,
ingested failure events and exact Fired alerts were verified. Observed delays
were 97.230 s and 50.185 s respectively; these are not an SLA.
See [measured results](docs/evidence/current-run.md#azure-only-training-failure-alerts).
External delivery and inference monitoring remain untested.
