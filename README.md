# Starter Backend — Complejo de salas para eventos

Backend de referencia de la Unidad 2. Implementa el contrato v2, que está
congelado y entregado al equipo de Frontend.

## Puesta en marcha

```bash
docker compose up --build
docker compose exec api alembic upgrade head
```

La API queda en `http://localhost:8000` y la documentación interactiva en
`http://localhost:8000/docs`.

El esquema **no** se crea al iniciar la aplicación: se construye con Alembic.
Si la base está vacía, el arranque siembra usuarios, una sala de 5×8 butacas y
un evento de ejemplo.

## Pruebas

```bash
pytest                       # suite completa (incluye tests/aceptacion/)
pytest -m race_demo          # demostración de la condición de carrera
python herramientas/evaluar_semana4.py   # tablero
```

La suite corre contra SQLite en archivo para no depender de tener PostgreSQL
levantado. Es una decisión pragmática con un límite real: la garantía de
`RET-001` se comprueba ahí porque SQLite soporta índices únicos parciales, pero
el comportamiento bajo concurrencia real solo se observa contra PostgreSQL.

## El canal de eventos

`GET /events/{event_id}/stream` mantiene una conexión abierta y avisa cuando
cambia el estado de una butaca. El primer evento es siempre un `snapshot` con el
mapa completo.

Para verlo funcionando, en una terminal:

```bash
curl -N localhost:8000/events/1/stream
```

y en otra:

```bash
curl -X POST localhost:8000/events/1/holds \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"user-1","seat_ids":[3,4]}'
```

El primer terminal recibe un `seats.updated` con las dos butacas.

**Límite importante:** la difusión vive en la memoria de este proceso. Con más
de una copia del backend corriendo, un evento producido en una copia no llega a
los clientes conectados a otra. Ver ADR-005 y `TODO.md`.

## Verificación contra el esquema

```bash
st run http://localhost:8000/openapi.json \
   --exclude-path "/events/{event_id}/stream"
```

La exclusión no es opcional: ese endpoint no cierra la conexión y la herramienta
se quedaría esperando hasta agotar el tiempo.

## Cómo está organizado

```
app/core            reglas y entidades. No conoce nada de afuera.
app/application     casos de uso y puertos.
app/infrastructure  adaptadores: base de datos, ORM.
app/api             adaptador HTTP.
tests/aceptacion    una verificación por criterio de aceptación.
docs/contrato       lo normativo: alcance, reglas, arquitectura, contrato, criterios.
docs/adr            decisiones tomadas, con sus alternativas.
docs/diagramas      documentos derivados del código. No se editan a mano.
herramientas        generadores y tablero.
```

Antes de pedirle un cambio a un agente, leer `AGENTS.md`: define qué puede
modificar y qué no.
