# La frontera entre core y application

> **Carácter del documento:** material didáctico. No define reglas ni restricciones. La arquitectura vigente está en `docs/contrato/arquitectura.md` y las reglas en `docs/contrato/reglas.md`.


## Por qué existe este documento

Este apartado nace de una
pregunta que parece simple: *¿dónde vive una regla de negocio?* La
respuesta corta ("en el core") suena obvia, pero al llevarla al código
aparecen ambigüedades que conviene desarmar con cuidado. Este es
justamente el tipo de conocimiento que rara vez se explicita y que
separa "escribir un backend" de "poder auditar uno".

## 1. "La regla vive en el core" — qué significa realmente

No significa que el core sea el único lugar con protección. Significa,
más angostamente, que **el core es el único lugar donde la regla está
expresada en términos de negocio, sin depender de ninguna tecnología.**

Hay que separar dos ideas que se confunden bajo la palabra "garantía":

- **Declarar la regla:** enunciar la invariante del negocio (RET-001).
  Esto vive en `app/core/rules.py`, como función pura.
- **Garantizar su cumplimiento:** el mecanismo que hace que la regla no
  se viole nunca, ni bajo concurrencia. Esto puede requerir apoyo de
  infraestructura (una restricción única, una transacción).

Dos verbos útiles para no confundirse: una regla puede estar
*asegurada* (funciona en el camino feliz) sin estar *garantizada* (no
falla ni siquiera bajo concurrencia). En la Semana 1, RET-001 está
asegurada pero no garantizada; `tests/test_race_demo.py` demuestra
exactamente esa diferencia.

## 2. Quién pregunta, quién contesta, quién ejecuta

La dirección de las preguntas es siempre una sola:

- **Application pregunta.** Es la única capa que orquesta: decide qué
  necesita y a quién pedírselo (al core y al puerto).
- **Core contesta.** Nunca inicia una llamada hacia afuera. Recibe datos
  como parámetros, calcula, devuelve. Es pasivo respecto de Application.
- **Infrastructure ejecuta.** Hace lo que se le pide (leer, escribir) y
  traduce errores técnicos, sin interpretar su significado de negocio.

Regla mental: **el core recibe todo, decide una vez, devuelve una vez.**
No hay diálogo, no hay ida y vuelta: es como una calculadora, no como un
interlocutor.

## 3. La prueba del verbo

Una heurística barata para auditar en qué capa debería vivir una función,
solo por su nombre:

- Verbos de pregunta o cálculo (`puede_...`, `es_valido...`,
  `calcular_...`, `determinar_...`) → probablemente **core**.
- Verbos de acción con resultado incierto (`intentar_...`, `crear_...`,
  `confirmar_...`, `reservar_...`) → probablemente **caso de uso**
  (Application).

Ejemplo de la trampa: `intentar_reservar` suena a core pero no lo es.
"Intentar" implica que puede fallar por causas externas (otro proceso
llegó antes) — eso es orquestación de una acción con efectos, trabajo de
Application. `puede_crear_retencion`, en cambio, es una pregunta pura:
dada esta lista de retenciones, ¿se puede? Esa sí es core.

## 4. TOCTOU: por qué el core "acierta" y aun así la regla se viola

TOCTOU = *Time Of Check To Time Of Use* (del momento en que se verifica
al momento en que se usa). Es la clave para entender por qué una función
pura no alcanza para garantizar RET-001 bajo concurrencia.

El flujo es:

```
1. Application consulta las retenciones existentes   (lee)
2. Application se las pasa al core
3. Core decide "sí, se puede"                         (instantáneo)
4. Application persiste la nueva retención            (escribe)
```

El peligro no está *dentro* de la función del core (que es instantánea e
ininterrumpible). Está en el hueco **entre el paso 1 y el paso 4**: si
dos peticiones concurrentes leen el mismo estado en el paso 1 (nadie
escribió todavía), ambas reciben "sí, se puede" en el paso 3, y ambas
escriben en el paso 4. El core no mintió: contestó bien para la foto que
le dieron. El problema es que la foto quedó vieja antes de aplicarse.

Esto **no se arregla** haciendo que el core pregunte de nuevo. Se
arregla dejando que la base de datos rechace la segunda escritura,
porque la base es el único punto con visibilidad simultánea sobre todos
los intentos concurrentes. El core nunca tuvo esa visibilidad, ni la va
a tener. Por eso la garantía final vive en Infrastructure (Semana 3), no
en el core.

## 5. Inyección de dependencias: por qué el core no la necesita

La inyección de dependencias resuelve el problema de "esta función
necesita algo externo y no quiero que decida qué implementación usar".
Solo tiene sentido cuando hay un colaborador externo que inyectar (un
repositorio, un servicio, un reloj).

El core no tiene colaboradores externos: recibe datos simples (listas,
entidades, valores), nunca objetos con comportamiento externo. Por eso
la pregunta "¿qué le inyecto al core?" ni siquiera aplica. Si alguna vez
sentís la tentación de inyectarle un repositorio al core, es la señal de
que esa función dejó de ser core y se volvió un caso de uso.

## 6. La zona gris honesta: DIP y la teoría estricta

Para ser justos con la teoría: Clean Architecture, en su formulación
general, **permitiría** que el núcleo llame a una fuente externa a
través de un puerto sin romper la regla de dependencia (eso es
Dependency Inversion). También es discutible, incluso citando a Robert
C. Martin, si RET-001 es una "enterprise business rule" (que iría en
Entities) o una "application business rule" (que iría en Use Cases). La
teoría no da una respuesta única.

Por eso nuestra postura no es "la teoría prohíbe X", sino: **elegimos la
interpretación más estricta y más simple**, con dos motivos concretos —
testeo sin dobles de prueba y verificación automática por test. Es una
decisión de diseño defendible, no una cita de autoridad. Cuando la
teoría admite varias lecturas válidas, elegir la más verificable es una
buena política, sobre todo si el sistema va a ser dirigido y auditado
con ayuda de agentes de IA.

## 7. El caso real del propio starter

Ni siquiera este material fue "puro" de entrada. En su versión inicial,
`app/application/use_cases.py` importaba directamente
`app.infrastructure.repository` — una fuga real de la regla de
dependencia. No fue un descuido: fue una decisión de alcance defendible
bajo YAGNI (no abstraer hasta necesitarlo). En la Semana 2 se resolvió
introduciendo el puerto, y la decisión completa (con su costo) quedó
documentada en `docs/adr/ADR-002.md` y verificada en
`tests/test_arquitectura.py`.

La lección para los cursantes: encontrar y documentar una fuga real en
tu propio código es mejor auditoría que repetir la teoría perfecta.
