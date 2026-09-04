# Trazabilidad

Este documento no vuelve a explicar las decisiones. Conecta cada identificador
con el código, la API y la evidencia que lo verifica.

`RET-002` se conserva como identificador porque el proyecto ya lo referencia,
aunque en `reglas.md` funcione como definición asociada a `RET-001`.

## Reglas de negocio

| ID | Implementación | Caso de uso | Exposición | Verificación |
|---|---|---|---|---|
| RET-001 (validación) | `app/core/rules.py::validar_creacion_retencion` | `use_cases.crear_retenciones` | `POST /events/{event_id}/holds` → `409 SEATS_UNAVAILABLE` | `tests/test_rules.py`, `tests/test_events.py` |
| RET-001 (garantía) | índice único parcial (`alembic/versions/0001_esquema_inicial.py`) + traducción del error en `app/infrastructure/repository.py` | — | idem | `tests/test_garantia_ret001.py` |
| RET-002 | `app/core/rules.py::esta_vigente`, `ocupante_de_butaca` | todas las lecturas | `GET /events/{event_id}/seats` | `tests/test_rules.py`, `tests/test_garantia_ret001.py` |
| RET-003 | `app/core/rules.py::validar_confirmacion` | `use_cases.confirmar_retenciones` | `POST /holds/confirm` → `409 HOLDS_NOT_CONFIRMABLE` | `tests/test_rules.py`, `tests/test_events.py` |
| RET-004 (derivación) | `app/core/rules.py::esta_vencida`, `proyectar_butaca` | `use_cases.obtener_mapa` | `GET /events/{event_id}/seats` | `tests/test_rules.py` |
| RET-004 (persistencia) | `app/infrastructure/repository.py::marcar_vencidas` | `use_cases.crear_retenciones` | — | `tests/test_garantia_ret001.py` |
| RET-005 | `app/core/rules.py::validar_creacion_retencion` | `use_cases.crear_retenciones` | `POST /events/{event_id}/holds` → `201` con la retención existente | `tests/test_rules.py`, `tests/test_events.py` |
| RET-006 | `app/core/rules.py::validar_liberacion` | `use_cases.liberar_retencion` | `DELETE /holds/{hold_id}` → `204` / `409 HOLD_NOT_RELEASABLE` | `tests/aceptacion/test_ca_018_*`, `test_ca_019_*`, `test_ca_020_*` |

`RET-001` aparece dos veces a propósito: el core valida antes y la base aplica
una restricción frente a escrituras concurrentes. Son dos protecciones de la
misma regla y se verifican de manera distinta. Ver `ARQ-009`.

`RET-004` aparece dos veces por el mismo motivo: una parte se calcula al leer y
otra se escribe al crear.

## Restricciones de arquitectura

| ID | Verificación |
|---|---|
| ARQ-001 | revisión humana |
| ARQ-002 | `tests/test_arquitectura.py::test_arq_002_core_independiente` |
| ARQ-003 | `tests/test_arquitectura.py::test_arq_003_application_no_importa_infrastructure` |
| ARQ-004, ARQ-005 | revisión humana |
| ARQ-006, ARQ-007 | `tests/test_arquitectura.py::test_arq_006_core_no_conoce_puertos` |
| ARQ-008 | `herramientas/evaluar_semana4.py` (inspección AST) |
| ARQ-009 | revisión humana |
| ARQ-010 | `herramientas/evaluar_semana4.py` (inspección AST, junto con ARQ-008) |

## Contrato de la API

| Elemento | Definición | Verificación |
|---|---|---|
| Rutas y códigos HTTP | `docs/contrato/contrato_api_frontend.md` | `herramientas/evaluar_semana4.py` (contra el OpenAPI de la app) |
| Forma de las respuestas | idem | `tests/test_events.py`; verificación contra el esquema, pendiente (`CA-021`) |
| Canal de eventos | idem, Sección 4.9 | `tests/aceptacion/test_ca_022_*` a `test_ca_025_*` |

## Criterios de aceptación

Cada criterio derivable tiene su verificación en `tests/aceptacion/`, un archivo
por criterio, con el identificador en el docstring. La correspondencia en los
dos sentidos la comprueba `herramientas/evaluar_semana4.py` (`CA-017`).

## Documentos derivados

| Documento | Se genera con | Se verifica con |
|---|---|---|
| `docs/diagramas/estados_retencion.md` | `herramientas/generar_diagrama_estados.py` | el mismo script con `--verificar` |
