import pytest

from scripts.check_managed_serving import verify_private_uri


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
