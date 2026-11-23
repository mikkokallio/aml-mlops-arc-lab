"""Deliberately fail an AML command job; never promote or register a model.

Run at the root of the registered f563c2f code asset with campaign-training:2.
This module also supports base64/compile/exec bootstrapping without ``__file__``.
Use a fresh output directory per invocation. Both cases must exit nonzero;
neither is a successful production pipeline execution.
The unchanged evaluator's MLflow run is FINISHED before its quality gate raises;
the original gate exception must fail the enclosing AML command job.
"""

import argparse
import json
from pathlib import Path
import re

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow.models import infer_signature
from sklearn.dummy import DummyRegressor

from scripts.pipeline import steps
from src.train import regression_metrics, selected_features, split_campaigns


COMPONENT_SOURCE_SHA = "f563c2fca1d62a6f9a4d209ca5be44d70b65de83"
CONTRACT = Path("config/features.yaml")
POLICY = Path("config/components/promotion-policy.yml")
MODEL_REQUIREMENTS = [
    "mlflow==2.22.2", "numpy==1.26.4", "pandas==2.2.3", "scikit-learn==1.6.1",
]


def git_sha(value: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise argparse.ArgumentTypeError("An exact lowercase 40-character fixture commit SHA is required.")
    return value


def quality_failure(data: Path, output: Path, data_version: str, identity: dict) -> None:
    snapshot = output / "snapshot"
    validated = output / "validated"
    training = output / "training"
    evaluation = output / "evaluation"
    steps.snapshot(data, snapshot, data_version)
    steps.validate(snapshot, validated, CONTRACT)
    features = selected_features(CONTRACT)
    train, holdout = split_campaigns(pd.read_csv(validated / "data.csv"))
    model = DummyRegressor(strategy="constant", constant=1000.0)
    model.fit(train[features], train["target"])
    example = holdout[features].head(3)
    signature = infer_signature(example, model.predict(example))
    training.mkdir()
    with mlflow.start_run() as run:
        mlflow.set_tags({**identity, "fixture_stage": "training"})
        mlflow.log_params({"strategy": "constant", "constant": 1000.0})
        metrics = regression_metrics(holdout, model.predict(holdout[features]))
        mlflow.log_metrics(metrics)
        info = mlflow.sklearn.log_model(
            model, artifact_path="model", signature=signature, input_example=example,
            pip_requirements=MODEL_REQUIREMENTS,
        )
        mlflow.sklearn.save_model(
            model, str(training / "model"), signature=signature,
            pip_requirements=MODEL_REQUIREMENTS,
        )
        reloaded = mlflow.pyfunc.load_model(info.model_uri)
        np.testing.assert_array_equal(reloaded.predict(example), model.predict(example))
        result = {
            **identity,
            "git_sha": COMPONENT_SOURCE_SHA,
            "run_id": run.info.run_id,
            "model_uri": info.model_uri,
            "framework": "sklearn-dummy-constant",
            "features": features,
            "metrics": metrics,
            "data_asset_version": data_version,
            "snapshot_sha256": steps.digest(validated / "data.csv"),
        }
        steps.write_json(training / "result.json", result)
        mlflow.log_artifact(str(training / "result.json"))
        mlflow.log_artifact(str(output / "fixture.json"))
    try:
        steps.evaluate(validated, training, evaluation, CONTRACT, POLICY, "none", "none")
    except RuntimeError as error:
        if not str(error).startswith("QUALITY_GATE_FAILED"):
            raise
        # AML cannot change a completed run to FAILED. Add provenance without
        # reopening it, and never let metadata failures mask the original gate.
        evaluation_run = mlflow.last_active_run()
        if evaluation_run is None:
            raise
        try:
            client = mlflow.tracking.MlflowClient()
            for key, value in {**identity, "fixture_stage": "evaluation"}.items():
                client.set_tag(evaluation_run.info.run_id, key, value)
            client.log_artifact(evaluation_run.info.run_id, str(output / "fixture.json"))
            decision = steps.read_json(evaluation / "decision.json")
            print(json.dumps(steps.read_json(training / "result.json"), allow_nan=False), flush=True)
            print(json.dumps(decision, allow_nan=False), flush=True)
        except Exception as metadata_error:
            print(f"FIXTURE_PROVENANCE_WARNING: {type(metadata_error).__name__}", flush=True)
        raise
    raise RuntimeError("FIXTURE_EXPECTATION_FAILED: unchanged quality gate did not fail.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("execution", "quality"), required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--fixture-git-sha", type=git_sha, required=True)
    parser.add_argument("--data-version", type=steps.versioned_asset,
                        default="azureml:campaign-synthetic:2")
    parser.add_argument("--output", type=Path, default=Path("outputs/failure-fixture"))
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=False)
    identity = {
        "purpose": "controlled-negative-test",
        "fixture_case": args.case,
        "component_source_sha": COMPONENT_SOURCE_SHA,
        "fixture_git_sha": args.fixture_git_sha,
        "data_asset_version": args.data_version,
        "policy_sha256": steps.digest(POLICY),
        "feature_contract_sha256": steps.digest(CONTRACT),
    }
    steps.write_json(args.output / "fixture.json", identity)
    if args.case == "execution":
        with mlflow.start_run():
            mlflow.set_tags({**identity, "fixture_stage": "execution"})
            mlflow.log_artifact(str(args.output / "fixture.json"))
            raise RuntimeError("CONTROLLED_EXECUTION_FAILURE")
    quality_failure(args.data, args.output, args.data_version, identity)


if __name__ == "__main__":
    main()
