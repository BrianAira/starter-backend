"""
Adaptador de persistencia sobre SQLAlchemy / PostgreSQL.

Traduce entre modelos de persistencia (ORM) y entidades de dominio.
Implementa el puerto app.application.ports.HoldRepository: la
dependencia apunta hacia adentro (Infrastructure -> Application).

Ver docs/contrato/arquitectura.md y docs/adr/ADR-002.md.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import DataError, IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.core.entities import Event, Hold, HoldStatus, Room, Seat, User
from app.core.rules import RetencionDuplicadaError
from app.infrastructure.models import (
    EventModel,
    HoldModel,
    RoomModel,
    SeatModel,
    UserModel,
)


def _user(m: UserModel) -> User:
    return User(id=m.id, name=m.name)


def _room(m: RoomModel) -> Room:
    return Room(id=m.id, name=m.name, rows=m.rows, columns=m.columns)


def _event(m: EventModel, room_name: str) -> Event:
    return Event(
        id=m.id,
        name=m.name,
        room_id=m.room_id,
        room_name=room_name,
        starts_at=m.starts_at,
    )


def _seat(m: SeatModel) -> Seat:
    return Seat(
        id=m.id,
        room_id=m.room_id,
        label=m.label,
        row=m.row,
        number=m.number,
        x=m.x,
        y=m.y,
        sector=m.sector,
    )


def _hold(m: HoldModel) -> Hold:
    return Hold(
        id=m.id,
        event_id=m.event_id,
        seat_id=m.seat_id,
        user_id=m.user_id,
        status=HoldStatus(m.status),
        created_at=m.created_at,
        expires_at=m.expires_at,
    )


class SqlAlchemyHoldRepository:
    """Implementación concreta del puerto HoldRepository."""

    def __init__(self, session: Session) -> None:
        self._session = session

    @contextmanager
    def transaccion(self):
        """
        Unidad de trabajo. Si algo falla adentro, no queda nada escrito.

        Traduce el error técnico de la base a una excepción del dominio:
        ni Application ni API conocen SQLAlchemy (ARQ-008).
        """
        try:
            yield
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise RetencionDuplicadaError(
                "La butaca ya está ocupada para este evento (RET-001)."
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    # -- lecturas ----------------------------------------------------

    def listar_usuarios(self) -> list[User]:
        modelos = self._session.scalars(
            select(UserModel).order_by(UserModel.id)
        ).all()
        return [_user(m) for m in modelos]

    def obtener_usuario(self, user_id: str) -> User | None:
        m = self._session.get(UserModel, user_id)
        return _user(m) if m else None

    def listar_eventos(self) -> list[Event]:
        filas = self._session.execute(
            select(EventModel, RoomModel)
            .join(RoomModel, RoomModel.id == EventModel.room_id)
            .order_by(EventModel.starts_at)
        ).all()
        return [_event(e, r.name) for e, r in filas]

    def obtener_evento(self, event_id: int) -> Event | None:
        fila = self._session.execute(
            select(EventModel, RoomModel)
            .join(RoomModel, RoomModel.id == EventModel.room_id)
            .where(EventModel.id == event_id)
        ).first()
        if fila is None:
            return None
        evento, sala = fila
        return _event(evento, sala.name)

    def obtener_sala(self, room_id: int) -> Room | None:
        m = self._session.get(RoomModel, room_id)
        return _room(m) if m else None

    def listar_butacas_de_evento(self, event_id: int) -> list[Seat]:
        modelos = self._session.scalars(
            select(SeatModel)
            .join(EventModel, EventModel.room_id == SeatModel.room_id)
            .where(EventModel.id == event_id)
            .order_by(SeatModel.y, SeatModel.x)
        ).all()
        return [_seat(m) for m in modelos]

    def holds_por_butaca(
        self, event_id: int, seat_ids: list[int] | None = None
    ) -> dict[int, list[Hold]]:
        consulta = select(HoldModel).where(HoldModel.event_id == event_id)
        if seat_ids is not None:
            consulta = consulta.where(HoldModel.seat_id.in_(seat_ids))

        agrupadas: dict[int, list[Hold]] = {}
        for m in self._session.scalars(consulta.order_by(HoldModel.id)).all():
            agrupadas.setdefault(m.seat_id, []).append(_hold(m))
        return agrupadas

    def obtener_hold(self, hold_id: int) -> Hold | None:
        try:
            m = self._session.get(HoldModel, hold_id)
        except (DataError, StatementError, OverflowError, ValueError):
            self._session.rollback()
            return None
        return _hold(m) if m else None

    # -- escrituras --------------------------------------------------

    def marcar_vencidas(
        self, event_id: int, seat_ids: list[int], ahora: datetime
    ) -> None:
        self._session.execute(
            update(HoldModel)
            .where(
                HoldModel.event_id == event_id,
                HoldModel.seat_id.in_(seat_ids),
                HoldModel.status == HoldStatus.ACTIVE.value,
                HoldModel.expires_at.is_not(None),
                HoldModel.expires_at <= ahora,
            )
            .values(status=HoldStatus.EXPIRED.value)
        )
        self._session.flush()

    def crear_retencion(
        self,
        event_id: int,
        seat_id: int,
        user_id: str,
        expires_at: datetime,
        demora_didactica_seg: float = 0.0,
    ) -> Hold:
        """
        Inserta una retención temporal.

        demora_didactica_seg existe solo para ensanchar la ventana de la
        condición de carrera durante la demostración. En producción vale 0.
        """
        if demora_didactica_seg:
            import time

            time.sleep(demora_didactica_seg)

        modelo = HoldModel(
            event_id=event_id,
            seat_id=seat_id,
            user_id=user_id,
            status=HoldStatus.ACTIVE.value,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            expires_at=expires_at.replace(tzinfo=None)
            if expires_at.tzinfo
            else expires_at,
        )
        self._session.add(modelo)
        self._session.flush()
        return _hold(modelo)

    def confirmar_hold(self, hold_id: int) -> Hold:
        m = self._session.get(HoldModel, hold_id)
        m.status = HoldStatus.CONFIRMED.value
        self._session.flush()
        return _hold(m)

    def liberar_hold(self, hold_id: int) -> Hold:
        m = self._session.get(HoldModel, hold_id)
        m.status = HoldStatus.RELEASED.value
        self._session.flush()
        return _hold(m)


def sembrar_datos_demo(session: Session) -> None:
    """
    Carga usuarios, una sala, sus butacas y un evento si la base está vacía.

    Es una utilidad de arranque, no una operación del caso de uso: por eso
    no forma parte del puerto.
    """
    if session.scalars(select(EventModel)).first() is not None:
        return

    for user_id, nombre in [
        ("user-1", "Ana"),
        ("user-2", "Bruno"),
        ("user-3", "Carla"),
    ]:
        session.add(UserModel(id=user_id, name=nombre))

    sala = RoomModel(name="Sala Principal", rows=5, columns=8)
    session.add(sala)
    session.flush()

    filas = ["A", "B", "C", "D", "E"]
    for y, fila in enumerate(filas, start=1):
        for x in range(1, sala.columns + 1):
            session.add(
                SeatModel(
                    room_id=sala.id,
                    label=f"{fila}{x}",
                    row=fila,
                    number=x,
                    x=x,
                    y=y,
                    sector="PLATEA" if y <= 2 else "PULLMAN",
                )
            )

    session.add(
        EventModel(
            name="Recital de ejemplo",
            room_id=sala.id,
            starts_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(days=7),
        )
    )
    session.commit()
