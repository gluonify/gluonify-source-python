"""The model. A note is IMMUTABLE (no update): deliberate, as in the Java version."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewNote(BaseModel):
    """Creation body, validated (400 with the list of violations otherwise)."""

    title: str = Field(min_length=1, max_length=120, pattern=r"\S")
    body: str | None = Field(default=None, max_length=4000)


class Note(BaseModel):
    id: str
    title: str
    body: str
    createdAt: datetime
    author: str
