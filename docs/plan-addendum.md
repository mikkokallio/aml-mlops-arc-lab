# Approved implementation addendum

Date: 23 November 2026.

The original review documents remain unchanged and outside the public example.
This addendum records the execution decisions approved for the lab.

## Today's scope

- Required: prerequisite probes; a tracked synthetic regression model with an
  MLflow signature; AML-managed deployment to Arc-enabled k3s; scoring and
  comparison with the same model locally.
- Stretch: GitHub OIDC release approval, second version, traffic rollback,
  and Fabric permission/capacity probes.
- Remaining pipeline, Fabric, monitoring, managed endpoint, and ownership-drill
  work is NOT RUN unless the required path finishes early.
- Calendar estimates are not acceptance evidence.

## Authorization

- Four dedicated resource groups are approved: ML, edge, Fabric, and identities.
- One tracking issue covers M0, M1, M5 core and the release workflow.
- Execute Owner-level prerequisite actions when necessary. Log the command,
  reason, permission, scope, result, and role that must repeat it.
- Test whether additional resources are necessary before provisioning them.
  Additional necessary resources are authorized; remain within the plan unless
  it proves impossible. Record any pivot and its reason.
- Do not reuse existing resources without permission.

## Execution order

1. Personal GitHub authentication/repository, provider state, policy and quotas.
2. Deploy ML and edge dependencies with Bicep after what-if.
3. Bootstrap an explicitly pinned k3s release, then connect it to Arc.
4. Install the inference-only AML extension; one router replica, NodePort,
   no public scoring or SSH exposure.
5. Create workload namespace and attach the cluster as Kubernetes compute.
6. Prepare the tracked, registered model while infrastructure provisions.
7. Deploy that workspace model through an AML Kubernetes online endpoint.
8. Score using VM Run Command and compare the same records with MLflow locally.

## Invariants and refinements

- No public IP on the edge VM. Test explicit egress requirements; an outbound NAT
  public IP, if needed, is not a public IP on the VM.
- Select Kubernetes within the AML N-2 window aligned with AKS GA releases.
  Pin an exact K3s release, never an unspecified latest release.
- Inference extension: enableInference=True, enableTraining=False,
  inferenceRouterServiceType=nodePort, inferenceRouterHA=False.
  Lab HTTP remains restricted to the internal scoring path.
- Arc and AML extension minor auto-upgrades are deliberate policy. Record actual
  versions per acceptance run; distinguish these from pinned client dependencies.
- Namespace exists before compute attachment.
- Distinguish VM onboarding, workspace, compute, endpoint, and CI principals.
  Store CI identities outside resource groups controlled by the RG persona.
- Log failed restricted-persona attempts before applying the minimum Owner fix.
  Owner access is not evidence that the restricted persona can perform the step.
- Janitor may deallocate the dedicated VM but must not modify/delete the AML
  Arc compute's Azure Relay dependency.
- Runtime package-index egress restrictions need a separate deployment test;
  open-egress scoring does not prove plant-proxy compatibility.
- Champion and candidate must use the same campaign-grouped holdout and metric
  definitions. Do not compare historical MAE tags from different populations.
- Future gate output is one decision JSON with eligibility, reason, metrics,
  and evaluation data version. Invalid execution must fail, not pass as rejection.
- Replay is lab scaffolding. Persist record IDs, predictions and deployment/model
  identity; customer prediction persistence remains an integration question.
- Future quality breaches log metrics then fail with QUALITY_GATE_FAILED.
  Prove both execution-failure and quality-failure job notifications.
- One CI identity across train/prod separates approval, not Azure privileges.
- Lab approvals may be self-approvals; never claim independent review.
- Author-performed ownership drills are PROVISIONAL, not independent ownership
  verdicts.
- Single-node production serving is reasonable only when the consumer tolerates
  restart outages; otherwise it is a shortcut requiring an exit criterion.

## Evidence

Use PASS, FAIL, BLOCKED, or NOT RUN per check. Preserve actual measurements.
Keep account identifiers, raw management responses, secrets, and environment
details outside the public repository. Publish only sanitized results.
