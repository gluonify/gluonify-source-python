"""Chooses the NoteStore implementation (``SOURCE_STORE``): the single place to change to add a storage."""

from __future__ import annotations

from collections.abc import Callable

from gluonify import GdownClient, GluonifyServices

from .store import GraphNoteStore, MemoryNoteStore, NoteStore

DEDICATED_DATABASE = "GLUONIFY_GDOWN_DATABASE"


def effective_store(store: str, dedicated_database: str | None) -> str:
    """``auto`` becomes ``gdown`` when the platform provides a dedicated database, ``memory`` otherwise."""
    if store != "auto":
        return store
    return "gdown" if dedicated_database and dedicated_database.strip() else "memory"


def note_store(
    store: str,
    services: GluonifyServices,
    gdown: Callable[[GluonifyServices], GdownClient] = GdownClient.from_env,
) -> NoteStore:
    kind = effective_store(store, services.env(DEDICATED_DATABASE))
    if kind == "memory":
        return MemoryNoteStore()
    if kind == "gdown":
        return GraphNoteStore(gdown(services))
    raise ValueError(f'unknown SOURCE_STORE: "{kind}" (auto, memory or gdown)')
