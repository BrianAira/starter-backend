# Alcance del starter

## Objetivo

Backend de un complejo de salas para eventos, usado para estudiar separación de
responsabilidades, reglas de negocio, garantías del esquema y verificación
automática.

## Funcionalidad incluida

- consultar el estado de salud;
- listar los usuarios precargados;
- listar y consultar eventos;
- consultar el mapa de butacas de un evento, con su estado público calculado;
- retener un lote de butacas para un usuario;
- liberar una retención individual;
- confirmar un lote de retenciones;
- recibir, por un canal de eventos, los cambios de estado de las butacas.

El contrato está implementado por completo: no hay operaciones declaradas y sin
construir.

## Fuera de alcance

- Autenticación y autorización. El usuario viaja como dato en la petición.
- Alta y edición de usuarios, eventos, salas y butacas: se cargan una vez, fuera
  de la API.
- Pagos, precios y emisión de entradas.
- Un proceso en segundo plano que venza retenciones. El vencimiento se escribe
  cuando alguien vuelve a tocar esas butacas, y se deriva en cada lectura.
- Publicación de eventos entre varias copias del backend. El canal difunde
  dentro de un solo proceso. Ver ADR-005.

## Contratos aplicables

- Reglas `RET-*`, definidas en `docs/contrato/reglas.md`.
- Restricciones `ARQ-*`, definidas en `docs/contrato/arquitectura.md`.
- Contrato público en `docs/contrato/contrato_api_frontend.md`, ya congelado y
  entregado al equipo de Frontend.
