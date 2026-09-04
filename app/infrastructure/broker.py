"""
Difusión de eventos dentro del proceso.

Mantiene una lista de suscriptores y les entrega cada evento publicado.
Usa colas sincronizadas (`queue.Queue`) porque el productor —una petición
HTTP que retiene o confirma— y el consumidor —una conexión abierta que
espera— corren en hilos distintos.

LIMITACIÓN CONOCIDA
-------------------
Las conexiones y los eventos viven en la memoria de este proceso. Con más
de una copia del backend corriendo, un evento producido en una copia no
llega a los clientes conectados a otra. Resolverlo requiere sacar la
difusión afuera de los procesos y queda fuera de alcance. Ver ADR-005 y
la Sección 8 del contrato.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any, Iterator

#: Cuántos eventos puede acumular un suscriptor lento antes de descartar.
CAPACIDAD_POR_SUSCRIPTOR = 100


@dataclass
class Suscripcion:
    """Cola propia de un cliente conectado, filtrada por evento."""

    event_id: int
    cola: "queue.Queue[dict[str, Any]]"

    def esperar(self, timeout: float) -> dict[str, Any] | None:
        """Devuelve el próximo mensaje, o None si venció la espera."""
        try:
            return self.cola.get(timeout=timeout)
        except queue.Empty:
            return None


class InMemoryBroker:
    """Difusor en memoria. Un solo proceso, sin persistencia."""

    def __init__(self) -> None:
        self._suscripciones: list[Suscripcion] = []
        self._candado = threading.Lock()

    def suscribir(self, event_id: int) -> Suscripcion:
        suscripcion = Suscripcion(
            event_id=event_id,
            cola=queue.Queue(maxsize=CAPACIDAD_POR_SUSCRIPTOR),
        )
        with self._candado:
            self._suscripciones.append(suscripcion)
        return suscripcion

    def desuscribir(self, suscripcion: Suscripcion) -> None:
        with self._candado:
            if suscripcion in self._suscripciones:
                self._suscripciones.remove(suscripcion)

    def publicar(self, event_id: int, mensaje: dict[str, Any]) -> None:
        with self._candado:
            destinatarios = [
                s for s in self._suscripciones if s.event_id == event_id
            ]
        for suscripcion in destinatarios:
            try:
                suscripcion.cola.put_nowait(mensaje)
            except queue.Full:
                # Un cliente que no consume no debe frenar a los demás ni a
                # quien publica. Pierde ese mensaje; al reconectar recibe un
                # snapshot completo.
                pass

    @property
    def suscriptores(self) -> int:
        with self._candado:
            return len(self._suscripciones)


#: Difusor del proceso. Lo usan el adaptador de publicación y el endpoint.
broker = InMemoryBroker()
