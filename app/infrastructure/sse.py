"""
Adaptador de salida: canal Server-Sent Events.

Traduce un evento de dominio (`SeatsChanged`) al formato del canal y lo
entrega al difusor del proceso. Es el único lugar del sistema que sabe
qué es `text/event-stream`.

Formato de un evento, según la Sección 4.9 del contrato:

    id: 2
    event: seats.updated
    data: {"seats": [...]}

Ver ARQ-010: ni Core ni Application conocen este módulo.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app.core.entities import SeatsChanged, SeatView
from app.infrastructure.broker import InMemoryBroker, broker as broker_del_proceso

#: Nombres de evento del canal. Son parte del contrato.
EVENTO_SNAPSHOT = "snapshot"
EVENTO_BUTACAS = "seats.updated"

#: Cada cuánto se manda un latido para que ningún intermediario corte la
#: conexión por inactividad.
LATIDO_SEG = 20.0


def _utc_z(valor: datetime | None) -> str | None:
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def butaca_a_dict(vista: SeatView) -> dict[str, Any]:
    """
    Serializa una butaca con la misma forma que devuelve
    `GET /events/{event_id}/seats`. Es deliberado: el consumidor reemplaza
    la butaca por su versión nueva y no recalcula nada.
    """
    return {
        "id": vista.seat.id,
        "label": vista.seat.label,
        "row": vista.seat.row,
        "number": vista.seat.number,
        "x": vista.seat.x,
        "y": vista.seat.y,
        "sector": vista.seat.sector,
        "status": vista.status.value,
        "hold_id": vista.hold_id,
        "held_by_user_id": vista.held_by_user_id,
        "expires_at": _utc_z(vista.expires_at),
    }


def mensaje_de_cambio(evento: SeatsChanged) -> dict[str, Any]:
    """Convierte el evento de dominio en el mensaje que viaja por el canal."""
    return {
        "event": EVENTO_BUTACAS,
        "data": {"seats": [butaca_a_dict(v) for v in evento.seats]},
    }


def formatear(mensaje: dict[str, Any], id_evento: int) -> str:
    """
    Arma el bloque de texto de un evento SSE.

    Cada bloque termina con una línea en blanco: es lo que le indica al
    cliente que el evento está completo.
    """
    cuerpo = json.dumps(mensaje["data"], ensure_ascii=False, separators=(",", ":"))
    return f"id: {id_evento}\nevent: {mensaje['event']}\ndata: {cuerpo}\n\n"


def latido() -> str:
    """Comentario SSE. El cliente lo descarta; los intermediarios no."""
    return ": keep-alive\n\n"


def mensaje_snapshot(evento, sala, vistas) -> dict[str, Any]:
    """
    Estado completo del mapa, con la misma forma que devuelve
    `GET /events/{event_id}/seats`. Es el primer evento de toda conexión:
    así el cliente no necesita consultar el mapa aparte y arriesgarse a
    perder los cambios ocurridos entre ambas llamadas.
    """
    return {
        "event": EVENTO_SNAPSHOT,
        "data": {
            "event": {
                "id": evento.id,
                "name": evento.name,
                "starts_at": _utc_z(evento.starts_at),
            },
            "room": {
                "id": sala.id,
                "name": sala.name,
                "rows": sala.rows,
                "columns": sala.columns,
            },
            "seats": [butaca_a_dict(v) for v in vistas],
        },
    }


def generar_stream(inicial: dict[str, Any], suscripcion, latido_seg: float = LATIDO_SEG):
    """
    Produce el cuerpo del canal: sugerencia de reconexión, snapshot y
    después un evento por cada cambio, con latidos mientras no pasa nada.

    Es un generador sincrónico a propósito: Starlette lo ejecuta en un
    hilo aparte, que es donde la espera bloqueante de la cola no molesta
    a nadie. Está separado del endpoint para poder probarlo sin abrir una
    conexión HTTP que nunca termina.
    """
    siguiente_id = 1
    try:
        yield "retry: 3000\n\n"
        yield formatear(inicial, siguiente_id)
        siguiente_id += 1

        while True:
            mensaje = suscripcion.esperar(timeout=latido_seg)
            if mensaje is None:
                yield latido()
                continue
            yield formatear(mensaje, siguiente_id)
            siguiente_id += 1
    finally:
        broker_del_proceso.desuscribir(suscripcion)


class SseEventPublisher:
    """
    Implementación del puerto `EventPublisher` sobre el difusor del proceso.

    Recibe el difusor por parámetro para que las pruebas puedan usar uno
    propio en lugar del global.
    """

    def __init__(self, difusor: InMemoryBroker | None = None) -> None:
        self._difusor = difusor or broker_del_proceso

    def publish(self, event: SeatsChanged) -> None:
        self._difusor.publicar(event.event_id, mensaje_de_cambio(event))
