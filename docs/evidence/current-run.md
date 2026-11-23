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
  crash with Unknown cluster type. The control-plane update is still pending.
- Original storage failures were OAuth 403 responses. Operator confirmed tenant
  guardrail remediation. Public-access attempts stopped; a private/scoped-trust
  configuration resolved minimal metric logging.
- Compute attach has progressed past two specific permission denials, but is
  blocked by the extension not being Installed.

## Not run

AML inference deployment, endpoint scoring/reference comparison,
package-index-denied deployment,
release/rollback, Fabric, independent ownership drills and the remaining MLOps
milestones have **not** passed.

Training succeeded under the restricted P-DS identity inside the VNet, invoked
from VS Code via Run Command. This does not demonstrate the VS Code AML
GUI extension or an interactive remote-development experience.

Neither Arc Connected nor a local model/test substitutes for real AML scoring.
