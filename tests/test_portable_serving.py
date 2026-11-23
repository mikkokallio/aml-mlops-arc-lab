import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts.check_portable_serving import check_private_url, main


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254", "0.0.0.0", "20.1.2.3"])
def test_portable_target_rejects_non_vnet_addresses(address):
    with pytest.raises(ValueError, match="private, non-loopback"):
        check_private_url("https://lab.example", address)


def test_portable_target_pins_private_dns_and_preserves_tls_hostname(monkeypatch):
    monkeypatch.setattr(
        "scripts.check_portable_serving.socket.getaddrinfo",
        lambda *args: [(2, 1, 6, "", ("10.82.3.8", 443))],
    )
    assert check_private_url("https://lab.example") == [
        "--resolve", "lab.example:443:10.82.3.8"
    ]
    monkeypatch.setattr(
        "scripts.check_portable_serving.socket.getaddrinfo",
        lambda *args: [
            (2, 1, 6, "", ("10.82.3.8", 443)),
            (2, 1, 6, "", ("20.1.2.3", 443)),
        ],
    )
    with pytest.raises(ValueError, match="private, non-loopback"):
        check_private_url("https://lab.example")


@pytest.mark.parametrize("manifest", ["expected", "wrong-model"])
def test_portable_check_requires_real_health_manifest_and_predictions(
    monkeypatch, tmp_path, manifest
):
    request = tmp_path / "request.json"
    reference = tmp_path / "reference.json"
    output = tmp_path / "proof.json"
    request.write_text('{"input_data": {}}', encoding="utf-8")
    reference.write_text(json.dumps([1.0] * 100), encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "check", "--target", "aca", "--url", "https://lab.example",
            "--resolve-ip", "10.82.3.8", "--request", str(request),
            "--reference", str(reference), "--output", str(output),
            "--model-manifest-sha256", "expected",
        ],
    )
    calls = []
    real_run = subprocess.run

    def run(command, **kwargs):
        if command[0] != "curl":
            return real_run(command, **kwargs)
        calls.append(command)
        assert command[1] == "--disable"
        assert "--insecure" not in command
        if command[-1].endswith("/health"):
            return SimpleNamespace(stdout=json.dumps({
                "status": "ready", "model_version": "2", "model_source": "bundled",
                "model_manifest": {"sha256": manifest},
            }))
        assert kwargs["input"] == request.read_text(encoding="utf-8")
        return SimpleNamespace(stdout=json.dumps([1.0] * 100))

    monkeypatch.setattr("scripts.check_portable_serving.subprocess.run", run)
    if manifest != "expected":
        with pytest.raises(AssertionError, match="expected bundled model"):
            main()
        assert not output.exists()
        assert len(calls) == 1
    else:
        main()
        proof = json.loads(output.read_text(encoding="utf-8"))
        assert proof["comparison"]["passed"]
        assert proof["comparison"]["rows"] == 100
        assert not proof["aml_managed_deployment"]
        assert len(calls) == 2
