"""Verify real private REST scoring and managed endpoint release operations."""

import argparse
import ipaddress
import json
from pathlib import Path
import socket
import time
from urllib.parse import urlparse

from azure.ai.ml import MLClient
from azure.ai.ml.entities import Model
from azure.identity import ManagedIdentityCredential
import requests

from scripts.compare_predictions import compare_predictions


def verify_private_uri(uri: str) -> None:
    parsed = urlparse(uri)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Managed scoring requires a reported HTTPS URI.")
    addresses = {
        row[4][0]
        for row in socket.getaddrinfo(parsed.hostname, 443, family=socket.AF_INET)
    }
    if not addresses or not all(ipaddress.ip_address(value).is_private for value in addresses):
        raise ValueError(f"Managed scoring must resolve privately: {sorted(addresses)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--step", choices=("blue", "green", "rollback", "rotation", "logs"), required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    client = MLClient(
        ManagedIdentityCredential(client_id=args.client_id),
        args.subscription,
        args.resource_group,
        args.workspace,
    )
    endpoint = client.online_endpoints.get(args.endpoint)
    if str(endpoint.public_network_access).lower() != "disabled":
        raise ValueError("Endpoint inbound public access is not disabled.")
    verify_private_uri(endpoint.scoring_uri)
    proof: dict[str, object] = {"endpoint": endpoint.name, "step": args.step}
    primary = client.online_endpoints.get_keys(args.endpoint).primary_key

    def score(key: str, version: str, deployment: str | None = None) -> dict:
        headers = {"Authorization": f"Bearer {key}"}
        if deployment:
            headers["azureml-model-deployment"] = deployment
        response = requests.post(
            endpoint.scoring_uri,
            headers=headers,
            json=json.loads((args.reference / f"request-{version}.json").read_text()),
            timeout=60,
        )
        response.raise_for_status()
        return compare_predictions(
            json.loads((args.reference / f"reference-{version}.json").read_text()),
            response.json(),
        )

    def check_deployment(name: str, version: str) -> dict:
        deployment = client.online_deployments.get(name, args.endpoint)
        expected = (
            f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}"
            f"/providers/Microsoft.MachineLearningServices/workspaces/{args.workspace}"
            f"/models/campaign-m3-synthetic-proof/versions/{version}"
        )
        model = deployment.model.id if isinstance(deployment.model, Model) else deployment.model
        if model not in (expected, f"azureml:{expected}"):
            raise ValueError(f"Deployment {name} has unexpected model ID: {model}")
        if str(deployment.egress_public_network_access).lower() != "disabled":
            raise ValueError("Deployment public egress is not disabled.")
        return {"model_id": model, "direct_rest": score(primary, version, name)}

    if args.step in ("blue", "green", "rollback"):
        target, version = ("green", "2") if args.step == "green" else ("blue", "1")
        proof["target"] = check_deployment(target, version)
        if args.step in ("green", "rollback"):
            proof["other"] = check_deployment(
                "blue" if target == "green" else "green",
                "1" if target == "green" else "2",
            )
        endpoint.traffic = {target: 100}
        client.online_endpoints.begin_create_or_update(endpoint).result(timeout=600)
        actual = client.online_endpoints.get(args.endpoint)
        if {key: value for key, value in actual.traffic.items() if value} != {target: 100}:
            raise ValueError(f"Unexpected routed traffic: {actual.traffic}")
        proof["traffic"] = actual.traffic
        proof["routed_rest"] = score(primary, version)
    elif args.step == "rotation":
        keys = client.online_endpoints.get_keys(args.endpoint)
        proof["old_primary_before"] = score(keys.primary_key, "1")
        proof["secondary_before"] = score(keys.secondary_key, "1")
        client.online_endpoints.begin_regenerate_keys(
            args.endpoint, key_type="primary"
        ).result(timeout=600)
        refreshed = client.online_endpoints.get_keys(args.endpoint)
        if refreshed.primary_key == keys.primary_key:
            raise ValueError("Primary key did not rotate.")
        if refreshed.secondary_key != keys.secondary_key:
            raise ValueError("Primary rotation unexpectedly changed the secondary key.")
        proof["secondary_after"] = score(keys.secondary_key, "1")
        proof["new_primary_after"] = score(refreshed.primary_key, "1")
        deadline = time.monotonic() + 120
        while True:
            stale = requests.post(
                endpoint.scoring_uri,
                headers={"Authorization": f"Bearer {keys.primary_key}"},
                json=json.loads((args.reference / "request-1.json").read_text()),
                timeout=60,
            )
            if stale.status_code == 401:
                proof["stale_primary_http_status"] = 401
                break
            if stale.status_code != 200 or time.monotonic() >= deadline:
                raise ValueError(f"Rotated-out key was not rejected: HTTP {stale.status_code}")
            time.sleep(10)
    else:
        logs = {}
        readiness = {}
        for name in ("blue", "green"):
            text = client.online_deployments.get_logs(name, args.endpoint, lines=500)
            (args.output / f"{name}.container.log").write_text(text)
            logs[name] = len(text.splitlines())
            events = []
            for line in text.splitlines():
                start = line.find('{"event":')
                if start >= 0:
                    event = json.loads(line[start:])
                    if event.get("event") == "serving_ready":
                        events.append(event)
            readiness[name] = events
        proof["container_log_lines"] = logs
        proof["readiness_events"] = readiness
    (args.output / f"{args.step}.proof.json").write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
