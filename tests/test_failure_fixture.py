import base64
import json
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import pytest
from mlflow.entities import RunStatus
from mlflow.exceptions import MlflowException
from mlflow.store.tracking.file_store import FileStore
from mlflow.tracking import MlflowClient

from scripts.pipeline import failure_fixture as fixture
from scripts.pipeline import steps
from src import train


FIXTURE_SHA = "1234567890abcdef1234567890abcdef12345678"


@pytest.fixture
def tracking(tmp_path: Path):
    old_tracking = mlflow.get_tracking_uri()
    old_registry = mlflow.get_registry_uri()
    uri = (tmp_path / "mlruns").as_uri()
    mlflow.set_tracking_uri(uri)
    mlflow.set_registry_uri(uri)
    experiment = mlflow.set_experiment("real-negative-fixtures")
    yield MlflowClient(), experiment.experiment_id
    mlflow.end_run()
    mlflow.set_tracking_uri(old_tracking)
    mlflow.set_registry_uri(old_registry)


def test_execution_failure_survives_base64_bootstrap(tmp_path: Path, tracking) -> None:
    client, experiment_id = tracking
    output = tmp_path / "execution"
    source = base64.b64encode(Path(fixture.__file__).read_bytes())
    namespace = {"__name__": "embedded_fixture"}
    exec(compile(base64.b64decode(source), "<aml-failure-fixture>", "exec"), namespace)
    assert "__file__" not in namespace
    with pytest.raises(RuntimeError, match="^CONTROLLED_EXECUTION_FAILURE$"):
        namespace["main"]([
            "--case", "execution", "--data", str(tmp_path / "unused-input"),
            "--fixture-git-sha", FIXTURE_SHA, "--output", str(output),
        ])
    runs = client.search_runs([experiment_id])
    assert len(runs) == 1
    assert runs[0].info.status == "FAILED"
    assert runs[0].data.tags["fixture_case"] == "execution"
    assert runs[0].data.tags["fixture_git_sha"] == FIXTURE_SHA
    assert not (output / "evaluation" / "decision.json").exists()
    assert not list(client.search_registered_models())


@pytest.mark.parametrize("provenance_outage", [False, True])
def test_real_bad_model_fails_unchanged_gate_and_logs_decision(
    tmp_path: Path, tracking, monkeypatch, provenance_outage: bool,
) -> None:
    # AML terminal states are immutable, unlike the default local file store.
    terminal_states = {}
    update_run_info = FileStore.update_run_info

    def immutable_terminal_status(store, run_id, run_status, end_time, run_name):
        if run_status is not None and RunStatus.is_terminated(run_status):
            status = RunStatus.to_string(run_status)
            if run_id in terminal_states and terminal_states[run_id] != status:
                raise MlflowException("Cannot set run to multiple terminal states", "BAD_REQUEST")
            terminal_states[run_id] = status
        return update_run_info(store, run_id, run_status, end_time, run_name)

    monkeypatch.setattr(FileStore, "update_run_info", immutable_terminal_status)
    if provenance_outage:
        set_tag = MlflowClient.set_tag

        def fail_evaluation_provenance(client, run_id, key, value, **kwargs):
            if key == "fixture_stage" and value == "evaluation":
                raise RuntimeError("Controlled provenance outage")
            return set_tag(client, run_id, key, value, **kwargs)

        monkeypatch.setattr(MlflowClient, "set_tag", fail_evaluation_provenance)
    client, experiment_id = tracking
    data = tmp_path / "source"
    data.mkdir()
    train.generate_campaigns(42, campaigns=8).to_csv(data / "data.csv", index=False)
    output = tmp_path / "quality"
    contract_hash = steps.digest(fixture.CONTRACT)
    policy_hash = steps.digest(fixture.POLICY)
    with pytest.raises(RuntimeError, match="^QUALITY_GATE_FAILED") as failure:
        fixture.main([
            "--case", "quality", "--data", str(data), "--fixture-git-sha", FIXTURE_SHA,
            "--output", str(output),
        ])
    result = steps.read_json(output / "training" / "result.json")
    decision = steps.read_json(output / "evaluation" / "decision.json")
    assert str(failure.value) == decision["reason"]
    assert any(frame.name == "evaluate" for frame in failure.traceback)
    assert mlflow.active_run() is None
    provenance = steps.read_json(output / "fixture.json")
    assert result["component_source_sha"] == provenance["component_source_sha"] == fixture.COMPONENT_SOURCE_SHA
    assert result["fixture_git_sha"] == provenance["fixture_git_sha"] == FIXTURE_SHA
    assert decision["git_sha"] == fixture.COMPONENT_SOURCE_SHA
    assert decision["candidate_model_uri"] == result["model_uri"]
    assert decision["training_run_id"] == result["run_id"]
    assert decision["eligible"] is False
    assert decision["reason"].startswith("QUALITY_GATE_FAILED")
    assert decision["evaluation_data_version"] == "azureml:campaign-synthetic:2"
    assert decision["reference_model"] == "training-target-median-baseline"
    assert decision["policy_sha256"] == policy_hash == steps.digest(fixture.POLICY)
    assert steps.digest(fixture.CONTRACT) == contract_hash
    assert decision["snapshot_sha256"] == steps.digest(data / "data.csv")

    frame = pd.read_csv(data / "data.csv")
    training, holdout = train.split_campaigns(frame)
    assert not set(training["campaign_id"]) & set(decision["holdout_campaigns"])
    assert decision["holdout_campaigns"] == sorted(holdout["campaign_id"].unique().tolist())
    expected = train.regression_metrics(holdout, np.full(len(holdout), 1000.0))
    assert decision["metrics"]["candidate"] == pytest.approx(expected)
    reference = train.regression_metrics(
        holdout, np.full(len(holdout), training["target"].median()),
    )
    assert decision["metrics"]["reference"] == pytest.approx(reference)
    assert min(expected.values()) > 900
    features = train.selected_features(fixture.CONTRACT)
    logged = mlflow.pyfunc.load_model(result["model_uri"])
    np.testing.assert_array_equal(logged.predict(holdout[features]), np.full(len(holdout), 1000.0))
    saved = mlflow.pyfunc.load_model(str(output / "training" / "model"))
    np.testing.assert_array_equal(saved.predict(holdout[features]), logged.predict(holdout[features]))
    runs = client.search_runs([experiment_id])
    assert len(runs) == 2
    evaluation = next(run for run in runs if "promotion_reason" in run.data.tags)
    assert evaluation.info.status == "FINISHED"
    assert client.get_run(result["run_id"]).info.status == "FINISHED"
    assert terminal_states == {run.info.run_id: "FINISHED" for run in runs}
    if not provenance_outage:
        assert evaluation.data.tags["fixture_stage"] == "evaluation"
    assert evaluation.data.tags["component_source_sha"] == fixture.COMPONENT_SOURCE_SHA
    assert evaluation.data.tags["fixture_git_sha"] == FIXTURE_SHA
    for group, metrics in decision["metrics"].items():
        for name, value in metrics.items():
            assert evaluation.data.metrics[f"{group}_{name}"] == pytest.approx(value)
    downloads = tmp_path / "downloads"
    downloads.mkdir()
    artifact = client.download_artifacts(evaluation.info.run_id, "decision.json", str(downloads))
    assert json.loads(Path(artifact).read_text(encoding="utf-8")) == decision
    assert not list(client.search_registered_models())
    assert not (output / "registration").exists()
