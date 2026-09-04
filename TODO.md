# Pendientes conocidos

Esta lista existe para que las brechas estén escritas en lugar de descubrirse.

## Verificación

- **La conformidad con el esquema OpenAPI no se comprobó todavía** (`CA-021`).
  `schemathesis` está en `requirements.txt` y el comando está en el README. La
  ruta del canal debe excluirse de la corrida: su respuesta no termina y la
  herramienta quedaría esperando hasta agotar el tiempo.
- La suite corre contra SQLite. La garantía de `RET-001` es comprobable ahí
  porque SQLite soporta índices únicos parciales, pero el comportamiento bajo
  concurrencia real solo se observa contra PostgreSQL.
- El canal se verifica sobre su generador, no abriendo una conexión HTTP: el
  cliente de pruebas acumula el cuerpo completo antes de devolver la respuesta,
  y este cuerpo no termina nunca. La comprobación del circuito completo es
  manual, con dos clientes.

## Canal de eventos

- **La difusión vive en la memoria de un proceso.** Con más de una copia del
  backend, un evento no llega a los clientes conectados a otra. Ver ADR-005.
- **No se notifican los vencimientos.** Nadie ejecuta código cuando pasa el
  plazo; esa transición solo se observa al leer. El consumidor necesita una
  consulta periódica de respaldo.
- Un suscriptor lento pierde mensajes: su cola tiene capacidad limitada.
- Cada conexión ocupa un hilo del *pool*. No se midió cuántas conexiones
  simultáneas soporta.

## Modelado

- No hay capacidad máxima de butacas por usuario y evento.
- `held_by_user_id` es visible para todos. Sin autenticación no hay nada que
  proteger; con usuarios reales debería ser un booleano `held_by_me`.
- Los identificadores son enteros correlativos: permiten adivinar y contar
  retenciones ajenas.
