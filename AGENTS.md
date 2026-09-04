# Instrucciones para agentes

Este archivo define el **procedimiento de trabajo** del agente. No define
arquitectura, alcance ni reglas de negocio: esas decisiones tienen sus
documentos propietarios.

Los identificadores `RET-*` incluyen reglas y definiciones funcionales del área
de retenciones. El agente debe respetar su significado actual sin intentar
reclasificarlos o renumerarlos durante esta tarea.

## Frontera de autoridad

El agente puede **traducir** un criterio a código ejecutable. No puede
**decidir** el criterio.

De ahí se sigue qué puede modificar y qué no:

| Solo lectura | Editable |
|---|---|
| `docs/contrato/criterios_de_aceptacion.md` | `app/` |
| `docs/contrato/contrato_api_frontend.md` | configuración y dependencias |
| El esquema OpenAPI declarado en el código de rutas | documentación derivada |
| `tests/aceptacion/` una vez generado | pruebas nuevas propias |
| `tests/test_arquitectura.py` y `tests/test_garantia_ret001.py` | |
| `herramientas/` | |

Reglas que se derivan de lo anterior:

1. No modificar, eliminar ni omitir una verificación para obtener una ejecución
   en verde.
2. No agregar `skip`, `xfail` ni capturas de excepción que oculten un fallo.
3. No ensanchar tipos, volver opcionales campos obligatorios ni documentar
   respuestas de error del servidor como esperadas para que una herramienta de
   verificación deje de reportarlas.
4. No excluir operaciones de una corrida de verificación para evitar un
   hallazgo. La única exclusión legítima está declarada en los criterios y tiene
   un motivo escrito.
5. Corregir la implementación.
6. **Ante una contradicción entre criterio, contrato e implementación,
   detenerse e informar.** No resolverla por cuenta propia.

## Antes de modificar el repositorio

1. Leer, en este orden:
   - `docs/contrato/alcance.md`;
   - `docs/contrato/reglas.md`;
   - `docs/contrato/arquitectura.md`;
   - `docs/contrato/contrato_api_frontend.md`;
   - `docs/contrato/base_de_datos.md`;
   - `docs/contrato/criterios_de_aceptacion.md`;
   - `docs/contrato/trazabilidad.md`.
2. Informar explícitamente qué archivos se leyeron.
3. Presentar un plan breve con:
   - archivos a crear o modificar;
   - propósito de cada cambio;
   - qué criterio `CA-*` satisface cada parte del plan;
   - riesgos o contradicciones detectadas entre documentos.

## Durante el cambio

1. Respetar las restricciones `ARQ-*` de `docs/contrato/arquitectura.md`.
2. Respetar las reglas `RET-*` de `docs/contrato/reglas.md`.
3. Respetar `docs/contrato/contrato_api_frontend.md`. Rutas, códigos HTTP y
   códigos de error no se modifican sin modificar antes ese documento, y ese
   documento no lo modifica el agente.
4. No ampliar el alcance sin modificar `docs/contrato/alcance.md`.
5. Cuando cambie una regla o restricción, modificar su documento propietario y
   actualizar trazabilidad, pruebas y diagramas afectados.
6. No duplicar definiciones normativas: referenciarlas por identificador.
7. No agregar dependencias o abstracciones sin justificar su necesidad y su
   costo.
8. Mantener cambios pequeños y verificables.

## Al generar verificaciones desde criterios

1. Un archivo por criterio, en `tests/aceptacion/`, nombrado con su
   identificador.
2. El identificador del criterio va en el docstring del test.
3. Cada cláusula del resultado observable produce al menos una aserción. Si una
   cláusula no se puede comprobar, decirlo en lugar de omitirla.
4. La verificación comprueba el comportamiento observable declarado en el
   criterio, no la implementación elegida.

## Antes de finalizar

1. Ejecutar las pruebas pertinentes.
2. Recorrer `docs/contrato/criterios_de_aceptacion.md` y declarar, criterio por
   criterio, si se cumple, no se cumple o no se verificó.
3. Informar:
   - qué cambió;
   - qué pruebas se ejecutaron y con qué resultado;
   - qué quedó pendiente;
   - cualquier diferencia respecto del plan inicial.
4. No declarar terminada una tarea cuyos criterios de aceptación no se
   comprobaron.
