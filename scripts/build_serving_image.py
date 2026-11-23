"""Build a portable image from registered models inside the private lab VNet."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from azure.ai.ml import MLClient
from azure.identity import ManagedIdentityCredential
import mlflow
import numpy as np
import pandas as pd
import requests


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--git-sha", required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    credential = ManagedIdentityCredential(client_id=args.client_id)
    client = MLClient(
        credential, args.subscription, args.resource_group, args.workspace
    )
    models: dict[str, dict[str, object]] = {}
    proof: dict[str, object] = {"git_sha": args.git_sha, "models": models}
    for version in ("1", "2"):
        asset = client.models.get(args.model_name, version)
        download = args.output / f"download-{version}"
        client.models.download(args.model_name, version, download_path=str(download))
        roots = list(download.rglob("MLmodel"))
        if len(roots) != 1:
            raise ValueError(f"Expected one MLmodel for version {version}: {roots}")
        source = roots[0].parent
        destination = args.context / "models" / version
        shutil.copytree(source, destination, dirs_exist_ok=False)
        model = mlflow.pyfunc.load_model(str(destination))
        example = json.loads((destination / "input_example.json").read_text())
        frame = pd.DataFrame(example["data"], columns=example["columns"])
        frame = pd.concat([frame] * 100, ignore_index=True).head(100)
        expected = np.asarray(model.predict(frame))
        if expected.shape != (100,) or not np.isfinite(expected).all():
            raise ValueError("Reference must contain 100 finite predictions.")
        request = {"input_data": frame.to_dict(orient="split")}
        (args.output / f"request-{version}.json").write_text(json.dumps(request))
        (args.output / f"reference-{version}.json").write_text(
            json.dumps(expected.tolist(), allow_nan=False)
        )
        files = {
            str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(destination.rglob("*"))
            if path.is_file()
        }
        models[version] = {
            "asset_id": asset.id,
            "registered_tags": asset.tags,
            "files_sha256": files,
            "reference_predictions": len(expected),
        }
    base = "python:3.12-slim-bookworm"
    subprocess.run(["docker", "pull", base], check=True)
    digest = subprocess.check_output(
        ["docker", "image", "inspect", base, "--format", "{{index .RepoDigests 0}}"],
        text=True,
    ).strip()
    if "@sha256:" not in digest:
        raise ValueError("Base image was not resolved to an immutable digest.")
    image = f"{args.registry}/aml-serving-matrix:{args.git_sha[:12]}"
    subprocess.run(
        [
            "docker", "build", "--build-arg", f"BASE_IMAGE={digest}",
            "--tag", image, str(args.context),
        ],
        check=True,
    )
    token = credential.get_token("https://management.azure.com/.default").token
    exchange = requests.post(
        f"https://{args.registry}/oauth2/exchange",
        data={
            "grant_type": "access_token",
            "service": args.registry,
            "tenant": args.tenant,
            "access_token": token,
        },
        timeout=30,
    )
    exchange.raise_for_status()
    login = subprocess.run(
        [
            "docker", "login", args.registry,
            "--username", "00000000-0000-0000-0000-000000000000",
            "--password-stdin",
        ],
        input=exchange.json()["refresh_token"],
        text=True,
        capture_output=True,
    )
    if login.returncode:
        raise RuntimeError(f"Registry login failed with exit code {login.returncode}.")
    try:
        subprocess.run(["docker", "push", image], check=True)
    finally:
        subprocess.run(["docker", "logout", args.registry], check=True)
    immutable = subprocess.check_output(
        ["docker", "image", "inspect", image, "--format", "{{index .RepoDigests 0}}"],
        text=True,
    ).strip()
    if "@sha256:" not in immutable:
        raise ValueError("Published serving image has no immutable digest.")
    proof.update({"base_image": digest, "image": immutable})
    (args.output / "image-proof.json").write_text(json.dumps(proof, indent=2))
    print(json.dumps({"image": immutable, "git_sha": args.git_sha}, indent=2))


if __name__ == "__main__":
    main()
