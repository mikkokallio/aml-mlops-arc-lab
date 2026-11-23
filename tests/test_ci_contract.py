"""Credential-free PR checks for committed source and deployment contracts."""

import socket
import tabnanny
import tokenize
import warnings
from pathlib import Path

import pytest
from azure.ai.ml import load_online_deployment, load_online_endpoint

from src.train import selected_features

ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = sorted(
    path
    for folder in ("src", "scripts", "tests")
    for path in (ROOT / folder).rglob("*.py")
)


@pytest.mark.parametrize(
    "path", PYTHON_FILES, ids=lambda path: path.relative_to(ROOT).as_posix()
)
def test_python_syntax_and_indentation(path: Path) -> None:
    with tokenize.open(path) as source:
        text = source.read()
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        compile(text, str(path), "exec")
    with path.open("rb") as source:
        tabnanny.process_tokens(tokenize.tokenize(source.readline))


def test_committed_feature_contract_is_prediction_safe() -> None:
    selected_features(ROOT / "config" / "features.yaml")


@pytest.mark.parametrize(
    ("filename", "loader"),
    [
        ("endpoint.yml", load_online_endpoint),
        ("deployment.yml", load_online_deployment),
    ],
)
def test_aml_yaml_schema_without_network(filename, loader, monkeypatch) -> None:
    def deny_network(*args, **kwargs):
        raise AssertionError("AML YAML validation must not access the network.")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    monkeypatch.setattr(socket, "create_connection", deny_network)
    # These SDK loaders validate their bundled schemas without an MLClient.
    # instance-types.yml is a Kubernetes CRD, not an AML SDK entity schema.
    loader(ROOT / "config" / filename)
