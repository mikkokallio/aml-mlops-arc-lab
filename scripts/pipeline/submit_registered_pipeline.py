"""Submit the proven synthetic pipeline through ARM, without blob or MLflow access."""

import argparse
import copy
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

API_VERSION = "2024-10-01"
BASELINE_JOB = "sincere_potato_q841s2zp8c"
COMPONENT_SOURCE_SHA = "f563c2fca1d62a6f9a4d209ca5be44d70b65de83"
NODES = {"snapshot", "validate", "train", "evaluate", "register"}
TERMINAL = {"Completed", "Failed", "Canceled", "NotResponding"}


class SubmissionError(RuntimeError):
    """An error whose message is safe for the public workflow log."""


class ArmClient:
    def request(self, method: str, resource_id: str, body: Path | None = None):
        command = [
            "az", "rest", "--method", method,
            "--url", f"https://management.azure.com{resource_id}?api-version={API_VERSION}",
            "--output", "json", "--only-show-errors",
        ]
        if body is not None:
            command.extend(["--body", "@" + str(body)])
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise SubmissionError("ARM CLI request could not complete; details suppressed.") from error
        if result.returncode:
            raise SubmissionError(f"ARM {method} failed; identifiers and response details suppressed.")
        try:
            return json.loads(result.stdout) if result.stdout.strip() else None
        except json.JSONDecodeError as error:
            raise SubmissionError("ARM returned an invalid JSON response; details suppressed.") from error


def github_context(environ) -> dict:
    if (
        environ.get("GITHUB_ACTIONS") != "true"
        or environ.get("GITHUB_REF") != "refs/heads/main"
        or environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
    ):
        raise SubmissionError("Only a manual GitHub Actions dispatch on main may submit training.")
    context = {
        "orchestrator_sha": environ.get("GITHUB_SHA", ""),
        "run_id": environ.get("GITHUB_RUN_ID", ""),
        "attempt": environ.get("GITHUB_RUN_ATTEMPT", ""),
        "repository": environ.get("GITHUB_REPOSITORY", ""),
    }
    if (
        not re.fullmatch(r"[0-9a-f]{40}", context["orchestrator_sha"])
        or not re.fullmatch(r"[0-9]+", context["run_id"])
        or not re.fullmatch(r"[0-9]+", context["attempt"])
        or not re.fullmatch(r"[\w.-]+/[\w.-]+", context["repository"])
    ):
        raise SubmissionError("Missing or invalid GitHub execution metadata.")
    return context


def workspace_id(value: str) -> str:
    value = value.rstrip("/")
    if not re.fullmatch(
        r"/subscriptions/[0-9a-f-]{36}/resourceGroups/[\w.-]+/providers/"
        r"Microsoft\.MachineLearningServices/workspaces/[\w-]+",
        value, re.IGNORECASE,
    ):
        raise SubmissionError("Invalid workspace resource ID; value suppressed.")
    return value


def registered_id(value, workspace: str, collection: str) -> str:
    if isinstance(value, str):
        value = value.removeprefix("azureml:")
    if not isinstance(value, str) or not re.fullmatch(
        re.escape(workspace) + "/" + collection + r"/[^/:]+/versions/[^/:]+",
        value, re.IGNORECASE,
    ) or value.lower().endswith("/latest"):
        raise SubmissionError(f"Expected an exact registered {collection} version in this workspace.")
    return value


def prepare_request(baseline: dict, workspace: str, context: dict) -> dict:
    properties = baseline["properties"]
    if (
        properties["jobType"] != "Pipeline" or properties["status"] != "Completed"
        or properties["tags"].get("source_sha") != COMPONENT_SOURCE_SHA
        or properties["inputs"]["git_sha"]["value"] != COMPONENT_SOURCE_SHA
        or set(properties["jobs"]) != NODES
    ):
        raise SubmissionError("Baseline is not the successful, pinned five-component source.")
    compute = properties["settings"]["default_compute"]
    if not isinstance(compute, str) or not compute.lower().startswith(workspace.lower() + "/computes/"):
        raise SubmissionError("Baseline compute is not in the expected workspace.")
    nodes = {}
    allowed = {
        "_source", "name", "type", "componentId", "environment_variables",
        "identity", "inputs", "outputs",
    }
    for name, node in properties["jobs"].items():
        if (
            set(node) - allowed or node["type"] != "command"
            or node["identity"] != {"identity_type": "Managed"}
            or set(node["environment_variables"]) != {"LAB_GIT_SHA", "MLFLOW_TRACKING_URI"}
            or node["environment_variables"]["LAB_GIT_SHA"] != COMPONENT_SOURCE_SHA
        ):
            raise SubmissionError("Baseline contains an unexpected inline node or runtime identity.")
        registered_id(node["componentId"], workspace, "components")
        nodes[name] = {
            key: copy.deepcopy(node[key])
            for key in ("type", "componentId", "environment_variables", "identity", "inputs", "outputs")
        }
    inputs = copy.deepcopy(properties["inputs"])
    inputs["source_data"] = {
        "jobInputType": "uri_folder", "mode": "ReadOnlyMount",
        "uri": workspace + "/data/campaign-synthetic/versions/2",
    }
    for key, value in {
        "data_version": "azureml:campaign-synthetic:2",
        "git_sha": COMPONENT_SOURCE_SHA,
        "model_name": "campaign-m3-synthetic-proof",
        "champion_uri": "models:/campaign-m3-synthetic-proof/2",
        "champion_deployment": "synthetic-fixture-not-a-serving-deployment",
    }.items():
        inputs[key] = {"jobInputType": "literal", "value": value}
    return {"properties": {
        "jobType": "Pipeline",
        "displayName": "GitHub reference-only synthetic training",
        "description": "Synthetic comparison fixture; not Fabric or deployed-champion proof.",
        "experimentName": properties["experimentName"],
        "jobs": nodes, "inputs": inputs,
        "outputs": {
            key: {"jobOutputType": "uri_folder", "mode": "ReadWriteMount"}
            for key in ("decision", "registration")
        },
        "settings": {
            "default_compute": compute, "continue_on_step_failure": False, "force_rerun": True,
        },
        "tags": {
            "source_sha": COMPONENT_SOURCE_SHA, "component_source_sha": COMPONENT_SOURCE_SHA,
            "orchestrator_sha": context["orchestrator_sha"],
            "github_run_id": context["run_id"], "github_run_attempt": context["attempt"],
            "github_repository": context["repository"],
            "proof_kind": "github-reference-only-synthetic-not-deployed-champion",
        },
    }}


def verify_dependencies(client, request: dict, workspace: str) -> None:
    code_ids = set()
    for node in request["properties"]["jobs"].values():
        component = client.request("GET", node["componentId"])["properties"]["componentSpec"]
        if (
            component["type"] != "command"
            or component["environment"].removeprefix("azureml:").lower()
            != (workspace + "/environments/campaign-training/versions/2").lower()
        ):
            raise SubmissionError("A registered component does not use the pinned environment v2.")
        code_ids.add(registered_id(component["code"], workspace, "codes"))
    if len(code_ids) != 1:
        raise SubmissionError("Registered components do not share the proven immutable code asset.")
    for collection, name, version in (
        ("data", "campaign-synthetic", "2"), ("models", "campaign-m3-synthetic-proof", "2"),
    ):
        properties = client.request("GET", f"{workspace}/{collection}/{name}/versions/{version}")["properties"]
        tags = properties.get("tags", {})
        source_tag = "source_sha" if collection == "data" else "git_sha"
        if tags.get(source_tag) != COMPONENT_SOURCE_SHA:
            raise SubmissionError(f"Registered {collection} provenance does not match the pinned source.")
        if collection == "models" and tags.get("data_asset_version") != "azureml:campaign-synthetic:2":
            raise SubmissionError("The synthetic reference model was not trained on data version 2.")


def execute(client, workspace: str, context: dict, state_dir: Path,
            timeout_seconds: int, poll_seconds: int, clock=time.monotonic, sleep=time.sleep) -> dict:
    deadline = clock() + timeout_seconds
    baseline = client.request("GET", f"{workspace}/jobs/{BASELINE_JOB}")
    request = prepare_request(baseline, workspace, context)
    verify_dependencies(client, request, workspace)
    state_dir.mkdir(parents=True, exist_ok=True)
    body = state_dir / "request.json"
    body.write_text(json.dumps(request), encoding="utf-8")
    body.chmod(0o600)
    name = f"gha-registered-{context['run_id']}-{context['attempt']}"
    resource = workspace + "/jobs/" + name
    terminal = False
    attempted = False
    try:
        if clock() >= deadline:
            raise SubmissionError("Preflight exceeded the execution deadline; no job submitted.")
        attempted = True
        client.request("PUT", resource, body)
        print(f"AML_JOB_NAME={name}", flush=True)
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with Path(output).open("a", encoding="utf-8") as stream:
                stream.write(f"aml_job_name={name}\n")
        while clock() < deadline:
            job = client.request("GET", resource)["properties"]
            status = job["status"]
            if not isinstance(status, str) or not re.fullmatch(r"[A-Za-z]+", status):
                raise SubmissionError("Invalid ARM job status; response suppressed.")
            print(f"AML_JOB_STATUS={status}", flush=True)
            if status in TERMINAL:
                terminal = True
                if status != "Completed":
                    raise SubmissionError(f"Managed training pipeline ended with status {status}.")
                if (
                    job["tags"].get("component_source_sha") != COMPONENT_SOURCE_SHA
                    or job["tags"].get("orchestrator_sha") != context["orchestrator_sha"]
                    or job["inputs"]["data_version"]["value"] != "azureml:campaign-synthetic:2"
                    or job["inputs"]["git_sha"]["value"] != COMPONENT_SOURCE_SHA
                    or job["inputs"]["champion_uri"]["value"] != "models:/campaign-m3-synthetic-proof/2"
                    or job["inputs"]["source_data"]["uri"].removeprefix("azureml:").lower()
                    != (workspace + "/data/campaign-synthetic/versions/2").lower()
                    or job["settings"].get("force_rerun") is not True
                    or any(
                        job["jobs"][name]["componentId"] != node["componentId"]
                        or job["jobs"][name]["identity"] != node["identity"]
                        for name, node in request["properties"]["jobs"].items()
                    )
                ):
                    raise SubmissionError("Completed job provenance does not match this dispatch.")
                return {
                    "aml_job_name": name, "status": status, "force_rerun": True,
                    "component_source_sha": COMPONENT_SOURCE_SHA,
                    "orchestrator_sha": context["orchestrator_sha"],
                    "data_asset_version": "azureml:campaign-synthetic:2",
                    "reference_model": "models:/campaign-m3-synthetic-proof/2",
                    "classification": "Synthetic fixture only; not Fabric or deployed-champion proof.",
                    "gate_outcome": "Not read from private artifacts; Completed permits normal NOT_REGISTERED.",
                }
            sleep(min(poll_seconds, max(0, deadline - clock())))
        raise SubmissionError("Training deadline exceeded; requesting ARM cancellation.")
    finally:
        if attempted and not terminal:
            try:
                client.request("POST", resource + "/cancel")
                print("ARM_CANCELLATION_REQUESTED", flush=True)
            except Exception:
                print("::warning::ARM cancellation could not be confirmed; inspect the named job.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path, default=Path(".local/registered-pipeline"))
    parser.add_argument("--timeout-seconds", type=int, default=1680)
    parser.add_argument("--poll-seconds", type=int, default=20)
    args = parser.parse_args()
    try:
        if not 1 <= args.timeout_seconds <= 1680 or not 1 <= args.poll_seconds <= 60:
            raise SubmissionError("Timeout or polling interval is outside the bounded execution policy.")
        context = github_context(os.environ)
        workspace = workspace_id(os.environ.get("AML_WORKSPACE_RESOURCE_ID", ""))
        summary = execute(ArmClient(), workspace, context, args.state_dir,
                          args.timeout_seconds, args.poll_seconds)
        text = json.dumps(summary, sort_keys=True)
        print(text)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as stream:
                stream.write("Reference-only managed training\n\n```json\n" + text + "\n```\n")
        return 0
    except SubmissionError as error:
        print(f"::error::{error}", file=sys.stderr)
    except KeyboardInterrupt:
        print("::error::Orchestration interrupted; active-job cancellation is best effort.", file=sys.stderr)
    except Exception:
        print("::error::Training orchestration failed; private response details suppressed.", file=sys.stderr)
    return 1


def interrupt_handler(_signal, _frame) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt_handler)
    raise SystemExit(main())
