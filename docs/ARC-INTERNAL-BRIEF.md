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
- AML Kubernetes extension installation is blocked. Therefore Kubernetes compute
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
