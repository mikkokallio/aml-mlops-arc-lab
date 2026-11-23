# First lab run: evidence, not an acceptance claim

23 November 2026. **Arc inference acceptance: NOT PASSED.**

## Verified

- Four isolated resource groups created; required providers Registered.
- Identity, ML dependency/workspace, and edge Bicep deployments succeeded after
  what-if. Bootstrap used authorized Owner, not the restricted persona.
- Standard_D4s_v5 VM: private IP only; no VM public IP and no public inbound rule.
- Before NAT: serial cloud-init probe could not reach ARM, PyPI or MCR.
- After dedicated NAT: all three transport probes reachable.
- Ubuntu x86-64, k3s v1.35.9+k3s1, node Ready.
- Arc control-plane resource: Succeeded, Connected; observed agent 1.39.3.
- Restricted-persona boundary failures and subsequent scoped role grants recorded
  in the [roadblock register](../ROADBLOCKS.md).
- AML namespace created and lab-cpu InstanceType admitted with 500m CPU request.
- Local isolated dependencies pass pip check; six focused training/scoring
  contract tests pass. Training and scoring Python passed Pylance syntax validation.
- SDK loads the endpoint and deployment YAML as Kubernetes entities.
- Private Blob/File/Key Vault endpoints and private DNS deployment succeeded.
- Verified storage: public access Disabled, shared keys disabled, default Deny,
  exactly one allowed resource instance (the workspace). Key Vault: private,
  default Deny, documented trusted-services bypass.
- Minimal MLflow metric logging now succeeds with that scoped configuration.
- P-DS completed real workspace MLflow training, metric/artifact logging and model
  registration from the private VM. Independent AML CLI readback confirms
  `campaign-xgboost:1`, type `mlflow_model`.
- Synthetic data: 49,457 rows, 550 campaigns; campaign-grouped final-20% holdout.
  Model MAE 0.4291787231 versus median-baseline MAE 4.5796678028.
- Logged model includes its signature and input example. Reloaded MLflow pyfunc
  produced 100 reference predictions, checked against the trained estimator.
  These are reference predictions, not endpoint responses.
- Initial training provenance is `git_sha=uncommitted`; this run does not prove a
  committed-source or CI provenance chain.

## Failed / unresolved

- Initial AML extension 1.1.115 install timed out after identity components
  rejected cluster type Unknown. Initial create and corrective update both
  failed. Actual 1.1.109 containers reproduce the same crash; its control-plane
  update also timed out.
  ARM extension identity reports SystemAssigned, but Helm release configuration
  reports UserAssigned in both legacy and global identity fields. Supplying
  Azure.Identity.Type=SystemAssigned did not resolve the mismatch.
  This is an observed installation blocker, not yet a vendor-confirmed defect.
  No direct patch to a managed pod was made.
- Automatic-minor upgrades restored: ARM confirms mode compatible and
  autoUpgradeMinorVersion true. A final configuration check supplies
  global.azure.identity.type=SystemAssigned, matching actual ARM identity.
  ARM accepted the setting. The new Helm install still renders both identity
  fields as UserAssigned, and its actual 1.1.109 gateway/proxy containers again
  crash with Unknown cluster type. The final control-plane update also timed out.
- Original storage failures were OAuth 403 responses. Operator confirmed tenant
  guardrail remediation. Public-access attempts stopped; a private/scoped-trust
  configuration resolved minimal metric logging.
- Compute attach has progressed past two specific permission denials, but is
  blocked by the extension not being Installed.

## Not run

AML inference deployment, endpoint scoring/reference comparison,
package-index-denied deployment,
release/rollback, Fabric ingestion, independent ownership drills and the remaining MLOps
milestones have **not** passed.

Training succeeded under the restricted P-DS identity inside the VNet, invoked
from VS Code via Run Command. This does not demonstrate the VS Code AML
GUI extension or an interactive remote-development experience.

Neither Arc Connected nor a local model/test substitutes for real AML scoring.

## Independent work advanced while Arc is blocked

- Private AML managed compute provisioned, zero minimum/one maximum node and
  no public node IP. Its required workspace private endpoint was added after
  the initial create returned that explicit prerequisite error.
- Immutable-base-image training environment registered. P-DS submitted a real
  AML command job with committed-source provenance. It reached Running, then
  failed before user code while mounting writable workspaceblobstore output.
  Its separate training-compute identity had no storage data role. Owner granted
  Storage Blob Data Contributor on that exact container. Retry entered user
  code, proving that mount blocker cleared, but failed because mlflow was absent.
  Actual environment v1 has null conda_file: assigning it after SDK construction
  did not serialize dependencies. Constructor-based registration of immutable
  v2 was corrected, registered and independently read back with every pinned
  dependency. Retry `musing_branch_g8hmb817q6` completed and registered
  `campaign-xgboost:2`, MAE 0.4291787231. It used the original committed d9345fe
  source archive with an explicit environment-v2 runtime override; the archive
  was not relabelled as newer source.
  The read-only inference identity was not widened.
- Five-component synthetic pipeline implementation passes local contracts and
  SDK YAML validation. Combined training, scoring, CI and pipeline suite:
  23 passed. CI schema coverage was then extended: all eight endpoint,
  deployment, pipeline and component cases pass with network access denied.
  Actual eligible pipeline `sincere_potato_q841s2zp8c` subsequently completed
  and registered `campaign-m3-synthetic-proof:1`. Actual controlled rejection
  `magenta_carpet_7xbqwfc7jp` completed with NOT_REGISTERED and no new model
  version. Both used committed source
  f563c2fca1d62a6f9a4d209ca5be44d70b65de83, environment 2, managed identities
  and synthetic data version 1. Data version 2 was separately registered;
  that registration alone is not proof of its pipeline consumption.
  The comparison model is an explicit synthetic fixture, not a deployed
  champion. Neither execution proves Fabric ingestion or production release.
- GitHub OIDC federated credentials and repository secrets are configured.
  The [first actual Actions run](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45205044415)
  failed in train authentication; production was skipped and no approval made.
  Safe boolean-only assertion diagnostics established that this new repository
  uses GitHub's immutable OIDC subject, including owner and repository IDs,
  rather than the legacy name-only subject. Only the two existing environment
  federated-credential subjects were corrected; issuer, audience and environment
  restrictions were preserved.
  [Actual corrected run](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45212597530)
  passed both P-CI Azure logins and exact-workspace ARM reads. Production was
  observed WAITING before operator self-approval, then succeeded.
  This proves the control-plane identity and approval pause, not independent
  review, model deployment or an end-to-end release.
- Azure-free GitHub CI baseline [passed](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45197315333).
  A [real leaking-feature PR](https://github.com/mikkokallio/aml-mlops-arc-lab/pull/9)
  [failed](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45197690905)
  specifically because measured_outcome is forbidden by the feature contract.
  The PR was closed without merging and its temporary branch deleted.
  Syntax/indentation checks are not a full Python linter.
- Main ruleset is active with no administrator bypass: an actual direct
  administrator push was rejected (GH013). A PR-only leaking-feature fixture
  [failed CI](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45205748229)
  with Forbidden post-outcome feature: measured_outcome; the attempted merge was
  rejected after that completed failure. The fixture was restored without
  entering main or the shared local worktree.
  The restored [PR 10](https://github.com/mikkokallio/aml-mlops-arc-lab/pull/10)
  [passed required CI](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45207190294)
  and merged without bypass. Zero required PR approvals is an
  explicit single-person lab limitation, not independent review.
- Fabric ARM capacity discovery passed; Fabric API token acquisition failed
  for operator and P-CI with AADSTS500014 (resource service principal disabled).
  Requires Entra-admin investigation; do not misclassify it as missing capacity
  or a Fabric SP allowlist denial.
  [Assigned admin-action issue 11](https://github.com/mikkokallio/aml-mlops-arc-lab/issues/11)
  tracks the tenant-policy decision and mandatory token/API retests.
  The signed-in Edge/Entra session confirms the exact resource application is
  Power BI Service: its identifiers include the Fabric API, activation is
  Deactivated and user sign-in is No. The user approved enabling this one
  tenant-wide application. The current portal exposes its Yes/No control as
  disabled/read-only; no mutation or permission workaround has been performed.
  The operator subsequently deferred Fabric testing in this lab. No further
  tenant access or capacity purchase is requested. Enabling, token/API retests
  and real ingestion remain NOT TESTED for a suitable environment/customer
  prerequisite; the synthetic pipeline is not their replacement.

## Arc workaround experiments

- Original-cluster Flux installation returned ARM Succeeded; Helm release is
  deployed, chart/app version 1.26.6. Flux also receives UserAssigned in both
  identity fields, despite SystemAssigned defaults. Thus the injected value is
  not unique to AML; its producer remains unconfirmed. This does not prove a
  Flux reconciliation workload or fix AML's legacy selector.
- Incoming ExtensionConfig objects live in the release namespaces. Both AML
  and Flux already contain spec.parameter.IdentityType UserAssigned, before
  Helm rendering. AML additionally retains both diagnostic SystemAssigned
  settings; they do not override the effective value.
- Explicit stable and preview Arc API reads expose no OIDC/workload-identity
  profile. Absence is not a verified enabled=false value; no speculative disable
  or identity override was applied.
- Both clean disposable experiments reproduced the installation failure:

  | Case | Arc location | k3s | Arc agent | AML extension | Actual outcome |
  |---|---|---|---|---|---|
  | A: different Kubernetes minor | Sweden Central | 1.36.6+k3s1 | 1.39.3 | 1.1.115 | Incoming UserAssigned; identity controller/proxy/gateway crash-loop with Unknown cluster type |
  | B: different Arc region | North Europe | 1.35.9+k3s1 | 1.39.3 | 1.1.115 | Same incoming value and constructor failure |

  Case A explicitly reported workload identity Disabled; ARM extension identity
  was SystemAssigned. Case B's VM remained in Sweden Central while its Arc
  resource used North Europe. Case A was stopped while ARM still reported
  Creating; that state is not a successful installation.
- Full health/component evidence was retained privately. Both disposable cases'
  resources were deleted and cleanup verified. The original cluster remains.
  Following the agreed stop rule, no further speculative identity changes,
  cluster replacements or agent downgrades are planned. One consolidated support
  brief covers the original cluster and both failed isolation cases; it has not
  been submitted to Microsoft.
