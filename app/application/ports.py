"""
Puertos de la capa Application.

Un puerto es una interfaz que Application define para expresar QUÉ
necesita de una fuente externa, sin comprometerse con CÓMO se
implementa. El adaptador concreto vive en app/infrastructure.

La dependencia apunta hacia adentro: Infrastructure conoce a
Application porque cumple su contrato, no al revés.

Ver docs/contrato/arquitectura.md y docs/adr/ADR-002.md.
"""

from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol

from app.core.entities import Event, Hold, Room, Seat, SeatsChanged, User


class HoldRepository(Protocol):
    """Persistencia que necesitan los casos de uso de retenciones."""

    def transaccion(self) -> AbstractContextManager[None]:
        """
        Delimita una unidad de trabajo. Todo lo que ocurre adentro se
        confirma junto o no ocurre. Es lo que sostiene el "todo o nada"
        de las operaciones por lote.
        """
        ...

    def listar_usuarios(self) -> list[User]: ...

    def obtener_usuario(self, user_id: str) -> User | None: ...

    def listar_eventos(self) -> list[Event]: ...

    def obtener_evento(self, event_id: int) -> Event | None: ...

    def obtener_sala(self, room_id: int) -> Room | None: ...

    def listar_butacas_de_evento(self, event_id: int) -> list[Seat]: ...

    def holds_por_butaca(
        self, event_id: int, seat_ids: list[int] | None = None
    ) -> dict[int, list[Hold]]:
        """Retenciones de un evento, agrupadas por butaca."""
        ...

    def contar_butacas_ocupantes_de_usuario(
        self, event_id: int, user_id: str, ahora: datetime
    ) -> int:
        """Cantidad de butacas ocupantes del usuario para RET-007."""
        ...

    def marcar_vencidas(
        self, event_id: int, seat_ids: list[int], ahora: datetime
    ) -> None:
        """
        Escribe el vencimiento de las retenciones temporales cuyo plazo
        pasó. Es una escritura, no un cálculo: el índice único parcial no
        puede leer el reloj. Ver docs/contrato/base_de_datos.md.
        """
        ...

    def crear_retencion(
        self,
        event_id: int,
        seat_id: int,
        user_id: str,
        expires_at: datetime,
        demora_didactica_seg: float = 0.0,
    ) -> Hold: ...

    def obtener_hold(self, hold_id: int) -> Hold | None: ...

    def confirmar_hold(self, hold_id: int) -> Hold: ...

    def liberar_hold(self, hold_id: int) -> Hold: ...


class EventPublisher(Protocol):
    """
    Salida de eventos de dominio.

    Application publica contra este puerto. Que el evento termine en un
    canal SSE, en un WebSocket o en ningún lado es decisión del
    adaptador: el dominio no conoce el transporte (ARQ-010).
    """

    def publish(self, event: SeatsChanged) -> None: ...


class NullPublisher:
    """
    Publicador que descarta todo.

    Es el valor por defecto de los casos de uso: publicar es un efecto
    opcional y su ausencia no cambia el resultado de la operación.
    """

    def publish(self, event: SeatsChanged) -> None:
        return None
