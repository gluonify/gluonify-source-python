# plan.md: what is left to do (gluonify-source-python)

1. Switch to the published SDK once `gluonify` is on PyPI: remove `[tool.uv.sources]`, `uv lock`, regenerate `requirements.lock` (today the SDK line is `-e ../gluonify-plasma-python/...` without hashes, which `pip install --require-hashes` refuses).
2. e2e on a real cluster (python.md V3-4, calqued on `gluonify-chamber/scripts/e2e-source.sh`), once Bup has the `python` framework (V3-2) and Strange/Higgs place Python apps (V3-3).
3. Check the Bolt path end to end (TLS, platform CA) once the platform injects `GLUONIFY_GDOWN_BOLT_URL` and `GLUONIFY_GDOWN_CA_FILE`.
4. Port the remaining parts of gluonify-source: Photon webhooks with an idempotent ledger, the files store (`/distributed/std`), documents with Crystallon (needs a Python client), the Vue UI (multilingual en/fr/es/it/de, served by `StaticFiles` or Field), `scripts/rename.py`.
5. Sites (gluonify-codex/sites): a page for the Python starter (V3-5).
