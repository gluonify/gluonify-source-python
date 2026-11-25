"""What the platform provided to this instance (never a secret), and the sign-in configuration of a browser UI."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from gluonify import GluonifyServices, Principal, Top
from gluonify.fastapi import require_roles
from pydantic import BaseModel

from .config import READ, SourceConfig

router = APIRouter(tags=["Platform"])

REALMS = "/realms/"
PLATFORM_REALM = "gluonify"


@router.get("/api/platform", summary="Environment provided by the platform, granted services, storage")
def info(request: Request, _: Annotated[Principal, Depends(require_roles(READ))]) -> dict[str, Any]:
    s: GluonifyServices = request.app.state.gluonify
    return {
        "envName": s.environment or "",
        "envNode": s.replica or "",
        "selfUrl": s.self_url or "",
        "services": s.granted(),
        "store": request.app.state.notes.kind(),
        "storeReady": request.app.state.notes.ready(),
        # a non-secret configuration key kept in Top (vault key GREETING, injected as APP_GREETING with "top": true)
        "greeting": Top(s.environ).get("GREETING", "") or "",
    }


class AuthConfig(BaseModel):
    """Null fields when the client is not configured (the UI then explains which variable is missing)."""

    signInRequired: bool
    clientId: str | None
    authorizationUrl: str | None
    tokenUrl: str | None
    logoutUrl: str | None
    scope: str


def charm_url(configured: str | None, issuer: str | None) -> str | None:
    """Charm's public base: the configured one, otherwise the issuer without its ``/realms/...`` part."""
    v = configured.strip() if configured and configured.strip() else None
    if v is None and issuer and issuer.startswith("http"):
        i = issuer.find(REALMS)
        v = issuer[:i] if i > 0 else issuer
    if v is None or not v.startswith(("https://", "http://")):
        return None
    return v.rstrip("/")


def endpoint_base(charm: str, issuer: str | None) -> str:
    """Base of the browser endpoints: Charm's address for the platform realm, ``<charm>/realms/<realm>`` for an organization's."""
    i = issuer.find(REALMS) if issuer else -1
    realm = issuer[i + len(REALMS) :].rstrip("/") if issuer and i >= 0 else ""
    return charm if realm in ("", PLATFORM_REALM) else charm + REALMS + realm


@router.get("/api/auth-config", tags=["Authentication"], summary="Public sign-in configuration (Charm client id and endpoints)")
def auth_config(request: Request) -> AuthConfig:
    cfg: SourceConfig = request.app.state.config
    required = request.app.state.gluonify_auth.sign_in_required
    base = charm_url(cfg.charm_public_url, cfg.issuer)
    if not cfg.client_id or base is None:
        return AuthConfig(
            signInRequired=required, clientId=None, authorizationUrl=None, tokenUrl=None, logoutUrl=None, scope=cfg.scope
        )
    # deployed for an organization, the issuer is that organization's realm and the endpoints are the realm's own;
    # the platform realm keeps Charm's root ones
    realm = endpoint_base(base, cfg.issuer)
    own = realm != base
    endpoints = realm + "/protocol/openid-connect" if own else base
    return AuthConfig(
        signInRequired=required,
        clientId=cfg.client_id,
        authorizationUrl=endpoints + ("/auth" if own else "/authorize"),
        tokenUrl=endpoints + "/token",
        logoutUrl=endpoints + "/logout",
        scope=cfg.scope,
    )
