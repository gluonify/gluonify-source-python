# gluonify-source-python

[English](README.md) · **Français** · [Español](README.es.md) · [Italiano](README.it.md) · [Deutsch](README.de.md)

> **Variantes Java.** Le même service en Quarkus existe dans [`gluonify-source`](https://github.com/gluonify/gluonify-source) (Maven) et [`gluonify-source-gradle`](https://github.com/gluonify/gluonify-source-gradle) (Gradle). Celui-ci en est l'équivalent **Python**, dans la mesure où il se transpose.

**Le point de départ d'un service Python sur [Gluonify](https://gluonify.io).** Un petit service complet (des « notes ») construit avec **FastAPI** et **uvicorn** au-dessus du SDK Python de Gluonify ([`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python) : distributions `gluonify` et `gluonify-fastapi`). Il montre, avec du code qui tourne et des tests, comment :

1. faire un **service REST** (validation, rôles, OpenAPI) ;
2. **vérifier les jetons de Charm** et les rôles, et donner à un navigateur de quoi se connecter ;
3. garder les données dans **gDown**, la base graphe de la plateforme (base dédiée, pilote officiel `neo4j` sur Bolt avec TLS) ;
4. exposer les points de **santé** que la plateforme surveille.

> Les applications Python tournent sur Gluonify avec le `python3` de Debian 13 (**CPython 3.13**) de chaque nœud : Bup installe vos dépendances verrouillées dans un venv, signe le code et le venv dans une archive, et le nœud l'exécute dans le même bac à sable que les applications natives. Pas de Dockerfile.

## Sommaire
1. [Démarrer en 5 minutes](#1-démarrer-en-5-minutes)
2. [La carte du projet](#2-la-carte-du-projet)
3. [Faire un service REST](#3-faire-un-service-rest)
4. [Authentification : les jetons de Charm](#4-authentification--les-jetons-de-charm)
5. [Stockage : mémoire ou gDown](#5-stockage--mémoire-ou-gdown)
6. [Configuration](#6-configuration)
7. [Construire et déployer](#7-construire-et-déployer)
8. [Tester](#8-tester)
9. [Ce qui se transpose de gluonify-source, et ce qui ne l'est pas encore](#9-ce-qui-se-transpose-de-gluonify-source-et-ce-qui-ne-lest-pas-encore)

---

## 1. Démarrer en 5 minutes

**Prérequis** : Python 3.13 et [uv](https://docs.astral.sh/uv/). Tant que le SDK n'est pas publié sur PyPI, clonez [`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python) **à côté** de ce dépôt (`../gluonify-plasma-python`) : `pyproject.toml` le prend là.

```bash
git clone https://github.com/gluonify/gluonify-source-python.git
cd gluonify-source-python
uv sync
SOURCE_DEV=1 uv run gluonify-source
```

`SOURCE_DEV=1` donne à toute requête sans jeton une identité « dev » avec tous les rôles (refusée sur la plateforme). Les notes sont en mémoire. Ensuite :

| Adresse | Contenu |
|---|---|
| `/api/notes` | l'API REST (JSON) |
| `/api/platform` | ce que la plateforme a fourni (environnement, services accordés, stockage) |
| `/api/auth-config` | configuration publique de connexion pour une interface web (client et adresses de Charm) |
| `/q/swagger-ui` · `/q/openapi` | documentation interactive et contrat OpenAPI |
| `/q/health/ready` · `/q/health/live` | disponibilité (le stockage répond) et vie |

```bash
curl -s localhost:8080/api/notes -H 'Content-Type: application/json' -d '{"title":"Courses","body":"du pain"}'
curl -s localhost:8080/api/notes
```

## 2. La carte du projet

```
pyproject.toml              le projet : dépendances, commande gluonify-source, ruff, pytest
uv.lock                     le fichier de verrouillage universel (empreintes de chaque fichier de PyPI)
requirements.lock           `uv export` de uv.lock, avec empreintes : ce que Bup installe par `pip install --require-hashes`
gluonify.json               lu par Bup : gdownDatabase, variable du port, chemin de santé (« uses » est déduit des marqueurs du SDK)
deploy/appspec.json         un exemple d'AppSpec pour un déploiement à la main
src/gluonify_source/
  main.py                   build() : create_app du SDK + notes + plateforme + disponibilité ; run() démarre uvicorn
  config.py                 chaque variable lue, avec sa valeur par défaut
  notes/models.py           NewNote (corps validé), Note
  notes/api.py              ← LE MODÈLE D'UNE RESSOURCE REST (à copier)
  notes/store.py            l'interface NoteStore ; MemoryNoteStore, GraphNoteStore (gDown)
  notes/gdown.py            COMMENT JOINDRE gDOWN : le pilote neo4j en dix lignes (TLS seulement, AC de la plateforme)
  notes/stores.py           choisit l'implémentation (SOURCE_STORE) : l'endroit où brancher la vôtre
  platform.py               /api/platform et /api/auth-config
tests/                      Charm simulé par une clé P-256 et son JWKS, gDown par un faux pilote neo4j
```

## 3. Faire un service REST

Lisez [`notes/api.py`](src/gluonify_source/notes/api.py) : c'est le modèle.

1. **Le modèle** : un `BaseModel` pydantic (validé, sérialisé, décrit par OpenAPI).
2. **Le routeur** : `APIRouter(prefix="/api/orders", tags=["Orders"])`, des fonctions `@router.get/post/delete`, les rôles par une dépendance `Annotated[Principal, Depends(require_roles("shop:write"))]`. Incluez-le dans `main.build()`.
3. **Codes HTTP** : 201 + `Location` à la création, 204 sans corps, 400 pour un corps invalide (`{"error": "invalid body", "violations": [...]}`), 401 sans jeton valide, 403 sans le rôle, 404 pour un identifiant inconnu. Les erreurs sont `{"error": "…"}`.
4. **Les tests** : copiez [`tests/test_notes.py`](tests/test_notes.py) : `charm.bearer("shop:read")` fabrique un jeton de test signé.

Le stockage est derrière [`NoteStore`](src/gluonify_source/notes/store.py) : implémentez-la et ajoutez un cas dans [`stores.py`](src/gluonify_source/notes/stores.py).

## 4. Authentification : les jetons de Charm

L'API vérifie les jetons porteurs émis par **Charm** (JWT, ES256) avec `require_roles` de `gluonify-fastapi` : rien à configurer sur la plateforme. Le SDK lit les clés de Charm à `GLUONIFY_SERVICE_CHARM_URL`, vérifie l'émetteur `GLUONIFY_OIDC_ISSUER` et l'audience `GLUONIFY_OIDC_AUDIENCE` (`gluonify-source` par défaut), et lit les rôles dans la revendication `roles` (`source:read`, `source:write`). Une interface web se connecte chez Charm lui-même (code d'autorisation + PKCE, le kit `@gluonify/ui`) grâce à `GET /api/auth-config` ; le mot de passe n'est jamais saisi dans cette application.

## 5. Stockage : mémoire ou gDown

`SOURCE_STORE=auto` (défaut) utilise **gDown** quand la plateforme fournit une base dédiée (`GLUONIFY_GDOWN_DATABASE`, venant de `"gdownDatabase": true`), la mémoire sinon. `GraphNoteStore` exécute quatre instructions Cypher paramétrées sur la base dédiée avec le pilote officiel **`neo4j`**. Il n'y a pas de client gDown dans le SDK : le pilote suffit, et c'est son installation (ou celle de **`neomodel`**, un OGM au-dessus, si vous préférez des classes associées) qui fait déduire `?gdown` à Bup.

**Comment joindre gDown** ([`notes/gdown.py`](src/gluonify_source/notes/gdown.py), montré ici avec `os.environ`) : Bolt est **en TLS seulement**, et la plateforme injecte `GLUONIFY_GDOWN_BOLT_URL` (`bolt+s://` ou `neo4j+s://`), `GLUONIFY_GDOWN_DATABASE`, `GLUONIFY_GDOWN_USER`, `GLUONIFY_GDOWN_PASSWORD` et `GLUONIFY_GDOWN_CA_FILE` (le PEM de l'AC).

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

Le pilote refuse une AC personnalisée avec un schéma `+s`, d'où `encrypted=True` avec `TrustCustomCAs` : c'est toujours du TLS, vérifié par l'AC de la plateforme. Une adresse `bolt://` sans TLS est refusée, sauf avec `SOURCE_DEV=1` (un gDown local), que la plateforme refuse.

## 6. Configuration

Toute la configuration vient de l'environnement (la plateforme, ou le coffre Top) ; rien de secret ne va dans Git.

| Variable | Défaut | Rôle |
|---|---|---|
| `SOURCE_STORE` | `auto` | `auto`, `memory` ou `gdown` |
| `SOURCE_DEV` | absente | `1` : identité de développement pour les requêtes sans jeton (refusée sur la plateforme) |
| `PORT` | `8080` | port d'écoute (toujours `0.0.0.0`) |
| `GLUONIFY_SOURCE_OIDC_ISSUER`, `GLUONIFY_SOURCE_OIDC_AUDIENCE`, `GLUONIFY_SOURCE_OIDC_CLIENT_ID` | valeurs `GLUONIFY_OIDC_*` de la plateforme | l'emportent sur les valeurs de la plateforme |
| `GLUONIFY_SOURCE_CHARM_PUBLIC_URL` | `GLUONIFY_OIDC_PUBLIC_URL`, sinon déduite de l'émetteur | adresse publique de Charm pour le navigateur |
| `SOURCE_AUTH_SCOPE` | `openid` | portée de la connexion du navigateur |
| `GLUONIFY_GDOWN_BOLT_URL`, `GLUONIFY_GDOWN_CA_FILE` | injectées par la plateforme | adresse Bolt de gDown (`bolt+s://`, TLS seulement) et AC de confiance |

## 7. Construire et déployer

Bup reconnaît un projet Python à son `pyproject.toml`, exige le fichier de verrouillage, analyse le code (SonarQube, règles d'appels dangereux, `pip-audit`), installe `requirements.lock` par `pip install --require-hashes` dans un venv, et signe le code et le venv dans un gzip. **`uses` est déduit** des marqueurs `[gluonify.uses]` des distributions du SDK installées dans ce venv (`gluonify` déclare `charm` ; la distribution `neo4j` fait déduire `gdown`) ; `gluonify.json` ne dit donc que ce qui ne se déduit pas :

```json
{"gdownDatabase": true, "portEnv": "PORT", "health": "/q/health/ready"}
```

Après un changement de dépendance : `uv lock && uv export --format requirements-txt --no-dev --no-emit-project -o requirements.lock`. (Le framework Python de Bup est la phase V3-2 de la spécification : pas encore disponible.)

## 8. Tester

```bash
uv run pytest --cov          # 57 tests
uv run ruff check . && uv run ruff format --check .
```

Charm est simulé par une paire de clés P-256 dont le vérificateur lit le JWKS ; gDown par un faux pilote `neo4j` qui interprète les quatre instructions. Les deux stockages passent les mêmes tests d'API. `tests/test_conformity.py` vérifie le fichier de verrouillage et ses empreintes, Python 3.13, l'absence de fichier sensible et de Dockerfile, et que les `uses` déduits et déclarés égalent ceux de `deploy/appspec.json`.

## 9. Ce qui se transpose de gluonify-source, et ce qui ne l'est pas encore

| gluonify-source (Java) | Ici |
|---|---|
| API REST des notes, rôles, validation, OpenAPI | ✅ |
| Jetons de Charm, `/api/auth-config` | ✅ |
| Stockage Gdown (API HTTP en Java) | ✅ par le pilote `neo4j` sur Bolt avec TLS |
| Stockage en mémoire, santé ready/live, `/api/platform` | ✅ |
| Interface Vue (Quinoa) | ❌ non reprise : servir une interface construite par `StaticFiles`, ou l'héberger sur Field |
| Stockage en fichiers (`/distributed/std`) | ❌ |
| Webhooks de Photon (`/hooks`), documents avec Crystallon | ❌ (pas encore de client Python dans le SDK) |
| Exécutable natif | sans objet : CPython du nœud |
| `scripts/rename.py` | ❌ : renommer `gluonify_source`, le nom du projet et `AUDIENCE` de `config.py` à la main |
