"""What Bup will check (python.md § 3 bis.3), on our side, plus the uses inferred from the SDK markers."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from gluonify import markers

ROOT = Path(__file__).resolve().parents[1]


def test_lock_file_present_with_hashes() -> None:
    lock = (ROOT / "uv.lock").read_text()
    assert "sha256:" in lock
    req = (ROOT / "requirements.lock").read_text()
    assert "--hash=sha256:" in req


def test_python_313() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert data["project"]["requires-python"] == ">=3.13"
    assert (ROOT / ".python-version").read_text().strip() == "3.13"


def test_no_sensitive_files() -> None:
    bad = [p for p in ROOT.rglob("*") if ".venv" not in p.parts and (p.name == ".env" or p.suffix in {".pem", ".p12", ".jks"})]
    assert bad == []


def test_depends_on_the_sdk_and_the_neo4j_driver() -> None:
    deps = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["dependencies"]
    names = {d.split("=")[0].split(">")[0] for d in deps}
    assert {"gluonify[fastapi]", "neo4j"} <= names  # the FastAPI integration is the extra of gluonify, not a distribution
    assert not any(n.startswith("gluonify-") for n in names)


def test_no_dockerfile() -> None:
    assert not list(ROOT.glob("Dockerfile*"))


def test_uses_inferred_plus_declared_equal_the_appspec() -> None:
    site = next((ROOT / ".venv/lib").glob("python3.*/site-packages"))
    inferred = markers.infer(site)
    assert set(inferred.services) == {"charm", "gdown"}
    assert inferred.sources == {"charm": ("gluonify",), "gdown": ("neo4j",)}  # gdown inferred from the neo4j driver
    declared = json.loads((ROOT / "gluonify.json").read_text()).get("uses", [])
    effective = {u.lstrip("?") for u in inferred.uses(declared)}
    spec = json.loads((ROOT / "deploy/appspec.json").read_text())
    assert effective == set(spec["uses"])
    assert spec["gdownDatabase"] is True


def test_listens_on_all_interfaces() -> None:
    from gluonify.fastapi import app as sdk_app

    assert '"0.0.0.0"' in Path(sdk_app.__file__).read_text()
