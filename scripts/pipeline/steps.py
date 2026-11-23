"""M3 synthetic-source proof; this is not the unfinished Fabric/OneLake M2 path.

Run from the repository root with ``python -m scripts.pipeline.steps --help``.
The source input is an immutable AML uri_folder data asset containing data.csv.
For a local fixture, use ``generate --output <folder>`` then register that folder
as a versioned AML data asset before submitting config/pipeline-synthetic.yml.
The caller resolves the endpoint's 100%-traffic deployment to an exact
models:/name/version URI (or explicitly chooses baseline when no champion exists).
"""

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import yaml
from mlflow.tracking import MlflowClient

from src.train import (
    generate_campaigns,
    regression_metrics,
    selected_features,
    split_campaigns,
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def versioned_asset(value: str) -> str:
    if not re.fullmatch(r"azureml:[^/:]+:[^/:]+", value) and not re.fullmatch(
        r"azureml://[^ ]+/data/[^/]+/versions/[^/]+", value
    ):
        raise ValueError("An exact versioned AML data asset ID is required.")
    if value.rsplit(":", 1)[-1] == "latest" or value.endswith("/latest"):
        raise ValueError("Mutable latest references are forbidden.")
    return value


def snapshot(source: Path, output: Path, data_version: str) -> None:
    versioned_asset(data_version)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "data.csv", output / "data.csv")
    write_json(output / "manifest.json", {
        "data_asset_version": data_version,
        "source_kind": "synthetic-lab-generator",
        "sha256": digest(output / "data.csv"),
    })


def validate(source: Path, output: Path, contract: Path) -> None:
    features = selected_features(contract)
    manifest = read_json(source / "manifest.json")
    versioned_asset(manifest["data_asset_version"])
    if digest(source / "data.csv") != manifest["sha256"]:
        raise ValueError("Snapshot checksum mismatch.")
    data = pd.read_csv(source / "data.csv")
    required = list(dict.fromkeys(["campaign_id", "item_position", "target", *features]))
    if data.empty or not set(required).issubset(data.columns):
        raise ValueError("Missing required columns or empty data.")
    if not np.isfinite(data[required].to_numpy(dtype=float)).all():
        raise ValueError("Required data must be finite numeric values.")
    if data.duplicated(["campaign_id", "item_position"]).any():
        raise ValueError("Duplicate campaign/item record IDs.")
    definitions = yaml.safe_load(contract.read_text(encoding="utf-8"))["features"]
    for name in features:
        rule = definitions[name]
        if rule["type"] == "integer" and (data[name] % 1 != 0).any():
            raise ValueError(f"Noninteger feature: {name}")
        if "min" in rule and (data[name] < rule["min"]).any():
            raise ValueError(f"Feature below minimum: {name}")
        if "max" in rule and (data[name] > rule["max"]).any():
            raise ValueError(f"Feature above maximum: {name}")
    _, holdout = split_campaigns(data)
    regression_metrics(holdout, holdout["target"].to_numpy())
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "data.csv", output / "data.csv")
    shutil.copyfile(source / "manifest.json", output / "manifest.json")


def decide(metrics: dict, policy: dict, data_version: str, **identity) -> dict:
    versioned_asset(data_version)
    margin = float(policy["min_relative_improvement"])
    if not np.isfinite(margin) or not 0 <= margin < 1:
        raise ValueError("Invalid improvement margin.")
    for group in ("candidate", "reference"):
        if not metrics[group] or any(
            not np.isfinite(value) or value < 0 for value in metrics[group].values()
        ):
            raise ValueError("Invalid evaluation metrics.")
    breaches = []
    for name, limit in policy["quality_max"].items():
        if not np.isfinite(limit) or limit < 0:
            raise ValueError("Invalid quality threshold.")
        if metrics["candidate"][name] > limit:
            breaches.append(name)
    eligible = metrics["candidate"]["mae"] < metrics["reference"]["mae"] * (1 - margin)
    reason = "ELIGIBLE" if eligible else "PROMOTION_REJECTED"
    if breaches:
        eligible, reason = False, "QUALITY_GATE_FAILED: " + ", ".join(breaches)
    return {
        "eligible": eligible,
        "reason": reason,
        "metrics": metrics,
        "evaluation_data_version": data_version,
        **identity,
    }


def evaluate(data_path: Path, training: Path, output: Path, contract: Path,
             policy_path: Path, champion_uri: str, champion_deployment: str) -> dict:
    manifest = read_json(data_path / "manifest.json")
    if digest(data_path / "data.csv") != manifest["sha256"]:
        raise ValueError("Evaluation snapshot checksum mismatch.")
    result = read_json(training / "result.json")
    if result["data_asset_version"] != manifest["data_asset_version"]:
        raise ValueError("Training/evaluation data version mismatch.")
    features = selected_features(contract)
    if features != result["features"]:
        raise ValueError("Training/evaluation feature contract mismatch.")
    train, holdout = split_campaigns(pd.read_csv(data_path / "data.csv"))
    candidate = mlflow.pyfunc.load_model(str(training / "model"))
    candidate_metrics = regression_metrics(holdout, candidate.predict(holdout[features]))
    if champion_uri == "none":
        if champion_deployment != "none":
            raise ValueError("Deployment provided without a champion.")
        reference_predictions = np.full(len(holdout), train["target"].median())
        reference_kind = "training-target-median-baseline"
    else:
        if not re.fullmatch(r"models:/[^/]+/[0-9]+", champion_uri) or champion_deployment == "none":
            raise ValueError("Champion requires an exact model version and deployment identity.")
        champion = mlflow.pyfunc.load_model(champion_uri)
        reference_predictions = champion.predict(holdout[features])
        reference_kind = champion_uri
    metrics = {
        "candidate": candidate_metrics,
        "reference": regression_metrics(holdout, reference_predictions),
    }
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    decision = decide(
        metrics, policy, manifest["data_asset_version"],
        reference_model=reference_kind, champion_deployment=champion_deployment,
        candidate_model_uri=result["model_uri"], training_run_id=result["run_id"],
        git_sha=result["git_sha"], framework=result["framework"],
        snapshot_sha256=manifest["sha256"], policy_sha256=digest(policy_path),
        holdout_campaigns=sorted(holdout["campaign_id"].unique().tolist()),
    )
    with mlflow.start_run():
        mlflow.log_metrics({
            f"{group}_{name}": value
            for group, values in metrics.items() for name, value in values.items()
        })
        mlflow.set_tags({
            "evaluation_data_version": manifest["data_asset_version"],
            "reference_model": reference_kind,
            "promotion_reason": decision["reason"],
            "source_kind": manifest["source_kind"],
        })
        write_json(output / "decision.json", decision)
        mlflow.log_artifact(str(output / "decision.json"))
    if decision["reason"].startswith("QUALITY_GATE_FAILED"):
        raise RuntimeError(decision["reason"])
    return decision


def register(decision_path: Path, training: Path, output: Path, model_name: str) -> dict:
    decision = read_json(decision_path / "decision.json")
    if type(decision["eligible"]) is not bool:
        raise ValueError("Decision eligibility must be a boolean.")
    versioned_asset(decision["evaluation_data_version"])
    trained = read_json(training / "result.json")
    if (trained["model_uri"] != decision["candidate_model_uri"]
            or trained["run_id"] != decision["training_run_id"]
            or trained["data_asset_version"] != decision["evaluation_data_version"]):
        raise ValueError("Decision does not identify this training output.")
    for group in ("candidate", "reference"):
        values = decision["metrics"][group]
        for key in ("mae", "mae_items_1_49", "mae_items_50_plus"):
            if not np.isfinite(values[key]) or values[key] < 0:
                raise ValueError("Invalid decision metrics.")
    if not decision["eligible"]:
        if decision["reason"] != "PROMOTION_REJECTED":
            raise ValueError("Only ordinary promotion rejection may succeed without registration.")
        result = {"status": "NOT_REGISTERED", "reason": decision["reason"]}
    else:
        if decision["reason"] != "ELIGIBLE":
            raise ValueError("Inconsistent eligible decision.")
        registered = mlflow.register_model(decision["candidate_model_uri"], model_name)
        client = MlflowClient()
        for key, value in {
            "git_sha": decision["git_sha"],
            "data_asset_version": decision["evaluation_data_version"],
            "mae": decision["metrics"]["candidate"]["mae"],
            "framework": decision["framework"],
            "evaluation_policy_sha256": decision["policy_sha256"],
        }.items():
            client.set_model_version_tag(registered.name, registered.version, key, str(value))
        result = {"status": "REGISTERED", "name": registered.name, "version": registered.version}
    write_json(output / "registration.json", result)
    print(json.dumps(result, allow_nan=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="step", required=True)
    generate = sub.add_parser("generate")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--campaigns", type=int, default=550)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--source", type=Path, required=True)
    snap.add_argument("--data-version", required=True)
    valid = sub.add_parser("validate")
    valid.add_argument("--source", type=Path, required=True)
    evaluation = sub.add_parser("evaluate")
    evaluation.add_argument("--data", type=Path, required=True)
    evaluation.add_argument("--training", type=Path, required=True)
    evaluation.add_argument("--policy", type=Path, default=Path("config/components/promotion-policy.yml"))
    evaluation.add_argument("--champion-uri", default="none")
    evaluation.add_argument("--champion-deployment", default="none")
    registration = sub.add_parser("register")
    registration.add_argument("--decision", type=Path, required=True)
    registration.add_argument("--training", type=Path, required=True)
    registration.add_argument("--model-name", default="campaign-xgboost")
    for command in (snap, valid, evaluation, registration):
        command.add_argument("--output", type=Path, required=True)
    for command in (valid, evaluation):
        command.add_argument("--contract", type=Path, default=Path("config/features.yaml"))
    args = parser.parse_args()
    if args.step == "generate":
        args.output.mkdir(parents=True, exist_ok=True)
        generate_campaigns(args.seed, args.campaigns).to_csv(args.output / "data.csv", index=False)
    elif args.step == "snapshot":
        snapshot(args.source, args.output, args.data_version)
    elif args.step == "validate":
        validate(args.source, args.output, args.contract)
    elif args.step == "evaluate":
        evaluate(args.data, args.training, args.output, args.contract, args.policy,
                 args.champion_uri, args.champion_deployment)
    else:
        register(args.decision, args.training, args.output, args.model_name)


if __name__ == "__main__":
    main()
