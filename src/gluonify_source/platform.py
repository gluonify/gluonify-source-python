"""What the platform provided to this instance (never a secret), and the sign-in configuration of a browser UI."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from gluonify import GluonifyServices, Principal
from gluonify_fastapi import require_roles
from pydantic import BaseModel

from .config import READ, SourceConfig

router = APIRouter(tags=["Platform"])


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
        i = issuer.find("/realms/")
        v = issuer[:i] if i > 0 else issuer
    if v is None or not v.startswith(("https://", "http://")):
        return None
    return v.rstrip("/")


@router.get("/api/auth-config", tags=["Authentication"], summary="Public sign-in configuration (Charm client id and endpoints)")
def auth_config(request: Request) -> AuthConfig:
    cfg: SourceConfig = request.app.state.config
    required = request.app.state.gluonify_auth.sign_in_required
    base = charm_url(cfg.charm_public_url, cfg.issuer)
    if not cfg.client_id or base is None:
        return AuthConfig(
            signInRequired=required, clientId=None, authorizationUrl=None, tokenUrl=None, logoutUrl=None, scope=cfg.scope
        )
    return AuthConfig(
        signInRequired=required,
        clientId=cfg.client_id,
        authorizationUrl=base + "/authorize",
        tokenUrl=base + "/token",
        logoutUrl=base + "/logout",
        scope=cfg.scope,
    )
