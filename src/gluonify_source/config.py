"""The configuration of the application. Everything comes from the environment (the platform, or Top); nothing is hard-coded.

| Variable | Default | Role |
|---|---|---|
| ``SOURCE_STORE`` | ``auto`` | ``auto`` (gdown with a dedicated database, memory otherwise), ``memory``, ``gdown`` |
| ``SOURCE_DEV`` | unset | ``1``: development identity (all roles) for requests without a token; refused on the platform |
| ``GLUONIFY_SOURCE_OIDC_ISSUER`` / ``_AUDIENCE`` / ``_CLIENT_ID`` | platform values | override ``GLUONIFY_OIDC_*`` |
| ``GLUONIFY_SOURCE_CHARM_PUBLIC_URL`` | ``GLUONIFY_OIDC_PUBLIC_URL`` | Charm's PUBLIC address (what the browser reaches) |
| ``SOURCE_AUTH_SCOPE`` | ``openid`` | scope asked by the sign-in of a browser |

An issuer override that is not the issuer of ``GLUONIFY_OIDC_REALM`` is logged once at startup (:func:`issuer_override_warning`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

AUDIENCE = "gluonify-source"
"""The audience expected in Charm tokens when nothing else is given: rename it with the project."""

READ = "source:read"
WRITE = "source:write"

SOURCE_ISSUER = "GLUONIFY_SOURCE_OIDC_ISSUER"
OIDC_REALM = "GLUONIFY_OIDC_REALM"
REALMS = "/realms/"
CHARM_BASES = (
    "GLUONIFY_SOURCE_CHARM_PUBLIC_URL",
    "GLUONIFY_OIDC_PUBLIC_URL",
    "GLUONIFY_OIDC_ISSUER",
    "GLUONIFY_SERVICE_CHARM_URL",
)
"""Where Charm's address can be read (public or internal); an issuer's ``/realms/...`` part is cut off."""

_DEFAULT_PORTS = {"http": 80, "https": 443}


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


def _normalised(url: str) -> tuple[str, str, str] | None:
    """``(scheme, host[:port], path)``: scheme and host in lower case, default port and trailing slash dropped; ``None``
    when ``url`` is not an ``http(s)`` URL with a host."""
    try:
        parts = urlsplit(url)
        port = parts.port  # raises ValueError for a port that is not a number or out of range
    except ValueError:
        return None
    scheme = parts.scheme.lower()
    if scheme not in _DEFAULT_PORTS or not parts.hostname:
        return None
    host = parts.hostname if port in (None, _DEFAULT_PORTS[scheme]) else f"{parts.hostname}:{port}"
    return scheme, host, parts.path.rstrip("/")


def _realm_part(path: str) -> str:
    i = path.rfind(REALMS)
    return path[i + len(REALMS) :] if i >= 0 else ""


def _charm_bases(env: Mapping[str, str]) -> set[tuple[str, str, str]]:
    bases: set[tuple[str, str, str]] = set()
    for key in CHARM_BASES:
        n = _normalised(_get(env, key) or "")
        if n is not None:
            i = n[2].find(REALMS)
            bases.add((n[0], n[1], n[2][:i] if i >= 0 else n[2]))
    return bases


def issuer_override_warning(env: Mapping[str, str]) -> str | None:
    """The warning to log at startup when ``GLUONIFY_SOURCE_OIDC_ISSUER`` is not the issuer of ``GLUONIFY_OIDC_REALM``.

    The token keys always follow the realm the platform injects, while the override replaces the issuer the tokens must
    carry: an override left over from a deployment without an organization makes every token of the organization's realm
    refused. The expected issuer is ``<Charm's public or internal base>/realms/<realm>`` (compared with the scheme and the
    host in lower case, without default port nor trailing slash); with no known base, only the realm part is compared.
    The message names the variables and the realm parts only, never a token or a credential; it is never sent to a client.
    ``None`` when there is no override, no realm, or the override is the realm's issuer.
    """
    override, realm = _get(env, SOURCE_ISSUER), _get(env, OIDC_REALM)
    if override is None or realm is None:
        return None
    issuer = _normalised(override)
    if issuer is not None and _is_issuer_of(issuer, realm, _charm_bases(env)):
        return None
    return (
        f"{SOURCE_ISSUER} {_mismatch(issuer, realm)}, but {OIDC_REALM} is {realm!r}: tokens are verified with the keys of "
        f"realm {realm!r} and must carry the override's issuer, so the realm's tokens are refused. "
        f"Remove the override or set it to <Charm>/realms/{realm}."
    )


def _is_issuer_of(issuer: tuple[str, str, str], realm: str, bases: set[tuple[str, str, str]]) -> bool:
    if not bases:
        return _realm_part(issuer[2]) == realm
    return any(issuer == (scheme, host, path + REALMS + realm) for scheme, host, path in bases)


def _mismatch(issuer: tuple[str, str, str] | None, realm: str) -> str:
    """What is wrong with the override, by its realm part only (an issuer is not a secret, but the message stays short)."""
    if issuer is None:
        return "is not an http(s) URL"
    found = _realm_part(issuer[2])
    if not found:
        return "has no /realms/<realm> part"
    return f"names realm {found!r}" if found != realm else "is not under Charm's address"
