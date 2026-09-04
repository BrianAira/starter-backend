"""
Garantía de RET-001 a nivel de esquema.

Estas pruebas no comprueban una regla escrita en Python: comprueban que
la base rechaza lo que no debe existir, aunque el código de aplicación se
equivoque. Ver ADR-003 y docs/contrato/base_de_datos.md.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.application import use_cases
from app.core.entities import HoldStatus
from app.core.rules import RetencionDuplicadaError
from app.infrastructure.models import HoldModel

AHORA = datetime(2026, 8, 7, 12, 0, 0)


def _insertar(session, seat_id, status=HoldStatus.ACTIVE, user="user-1"):
    session.add(
        HoldModel(
            event_id=1,
            seat_id=seat_id,
            user_id=user,
            status=status.value,
            created_at=AHORA,
            expires_at=AHORA + timedelta(minutes=15),
        )
    )
    session.flush()


def test_la_base_rechaza_dos_ocupaciones_de_la_misma_butaca(session):
    _insertar(session, 1)
    with pytest.raises(IntegrityError):
        _insertar(session, 1, user="user-2")
    session.rollback()


def test_una_confirmada_tambien_ocupa(session):
    _insertar(session, 2, status=HoldStatus.CONFIRMED)
    with pytest.raises(IntegrityError):
        _insertar(session, 2, user="user-2")
    session.rollback()


@pytest.mark.parametrize("status", [HoldStatus.EXPIRED, HoldStatus.RELEASED])
def test_los_estados_terminales_liberan_la_butaca(session, status):
    _insertar(session, 3, status=status)
    _insertar(session, 3, user="user-2")  # no debe fallar
    session.rollback()


def test_el_adaptador_traduce_el_error_de_la_base(repo, session):
    """
    ARQ-008: el IntegrityError no cruza la frontera. Application y API
    ven una excepción del dominio.
    """
    _insertar(session, 4, user="user-2")
    session.commit()

    with pytest.raises(RetencionDuplicadaError):
        with repo.transaccion():
            repo.crear_retencion(
                event_id=1,
                seat_id=4,
                user_id="user-1",
                expires_at=AHORA + timedelta(minutes=15),
            )


def test_la_sesion_sigue_usable_despues_del_conflicto(repo, session):
    _insertar(session, 5, user="user-2")
    session.commit()

    with pytest.raises(RetencionDuplicadaError):
        with repo.transaccion():
            repo.crear_retencion(
                event_id=1,
                seat_id=5,
                user_id="user-1",
                expires_at=AHORA + timedelta(minutes=15),
            )

    # La misma sesión puede seguir trabajando.
    assert repo.obtener_evento(1) is not None


def test_una_butaca_vencida_vuelve_a_poder_retenerse(repo, session):
    """
    El vencimiento se escribe dentro de la transacción, antes de insertar.
    Sin esa escritura, la butaca quedaría bloqueada para siempre por el
    índice, aunque el mapa la mostrara libre.
    """
    session.add(
        HoldModel(
            event_id=1,
            seat_id=6,
            user_id="user-2",
            status=HoldStatus.ACTIVE.value,
            created_at=AHORA,
            expires_at=AHORA + timedelta(minutes=1),
        )
    )
    session.commit()

    despues = AHORA + timedelta(minutes=30)
    holds = use_cases.crear_retenciones(
        repo, event_id=1, user_id="user-1", seat_ids=[6], ahora=despues
    )

    assert holds[0].user_id == "user-1"
