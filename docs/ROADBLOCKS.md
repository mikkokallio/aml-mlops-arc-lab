# Permission and roadblock register

Every elevated action must record the specific permission and resource scope.
Do not grant broad privileges merely to suppress a diagnostic failure.

| Date | Persona | Step | Command or script | Result/error | Permission or setting needed | Scope | Applied by | Repeating role | Expected/surprise |
|---|---|---|---|---|---|---|---|---|---|

| 2026-11-23 | Bootstrap Owner | Register providers | scripts/admin/Initialize-Lab.ps1 | Four providers initially NotRegistered; now all Registered | Microsoft.Resources/subscriptions/providers/register/action | Subscription | Assistant, authorized | One-time platform admin | Expected |
| 2026-11-23 | Bootstrap Owner | Isolated scaffolding | scripts/Deploy-Group.ps1 | ID, ML and edge deployments succeeded after what-if | Resource-group creation; deployments/write and each template resource write | Four new RGs only | Assistant, authorized | Contributor for resources; role administration separate | Expected |
| 2026-11-23 | Bootstrap Owner | Restricted personas | scripts/admin/Grant-LabRole.ps1 | RGC: Contributor on ML RG; DS/CI: AzureML Data Scientist on workspace; onboarding: Arc Onboarding on edge RG | Microsoft.Authorization/roleAssignments/write | Exact RG/workspace scopes, private command log | Assistant, authorized | Owner or RBAC Administrator at those scopes | Expected |
| 2026-11-23 | VM bootstrap | No-egress test | cloud-init serial log | ARM, PyPI, MCR all UNREACHABLE; VM has private IP and no public IP | Explicit outbound path required; adding NAT to dedicated subnet | Edge subnet only | Assistant, authorized | Network Contributor | Expected, measured |

Private command/output log: `.local/admin-actions.jsonl`. Bootstrap provisioning
was performed by the authorized Owner, not represented as a successful
restricted-persona drill. Actual restricted operations are recorded separately.

Private-connectivity provisioning also crosses resource-group scopes: private
endpoints, their DNS zone groups, private DNS zones and VNet links are in the ML
RG, while the referenced subnet/VNet are in the edge RG. Repeating this requires
the corresponding Network resource writes, subnet/VNet join permissions at the
referenced network, and target storage/Key Vault private-link approval rights.
Contributor on the ML RG alone is not evidence that these cross-scope operations
are permitted. This deployment was performed by Owner; a restricted-persona
private-network provisioning drill has NOT RUN.

The AML size/quota CLI probes attempted a dynamic upgrade of the user's shared
AML extension. Those two task-owned processes were stopped. VM capacity is
proved by the successful Standard_D4s_v5 deployment, not those incomplete probes.

## Measured implementation roadblocks

Additional authorized operations, with exact commands/scopes retained in the
private action log:

- Managed command job: training-compute SystemAssigned identity had no storage
  data role and the job failed mounting writable output before user code.
  Owner granted Storage Blob Data Contributor on the exact workspaceblobstore
  container, not the account and not the read-only inference identity. Granting
  requires roleAssignments/write there (Owner/RBAC Administrator); ordinary
  Contributor is insufficient. Retry entered user code, verifying mount
  resolution, then failed on missing mlflow. Environment v1 readback has null
  conda_file: the SDK omitted post-construction assignment. Fix is constructor
  input and immutable v2 registration/readback, not another storage grant.
  Both are now verified: the real retry completed and registered model version
  2. A serialization regression test covers the missing Conda specification.
- P-DS source upload for the actual pipeline separately returned storage 403.
  Owner granted Storage Blob Data Contributor only at the workspaceblobstore
  container. This is an additional data-plane permission beyond workspace
  AzureML Data Scientist, not evidence that AML-RG Contributor suffices.
  Eligible and rejected cloud pipelines subsequently completed. Neither this
  grant nor the training-compute grant widened the inference identity.
- GitHub OIDC bootstrap: two federated credentials on the P-CI UAMI require
  userAssignedIdentities/federatedIdentityCredentials/write at that identity,
  for example Managed Identity Contributor. Managed Identity Operator alone
  does not grant that write. Repository Actions-secret creation separately
  requires GitHub repository permission, not Azure Owner. Credentials/secrets
  are configured and read back. Initial AADSTS700213 was traced through
  boolean-only assertion comparisons to GitHub's enabled immutable-subject
  policy. Its actual subject includes structured owner/repository IDs.
  The two existing credentials' subjects were replaced, preserving issuer,
  audience and train/prod boundaries, with no additional credential or role.
  Actual run 45212597530 passed both P-CI Azure logins and workspace reads.
  Production WAITING was observed before operator self-approval. This is not
  independent review or a model-deployment acceptance.
- Main ruleset creation requires GitHub repository Administration:write, not
  Azure Owner or AML Contributor. It requires PRs and the named GitHub Actions
  check with no bypass actors. Actual administrator direct-push and failed-check
  merge attempts were rejected. Zero required PR reviews is documented because
  this lab has one person; independent review is not claimed.
- Azure-only training monitoring adds a separate diagnostic setting on the lab
  AML workspace and a scheduled-query rule in the same ML RG, targeting only
  the owned Log Analytics workspace. Deployment requires
  Microsoft.Insights/diagnosticSettings/write on the AML workspace,
  Microsoft.Insights/scheduledQueryRules/write and deployment permissions in
  the ML RG, plus access to the destination workspace. Query/alert readback
  requires Log Analytics query access and Microsoft.AlertsManagement/alerts/read.
  These are not Owner-only role-assignment operations. Actual execution used
  the authorized Owner, not a restricted monitoring-persona drill; no new
  role grants were made. Existing governance diagnostics and their external
  workspace were neither changed nor queried.
- Private negative-test artifact verification used existing P-DS access from
  the lab VM, temporarily starting it and restoring deallocated state without
  changing its shutdown schedule. The operator's VM read/start, runCommand/action
  and deallocate/action permissions are needed at that edge VM; Contributor
  on the ML RG alone does not cover it. These power/readback actions are
  individually recorded in the private action log.
- The initial quality fixture tried to change an already FINISHED evaluation
  run to FAILED. Unlike the local MLflow file store, AML rejects multiple
  terminal states; its BAD_REQUEST masked the original QUALITY_GATE_FAILED.
  The corrected fixture preserves the original exception without reopening the
  completed run; a real rerun verified the final QUALITY_GATE_FAILED and Fired
  alert. An immutable-terminal regression covers the masking bug.
  The unchanged f563 evaluator finishes metrics evaluation
  before raising the quality decision: FINISHED evaluation metadata and a
  Failed enclosing AML command are distinct, valid outcomes.
- Disposable managed serving: the private image-builder's actual registered
  model download returned AuthorizationPermissionMismatch. P-DS's existing
  workspaceblobstore grant did not cover workspaceartifactstore (container
  azureml). A temporary Storage Blob Data Reader grant on that exact container
  resolved the read after propagation; direct keyless/private Blob access was
  independently verified. Temporary AcrPush on only the lab registry permitted
  publishing immutable images. Both assignments were deleted after use and
  P-DS's original two assignments independently read back.
- Managed serving's documented per-deployment secure egress needs private link
  to the workspace-associated ACR. Its Basic SKU was temporarily upgraded to
  Premium; public-access and admin-authentication settings were not relaxed.
  The original SKU is recorded for restoration after temporary private links
  are removed. This legacy per-deployment approach avoids changing the working
  workspace's network-isolation architecture for a disposable test.
- Actual P-DS traffic update passed onlineEndpoints/write but failed linked
  userAssignedIdentities/assign/action. A temporary Managed Identity Operator
  grant covers only the existing read-only inference UAMI, not its RG; the
  inference identity's own data roles were not widened. Owner/RBAC
  administration is required to grant it. AML-RG Contributor alone is
  insufficient for this cross-RG linked identity assignment.
- SDK key-regeneration async polling returned 404. The documented 2024-10-01
  REST operation plus bounded actual key readback and real scoring verifies the
  requirement without upgrading shared tools or treating HTTP202 as success.
  A subsequent actual probe exposed data-plane propagation: new-key scoring
  initially returned 401 after ARM key readback changed. The verified test waits
  for new-key success and stale-key 401, checking unchanged-secondary scoring
  while waiting; observed convergence was 10.350 seconds, not an SLA.
- Native AKS control experiment: the same current AML extension 1.1.115
  installed successfully on private managed-identity AKS 1.35.9. AML compute
  attachment, registered-model deployment and actual private 100-row REST
  scoring passed with zero reference error. No identity overrides, extension
  downgrades or pod patches were needed. This narrows the original blocker to
  the measured Arc path; it does not establish its product root cause.
- The installed `az aks command invoke` prints its command-start/finish line and
  logs as text even with the default JSON output option. The first parent
  JSON parse failed after an actual exitcode=0 node/namespace command. Checking
  the actual command exit-code line avoids misreporting successful cluster work
  as a cloud failure.

| Persona / component | Actual finding | Minimum action and scope | Status |
|---|---|---|---|
| VM bootstrap | Node object did not exist immediately after k3s service start | Wait for node creation before waiting for Ready | Fixed; node Ready, pinned version verified |
| P-RGC extension install | AuthorizationFailed: connectedClusters/read in edge RG | Owner performs one-time extension/Relay setup; no Contributor over edge RG granted to P-RGC | Denial recorded; extension setup has a separate runtime failure below |
| P-RGC compute attach | LinkedAuthorizationFailed: connectedClusters/write | Arc Onboarding role on this exact cluster only | Granted by Owner, logged |
| P-RGC compute attach, retry | LinkedAuthorizationFailed: userAssignedIdentities/assign/action | Managed Identity Operator on compute UAMI only, not ID RG | Granted by Owner, logged |
| Compute identity | Documented image/model access prerequisites | AcrPull on lab ACR; Storage Blob Data Reader on lab storage | Granted by Owner, logged; inference access NOT YET VERIFIED |
| InstanceType admission | CRD rejected CPU string 0.5 | Equivalent standard Kubernetes quantity 500m | Applied successfully |
| MLflow adapter | azureml-mlflow 1.61.0 calls a newer ArtifactRepository constructor than mlflow 2.22.2 provides | Inspected 1.60.0 wheel constructor; pin adapter 1.60.0 | Installed; pip check passes |
| YAML loading | Deployment defaults to managed without type; endpoint rejects type | Deployment type=kubernetes; endpoint selected through compute field | SDK loads both as Kubernetes entities |
| AML extension 1.1.115 and 1.1.109 | Identity controller/proxy/gateway fail: Unknown cluster type Unknown | ARM identity is SystemAssigned, but Helm configuration has UserAssigned in both identity fields; neither legacy nor canonical global setting resolves it | Both versions and the final canonical-setting update timed out; NOT PASSED |
| MLflow metrics | Workspace storage authentication failure; resource logs show OAuth 403 AuthorizationFailure on CreateContainer/GetBlob by workspace identity | Public access remains Disabled; default Deny; resource-instance exception for this workspace only, with existing identity RBAC | Minimal metric operation and full P-DS training/artifact logging/model registration PASSED |
| Local caller datastore access | Direct OAuth container access failed | Storage Blob Data Contributor for current lab operator on lab storage only | Granted by Owner, logged; did not resolve backend metric failure |

### Storage networking discrepancy

The template requested public network access, matching the approved lab network
design. Actual ARM state reports `publicNetworkAccess=Disabled`. No applicable
policy assignment was returned by the resource-scope inherited-assignment query.
This is **not** evidence that no other guardrail exists.

An explicit CLI update and direct ARM PATCH were tested. Debug evidence confirms
the request contained `publicNetworkAccess=Enabled`, but the HTTP 200 response
still reported Disabled. A second supported API version behaved the same way.
The operator then confirmed tenant guardrails automatically revert unsafe
settings. No further public-enablement attempt was made after that confirmation.
The initial public-service shortcut was not viable in this tenant.

Shared-key enablement alone, a default-datastore auth-mode change, caller Blob
Data Contributor, and workspace credential synchronization did not fix metric
logging. The observed failed storage requests used OAuth, not an account key.
The final template removes both credential-mode experiment switches, restores
identity-based system datastores, and keeps shared keys and public access disabled.
Exact state verification confirmed default Deny and exactly one resource-instance
exception: this AML workspace. Key Vault is also private/default-Deny with the
documented trusted-services bypass required for AML service-side secret access.

Blob, File and Key Vault private endpoints and private DNS links were deployed
successfully into the existing lab VNet, after what-if. These are additional
resources made necessary by the measured tenant restriction, under the operator's
authorization for necessary additions. No policy exemption or policy change was
requested. The local laptop does not gain access to private storage; model
training is invoked from VS Code through Run Command under P-DS inside the VNet.

The official storage firewall documentation states that trusted resource-instance
exceptions remain effective with public network access Disabled. This allows
only the authenticated workspace service-side access, not general public clients.
See [storage firewall limitations](https://learn.microsoft.com/en-us/azure/storage/common/storage-network-security-limitations)
and [secure AML dependencies](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-secure-workspace-vnet).

### Extension version recovery experiment

The cluster's stable version-discovery API explicitly offered 1.1.115 and
1.1.109, not a guessed 1.1.114. Actual 1.1.109 containers reproduce the same
Unknown cluster-type crash; that update also timed out.
Automatic upgrades were temporarily disabled for the comparison, then restored:
ARM confirms autoUpgradeMode compatible and autoUpgradeMinorVersion true.
No Relay resource is deleted or modified by a janitor.

Selective Helm inspection shows chart defaults specify SystemAssigned, while
the release configuration specifies UserAssigned for both `Azure.Identity.Type`
and `global.azure.identity.type`. The legacy helper maps SystemAssigned to ARC,
AKSCreated to AKS, and other values to Unknown. This explains the rejected
rendered cluster type, but does not yet identify a supported producer-side fix.
Do not treat another version guess or a manual managed-pod patch as resolution.

A final configuration check supplies `global.azure.identity.type=SystemAssigned`
through the extension API, matching actual ARM identity rather than inventing a
cluster identity. ARM accepted the global setting and the automatic-upgrade
restoration; that update ultimately timed out too. Acceptance requires checking the rendered
configuration and real readiness, not just request acceptance.

The new install's Helm timestamp is after the canonical-setting request. Its
chart is 1.1.109; both rendered identity fields are still UserAssigned. Fresh
gateway/proxy logs reproduce the same Unknown cluster-type failure.
Thus neither spelling changes the actual rendered configuration. No additional
RBAC grant was made for this crash; no permission denial explains these logs.
An automatic-upgrade policy does not prove that the installed release immediately
returned to 1.1.115.

### Extension escalation evidence

Expected: the extension with ARM identity SystemAssigned renders the ARC cluster
type and its identity components become ready.

Observed: the chart's legacy selector receives UserAssigned, maps it to Unknown,
and the token-provider constructor rejects Unknown before normal operation.
The installed agent/chart integration's supported correction is unresolved.
This is not yet a vendor-confirmed defect, and no alternate target counts as
an Arc pass.

Reproducer in this lab:

1. Connect the pinned k3s cluster to Arc and verify Connected.
2. Run the inference-only extension installer; record version and failure.
3. Use the logged extension-update script to supply
   `Azure.Identity.Type=SystemAssigned`; verify ARM retention and rendered values.
4. Repeat with `global.azure.identity.type=SystemAssigned`. The
   `inspect-identity-values.sh` script prints only selected nonsecret identity
   fields and release metadata; `diagnose-extension.sh` captures component errors.
5. Compare the post-request Helm timestamp and image versions, not an earlier
   release. Do not dump the full Helm secret or protected Relay settings.

Ignored local evidence includes `canonical-identity-render-version.json`,
`canonical-identity-component-logs.json`, `extension-escalation-activity.json`,
and `admin-actions.jsonl` under `.local`. Correlation IDs and raw account/resource
identities are retained privately, not copied into a public issue.

### Successful private training boundary

The P-DS workspace-scoped AzureML Data Scientist identity successfully trained,
logged metrics/artifacts, and registered `campaign-xgboost:1` through the private
client path. No additional storage role was required for that DS operation.
Author-performed execution is provisional persona evidence, not an independent
ownership drill. Endpoint access, serving image compatibility, and the proposed
secret-scoped Key Vault roles remain untested.

### Independent managed-training path

Arc is not a dependency for AML command jobs. The regional quota API confirms
available dedicated CPU quota. Creating a no-public-IP AML compute initially
failed with `Provided EnableNodePublicIp 'False' requires workspace private endpoint`.
A workspace private endpoint and its API/notebook private DNS zones were added
to the existing lab VNet; public-access restrictions on storage/Key Vault were
not relaxed. This additional endpoint adds recurring cost.

The retry provisioned `cpu-training`: SystemAssigned identity, no node public IP,
minimum zero nodes, maximum one, two-minute idle scale-down. Workspace image
builds use that private cluster. A training environment was registered using an
immutable MCR image digest and the shared pinned dependency manifest.

The existing workspace-scoped P-DS identity successfully submitted a genuine AML
command job from inside the VNet. Only committed training source was archived;
the real source SHA is injected as metadata. Submission returned Starting.
The first execution exposed the distinct output-mount and environment defects
described above. After their scoped corrections, command
`musing_branch_g8hmb817q6` completed and registered `campaign-xgboost:2`.
Two actual five-component synthetic pipelines also completed: an eligible
registration and a controlled NOT_REGISTERED case without an extra version.
Both used committed f563c2f source, environment 2 and data version 1. Their
comparison fixture is not a deployed champion and their input is not Fabric.
A subsequent actual data-version-2 run reused registered components without
source/data upload, improved MAE by 1.4708% against the registered-v1 fixture
on the same new holdout, and registered model version 2. No additional grant
was required. This reference-only control-plane submission is distinct from
uploading source to private storage from a public GitHub-hosted runner;
Actual GitHub run 45230564606 subsequently proved that reference-only path
under P-CI: the managed pipeline and all five children completed with the
existing workspace role and training runtime identity. No P-CI Blob write,
public storage access, additional grant or VM start was needed. Current-checkout
source packaging and private artifact/log access from the hosted runner remain
separate, unproven capabilities.
Managed compute is separate from the edge VM shutdown schedule.

Local environment registration initially hit AzureCliCredential's ten-second
subprocess timeout. Raising its explicit process timeout to sixty seconds fixed
the observed Windows CLI-startup failure; this was not an Azure permission denial.

### Fabric prerequisite: tenant-admin action required

Independent live probes succeeded against ARM: zero Fabric capacities in the
lab subscription, and F2 advertised in all three planned regions without listed
restrictions. This does not establish tenant-wide capacity absence.

Both operator and P-CI Fabric API token requests failed with:

```text
AADSTS500014: The service principal for resource
'https://api.fabric.microsoft.com' is disabled.
```

Entra administration must investigate the resource enterprise application's
disabled status and subscription validity, restoring access only if policy
permits. Subscription Owner does not by itself provide that tenant authority.
This error is not evidence of a Fabric service-principal allowlist problem;
Fabric API admission/workspace permissions remain unverified behind it.
No tenant settings, role grants, capacity purchases, existing-resource reuse,
or business data access were performed for these probes.

Subsequent user-assisted Edge/Entra inspection verified the resource application's
identity through its Fabric API identifiers: Power BI Service, activation
Deactivated, Enabled for users to sign-in No. The user explicitly approved
enabling this one tenant-wide application. Its current Yes/No controls are
disabled/read-only; no setting was changed. The portal states that editing
requires Global Administrator, Cloud Application Administrator or Application
Administrator. The specific reason this session is read-only was not verified;
do not infer a role grant or bypass a permission barrier.
The operator then explicitly deferred Fabric testing in this lab. Stop tenant
enablement/privilege requests; no capacity purchase or alternate-tenant
provisioning is authorized by that deferral. Issue 11 remains open as a deferred
prerequisite. Identity/token retests, API admission and actual ingestion must
eventually pass in a suitable environment; none is accepted here.

OneLake Storage token acquisition succeeded, but an account-level HEAD returned
405: reachability only, not a successful OneLake file-read permission test.
Raw evidence is in ignored `.local`; the probes are under `scripts/fabric`.

Raw evidence, resource identities, correlation IDs, and exact Owner role grants
remain in ignored `.local`; the public register deliberately omits identifiers.

## Authorization update

The operator authorized the assistant to execute required Owner commands on
23 November 2026. Continue to log those actions. This does not authorize unrelated
tenant administration, existing-resource reuse, or changes outside the lab.
