# Version policy and observed versions

Date: 23 November 2026.

| Component | Selected/observed version | Policy/status |
|---|---|---|
| Local Azure CLI | 2.93.0 | Observed |
| Task-local AML CLI extension | 2.45.2 | Installed in ignored task-local extension directory |
| Local Bicep | 0.38.33 | Observed; ARM what-if also required where types are unavailable |
| Local training Python | 3.10.11 AMD64 | Observed; isolated venv, not the PATH ARM64 interpreter |
| Private-VM training Python | 3.12.3 x86-64 | Actual successful workspace training; serving environment compatibility NOT VERIFIED |
| K3s | v1.35.9+k3s1 | Installed; x86-64 node Ready |
| AKS GA minor releases observed | 1.37, 1.36, 1.35 | AML N-2 selection; older listed LTS releases not used |
| Python dependencies | Exact direct pins in requirements.txt | Installed; pip check and six focused tests pass |
| Azure MLflow adapter | 1.60.0 | 1.61.0 constructor incompatible with pinned MLflow 2.22.2 |
| Arc agents | 1.39.3 | Observed Connected; automatic upgrades |
| AML Kubernetes extension | 1.1.115 and 1.1.109 timed out | Canonical-setting install still renders UserAssigned and crashes on 1.1.109; auto-minor restored; update pending |

The local Python executable on PATH is ARM64. Training explicitly selects the
already installed AMD64 Python interpreter for xgboost wheel compatibility.

No installed version or local success is evidence of successful cluster serving.
