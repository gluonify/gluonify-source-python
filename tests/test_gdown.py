"""The ten lines that reach gDown: TLS only, the platform CA through TrustCustomCAs, plain Bolt for dev only."""

from __future__ import annotations

from typing import Any

import neo4j
import pytest

from gluonify_source.notes.gdown import gdown_driver

ENV = {"GLUONIFY_GDOWN_USER": "u", "GLUONIFY_GDOWN_PASSWORD": "pw"}


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(neo4j.GraphDatabase, "driver", lambda url, **kw: calls.append((url, kw)) or "driver")
    return calls


@pytest.mark.parametrize("url", ["bolt+s://g:7687", "neo4j+s://g:7687"])
def test_tls_with_system_cas(opened: list[tuple[str, dict[str, Any]]], url: str) -> None:
    assert gdown_driver({**ENV, "GLUONIFY_GDOWN_BOLT_URL": url}) == "driver"
    assert opened == [(url, {"auth": ("u", "pw")})]


def test_tls_with_the_platform_ca(opened: list[tuple[str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(neo4j, "TrustCustomCAs", lambda *f: ("custom", f))
    gdown_driver({**ENV, "GLUONIFY_GDOWN_BOLT_URL": "neo4j+s://g:7687", "GLUONIFY_GDOWN_CA_FILE": "/run/ca.pem"})
    url, kw = opened[0]
    assert url == "neo4j://g:7687"
    assert kw == {"auth": ("u", "pw"), "encrypted": True, "trusted_certificates": ("custom", ("/run/ca.pem",))}


def test_the_real_driver_accepts_these_options() -> None:
    d = neo4j.GraphDatabase.driver(
        "bolt://localhost:7687", auth=("u", "p"), encrypted=True, trusted_certificates=neo4j.TrustCustomCAs()
    )
    d.close()  # no connection is opened until the first query


@pytest.mark.parametrize("url", ["bolt://g:7687", "neo4j://g:7687"])
def test_plain_bolt_refused_except_for_dev(opened: list[tuple[str, dict[str, Any]]], url: str) -> None:
    with pytest.raises(RuntimeError, match="TLS required"):
        gdown_driver({**ENV, "GLUONIFY_GDOWN_BOLT_URL": url})
    gdown_driver({**ENV, "GLUONIFY_GDOWN_BOLT_URL": url, "GLUONIFY_GDOWN_CA_FILE": "/ca.pem"}, dev=True)
    assert opened == [(url, {"auth": ("u", "pw")})]  # no custom CA without TLS


def test_missing_variables() -> None:
    with pytest.raises(KeyError, match="GLUONIFY_GDOWN_BOLT_URL"):
        gdown_driver(ENV)
