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
| AML extension 1.1.115 and 1.1.109 | Identity controller/proxy/gateway fail: Unknown cluster type Unknown | ARM identity is SystemAssigned, but Helm configuration has UserAssigned in both identity fields; neither legacy nor canonical global setting resolves it | Both versions timed out; new canonical-setting rollout reproduces the crash, control-plane update pending; NOT PASSED |
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
restoration; rollout is Updating. Acceptance requires checking the rendered
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

Raw evidence, resource identities, correlation IDs, and exact Owner role grants
remain in ignored `.local`; the public register deliberately omits identifiers.

## Authorization update

The operator authorized the assistant to execute required Owner commands on
23 November 2026. Continue to log those actions. This does not authorize unrelated
tenant administration, existing-resource reuse, or changes outside the lab.
