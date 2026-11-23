"""Portable, build-time provisioned MLflow model HTTP service."""

import hashlib
import json
import logging
import math
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import mlflow
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request
from mlflow.models import Model
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType


LOGGER = logging.getLogger(__name__)
BUNDLED_MODELS_ROOT = Path("/opt/models")
EXPECTED_COLUMNS = ["item_position", "setting_a", "setting_b"]
PACKAGE_INDEX_URLS = {
    "pypi": "https://pypi.org/simple/pip/",
    "pythonhosted": "https://files.pythonhosted.org/",
}
NUMERIC_TYPES = {
    "integer": np.int32,
    "long": np.int64,
    "float": np.float32,
    "double": np.float64,
}


class InvalidInput(ValueError):
    """A malformed scoring request."""


def model_directory(version: str) -> tuple[Path, str]:
    if "AZUREML_MODEL_DIR" in os.environ:
        mounted = os.environ["AZUREML_MODEL_DIR"]
        if not mounted.strip():
            raise ValueError("AZUREML_MODEL_DIR must not be empty.")
        root = Path(mounted).resolve(strict=True)
        source = "azureml_mount"
    else:
        root = (BUNDLED_MODELS_ROOT / version).resolve(strict=True)
        source = "bundled"
    candidates = sorted(root.rglob("MLmodel"))
    if len(candidates) != 1 or not candidates[0].is_file():
        raise ValueError("Model directory must contain exactly one MLmodel file.")
    return candidates[0].parent, source


def content_manifest(directory: Path) -> dict:
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Model artifacts must not contain symbolic links.")
        if path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            files.append(
                {
                    "path": path.relative_to(directory).as_posix(),
                    "sha256": digest.hexdigest(),
                    "bytes": path.stat().st_size,
                }
            )
    serialized = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"sha256": hashlib.sha256(serialized).hexdigest(), "files": files}


def probe_package_indexes() -> dict:
    results = {}
    for name, url in PACKAGE_INDEX_URLS.items():
        try:
            with urlopen(url, timeout=5) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
        except (URLError, OSError) as error:
            LOGGER.warning("package_index_network_error index=%s error=%s", name, type(error).__name__)
            results[name] = {"status": "blocked", "error": type(error).__name__}
            continue
        LOGGER.info("package_index_network_allowed index=%s http_status=%s", name, status)
        results[name] = {"status": "allowed", "http_status": status}
    return results


def input_frame(payload: object, columns: list[str], types: list[str]) -> pd.DataFrame:
    if not isinstance(payload, dict) or set(payload) != {"input_data"}:
        raise InvalidInput("Expected an object containing only input_data.")
    split = payload["input_data"]
    if not isinstance(split, dict) or set(split) != {"columns", "index", "data"}:
        raise InvalidInput("input_data must contain columns, index and data.")
    if split["columns"] != columns:
        raise InvalidInput(f"columns must equal {columns}.")
    rows = split["data"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise InvalidInput("data must contain between 1 and 500 rows.")
    index = split["index"]
    if not isinstance(index, list) or len(index) != len(rows):
        raise InvalidInput("index must contain one entry per row.")
    if any(isinstance(value, (dict, list, bool)) or not isinstance(value, (str, int)) for value in index):
        raise InvalidInput("index entries must be strings or integers.")
    for row in rows:
        if not isinstance(row, list) or len(row) != len(columns):
            raise InvalidInput("Each row must contain one number per column.")
        for value, type_name in zip(row, types):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise InvalidInput("Feature values must be finite numbers.")
            try:
                finite = math.isfinite(value)
            except OverflowError:
                finite = False
            if not finite:
                raise InvalidInput("Feature values must be finite numbers.")
            dtype = NUMERIC_TYPES[type_name]
            if np.issubdtype(dtype, np.integer):
                limits = np.iinfo(dtype)
                if value != int(value) or not limits.min <= value <= limits.max:
                    raise InvalidInput("Integer features must be integral and within model dtype bounds.")
            elif abs(value) > np.finfo(dtype).max:
                raise InvalidInput("Feature value exceeds model dtype bounds.")
    return pd.DataFrame(
        {name: pd.Series([row[i] for row in rows], dtype=NUMERIC_TYPES[types[i]])
         for i, name in enumerate(columns)}
    )


def create_app() -> Flask:
    version = os.environ.get("MODEL_VERSION", "")
    if version not in {"1", "2"}:
        raise ValueError("MODEL_VERSION must be explicitly set to 1 or 2.")
    directory, source = model_directory(version)
    manifest = content_manifest(directory)
    metadata = Model.load(str(directory / "MLmodel"))
    if metadata.signature is None or metadata.signature.inputs is None:
        raise ValueError("Model must declare its input signature.")
    schema = metadata.signature.inputs
    columns = schema.input_names()
    types = [getattr(field.type, "name", "") for field in schema.inputs]
    if columns != EXPECTED_COLUMNS or any(name not in NUMERIC_TYPES for name in types):
        raise ValueError("Model signature must match the three numeric campaign features.")
    model = mlflow.pyfunc.load_model(str(directory))
    health = {
        "status": "ready",
        "model_version": version,
        "model_source": source,
        "model_manifest": manifest,
        "source_git_sha": os.environ.get("SOURCE_GIT_SHA", os.environ.get("LAB_GIT_SHA", "unknown")),
        "model_provenance": os.environ.get("MODEL_PROVENANCE", "unspecified"),
        "package_index_probe_enabled": os.environ.get("PROBE_PACKAGE_INDEX") == "1",
        "package_index_probe": {},
    }
    if health["package_index_probe_enabled"]:
        health["package_index_probe"] = probe_package_indexes()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    LOGGER.info("model_ready version=%s source=%s manifest_sha256=%s", version, source, manifest["sha256"])

    @app.get("/health")
    def ready():
        return jsonify(health)

    @app.errorhandler(InvalidInput)
    @app.errorhandler(BadRequest)
    @app.errorhandler(RequestEntityTooLarge)
    @app.errorhandler(UnsupportedMediaType)
    def invalid_request(error):
        if isinstance(error, InvalidInput):
            message = str(error)
        elif isinstance(error, RequestEntityTooLarge):
            message = "Request must not exceed 1 MiB."
        else:
            message = "Request must contain valid JSON."
        LOGGER.warning("invalid_scoring_request reason=%s", message)
        return jsonify({"error": message}), 400

    @app.post("/score")
    def score():
        frame = input_frame(request.get_json(), columns, types)
        predictions = np.asarray(model.predict(frame))
        if (
            predictions.shape != (len(frame),)
            or not np.issubdtype(predictions.dtype, np.number)
            or np.iscomplexobj(predictions)
            or not np.isfinite(predictions).all()
        ):
            raise ValueError("Model must return one finite numeric prediction per row.")
        return jsonify(predictions.tolist())

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    create_app().run(host="0.0.0.0", port=8080)
