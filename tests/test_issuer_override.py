"""GLUONIFY_SOURCE_OIDC_ISSUER against the realm the platform injects: a mismatch is logged once at startup, never refused."""

from __future__ import annotations

import logging

import pytest
from conftest import ISS, PLATFORM, FakeCharm, FakeGdown, client
from gluonify import GluonifyServices

from gluonify_source.config import issuer_override_warning
from gluonify_source.main import build

LOGGER = "gluonify_source.main"
ORG = "https://id.gluonify.lan/realms/org-acme"
ORG_PLATFORM = {**PLATFORM, "GLUONIFY_OIDC_REALM": "org-acme", "GLUONIFY_OIDC_ISSUER": ORG}


def warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno == logging.WARNING]


def test_platform_issuer_override_in_an_organization_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    env = {**ORG_PLATFORM, "GLUONIFY_SOURCE_OIDC_ISSUER": ISS}
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        app = build(GluonifyServices(env), gdown=lambda s: None)  # type: ignore[arg-type,return-value]
        v = app.state.gluonify_auth.verifier()  # building the verifier does not warn again
    assert v.issuer == ISS  # warned, not refused: the override still wins
    [message] = warnings(caplog)
    assert "GLUONIFY_SOURCE_OIDC_ISSUER names realm 'gluonify'" in message
    assert "GLUONIFY_OIDC_REALM is 'org-acme'" in message
    assert "id.gluonify.lan" not in message
    assert "pw" not in message  # no credential of the environment


def test_mismatch_is_not_exposed_to_clients(caplog: pytest.LogCaptureFixture, charm: FakeCharm, gdown: FakeGdown) -> None:
    env = {**ORG_PLATFORM, "GLUONIFY_SOURCE_OIDC_ISSUER": ISS, "GLUONIFY_OIDC_CLIENT_ID": "app-source"}
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        c = client(env, charm, gdown)
    assert len(warnings(caplog)) == 1
    for path in ("/api/auth-config", "/health/ready", "/openapi.json"):
        assert "GLUONIFY_OIDC_REALM" not in c.get(path).text
    assert "GLUONIFY_OIDC_REALM" not in c.get("/api/platform", headers=charm.bearer("source:read")).text


@pytest.mark.parametrize(
    "override",
    [
        ORG,
        "HTTPS://ID.Gluonify.LAN/realms/org-acme/",  # case of scheme and host, trailing slash
        "https://id.gluonify.lan:443/realms/org-acme",  # default port
        "http://charm:8080/realms/org-acme",  # Charm's internal address
    ],
)
def test_override_matching_the_realm_is_silent(override: str, caplog: pytest.LogCaptureFixture) -> None:
    env = {**ORG_PLATFORM, "GLUONIFY_SOURCE_OIDC_ISSUER": override}
    assert issuer_override_warning(env) is None
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        build(GluonifyServices(env), gdown=lambda s: None)  # type: ignore[arg-type,return-value]
    assert warnings(caplog) == []


def test_override_without_realm_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    env = {**PLATFORM, "GLUONIFY_SOURCE_OIDC_ISSUER": "https://id.example.com/realms/other"}
    assert issuer_override_warning(env) is None
    assert issuer_override_warning({**env, "GLUONIFY_OIDC_REALM": "  "}) is None
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        build(GluonifyServices(env), gdown=lambda s: None)  # type: ignore[arg-type,return-value]
    assert warnings(caplog) == []


def test_realm_without_override_is_silent(caplog: pytest.LogCaptureFixture) -> None:
    assert issuer_override_warning(ORG_PLATFORM) is None
    assert issuer_override_warning({**ORG_PLATFORM, "GLUONIFY_SOURCE_OIDC_ISSUER": " "}) is None
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        build(GluonifyServices(ORG_PLATFORM), gdown=lambda s: None)  # type: ignore[arg-type,return-value]
    assert warnings(caplog) == []


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ("not a url", "is not an http(s) URL"),
        ("any", "is not an http(s) URL"),
        ("ftp://id.gluonify.lan/realms/org-acme", "is not an http(s) URL"),
        ("https://[::1/realms/org-acme", "is not an http(s) URL"),  # invalid IPv6 host
        ("https://id.gluonify.lan:port/realms/org-acme", "is not an http(s) URL"),  # port not a number
        ("https:///realms/org-acme", "is not an http(s) URL"),  # no host
        ("https://id.gluonify.lan", "has no /realms/<realm> part"),
        ("https://elsewhere.example/realms/org-acme", "is not under Charm's address"),
    ],
)
def test_malformed_or_foreign_override_warns_without_raising(
    override: str, reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    env = {**ORG_PLATFORM, "GLUONIFY_SOURCE_OIDC_ISSUER": override}
    with caplog.at_level(logging.WARNING, logger=LOGGER):
        build(GluonifyServices(env), gdown=lambda s: None)  # type: ignore[arg-type,return-value]
    [message] = warnings(caplog)
    assert message.startswith(f"GLUONIFY_SOURCE_OIDC_ISSUER {reason}, but GLUONIFY_OIDC_REALM is 'org-acme'")


def test_without_any_charm_address_only_the_realm_part_is_compared() -> None:
    env = {"GLUONIFY_OIDC_REALM": "org-acme"}
    assert issuer_override_warning({**env, "GLUONIFY_SOURCE_OIDC_ISSUER": "https://anywhere.example/realms/org-acme"}) is None
    warning = issuer_override_warning({**env, "GLUONIFY_SOURCE_OIDC_ISSUER": "https://anywhere.example/realms/org-other"})
    assert warning is not None
    assert "names realm 'org-other'" in warning
