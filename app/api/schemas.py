"""
Esquemas de entrada y salida de la API.

Su forma la fija docs/contrato/contrato_api_frontend.md, que está
congelado. Ante una diferencia entre este archivo y ese documento, manda
el documento.
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer


PG_INTEGER_MIN = -2147483648
PG_INTEGER_MAX = 2147483647

PgInt = Annotated[int, Field(ge=PG_INTEGER_MIN, le=PG_INTEGER_MAX)]


def _utc_z(valor: datetime | None) -> str | None:
    """
    Serializa una marca de tiempo en ISO 8601 con Z, como exige la
    Sección 2 del contrato. Internamente el proyecto usa UTC ingenuo: la
    zona se agrega solamente acá, en el borde.
    """
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[datetime, PlainSerializer(_utc_z, return_type=str)]


class UserOut(BaseModel):
    id: str
    name: str


class EventOut(BaseModel):
    id: PgInt
    name: str
    room_id: PgInt
    room_name: str
    starts_at: UtcDatetime


class EventBriefOut(BaseModel):
    id: PgInt
    name: str
    starts_at: UtcDatetime


class RoomOut(BaseModel):
    id: PgInt
    name: str
    rows: PgInt
    columns: PgInt


class SeatOut(BaseModel):
    id: PgInt
    label: str
    row: str
    number: PgInt
    x: PgInt
    y: PgInt
    sector: str
    status: str
    hold_id: PgInt | None = None
    held_by_user_id: str | None = None
    expires_at: UtcDatetime | None = None


class SeatMapOut(BaseModel):
    event: EventBriefOut
    room: RoomOut
    seats: list[SeatOut]


class HoldOut(BaseModel):
    id: PgInt
    event_id: PgInt
    seat_id: PgInt
    user_id: str
    status: str
    expires_at: UtcDatetime | None = None


class HoldsOut(BaseModel):
    holds: list[HoldOut]


class ConfirmedHoldOut(BaseModel):
    id: PgInt
    seat_id: PgInt
    user_id: str
    status: str


class ConfirmedHoldsOut(BaseModel):
    holds: list[ConfirmedHoldOut]


class CreateHoldsIn(BaseModel):
    user_id: str
    seat_ids: list[PgInt] = Field(min_length=1)


class ConfirmHoldsIn(BaseModel):
    user_id: str
    hold_ids: list[PgInt] = Field(min_length=1)


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    detail: ErrorBody
