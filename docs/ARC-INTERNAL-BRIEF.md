# Microsoft-internal investigation request: AML extension identity mismatch

## Request

Please check internal known issues, compatibility records, rollout changes and
supported mitigations for the failure below. We need AML-managed model deployment
to Arc-enabled Kubernetes, not a manually served model or an AKS substitute.
No internal material needs to be copied into the public repository.

## Working boundary

- Private Ubuntu x86-64 Azure VM; k3s v1.35.9+k3s1, node Ready.
- Arc resource Succeeded/Connected; observed Arc agent version 1.39.3.
- Actual config-agent, extension-manager and clusterconnect-agent images are
  1.39.3; each deployment reports one ready replica.
- AML workspace training, MLflow metrics/artifacts and workspace model
  registration succeed through private storage/Key Vault connectivity.
- AML Arc Kubernetes extension installation is blocked. Therefore Arc compute
  attachment, AML model deployment and endpoint scoring have not succeeded.

## Extension and failure

- Type: Microsoft.AzureML.Kubernetes; cluster type: connectedClusters.
- Cluster scope; release namespace azureml.
- enableInference=True; enableTraining=False.
- inferenceRouterServiceType=nodePort; inferenceRouterHA=False.
- allowInsecureConnections=True for private lab HTTP only.
- Actual releases 1.1.115 and 1.1.109 both timed out during installation.
- Identity controller, identity proxy and gateway repeatedly crash:

```text
Unknown cluster type Unknown when creating the extension token provider
```

Proxy stack identifies `goms.io/azureml/amlarc/identity/pkg/tokenprovider.NewExtensionTokenProvider`
in `identity/pkg/tokenprovider/extension_token_provider.go:56`.

## Observed mismatch

| Location | Value |
|---|---|
| Extension ARM identity.type | SystemAssigned |
| Chart defaults Azure.Identity.Type | SystemAssigned |
| Helm release config Azure.Identity.Type | UserAssigned |
| Helm release config global.azure.identity.type | UserAssigned |

The chart's legacy `amlArcExtension.clusterType` helper maps SystemAssigned to
ARC, AKSCreated to AKS, and other values to Unknown. A separate clusterTypeV2
helper derives ConnectedClusters correctly from the cluster resource ID.

Both `Azure.Identity.Type=SystemAssigned` and
`global.azure.identity.type=SystemAssigned` were accepted and retained in ARM
configurationSettings. The fresh post-request 1.1.109 Helm install nevertheless
renders UserAssigned in both fields and reproduces the same constructor failure.
This is not merely inspection of an old release: Helm deployment timestamps and
actual image tags were checked.

Automatic-minor upgrades were temporarily disabled for the previous-release
comparison, then restored. ARM confirms autoUpgradeMode compatible and
autoUpgradeMinorVersion true. That restoration did not immediately replace the
observed 1.1.109 install. The final control-plane update subsequently timed out
with the same identity-controller/proxy/gateway crash-loop symptoms.

## Internal questions

Additional isolation result: Flux installed on the same original cluster,
returning ARM Succeeded and Helm deployed (chart/app 1.26.6). Its release
configuration also has UserAssigned in both identity fields, despite
SystemAssigned chart defaults. The value is therefore not unique to AML.
This does not identify its producer or demonstrate a Flux reconciliation
workload. Both clean different-minor and different-region AML installs have now
reproduced the failure; their disposable resources were cleaned up and verified.

All-namespace inspection now locates ExtensionConfig in each release namespace,
not azure-arc. Incoming AML `spec.parameter.IdentityType` is UserAssigned,
alongside the two diagnostic SystemAssigned settings. Incoming Flux also has
IdentityType UserAssigned. The value is therefore already present before Helm
rendering; the originating service/agent and supported correction remain open.

Stable and preview Arc resource API reads expose no OIDC/workload-identity
profile. We have not treated absence as an explicit disabled value or applied
a speculative identity change.

## Completed isolation matrix

| Target | k3s | Arc resource region | Arc agent | AML extension | Result |
|---|---|---|---|---|---|
| Original | 1.35.9+k3s1 | Sweden Central | 1.39.3 | 1.1.115 and 1.1.109 | Unknown cluster type; neither identity-setting spelling changes rendered UserAssigned |
| Clean A | 1.36.6+k3s1 | Sweden Central | 1.39.3 | 1.1.115 | Incoming UserAssigned; identity components crash-loop |
| Clean B | 1.35.9+k3s1 | North Europe | 1.39.3 | 1.1.115 | Same incoming value and constructor failure |

Both disposable VMs were in Sweden Central; B varies the Arc resource region,
not the VM region. A explicitly reported workload identity Disabled, while its
extension ARM identity was SystemAssigned. A's identity controller, proxy and
gateway each restarted six times; its ARM operation was still Creating when
the bounded test stopped. None of these are deployment/scoring passes.

Full healthcheck/component evidence was retained privately before cleanup.
The agreed practical experiments are exhausted. Do not prescribe another
unverified identity override, agent downgrade or managed-component patch.
The original target is retained for a supported mitigation and actual retest.

## Successful native AKS control

A subsequent disposable **native AKS 1.35.9** cluster in Sweden Central,
with a managed identity, private API and a single x86-64 node, successfully
installed the same current AML extension **1.1.115** using the same
inference-only private NodePort settings. Its actual identity controller,
identity proxy, gateway and inference-controller pods were Running.

AML Kubernetes compute attachment and deployment of registered synthetic model
2 with the immutable custom serving environment then succeeded. A separate
private client using P-DS performed actual directed REST scoring through the
AML router: HTTP200, 100 predictions, zero maximum absolute reference error,
rtol/atol 0.00001. No extension downgrade, identity override or pod patch was
used. Infrastructure/deployment used the authorized bootstrap operator; HTTP
was VNet-only lab transport, not production TLS acceptance.

This is a useful counterexample to a universal extension-version or AML-serving
failure, not an Arc fix or proof of the upstream producer's root cause.
Native AKS acceptance does not satisfy the original Arc target. Exact private
operation, runtime and REST evidence is retained alongside the Arc evidence.

## One consolidated support request

**Suggested title:** AML Arc extension rejects upstream UserAssigned identity
as Unknown cluster type across clean Kubernetes-minor and Arc-region cases.

**Expected:** Supported Arc inference-only installation starts its identity
components and permits AML Kubernetes compute attachment.

**Actual:** SystemAssigned ARM extension receives incoming
`spec.parameter.IdentityType=UserAssigned`; rendered legacy selector returns
Unknown and the token-provider constructor crashes. Flux receives the same
upstream identity value but installs successfully.

**Impact:** AML compute attachment, managed deployment and scoring are blocked.
Private managed AML training and synthetic cloud pipelines succeed independently.

**Private attachments available:** Original operation/correlation and selected
rendered-value evidence; A full health/component archive and outcome; B support
archive and outcome; version/region matrix and verified cleanup records.
The native AKS control's successful extension, attachment, deployment and real
REST comparison evidence is also available privately.
Raw evidence must use an approved private support channel, not this public repo.

**Requested resolution:** Identify the upstream identity producer and provide
one supported service-side/configuration/release correction, including exact
applicability and rollback guidance. Address the numbered questions below in
this same request rather than opening separate tickets for each experiment.

This is a prepared support brief, **not a submitted support case**, and the
failure is not yet a vendor-confirmed defect.

## Questions for that request

1. What producer supplies UserAssigned in this SystemAssigned extension case:
   extension RP, Arc agent/extension manager, or AML-specific configuration?
2. Is UserAssigned now an expected injected identity type? If so, which AML
   release handles it, and why is the legacy cluster-type selector still used?
3. Are Arc agent 1.39.3 and AML extension 1.1.115/1.1.109 a known incompatible
   combination? Are there region-specific rollout or service-side changes?
4. Is there a documented, supported configuration or hotfix? Please identify
   the exact supported mechanism, not a guessed version or a managed-pod patch.
5. Are there additional relevant k3s/Kubernetes support constraints for this
   combination? The observed failure is identity/cluster-type selection, not
   scheduling, image pull, or an observed Azure RBAC denial.

## Public research cross-check

Public documentation lists the AML extension for CNCF-certified, non-Arm64 Arc
clusters and documents the inference-only, NodePort, single-node settings used
here. AML's N-2 rule combined with the published AKS GA calendar places Kubernetes
1.35 within the minor-version window. That is not certification of this exact
k3s patch/Arc-agent/chart combination.

The public research pass found no matching known issue, documented mitigation,
or compatibility matrix for these exact Arc-agent/AML-extension versions.
Neither identity-setting spelling tested above is in AML's documented
configuration-key list: they were diagnostic experiments, not documented fixes.
The source of the injected UserAssigned value remains unconfirmed.

- [Arc extension availability](https://learn.microsoft.com/en-us/azure/azure-arc/kubernetes/extensions-release)
- [AML Kubernetes requirements/components](https://learn.microsoft.com/en-us/azure/machine-learning/reference-kubernetes)
- [AKS supported versions](https://learn.microsoft.com/en-us/azure/aks/supported-kubernetes-versions)
- [AML extension configuration](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-deploy-kubernetes-extension)
- [Supported AML extension diagnostics](https://learn.microsoft.com/en-us/azure/machine-learning/how-to-troubleshoot-kubernetes-extension)

## Evidence and safeguards

Selective nonsecret Helm inspection, fresh component logs, extension-operation
results, activity-log correlation IDs and exact elevated-action records are
retained locally. Private resource identifiers can be supplied through an
approved private channel; they are deliberately absent here.
The observed healthcheck pod phase is Succeeded; its retained report has
reports-pre-install and reports-pre-delete sections. Full healthcheck logs and
the report were saved privately on the VM, not pasted into this brief.

No full Helm secret, protected Relay credentials, policy exemption, manual
managed-component patch, or spoofed cluster identity has been used. Tenant
network guardrails remain respected. This is a reproducible installation
blocker, not yet a vendor-confirmed defect.
