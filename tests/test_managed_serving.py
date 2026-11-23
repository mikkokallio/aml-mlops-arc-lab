from types import SimpleNamespace

import pytest

from scripts.check_managed_serving import regenerate_primary, verify_private_uri


def test_managed_scoring_requires_exclusively_private_dns(monkeypatch):
    monkeypatch.setattr(
        "scripts.check_managed_serving.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("10.82.1.9", 443))],
    )
    verify_private_uri("https://lab.inference.ml.azure.com/score")
    monkeypatch.setattr(
        "scripts.check_managed_serving.socket.getaddrinfo",
        lambda *args, **kwargs: [
            (2, 1, 6, "", ("10.82.1.9", 443)),
            (2, 1, 6, "", ("20.1.2.3", 443)),
        ],
    )
    with pytest.raises(ValueError, match="resolve privately"):
        verify_private_uri("https://lab.inference.ml.azure.com/score")


def test_managed_scoring_rejects_plaintext_before_resolving():
    with pytest.raises(ValueError, match="HTTPS"):
        verify_private_uri("http://10.82.1.9/score")


def test_key_rotation_requires_real_stored_change_not_async_acceptance(monkeypatch):
    keys = SimpleNamespace(primary_key="old-test-key", secondary_key="secondary-test-key")
    client = SimpleNamespace(online_endpoints=SimpleNamespace(get_keys=lambda name: keys))
    credential = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="test-token"))
    monkeypatch.setattr(
        "scripts.check_managed_serving.requests.post",
        lambda *args, **kwargs: SimpleNamespace(raise_for_status=lambda: None),
    )
    clock = iter((0, 121))
    monkeypatch.setattr("scripts.check_managed_serving.time.monotonic", lambda: next(clock))
    with pytest.raises(TimeoutError, match="did not change"):
        regenerate_primary(client, credential, SimpleNamespace(name="lab", id="/lab"))


def test_key_rotation_rejects_unexpected_secondary_change(monkeypatch):
    states = iter(
        (
            SimpleNamespace(primary_key="old-test-key", secondary_key="secondary-test-key"),
            SimpleNamespace(primary_key="new-test-key", secondary_key="unexpected-test-key"),
        )
    )
    client = SimpleNamespace(online_endpoints=SimpleNamespace(get_keys=lambda name: next(states)))
    credential = SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="test-token"))
    monkeypatch.setattr(
        "scripts.check_managed_serving.requests.post",
        lambda *args, **kwargs: SimpleNamespace(raise_for_status=lambda: None),
    )
    with pytest.raises(ValueError, match="secondary key"):
        regenerate_primary(client, credential, SimpleNamespace(name="lab", id="/lab"))
