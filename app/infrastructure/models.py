"""
Modelos de persistencia (SQLAlchemy).

Estos modelos son detalle de infraestructura. No son las entidades de
dominio (ver app/core/entities.py). Application y Core no los importan.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)


class RoomModel(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    columns: Mapped[int] = mapped_column(Integer, nullable=False)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SeatModel(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    row: Mapped[str] = mapped_column(String, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    x: Mapped[int] = mapped_column(Integer, nullable=False)
    y: Mapped[int] = mapped_column(Integer, nullable=False)
    sector: Mapped[str] = mapped_column(String, nullable=False)

    Index("uq_seats_room_xy", room_id, x, y, unique=True)


class HoldModel(Base):
    __tablename__ = "holds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Garantía de RET-001: índice único parcial. Solo los estados que
    # mantienen ocupada la butaca participan de la unicidad, de modo que
    # una butaca liberada o vencida vuelve a poder retenerse.
    #
    # El predicado NO mira el reloj: una función como now() no es inmutable
    # y PostgreSQL no la admite acá. Por eso el vencimiento se escribe
    # (status pasa a 'expired') dentro de la transacción, antes de
    # insertar. Ver ADR-003 y docs/contrato/base_de_datos.md.
    Index(
        "uq_holds_event_seat_active",
        event_id,
        seat_id,
        unique=True,
        sqlite_where=text("status IN ('active','confirmed')"),
        postgresql_where=text("status IN ('active','confirmed')"),
    )
