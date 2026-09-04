# Criterios de aceptación — Semana 4

Este documento indica qué evidencias necesitamos antes de considerar terminada
la evolución de la Semana 4. No vuelve a definir las reglas, la arquitectura ni
la API: esas decisiones viven en sus documentos correspondientes.

Los identificadores `CA-*` continúan la numeración de la semana anterior. Los
criterios `CA-001` a `CA-016` siguen vigentes: la suite y el tablero los siguen
comprobando y ninguno se retira.

## Qué cambia esta semana en la forma de trabajar

Hasta ahora los criterios describían qué debía cumplirse y las verificaciones se
escribían aparte. A partir de esta semana **las verificaciones se derivan de los
criterios**: el agente traduce cada criterio a un archivo ejecutable en
`tests/aceptacion/`.

Eso obliga a escribir los criterios de otra manera. Cada uno declara un
resultado observable **en términos del contrato** —código HTTP, código de error,
campo del JSON—, nunca en términos de implementación, y una cláusula por celda.
Contar cláusulas contra aserciones es lo que permite revisar una traducción sin
leer el código.

---

## Reglas del experimento

| ID | Condición |
|---|---|
| `CA-000` | El agente no modifica los instrumentos que lo evalúan ni los documentos que definen qué debe ser verdad. La lista está en la tabla de frontera de autoridad de `AGENTS.md`. |
| `CA-000b` | El agente puede crear pruebas nuevas, pero no reemplazar, desactivar ni debilitar las existentes. |
| `CA-000c` | El agente no afloja el esquema declarado ni excluye operaciones de una corrida de verificación para evitar un hallazgo. |

`CA-000` cambió de forma respecto de la Semana 3. Antes enumeraba archivos de
medición; ahora nombra un principio: **el oráculo queda del lado de la persona**.
La lista de archivos es la aplicación de ese principio, no su definición.

Si el agente propone alterar los instrumentos que lo evalúan, debe detenerse y
explicar el motivo.

---

## Trazabilidad entre criterios y verificaciones

### `CA-017` — Toda verificación derivada apunta a un criterio existente

Cada archivo de `tests/aceptacion/` declara en su docstring un identificador
`CA-*` que existe en este documento, y todo criterio marcado como derivable
tiene al menos un archivo que lo referencia.

- **Resultado observable:** no hay verificaciones huérfanas ni criterios sin
  verificación derivada.
- **Comprobación:** control de sincronía cruzada, análogo al del diagrama de
  estados.

---

## Liberación de una retención

### `CA-018` — `DELETE /holds/{hold_id}` libera una retención vigente

| | |
|---|---|
| Precondición | Existe una retención en estado público `HELD`. |
| Acción | `DELETE /holds/{hold_id}` |
| Resultado | El código de respuesta es `204`. |
| Resultado | La respuesta no tiene cuerpo. |
| Resultado | La retención queda en estado `RELEASED`. |
| Resultado | La butaca vuelve a aparecer con `status` igual a `AVAILABLE` en `GET /events/{event_id}/seats`. |

- **Relacionado con:** `RET-002`, y la operación declarada en el contrato.
- **Nota:** la ruta respondía `501 NOT_IMPLEMENTED` hasta que se construyó.
  Estaba en el contrato y no estaba hecha, que no es lo mismo que no existir.

### `CA-019` — Liberar es idempotente

| | |
|---|---|
| Precondición | Una retención ya está en estado `RELEASED` o `EXPIRED`. |
| Acción | `DELETE /holds/{hold_id}` |
| Resultado | El código de respuesta es `204`. |

El efecto deseado ya se cumple, y un reintento no debe parecer un error.

### `CA-020` — Una retención confirmada no se libera

| | |
|---|---|
| Precondición | Una retención está en estado `CONFIRMED`. |
| Acción | `DELETE /holds/{hold_id}` |
| Resultado | El código de respuesta es `409`. |
| Resultado | El cuerpo contiene `code` igual a `HOLD_NOT_RELEASABLE`. |

---

## Cumplimiento del contrato

### `CA-021` — La implementación cumple el esquema declarado

**Pendiente.** Es el único criterio que todavía no se comprobó: la herramienta
está instalada y el comando está en el README, pero la corrida no se hizo.

Una corrida de verificación basada en el esquema OpenAPI no reporta hallazgos.

- **Resultado observable:** ninguna respuesta con estructura no declarada;
  ninguna respuesta de error del servidor ante entradas generadas desde el
  esquema.
- **Exclusión declarada:** la ruta del canal de eventos queda fuera de esta
  corrida, porque su respuesta no termina y la herramienta quedaría esperando
  hasta agotar el tiempo. Es la única exclusión permitida y este es su motivo.

---

## Publicación de eventos

### `CA-022` — Retener publica un evento con las butacas afectadas

| | |
|---|---|
| Precondición | Hay butacas disponibles en un evento. |
| Acción | `POST /events/{event_id}/holds` con dos butacas. |
| Resultado | Se publica exactamente un evento. |
| Resultado | El evento contiene las dos butacas, con la forma del objeto `seat` del contrato. |
| Resultado | Las butacas del evento tienen `status` igual a `HELD`. |

- **Comprobación:** publicador espía en lugar del adaptador real.

### `CA-023` — El evento se publica después del `commit`

| | |
|---|---|
| Precondición | Una operación de retención falla y revierte la transacción. |
| Acción | `POST /events/{event_id}/holds` sobre una butaca ya ocupada. |
| Resultado | No se publica ningún evento. |

### `CA-024` — El evento se serializa con el formato del canal

| | |
|---|---|
| Precondición | Existe un evento de dominio con butacas afectadas. |
| Acción | Se lo entrega al adaptador de salida. |
| Resultado | La salida declara un nombre de evento. |
| Resultado | La salida declara un identificador numérico. |
| Resultado | El contenido es un JSON válido con la clave `seats`. |

### `CA-025` — El primer evento del canal es el estado completo

| | |
|---|---|
| Precondición | Un evento existe y tiene butacas. |
| Acción | Se abre `GET /events/{event_id}/stream`. |
| Resultado | El primer evento recibido es `snapshot`. |
| Resultado | Su contenido tiene la misma forma que la respuesta de `GET /events/{event_id}/seats`. |

- **Nota:** se verifica sobre el generador del canal, no abriendo una conexión
  HTTP. El cliente de pruebas acumula el cuerpo completo antes de devolver la
  respuesta, y este cuerpo no termina nunca. La comprobación del circuito
  entero, con dos clientes reales, es manual y está descrita en el README.

---

## Arquitectura

### `CA-026` — El transporte no entra al dominio

`app/core` y `app/application` no importan el framework web, el adaptador del
canal ni ninguna biblioteca de transporte.

- **Relacionado con:** `ARQ-008`.
- **Comprobación:** inspección AST, junto con las restricciones anteriores.

---

## Documentación y consumidor

### `CA-027` — El contrato incorpora el canal y sus límites

El documento del contrato declara la operación del canal, la forma del evento,
el comportamiento ante reconexión y qué no promete.

- **Comprobación:** revisión.

### `CA-028` — El consumidor tiene una nota de cambios

Existe una nota dirigida al equipo de Frontend que permite adaptarse sin leer el
contrato completo.

- **Comprobación:** revisión.

### `CA-029` — La limitación de la publicación en memoria está registrada

Un ADR y la sección de límites del contrato dejan constancia de que las
conexiones y los eventos viven en la memoria de un proceso, y de que un
despliegue con varias copias del backend requeriría un mecanismo compartido de
publicación, cuya resolución queda fuera de alcance.

- **Comprobación:** revisión.

### `CA-013` a `CA-016` — siguen vigentes

Diagrama sincronizado, trazabilidad actualizada, documento propietario por
decisión y alcance razonable del cambio.

---

## Límites de estas comprobaciones

Un tablero en verde significa que el proyecto satisface **estas verificaciones**.
No demuestra por sí solo:

- que el código sea fácil de mantener;
- que los mensajes sean claros para una persona;
- que el canal funcione con más de una copia del backend corriendo;
- que el rendimiento sea suficiente con muchas conexiones abiertas;
- que no existan problemas en operaciones no cubiertas.

Y hay un límite nuevo, propio de esta semana: las verificaciones fueron
**traducidas** por el agente a partir de criterios escritos por personas. Una
traducción laxa —un criterio con tres cláusulas comprobado con una sola
aserción— produce un verde que no corresponde. Por eso los criterios se escriben
con una cláusula por celda: para que revisarlos sea contar, y no leer código.

El agente propone cambios. Las pruebas y verificaciones aportan evidencia. La
responsabilidad final sigue siendo del equipo.
