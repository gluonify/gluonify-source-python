"""The storage interface and its implementations: the resource does not know where the data lives."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any, Protocol

from gluonify_gdown import GdownClient

from .models import NewNote, Note

LIMIT = 200


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
            notes = list(self._notes.values())
        return sorted(notes, key=lambda n: n.createdAt, reverse=True)[:LIMIT]

    def get(self, note_id: str) -> Note | None:
        return self._notes.get(note_id)

    def delete(self, note_id: str) -> bool:
        with self._lock:
            return self._notes.pop(note_id, None) is not None

    def ready(self) -> bool:
        return True


class GraphNoteStore:
    """Notes in gDown (dedicated database) through gluonify-gdown: Bolt with TLS, or gDown's HTTP API."""

    def __init__(self, client: GdownClient) -> None:
        self.client = client

    def kind(self) -> str:
        return "gdown"

    def create(self, new: NewNote, author: str) -> Note:
        n = _new(new, author)
        self.client.write(
            "CREATE (:Note {id: $id, title: $title, body: $body, createdAt: $createdAt, author: $author})",
            {"id": n.id, "title": n.title, "body": n.body, "createdAt": n.createdAt.isoformat(), "author": n.author},
        )
        return n

    def list(self) -> list[Note]:
        return [
            self._note(r)
            for r in self.client.query(
                "MATCH (n:Note) RETURN n.id AS id, n.title AS title, n.body AS body, n.createdAt AS createdAt, "
                "n.author AS author ORDER BY n.createdAt DESC LIMIT $limit",
                {"limit": LIMIT},
            )
        ]

    def get(self, note_id: str) -> Note | None:
        rows = self.client.query(
            "MATCH (n:Note {id: $id}) RETURN n.id AS id, n.title AS title, n.body AS body, n.createdAt AS createdAt, "
            "n.author AS author",
            {"id": note_id},
        )
        return self._note(rows[0]) if rows else None

    def delete(self, note_id: str) -> bool:
        return self.client.write("MATCH (n:Note {id: $id}) DELETE n", {"id": note_id})["nodes_deleted"] > 0

    def ready(self) -> bool:
        return self.client.ready()

    @staticmethod
    def _note(r: dict[str, Any]) -> Note:
        return Note(
            id=r["id"],
            title=r["title"],
            body=r.get("body") or "",
            createdAt=datetime.fromisoformat(r["createdAt"]),
            author=r.get("author") or "",
        )
