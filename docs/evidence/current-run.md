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
  and synthetic data version 1.
  The comparison model is an explicit synthetic fixture, not a deployed
  champion. Neither execution proves Fabric ingestion or production release.
- Changed-data execution `cyan_quince_gwc0wwhyfw` completed using synthetic
  data version 2, the same committed f563 components and environment 2.
  The snapshot SHA-256 changed from
  `112917b49ac405bb0dae20d7f06fceb1c467d6fda4b20ae942c2b4d216bc4203`
  to `71ec5e60738c608842937bdc42d62a6e32129467d9ee38ca1da6346bff6c3750`.
  Candidate and registered-model-v1 fixture were evaluated on the SAME new
  campaign-grouped holdout: MAE 0.4167589735 versus 0.4229801117,
  a 1.4708% improvement. Candidate 1-49/50+ MAE was
  0.4202226723/0.4122043658; both satisfy the absolute 2.0 threshold.
  The unchanged policy returned ELIGIBLE and registered
  `campaign-m3-synthetic-proof:2`, linked to training run
  `f3eda736-d476-4bb3-94fb-d1245e1dda87`.
  Existing registered components were reused without source/data upload;
  every component used managed identity and no new grants were added.
  The original VM was restored to deallocated; its schedule was unchanged.
  This proves changed-data consumption/lineage and same-holdout synthetic
  comparison, not a deployed-champion or GitHub-triggered-training acceptance.
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
- **Actual GitHub-launched training PASSED:**
  [run 45230564606](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45230564606)
  used P-CI/train OIDC to submit `gha-registered-45230564606-1`, then polled ARM
  until Completed. Independent AML CLI readback confirms all five child jobs
  Completed. The runtime used registered f563 components, environment 2, data 2,
  explicit synthetic reference model 2, managed identities and force_rerun true.
  Component source SHA is f563c2fca1d62a6f9a4d209ca5be44d70b65de83;
  orchestrator SHA is separately 520361931b61a376b843e5d30c840f700ee5ea1e.
  The hosted runner uploaded no training source/data and accessed no private
  MLflow/artifact endpoints. No new grants or VM start were required.
  Registry readback still lists only synthetic proof model versions 1 and 2.
  The workflow did not read private gate artifacts: do not infer a particular
  decision reason from Completed or from the unchanged registry.
  This is genuine Actions-launched managed training, not fresh-checkout code
  packaging, production deployment, Fabric or deployed-champion proof.
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

## Azure-only training-failure alerts

**PASSED: real execution failure and real quality-gate failure, ingested events
and exact per-RunId Fired alerts.** These are successful negative tests, not
successful production training. All times below are UTC on 23 November 2026.

| Case / actual AML job | Failed event | Fired alert | Observed delay |
|---|---|---|---|
| Execution: `aml-alert-execution-52b2cc0` | 18:29:40.554 | 18:31:17.784 | 97.230 s |
| Corrected quality: `aml-alert-quality-b36ee32` | 19:03:23.649 | 19:04:13.835 | 50.185 s |

- Private job logs confirm the execution case's CONTROLLED_EXECUTION_FAILURE
  and the corrected quality case's final QUALITY_GATE_FAILED, with no masking
  BAD_REQUEST. Both enclosing AML command jobs are Failed.
- The quality fixture fitted, saved, logged and reloaded a deliberately bad
  constant model against real synthetic data version 2. The unchanged f563
  evaluator/policy produced overall MAE 986.595207 and 1-49/50+ slice MAEs
  985.623476/987.872989, failing the absolute 2.0 thresholds. The persisted
  ineligible decision, metrics logged before failure, policy/features,
  actual model URI and source/data provenance were verified privately.
  Registry readback still lists only synthetic-proof model versions 1 and 2.
- Execution fixture SHA: 52b2cc08a44594d4b3b596ec0198634eb175df21.
  Corrected quality fixture SHA: b36ee32f653933f467086e97ce2772cc257dcf60.
  Both used registered core source
  f563c2fca1d62a6f9a4d209ca5be44d70b65de83, environment 2 and managed compute.
  [Required CI for the correction](https://github.com/mikkokallio/aml-mlops-arc-lab/actions/runs/45244054047)
  passed.
- The first quality fixture exposed a real backend difference: AML rejects
  changing an already FINISHED evaluation run to another terminal state.
  That attempted transition masked the quality-gate error. The correction
  preserves the original exception without reopening the run; an immutable-
  terminal regression catches the original bug. The evaluator's metrics run
  is honestly FINISHED while the enclosing AML command is Failed.
- A separate lab-owned diagnostic setting forwards only
  AmlRunStatusChangedEvent into the owned Log Analytics workspace. ARM returned
  null for logAnalyticsDestinationType despite the requested Dedicated value;
  actual rows, not that property, establish the resource-specific table.
  The query-validated enabled rule produced a distinct Sev2 Fired alert for
  each exact RunId, with count 1 greater than threshold 0.
  The alertRule API filter requires the full scheduled-query-rule ARM ID.
- No action-group receivers were configured. No potentially applicable enabled
  inherited AddActionGroups rules were found. Existing governance diagnostics
  and their external workspace were untouched. **External notification delivery
  is NOT TESTED**, as explicitly chosen by the operator; customer rollout must
  collect notification/response-owner preferences.
- No role grants or public-network relaxations were added. Private artifact
  verification temporarily used the original VM, restored and verified
  deallocated with its shutdown schedule unchanged. Exact operations and
  permissions are in the private action log and [roadblock register](../ROADBLOCKS.md).
  Monitoring execution used the authorized Owner; restricted-persona monitoring
  acceptance is not claimed. These two measured delays are not a delivery SLA
  or inference-monitoring acceptance.

## Disposable serving-target matrix

The operator approved sequential tests of five targets with a EUR30 incremental
working ceiling: AML managed online (primary lifecycle), native AML on AKS, a VM
container, Azure Container Instances and Azure Container Apps. The last three
are portable model-serving tests, not AML-managed deployment acceptance.
The existing Arc cluster is not changed by this matrix.

### Primary: AML managed online

Real cloud checks passed on private endpoint `amlarclab-managed-1123`:

- Registered model 1 / blue and model 2 / green each returned 100 REST
  predictions identical to their local registered-model references
  (maximum absolute error 0, tolerances rtol/atol 1e-5).
- Traffic changed blue 100% -> green 100% -> blue 100%; directed and routed
  REST responses were checked at each applicable stage. This proves actual
  model-version transition and rollback, not just ARM traffic configuration.
- Primary-key rotation was verified by real new-key scoring, stale-primary
  HTTP401, unchanged-secondary scoring and three successful secondary probes.
  Observed data-plane propagation was 10.350 seconds. The initial SDK async
  polling URL returned 404; the verified test uses the documented 2024-10-01
  regeneration API and actual bounded key/authentication readback.
- Green startup logs prove the model was loaded from the AML mount, with file
  hashes matching the registered-model build manifest, and both actual PyPI
  and pythonhosted probes blocked. The immutable image installs dependencies
  at build time, not startup. Inbound public access and deployment public egress
  were Disabled; existing private storage/firewall guardrails were not relaxed.
- A deliberately invalid feature request produced HTTP424 / model HTTP400,
  appeared in actual traffic logs with its exact client request ID, and
  produced a matching Sev2 Fired alert at 20:25:05 UTC. The request event was
  20:22:19 UTC. Valid scoring immediately afterward still matched the reference.
  Telemetry/controlled-failure alerting is proven; this is not drift monitoring,
  production alert-policy design or external notification delivery.
- A subsequent comparison used the actual 100%-traffic blue REST champion
  across all 9,489 rows of the registered data2 campaign-grouped holdout.
  Candidate model2 MAE was 0.4167589735 versus the live champion's
  0.4229801117. The unchanged policy returned ELIGIBLE; candidate slice MAEs
  were 0.4202226723/0.4122043658. Actual data bytes matched the registered
  `71ec5e60...` snapshot hash. Endpoint traffic/model identity were checked
  before and after the comparison.

Serving image source was committed separately from model-training source f563:
blue image source 9df04bce5fe6ad3eee2eaf78b2493da53ded3429;
green image source 0cfa2c0eab0c716d8ca5922294abdbbf2b187f3b.
Both images and the shared Python base were pinned by digest. Custom portable
serving deliberately replaces MLflow's runtime dependency-installing no-code
container; the registered models and quality policy were not changed.

Execution used P-DS from a new disposable private VM, orchestrated by the
authorized operator. This is **not GitHub model-release acceptance**, fresh-code
training upload from a hosted runner, independent approval or Arc acceptance.
The temporary build identity's measured artifact-container and image-push
permissions were revoked after use. The linked inference-UAMI assignment
permission and registry private-link SKU prerequisite are explicitly audited.
The managed endpoint (including both deployments) and temporary inference alert
were deleted and independently read back HTTP404 before AKS was created.
Registry private connections were independently empty, then the original Basic
SKU/public-enabled/admin-disabled baseline was restored and read back.

### Native AML on AKS: REST passed

A disposable private AKS 1.35.9 cluster used one Standard_D4s_v5 node, the Free
control-plane tier and an isolated subnet with the existing NAT gateway. Its
node was Ready with a private address and no external IP. Local accounts remain
enabled as required by the documented AML extension prerequisite; this is not
a production AKS-hardening acceptance.

The current AML extension **1.1.115 installed successfully** without identity
overrides, downgrades, pod patches or Arc attachment. Actual identity/inference
controller pods were Running, the inference router was private NodePort, and
the existing `lab-cpu` InstanceType was installed. AML Kubernetes compute
`aks-smoke` attached successfully using the existing read-only inference UAMI
and a separate inference namespace.

Endpoint `amlarclab-aks-1123`, deployment blue, used registered synthetic model
2 and the same immutable custom serving environment as the managed green.
From the separate private worker, P-DS retrieved endpoint metadata/keys and
issued an actual directed REST request through the AML router: **HTTP200,
100 finite predictions, max absolute error 0**, rtol/atol 0.00001 against the
original registered-model build reference.

This proves native AML-on-AKS deployment and real REST scoring, not just image
portability. Infrastructure, attachment and deployment used the authorized
bootstrap operator; restricted-persona deployment is not implicitly passed.
HTTP was confined to VNet-only NodePort for this disposable lab: production TLS,
AKS promotion/rollback and GitHub release automation are not tested.
The endpoint and compute attachment were deleted/detached and read back absent.
The cluster, generated node RG, owned control identity, exact subnet network
role and isolated subnet were all verified absent before the next VM target
was started. The temporary P-DS inference-UAMI Operator assignment was deleted
and read back HTTP404; its exact original two role/scope pairs were independently
verified restored. The actual retail Linux node rate recorded was
EUR0.1831/hour; that is not a measured invoice.

### Private VM container: REST passed

A separate disposable Standard_D2s_v3 Ubuntu VM was created in an isolated
subnet, with a private address and no public-IP association. Its existing
read-only inference UAMI successfully obtained an ACR login and pulled the
same immutable green image, digest
`69de0659299816d9ede8ad3a38a44982509ae71701932ac6f18687f3e5a0e40a`.
Docker 29.1.3 started its nonroot model2 service; registry login was removed
after the pull.

The separate worker, not VM loopback, issued real health and scoring requests.
Health reported bundled model2 and the exact seven-file registered-model
manifest `f9f53c9635e7527c74443e6818ef61b5f370379a0a27344b6f44f372150bc5b0`.
The actual REST result was **HTTP200, 100 finite predictions, max absolute
error 0**, rtol/atol 0.00001. Optional source/model labels remained
unknown/unspecified because they were not set on this portable container;
identity comes from the actual image pull digest and independent model hashes,
not those labels.

The initial standalone bootstrap's exit0 skipped the outer Run Command
completion marker despite successful image pull and actual loopback-ready
health. The private invocation was corrected to execute that script in a child
shell; the existing container was not recreated or falsely marked passed.
The separate successful REST/model-identity check supplied acceptance.

This is private HTTP portable serving, without server authentication, **not
AML-managed deployment, production transport/security or release acceptance**.
The VM, schedule, automatically deleted NIC/disk and isolated subnet were all
read back absent before ACI was started.

### Private Azure Container Instances: REST passed

A disposable private Linux container group used one CPU, 2 GB memory, its own
delegated subnet and the existing NAT gateway. The existing read-only inference
UAMI pulled the same immutable image; no registry password or new role grant was
needed. The separate worker obtained real health and scoring output from the
group's private address: the exact model2 seven-file manifest, **100 finite REST
predictions, max absolute error 0**, rtol/atol 0.00001.

The first subnet what-if hit a local Azure authentication network timeout
before creating resources. One identical retry succeeded without login,
broker/configuration changes or a network-policy workaround. That is not a
failed ACI inference acceptance. The container group and delegated subnet were
subsequently deleted and read back absent before Container Apps was started.
This is unauthenticated private HTTP portable serving, not AML management or
production security/release acceptance.

### Internal Azure Container Apps: HTTPS REST passed

A disposable internal VNet environment used the Consumption workload profile
and a single app replica requesting one CPU and 2 GiB. The same existing
read-only inference UAMI pulled the same immutable image. Actual environment
readback confirmed internal=true, the isolated delegated subnet, a private
static address and the generated infrastructure resource group.

The separate worker contacted the app's actual HTTPS hostname using curl's
private-address `--resolve` option, preserving SNI and certificate/hostname
verification without a permanent DNS-zone change. Both initial and final
committed-checker runs returned the exact bundled model2 manifest and **100
finite predictions, max absolute error 0**, rtol/atol 0.00001. The final checker
also disables implicit curl configuration, so a client's default insecure or
redirect options cannot silently alter this test.

The app's external ingress means reachable outside the app/environment within
the VNet, not public Internet ingress: the environment itself is internal.
This is private HTTPS portable serving without app authentication, not AML
deployment management, production authorization or release-workflow acceptance.
The app and generated infrastructure resource group returned GET404 first. The
environment record remained ScheduledForDelete after the first bounded 20-minute cleanup
wait; a second exact DELETE returned 202 with its operation still pending.
Actual subnet readback showed no service-association links or IP configurations,
so only the empty owned ACA subnet was deleted and GET404 verified. The shared
original VNet was preserved; advice to delete an entire associated VNet was not
followed. The subsequent bounded follow-up also observed **GET404 for the
environment itself** and reverified app/generated RG/subnet absence. ACA
cleanup is now complete, including the delayed control-plane record.

### Matrix boundaries and retained replay assets

All five selected targets passed their specified real-serving tests. Only the
private managed-online primary received the full serving lifecycle; native AKS
received AML attachment/deployment/REST tests; VM/ACI/ACA received portable REST
tests. None substitutes for the still-blocked original Arc path or deferred
Fabric integration, fresh-checkout hosted-runner training packaging, GitHub
model release, independent approval, drift monitoring or external notification
delivery.

The two versioned serving environments and their immutable registry images are
retained for replay, not as active compute. The restored Basic registry reports
2,128,945,783 bytes used, below its 10,737,418,240-byte included storage allowance;
there is no new registry SKU or storage-overage provision for those artifacts.
The original registered training models/data/environments are unchanged.
Exact original request/reference fixture bytes were exported privately and all
four SHA256 hashes independently verified before private-worker removal.

The private worker, its shutdown schedule, NIC and OS disk are all GET404.
Original VM readback is deallocated and its original enabled 1900 shutdown
schedule is preserved. Independent final role queries match the original two
P-DS role/scope pairs and original two read-only inference-UAMI pairs. Registry
readback is Basic/publicEnabled/adminDisabled with no private connections;
storage remains publicDisabled/sharedKeyDisabled/defaultDeny with its approved
private connections.

For scale, a deliberately rounded-up compute estimate using observed provision
windows and public Sweden Central EUR rates is about EUR0.89: four worker
D2s_v3 hours, one smoke-VM D2s_v3 hour, two managed DS2_v2 deployment-hours and
one AKS D4s_v5 hour. This excludes short ACI/ACA usage, disks, temporary registry
Premium/private-link charges, logs and networking. It is neither a measured
invoice nor proof of the total EUR30 working ceiling; no hard billing cap was
promised. No disposable serving compute remains running.

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
