"""
Entidades y estados del dominio.

Este módulo no debe importar FastAPI, SQLAlchemy, psycopg ni ningún
detalle de infraestructura. Ver AGENTS.md y docs/contrato/arquitectura.md.

Sobre los identificadores: eventos, salas, butacas y retenciones usan
enteros; los usuarios usan cadenas. No es una preferencia técnica: lo
fija docs/contrato/contrato_api_frontend.md, que ya está congelado.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class HoldStatus(str, Enum):
    """
    Estados internos de una retención.

    El dominio usa ACTIVE para una retención temporal vigente. La API lo
    traduce al estado público HELD. Ver docs/contrato/reglas.md.
    """

    ACTIVE = "active"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    RELEASED = "released"


class SeatStatus(str, Enum):
    """
    Estado público de una butaca. No se guarda: se calcula al leer.

    Ver docs/contrato/contrato_api_frontend.md, sección 3.1.
    """

    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    CONFIRMED = "CONFIRMED"


#: Estados internos que mantienen ocupada una butaca (RET-002).
ESTADOS_OCUPANTES = (HoldStatus.ACTIVE, HoldStatus.CONFIRMED)


@dataclass(frozen=True)
class User:
    id: str
    name: str


@dataclass(frozen=True)
class Room:
    id: int
    name: str
    rows: int
    columns: int


@dataclass(frozen=True)
class Event:
    id: int
    name: str
    room_id: int
    room_name: str
    starts_at: datetime


@dataclass(frozen=True)
class Seat:
    id: int
    room_id: int
    label: str
    row: str
    number: int
    x: int
    y: int
    sector: str


@dataclass(frozen=True)
class Hold:
    id: int
    event_id: int
    seat_id: int
    user_id: str
    status: HoldStatus
    created_at: datetime
    expires_at: datetime | None


@dataclass(frozen=True)
class SeatView:
    """
    Butaca con su estado público ya calculado. Es lo que consume la API
    y lo que viaja en el canal de eventos: una sola forma, un solo
    cálculo. Ver docs/contrato/contrato_api_frontend.md, regla 7.8.
    """

    seat: Seat
    status: SeatStatus
    hold_id: int | None
    held_by_user_id: str | None
    expires_at: datetime | None


@dataclass(frozen=True)
class SeatsChanged:
    """
    Evento de dominio: cambió el estado público de un conjunto de butacas.

    Transporta butacas completas, no el hecho que las cambió: así el
    consumidor no tiene que recalcular el estado por su cuenta.

    El dominio no sabe si esto termina en un canal SSE, en un WebSocket o
    en ningún lado. Ver ARQ-010.
    """

    event_id: int
    seats: tuple[SeatView, ...]
