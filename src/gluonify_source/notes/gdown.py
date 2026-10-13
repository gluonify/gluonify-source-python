"""How to reach gDown: the official neo4j driver, nothing else (no SDK client). The platform injects every value
("gdownDatabase": true); Bolt is TLS only. Installing ``neo4j`` (or ``neomodel``) is what makes Bup infer ``?gdown``."""

from __future__ import annotations

from collections.abc import Mapping

import neo4j


def gdown_driver(env: Mapping[str, str], dev: bool = False) -> neo4j.Driver:
    url = env["GLUONIFY_GDOWN_BOLT_URL"]  # bolt+s://… or neo4j+s://…
    scheme, rest = url.split("://", 1)
    if not scheme.endswith("+s") and not dev:
        raise RuntimeError("gDown: TLS required (bolt+s:// or neo4j+s://)")
    auth = (env["GLUONIFY_GDOWN_USER"], env["GLUONIFY_GDOWN_PASSWORD"])
    ca = env.get("GLUONIFY_GDOWN_CA_FILE")
    if ca and scheme.endswith("+s"):  # the driver refuses a custom CA with "+s": same TLS, explicit trust
        return neo4j.GraphDatabase.driver(
            f"{scheme[:-2]}://{rest}", auth=auth, encrypted=True, trusted_certificates=neo4j.TrustCustomCAs(ca)
        )
    return neo4j.GraphDatabase.driver(url, auth=auth)
