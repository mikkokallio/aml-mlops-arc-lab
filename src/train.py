"""Train and log a small campaign-grouped regression model for the Arc probe."""

import argparse
import json
import os
from pathlib import Path

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import yaml
from mlflow.models import infer_signature
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor


def selected_features(contract_path: Path) -> list[str]:
    contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
    selected = contract["selected"]
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("Selected features must be nonempty and unique.")
    for name in selected:
        definition = contract["features"][name]
        if definition["known_at_prediction_time"] is not True:
            raise ValueError(f"Forbidden post-outcome feature: {name}")
    return selected


def generate_campaigns(seed: int, campaigns: int = 550) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    frames = []
    for campaign in range(campaigns):
        size = int(rng.integers(60, 121))
        position = np.arange(1, size + 1)
        setting_a = rng.uniform(-3, 3, size)
        setting_b = rng.uniform(-3, 3, size)
        target = (
            12
            + 2.5 * setting_a
            - 1.8 * setting_b
            + 7 * np.exp(-position / 18)
            + rng.normal(0, 0.3)
            + rng.normal(0, 0.4, size)
        )
        frames.append(
            pd.DataFrame(
                {
                    "campaign_id": campaign,
                    "item_position": position,
                    "setting_a": setting_a,
                    "setting_b": setting_b,
                    "target": target,
                    "measured_outcome": target + rng.normal(0, 0.01, size),
                    "final_adjustment": target - 12,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def split_campaigns(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    campaign_ids = np.sort(data["campaign_id"].unique())
    if len(campaign_ids) < 2:
        raise ValueError("At least two campaigns are required.")
    boundary = campaign_ids[int(len(campaign_ids) * 0.8)]
    train = data.loc[data["campaign_id"] < boundary]
    holdout = data.loc[data["campaign_id"] >= boundary]
    if train.empty or holdout.empty or set(train["campaign_id"]) & set(holdout["campaign_id"]):
        raise ValueError("Invalid campaign-grouped split.")
    return train, holdout


def regression_metrics(holdout: pd.DataFrame, predicted: np.ndarray) -> dict[str, float]:
    predicted = np.asarray(predicted)
    if predicted.shape != (len(holdout),) or not np.isfinite(predicted).all():
        raise ValueError("Predictions must be one finite value per holdout row.")
    errors = abs(holdout["target"].to_numpy() - predicted)
    metrics = {
        "mae": float(mean_absolute_error(holdout["target"], predicted)),
        "mae_items_1_49": float(errors[holdout["item_position"].to_numpy() < 50].mean()),
        "mae_items_50_plus": float(errors[holdout["item_position"].to_numpy() >= 50].mean()),
    }
    if not all(np.isfinite(value) for value in metrics.values()):
        raise ValueError("Both campaign phases must have finite metrics.")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("outputs"))
    parser.add_argument("--contract", type=Path, default=Path("config/features.yaml"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--tracking-uri")
    parser.add_argument("--experiment", default="arc-campaign-probe")
    parser.add_argument("--model-name", default="campaign-xgboost")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--data", type=Path, help="Validated snapshot folder containing data.csv.")
    parser.add_argument("--data-version", default="synthetic-inline-seed-42")
    parser.add_argument("--git-sha", default=os.environ.get("LAB_GIT_SHA", "uncommitted"))
    args = parser.parse_args()
    if args.register and not args.tracking_uri:
        raise ValueError("Registration requires an explicit workspace tracking URI.")

    args.output.mkdir(parents=True, exist_ok=True)
    features = selected_features(args.contract)
    data = pd.read_csv(args.data / "data.csv") if args.data else generate_campaigns(args.seed)
    train, holdout = split_campaigns(data)
    if args.tracking_uri:
        mlflow.set_tracking_uri(args.tracking_uri)
    mlflow.set_experiment(args.experiment)
    mlflow.xgboost.autolog(log_models=False)
    model = XGBRegressor(
        n_estimators=120,
        max_depth=4,
        learning_rate=0.1,
        n_jobs=2,
        random_state=args.seed,
    )
    with mlflow.start_run() as run:
        mlflow.set_tags(
            {
                "purpose": "arc-feasibility-probe",
                "data_producer": "synthetic-lab-generator",
                "git_sha": args.git_sha,
                "framework": "xgboost",
                "split": "campaign-grouped-final-20-percent",
                "data_asset_version": args.data_version if args.data else f"synthetic-inline-seed-{args.seed}",
            }
        )
        model.fit(train[features], train["target"])
        predicted = model.predict(holdout[features])
        evaluation = holdout[["campaign_id", "item_position", "target"]].copy()
        evaluation["prediction"] = predicted
        evaluation["absolute_error"] = abs(evaluation["target"] - predicted)
        baseline = np.full(len(holdout), train["target"].median())
        metrics = regression_metrics(holdout, predicted)
        metrics["baseline_mae"] = float(mean_absolute_error(holdout["target"], baseline))
        mlflow.log_metrics(metrics)
        mlflow.log_params(
            {
                "seed": args.seed,
                "rows": len(data),
                "train_campaigns": train["campaign_id"].nunique(),
                "holdout_campaigns": holdout["campaign_id"].nunique(),
            }
        )
        evaluation.groupby("campaign_id")["absolute_error"].mean().to_csv(
            args.output / "per-campaign-mae.csv"
        )
        mlflow.log_artifact(str(args.output / "per-campaign-mae.csv"))
        mlflow.log_artifact(str(args.contract))
        example = holdout[features].head(100).copy()
        reference = model.predict(example)
        signature = infer_signature(example, reference)
        model_info = mlflow.xgboost.log_model(
            model,
            artifact_path="model",
            signature=signature,
            input_example=example.head(3),
            pip_requirements=[
                "mlflow==2.22.2",
                "xgboost==2.1.4",
                "numpy==1.26.4",
                "pandas==2.2.3",
                "scikit-learn==1.6.1",
                "azureml-inference-server-http==1.5.0",
                "azureml-ai-monitoring==1.0.0",
            ],
        )
        mlflow.xgboost.save_model(
            model, str(args.output / "model"), signature=signature
        )
        reloaded = mlflow.pyfunc.load_model(model_info.model_uri)
        reference = np.asarray(reloaded.predict(example))
        np.testing.assert_allclose(
            reference, model.predict(example), rtol=0.00001, atol=0.00001
        )
        payload = {"input_data": example.to_dict(orient="split")}
        (args.output / "request.json").write_text(
            json.dumps(payload, allow_nan=False), encoding="utf-8"
        )
        (args.output / "reference.json").write_text(
            json.dumps(reference.tolist(), allow_nan=False), encoding="utf-8"
        )
        result = {
            "run_id": run.info.run_id,
            "model_uri": model_info.model_uri,
            "metrics": metrics,
            "rows": len(data),
            "features": features,
            "data_asset_version": args.data_version if args.data else f"synthetic-inline-seed-{args.seed}",
            "git_sha": args.git_sha,
            "framework": "xgboost",
            "prediction_tolerance": {"rtol": 0.00001, "atol": 0.00001},
            "reference_predictor": "mlflow.pyfunc.load_model(logged_model_uri)",
        }
        if args.register:
            registered = mlflow.register_model(
                model_info.model_uri, args.model_name, await_registration_for=300
            )
            result["model_name"] = registered.name
            result["model_version"] = registered.version
        (args.output / "result.json").write_text(
            json.dumps(result, indent=2, allow_nan=False), encoding="utf-8"
        )
        print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
