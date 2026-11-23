import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from azure.ai.ml import MLClient
from azure.core.credentials import AccessToken
from azure.core.pipeline.transport import HttpResponse, HttpTransport

from scripts import register_training_environment
from src.train import generate_campaigns, selected_features


def test_post_outcome_feature_is_rejected(tmp_path: Path) -> None:
    contract = {
        "selected": ["measured_outcome"],
        "features": {"measured_outcome": {"known_at_prediction_time": False}},
    }
    path = tmp_path / "features.yaml"
    path.write_text(yaml.safe_dump(contract), encoding="utf-8")
    with pytest.raises(ValueError, match="Forbidden post-outcome"):
        selected_features(path)


def test_campaign_generator_is_reproducible_and_covers_both_phases() -> None:
    first = generate_campaigns(42, campaigns=5)
    second = generate_campaigns(42, campaigns=5)
    assert first.equals(second)
    lengths = first.groupby("campaign_id").size()
    assert lengths.between(60, 120).all()
    assert (first["item_position"] < 50).any()
    assert (first["item_position"] >= 50).any()


def test_training_environment_sends_conda_requirements_in_actual_sdk_request(monkeypatch) -> None:
    payloads = []

    class Response(HttpResponse):
        def __init__(self, request, payload):
            super().__init__(request, None)
            self.status_code = 200
            self.headers = {"Content-Type": "application/json"}
            self.content_type = "application/json"
            self.reason = "OK"
            self.payload = payload

        def body(self):
            return json.dumps(self.payload).encode()

    class Transport(HttpTransport):
        def open(self):
            pass

        def close(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

        def send(self, request, **kwargs):
            assert request.method == "PUT"
            payload = json.loads(request.body)
            payloads.append(payload)
            return Response(request, {
                "id": request.url.split("?")[0].removeprefix("https://management.azure.com"),
                "name": "2",
                "properties": payload["properties"],
            })

    root = Path(__file__).resolve().parents[1]
    credential = SimpleNamespace(
        get_token=lambda *args, **kwargs: AccessToken("offline-test-token", int(time.time()) + 3600)
    )
    client = MLClient(
        credential, "00000000-0000-0000-0000-000000000000", "test-rg", "test-workspace",
        transport=Transport(),
    )
    monkeypatch.setattr(register_training_environment, "AzureCliCredential", lambda **kwargs: credential)
    monkeypatch.setattr(register_training_environment, "MLClient", lambda *args: client)
    monkeypatch.setattr(sys, "argv", [
        "register_training_environment", "--subscription", "test-subscription",
        "--resource-group", "test-rg", "--workspace", "test-workspace",
        "--environment", str(root / "config" / "training-environment.yml"),
        "--requirements", str(root / "requirements.txt"),
    ])
    register_training_environment.main()
    conda = yaml.safe_load(payloads[0]["properties"]["condaFile"])
    assert "python=3.12.3" in conda["dependencies"]
    actual = next(item["pip"] for item in conda["dependencies"] if isinstance(item, dict))
    expected = [
        line.strip() for line in (root / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert actual == expected
