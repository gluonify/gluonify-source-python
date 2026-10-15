# CLAUDE.md: guidance for an AI assistant working on this project

This repository is the **starting point** for a Python (FastAPI + uvicorn) service that runs on Gluonify, the Python counterpart of `gluonify-source`. Read `README.md` first (also `README.fr.md`, `README.es.md`, `README.it.md`, `README.de.md`: keep the five in step). This is an **"en" repository**: code, comments, this file and commit messages in English.

Shared context for every gluonify-* repository: `/Users/a/dev/gluonify/CLAUDE.md` (in French).

## Commands
- `uv sync`, then `SOURCE_DEV=1 uv run gluonify-source` (http://localhost:8080, development identity with all roles, notes in memory).
- `uv run pytest --cov` (57 tests, coverage gate 90 %), `uv run ruff check . && uv run ruff format --check .`.
- After any dependency change: `uv lock` then `uv export --format requirements-txt --no-dev --no-emit-project -o requirements.lock` (Bup installs that file with `pip install --require-hashes`); commit both.
- The SDK (`gluonify[fastapi]`: the distribution `gluonify` with its extra `fastapi`) comes from `../gluonify-plasma-python` (path sources in `pyproject.toml`) until it is on PyPI; then remove `[tool.uv.sources]` and lock again.

## Platform rules
- Python 3.13 (CPython of Debian 13 on the nodes). No Dockerfile. A lock file with hashes is mandatory. No `.env`, `*.pem`, `*.p12`, `*.jks`. Listen on `0.0.0.0:$PORT`, one process. Health `/health/ready` and `/health/live` (never `/q/`, the Quarkus namespace) (liveness depends on nothing external). `tests/test_conformity.py` checks these.
- **All configuration comes from the environment** (platform or Top). Never hard-code an address, a port or a password. Charm and gDown need NO configuration: the SDK finds them.
- `SOURCE_DEV` is for local development only; `create_app` refuses it on the platform. Do not weaken that.
- **`uses` is inferred by Bup** from the `[gluonify.uses]` markers of the installed SDK distributions (`gluonify` -> `charm`; the `neo4j` distribution -> `gdown`): `gluonify.json` declares only what cannot be inferred (`gdownDatabase`, `portEnv`, `health`). Declared plus inferred must equal the `uses` of `deploy/appspec.json` (checked by a test).
- Roles: `source:read`, `source:write` from the `roles` claim. Errors are `{"error": "..."}`; invalid bodies are 400 with `violations`.
- gDown: the official `neo4j` driver directly (`notes/gdown.py`, about ten lines, no SDK client, no HTTP fallback): `GLUONIFY_GDOWN_BOLT_URL` with TLS only, the platform CA `GLUONIFY_GDOWN_CA_FILE` through `TrustCustomCAs` with `encrypted=True`; plain `bolt://` only with `SOURCE_DEV=1`. Keep the snippet of the five READMEs and of the SDK README identical to that file.

## Where to change what
`notes/api.py` = the model of a REST resource; `notes/store.py` + `notes/stores.py` = where to plug in a store; `notes/gdown.py` = how to reach gDown; `config.py` = every variable; `platform.py` = platform info and browser sign-in configuration; `main.py` = wiring.
