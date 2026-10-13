"""Chooses the NoteStore implementation (``SOURCE_STORE``): the single place to change to add a storage."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

from gluonify import GluonifyServices

from .gdown import gdown_driver
from .store import Driver, GraphNoteStore, MemoryNoteStore, NoteStore

DEDICATED_DATABASE = "GLUONIFY_GDOWN_DATABASE"


def effective_store(store: str, dedicated_database: str | None) -> str:
    """``auto`` becomes ``gdown`` when the platform provides a dedicated database, ``memory`` otherwise."""
    if store != "auto":
        return store
    return "gdown" if dedicated_database and dedicated_database.strip() else "memory"


def note_store(
    store: str,
    services: GluonifyServices,
    gdown: Callable[[GluonifyServices], Driver] | None = None,
    dev: bool = False,
) -> NoteStore:
    kind = effective_store(store, services.env(DEDICATED_DATABASE))
    if kind == "memory":
        return MemoryNoteStore()
    if kind == "gdown":
        database = services.env(DEDICATED_DATABASE)
        if database is None:
            raise ValueError(
                f'SOURCE_STORE=gdown needs a dedicated database ({DEDICATED_DATABASE}): deploy with "gdownDatabase": true'
            )
        driver = gdown(services) if gdown else cast(Driver, gdown_driver(services.environ, dev=dev))
        return GraphNoteStore(driver, database.strip())
    raise ValueError(f'unknown SOURCE_STORE: "{kind}" (auto, memory or gdown)')
