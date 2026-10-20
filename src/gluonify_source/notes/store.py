"""The storage interface and its implementations: the resource does not know where the data lives."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from .models import NewNote, Note

LIMIT = 200


class Driver(Protocol):
    """What GraphNoteStore uses of ``neo4j.Driver`` (faked in tests)."""

    def execute_query(self, query: str, parameters: dict[str, Any] | None = ..., /, **kwargs: Any) -> Any: ...


class NoteStore(Protocol):
    def kind(self) -> str: ...
    def create(self, new: NewNote, author: str) -> Note: ...
    def list(self) -> list[Note]: ...
    def get(self, note_id: str) -> Note | None: ...
    def delete(self, note_id: str) -> bool: ...
    def ready(self) -> bool: ...


def _new(new: NewNote, author: str) -> Note:
    return Note(id=str(uuid.uuid4()), title=new.title, body=new.body or "", createdAt=datetime.now(UTC), author=author or "")


class MemoryNoteStore:
    """In memory: the default for development. Each replica has its own notes; they disappear on shutdown."""

    def __init__(self) -> None:
        self._notes: dict[str, Note] = {}
        self._lock = threading.Lock()

    def kind(self) -> str:
        return "memory"

    def create(self, new: NewNote, author: str) -> Note:
        n = _new(new, author)
        with self._lock:
            self._notes[n.id] = n
        return n

    def list(self) -> list[Note]:
        with self._lock:
            notes = sorted(self._notes.values(), key=lambda n: n.createdAt, reverse=True)
        return notes[:LIMIT]

    def get(self, note_id: str) -> Note | None:
        return self._notes.get(note_id)

    def delete(self, note_id: str) -> bool:
        with self._lock:
            return self._notes.pop(note_id, None) is not None

    def ready(self) -> bool:
        return True


class GraphNoteStore:
    """Notes in gDown, the platform's graph database (dedicated database), with the official neo4j driver."""

    def __init__(self, driver: Driver, database: str) -> None:
        self.driver = driver
        self.database = database

    def _run(self, statement: str, parameters: dict[str, Any]) -> Any:
        return self.driver.execute_query(statement, parameters, database_=self.database)

    def kind(self) -> str:
        return "gdown"

    def create(self, new: NewNote, author: str) -> Note:
        n = _new(new, author)
        self._run(
            "CREATE (:Note {id: $id, title: $title, body: $body, createdAt: $createdAt, author: $author})",
            {"id": n.id, "title": n.title, "body": n.body, "createdAt": n.createdAt.isoformat(), "author": n.author},
        )
        return n

    def list(self) -> list[Note]:
        r = self._run(
            "MATCH (n:Note) RETURN n.id AS id, n.title AS title, n.body AS body, n.createdAt AS createdAt, "
            "n.author AS author ORDER BY n.createdAt DESC LIMIT $limit",
            {"limit": LIMIT},
        )
        return [self._note(dict(rec)) for rec in r.records]

    def get(self, note_id: str) -> Note | None:
        r = self._run(
            "MATCH (n:Note {id: $id}) RETURN n.id AS id, n.title AS title, n.body AS body, n.createdAt AS createdAt, "
            "n.author AS author",
            {"id": note_id},
        )
        return self._note(dict(r.records[0])) if r.records else None

    def delete(self, note_id: str) -> bool:
        return int(self._run("MATCH (n:Note {id: $id}) DELETE n", {"id": note_id}).summary.counters.nodes_deleted) > 0

    def ready(self) -> bool:
        try:
            self._run("RETURN 1 AS ok", {})
        except Exception:
            return False
        return True

    @staticmethod
    def _note(r: dict[str, Any]) -> Note:
        return Note(
            id=r["id"],
            title=r["title"],
            body=r.get("body") or "",
            createdAt=datetime.fromisoformat(r["createdAt"]),
            author=r.get("author") or "",
        )
