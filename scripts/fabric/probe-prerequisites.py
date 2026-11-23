"""Read-only, bounded metadata probes using the VM's P-CI managed identity."""

import collections
import datetime
import json
import os
import pathlib
import subprocess
import urllib.error
import urllib.request


root = pathlib.Path(os.environ["LAB_FABRIC_EVIDENCE"])
root.mkdir(parents=True, exist_ok=True)
results = []


def probe(name, url, resource, method="GET"):
    entry = {"probe": name, "method": method}
    token_result = subprocess.run(
        [
            "az", "account", "get-access-token", "--resource", resource,
            "--query", "accessToken", "--output", "tsv",
        ],
        capture_output=True, text=True, timeout=70, check=False,
    )
    if token_result.returncode:
        (root / f"{name}.token-error.txt").write_text(token_result.stderr)
        entry.update(stage="token", error=token_result.stderr.strip())
        results.append(entry)
        return
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token_result.stdout.strip(),
            "x-ms-version": "2021-06-08",
        },
        method=method,
    )
    try:
        response = urllib.request.urlopen(request, timeout=40)
    except urllib.error.HTTPError as error:
        response = error
    except (urllib.error.URLError, TimeoutError) as error:
        entry.update(stage="transport", error=str(error))
        results.append(entry)
        return
    with response:
        body = response.read().decode("utf-8", errors="replace")
        status = response.status
        headers = dict(response.headers)
    (root / f"{name}.json").write_text(
        json.dumps({"status": status, "headers": headers, "body": body})
    )
    entry.update(status=status, errorCode=headers.get("x-ms-error-code"))
    if 200 <= status < 300 and body:
        payload = json.loads(body)
        items = payload.get("value", [])
        entry["count"] = len(items)
        entry["hasMore"] = bool(
            payload.get("nextLink") or payload.get("continuationToken")
        )
        if name == "ci-fabric-capacities":
            entry["skuCounts"] = dict(collections.Counter(x.get("sku") for x in items))
        if name == "ci-fabric-workspaces":
            entry["typeCounts"] = dict(collections.Counter(x.get("type") for x in items))
    elif status >= 400:
        try:
            payload = json.loads(body)
            error = payload.get("error", payload)
            entry["errorCode"] = error.get("errorCode", error.get("code"))
            entry["message"] = error.get("message")
        except ValueError:
            entry["message"] = body[:1200]
    results.append(entry)


subscription = os.environ["LAB_SUBSCRIPTION"]
probe(
    "ci-arm-capacities",
    f"https://management.azure.com/subscriptions/{subscription}/providers/"
    "Microsoft.Fabric/capacities?api-version=2023-11-01",
    "https://management.azure.com/",
)
probe(
    "ci-fabric-capacities", "https://api.fabric.microsoft.com/v1/capacities",
    "https://api.fabric.microsoft.com",
)
probe(
    "ci-fabric-workspaces", "https://api.fabric.microsoft.com/v1/workspaces",
    "https://api.fabric.microsoft.com",
)
probe(
    "ci-onelake-account-head", "https://onelake.dfs.fabric.microsoft.com/",
    "https://storage.azure.com/", method="HEAD",
)
report = {
    "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "identity": "P-CI managed identity",
    "scope": "metadata only; OneLake account HEAD; no existing workspace items accessed",
    "results": results,
}
(root / "summary.json").write_text(json.dumps(report, indent=2))
print("FABRIC_PROBE_JSON=" + json.dumps(report, separators=(",", ":")))
