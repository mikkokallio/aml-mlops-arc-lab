import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import mlflow
import numpy as np
import pytest

from scripts.pipeline import steps
from src import train


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "config" / "components" / "promotion-policy.yml"
CONTRACT = ROOT / "config" / "features.yaml"
DATA_VERSION = "azureml:campaign-synthetic:1"


@pytest.fixture
def snapshot_data(tmp_path: Path):
    source = tmp_path / "source"
    source.mkdir()
    train.generate_campaigns(42, campaigns=8).to_csv(source / "data.csv", index=False)
    snapshot = tmp_path / "snapshot"
    validated = tmp_path / "validated"
    steps.snapshot(source, snapshot, DATA_VERSION)
    steps.validate(snapshot, validated, CONTRACT)
    return validated


@pytest.fixture
def local_tracking(tmp_path: Path):
    old_uri = mlflow.get_tracking_uri()
    old_registry = mlflow.get_registry_uri()
    uri = (tmp_path / "mlruns").as_uri()
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    mlflow.set_experiment("pipeline-contract")
    yield
    mlflow.end_run()
    mlflow.set_tracking_uri(old_uri)
    mlflow.set_registry_uri(old_registry)


def test_legacy_training_and_versioned_pipeline_register_then_reject(
    tmp_path: Path, monkeypatch, snapshot_data: Path, local_tracking
) -> None:
    # Keep the no-argument contract, reducing only fixture size.
    generator = train.generate_campaigns
    monkeypatch.setattr(train, "generate_campaigns", lambda seed: generator(seed, campaigns=8))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config").mkdir()
    shutil.copyfile(CONTRACT, tmp_path / "config" / "features.yaml")
    monkeypatch.setattr(sys, "argv", ["train"])
    train.main()
    legacy = steps.read_json(tmp_path / "outputs" / "result.json")
    assert legacy["rows"] > 0
    assert len(json.loads((tmp_path / "outputs" / "reference.json").read_text())) == 100

    training = tmp_path / "training"
    monkeypatch.setattr(sys, "argv", [
        "train", "--data", str(snapshot_data), "--data-version", DATA_VERSION,
        "--output", str(training),
    ])
    train.main()
    candidate = steps.read_json(training / "result.json")
    assert candidate["metrics"] == pytest.approx(legacy["metrics"], abs=1e-10)
    eligible = steps.evaluate(snapshot_data, training, tmp_path / "eligible", CONTRACT,
                              POLICY, "none", "none")
    assert eligible["eligible"] is True
    registered = steps.register(tmp_path / "eligible", training, tmp_path / "registered",
                                "pipeline-contract-candidate")
    assert registered["status"] == "REGISTERED"
    rejected = steps.evaluate(
        snapshot_data, training, tmp_path / "rejected", CONTRACT, POLICY,
        f"models:/{registered['name']}/{registered['version']}", "endpoint/blue",
    )
    assert rejected["reason"] == "PROMOTION_REJECTED"
    assert rejected["metrics"]["candidate"] == rejected["metrics"]["reference"]
    assert rejected["evaluation_data_version"] == DATA_VERSION
    assert steps.register(tmp_path / "rejected", training, tmp_path / "not-registered",
                          "pipeline-contract-candidate")["status"] == "NOT_REGISTERED"


@pytest.mark.parametrize("invalid", [False, True], ids=["quality-breach", "invalid-execution"])
def test_quality_failure_logs_metrics_but_invalid_execution_never_becomes_rejection(
    tmp_path: Path, monkeypatch, snapshot_data: Path, local_tracking, invalid: bool
) -> None:
    training = tmp_path / "training"
    training.mkdir()
    steps.write_json(training / "result.json", {
        "data_asset_version": DATA_VERSION,
        "features": train.selected_features(CONTRACT),
        "model_uri": "runs:/candidate/model",
        "run_id": "candidate",
        "git_sha": "test",
        "framework": "xgboost",
    })
    data = __import__("pandas").read_csv(snapshot_data / "data.csv")
    _, holdout = train.split_campaigns(data)
    predictions = np.full(len(holdout), np.nan) if invalid else holdout["target"].to_numpy() + 100
    monkeypatch.setattr(mlflow.pyfunc, "load_model",
                        lambda _: SimpleNamespace(predict=lambda _: predictions))
    logged = []
    monkeypatch.setattr(mlflow, "log_metrics", lambda value: logged.append(value))
    output = tmp_path / "evaluation"
    if invalid:
        with pytest.raises(ValueError, match="finite value"):
            steps.evaluate(snapshot_data, training, output, CONTRACT, POLICY, "none", "none")
        assert not (output / "decision.json").exists()
        assert not logged
    else:
        with pytest.raises(RuntimeError, match="^QUALITY_GATE_FAILED"):
            steps.evaluate(snapshot_data, training, output, CONTRACT, POLICY, "none", "none")
        assert logged[0]["candidate_mae"] == pytest.approx(100)
        assert steps.read_json(output / "decision.json")["eligible"] is False
        with pytest.raises(ValueError, match="ordinary promotion rejection"):
            steps.register(output, training, tmp_path / "registration", "must-not-register")
        assert not (tmp_path / "registration" / "registration.json").exists()
