# Informe de Entrega: Implementación de Regla RET-007

* **Unidad:** Desarrollo Backend — Entrega Integradora Unidad 2  
* **Proyecto:** Sistema de Reservas y Gestión de Eventos  
* **Regla Implementada:** `RET-007` (Límite de 4 butacas ocupantes por usuario por evento)

---

## 1. Resumen de la Solución y Artefactos Modificados

Se implementó el control de la invariante de agregado que limita a un máximo de **cuatro (4) butacas** por usuario en estado ocupante (`ACTIVE` o `CONFIRMED`) para un mismo evento. La validación se ejecuta de manera atómica dentro de la transacción del caso de uso antes de persistir las nuevas retenciones.

### Artefactos Documentales y Normativos
* **Reglas de Negocio (`docs/contrato/reglas.md`):** Formalización de la regla `RET-007` y actualización de la sección de alcance.
* **Registro de Decisión de Arquitectura (`docs/adr/ADR-007.md`):** Documentación de la estrategia de validación en la capa de aplicación y justificación de las alternativas descartadas (índices únicos y bloqueos pesimistas).
* **Contrato de API (`docs/contrato/contrato_api_frontend.md`):** Incorporación del código de error HTTP `409 Conflict` con la clave `USER_HOLD_LIMIT_REACHED`.
* **Matriz de Trazabilidad (`docs/contrato/trazabilidad.md`):** Mapeo de la regla `RET-007` con su implementación y suite de pruebas.

### Artefactos de Código Fuente
* **`app/core/rules.py`:** Definición de la excepción de dominio pura `LimiteButacasUsuarioError` y la función de regla `validar_limite_butacas_usuario()`.
* **`app/application/ports.py`:** Definición del método `contar_butacas_ocupantes_de_usuario()` en el puerto `HoldRepository`.
* **`app/application/use_cases.py`:** Integración atómica de la validación previo a la creación de las retenciones.
* **`app/infrastructure/repository.py`:** Consulta SQL que calcula la cantidad de butacas ocupantes ignorando las retenciones caducadas (`expires_at < now`).
* **`app/api/routes.py`:** Mapeo de la excepción de dominio al contrato de respuesta HTTP `409`.

---

## 2. Evidencia de Funcionamiento y Cobertura

El funcionamiento del sistema fue verificado mediante herramientas de evaluación automatizada y ejecuciones de pruebas de integración y unitarias sobre el entorno del proyecto.

### Pruebas Automatizadas Específicas (`pytest tests/test_ret007.py -v`)

```text
tests/test_ret007.py::test_un_usuario_puede_retener_hasta_cuatro_butacas PASSED           [ 16%]
tests/test_ret007.py::test_el_limite_rechaza_la_quinta_retencion_activa_por_http PASSED   [ 33%]
tests/test_ret007.py::test_el_limite_incluye_retenciones_confirmadas PASSED               [ 50%]
tests/test_ret007.py::test_retenciones_vencidas_no_cuentan_para_el_limite PASSED          [ 66%]
tests/test_ret007.py::test_retenciones_liberadas_no_cuentan_para_el_limite PASSED         [ 83%]
tests/test_ret007.py::test_el_caso_de_uso_rechaza_el_quinto_cupo_de_forma_atomica PASSED  [100%]

============================== 6 passed in 0.45s ============================== 
```

## 3. Aspectos No Garantizados y Asunciones de Diseño / Daño

Conforme a las decisiones de arquitectura documentadas en el `ADR-007`, la solución establece los siguientes límites operacionales y asunciones de riesgo/daño:

1. **Condiciones de carrera bajo concurrencia extrema:**
   * **No garantizado:** Si un mismo usuario envía dos solicitudes HTTP exactamente simultáneas desde clientes distintos, ambas peticiones podrían leer el mismo conteo inicial antes de que alguna de las dos inserte en la base de datos, posibilitando eventualmente superar el límite de 4 butacas.
   * **Justificación:** Se descartó el uso de bloqueos pesimistas (`SELECT FOR UPDATE`) o transacciones de nivel de aislamiento serializable para evitar contención de memoria, cuellos de botella y alta latencia en la base de datos durante picos de demanda. Este riesgo marginal bajo peticiones simultáneas del mismo ID de usuario fue explícitamente aceptado.

2. **Dependencia de procesos en segundo plano:**
   * **Garantizado por consulta:** El sistema no depende de un proceso o worker en segundo plano (Cron/Sweeper) para limpiar físicamente las retenciones vencidas antes de permitir una nueva compra. El repositorio filtra lógicamente comprobando `expires_at > now`, garantizando que las retenciones caducadas no bloqueen el cupo del usuario independientemente del estado de la limpieza física.

3. **Asunciones de impacto/daño ante fallas de infraestructura:**
   * **Aislamiento de fallas:** Si la base de datos experimenta degradación o la transacción se interrumpe a mitad del proceso, la regla de negocio garantiza el comportamiento *todo o nada* (atomicidad), abortando el lote completo sin dejar butacas parcialmente reservadas.
   * **Comportamiento no garantizado ante fallas de red:** En caso de interrupción de red justo después del `COMMIT` en la base de datos pero antes de la respuesta HTTP al cliente, el cliente no recibirá la confirmación directa pero las butacas quedarán retenidas en el backend hasta su expiración natural (`expires_at`), asumiendo ese impacto como un costo aceptable para priorizar la integridad de los datos.