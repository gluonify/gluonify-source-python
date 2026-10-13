# gluonify-source-python

[English](README.md) · [Français](README.fr.md) · **Español** · [Italiano](README.it.md) · [Deutsch](README.de.md)

> **Variantes Java.** El mismo servicio en Quarkus está en [`gluonify-source`](https://github.com/gluonify/gluonify-source) (Maven) y [`gluonify-source-gradle`](https://github.com/gluonify/gluonify-source-gradle) (Gradle). Este es su equivalente en **Python**, en la medida en que se traslada.

**El punto de partida de un servicio Python en [Gluonify](https://gluonify.io).** Un servicio pequeño y completo (unas «notas») construido con **FastAPI** y **uvicorn** sobre el SDK Python de Gluonify ([`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python): distribuciones `gluonify` y `gluonify-fastapi`). Muestra, con código que funciona y pruebas, cómo:

1. crear un **servicio REST** (validación, roles, OpenAPI);
2. **verificar los tokens de Charm** y los roles, y dar a un navegador lo necesario para iniciar sesión;
3. guardar los datos en **gDown**, la base de datos de grafos de la plataforma (base dedicada, controlador oficial `neo4j` sobre Bolt);
4. exponer los puntos de **salud** que vigila la plataforma.

> Las aplicaciones Python se ejecutan en Gluonify con el `python3` de Debian 13 (**CPython 3.13**) de cada nodo: Bup instala las dependencias bloqueadas en un venv, firma el código y el venv en un archivo, y el nodo lo ejecuta en el mismo entorno aislado que las aplicaciones nativas. Sin Dockerfile.

## Índice
1. [Empezar en 5 minutos](#1-empezar-en-5-minutos)
2. [El mapa del proyecto](#2-el-mapa-del-proyecto)
3. [Crear un servicio REST](#3-crear-un-servicio-rest)
4. [Autenticación: los tokens de Charm](#4-autenticación-los-tokens-de-charm)
5. [Almacenamiento: memoria o gDown](#5-almacenamiento-memoria-o-gdown)
6. [Configuración](#6-configuración)
7. [Construir y desplegar](#7-construir-y-desplegar)
8. [Probar](#8-probar)
9. [Lo que se traslada de gluonify-source, y lo que aún no](#9-lo-que-se-traslada-de-gluonify-source-y-lo-que-aún-no)

---

## 1. Empezar en 5 minutos

**Requisitos**: Python 3.13 y [uv](https://docs.astral.sh/uv/). Mientras el SDK no esté publicado en PyPI, clone [`gluonify-plasma-python`](https://github.com/gluonify/gluonify-plasma-python) **junto a** este repositorio (`../gluonify-plasma-python`): `pyproject.toml` lo toma de ahí.

```bash
git clone https://github.com/gluonify/gluonify-source-python.git
cd gluonify-source-python
uv sync
SOURCE_DEV=1 uv run gluonify-source
```

`SOURCE_DEV=1` da a toda petición sin token una identidad «dev» con todos los roles (rechazada en la plataforma). Las notas están en memoria. Después:

| Dirección | Contenido |
|---|---|
| `/api/notes` | la API REST (JSON) |
| `/api/platform` | lo que proporcionó la plataforma (entorno, servicios concedidos, almacenamiento) |
| `/api/auth-config` | configuración pública de inicio de sesión para una interfaz web (cliente y direcciones de Charm) |
| `/q/swagger-ui` · `/q/openapi` | documentación interactiva y contrato OpenAPI |
| `/q/health/ready` · `/q/health/live` | disponibilidad (el almacenamiento responde) y vida |

```bash
curl -s localhost:8080/api/notes -H 'Content-Type: application/json' -d '{"title":"Compras","body":"pan"}'
curl -s localhost:8080/api/notes
```

## 2. El mapa del proyecto

```
pyproject.toml              el proyecto: dependencias, comando gluonify-source, ruff, pytest
uv.lock                     el archivo de bloqueo universal (huellas de cada archivo de PyPI)
requirements.lock           `uv export` de uv.lock, con huellas: lo que Bup instala con `pip install --require-hashes`
gluonify.json               leído por Bup: gdownDatabase, variable del puerto, ruta de salud («uses» se deduce de los marcadores del SDK)
deploy/appspec.json         un ejemplo de AppSpec para un despliegue manual
src/gluonify_source/
  main.py                   build(): create_app del SDK + notas + plataforma + disponibilidad; run() arranca uvicorn
  config.py                 cada variable leída, con su valor por defecto
  notes/models.py           NewNote (cuerpo validado), Note
  notes/api.py              ← EL MODELO DE UN RECURSO REST (para copiar)
  notes/store.py            la interfaz NoteStore; MemoryNoteStore, GraphNoteStore (gDown)
  notes/stores.py           elige la implementación (SOURCE_STORE): el lugar para conectar la suya
  platform.py               /api/platform y /api/auth-config
tests/                      Charm simulado por una clave P-256 y su JWKS, gDown por un falso controlador neo4j
```

## 3. Crear un servicio REST

Lea [`notes/api.py`](src/gluonify_source/notes/api.py): es el modelo.

1. **El modelo**: un `BaseModel` de pydantic (validado, serializado, descrito por OpenAPI).
2. **El router**: `APIRouter(prefix="/api/orders", tags=["Orders"])`, funciones `@router.get/post/delete`, roles con una dependencia `Annotated[Principal, Depends(require_roles("shop:write"))]`. Inclúyalo en `main.build()`.
3. **Códigos HTTP**: 201 + `Location` al crear, 204 sin cuerpo, 400 para un cuerpo no válido (`{"error": "invalid body", "violations": [...]}`), 401 sin token válido, 403 sin el rol, 404 para un identificador desconocido. Los errores son `{"error": "…"}`.
4. **Las pruebas**: copie [`tests/test_notes.py`](tests/test_notes.py): `charm.bearer("shop:read")` crea un token de prueba firmado.

El almacenamiento está detrás de [`NoteStore`](src/gluonify_source/notes/store.py): impleméntela y añada un caso en [`stores.py`](src/gluonify_source/notes/stores.py).

## 4. Autenticación: los tokens de Charm

La API verifica los tokens portadores emitidos por **Charm** (JWT, ES256) con `require_roles` de `gluonify-fastapi`: nada que configurar en la plataforma. El SDK lee las claves de Charm en `GLUONIFY_SERVICE_CHARM_URL`, comprueba el emisor `GLUONIFY_OIDC_ISSUER` y la audiencia `GLUONIFY_OIDC_AUDIENCE` (`gluonify-source` por defecto), y lee los roles del claim `roles` (`source:read`, `source:write`). Una interfaz web inicia sesión en el propio Charm (código de autorización + PKCE, el kit `@gluonify/ui`) gracias a `GET /api/auth-config`; la contraseña nunca se escribe en esta aplicación.

## 5. Almacenamiento: memoria o gDown

`SOURCE_STORE=auto` (por defecto) usa **gDown** cuando la plataforma proporciona una base dedicada (`GLUONIFY_GDOWN_DATABASE`, de `"gdownDatabase": true`), y la memoria en otro caso. `GraphNoteStore` ejecuta cuatro sentencias Cypher parametrizadas mediante `GdownClient` del SDK (el controlador `neo4j`, en la base dedicada). La disponibilidad responde 503 mientras gDown no responda; la vida nunca depende de ello.

> **Punto abierto**: la plataforma arranca hoy gDown con Bolt desactivado; hasta que Higgs abra Bolt a las aplicaciones, el almacenamiento gDown funciona con un gDown que usted mismo ejecute (`GLUONIFY_GDOWN_BOLT_URL`).

## 6. Configuración

Toda la configuración viene del entorno (la plataforma, o el almacén Top); nada secreto va a Git.

| Variable | Por defecto | Función |
|---|---|---|
| `SOURCE_STORE` | `auto` | `auto`, `memory` o `gdown` |
| `SOURCE_DEV` | ausente | `1`: identidad de desarrollo para peticiones sin token (rechazada en la plataforma) |
| `PORT` | `8080` | puerto de escucha (siempre `0.0.0.0`) |
| `GLUONIFY_SOURCE_OIDC_ISSUER`, `GLUONIFY_SOURCE_OIDC_AUDIENCE`, `GLUONIFY_SOURCE_OIDC_CLIENT_ID` | valores `GLUONIFY_OIDC_*` de la plataforma | prevalecen sobre los valores de la plataforma |
| `GLUONIFY_SOURCE_CHARM_PUBLIC_URL` | `GLUONIFY_OIDC_PUBLIC_URL`, si no, deducida del emisor | dirección pública de Charm para el navegador |
| `SOURCE_AUTH_SCOPE` | `openid` | ámbito del inicio de sesión del navegador |
| `GLUONIFY_GDOWN_BOLT_URL` | deducida de `GLUONIFY_SERVICE_GDOWN_URL`, puerto 7687 | dirección Bolt de gDown |

## 7. Construir y desplegar

Bup reconoce un proyecto Python por su `pyproject.toml`, exige el archivo de bloqueo, analiza el código (SonarQube, reglas de llamadas peligrosas, `pip-audit`), instala `requirements.lock` con `pip install --require-hashes` en un venv, y firma el código y el venv en un gzip. **`uses` se deduce** de los marcadores `[gluonify.uses]` de las distribuciones del SDK instaladas en ese venv (`gluonify` declara `charm` y `gdown`); `gluonify.json` solo indica lo que no se puede deducir:

```json
{"gdownDatabase": true, "portEnv": "PORT", "health": "/q/health/ready"}
```

Tras cambiar una dependencia: `uv lock && uv export --format requirements-txt --no-dev --no-emit-project -o requirements.lock`. (El framework Python de Bup es la fase V3-2 de la especificación: aún no disponible.)

## 8. Probar

```bash
uv run pytest --cov          # 47 pruebas
uv run ruff check . && uv run ruff format --check .
```

Charm se simula con un par de claves P-256 cuyo JWKS lee el verificador; gDown con un falso controlador `neo4j` que interpreta las cuatro sentencias. Ambos almacenamientos pasan las mismas pruebas de API. `tests/test_conformity.py` comprueba el archivo de bloqueo y sus huellas, Python 3.13, la ausencia de archivos sensibles y de Dockerfile, y que los `uses` deducidos y declarados igualan los de `deploy/appspec.json`.

## 9. Lo que se traslada de gluonify-source, y lo que aún no

| gluonify-source (Java) | Aquí |
|---|---|
| API REST de notas, roles, validación, OpenAPI | ✅ |
| Tokens de Charm, `/api/auth-config` | ✅ |
| Almacenamiento Gdown (API HTTP en Java) | ✅ sobre Bolt (ver el punto abierto del §5) |
| Almacenamiento en memoria, salud ready/live, `/api/platform` | ✅ |
| Interfaz Vue (Quinoa) | ❌ no portada: servir una interfaz construida con `StaticFiles`, o alojarla en Field |
| Almacenamiento en archivos (`/distributed/std`) | ❌ |
| Webhooks de Photon (`/hooks`), documentos con Crystallon | ❌ (aún sin cliente Python en el SDK) |
| Ejecutable nativo | no aplica: CPython del nodo |
| `scripts/rename.py` | ❌: renombrar a mano `gluonify_source`, el nombre del proyecto y `AUDIENCE` de `config.py` |
