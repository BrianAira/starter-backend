# Base de datos: conexión, SQLAlchemy y evolución del esquema

Este documento explica cómo se conecta la aplicación, qué papel cumple
SQLAlchemy y cómo se modifica el esquema de la base a partir de la Semana 3.

## 1. Cómo se conecta la aplicación

La configuración vive en `app/infrastructure/db.py` y depende de la variable de
entorno `DATABASE_URL`.

- En `docker-compose.yml` apunta a PostgreSQL, el motor real del proyecto:
  `postgresql+psycopg://app:app@db:5432/app`.
- En los tests, `tests/conftest.py` la reemplaza por una base SQLite en archivo
  antes de importar la aplicación.

La misma aplicación puede trabajar con ambas configuraciones porque la URL no
está escrita dentro del código de negocio.

## 2. Qué hace SQLAlchemy

SQLAlchemy conecta objetos Python con operaciones de base de datos. No reemplaza
la base ni elimina la necesidad de entender transacciones, índices o
restricciones.

```text
Entidad del dominio
        ↓ traducción del adaptador
Modelo SQLAlchemy
        ↓
Session
        ↓
Engine y driver
        ↓
Base de datos
```

### Modelos

Los modelos de `app/infrastructure/models.py` describen tablas, columnas,
relaciones, índices y restricciones.

No son las entidades del dominio:

- `EventModel`, `SeatModel` y `HoldModel` pertenecen a Infrastructure;
- `Event`, `Seat` y `Hold` pertenecen al core.

El adaptador traduce entre ambos mundos.

### Engine

El `engine` sabe cómo obtener conexiones usando `DATABASE_URL`.

### Session

La `Session` representa una unidad de trabajo. Permite consultar, agregar y
modificar objetos dentro de una transacción.

- `flush` envía operaciones pendientes a la base sin confirmar todavía la
  transacción;
- `commit` confirma los cambios;
- `rollback` descarta la transacción después de un error.

Una restricción puede fallar durante `flush` o `commit`. Después de un
`IntegrityError`, la sesión necesita `rollback` antes de volver a utilizarse.

## 3. Verificación rápida y motor real

SQLite soporta índices únicos parciales. Por eso la conducta central de
`RET-001` puede probarse en la suite rápida sin levantar Docker.

La prueba contra PostgreSQL sigue siendo útil para confirmar que la migración,
el dialecto y el tratamiento del error funcionan también en el motor real.

```text
SQLite en tests       → verifica rápidamente el comportamiento esperado
PostgreSQL integración → confirma la implementación sobre el motor real
```

## 4. Cómo evoluciona el esquema

A partir de la Semana 3, el esquema se gestiona con **migraciones Alembic**.
`Base.metadata.create_all` deja de ser el mecanismo normal de arranque.

### Por qué `create_all` deja de alcanzar

`create_all` crea tablas que todavía no existen. No transforma de manera
controlada las tablas ya creadas.

Si se agrega una columna, un índice o una restricción al modelo Python, una base
existente no recibe automáticamente ese cambio. La tabla `holds` ya existe en
instalaciones anteriores, por lo que la nueva restricción de `RET-001` necesita
una migración.

### Qué es una migración

Una migración describe cómo pasar de una versión del esquema a otra.

- `upgrade`: aplica el cambio;
- `downgrade`: lo revierte cuando es posible.

Alembic registra en la propia base qué revisión está aplicada. Las migraciones
se versionan con Git y se ejecutan con:

```bash
alembic upgrade head
```

### Condición operativa

Una base vacía debe poder construirse íntegramente con:

```bash
alembic upgrade head
```

Si además hace falta que la aplicación cree tablas al arrancar, el historial de
migraciones está incompleto.

### Qué no se delega al agente

El agente puede generar la sintaxis de una migración. La persona responsable del
proyecto debe poder explicar:

- qué cambia;
- por qué cambia;
- cómo se comprueba;
- qué riesgo existe si la base ya contiene datos;
- qué ocurre al revertirla.

Una migración que agrega unicidad puede fallar si ya existen filas duplicadas.
Eso no debe ocultarse: obliga a decidir qué hacer con esos datos antes de aplicar
la nueva regla.

## 5. Protección elegida para RET-001

Un **índice único parcial** sobre `(event_id, seat_id)`, restringido a los
estados que mantienen ocupada la butaca:

```sql
CREATE UNIQUE INDEX uq_holds_event_seat_active
    ON holds (event_id, seat_id)
    WHERE status IN ('active', 'confirmed');
```

Es parcial a propósito: si abarcara todos los estados, una butaca liberada o
vencida quedaría bloqueada para siempre.

### Por qué el predicado no mira el reloj

La condición natural sería "activa y no vencida". No se puede: el predicado de
un índice debe ser inmutable y `now()` no lo es. PostgreSQL rechaza la
definición.

La consecuencia es concreta y está en `RET-004`: el vencimiento **se escribe**.
Antes de insertar una retención nueva, la misma transacción marca como
`expired` las retenciones vencidas de las butacas pedidas. Recién entonces el
índice deja de considerarlas ocupantes.

Sin esa escritura, el sistema mostraría la butaca disponible en el mapa —porque
la lectura sí deriva el vencimiento— y rechazaría la retención con un conflicto
que el usuario no podría entender.

## 6. Tablas del esquema vigente

| Tabla | Contenido | Notas |
|---|---|---|
| `users` | Usuarios precargados. | Identificador de tipo cadena, según el contrato. |
| `rooms` | Salas, con cantidad de filas y columnas. | |
| `seats` | Butacas de una sala, con coordenadas y sector. | Índice único por `(room_id, x, y)`. |
| `events` | Eventos, asociados a una sala. | |
| `holds` | Retenciones. | Índice único parcial de RET-001. |

Las butacas pertenecen a la **sala**, no al evento: el mismo mapa se reutiliza
para todos los eventos de esa sala, y las retenciones son las que están
asociadas al evento.

Las marcas de tiempo se guardan en UTC sin zona. La zona se agrega al
serializar, porque el contrato exige el sufijo `Z`.
