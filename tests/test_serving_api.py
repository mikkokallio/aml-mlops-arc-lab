import copy
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import mlflow.xgboost
import numpy as np
import pandas as pd
import pytest
from mlflow.models import infer_signature
from xgboost import XGBRegressor

from scripts.compare_predictions import compare_predictions
from scripts.serving import score


@pytest.fixture(scope="module")
def saved_models():
    root = Path("tests") / ".serving-test-models"
    root.mkdir(exist_ok=False)
    frame = pd.DataFrame(
        {
            "item_position": np.arange(1, 101, dtype=np.int64),
            "setting_a": np.linspace(-2, 2, 100),
            "setting_b": np.linspace(2, -1, 100),
        }
    )
    models = {}
    try:
        for version in ("1", "2"):
            model = XGBRegressor(n_estimators=3, max_depth=2, n_jobs=1, random_state=42)
            model.fit(frame, frame["setting_a"] * 2 + int(version) * 10)
            mlflow.xgboost.save_model(
                model,
                str(root / version),
                signature=infer_signature(frame, model.predict(frame)),
                pip_requirements=[],
            )
            models[version] = model
        yield root, frame, models
    finally:
        import shutil

        shutil.rmtree(root)


@pytest.fixture
def configured(monkeypatch, saved_models):
    root, frame, models = saved_models
    monkeypatch.delenv("AZUREML_MODEL_DIR", raising=False)
    monkeypatch.delenv("PROBE_PACKAGE_INDEX", raising=False)
    monkeypatch.setenv("MODEL_VERSION", "1")
    monkeypatch.setattr(score, "BUNDLED_MODELS_ROOT", root)
    return frame, models


def payload(frame):
    return {"input_data": frame.to_dict(orient="split")}


@pytest.mark.parametrize("version", ["1", "2"])
def test_real_model_predictions_and_startup_snapshot(monkeypatch, configured, version):
    frame, models = configured
    monkeypatch.setenv("MODEL_VERSION", version)
    monkeypatch.setenv("SOURCE_GIT_SHA", "source-commit")
    monkeypatch.setenv("MODEL_PROVENANCE", "registered-model-version")
    app = score.create_app()
    client = app.test_client()
    monkeypatch.setenv("MODEL_VERSION", "2" if version == "1" else "1")
    response = client.post("/score", json=payload(frame))
    assert response.status_code == 200
    assert compare_predictions(models[version].predict(frame).tolist(), response.json)["passed"]
    health = client.get("/health").json
    assert health["model_version"] == version
    assert health["source_git_sha"] == "source-commit"
    assert health["model_provenance"] == "registered-model-version"
    assert health["package_index_probe"] == {}
    manifest = health["model_manifest"]
    encoded = json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
    assert manifest["sha256"] == hashlib.sha256(encoded).hexdigest()
    for entry in manifest["files"]:
        data = (score.BUNDLED_MODELS_ROOT / version / entry["path"]).read_bytes()
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["bytes"] == len(data)


def test_mount_precedence_no_fallback_and_load_once(monkeypatch, configured, saved_models):
    frame, models = configured
    root, _, _ = saved_models
    monkeypatch.setenv("AZUREML_MODEL_DIR", str(root / "2"))
    original = score.mlflow.pyfunc.load_model
    calls = []

    def load(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(score.mlflow.pyfunc, "load_model", load)
    client = score.create_app().test_client()
    monkeypatch.setenv("AZUREML_MODEL_DIR", str(root / "1"))
    for _ in range(2):
        result = client.post("/score", json=payload(frame))
        assert compare_predictions(models["2"].predict(frame).tolist(), result.json)["passed"]
    assert len(calls) == 1
    assert client.get("/health").json["model_source"] == "azureml_mount"


@pytest.mark.parametrize("mount", ["", "missing", "ambiguous", "no-model"])
def test_invalid_mount_never_uses_valid_bundle(monkeypatch, configured, saved_models, mount):
    root, _, _ = saved_models
    value = {"": "", "missing": str(root / "missing"), "ambiguous": str(root), "no-model": str(root / "empty")}[mount]
    if mount == "no-model":
        (root / "empty").mkdir(exist_ok=True)
    monkeypatch.setenv("AZUREML_MODEL_DIR", value)
    with pytest.raises((ValueError, FileNotFoundError)):
        score.create_app()


@pytest.mark.parametrize("version", ["", "3", "../1"])
def test_invalid_version_rejected(monkeypatch, configured, version):
    monkeypatch.setenv("MODEL_VERSION", version)
    with pytest.raises(ValueError, match="MODEL_VERSION"):
        score.create_app()


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(extra=True),
        lambda p: p.update(input_data=[]),
        lambda p: p["input_data"].update(columns=list(reversed(score.EXPECTED_COLUMNS))),
        lambda p: p["input_data"].update(data=[]),
        lambda p: p["input_data"].update(data=[[1, 2, 3]] * 501, index=list(range(501))),
        lambda p: p["input_data"].update(index=[]),
        lambda p: p["input_data"]["data"].__setitem__(0, [1, 2]),
        lambda p: p["input_data"]["data"][0].__setitem__(1, True),
        lambda p: p["input_data"]["data"][0].__setitem__(1, "2"),
        lambda p: p["input_data"]["data"][0].__setitem__(1, None),
        lambda p: p["input_data"]["data"][0].__setitem__(1, float("nan")),
        lambda p: p["input_data"]["data"][0].__setitem__(1, float("inf")),
        lambda p: p["input_data"]["data"][0].__setitem__(1, 10**400),
        lambda p: p["input_data"]["data"][0].__setitem__(0, 1.5),
        lambda p: p["input_data"]["data"][0].__setitem__(0, 2**64),
    ],
)
def test_invalid_payloads_return_400(configured, change):
    frame, _ = configured
    body = copy.deepcopy(payload(frame))
    change(body)
    response = score.create_app().test_client().post("/score", json=body)
    assert response.status_code == 400
    assert set(response.json) == {"error"}


@pytest.mark.parametrize("data,content_type", [("{", "application/json"), ("{}", "text/plain"), ("null", "application/json")])
def test_bad_json_returns_400(configured, data, content_type):
    response = score.create_app().test_client().post("/score", data=data, content_type=content_type)
    assert response.status_code == 400
    assert "error" in response.json


def test_oversized_request_returns_json_400(configured):
    response = score.create_app().test_client().post(
        "/score", data=" " * (1024 * 1024 + 1), content_type="application/json"
    )
    assert response.status_code == 400
    assert "1 MiB" in response.json["error"]


def test_500_row_boundary(configured):
    frame, _ = configured
    frame = pd.concat([frame] * 5, ignore_index=True)
    response = score.create_app().test_client().post("/score", json=payload(frame))
    assert response.status_code == 200
    assert len(response.json) == 500


@pytest.mark.parametrize("output", [np.ones((100, 1)), np.full(100, np.nan), np.ones(99), np.array(["bad"] * 100)])
def test_invalid_predictions_are_logged_500(monkeypatch, configured, caplog, output):
    frame, _ = configured

    class BrokenModel:
        def predict(self, frame):
            return output

    monkeypatch.setattr(score.mlflow.pyfunc, "load_model", lambda path: BrokenModel())
    response = score.create_app().test_client().post("/score", json=payload(frame))
    assert response.status_code == 500
    assert not isinstance(response.json, list)
    assert "Model must return" in caplog.text


def test_unexpected_inference_exception_is_not_success(monkeypatch, configured, caplog):
    frame, _ = configured

    class BrokenModel:
        def predict(self, frame):
            raise RuntimeError("inference failed")

    monkeypatch.setattr(score.mlflow.pyfunc, "load_model", lambda path: BrokenModel())
    response = score.create_app().test_client().post("/score", json=payload(frame))
    assert response.status_code == 500
    assert "inference failed" in caplog.text


def test_probe_disabled_makes_no_network_calls(monkeypatch, configured):
    def forbidden(*args, **kwargs):
        pytest.fail("Package-index probe was not enabled.")

    monkeypatch.setattr(score, "urlopen", forbidden)
    score.create_app()


def test_probe_records_independent_results_once(monkeypatch, configured, caplog):
    calls = []

    def request(url, timeout):
        calls.append((url, timeout))
        if "pypi.org" in url:
            raise URLError("network denied")
        raise HTTPError(url, 404, "not found", {}, None)

    monkeypatch.setenv("PROBE_PACKAGE_INDEX", "1")
    monkeypatch.setattr(score, "urlopen", request)
    client = score.create_app().test_client()
    monkeypatch.delenv("PROBE_PACKAGE_INDEX")
    for _ in range(2):
        probe = client.get("/health").json["package_index_probe"]
        assert probe["pypi"]["status"] == "blocked"
        assert probe["pythonhosted"] == {"status": "allowed", "http_status": 404}
    assert calls == [(url, 5) for url in score.PACKAGE_INDEX_URLS.values()]
    assert "package_index_network_error index=pypi" in caplog.text


def test_signature_mismatch_fails_startup(monkeypatch, configured):
    original = score.Model.load

    def wrong_signature(path):
        model = original(path)
        model.signature = infer_signature(pd.DataFrame({"wrong": [1.0]}), np.array([1.0]))
        return model

    monkeypatch.setattr(score.Model, "load", wrong_signature)
    with pytest.raises(ValueError, match="signature"):
        score.create_app()
