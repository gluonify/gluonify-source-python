"""The notes API (the model of NotesResourceTest): roles, validation, HTTP codes, both stores."""

from __future__ import annotations

import pytest
from conftest import PLATFORM, FakeCharm, FakeGdown, client
from fastapi.testclient import TestClient

R, W = "source:read", "source:write"


@pytest.fixture(params=["memory", "gdown"])
def api(request: pytest.FixtureRequest, charm: FakeCharm, gdown: FakeGdown) -> TestClient:
    env = PLATFORM if request.param == "gdown" else {"SOURCE_STORE": "memory"}
    return client(env, charm, gdown)


def test_create_list_get_delete(api: TestClient, charm: FakeCharm) -> None:
    r = api.post("/api/notes", json={"title": "Groceries", "body": "bread"}, headers=charm.bearer(W))
    assert r.status_code == 201
    note = r.json()
    assert note["title"] == "Groceries"
    assert note["body"] == "bread"
    assert note["author"] == "ada"
    assert r.headers["location"].endswith("/api/notes/" + note["id"])
    api.post("/api/notes", json={"title": "Second"}, headers=charm.bearer(W))
    listed = api.get("/api/notes", headers=charm.bearer(R)).json()
    assert [n["title"] for n in listed] == ["Second", "Groceries"]
    assert listed[0]["body"] == ""
    assert api.get("/api/notes/" + note["id"], headers=charm.bearer(R)).json() == note
    assert api.delete("/api/notes/" + note["id"], headers=charm.bearer(W)).status_code == 204
    r = api.get("/api/notes/" + note["id"], headers=charm.bearer(R))
    assert r.status_code == 404
    assert r.json() == {"error": "unknown note"}
    assert api.delete("/api/notes/" + note["id"], headers=charm.bearer(W)).status_code == 404


def test_without_token_401(api: TestClient) -> None:
    r = api.get("/api/notes")
    assert r.status_code == 401
    assert "error" in r.json()


def test_reader_cannot_write_403(api: TestClient, charm: FakeCharm) -> None:
    r = api.post("/api/notes", json={"title": "x"}, headers=charm.bearer(R))
    assert r.status_code == 403
    assert api.delete("/api/notes/x", headers=charm.bearer(R)).status_code == 403


def test_writer_cannot_read_403(api: TestClient, charm: FakeCharm) -> None:
    assert api.get("/api/notes", headers=charm.bearer(W)).status_code == 403


def test_token_for_another_audience_401(api: TestClient, charm: FakeCharm) -> None:
    t = charm.token(R, aud="gluonify-other")
    assert api.get("/api/notes", headers={"Authorization": f"Bearer {t}"}).status_code == 401


@pytest.mark.parametrize(
    "body",
    [{}, {"title": ""}, {"title": "   "}, {"title": "x" * 121}, {"title": "ok", "body": "x" * 4001}, {"title": 3}],
)
def test_invalid_body_400(api: TestClient, charm: FakeCharm, body: dict[str, object]) -> None:
    r = api.post("/api/notes", json=body, headers=charm.bearer(W))
    assert r.status_code == 400
    assert r.json()["error"] == "invalid body"
    assert r.json()["violations"]


def test_gdown_statements_go_to_the_dedicated_database(charm: FakeCharm, gdown: FakeGdown) -> None:
    c = client(PLATFORM, charm, gdown)
    c.post("/api/notes", json={"title": "t"}, headers=charm.bearer(W))
    query, params, database = gdown.calls[0]
    assert query.startswith("CREATE (:Note")
    assert params["title"] == "t"
    assert database == "app_1234"
