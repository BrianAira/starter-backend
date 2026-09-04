# Contrato de la API — v2

Este documento es la única fuente normativa de lo que la API promete a quien la
consume. El equipo de Frontend trabaja contra este contrato, no contra el
código.

**Lo que este documento fija** (y no puede cambiar sin una nueva versión):
rutas, métodos, forma del JSON, campos obligatorios, formato de fechas,
vocabulario de estados, códigos HTTP y códigos de error.

---

## 1. Principio de versionado

El contrato se estabiliza antes que la implementación. Un endpoint puede estar
definido acá y todavía no implementado; en ese caso responde `501` con el
código `NOT_IMPLEMENTED`, nunca `404`.

Un `404` significa "este recurso no existe". Un `501` significa "esta operación
existe en el contrato y todavía no está construida". Confundirlos hace que el
Frontend no pueda distinguir un error propio de una funcionalidad pendiente.

### 1.1. Alcance

La API cubre la vista del espectador: elegir quién es, mirar el mapa de una
sala, retener butacas, soltarlas y confirmar la compra.

Los usuarios, los eventos, las salas y la disposición de butacas se cargan una
única vez fuera de la API. **No hay endpoints de alta ni de edición para nada de
eso**, y su ausencia no es una funcionalidad pendiente: está fuera de alcance.

---

## 2. Convenciones generales

- Todas las respuestas son `application/json`, con una única excepción: el canal
  de eventos de la Sección 4.9, que es `text/event-stream`.
- Las fechas se expresan en **ISO 8601 con zona UTC**, siempre con `Z`:
  `2026-08-15T20:00:00Z`. El Frontend convierte a hora local para mostrar. No
  se envían fechas sin zona: una cuenta regresiva calculada sobre una fecha sin
  zona da mal por tres horas en Argentina.
- Los identificadores de eventos, salas, butacas y retenciones son **enteros**.
  Los identificadores de usuario son **cadenas** (`"user-1"`). El cliente no
  debe derivar significado de su valor ni construirlos.
- Los campos declarados como obligatorios están siempre presentes; los
  opcionales pueden venir en `null`.
- No hay autenticación. El usuario viaja como dato en la petición. Esto es una
  simplificación deliberada del trabajo práctico y está registrada como tal.

### Formato de error

Toda respuesta de error tiene esta forma:

```json
{
  "detail": {
    "code": "SEATS_UNAVAILABLE",
    "message": "Una o más butacas ya no están disponibles."
  }
}
```

`code` es el contrato: es estable y está pensado para que el cliente ramifique
sobre él. `message` es orientativo y puede cambiar de redacción sin aviso. **El
Frontend no debe ramificar sobre `message`.**

Algunos errores agregan un campo extra con el detalle de qué falló. Cuando
existe, está documentado en el endpoint correspondiente y en el catálogo de la
Sección 5.

---

## 3. Vocabulario público de estados

Hay dos vocabularios distintos y conviene no mezclarlos.

### 3.1. Estado de una butaca

Es lo que muestra el mapa. Se **calcula** en el momento de la lectura; no es un
campo guardado.

| Estado | Significado |
|---|---|
| `AVAILABLE` | Se puede retener. |
| `HELD` | Alguien la tiene retenida y la retención no venció. |
| `CONFIRMED` | La compra se confirmó. |

### 3.2. Estado de una retención

| Estado | Significado | Terminal |
|---|---|---|
| `HELD` | Retención vigente, sin confirmar, con `expires_at` en el futuro. | No |
| `CONFIRMED` | Confirmada. | Sí |
| `RELEASED` | El usuario la soltó con `DELETE`. | Sí |
| `EXPIRED` | Venció sin confirmarse. | Sí |

Una butaca puede tener muchas retenciones a lo largo del tiempo: una por cada
vez que alguien la intentó tomar. Una retención terminal no se reutiliza; un
intento nuevo crea una retención nueva, con otro `hold_id`.

> **Sobre `HELD` y el paso del tiempo.** Una retención está vigente si su estado
> es `HELD` **y** `expires_at` todavía no pasó. Las dos condiciones, siempre. El
> Frontend puede confiar en el `status` que devuelve la API: el servidor ya hizo
> esa cuenta antes de responder.

---

## 4. Endpoints

### 4.1. `GET /health`

Comprobación de vida del servicio. Sin parámetros.

`200`:

```json
{ "status": "ok" }
```

---

### 4.2. `GET /users`

Devuelve los usuarios precargados. No hay registro ni login: el Frontend
muestra esta lista y el usuario elige quién es.

`200`:

```json
[
  { "id": "user-1", "name": "Ana" },
  { "id": "user-2", "name": "Bruno" }
]
```

---

### 4.3. `GET /events`

Devuelve los eventos disponibles, ordenados por `starts_at` ascendente.

`200`:

```json
[
  {
    "id": 1,
    "name": "Concierto del sábado",
    "room_id": 1,
    "room_name": "Sala Principal",
    "starts_at": "2026-08-08T21:00:00Z"
  }
]
```

---

### 4.4. `GET /events/{event_id}`

Devuelve un evento. Mismo objeto que en la lista anterior.

- `200`: el evento.
- `404` (`EVENT_NOT_FOUND`): el evento no existe.

---

### 4.5. `GET /events/{event_id}/seats`

Devuelve la sala y todas sus butacas con el estado actual para ese evento.

`200`:

```json
{
  "event": {
    "id": 1,
    "name": "Concierto del sábado",
    "starts_at": "2026-08-08T21:00:00Z"
  },
  "room": {
    "id": 1,
    "name": "Sala Principal",
    "rows": 12,
    "columns": 20
  },
  "seats": [
    {
      "id": 101,
      "label": "A1",
      "row": "A",
      "number": 1,
      "x": 1,
      "y": 1,
      "sector": "PLATEA",
      "status": "AVAILABLE",
      "hold_id": null,
      "held_by_user_id": null,
      "expires_at": null
    },
    {
      "id": 102,
      "label": "A2",
      "row": "A",
      "number": 2,
      "x": 2,
      "y": 1,
      "sector": "PLATEA",
      "status": "HELD",
      "hold_id": 5001,
      "held_by_user_id": "user-1",
      "expires_at": "2026-08-03T00:25:00Z"
    }
  ]
}
```

- `404` (`EVENT_NOT_FOUND`): el evento no existe.

**Reglas de este objeto, normativas:**

- `x` e `y` son coordenadas de grilla con origen `(1,1)` arriba a la izquierda.
  Sirven para dibujar el mapa. Dos butacas nunca comparten coordenada dentro de
  la misma sala.
- `row`, `number` y `label` son para mostrar. `label` es la concatenación
  legible y es lo que el usuario reconoce.
- `sector` es una cadena libre del dominio (`PLATEA`, `PULLMAN`, `PALCO`). El
  Frontend puede usarla para agrupar o colorear, pero no debe asumir un
  conjunto cerrado de valores.
- `hold_id`, `held_by_user_id` y `expires_at` vienen en `null` salvo que
  `status` sea `HELD` o `CONFIRMED`.
- **Si una retención venció, la butaca aparece como `AVAILABLE` y sus tres
  campos de retención vienen en `null`.** Nunca se devuelven los datos de una
  retención vencida: sería decirle al Frontend que la butaca está tomada
  mientras el `status` dice lo contrario.

---

### 4.6. `POST /events/{event_id}/holds`

Retiene una o varias butacas para un usuario. **La operación es conjunta: se
retienen todas o ninguna.**

Cuerpo:

```json
{
  "user_id": "user-1",
  "seat_ids": [101, 102, 103]
}
```

- `seat_ids` debe tener al menos un elemento y no puede repetir valores.

`201`:

```json
{
  "holds": [
    {
      "id": 5001,
      "event_id": 1,
      "seat_id": 101,
      "user_id": "user-1",
      "status": "HELD",
      "expires_at": "2026-08-03T00:25:00Z"
    },
    {
      "id": 5002,
      "event_id": 1,
      "seat_id": 102,
      "user_id": "user-1",
      "status": "HELD",
      "expires_at": "2026-08-03T00:25:00Z"
    }
  ]
}
```

Todas las retenciones creadas en una misma petición comparten `expires_at`.

**Otros resultados:**

- `404` (`EVENT_NOT_FOUND`, `USER_NOT_FOUND`, `SEATS_NOT_FOUND`): no existe el
  evento, el usuario, o alguna butaca de la lista. `SEATS_NOT_FOUND` incluye
  `seat_ids` con las que no existen.
- `409` (`SEATS_UNAVAILABLE`): al menos una butaca ya está retenida o confirmada
  por **otro** usuario.

```json
{
  "detail": {
    "code": "SEATS_UNAVAILABLE",
    "message": "Una o más butacas ya no están disponibles.",
    "seat_ids": [102]
  }
}
```

- `422` (`INVALID_REQUEST`): el cuerpo no cumple la forma declarada.

**Idempotencia.** Si una butaca del pedido ya tiene una retención vigente **del
mismo usuario**, no se crea una retención nueva ni se produce un conflicto: se
devuelve la retención existente, con su `expires_at` original. Esto hace que un
reintento del navegador —o un doble clic— sea inofensivo. Sin esta regla, el
usuario recibiría `409` por butacas que ya son suyas.

---

### 4.7. `POST /holds/confirm`

Confirma una o varias retenciones. **Se confirman todas juntas o ninguna.**

Cuerpo:

```json
{
  "user_id": "user-1",
  "hold_ids": [5001, 5002, 5003]
}
```

`200`:

```json
{
  "holds": [
    { "id": 5001, "seat_id": 101, "user_id": "user-1", "status": "CONFIRMED" },
    { "id": 5002, "seat_id": 102, "user_id": "user-1", "status": "CONFIRMED" }
  ]
}
```

**Otros resultados:**

- `404` (`HOLDS_NOT_FOUND`): alguna retención no existe, **o no pertenece al
  usuario indicado**. Los dos casos responden igual, a propósito: una retención
  ajena no existe para este usuario. Incluye `hold_ids` con las que fallaron.
- `409` (`HOLDS_NOT_CONFIRMABLE`): alguna retención venció, fue liberada o ya
  estaba confirmada.

```json
{
  "detail": {
    "code": "HOLDS_NOT_CONFIRMABLE",
    "message": "Una o más retenciones no pueden confirmarse.",
    "hold_ids": [5002]
  }
}
```

- `422` (`INVALID_REQUEST`): el cuerpo no cumple la forma declarada.

Una retención ya confirmada no da `200`: da `409`. Confirmar dos veces no es lo
mismo que confirmar una vez, porque el Frontend tiene que poder distinguir "tu
compra se hizo recién" de "esto ya estaba hecho".

---

### 4.8. `DELETE /holds/{hold_id}`

Libera una retención individual. Permite sacar una butaca de la selección sin
perder las demás.

- `204`: sin cuerpo. La retención queda `RELEASED` y la butaca vuelve a estar
  disponible.
- `404` (`HOLD_NOT_FOUND`): la retención no existe.
- `409` (`HOLD_NOT_RELEASABLE`): la retención está `CONFIRMED` y ya no puede
  liberarse.

**Idempotencia.** Liberar una retención ya `RELEASED` o ya `EXPIRED` devuelve
`204`, no `404` ni `409`. El efecto deseado —que la butaca no esté tomada por
este usuario— ya se cumple, y un reintento no debe parecer un error.

---

### 4.9. `GET /events/{event_id}/stream`

Canal de eventos del servidor hacia el cliente (*Server-Sent Events*). Notifica
cambios en el estado de las butacas de un evento sin que el Frontend tenga que
volver a preguntar.

Es un canal de **notificación**, no de operación: todas las acciones siguen
haciéndose con los endpoints anteriores. El servidor nunca recibe datos por este
canal.

**Respuesta:** `200` con `Content-Type: text/event-stream` y la conexión
abierta. El cuerpo es una secuencia de eventos con el formato estándar de SSE:

```text
retry: 3000

id: 1
event: snapshot
data: {"event":{...},"room":{...},"seats":[...]}

id: 2
event: seats.updated
data: {"seats":[{...},{...}]}

: keep-alive
```

- `404` (`EVENT_NOT_FOUND`): el evento no existe. Se responde **antes** de abrir
  el stream, como respuesta HTTP normal.

**Reglas de este canal, normativas:**

1. **El primer evento siempre es `snapshot`.** Su `data` es exactamente el mismo
   objeto que devuelve `GET /events/{event_id}/seats` (Sección 4.5), con las
   mismas reglas. El Frontend no necesita hacer esa consulta antes de abrir el
   stream: si lo hace, se expone a perder los cambios ocurridos entre las dos
   llamadas.

2. **`seats.updated` transporta butacas completas.** Su `data` es
   `{"seats": [...]}`, donde cada elemento tiene la forma del objeto `seat` de la
   Sección 4.5, con todos sus campos. No se envían diferencias ni identificadores
   sueltos: el Frontend reemplaza cada butaca recibida por su versión nueva y no
   recalcula nada.

3. **Una operación por lote produce un solo evento.** Retener tres butacas emite
   un `seats.updated` con tres butacas, no tres eventos. Es coherente con el
   "todo o nada" de las Secciones 4.6 y 4.7.

4. **`id` es un número entero creciente dentro de la conexión.** Sirve para
   descartar eventos fuera de orden. No es un identificador global ni comparable
   entre conexiones distintas.

5. **El servidor no repone eventos perdidos.** Si el cliente se reconecta —el
   navegador lo hace solo—, el servidor ignora la cabecera `Last-Event-ID` y
   vuelve a emitir un `snapshot` completo. Es más simple y más seguro que un
   buffer: el estado completo siempre es reconstruible.

6. **Hay latido cada 20 segundos.** Una línea de comentario (`: keep-alive`),
   que `EventSource` descarta. Existe para que ningún intermediario corte la
   conexión por inactividad. El Frontend puede usar su ausencia como señal de que
   el canal se cayó.

7. **Una vez abierto el stream no hay más códigos HTTP.** Si algo falla del lado
   del servidor, la conexión se cierra. El Frontend debe tratar el cierre como
   evento normal y dejar que la reconexión ocurra.

---

## 5. Catálogo de códigos de error

| Código | HTTP | Campo extra | Cuándo |
|---|---|---|---|
| `EVENT_NOT_FOUND` | 404 | — | El evento no existe. |
| `USER_NOT_FOUND` | 404 | — | El usuario no existe. |
| `SEATS_NOT_FOUND` | 404 | `seat_ids` | Alguna butaca no existe en esa sala. |
| `HOLD_NOT_FOUND` | 404 | — | La retención no existe. |
| `HOLDS_NOT_FOUND` | 404 | `hold_ids` | Alguna retención no existe o es de otro usuario. |
| `SEATS_UNAVAILABLE` | 409 | `seat_ids` | Butacas tomadas por otro usuario. |
| `HOLDS_NOT_CONFIRMABLE` | 409 | `hold_ids` | Retenciones vencidas, liberadas o ya confirmadas. |
| `HOLD_NOT_RELEASABLE` | 409 | — | La retención está confirmada. |
| `INVALID_REQUEST` | 422 | — | El cuerpo no cumple la forma declarada. |
| `NOT_IMPLEMENTED` | 501 | — | Endpoint definido en el contrato y todavía no construido. |

Esta lista es cerrada. Un código que no esté acá no debe aparecer en una
respuesta.

---

## 6. Flujo de referencia para el Frontend

```text
GET /users
    └── el usuario elige quién es

GET /events
    └── elige un evento

GET /events/{event_id}/stream       ← se abre y queda escuchando
    └── snapshot inicial: dibuja el mapa
    └── seats.updated: actualiza butacas sueltas

GET /events/{event_id}/seats        ← consulta periódica de respaldo
    └── selecciona butacas

POST /events/{event_id}/holds
    └── recibe los hold_id y el expires_at

DELETE /holds/{hold_id}
    └── saca una butaca de la selección

POST /holds/confirm
    └── confirma las que quedaron
```

### 6.1. Actualización del mapa

El mapa se mantiene actualizado por dos vías, y hacen falta las dos:

1. **El canal de eventos (Sección 4.9)** entrega los cambios producidos por
   acciones de otros usuarios: retenciones, liberaciones y confirmaciones. Es la
   vía principal y la que da la sensación de tiempo real.

2. **Una consulta periódica a `GET /events/{event_id}/seats`**, con un intervalo
   holgado —30 segundos es razonable; el contrato no lo fija—, cubre lo que el
   canal no notifica: el vencimiento de retenciones (ver 6.5) y cualquier evento
   perdido mientras el canal estuvo caído.

Un Frontend que solo escuche el canal va a mostrar butacas retenidas que ya
vencieron. Un Frontend que solo consulte por *polling* funciona, pero con el
retraso del intervalo.

### 6.2. El `409` es parte del flujo normal

Con varios usuarios mirando el mismo mapa, dos personas van a ver la misma
butaca libre y una va a perder. **`SEATS_UNAVAILABLE` no es una falla del
sistema ni un error del usuario.** El Frontend debe refrescar el mapa, avisar
cuáles butacas se perdieron —vienen en `seat_ids`— y dejar seguir. Una pantalla
de error genérica en ese caso es un defecto del Frontend.

### 6.3. La cuenta regresiva

`expires_at` es la fecha límite. El Frontend puede mostrar el tiempo restante,
pero **no debe asumir que la retención sigue viva porque su reloj todavía no
llegó**: el reloj del navegador puede estar corrido. La verdad la dice el
servidor en la respuesta siguiente.

### 6.4. Quien ejecuta la acción no espera el evento

El cliente que hace `POST /events/{id}/holds`, `POST /holds/confirm` o
`DELETE /holds/{id}` actualiza su pantalla **con la respuesta HTTP**, no con el
evento que va a llegar por el canal.

El canal es para los demás clientes. Esperar el evento propio introduce una
carrera entre la respuesta y la notificación, y hace que un error de conexión
del stream se vea como una operación que no se hizo, cuando en realidad sí se
hizo.

El evento correspondiente va a llegar igual, con el mismo estado. Aplicarlo dos
veces es inofensivo: las butacas se reemplazan por su versión nueva y el
resultado es idéntico.

### 6.5. El vencimiento no lo anuncia nadie

Cuando una retención vence, no se ejecuta código en el servidor: el reloj no
dispara nada. Por eso **el canal no emite ningún evento cuando una butaca pasa de
`HELD` a `AVAILABLE` por vencimiento**.

El Frontend tiene dos herramientas para eso:

- `expires_at`, para mostrar la cuenta regresiva y anticipar visualmente el
  cambio (con la advertencia de la Sección 6.3);
- la consulta periódica de la Sección 6.1, que es la que confirma el estado real.

---

## 7. Reglas de implementación derivadas

Esta sección no es parte de lo que se le promete al consumidor: es lo que el
contrato le obliga al Backend. Está acá porque son consecuencias directas de lo
anterior y no deberían quedar libradas a interpretación.

1. **RET-001 sigue siendo una garantía de la base.** Una butaca no puede tener
   dos retenciones ocupantes para el mismo evento. La protege el índice único
   parcial, no una validación previa. Ver `docs/contrato/base_de_datos.md`.

2. **El vencimiento se calcula en la lectura y se escribe en la escritura.** Son
   dos cosas distintas y hacen falta las dos:
   - `GET /seats` deriva el estado de `(status, expires_at)`, sin escribir nada.
   - La transacción de `POST /holds` marca como `EXPIRED` las retenciones
     vencidas de las butacas pedidas **antes** de insertar, dentro de la misma
     transacción. El índice no puede leer el reloj: `now()` no es inmutable y
     PostgreSQL no la admite en el predicado de un índice. Sin esa escritura,
     una butaca vencida queda bloqueada para siempre aunque el mapa la muestre
     libre.

3. **Todo o nada.** Retención y confirmación por lote son transaccionales. Si
   una butaca del lote falla, no queda ninguna retenida.

4. **Las butacas se procesan en orden ascendente de `seat_id`.** Dos usuarios
   pidiendo lotes que se cruzan en distinto orden pueden trabarse mutuamente y
   provocar un *deadlock*. Ordenar siempre igual lo evita.

5. **Los errores técnicos no cruzan la frontera** (ARQ-008). El
   `IntegrityError` se traduce a una excepción del dominio en el adaptador; ni
   Application ni API conocen SQLAlchemy.

6. **El TTL de una retención es una constante de configuración**, no un valor
   que el cliente pueda enviar. Su valor no es parte del contrato: el Frontend
   lee `expires_at` y no necesita saber cuántos minutos son.

7. **Los eventos se publican después del `commit`, nunca dentro de la
   transacción.** El caso de uso acumula los cambios y un mecanismo posterior al
   `commit` los publica. Publicar antes hace que un `rollback` deje al Frontend
   mostrando una butaca retenida que nunca existió.

8. **El evento y `GET /seats` se arman con la misma proyección.** El cálculo de
   `status`, `hold_id`, `held_by_user_id` y `expires_at` a partir de
   `(status, expires_at)` vive en una sola función, que usan los dos caminos. Dos
   implementaciones del mismo cálculo se desincronizan; es cuestión de tiempo.

9. **La publicación no puede depender del proceso que atendió la petición.** Con
   más de un *worker*, el evento nace en el proceso que resolvió el `POST` y los
   clientes conectados a otro proceso no lo reciben nunca. Mientras el despliegue
   sea de un solo *worker*, alcanza con un mecanismo en memoria, y esa limitación
   debe estar registrada en un ADR. Si deja de serlo, hace falta un canal entre
   procesos (`LISTEN/NOTIFY` de PostgreSQL o un *bus* externo).

10. **El transporte no entra al dominio.** El caso de uso publica un evento de
    dominio contra un puerto; que ese evento termine en SSE, en WebSocket o en
    ningún lado es decisión del adaptador. Application no conoce
    `text/event-stream`.

---

## 8. Lo que este contrato no promete

- Que exista un proceso que venza retenciones en segundo plano. Puede haberlo o
  no; el Frontend no debe depender de eso.
- Un orden estable de `seats` más allá del que permita reconstruir el mapa con
  `x` e `y`.
- Que `hold_id` sea contiguo, ni que su valor tenga relación con el orden de
  creación.
- **Entrega garantizada de los eventos.** Si el canal se cae, los eventos de ese
  intervalo se pierden. El estado completo siempre se puede recuperar con
  `GET /events/{event_id}/seats` o reconectando.
- **Reposición de eventos anteriores.** `Last-Event-ID` no se honra.
- **Notificación de vencimientos.** Ver Sección 6.5.
- **Orden entre conexiones distintas.** El `id` de un evento solo ordena dentro
  de una misma conexión.
- **Un límite conocido de conexiones simultáneas.** El contrato no lo fija y el
  Frontend no debe abrir más de un canal por evento y pestaña.

---

## 9. Decisiones abiertas

Registradas acá para que no se resuelvan por omisión durante la implementación.

- **`held_by_user_id` es visible para todos.** Sin autenticación no hay nada que
  proteger, pero si en algún momento hay usuarios reales, este campo debería
  reemplazarse por un booleano `held_by_me`.
- **Identificadores enteros y correlativos.** Permiten adivinar y contar
  retenciones ajenas. Es aceptable para un trabajo práctico sin autenticación y
  no lo sería en producción.
- **Butacas fuera de venta.** No hay un estado para una butaca rota o una fila
  bloqueada por producción, porque no hay nada en el modelo que lo produzca. Si
  aparece la necesidad, entra como campo de la butaca, no como estado derivado de
  la retención.
