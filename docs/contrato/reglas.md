# Reglas y definiciones del dominio

Este documento reúne las decisiones funcionales vinculadas con las
**retenciones**. Por eso sus identificadores comienzan con `RET`.

`RET` no es una tecnología ni una categoría universal: es el prefijo que usa
este proyecto para poder referenciar estas decisiones desde pruebas, criterios
de aceptación, ADR y trazabilidad.

Algunas entradas son reglas y otras son definiciones necesarias para entender
esas reglas.

## Vocabulario usado por el proyecto

### Estado interno y estado público

El dominio usa internamente `ACTIVE` para una retención temporal vigente. La API
lo traduce al estado público `HELD`, que resulta más claro para Frontend.

```text
Dominio: ACTIVE  →  API: HELD
```

No se cambia el nombre interno porque ya forma parte del código, las pruebas y
los diagramas. La traducción evita que ese detalle se filtre al contrato.

### Estado de una butaca

El estado público de una butaca no se guarda: **se calcula al leer**, a partir
de las retenciones que existen sobre ella y del instante actual. La función que
lo hace es una sola y la usan todas las salidas del sistema.

---

## RET-001 — Una butaca no puede quedar ocupada dos veces

Para un mismo evento y una misma butaca no puede existir más de una retención
que la mantenga ocupada.

La aplicación valida antes de crear. Pero dos solicitudes pueden consultar al
mismo tiempo y encontrar la butaca libre: por eso, además de la validación en
Python, el esquema rechaza el segundo intento.

- **Se evalúa al:** crear una retención.
- **Riesgo principal:** solicitudes concurrentes.
- **Protección elegida:** validación en el core y restricción de unicidad en la
  base de datos.
- **Estado funcional:** vigente.

## RET-002 — Qué significa que una butaca esté ocupada

Definición asociada a RET-001, no una regla independiente.

Una butaca está ocupada para un evento cuando existe una retención que cumple
**las dos** condiciones:

1. su estado interno es `ACTIVE` o `CONFIRMED`;
2. si es temporal, su plazo todavía no venció.

Los estados `EXPIRED` y `RELEASED` no mantienen ocupada la butaca.

Esta definición debe coincidir en todos los lugares donde el sistema calcula la
disponibilidad: el core, la persistencia, la API y la restricción del esquema.

### Decisión de modelado

Una confirmación sigue siendo un estado de `Hold`. Otro diseño podría crear una
entidad distinta, como `Reservation` o `Ticket`. Se conserva el modelo actual
para no ampliar el alcance.

## RET-003 — Solo una retención vigente puede confirmarse

Una retención puede confirmarse únicamente cuando está `ACTIVE` y no venció.

Confirmar una retención `CONFIRMED`, `EXPIRED` o `RELEASED` es una operación
inválida y debe rechazarse.

- **Se evalúa al:** confirmar una retención.
- **Protección actual:** validación en el core.
- **Estado funcional:** vigente.

## RET-004 — Una retención temporal vence

Al crearse, una retención recibe un plazo (`expires_at`). Cuando ese instante
pasa, la retención deja de ocupar la butaca.

El vencimiento se maneja de dos formas, y hacen falta las dos:

- **En la lectura se deriva:** el mapa muestra la butaca disponible sin escribir
  nada.
- **En la escritura se persiste:** antes de insertar una retención nueva, la
  misma transacción marca como `EXPIRED` las retenciones vencidas de esas
  butacas.

El motivo de la segunda parte es concreto: el índice único parcial no puede
mirar el reloj —una función como `now()` no es inmutable y PostgreSQL no la
admite en el predicado de un índice—. Sin esa escritura, una butaca vencida
quedaría bloqueada para siempre aunque el mapa la mostrara libre.

- **Se evalúa al:** leer el mapa y al crear una retención.
- **Estado funcional:** vigente.

## RET-005 — Retener lo propio no crea una retención nueva

Si un usuario pide una butaca que él mismo ya tiene retenida y vigente, se
devuelve la retención existente con su plazo original, en lugar de crear otra o
rechazar el pedido.

Sin esta regla, un doble clic o un reintento del navegador produciría un
conflicto por butacas que ya son suyas.

- **Se evalúa al:** crear una retención.
- **Estado funcional:** vigente.

## RET-006 — Liberar es idempotente y no revierte una confirmación

Un usuario puede soltar una retención vigente: pasa a `RELEASED` y la butaca
vuelve a estar disponible.

Liberar algo que ya está `RELEASED` o `EXPIRED` produce el mismo resultado y no
es un error: el efecto deseado —que la butaca no esté tomada— ya se cumple.

Una retención `CONFIRMED` no se libera. Deshacer una compra sería otra
operación, con otras consecuencias, y está fuera de alcance.

- **Se evalúa al:** liberar una retención.
- **Estado funcional:** vigente.

---

## Reglas todavía fuera de alcance

- Márgenes de montaje y limpieza para una sala.
- Vencimiento en segundo plano: nadie ejecuta código cuando pasa el plazo.

### `RET-007` — Límite de butacas ocupantes por usuario en un evento

Un usuario no puede poseer más de cuatro (4) butacas en estado ocupante
(`ACTIVE` o `CONFIRMED`) para un mismo evento. Si una solicitud hace que el
total de butacas ocupantes supere este límite, la operación debe ser rechazada
de manera atómica con una excepción de dominio, traduciéndose en una respuesta
HTTP `409 Conflict` con el código `USER_HOLD_LIMIT_REACHED`.
