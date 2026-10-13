"""The application: ``create_app`` of the SDK, the notes, the platform endpoints and the readiness of the storage.

Run it: ``uv run gluonify-source`` (``0.0.0.0:$PORT``, 8080 by default), or ``uvicorn --factory gluonify_source.main:build``.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import FastAPI
from gluonify import CharmVerifier, GluonifyServices, Principal
from gluonify.fastapi import GluonifyAuth, create_app, serve

from . import __version__, platform
from .config import READ, WRITE, SourceConfig
from .notes import api
from .notes.store import Driver
from .notes.stores import note_store

DEV = Principal("dev", frozenset({READ, WRITE}), {})


def build(
    services: GluonifyServices | None = None,
    *,
    verifier: Callable[[], CharmVerifier] | None = None,
    gdown: Callable[[GluonifyServices], Driver] | None = None,
) -> FastAPI:
    """Builds the application. ``verifier`` and ``gdown`` are replaceable in tests (as the Java tests fake Charm and Gdown)."""
    s = services or GluonifyServices()
    cfg = SourceConfig.from_env(s.environ)

    def charm() -> CharmVerifier:
        v = CharmVerifier.from_env(s, audience=cfg.audience, issuer=cfg.issuer)
        v.audience, v.issuer = cfg.audience, cfg.issuer  # GLUONIFY_SOURCE_OIDC_* override every platform value
        return v

    dev = DEV if cfg.dev else None
    app = create_app(
        "gluonify-source",
        audience=cfg.audience,
        version=__version__,
        description="Example application for Gluonify (Python): notes, Charm authentication, gDown storage.",
        services=s,
        auth=GluonifyAuth(verifier or charm, dev_identity=dev),
        dev_identity=dev,
    )
    app.state.config = cfg
    # plain bolt:// is accepted only with SOURCE_DEV=1, which create_app refuses on the platform
    app.state.notes = note_store(cfg.store, s, gdown, dev=cfg.dev)
    app.state.health.readiness("notes storage", lambda: (app.state.notes.ready(), {"store": app.state.notes.kind()}))
    app.include_router(api.router)
    app.include_router(platform.router)
    return app


def run() -> None:  # pragma: no cover - starts a server
    serve(build())


if __name__ == "__main__":  # pragma: no cover
    run()
