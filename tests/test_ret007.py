"""Verificaciones de RET-007: límite de butacas ocupantes por usuario."""

from datetime import datetime, timedelta

import pytest

from app.application import use_cases
from app.core.rules import LimiteButacasUsuarioError

AHORA = datetime(2026, 8, 7, 12, 0, 0)


def test_un_usuario_puede_retener_hasta_cuatro_butacas(client):
    respuesta = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [1, 2, 3, 4]}
    )

    assert respuesta.status_code == 201
    assert [hold["seat_id"] for hold in respuesta.json()["holds"]] == [1, 2, 3, 4]


def test_el_limite_rechaza_la_quinta_retencion_activa_por_http(client):
    client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [1, 2, 3, 4]}
    )

    respuesta = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [5]}
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["code"] == "USER_HOLD_LIMIT_REACHED"


def test_el_limite_incluye_retenciones_confirmadas(client):
    creadas = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [1, 2, 3, 4]}
    ).json()["holds"]
    confirmacion = client.post(
        "/holds/confirm",
        json={"user_id": "user-1", "hold_ids": [hold["id"] for hold in creadas]},
    )

    respuesta = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [5]}
    )

    assert confirmacion.status_code == 200
    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == {
        "code": "USER_HOLD_LIMIT_REACHED",
        "message": "El usuario no puede tener más de 4 butacas ocupadas para un mismo evento.",
    }
    assert client.get("/events/1/seats").json()["seats"][4]["status"] == "AVAILABLE"


def test_retenciones_vencidas_no_cuentan_para_el_limite(repo):
    use_cases.crear_retenciones(
        repo,
        event_id=1,
        user_id="user-1",
        seat_ids=[1, 2, 3, 4],
        ttl_minutos=1,
        ahora=AHORA,
    )

    nuevas = use_cases.crear_retenciones(
        repo,
        event_id=1,
        user_id="user-1",
        seat_ids=[5],
        ahora=AHORA + timedelta(minutes=2),
    )

    assert [hold.seat_id for hold in nuevas] == [5]


def test_retenciones_liberadas_no_cuentan_para_el_limite(repo):
    creadas = use_cases.crear_retenciones(
        repo, event_id=1, user_id="user-1", seat_ids=[1, 2, 3, 4], ahora=AHORA
    )
    for hold in creadas:
        use_cases.liberar_retencion(repo, hold.id, ahora=AHORA)

    nuevas = use_cases.crear_retenciones(
        repo, event_id=1, user_id="user-1", seat_ids=[5], ahora=AHORA
    )

    assert [hold.seat_id for hold in nuevas] == [5]


def test_el_caso_de_uso_rechaza_el_quinto_cupo_de_forma_atomica(repo):
    use_cases.crear_retenciones(
        repo, event_id=1, user_id="user-1", seat_ids=[1, 2, 3, 4], ahora=AHORA
    )

    with pytest.raises(LimiteButacasUsuarioError):
        use_cases.crear_retenciones(
            repo, event_id=1, user_id="user-1", seat_ids=[5, 6], ahora=AHORA
        )

    mapa = use_cases.obtener_mapa(repo, 1, ahora=AHORA)[2]
    assert all(vista.status.value == "AVAILABLE" for vista in mapa if vista.seat.id in {5, 6})
