# gluonify-source-python

[English](README.md) · [Français](README.fr.md) · [Español](README.es.md) · **Italiano** · [Deutsch](README.de.md)

> **Varianti Java.** Lo stesso servizio in Quarkus si trova in [`gluonify-source`](https://github.com/gluonify/gluonify-source) (Maven) e [`gluonify-source-gradle`](https://github.com/gluonify/gluonify-source-gradle) (Gradle). Questo ne è l'equivalente **Python**, per quanto si possa trasporre.

**Il punto di partenza di un servizio Python su [Gluonify](https://gluonify.io).** Un servizio piccolo e completo (delle «note») costruito con **FastAPI** e **uvicorn** sopra l'SDK Python di Gluonify ([`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python): distribuzione `gluonify` con il suo extra `fastapi`, `pip install "gluonify[fastapi]"`). Mostra, con codice funzionante e test, come:

1. creare un **servizio REST** (validazione, ruoli, OpenAPI);
2. **verificare i token di Charm** e i ruoli, e dare a un browser ciò che serve per accedere;
3. tenere i dati in **gDown**, il database a grafo della piattaforma (database dedicato, driver ufficiale `neo4j` su Bolt con TLS);
4. esporre gli endpoint di **salute** che la piattaforma sorveglia.

> Le applicazioni Python girano su Gluonify con il `python3` di Debian 13 (**CPython 3.13**) di ogni nodo: Bup installa le dipendenze bloccate in un venv, firma codice e venv in un archivio, e il nodo lo esegue nella stessa sandbox delle applicazioni native. Nessun Dockerfile.

## Indice
1. [Iniziare in 5 minuti](#1-iniziare-in-5-minuti)
2. [La mappa del progetto](#2-la-mappa-del-progetto)
3. [Creare un servizio REST](#3-creare-un-servizio-rest)
4. [Autenticazione: i token di Charm](#4-autenticazione-i-token-di-charm)
5. [Archiviazione: memoria o gDown](#5-archiviazione-memoria-o-gdown)
6. [Configurazione](#6-configurazione)
7. [Costruire e distribuire](#7-costruire-e-distribuire)
8. [Testare](#8-testare)
9. [Cosa si traspone da gluonify-source, e cosa non ancora](#9-cosa-si-traspone-da-gluonify-source-e-cosa-non-ancora)

---

## 1. Iniziare in 5 minuti

**Prerequisiti**: Python 3.13 e [uv](https://docs.astral.sh/uv/). Finché l'SDK non è pubblicato su PyPI, clonate [`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python) **accanto** a questo repository (`../gluonify-plasma-python`): `pyproject.toml` lo prende da lì.

```bash
git clone https://github.com/gluonify/gluonify-source-python.git
cd gluonify-source-python
uv sync
SOURCE_DEV=1 uv run gluonify-source
```

`SOURCE_DEV=1` dà a ogni richiesta senza token un'identità «dev» con tutti i ruoli (rifiutata sulla piattaforma). Le note sono in memoria. Poi:

| Indirizzo | Contenuto |
|---|---|
| `/api/notes` | l'API REST (JSON) |
| `/api/platform` | ciò che la piattaforma ha fornito (ambiente, servizi concessi, archiviazione) e la chiave Top `GREETING` (`greeting`, letta con `Top.get`) |
| `/api/auth-config` | configurazione pubblica di accesso per un'interfaccia web (client e indirizzi di Charm) |
| `/q/swagger-ui` · `/q/openapi` | documentazione interattiva e contratto OpenAPI |
| `/q/health/ready` · `/q/health/live` | disponibilità (l'archiviazione risponde) e vita |

```bash
curl -s localhost:8080/api/notes -H 'Content-Type: application/json' -d '{"title":"Spesa","body":"pane"}'
curl -s localhost:8080/api/notes
```

## 2. La mappa del progetto

```
pyproject.toml              il progetto: dipendenze, comando gluonify-source, ruff, pytest
uv.lock                     il file di blocco universale (impronte di ogni file di PyPI)
requirements.lock           `uv export` di uv.lock, con impronte: ciò che Bup installa con `pip install --require-hashes`
gluonify.json               letto da Bup: gdownDatabase, variabile della porta, percorso di salute («uses» è dedotto dai marcatori dell'SDK)
deploy/appspec.json         un esempio di AppSpec per una distribuzione manuale
src/gluonify_source/
  main.py                   build(): create_app dell'SDK + note + piattaforma + disponibilità; run() avvia uvicorn
  config.py                 ogni variabile letta, con il suo valore predefinito
  notes/models.py           NewNote (corpo validato), Note
  notes/api.py              ← IL MODELLO DI UNA RISORSA REST (da copiare)
  notes/store.py            l'interfaccia NoteStore; MemoryNoteStore, GraphNoteStore (gDown)
  notes/gdown.py            COME RAGGIUNGERE gDOWN: il driver neo4j in dieci righe (solo TLS, CA della piattaforma)
  notes/stores.py           sceglie l'implementazione (SOURCE_STORE): il punto dove collegare la vostra
  platform.py               /api/platform e /api/auth-config
tests/                      Charm simulato da una chiave P-256 e il suo JWKS, gDown da un falso driver neo4j
```

## 3. Creare un servizio REST

Leggete [`notes/api.py`](src/gluonify_source/notes/api.py): è il modello.

1. **Il modello**: un `BaseModel` di pydantic (validato, serializzato, descritto da OpenAPI).
2. **Il router**: `APIRouter(prefix="/api/orders", tags=["Orders"])`, funzioni `@router.get/post/delete`, ruoli con una dipendenza `Annotated[Principal, Depends(require_roles("shop:write"))]`. Includetelo in `main.build()`.
3. **Codici HTTP**: 201 + `Location` alla creazione, 204 senza corpo, 400 per un corpo non valido (`{"error": "invalid body", "violations": [...]}`), 401 senza token valido, 403 senza il ruolo, 404 per un identificatore sconosciuto. Gli errori sono `{"error": "…"}`.
4. **I test**: copiate [`tests/test_notes.py`](tests/test_notes.py): `charm.bearer("shop:read")` crea un token di test firmato.

L'archiviazione sta dietro [`NoteStore`](src/gluonify_source/notes/store.py): implementatela e aggiungete un caso in [`stores.py`](src/gluonify_source/notes/stores.py).

## 4. Autenticazione: i token di Charm

L'API verifica i token bearer emessi da **Charm** (JWT, ES256) con `require_roles` di `gluonify.fastapi`: niente da configurare sulla piattaforma. L'SDK legge le chiavi di Charm da `GLUONIFY_SERVICE_CHARM_URL`, controlla l'emittente `GLUONIFY_OIDC_ISSUER` e l'audience `GLUONIFY_OIDC_AUDIENCE` (`gluonify-source` per impostazione predefinita), e legge i ruoli dal claim `roles` (`source:read`, `source:write`). Un'interfaccia web accede presso Charm stesso (codice di autorizzazione + PKCE, il kit `@gluonify/ui`) grazie a `GET /api/auth-config`; la password non viene mai digitata in questa applicazione.

## 5. Archiviazione: memoria o gDown

`SOURCE_STORE=auto` (predefinito) usa **gDown** quando la piattaforma fornisce un database dedicato (`GLUONIFY_GDOWN_DATABASE`, da `"gdownDatabase": true`), altrimenti la memoria. `GraphNoteStore` esegue quattro istruzioni Cypher parametrizzate sul database dedicato con il driver ufficiale **`neo4j`**. Nell'SDK non c'è un client gDown: basta il driver, ed è la sua installazione (o quella di **`neomodel`**, un OGM sopra di esso, se preferite classi mappate) a far dedurre `?gdown` a Bup.

**Come raggiungere gDown** ([`notes/gdown.py`](src/gluonify_source/notes/gdown.py), mostrato qui con `os.environ`): Bolt è **solo TLS**, e la piattaforma inietta `GLUONIFY_GDOWN_BOLT_URL` (`bolt+s://` o `neo4j+s://`), `GLUONIFY_GDOWN_DATABASE`, `GLUONIFY_GDOWN_USER`, `GLUONIFY_GDOWN_PASSWORD` e `GLUONIFY_GDOWN_CA_FILE` (il PEM della CA).

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

Il driver rifiuta una CA personalizzata con uno schema `+s`, da cui `encrypted=True` con `TrustCustomCAs`: resta TLS, verificato con la CA della piattaforma. Un indirizzo `bolt://` senza TLS è rifiutato, tranne con `SOURCE_DEV=1` (un gDown locale), che la piattaforma rifiuta.

## 6. Configurazione

Tutta la configurazione viene dall'ambiente (la piattaforma, o la cassaforte Top); nulla di segreto va in Git.

| Variabile | Predefinito | Ruolo |
|---|---|---|
| `SOURCE_STORE` | `auto` | `auto`, `memory` o `gdown` |
| `SOURCE_DEV` | assente | `1`: identità di sviluppo per le richieste senza token (rifiutata sulla piattaforma) |
| `PORT` | `8080` | porta di ascolto (sempre `0.0.0.0`) |
| `GLUONIFY_SOURCE_OIDC_ISSUER`, `GLUONIFY_SOURCE_OIDC_AUDIENCE`, `GLUONIFY_SOURCE_OIDC_CLIENT_ID` | valori `GLUONIFY_OIDC_*` della piattaforma | prevalgono sui valori della piattaforma |
| `GLUONIFY_SOURCE_CHARM_PUBLIC_URL` | `GLUONIFY_OIDC_PUBLIC_URL`, altrimenti dedotta dall'emittente | indirizzo pubblico di Charm per il browser |
| `SOURCE_AUTH_SCOPE` | `openid` | ambito dell'accesso del browser |
| `GLUONIFY_GDOWN_BOLT_URL`, `GLUONIFY_GDOWN_CA_FILE` | iniettate dalla piattaforma | indirizzo Bolt di gDown (`bolt+s://`, solo TLS) e la CA di fiducia |

## 7. Costruire e distribuire

Bup riconosce un progetto Python dal suo `pyproject.toml`, esige il file di blocco, analizza il codice (SonarQube, regole sulle chiamate pericolose, `pip-audit`), installa `requirements.lock` con `pip install --require-hashes` in un venv, e firma codice e venv in un gzip. **`uses` è dedotto** dai marcatori `[gluonify.uses]` delle distribuzioni dell'SDK installate in quel venv (`gluonify` dichiara `charm`; la distribuzione `neo4j` fa dedurre `gdown`); `gluonify.json` dice solo ciò che non si può dedurre:

```json
{"gdownDatabase": true, "portEnv": "PORT", "health": "/q/health/ready"}
```

Dopo aver cambiato una dipendenza: `uv lock && uv export --format requirements-txt --no-dev --no-emit-project -o requirements.lock`. (Il framework Python di Bup è la fase V3-2 della specifica: non ancora disponibile.)

## 8. Testare

```bash
uv run pytest --cov          # 57 test
uv run ruff check . && uv run ruff format --check .
```

Charm è simulato da una coppia di chiavi P-256 il cui JWKS è letto dal verificatore; gDown da un falso driver `neo4j` che interpreta le quattro istruzioni. Entrambe le archiviazioni passano gli stessi test di API. `tests/test_conformity.py` controlla il file di blocco e le sue impronte, Python 3.13, l'assenza di file sensibili e di Dockerfile, e che gli `uses` dedotti e dichiarati siano uguali a quelli di `deploy/appspec.json`.

## 9. Cosa si traspone da gluonify-source, e cosa non ancora

| gluonify-source (Java) | Qui |
|---|---|
| API REST delle note, ruoli, validazione, OpenAPI | ✅ |
| Token di Charm, `/api/auth-config` | ✅ |
| Archiviazione Gdown (API HTTP in Java) | ✅ con il driver `neo4j` su Bolt con TLS |
| Archiviazione in memoria, salute ready/live, `/api/platform` | ✅ |
| Interfaccia Vue (Quinoa) | ❌ non trasposta: servire un'interfaccia costruita con `StaticFiles`, o ospitarla su Field |
| Archiviazione su file (`/distributed/std`) | ❌ |
| Webhook di Photon (`/hooks`), documenti con Crystallon | ❌ (ancora nessun client Python nell'SDK) |
| Eseguibile nativo | non applicabile: CPython del nodo |
| `scripts/rename.py` | ❌: rinominare a mano `gluonify_source`, il nome del progetto e `AUDIENCE` di `config.py` |
