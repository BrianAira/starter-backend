"""
CA-025 — El primer evento del canal es el estado completo.

Se prueba el generador del canal directamente, no a través del cliente de
pruebas: `TestClient` acumula el cuerpo completo antes de devolver la
respuesta, y este cuerpo no termina nunca. Es el ejemplo más claro de por
qué la prueba integral del canal es la más frágil de todas.
"""

import json

from app.application import use_cases
from app.infrastructure import sse
from app.infrastructure.broker import InMemoryBroker


def _leer(bloque: str) -> tuple[str, dict]:
    lineas = [l for l in bloque.splitlines() if l]
    nombre = next(l[len("event: ") :] for l in lineas if l.startswith("event: "))
    datos = next(l[len("data: ") :] for l in lineas if l.startswith("data: "))
    return nombre, json.loads(datos)


def test_ca_025(repo):
    evento, sala, vistas = use_cases.obtener_mapa(repo, 1)
    difusor = InMemoryBroker()

    generador = sse.generar_stream(
        sse.mensaje_snapshot(evento, sala, vistas),
        difusor.suscribir(1),
        latido_seg=0.05,
    )

    assert next(generador).startswith("retry:")

    nombre, datos = _leer(next(generador))
    assert nombre == "snapshot"
    assert set(datos) == {"event", "room", "seats"}
    assert datos["room"]["rows"] == 5
    assert len(datos["seats"]) == 40

    generador.close()


def test_ca_025_un_cambio_llega_como_seats_updated(repo):
    """El segundo evento en adelante transporta butacas completas."""
    evento, sala, vistas = use_cases.obtener_mapa(repo, 1)
    difusor = InMemoryBroker()
    suscripcion = difusor.suscribir(1)

    generador = sse.generar_stream(
        sse.mensaje_snapshot(evento, sala, vistas), suscripcion, latido_seg=0.05
    )
    next(generador)  # retry
    next(generador)  # snapshot

    use_cases.crear_retenciones(
        repo,
        event_id=1,
        user_id="user-1",
        seat_ids=[4],
        publisher=sse.SseEventPublisher(difusor),
    )

    nombre, datos = _leer(next(generador))
    assert nombre == "seats.updated"
    assert datos["seats"][0]["id"] == 4
    assert datos["seats"][0]["status"] == "HELD"
    assert datos["seats"][0]["held_by_user_id"] == "user-1"

    generador.close()


def test_ca_025_evento_inexistente(client):
    """Antes de abrir el canal todavía se puede responder un código HTTP."""
    respuesta = client.get("/events/999/stream")
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"]["code"] == "EVENT_NOT_FOUND"
