# Arquitectura vigente

Este documento define las restricciones actuales de arquitectura. No describe
las reglas del negocio ni el contrato HTTP: esas decisiones viven en
`reglas.md` y `contrato_api.md`.

Los ADR explican por qué se eligió una solución. Este archivo indica qué debe
respetar hoy cualquier cambio, sea escrito por una persona o por un agente.

## Estructura

```text
app/
├── api/
├── application/
├── core/
└── infrastructure/
```

## ARQ-001 — Dirección general de dependencias

Las dependencias del código apuntan hacia el núcleo de la aplicación.

```text
API → Application → Core
Infrastructure → Application
```

Infrastructure implementa necesidades declaradas por Application; Application
no depende de implementaciones concretas de Infrastructure.

## ARQ-002 — Independencia del core

`app/core` no puede importar:

- `app/api`;
- `app/application`;
- `app/infrastructure`;
- FastAPI;
- SQLAlchemy;
- psycopg.

El core recibe datos por parámetro, toma decisiones sin I/O y devuelve
resultados.

## ARQ-003 — Application no depende de Infrastructure

`app/application` expresa sus necesidades externas mediante puertos y no
importa implementaciones de `app/infrastructure`.

## ARQ-004 — Acceso a persistencia

Las consultas y escrituras de base de datos se realizan mediante adaptadores
ubicados en `app/infrastructure`.

## ARQ-005 — Responsabilidad de API

`app/api` traduce HTTP hacia y desde Application. No contiene reglas de negocio
ni realiza acceso directo a persistencia.

## ARQ-006 — Core funcional

El core no inicia I/O ni utiliza puertos de salida. Una función del core recibe
los datos necesarios ya resueltos por Application.

## ARQ-007 — Ubicación de los puertos

Los puertos requeridos por los casos de uso se definen en `app/application`.
Los adaptadores concretos se implementan en `app/infrastructure` y se conectan
en el borde de entrada.

## ARQ-008 — Los detalles de persistencia no salen de Infrastructure

Ni `app/application` ni `app/api` pueden importar el ORM, el driver, los modelos
de persistencia ni las excepciones producidas por esas bibliotecas.

Esta restricción incluye:

- `sqlalchemy` y sus submódulos;
- `psycopg`, `psycopg2` y `sqlite3`;
- `app.infrastructure.models`;
- excepciones como `IntegrityError`.

Cuando la base rechaza una operación, el adaptador traduce el error técnico a
una excepción definida por el proyecto antes de devolver el control a
Application. Por eso un bloque `except IntegrityError` solo puede existir en
`app/infrastructure`.

## ARQ-009 — RET-001 tiene dos capas de protección

Para `RET-001` se usan dos mecanismos complementarios:

| Mecanismo | Para qué sirve | Dónde vive |
|---|---|---|
| Validación previa | Detecta el caso normal y permite responder con un error claro. | `app/core` |
| Restricción del esquema | Impide que dos escrituras concurrentes dejen un estado inválido. | base de datos |

No se presenta esto como una clasificación universal de todas las reglas. Es la
decisión concreta adoptada para `RET-001` después de analizar el riesgo de dos
solicitudes simultáneas.

Ambos caminos terminan en la misma excepción del proyecto, para que API y
Application no necesiten saber si el conflicto fue detectado antes de escribir
o por la propia base.

## Responsabilidades

| Área | Responsabilidad |
|---|---|
| `app/api` | Rutas y traducción entre HTTP y Application. |
| `app/application` | Coordinación de casos de uso y definición de puertos. |
| `app/core` | Entidades, estados, reglas y decisiones puras. |
| `app/infrastructure` | Persistencia, SQLAlchemy, PostgreSQL, adaptadores y traducción de errores técnicos. |

## Flujo de creación de una retención

```text
HTTP
  ↓
API
  ↓
Application
  ↓
Core: validación previa
  ↓
Application ──puerto──→ Infrastructure ──→ base de datos
                                              ↓
                           restricción acepta o rechaza
                                              ↓
API ←── excepción del proyecto ←── traducción del adaptador
```

Las reglas funcionales se definen en `docs/contrato/reglas.md`. El contrato con
Frontend se define en `docs/contrato/contrato_api.md`. La historia de las
decisiones se conserva en `docs/adr/`.

## ARQ-010 — El transporte no entra al dominio

Ni Core ni Application conocen el mecanismo por el cual un cambio llega a un
cliente. Cuando exista publicación de eventos, Application publicará contra un
puerto y el adaptador decidirá si eso sale por un canal SSE, por un WebSocket o
por ningún lado.

En términos prácticos: `app/core` y `app/application` no importan el framework
web, ni la biblioteca del canal, ni nada que hable de HTTP.

- **Motivo:** el mecanismo de notificación es una decisión reemplazable. Si el
  dominio lo conoce, cambiarlo obliga a tocar reglas que no tienen nada que ver.
- **Verificación:** inspección AST desde el tablero, junto con ARQ-008.
