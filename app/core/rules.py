"""
Reglas de negocio del dominio.

Este módulo es puro: recibe datos y decide. No hace I/O ni conoce la
base de datos. Ver docs/contrato/reglas.md y docs/contrato/trazabilidad.md.

RET-001  Una butaca no puede quedar ocupada dos veces.
RET-002  Qué significa que una butaca esté ocupada.
RET-003  Solo una retención vigente puede confirmarse.
RET-004  Una retención vence al llegar expires_at.

La validación de RET-001 acá NO resuelve la condición de carrera: entre
la consulta y la inserción puede colarse otra petición. Esa garantía la
da el índice único parcial del esquema. Ver ADR-003.
"""

from datetime import datetime

from app.core.entities import (
    ESTADOS_OCUPANTES,
    Hold,
    HoldStatus,
    Seat,
    SeatStatus,
    SeatView,
)


class RetencionDuplicadaError(Exception):
    """Se intentó ocupar una butaca que ya está ocupada por otro usuario."""


class RetencionNoConfirmableError(Exception):
    """Se intentó confirmar una retención que no está vigente (RET-003)."""


class RetencionNoLiberableError(Exception):
    """Se intentó liberar una retención ya confirmada."""


def esta_vencida(hold: Hold, ahora: datetime) -> bool:
    """
    RET-004. Una retención temporal está vencida cuando su plazo pasó.

    Una retención confirmada no vence: expires_at deja de tener efecto.
    """
    if hold.status is not HoldStatus.ACTIVE:
        return False
    return hold.expires_at is not None and hold.expires_at <= ahora


def esta_vigente(hold: Hold, ahora: datetime) -> bool:
    """
    RET-002. Una retención mantiene ocupada la butaca cuando su estado es
    ocupante y, si es temporal, todavía no venció. Las dos condiciones,
    siempre.
    """
    if hold.status not in ESTADOS_OCUPANTES:
        return False
    return not esta_vencida(hold, ahora)


def ocupante_de_butaca(holds: list[Hold], ahora: datetime) -> Hold | None:
    """
    Devuelve la retención que mantiene ocupada la butaca, si existe.

    Por RET-001 no puede haber más de una: si aparecen varias, es un
    defecto de la garantía y no algo que esta función deba resolver
    eligiendo. Se devuelve la primera de forma determinista.
    """
    vigentes = sorted(
        (h for h in holds if esta_vigente(h, ahora)), key=lambda h: h.id
    )
    return vigentes[0] if vigentes else None


def proyectar_butaca(seat: Seat, holds: list[Hold], ahora: datetime) -> SeatView:
    """
    Proyección única del estado público de una butaca.

    La usan la lectura del mapa y el canal de eventos. Dos
    implementaciones del mismo cálculo se desincronizan: por eso hay una
    sola. Ver docs/contrato/contrato_api_frontend.md, regla 7.8.
    """
    ocupante = ocupante_de_butaca(holds, ahora)

    if ocupante is None:
        return SeatView(
            seat=seat,
            status=SeatStatus.AVAILABLE,
            hold_id=None,
            held_by_user_id=None,
            expires_at=None,
        )

    publico = (
        SeatStatus.CONFIRMED
        if ocupante.status is HoldStatus.CONFIRMED
        else SeatStatus.HELD
    )
    return SeatView(
        seat=seat,
        status=publico,
        hold_id=ocupante.id,
        held_by_user_id=ocupante.user_id,
        expires_at=ocupante.expires_at if publico is SeatStatus.HELD else None,
    )


def validar_creacion_retencion(
    holds_de_la_butaca: list[Hold], user_id: str, ahora: datetime
) -> Hold | None:
    """
    RET-001 para una butaca concreta.

    Devuelve la retención existente si la butaca ya está ocupada por el
    mismo usuario, en cuyo caso crear una nueva sería un error y hay que
    reutilizarla (idempotencia). Devuelve None si la butaca está libre.
    Lanza RetencionDuplicadaError si la ocupa otro usuario.
    """
    ocupante = ocupante_de_butaca(holds_de_la_butaca, ahora)

    if ocupante is None:
        return None

    if ocupante.user_id == user_id and ocupante.status is HoldStatus.ACTIVE:
        return ocupante

    raise RetencionDuplicadaError(
        "La butaca ya está ocupada para este evento (RET-001)."
    )


def validar_confirmacion(hold: Hold, ahora: datetime) -> None:
    """RET-003: solo una retención temporal vigente puede confirmarse."""
    if hold.status is not HoldStatus.ACTIVE or esta_vencida(hold, ahora):
        raise RetencionNoConfirmableError(
            "La retención no puede confirmarse (RET-003)."
        )


def validar_liberacion(hold: Hold) -> None:
    """Una retención confirmada no puede liberarse."""
    if hold.status is HoldStatus.CONFIRMED:
        raise RetencionNoLiberableError(
            "La retención está confirmada y no puede liberarse."
        )
