# Estado del repositorio

Implementa el contrato v2 **completo**, incluido el canal de eventos. No hay
operaciones declaradas y sin construir.

## Verificado

```
CTX         OK
CA-004      OK    47 passed, 1 deselected
CA-009      OK
CA-010/026  OK
CA-011      OK
CA-006b     OK
CA-007      OK
CA-013      OK
CA-017      OK
9 comprobaciones cumplidas.
```

Además de la suite, se comprobó a mano contra un servidor real:

- abrir el canal devuelve `retry`, luego un `snapshot` con las 40 butacas;
- un `POST` de dos butacas produce un `seats.updated` con las dos, en estado
  `HELD`, con `held_by_user_id` y `expires_at`;
- `DELETE` de una retención devuelve `204`, y repetirlo también;
- `alembic upgrade head` construye el esquema con el índice único parcial.

## No verificado

- **PostgreSQL.** Todo corrió contra SQLite. Levantar el `docker compose` y
  correr el tablero ahí antes de repartir.
- **Schemathesis** (`CA-021`). Instalado, con el comando en el README, sin
  correr.
- **Carga.** Cada conexión del canal ocupa un hilo del *pool*; no se midió
  cuántas soporta.

## Lo que queda fuera a propósito

- Capacidad máxima de butacas por usuario y evento: es el trabajo práctico final.
- Difusión entre varias copias del backend: la limitación está registrada en
  ADR-005, en `TODO.md` y en la Sección 8 del contrato.
- WebSocket: solo comparación, en el ADR-005.
