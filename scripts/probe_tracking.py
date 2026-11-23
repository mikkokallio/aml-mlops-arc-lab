"""Reproduce the minimal workspace metric operation, without hiding failures."""

import mlflow

mlflow.set_experiment("arc-compatibility-probe")
with mlflow.start_run() as run:
    print("RUN_CREATED", run.info.run_id)
    mlflow.log_metric("storage_probe", 1)
print("METRIC_LOGGING_SUCCEEDED")
