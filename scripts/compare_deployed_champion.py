"""Compare the registered candidate with the actual live champion on data 2."""

import argparse
import hashlib
import io
import json
from pathlib import Path

from azure.ai.ml import MLClient
from azure.ai.ml.entities import Model
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import ContainerClient
import mlflow
import numpy as np
import pandas as pd
import requests
import yaml

from scripts.check_managed_serving import verify_private_uri
from scripts.pipeline.steps import decide, digest
from src.train import regression_metrics, selected_features, split_campaigns


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--image-proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    credential = ManagedIdentityCredential(client_id=args.client_id)
    client = MLClient(credential, args.subscription, "rg-amlarclab-ml", "mlw-amlarclab")
    endpoint = client.online_endpoints.get("amlarclab-managed-1123")
    traffic = {name: weight for name, weight in endpoint.traffic.items() if weight}
    if traffic != {"blue": 100}:
        raise ValueError(f"Expected a single live blue champion, got {traffic}")
    verify_private_uri(endpoint.scoring_uri)
    champion = client.online_deployments.get("blue", endpoint.name)
    champion_id = champion.model.id if isinstance(champion.model, Model) else champion.model
    expected = f"/subscriptions/{args.subscription}/resourceGroups/rg-amlarclab-ml/providers/Microsoft.MachineLearningServices/workspaces/mlw-amlarclab/models/campaign-m3-synthetic-proof/versions/1"
    if champion_id not in (expected, f"azureml:{expected}"):
        raise ValueError(f"Unexpected live champion model: {champion_id}")
    asset = client.data.get("campaign-synthetic", "2")
    if "/datastores/" not in asset.path or "/paths/" not in asset.path:
        raise ValueError("Expected a versioned datastore-backed folder.")
    datastore_name = asset.path.split("/datastores/", 1)[1].split("/", 1)[0]
    prefix = asset.path.split("/paths/", 1)[1].rstrip("/") + "/"
    store = client.datastores.get(datastore_name)
    container = ContainerClient(
        f"https://{store.account_name}.blob.core.windows.net",
        store.container_name,
        credential,
    )
    content = container.download_blob(prefix + "data.csv").readall()
    snapshot_sha = hashlib.sha256(content).hexdigest()
    if snapshot_sha != asset.tags["content_sha256"]:
        raise ValueError("Actual data bytes differ from registered snapshot hash.")
    _, holdout = split_campaigns(pd.read_csv(io.BytesIO(content)))
    contract = Path("config/features.yaml")
    policy_path = Path("config/components/promotion-policy.yml")
    if digest(policy_path) != "fef11171cbe85db4b04d5574ce5631036a0cc40390c9108b227ac1d24d59f075":
        raise ValueError("The evaluation policy differs from the accepted unchanged policy.")
    features = selected_features(contract)
    candidate_asset = client.models.get("campaign-m3-synthetic-proof", "2")
    image_proof = json.loads(args.image_proof.read_text())
    candidate_proof = image_proof["models"]["2"]
    actual_files = {
        str(path.relative_to(args.candidate)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in args.candidate.rglob("*")
        if path.is_file()
    }
    if (
        candidate_proof["asset_id"].casefold() != candidate_asset.id.casefold()
        or actual_files != candidate_proof["files_sha256"]
    ):
        raise ValueError("Candidate files do not match the registered-model build proof.")
    candidate = mlflow.pyfunc.load_model(str(args.candidate))
    candidate_predictions = candidate.predict(holdout[features])
    key = client.online_endpoints.get_keys(endpoint.name).primary_key
    predictions: list[float] = []
    with requests.Session() as session:
        for offset in range(0, len(holdout), 500):
            batch = holdout[features].iloc[offset:offset + 500]
            response = session.post(
                endpoint.scoring_uri,
                headers={"Authorization": f"Bearer {key}"},
                json={"input_data": batch.to_dict(orient="split")},
                timeout=60,
            )
            response.raise_for_status()
            values = response.json()
            if (
                not isinstance(values, list)
                or len(values) != len(batch)
                or any(not isinstance(value, (int, float)) or isinstance(value, bool) for value in values)
                or not np.isfinite(values).all()
            ):
                raise ValueError("Live champion returned an invalid prediction batch.")
            predictions.extend(values)
    after = client.online_endpoints.get(endpoint.name)
    if {name: weight for name, weight in after.traffic.items() if weight} != traffic:
        raise ValueError("Champion traffic changed during evaluation.")
    after_deployment = client.online_deployments.get("blue", endpoint.name)
    after_id = after_deployment.model.id if isinstance(after_deployment.model, Model) else after_deployment.model
    if after_id != champion_id:
        raise ValueError("Champion model changed during evaluation.")
    decision = decide(
        {
            "candidate": regression_metrics(holdout, candidate_predictions),
            "reference": regression_metrics(holdout, np.asarray(predictions)),
        },
        yaml.safe_load(policy_path.read_text()),
        "azureml:campaign-synthetic:2",
        snapshot_sha256=snapshot_sha,
        policy_sha256=digest(policy_path),
        reference_model=champion_id,
        champion_deployment=f"{endpoint.id}/deployments/blue",
        reference_kind="live-private-rest-100-percent-traffic",
        candidate_model="azureml:campaign-m3-synthetic-proof:2",
        holdout_rows=len(holdout),
        holdout_campaigns=sorted(holdout["campaign_id"].unique().tolist()),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(decision, indent=2, allow_nan=False))
    print(json.dumps({key: value for key, value in decision.items() if key != "holdout_campaigns"}, indent=2))


if __name__ == "__main__":
    main()
