import copy
import json
import subprocess
from types import SimpleNamespace

import pytest

from scripts.pipeline import submit_registered_pipeline as submit


WORKSPACE = (
    "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/test-rg/"
    "providers/Microsoft.MachineLearningServices/workspaces/test-workspace"
)
CONTEXT = {"orchestrator_sha": "a" * 40, "run_id": "123", "attempt": "1", "repository": "test/repo"}


def baseline():
    return {"properties": {
        "jobType": "Pipeline", "status": "Completed",
        "tags": {"source_sha": submit.COMPONENT_SOURCE_SHA},
        "experimentName": "synthetic-contract",
        "settings": {"default_compute": WORKSPACE + "/computes/test-compute"},
        "inputs": {"git_sha": {"jobInputType": "literal", "value": submit.COMPONENT_SOURCE_SHA}},
        "jobs": {
            name: {
                "type": "command",
                "componentId": WORKSPACE + f"/components/{name}/versions/1",
                "identity": {"identity_type": "Managed"},
                "environment_variables": {
                    "LAB_GIT_SHA": submit.COMPONENT_SOURCE_SHA,
                    "MLFLOW_TRACKING_URI": "azureml://private-tracking",
                },
                "inputs": {"data": {"job_input_type": "literal", "value": "${{parent.inputs.source_data}}"}},
                "outputs": {"output": {"job_output_type": "uri_folder", "mode": "ReadWriteMount"}},
            } for name in submit.NODES
        },
    }}


class FakeArm:
    def __init__(self, complete=True, final_status="Completed"):
        self.complete = complete
        self.final_status = final_status
        self.calls = []
        self.payload = None

    def request(self, method, resource, body=None):
        self.calls.append((method, resource))
        if resource.endswith("/jobs/" + submit.BASELINE_JOB):
            return baseline()
        if "/components/" in resource:
            return {"properties": {"componentSpec": {
                "type": "command",
                "environment": "azureml:" + WORKSPACE + "/environments/campaign-training/versions/2",
                "code": "azureml:" + WORKSPACE + "/codes/shared-source/versions/1",
            }}}
        if "/data/" in resource:
            return {"properties": {"tags": {"source_sha": submit.COMPONENT_SOURCE_SHA}}}
        if "/models/" in resource:
            return {"properties": {"tags": {
                "git_sha": submit.COMPONENT_SOURCE_SHA,
                "data_asset_version": "azureml:campaign-synthetic:2",
            }}}
        if method == "PUT":
            self.payload = json.loads(body.read_text())
            return {}
        if method == "POST":
            return None
        properties = copy.deepcopy(self.payload["properties"])
        properties["status"] = self.final_status if self.complete else "Running"
        return {"properties": properties}


def test_reference_only_submission_runs_arm_and_keeps_source_provenance_separate(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    client = FakeArm()
    result = submit.execute(client, WORKSPACE, CONTEXT, tmp_path, 60, 1)
    properties = client.payload["properties"]
    assert result["status"] == "Completed"
    assert properties["settings"]["force_rerun"] is True
    assert properties["inputs"]["source_data"]["uri"] == WORKSPACE + "/data/campaign-synthetic/versions/2"
    assert properties["inputs"]["data_version"]["value"] == "azureml:campaign-synthetic:2"
    assert properties["inputs"]["champion_uri"]["value"] == "models:/campaign-m3-synthetic-proof/2"
    assert properties["inputs"]["git_sha"]["value"] == submit.COMPONENT_SOURCE_SHA
    assert properties["tags"]["orchestrator_sha"] == CONTEXT["orchestrator_sha"]
    assert properties["tags"]["component_source_sha"] != CONTEXT["orchestrator_sha"]
    assert all(set(node) == {
        "type", "componentId", "identity", "environment_variables", "inputs", "outputs"
    } for node in properties["jobs"].values())
    assert [method for method, _ in client.calls].count("PUT") == 1
    assert not any(method == "POST" for method, _ in client.calls)


@pytest.mark.parametrize("invalid", ["local-code", "wrong-source", "different-workspace"])
def test_invalid_baseline_never_becomes_an_upload_or_submission(invalid):
    value = baseline()
    if invalid == "local-code":
        value["properties"]["jobs"]["train"]["code"] = "."
    elif invalid == "wrong-source":
        value["properties"]["tags"]["source_sha"] = "b" * 40
    else:
        value["properties"]["jobs"]["train"]["componentId"] = "/another-workspace/components/train/versions/1"
    with pytest.raises(submit.SubmissionError):
        submit.prepare_request(value, WORKSPACE, CONTEXT)


def test_timeout_requests_arm_cancellation_instead_of_green_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    client = FakeArm(complete=False)
    now = [0]
    with pytest.raises(submit.SubmissionError, match="deadline exceeded"):
        submit.execute(client, WORKSPACE, CONTEXT, tmp_path, 2, 1,
                       clock=lambda: now[0], sleep=lambda duration: now.__setitem__(0, now[0] + duration))
    assert client.calls[-1] == ("POST", WORKSPACE + "/jobs/gha-registered-123-1/cancel")


def test_failed_managed_execution_is_not_reported_as_success(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    client = FakeArm(final_status="Failed")
    with pytest.raises(submit.SubmissionError, match="ended with status Failed"):
        submit.execute(client, WORKSPACE, CONTEXT, tmp_path, 60, 1)
    assert not any(method == "POST" for method, _ in client.calls)


def test_wrong_registered_environment_fails_before_job_submission(tmp_path):
    class WrongEnvironment(FakeArm):
        def request(self, method, resource, body=None):
            result = super().request(method, resource, body)
            if "/components/" in resource:
                result["properties"]["componentSpec"]["environment"] = (
                    "azureml:" + WORKSPACE + "/environments/campaign-training/versions/1"
                )
            return result

    client = WrongEnvironment()
    with pytest.raises(submit.SubmissionError, match="pinned environment v2"):
        submit.execute(client, WORKSPACE, CONTEXT, tmp_path, 60, 1)
    assert not any(method == "PUT" for method, _ in client.calls)


def test_non_main_dispatch_and_private_arm_errors_are_rejected_without_leaking(capsys, monkeypatch):
    with pytest.raises(submit.SubmissionError, match="manual.*main"):
        submit.github_context({
            "GITHUB_ACTIONS": "true", "GITHUB_REF": "refs/heads/feature",
            "GITHUB_EVENT_NAME": "workflow_dispatch",
        })
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stdout="", stderr="PRIVATE-WORKSPACE-ID AND RAW-TOKEN"
    ))
    with pytest.raises(submit.SubmissionError) as error:
        submit.ArmClient().request("GET", WORKSPACE)
    assert "PRIVATE-WORKSPACE" not in str(error.value)
    assert not capsys.readouterr().out
