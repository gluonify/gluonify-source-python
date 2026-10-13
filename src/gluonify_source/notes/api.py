"""The notes REST API: the model to copy for your own resource.

* ``APIRouter`` with a prefix: the address; JSON in and out (pydantic models);
* ``require_roles``: the roles of the Charm token (``roles`` claim); read = ``source:read``, write = ``source:write``;
* the pydantic body is validated, 400 otherwise; ``summary`` and ``tags`` document it in ``/q/swagger-ui``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from gluonify import Principal
from gluonify_fastapi import require_roles

from ..config import READ, WRITE
from .models import NewNote, Note
from .store import NoteStore

router = APIRouter(prefix="/api/notes", tags=["Notes"])

Reader = Annotated[Principal, Depends(require_roles(READ))]
Writer = Annotated[Principal, Depends(require_roles(WRITE))]


def store(request: Request) -> NoteStore:
    s: NoteStore = request.app.state.notes
    return s


Store = Annotated[NoteStore, Depends(store)]


@router.get("", summary="The notes, most recent first (200 at most)")
def list_notes(_: Reader, notes: Store) -> list[Note]:
    return notes.list()


@router.get("/{note_id}", summary="One note")
def get_note(note_id: str, _: Reader, notes: Store) -> Note:
    n = notes.get(note_id)
    if n is None:
        raise HTTPException(404, "unknown note")
    return n


@router.post("", status_code=201, summary="Creates a note (the author is the token subject)")
def create_note(new: NewNote, p: Writer, notes: Store, request: Request, response: Response) -> Note:
    n = notes.create(new, p.subject)
    response.headers["Location"] = str(request.url_for("get_note", note_id=n.id))
    return n


@router.delete("/{note_id}", status_code=204, summary="Deletes a note")
def delete_note(note_id: str, _: Writer, notes: Store) -> Response:
    if not notes.delete(note_id):
        raise HTTPException(404, "unknown note")
    return Response(status_code=204)
