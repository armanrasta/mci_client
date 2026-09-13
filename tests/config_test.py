import pytest
from pydantic import ValidationError

from mci_client.config import ClusterConfig


def test_parse_hosts_from_string(monkeypatch):
    monkeypatch.setenv("MCI_HOSTS", "http://a,http://b,http://c")
    cfg = ClusterConfig() # type: ignore
    assert cfg.hosts == ["http://a", "http://b", "http://c"]


def test_parse_hosts_strips_whitespace(monkeypatch):
    monkeypatch.setenv("MCI_HOSTS", " http://a , http://b ")
    cfg = ClusterConfig() # type: ignore
    assert cfg.hosts == ["http://a", "http://b"]


def test_parse_hosts_rejects_empty(monkeypatch):
    monkeypatch.setenv("MCI_HOSTS", "   ")
    with pytest.raises(ValidationError):
        ClusterConfig() # type: ignore


def test_validate_hosts_rejects_invalid_url(monkeypatch):
    monkeypatch.setenv("MCI_HOSTS", "not-a-url")
    with pytest.raises(ValidationError):
        ClusterConfig() # type: ignore