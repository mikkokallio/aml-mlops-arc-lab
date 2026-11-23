"""Verify private REST scoring by the same immutable model on portable targets."""

import argparse
import ipaddress
import json
from pathlib import Path
import socket
import subprocess
from urllib.parse import urlsplit

from scripts.compare_predictions import compare_predictions


def check_private_url(url: str, resolve_ip: str | None = None) -> list[str]:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use an HTTP(S) origin without credentials or a path.")
    addresses = (
        [resolve_ip]
        if resolve_ip
        else list({item[4][0] for item in socket.getaddrinfo(parsed.hostname, None)})
    )
    if not addresses or any(
        not ipaddress.ip_address(address).is_private
        or ipaddress.ip_address(address).is_loopback
        or ipaddress.ip_address(address).is_link_local
        or ipaddress.ip_address(address).is_unspecified
        for address in addresses
    ):
        raise ValueError("All destination addresses must be private, non-loopback IPs.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    address = addresses[0]
    if ":" in address:
        address = f"[{address}]"
    return ["--resolve", f"{parsed.hostname}:{port}:{address}"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["vm", "aci", "aca"], required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--resolve-ip")
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--model-manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    resolve = check_private_url(args.url, args.resolve_ip)
    base = args.url.rstrip("/")
    command = [
        "curl", "--silent", "--show-error", "--fail-with-body", "--noproxy", "*",
        "--connect-timeout", "10", "--max-time", "90", *resolve,
    ]
    health = json.loads(
        subprocess.run(
            [*command, f"{base}/health"], check=True, capture_output=True, text=True
        ).stdout
    )
    if (
        health["status"] != "ready"
        or health["model_version"] != "2"
        or health["model_source"] != "bundled"
        or health["model_manifest"]["sha256"] != args.model_manifest_sha256
    ):
        raise AssertionError("Target readiness does not identify the expected bundled model.")
    response = subprocess.run(
        [
            *command, "--header", "Content-Type: application/json",
            "--data-binary", "@-", f"{base}/score",
        ],
        input=args.request.read_text(encoding="utf-8"),
        check=True,
        capture_output=True,
        text=True,
    )
    comparison = compare_predictions(
        json.loads(args.reference.read_text(encoding="utf-8")),
        json.loads(response.stdout),
    )
    proof = {
        "target": args.target,
        "url": args.url,
        "tls_verified": urlsplit(args.url).scheme == "https",
        "private_transport_only": True,
        "aml_managed_deployment": False,
        "health": health,
        "comparison": comparison,
    }
    args.output.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    print(json.dumps(proof, indent=2))


if __name__ == "__main__":
    main()
