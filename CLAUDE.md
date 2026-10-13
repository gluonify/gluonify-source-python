# CLAUDE.md: guidance for an AI assistant working on this project

This repository is the **starting point** for a Python (FastAPI + uvicorn) service that runs on Gluonify, the Python counterpart of `gluonify-source`. Read `README.md` first (also `README.fr.md`, `README.es.md`, `README.it.md`, `README.de.md`: keep the five in step). This is an **"en" repository**: code, comments, this file and commit messages in English.

Shared context for every gluonify-* repository: `/Users/a/dev/gluonify/CLAUDE.md` (in French).

## Commands
- `uv sync`, then `SOURCE_DEV=1 uv run gluonify-source` (http://localhost:8080, development identity with all roles, notes in memory).
- `uv run pytest --cov` (47 tests, coverage gate 90 %), `uv run ruff check . && uv run ruff format --check .`.
- After any dependency change: `uv lock` then `uv export --format requirements-txt --no-dev --no-emit-project -o requirements.lock` (Bup installs that file with `pip install --require-hashes`); commit both.
- The SDK (`gluonify`, `gluonify-fastapi`) comes from `../gluonify-plasma-python` (path sources in `pyproject.toml`) until it is on PyPI; then remove `[tool.uv.sources]` and lock again.

## Platform rules
- Python 3.13 (CPython of Debian 13 on the nodes). No Dockerfile. A lock file with hashes is mandatory. No `.env`, `*.pem`, `*.p12`, `*.jks`. Listen on `0.0.0.0:$PORT`, one process. Health `/q/health/ready` and `/q/health/live` (liveness depends on nothing external). `tests/test_conformity.py` checks these.
- **All configuration comes from the environment** (platform or Top). Never hard-code an address, a port or a password. Charm and gDown need NO configuration: the SDK finds them.
- `SOURCE_DEV` is for local development only; `create_app` refuses it on the platform. Do not weaken that.
- **`uses` is inferred by Bup** from the `[gluonify.uses]` markers of the installed SDK distributions (`gluonify` -> `charm`, `gdown`): `gluonify.json` declares only what cannot be inferred (`gdownDatabase`, `portEnv`, `health`). Declared plus inferred must equal the `uses` of `deploy/appspec.json` (checked by a test).
- Roles: `source:read`, `source:write` from the `roles` claim. Errors are `{"error": "..."}`; invalid bodies are 400 with `violations`.
- Known open point: the platform starts gDown with Bolt disabled (see README §5).

## Where to change what
`notes/api.py` = the model of a REST resource; `notes/store.py` + `notes/stores.py` = where to plug in a store; `config.py` = every variable; `platform.py` = platform info and browser sign-in configuration; `main.py` = wiring.
