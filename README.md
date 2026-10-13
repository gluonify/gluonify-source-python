# gluonify-source-python

**English** · [Français](README.fr.md) · [Español](README.es.md) · [Italiano](README.it.md) · [Deutsch](README.de.md)

> **Java variants.** The same service in Quarkus lives in [`gluonify-source`](https://github.com/gluonify/gluonify-source) (Maven) and [`gluonify-source-gradle`](https://github.com/gluonify/gluonify-source-gradle) (Gradle). This one is its **Python** counterpart, as far as it maps.

**The starting point for a Python service on [Gluonify](https://gluonify.io).** A small, complete service (some "notes") built with **FastAPI** and **uvicorn** on top of the Gluonify Python SDK ([`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python): distribution `gluonify` with its extra `fastapi`, `pip install "gluonify[fastapi]"`). It shows, with running code and tests, how to:

1. build a **REST service** (validation, roles, OpenAPI);
2. **verify Charm tokens** and check roles, and give a browser what it needs to sign in;
3. keep data in **gDown**, the platform's graph database (dedicated database, official `neo4j` driver over Bolt with TLS);
4. expose the **health** endpoints the platform watches.

> Python applications run on Gluonify with the `python3` of Debian 13 (**CPython 3.13**) on each node: Bup installs your locked dependencies into a venv, signs code and venv in one archive, and the node runs it in the same sandbox as native applications. No Dockerfile.

## Contents
1. [Getting started in 5 minutes](#1-getting-started-in-5-minutes)
2. [The project map](#2-the-project-map)
3. [Building a REST service](#3-building-a-rest-service)
4. [Authentication: Charm tokens](#4-authentication-charm-tokens)
5. [Storage: memory or gDown](#5-storage-memory-or-gdown)
6. [Configuration](#6-configuration)
7. [Building and deploying](#7-building-and-deploying)
8. [Testing](#8-testing)
9. [What maps from gluonify-source, and what does not yet](#9-what-maps-from-gluonify-source-and-what-does-not-yet)

---

## 1. Getting started in 5 minutes

**Prerequisites**: Python 3.13 and [uv](https://docs.astral.sh/uv/). Until the SDK is published on PyPI, clone [`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python) **next to** this repository (`../gluonify-plasma-python`): `pyproject.toml` takes it from there.

```bash
git clone https://github.com/gluonify/gluonify-source-python.git
cd gluonify-source-python
uv sync
SOURCE_DEV=1 uv run gluonify-source
```

`SOURCE_DEV=1` gives every request without a token a "dev" identity with all roles (refused on the platform). Notes are in memory. Then:

| Address | Content |
|---|---|
| `/api/notes` | the REST API (JSON) |
| `/api/platform` | what the platform provided (environment, granted services, storage) |
| `/api/auth-config` | public sign-in configuration for a browser UI (Charm client id and endpoints) |
| `/q/swagger-ui` · `/q/openapi` | interactive documentation and the OpenAPI contract |
| `/q/health/ready` · `/q/health/live` | readiness (the storage answers) and liveness |

```bash
curl -s localhost:8080/api/notes -H 'Content-Type: application/json' -d '{"title":"Groceries","body":"bread"}'
curl -s localhost:8080/api/notes
```

## 2. The project map

```
pyproject.toml              the project: dependencies, script gluonify-source, ruff, pytest
uv.lock                     the universal lock file (hashes of every PyPI file)
requirements.lock           `uv export` of uv.lock, with hashes: what Bup installs with `pip install --require-hashes`
gluonify.json               read by Bup: gdownDatabase, port variable, health path ("uses" is inferred from the SDK markers)
deploy/appspec.json         an example AppSpec for a deployment by hand
src/gluonify_source/
  main.py                   build(): create_app of the SDK + notes + platform + readiness; run() starts uvicorn
  config.py                 every variable read, with its default
  notes/models.py           NewNote (validated body), Note
  notes/api.py              ← THE MODEL OF A REST RESOURCE (to copy)
  notes/store.py            the NoteStore interface; MemoryNoteStore, GraphNoteStore (gDown)
  notes/gdown.py            HOW TO REACH gDOWN: the neo4j driver in ten lines (TLS only, platform CA)
  notes/stores.py           picks the implementation (SOURCE_STORE): the place to plug in yours
  platform.py               /api/platform and /api/auth-config
tests/                      Charm faked by a P-256 key and its JWKS, gDown by a fake neo4j driver
```

## 3. Building a REST service

Read [`notes/api.py`](src/gluonify_source/notes/api.py): it is the model.

1. **The model**: a pydantic `BaseModel` (validated, serialised, described by OpenAPI).
2. **The router**: `APIRouter(prefix="/api/orders", tags=["Orders"])`, functions with `@router.get/post/delete`, roles with a dependency `Annotated[Principal, Depends(require_roles("shop:write"))]`. Include it in `main.build()`.
3. **HTTP codes**: 201 + `Location` on creation, 204 with no body, 400 for an invalid body (`{"error": "invalid body", "violations": [...]}`), 401 without a valid token, 403 without the role, 404 for an unknown id. Errors are `{"error": "…"}`.
4. **The tests**: copy [`tests/test_notes.py`](tests/test_notes.py): `charm.bearer("shop:read")` makes a signed test token.

Storage sits behind [`NoteStore`](src/gluonify_source/notes/store.py): implement it and add a case in [`stores.py`](src/gluonify_source/notes/stores.py).

## 4. Authentication: Charm tokens

The API verifies bearer tokens issued by **Charm** (JWT, ES256) with `require_roles` of `gluonify.fastapi`: nothing to configure on the platform. The SDK fetches Charm's keys from `GLUONIFY_SERVICE_CHARM_URL`, checks the issuer `GLUONIFY_OIDC_ISSUER` and the audience `GLUONIFY_OIDC_AUDIENCE` (`gluonify-source` by default), and reads the roles from the `roles` claim (`source:read`, `source:write`). A browser UI signs in with Charm itself (authorization code + PKCE, the `@gluonify/ui` kit) using `GET /api/auth-config`; the password is never typed into this application.

## 5. Storage: memory or gDown

`SOURCE_STORE=auto` (default) uses **gDown** when the platform provides a dedicated database (`GLUONIFY_GDOWN_DATABASE`, from `"gdownDatabase": true`), memory otherwise. `GraphNoteStore` runs four parameterised Cypher statements on the dedicated database with the official **`neo4j`** driver. There is no SDK client for gDown: the driver is enough, and installing it (or **`neomodel`**, an OGM on top of it, if you prefer mapped classes) is what makes Bup infer `?gdown`.

**How to reach gDown** ([`notes/gdown.py`](src/gluonify_source/notes/gdown.py), shown here with `os.environ`): Bolt is **TLS only**, and the platform injects `GLUONIFY_GDOWN_BOLT_URL` (`bolt+s://` or `neo4j+s://`), `GLUONIFY_GDOWN_DATABASE`, `GLUONIFY_GDOWN_USER`, `GLUONIFY_GDOWN_PASSWORD` and `GLUONIFY_GDOWN_CA_FILE` (the CA PEM).

```python
import os

import neo4j  # pip install neo4j  (Bup then infers "?gdown")


def gdown_driver(dev: bool = False) -> neo4j.Driver:
    url = os.environ["GLUONIFY_GDOWN_BOLT_URL"]  # bolt+s://… or neo4j+s://…
    scheme, rest = url.split("://", 1)
    if not scheme.endswith("+s") and not dev:
        raise RuntimeError("gDown: TLS required (bolt+s:// or neo4j+s://)")
    auth = (os.environ["GLUONIFY_GDOWN_USER"], os.environ["GLUONIFY_GDOWN_PASSWORD"])
    ca = os.environ.get("GLUONIFY_GDOWN_CA_FILE")
    if ca and scheme.endswith("+s"):  # the driver refuses a custom CA with "+s": same TLS, explicit trust
        return neo4j.GraphDatabase.driver(f"{scheme[:-2]}://{rest}", auth=auth, encrypted=True,
                                          trusted_certificates=neo4j.TrustCustomCAs(ca))
    return neo4j.GraphDatabase.driver(url, auth=auth)


driver = gdown_driver()
records, _, _ = driver.execute_query("MATCH (n:Note) RETURN n.title AS title",
                                     database_=os.environ["GLUONIFY_GDOWN_DATABASE"])
```

The driver refuses a custom CA with a `+s` scheme, hence `encrypted=True` with `TrustCustomCAs`: still TLS, verified against the platform CA. A plain `bolt://` URL is refused, except with `SOURCE_DEV=1` (a local gDown), which the platform refuses.

## 6. Configuration

All configuration comes from the environment (the platform, or the Top vault); nothing secret goes into Git.

| Variable | Default | Role |
|---|---|---|
| `SOURCE_STORE` | `auto` | `auto`, `memory` or `gdown` |
| `SOURCE_DEV` | unset | `1`: development identity for requests without a token (refused on the platform) |
| `PORT` | `8080` | listening port (always `0.0.0.0`) |
| `GLUONIFY_SOURCE_OIDC_ISSUER`, `GLUONIFY_SOURCE_OIDC_AUDIENCE`, `GLUONIFY_SOURCE_OIDC_CLIENT_ID` | platform values `GLUONIFY_OIDC_*` | override the platform values |
| `GLUONIFY_SOURCE_CHARM_PUBLIC_URL` | `GLUONIFY_OIDC_PUBLIC_URL`, else derived from the issuer | Charm's public address for the browser |
| `SOURCE_AUTH_SCOPE` | `openid` | scope of the browser sign-in |
| `GLUONIFY_GDOWN_BOLT_URL`, `GLUONIFY_GDOWN_CA_FILE` | injected by the platform | gDown's Bolt address (`bolt+s://`, TLS only) and the CA to trust |

## 7. Building and deploying

Bup detects a Python project by its `pyproject.toml`, requires the lock file, analyses the code (SonarQube, dangerous-call rules, `pip-audit`), installs `requirements.lock` with `pip install --require-hashes` into a venv, and signs code and venv in one gzip. **`uses` is inferred** from the `[gluonify.uses]` markers of the SDK distributions installed in that venv (`gluonify` declares `charm`; the `neo4j` distribution infers `gdown`), so `gluonify.json` only says what cannot be inferred:

```json
{"gdownDatabase": true, "portEnv": "PORT", "health": "/q/health/ready"}
```

After changing a dependency: `uv lock && uv export --format requirements-txt --no-dev --no-emit-project -o requirements.lock`. (Bup's Python framework is phase V3-2 of the specification: not available yet.)

## 8. Testing

```bash
uv run pytest --cov          # 57 tests
uv run ruff check . && uv run ruff format --check .
```

Charm is faked by a P-256 key pair whose JWKS the verifier reads; gDown by a fake `neo4j` driver that interprets the four statements. Both stores run the same API tests. `tests/test_conformity.py` checks the lock file and its hashes, Python 3.13, no sensitive file, no Dockerfile, and that inferred plus declared `uses` equal those of `deploy/appspec.json`.

## 9. What maps from gluonify-source, and what does not yet

| gluonify-source (Java) | Here |
|---|---|
| Notes REST API, roles, validation, OpenAPI | ✅ |
| Charm tokens, `/api/auth-config` | ✅ |
| Gdown store (HTTP API in Java) | ✅ with the `neo4j` driver over Bolt with TLS |
| Memory store, health ready/live, `/api/platform` | ✅ |
| Vue UI (Quinoa) | ❌ not ported: serve a built UI with `StaticFiles`, or host it on Field |
| Files store (`/distributed/std`) | ❌ |
| Photon webhooks (`/hooks`), documents with Crystallon | ❌ (no Python client in the SDK yet) |
| Native executable | not applicable: CPython of the node |
| `scripts/rename.py` | ❌: rename `gluonify_source`, the project name and `AUDIENCE` in `config.py` by hand |
