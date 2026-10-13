# gluonify-source-python

[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · [Italiano](README.it.md) · **Deutsch**

> **Java-Varianten.** Derselbe Dienst in Quarkus liegt in [`gluonify-source`](https://github.com/gluonify/gluonify-source) (Maven) und [`gluonify-source-gradle`](https://github.com/gluonify/gluonify-source-gradle) (Gradle). Dieser hier ist sein **Python**-Gegenstück, soweit es sich übertragen lässt.

**Der Ausgangspunkt für einen Python-Dienst auf [Gluonify](https://gluonify.io).** Ein kleiner, vollständiger Dienst („Notizen“), gebaut mit **FastAPI** und **uvicorn** auf dem Python-SDK von Gluonify ([`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python): Distributionen `gluonify` und `gluonify-fastapi`). Er zeigt mit lauffähigem Code und Tests, wie man:

1. einen **REST-Dienst** baut (Validierung, Rollen, OpenAPI);
2. **Charm-Token prüft** und Rollen kontrolliert, und einem Browser gibt, was er zur Anmeldung braucht;
3. Daten in **gDown** hält, der Graphdatenbank der Plattform (eigene Datenbank, offizieller `neo4j`-Treiber über Bolt mit TLS);
4. die **Health**-Endpunkte bereitstellt, die die Plattform überwacht.

> Python-Anwendungen laufen auf Gluonify mit dem `python3` von Debian 13 (**CPython 3.13**) jedes Knotens: Bup installiert die gesperrten Abhängigkeiten in ein venv, signiert Code und venv in einem Archiv, und der Knoten führt es in derselben Sandbox aus wie native Anwendungen. Kein Dockerfile.

## Inhalt
1. [In 5 Minuten starten](#1-in-5-minuten-starten)
2. [Die Projektkarte](#2-die-projektkarte)
3. [Einen REST-Dienst bauen](#3-einen-rest-dienst-bauen)
4. [Authentifizierung: Charm-Token](#4-authentifizierung-charm-token)
5. [Speicherung: Speicher oder gDown](#5-speicherung-speicher-oder-gdown)
6. [Konfiguration](#6-konfiguration)
7. [Bauen und bereitstellen](#7-bauen-und-bereitstellen)
8. [Testen](#8-testen)
9. [Was aus gluonify-source übertragen ist, und was noch nicht](#9-was-aus-gluonify-source-übertragen-ist-und-was-noch-nicht)

---

## 1. In 5 Minuten starten

**Voraussetzungen**: Python 3.13 und [uv](https://docs.astral.sh/uv/). Solange das SDK nicht auf PyPI veröffentlicht ist, klonen Sie [`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python) **neben** dieses Repository (`../gluonify-plasma-python`): `pyproject.toml` nimmt es von dort.

```bash
git clone https://github.com/gluonify/gluonify-source-python.git
cd gluonify-source-python
uv sync
SOURCE_DEV=1 uv run gluonify-source
```

`SOURCE_DEV=1` gibt jeder Anfrage ohne Token eine „dev“-Identität mit allen Rollen (auf der Plattform abgelehnt). Die Notizen liegen im Speicher. Danach:

| Adresse | Inhalt |
|---|---|
| `/api/notes` | die REST-API (JSON) |
| `/api/platform` | was die Plattform bereitgestellt hat (Umgebung, gewährte Dienste, Speicherung) |
| `/api/auth-config` | öffentliche Anmeldekonfiguration für eine Weboberfläche (Client und Adressen von Charm) |
| `/q/swagger-ui` · `/q/openapi` | interaktive Dokumentation und OpenAPI-Vertrag |
| `/q/health/ready` · `/q/health/live` | Bereitschaft (die Speicherung antwortet) und Lebendigkeit |

```bash
curl -s localhost:8080/api/notes -H 'Content-Type: application/json' -d '{"title":"Einkauf","body":"Brot"}'
curl -s localhost:8080/api/notes
```

## 2. Die Projektkarte

```
pyproject.toml              das Projekt: Abhängigkeiten, Befehl gluonify-source, ruff, pytest
uv.lock                     die universelle Sperrdatei (Prüfsummen jeder Datei von PyPI)
requirements.lock           `uv export` von uv.lock, mit Prüfsummen: was Bup mit `pip install --require-hashes` installiert
gluonify.json               von Bup gelesen: gdownDatabase, Port-Variable, Health-Pfad („uses“ wird aus den Markern des SDK abgeleitet)
deploy/appspec.json         ein Beispiel-AppSpec für eine Bereitstellung von Hand
src/gluonify_source/
  main.py                   build(): create_app des SDK + Notizen + Plattform + Bereitschaft; run() startet uvicorn
  config.py                 jede gelesene Variable mit ihrem Standardwert
  notes/models.py           NewNote (validierter Body), Note
  notes/api.py              ← DAS MODELL EINER REST-RESSOURCE (zum Kopieren)
  notes/store.py            die Schnittstelle NoteStore; MemoryNoteStore, GraphNoteStore (gDown)
  notes/gdown.py            WIE MAN gDOWN ERREICHT: der neo4j-Treiber in zehn Zeilen (nur TLS, CA der Plattform)
  notes/stores.py           wählt die Implementierung (SOURCE_STORE): der Ort für Ihre eigene
  platform.py               /api/platform und /api/auth-config
tests/                      Charm durch einen P-256-Schlüssel und sein JWKS simuliert, gDown durch einen falschen neo4j-Treiber
```

## 3. Einen REST-Dienst bauen

Lesen Sie [`notes/api.py`](src/gluonify_source/notes/api.py): es ist das Modell.

1. **Das Modell**: ein pydantic-`BaseModel` (validiert, serialisiert, von OpenAPI beschrieben).
2. **Der Router**: `APIRouter(prefix="/api/orders", tags=["Orders"])`, Funktionen mit `@router.get/post/delete`, Rollen über eine Abhängigkeit `Annotated[Principal, Depends(require_roles("shop:write"))]`. Binden Sie ihn in `main.build()` ein.
3. **HTTP-Codes**: 201 + `Location` beim Anlegen, 204 ohne Body, 400 bei ungültigem Body (`{"error": "invalid body", "violations": [...]}`), 401 ohne gültiges Token, 403 ohne die Rolle, 404 für eine unbekannte Kennung. Fehler sind `{"error": "…"}`.
4. **Die Tests**: kopieren Sie [`tests/test_notes.py`](tests/test_notes.py): `charm.bearer("shop:read")` erzeugt ein signiertes Testtoken.

Die Speicherung liegt hinter [`NoteStore`](src/gluonify_source/notes/store.py): implementieren Sie sie und ergänzen Sie einen Fall in [`stores.py`](src/gluonify_source/notes/stores.py).

## 4. Authentifizierung: Charm-Token

Die API prüft von **Charm** ausgestellte Bearer-Token (JWT, ES256) mit `require_roles` aus `gluonify-fastapi`: auf der Plattform ist nichts zu konfigurieren. Das SDK liest die Schlüssel von Charm unter `GLUONIFY_SERVICE_CHARM_URL`, prüft den Aussteller `GLUONIFY_OIDC_ISSUER` und die Zielgruppe `GLUONIFY_OIDC_AUDIENCE` (standardmäßig `gluonify-source`) und liest die Rollen aus dem Claim `roles` (`source:read`, `source:write`). Eine Weboberfläche meldet sich bei Charm selbst an (Autorisierungscode + PKCE, das Kit `@gluonify/ui`) über `GET /api/auth-config`; das Passwort wird nie in diese Anwendung eingegeben.

## 5. Speicherung: Speicher oder gDown

`SOURCE_STORE=auto` (Standard) verwendet **gDown**, wenn die Plattform eine eigene Datenbank bereitstellt (`GLUONIFY_GDOWN_DATABASE`, aus `"gdownDatabase": true`), sonst den Speicher. `GraphNoteStore` führt vier parametrisierte Cypher-Anweisungen auf der eigenen Datenbank mit dem offiziellen **`neo4j`**-Treiber aus. Das SDK hat keinen gDown-Client: der Treiber genügt, und seine Installation (oder die von **`neomodel`**, einem OGM darauf, wenn Sie abgebildete Klassen bevorzugen) lässt Bup `?gdown` ableiten.

**Wie man gDown erreicht** ([`notes/gdown.py`](src/gluonify_source/notes/gdown.py), hier mit `os.environ` gezeigt): Bolt ist **nur mit TLS** möglich, und die Plattform injiziert `GLUONIFY_GDOWN_BOLT_URL` (`bolt+s://` oder `neo4j+s://`), `GLUONIFY_GDOWN_DATABASE`, `GLUONIFY_GDOWN_USER`, `GLUONIFY_GDOWN_PASSWORD` und `GLUONIFY_GDOWN_CA_FILE` (das PEM der CA).

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

Der Treiber lehnt eine eigene CA mit einem `+s`-Schema ab, daher `encrypted=True` mit `TrustCustomCAs`: weiterhin TLS, geprüft gegen die CA der Plattform. Eine `bolt://`-Adresse ohne TLS wird abgelehnt, außer mit `SOURCE_DEV=1` (ein lokales gDown), das die Plattform ablehnt.

## 6. Konfiguration

Die gesamte Konfiguration kommt aus der Umgebung (der Plattform oder dem Tresor Top); nichts Geheimes gehört in Git.

| Variable | Standard | Rolle |
|---|---|---|
| `SOURCE_STORE` | `auto` | `auto`, `memory` oder `gdown` |
| `SOURCE_DEV` | nicht gesetzt | `1`: Entwicklungsidentität für Anfragen ohne Token (auf der Plattform abgelehnt) |
| `PORT` | `8080` | Port (immer `0.0.0.0`) |
| `GLUONIFY_SOURCE_OIDC_ISSUER`, `GLUONIFY_SOURCE_OIDC_AUDIENCE`, `GLUONIFY_SOURCE_OIDC_CLIENT_ID` | Plattformwerte `GLUONIFY_OIDC_*` | haben Vorrang vor den Plattformwerten |
| `GLUONIFY_SOURCE_CHARM_PUBLIC_URL` | `GLUONIFY_OIDC_PUBLIC_URL`, sonst aus dem Aussteller abgeleitet | öffentliche Adresse von Charm für den Browser |
| `SOURCE_AUTH_SCOPE` | `openid` | Scope der Browser-Anmeldung |
| `GLUONIFY_GDOWN_BOLT_URL`, `GLUONIFY_GDOWN_CA_FILE` | von der Plattform injiziert | Bolt-Adresse von gDown (`bolt+s://`, nur TLS) und die vertrauenswürdige CA |

## 7. Bauen und bereitstellen

Bup erkennt ein Python-Projekt an seiner `pyproject.toml`, verlangt die Sperrdatei, analysiert den Code (SonarQube, Regeln für gefährliche Aufrufe, `pip-audit`), installiert `requirements.lock` mit `pip install --require-hashes` in ein venv und signiert Code und venv in einem gzip. **`uses` wird abgeleitet** aus den Markern `[gluonify.uses]` der in diesem venv installierten SDK-Distributionen (`gluonify` deklariert `charm`; die Distribution `neo4j` lässt `gdown` ableiten); `gluonify.json` enthält daher nur, was sich nicht ableiten lässt:

```json
{"gdownDatabase": true, "portEnv": "PORT", "health": "/q/health/ready"}
```

Nach einer Änderung der Abhängigkeiten: `uv lock && uv export --format requirements-txt --no-dev --no-emit-project -o requirements.lock`. (Das Python-Framework von Bup ist Phase V3-2 der Spezifikation: noch nicht verfügbar.)

## 8. Testen

```bash
uv run pytest --cov          # 57 Tests
uv run ruff check . && uv run ruff format --check .
```

Charm wird durch ein P-256-Schlüsselpaar simuliert, dessen JWKS der Prüfer liest; gDown durch einen falschen `neo4j`-Treiber, der die vier Anweisungen interpretiert. Beide Speicherungen durchlaufen dieselben API-Tests. `tests/test_conformity.py` prüft die Sperrdatei und ihre Prüfsummen, Python 3.13, das Fehlen sensibler Dateien und eines Dockerfiles, und dass abgeleitete plus deklarierte `uses` denen von `deploy/appspec.json` entsprechen.

## 9. Was aus gluonify-source übertragen ist, und was noch nicht

| gluonify-source (Java) | Hier |
|---|---|
| REST-API der Notizen, Rollen, Validierung, OpenAPI | ✅ |
| Charm-Token, `/api/auth-config` | ✅ |
| Gdown-Speicherung (HTTP-API in Java) | ✅ mit dem `neo4j`-Treiber über Bolt mit TLS |
| Speicher im Arbeitsspeicher, Health ready/live, `/api/platform` | ✅ |
| Vue-Oberfläche (Quinoa) | ❌ nicht übertragen: eine gebaute Oberfläche mit `StaticFiles` ausliefern oder auf Field hosten |
| Dateispeicherung (`/distributed/std`) | ❌ |
| Photon-Webhooks (`/hooks`), Dokumente mit Crystallon | ❌ (noch kein Python-Client im SDK) |
| Native ausführbare Datei | entfällt: CPython des Knotens |
| `scripts/rename.py` | ❌: `gluonify_source`, den Projektnamen und `AUDIENCE` in `config.py` von Hand umbenennen |
