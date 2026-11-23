"""Score the reported private Arc URI, using a key published through Key Vault."""

import ipaddress
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from azure.ai.ml import MLClient
from azure.ai.ml.entities import Model
from azure.identity import ManagedIdentityCredential

from compare_predictions import compare_predictions


def main() -> None:
    output = Path("/var/lib/aml-arc-lab/training/latest-output").resolve(strict=True)
    trained = json.loads((output / "result.json").read_text())
    credential = ManagedIdentityCredential(client_id=os.environ["LAB_DS_CLIENT_ID"])
    client = MLClient(
        credential, os.environ["LAB_SUBSCRIPTION"], "rg-amlarclab-ml", "mlw-amlarclab"
    )
    endpoint = client.online_endpoints.get("campaign-arc")
    if endpoint.traffic != {"blue": 100}:
        raise ValueError(f"Unexpected endpoint traffic: {endpoint.traffic}")
    deployment = client.online_deployments.get("blue", "campaign-arc")
    model_id = deployment.model.id if isinstance(deployment.model, Model) else deployment.model
    expected_id = (
        os.environ["LAB_WORKSPACE_ID"]
        + f'/models/{trained["model_name"]}/versions/{trained["model_version"]}'
    )
    if model_id not in (expected_id, "azureml:" + expected_id):
        raise ValueError(f"Deployed model does not match the reference model: {model_id}")
    uri = endpoint.scoring_uri
    parsed = urlparse(uri)
    if parsed.scheme != "http" or not ipaddress.ip_address(parsed.hostname).is_private:
        raise ValueError("Lab HTTP scoring must use the reported private IP, never a public route.")

    secret_uri = f'https://{os.environ["LAB_VAULT_HOST"]}/secrets/campaign-arc-primary?api-version=7.4'
    keys = client.online_endpoints.get_keys("campaign-arc")
    published = requests.put(
        secret_uri,
        headers={"Authorization": "Bearer " + credential.get_token("https://vault.azure.net/.default").token},
        json={"value": keys.primary_key},
        timeout=30,
    )
    published.raise_for_status()
    consumer = ManagedIdentityCredential(client_id=os.environ["LAB_COMPUTE_CLIENT_ID"])
    retrieved = requests.get(
        secret_uri,
        headers={"Authorization": "Bearer " + consumer.get_token("https://vault.azure.net/.default").token},
        timeout=30,
    )
    retrieved.raise_for_status()
    response = requests.post(
        uri,
        headers={"Authorization": "Bearer " + retrieved.json()["value"]},
        json=json.loads((output / "request.json").read_text()),
        timeout=60,
    )
    response.raise_for_status()
    actual = response.json()
    (output / "response.json").write_text(json.dumps(actual, allow_nan=False))
    result = compare_predictions(json.loads((output / "reference.json").read_text()), actual)
    result.update(
        {
            "endpoint": endpoint.name,
            "deployment": deployment.name,
            "model_id": model_id,
            "scoring_uri": uri,
            "run_id": trained["run_id"],
            "reference_predictor": trained["reference_predictor"],
            "key_path": "endpoint get-credentials -> Key Vault -> consumer managed identity",
        }
    )
    (output / "scoring-result.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
