# Ownership evidence

Build times and verdicts are measured, never inferred from implementation.
Author-performed drills are PROVISIONAL.

| Component | Class | Owner | Skills | Measured build time | Day-2 work | Runbook | Drill | Verdict |
|---|---|---|---|---|---|---|---|---|
| Workspace MLflow training | CORE | DS | Python, MLflow, AML CLI | Not separately timed | Retrain, dependency updates | Training script exists; clean rerun drill pending | P-DS trained/logged/registered; author performed | PROVISIONAL; independent drill NOT RUN |
| k3s, Arc, AML extension and attach | CORE | EDGE | Linux, Kubernetes, Azure identities | NOT RUN | Patching, proxy, certificates | Pending | NOT RUN | Pending |
| Kubernetes online deployment/scoring | CORE | DS via workflow; EDGE for platform | MLflow, AML endpoints | NOT RUN | Release, rollback, key rotation | Pending | NOT RUN | Pending |
| Lab provisioning and scoring harness | L | Lab operator | Bicep, Azure CLI | In progress | Lab-only | Pending | NOT RUN | Not customer deliverable |

## Customer notification decision

Before customer setup, explicitly ask which notification channels, recipients
and response owners they prefer. This lab's Azure-only fired-alert test has no
external receiver and must not become an assumed customer default. Alert firing
and end-to-end notification delivery are separate acceptance checks.
