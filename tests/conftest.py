"""Charm and gDown faked, as the Java tests do: a P-256 key standing in for Charm, a fake neo4j driver for gDown."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from typing import Any
from unittest.mock import patch

import jwt
import neo4j
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from gluonify import CharmVerifier, GluonifyServices

from gluonify_source.main import build
from gluonify_source.notes.gdown import gdown_driver

ISS = "https://id.gluonify.lan/realms/gluonify"


class FakeCharm:
    def __init__(self) -> None:
        self.key = ec.generate_private_key(ec.SECP256R1())

    def jwks(self, _: str) -> dict[str, Any]:
        jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self.key.public_key()))
        jwk.update({"kid": "k1", "use": "sig"})
        return {"keys": [jwk]}

    def verifier(self, audience: str = "gluonify-source") -> CharmVerifier:
        return CharmVerifier("http://charm/certs", audience=audience, issuer=ISS, fetch=self.jwks)

    def token(self, *roles: str, sub: str = "ada", aud: str = "gluonify-source") -> str:
        now = int(time.time())
        claims = {"sub": sub, "aud": aud, "iss": ISS, "iat": now, "exp": now + 300, "roles": list(roles)}
        return jwt.encode(claims, self.key, algorithm="ES256", headers={"kid": "k1"})

    def bearer(self, *roles: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token(*roles)}"}


class Counters:
    def __init__(self, deleted: int = 0) -> None:
        self.nodes_created = 0
        self.nodes_deleted = deleted
        self.relationships_created = 0
        self.relationships_deleted = 0
        self.properties_set = 0


class FakeGdown:
    """A tiny in-memory interpreter of the four statements of GraphNoteStore, behind the neo4j driver interface."""

    def __init__(self) -> None:
        self.nodes: list[dict[str, Any]] = []
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []
        self.down = False
        self.url: str | None = None
        self.options: dict[str, Any] = {}

    def opened(self, url: str, options: dict[str, Any]) -> FakeGdown:
        self.url, self.options = url, options
        return self

    def execute_query(self, query: str, parameters: Mapping[str, Any] | None = None, /, **kw: Any) -> Any:
        if self.down:
            raise OSError("gdown down")
        p = dict(parameters or {})
        self.calls.append((query, p, kw.get("database_")))
        records: list[dict[str, Any]] = []
        deleted = 0
        if query.startswith("CREATE"):
            self.nodes.append(p)
        elif query.startswith("MATCH (n:Note {id: $id}) DELETE"):
            before = len(self.nodes)
            self.nodes = [n for n in self.nodes if n["id"] != p["id"]]
            deleted = before - len(self.nodes)
        elif query.startswith("MATCH (n:Note {id: $id})"):
            records = [dict(n) for n in self.nodes if n["id"] == p["id"]]
        elif query.startswith("MATCH (n:Note)"):
            records = sorted((dict(n) for n in self.nodes), key=lambda n: n["createdAt"], reverse=True)[: p["limit"]]
        elif query.startswith("RETURN 1"):
            records = [{"ok": 1}]

        class R:
            pass

        r = R()
        r.records = records  # type: ignore[attr-defined]
        r.summary = R()  # type: ignore[attr-defined]
        r.summary.counters = Counters(deleted)  # type: ignore[attr-defined]
        return r

    def verify_connectivity(self) -> None:
        return None

    def close(self) -> None:
        return None


@pytest.fixture
def charm() -> FakeCharm:
    return FakeCharm()


@pytest.fixture
def gdown() -> FakeGdown:
    return FakeGdown()


PLATFORM = {
    "GLUONIFY_ENVIRONMENT": "SBX",
    "GLUONIFY_REPLICA": "1",
    "GLUONIFY_SELF_URL": "http://10.0.0.5:8080",
    "GLUONIFY_SERVICE_CHARM_URL": "http://charm:8080",
    "GLUONIFY_SERVICE_GDOWN_URL": "http://gdown:8080",
    "GLUONIFY_GDOWN_BOLT_URL": "bolt+s://gdown:7687",
    "GLUONIFY_GDOWN_DATABASE": "app_1234",
    "GLUONIFY_GDOWN_USER": "app_1234",
    "GLUONIFY_GDOWN_PASSWORD": "pw",
    "GLUONIFY_OIDC_ISSUER": ISS,
    "GLUONIFY_OIDC_AUDIENCE": "gluonify-source",
}


def client(env: Mapping[str, str], charm: FakeCharm, gdown: FakeGdown | None = None) -> TestClient:
    def fake_gdown(s: GluonifyServices) -> Any:
        # the real gdown_driver of the app, with the neo4j driver constructor replaced by the fake
        with patch.object(neo4j.GraphDatabase, "driver", lambda url, **kw: gdown.opened(url, kw)):
            return gdown_driver(s.environ)

    return TestClient(build(GluonifyServices(dict(env)), verifier=charm.verifier, gdown=fake_gdown))
