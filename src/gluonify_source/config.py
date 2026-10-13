"""The configuration of the application. Everything comes from the environment (the platform, or Top); nothing is hard-coded.

| Variable | Default | Role |
|---|---|---|
| ``SOURCE_STORE`` | ``auto`` | ``auto`` (gdown with a dedicated database, memory otherwise), ``memory``, ``gdown`` |
| ``SOURCE_DEV`` | unset | ``1``: development identity (all roles) for requests without a token; refused on the platform |
| ``GLUONIFY_SOURCE_OIDC_ISSUER`` / ``_AUDIENCE`` / ``_CLIENT_ID`` | platform values | override ``GLUONIFY_OIDC_*`` |
| ``GLUONIFY_SOURCE_CHARM_PUBLIC_URL`` | ``GLUONIFY_OIDC_PUBLIC_URL`` | Charm's PUBLIC address (what the browser reaches) |
| ``SOURCE_AUTH_SCOPE`` | ``openid`` | scope asked by the sign-in of a browser |
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

AUDIENCE = "gluonify-source"
"""The audience expected in Charm tokens when nothing else is given: rename it with the project."""

READ = "source:read"
WRITE = "source:write"


def _get(env: Mapping[str, str], *keys: str, default: str | None = None) -> str | None:
    for k in keys:
        v = env.get(k)
        if v is not None and v.strip():
            return v.strip()
    return default


@dataclass(frozen=True, slots=True)
class SourceConfig:
    store: str
    dev: bool
    issuer: str | None
    audience: str
    client_id: str | None
    charm_public_url: str | None
    scope: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> SourceConfig:
        return cls(
            store=(_get(env, "SOURCE_STORE", default="auto") or "auto").lower(),
            dev=(_get(env, "SOURCE_DEV", default="") or "").lower() in {"1", "true", "yes"},
            issuer=_get(env, "GLUONIFY_SOURCE_OIDC_ISSUER", "GLUONIFY_OIDC_ISSUER"),
            audience=_get(env, "GLUONIFY_SOURCE_OIDC_AUDIENCE", "GLUONIFY_OIDC_AUDIENCE", default=AUDIENCE) or AUDIENCE,
            client_id=_get(env, "GLUONIFY_SOURCE_OIDC_CLIENT_ID", "GLUONIFY_OIDC_CLIENT_ID"),
            charm_public_url=_get(env, "GLUONIFY_SOURCE_CHARM_PUBLIC_URL", "GLUONIFY_OIDC_PUBLIC_URL"),
            scope=_get(env, "SOURCE_AUTH_SCOPE", default="openid") or "openid",
        )
