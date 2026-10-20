"""Platform information, sign-in configuration, health and the choice of the store."""

from __future__ import annotations

import pytest
from conftest import ISS, PLATFORM, FakeCharm, FakeGdown, client
from gluonify import GluonifyServices

from gluonify_source.config import SourceConfig
from gluonify_source.main import build
from gluonify_source.notes.stores import effective_store, note_store
from gluonify_source.platform import charm_url


def test_platform_info(charm: FakeCharm, gdown: FakeGdown) -> None:
    body = client(PLATFORM, charm, gdown).get("/api/platform", headers=charm.bearer("source:read")).json()
    assert body == {
        "envName": "SBX",
        "envNode": "1",
        "selfUrl": "http://10.0.0.5:8080",
        "services": {"charm": "http://charm:8080", "gdown": "http://gdown:8080"},
        "store": "gdown",
        "storeReady": True,
        "greeting": "",
    }
    assert "pw" not in str(body)


def test_platform_info_reads_top(charm: FakeCharm, gdown: FakeGdown) -> None:
    env = {**PLATFORM, "APP_GREETING": "hello from Top", "GREETING": "ignored"}
    body = client(env, charm, gdown).get("/api/platform", headers=charm.bearer("source:read")).json()
    assert body["greeting"] == "hello from Top"  # the APP_ prefix ("top": true) wins over the bare name


def test_platform_info_needs_a_role(charm: FakeCharm) -> None:
    assert client({}, charm).get("/api/platform").status_code == 401


def test_health(charm: FakeCharm, gdown: FakeGdown) -> None:
    c = client(PLATFORM, charm, gdown)
    assert c.get("/health/live").status_code == 200
    r = c.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["checks"] == [{"name": "notes storage", "status": "UP", "data": {"store": "gdown"}}]
    gdown.down = True
    r = c.get("/health/ready")
    assert r.status_code == 503
    assert c.get("/q/health/ready").status_code == 404  # /q/ is the Quarkus namespace
    assert c.get("/health/live").status_code == 200  # a gDown outage must not restart the app


def test_auth_config_on_the_platform(charm: FakeCharm, gdown: FakeGdown) -> None:
    env = {**PLATFORM, "GLUONIFY_OIDC_CLIENT_ID": "app-source"}
    body = client(env, charm, gdown).get("/api/auth-config").json()
    assert body == {
        "signInRequired": True,
        "clientId": "app-source",
        "authorizationUrl": "https://id.gluonify.lan/authorize",
        "tokenUrl": "https://id.gluonify.lan/token",
        "logoutUrl": "https://id.gluonify.lan/logout",
        "scope": "openid",
    }


def test_auth_config_overrides(charm: FakeCharm) -> None:
    env = {
        "GLUONIFY_OIDC_CLIENT_ID": "platform",
        "GLUONIFY_SOURCE_OIDC_CLIENT_ID": "mine",
        "GLUONIFY_SOURCE_CHARM_PUBLIC_URL": "https://charm.example/",
        "SOURCE_AUTH_SCOPE": "openid profile",
    }
    body = client(env, charm).get("/api/auth-config").json()
    assert body["clientId"] == "mine"
    assert body["tokenUrl"] == "https://charm.example/token"
    assert body["scope"] == "openid profile"


def test_auth_config_not_configured(charm: FakeCharm) -> None:
    body = client({}, charm).get("/api/auth-config").json()
    assert body["clientId"] is None
    assert body["authorizationUrl"] is None


@pytest.mark.parametrize(
    ("configured", "issuer", "expected"),
    [
        (None, ISS, "https://id.gluonify.lan"),
        ("  ", "https://x/", "https://x"),
        ("https://c/", ISS, "https://c"),
        (None, None, None),
        (None, "any", None),
        ("ftp://c", None, None),
    ],
)
def test_charm_url(configured: str | None, issuer: str | None, expected: str | None) -> None:
    assert charm_url(configured, issuer) == expected


def test_dev_identity(charm: FakeCharm) -> None:
    c = client({"SOURCE_DEV": "1"}, charm)
    assert c.get("/api/notes").status_code == 200
    assert c.post("/api/notes", json={"title": "x"}).json()["author"] == "dev"
    assert c.get("/api/auth-config").json()["signInRequired"] is False


def test_dev_identity_refused_on_the_platform() -> None:
    services = GluonifyServices({**PLATFORM, "SOURCE_DEV": "true"})
    with pytest.raises(RuntimeError, match="refused on the platform"):
        build(services)


def test_source_overrides_win_over_platform_values(charm: FakeCharm) -> None:
    env = {**PLATFORM, "GLUONIFY_OIDC_AUDIENCE": "gluonify-platform", "GLUONIFY_SOURCE_OIDC_AUDIENCE": "gluonify-mine"}
    cfg = SourceConfig.from_env(env)
    assert cfg.audience == "gluonify-mine"
    app = build(GluonifyServices(env), gdown=lambda s: None)  # type: ignore[arg-type,return-value]
    v = app.state.gluonify_auth.verifier()  # the real factory: Charm resolved from the platform
    assert v.audience == "gluonify-mine"
    assert v.issuer == ISS
    assert v.jwks_url == "http://charm:8080/realms/gluonify/protocol/openid-connect/certs"


def test_store_choice() -> None:
    assert effective_store("auto", "db") == "gdown"
    assert effective_store("auto", " ") == "memory"
    assert effective_store("auto", None) == "memory"
    assert effective_store("memory", "db") == "memory"
    services = GluonifyServices({})
    with pytest.raises(ValueError, match="unknown SOURCE_STORE"):
        note_store("files", services)


def test_plain_bolt_refused_on_the_platform_and_allowed_for_dev() -> None:
    services = GluonifyServices({**PLATFORM, "GLUONIFY_GDOWN_BOLT_URL": "bolt://gdown:7687"})
    with pytest.raises(RuntimeError, match="TLS required"):
        build(services)
    dev = {
        "SOURCE_DEV": "1",
        "SOURCE_STORE": "gdown",
        "GLUONIFY_GDOWN_DATABASE": "d",
        "GLUONIFY_GDOWN_USER": "u",
        "GLUONIFY_GDOWN_PASSWORD": "p",
        "GLUONIFY_GDOWN_BOLT_URL": "bolt://localhost:7687",
    }
    assert build(GluonifyServices(dev)).state.notes.kind() == "gdown"


def test_platform_driver_options(charm: FakeCharm, gdown: FakeGdown) -> None:
    client(PLATFORM, charm, gdown)
    assert gdown.url == "bolt+s://gdown:7687"
    assert gdown.options == {"auth": ("app_1234", "pw")}


def test_gdown_without_database_fails_at_start() -> None:
    services = GluonifyServices({"SOURCE_STORE": "gdown"})
    with pytest.raises(ValueError, match="needs a dedicated database"):
        build(services)


def test_openapi(charm: FakeCharm) -> None:
    doc = client({}, charm).get("/openapi.json").json()
    assert doc["info"]["title"] == "gluonify-source"
    assert "/api/notes" in doc["paths"]


def test_swagger_ui_at_docs_interactive_locally_read_only_on_the_platform(charm: FakeCharm, gdown: FakeGdown) -> None:
    local = client({}, charm)
    assert local.get("/docs").status_code == 200
    assert "read-only" not in local.get("/docs").text
    assert local.get("/q/openapi").status_code == 404
    page = client(PLATFORM, charm, gdown).get("/docs")
    assert page.status_code == 200
    assert "Swagger UI is read-only in production" in page.text
