# Qué pasó con todo

Informe de la reconstrucción del starter sobre el contrato v2.

El punto de partida fue el repositorio de la Semana 3, que implementaba el v1.
El contrato v2 ya estaba congelado y entregado, así que en cada diferencia mandó
el documento.

---

## 1. Lo que se conservó sin tocar

- `Dockerfile`, `docker-compose.yml`, `alembic.ini`, `alembic/env.py`,
  `pytest.ini`.
- `docs/contrato/arquitectura.md` (solo se le agregó `ARQ-010`).
- `docs/adr/ADR-001`, `ADR-002`, `ADR-003`.
- `docs/teoria/frontera_core_application.md`.
- `herramientas/generar_diagrama_estados.py`, que siguió funcionando sin
  cambios sobre el código nuevo.
- `tests/test_arquitectura.py`.
- La estructura de capas, los nombres de los módulos y el estilo de los
  comentarios explicativos.

---

## 2. Lo que se reescribió, y por qué

| Archivo | Motivo |
|---|---|
| `app/core/entities.py` | Identificadores enteros; entidades `User` y `Room`; `expires_at`; estado público de butaca; `SeatView`. |
| `app/core/rules.py` | `RET-002` con vencimiento; proyección única del estado; idempotencia (`RET-005`); confirmación (`RET-003`). |
| `app/application/ports.py` | Puerto ampliado y unidad de trabajo explícita (`transaccion`). |
| `app/application/use_cases.py` | Operaciones por lote, todo o nada, con orden ascendente de butacas. |
| `app/api/schemas.py` | Formas del contrato v2; serialización de fechas con sufijo `Z`. |
| `app/api/routes.py` | Rutas del v2 y catálogo de errores `{code, message}`. |
| `app/api/errors.py` | Nuevo: constructor único de respuestas de error. |
| `app/infrastructure/models.py` | Tablas `users`, `rooms`, `seats` con geometría, `holds` con `user_id` y `expires_at`. |
| `app/infrastructure/repository.py` | Adaptador del puerto nuevo; `marcar_vencidas`; siembra de una sala completa. |
| `main.py` | `lifespan` en lugar del evento `startup`, que está obsoleto. |
| `alembic/versions/0001_esquema_inicial.py` | Migración única del esquema v2. |
| `herramientas/evaluar_semana4.py` | Tablero, reescrito sobre el anterior. |

---

## 3. Decisiones que hubo que tomar y no estaban escritas

**Las butacas pertenecen a la sala, no al evento.** El contrato describe una
sala con filas y columnas y butacas con coordenadas; con las butacas colgando
del evento, dos funciones en la misma sala tendrían mapas distintos. Las
retenciones sí están asociadas al evento.

**Zonas horarias.** Internamente se usa UTC sin zona, porque comparar una marca
con zona contra una sin zona es un error de tipo y la base guarda sin zona. La
zona se agrega solo al serializar, que es donde el contrato exige el sufijo `Z`.

**Unidad de trabajo explícita.** El puerto expone `transaccion()` como
administrador de contexto. Sin eso no hay forma de sostener el "todo o nada" de
los lotes desde Application sin que Application conozca SQLAlchemy.

**El adaptador traduce el error dentro de la transacción.** El `IntegrityError`
se convierte en `RetencionDuplicadaError` en el mismo lugar donde se hace el
`rollback`, y ni Application ni API conocen SQLAlchemy (`ARQ-008`).

**Idempotencia como regla propia.** El contrato la describe pero no la
identificaba. Quedó como `RET-005`, para poder referenciarla desde pruebas y
criterios.

---

## 4. Lo que se dejó deliberadamente sin construir

Dos operaciones están en el contrato y responden `501 NOT_IMPLEMENTED`:

- `DELETE /holds/{hold_id}`. Además, **no existe** el método de puerto ni el del
  adaptador: hay que agregarlos. Ningún camino del sistema produce el estado
  `RELEASED`, y el diagrama derivado lo muestra sin productor. Implementarlo
  cambia el diagrama, que a su vez está verificado.
- `GET /events/{event_id}/stream`. No existe puerto de publicación de eventos ni
  publicación en los casos de uso.

No hay `tests/aceptacion/`: generar verificaciones desde criterios es la tarea
de la semana, y el tablero lo reporta como `CA-017`.

---

## 5. Estado verificado

```
CTX         OK
CA-004      OK    37 passed, 1 deselected
CA-009      OK
CA-010/026  OK
CA-011      OK
CA-006b     OK
CA-007      OK
CA-013      OK
CA-017      FALLA  todavía no existe tests/aceptacion/
```

Lo comprobado de verdad:

- la suite completa pasa (37 pruebas) y la demostración de carrera produce un
  ganador y un perdedor;
- `alembic upgrade head` construye una base vacía y el esquema resultante
  coincide con los modelos, con el índice único parcial presente;
- las nueve rutas del contrato aparecen en el OpenAPI, incluidas las dos que
  responden `501`;
- `app/core` y `app/application` no importan infraestructura ni transporte;
- el diagrama commiteado coincide con el código.

**Lo que no está comprobado:** todo esto corrió contra SQLite, no contra
PostgreSQL. SQLite soporta índices únicos parciales, así que la garantía es
comprobable, pero el comportamiento bajo concurrencia real —bloqueos, orden de
transacciones, tiempos— solo se observa contra Postgres. Antes de repartir el
repositorio conviene levantar el `docker compose` y correr el tablero ahí.

Tampoco se corrió Schemathesis: está en `requirements.txt` y `CA-021` lo espera,
pero la primera corrida es contenido del video y conviene que la hagas vos, para
elegir qué hallazgos mostrar.

---

## 6. Diferencias con el repositorio anterior que conviene mirar

- Los usuarios de ejemplo son `user-1`, `user-2` y `user-3`. Los identificadores
  de eventos, butacas y retenciones son enteros: el evento sembrado es el `1` y
  las butacas van del `1` al `40`.
- `CA-012` del documento anterior hablaba de `SEAT_UNAVAILABLE` en singular. El
  contrato v2 usa `SEATS_UNAVAILABLE` con la lista de butacas en conflicto.
- El plazo de una retención se configura con `HOLD_TTL_MINUTOS` (15 por
  defecto). No es parte del contrato: el Frontend lee `expires_at`.
