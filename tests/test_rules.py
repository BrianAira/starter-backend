"""Reglas puras del dominio. Sin base de datos, sin HTTP."""

from datetime import datetime, timedelta

import pytest

from app.core.entities import Hold, HoldStatus, Seat, SeatStatus
from app.core.rules import (
    RetencionDuplicadaError,
    RetencionNoConfirmableError,
    esta_vigente,
    proyectar_butaca,
    validar_confirmacion,
    validar_creacion_retencion,
)

AHORA = datetime(2026, 8, 7, 12, 0, 0)
BUTACA = Seat(id=1, room_id=1, label="A1", row="A", number=1, x=1, y=1, sector="PLATEA")


def _hold(status=HoldStatus.ACTIVE, minutos=10, user="user-1", hold_id=1):
    return Hold(
        id=hold_id,
        event_id=1,
        seat_id=1,
        user_id=user,
        status=status,
        created_at=AHORA,
        expires_at=AHORA + timedelta(minutes=minutos),
    )


def test_butaca_sin_retenciones_esta_disponible():
    vista = proyectar_butaca(BUTACA, [], AHORA)
    assert vista.status is SeatStatus.AVAILABLE
    assert vista.hold_id is None
    assert vista.held_by_user_id is None
    assert vista.expires_at is None


def test_retencion_vigente_ocupa_la_butaca():
    vista = proyectar_butaca(BUTACA, [_hold()], AHORA)
    assert vista.status is SeatStatus.HELD
    assert vista.held_by_user_id == "user-1"
    assert vista.expires_at is not None


def test_retencion_vencida_libera_la_butaca_y_no_filtra_datos():
    """RET-004: una retención vencida no se muestra como ocupación."""
    vista = proyectar_butaca(BUTACA, [_hold(minutos=-1)], AHORA)
    assert vista.status is SeatStatus.AVAILABLE
    assert vista.hold_id is None
    assert vista.held_by_user_id is None
    assert vista.expires_at is None


def test_confirmada_no_vence():
    vista = proyectar_butaca(
        BUTACA, [_hold(status=HoldStatus.CONFIRMED, minutos=-100)], AHORA
    )
    assert vista.status is SeatStatus.CONFIRMED
    assert vista.expires_at is None


@pytest.mark.parametrize(
    "status", [HoldStatus.EXPIRED, HoldStatus.RELEASED]
)
def test_estados_terminales_no_ocupan(status):
    assert esta_vigente(_hold(status=status), AHORA) is False


def test_ret001_rechaza_butaca_de_otro_usuario():
    with pytest.raises(RetencionDuplicadaError):
        validar_creacion_retencion([_hold(user="user-2")], "user-1", AHORA)


def test_retener_lo_propio_devuelve_la_retencion_existente():
    """Idempotencia: repetir un pedido propio no crea otra retención."""
    existente = _hold(user="user-1")
    assert validar_creacion_retencion([existente], "user-1", AHORA) is existente


def test_butaca_libre_no_devuelve_retencion():
    assert validar_creacion_retencion([], "user-1", AHORA) is None


def test_ret003_solo_confirma_una_retencion_vigente():
    validar_confirmacion(_hold(), AHORA)
    for hold in (
        _hold(minutos=-1),
        _hold(status=HoldStatus.CONFIRMED),
        _hold(status=HoldStatus.RELEASED),
    ):
        with pytest.raises(RetencionNoConfirmableError):
            validar_confirmacion(hold, AHORA)
