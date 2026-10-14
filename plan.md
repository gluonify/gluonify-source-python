# plan.md: what is left to do (gluonify-source-python)

1. Switch to the published SDK once `gluonify` is on PyPI: remove `[tool.uv.sources]`, `uv lock`, regenerate `requirements.lock` (today the SDK line is `-e ../gluonify-plasma-python/...` without hashes, which `pip install --require-hashes` refuses).
2. Done 2026-10-14: e2e on a real cluster (python.md V3-4), `gluonify-chamber/scripts/e2e-source-python.sh`, 29/29 in arm64 (Bolt+TLS path included). Left: run it on quark (x86_64), and through the real Bup build once item 1 is done.
3. Port the remaining parts of gluonify-source: Photon webhooks with an idempotent ledger, the files store (`/distributed/std`), documents with Crystallon (needs a Python client), the Vue UI (multilingual en/fr/es/it/de, served by `StaticFiles` or Field), `scripts/rename.py`.
4. Sites (gluonify-codex/sites): a page for the Python starter (V3-5).
