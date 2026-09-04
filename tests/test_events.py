"""
Comportamiento observable de la API.

Cada aserción se corresponde con algo declarado en
docs/contrato/contrato_api_frontend.md.
"""


def _mapa(client, event_id=1):
    return client.get(f"/events/{event_id}/seats").json()


def _butaca(mapa, seat_id):
    return next(s for s in mapa["seats"] if s["id"] == seat_id)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_usuarios_precargados(client):
    datos = client.get("/users").json()
    assert {u["id"] for u in datos} == {"user-1", "user-2", "user-3"}


def test_evento_declara_su_sala(client):
    evento = client.get("/events").json()[0]
    assert evento["id"] == 1
    assert evento["room_id"] == 1
    assert evento["room_name"]


def test_evento_inexistente(client):
    respuesta = client.get("/events/999")
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"]["code"] == "EVENT_NOT_FOUND"


def test_mapa_trae_sala_y_coordenadas(client):
    mapa = _mapa(client)
    assert mapa["room"]["rows"] == 5
    assert mapa["room"]["columns"] == 8
    assert len(mapa["seats"]) == 40

    butaca = _butaca(mapa, 1)
    assert butaca["status"] == "AVAILABLE"
    assert butaca["hold_id"] is None
    assert (butaca["x"], butaca["y"]) == (1, 1)
    assert butaca["sector"] in {"PLATEA", "PULLMAN"}


def test_retener_un_lote(client):
    respuesta = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [1, 2, 3]}
    )
    assert respuesta.status_code == 201

    holds = respuesta.json()["holds"]
    assert [h["seat_id"] for h in holds] == [1, 2, 3]
    assert {h["expires_at"] for h in holds} != {None}
    assert len({h["expires_at"] for h in holds}) == 1

    mapa = _mapa(client)
    for seat_id in (1, 2, 3):
        butaca = _butaca(mapa, seat_id)
        assert butaca["status"] == "HELD"
        assert butaca["held_by_user_id"] == "user-1"


def test_retener_es_idempotente_para_el_mismo_usuario(client):
    primera = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [5]}
    ).json()["holds"]
    segunda = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [5]}
    ).json()["holds"]

    assert primera[0]["id"] == segunda[0]["id"]
    assert primera[0]["expires_at"] == segunda[0]["expires_at"]


def test_butaca_de_otro_usuario_da_conflicto_con_la_lista(client):
    client.post("/events/1/holds", json={"user_id": "user-1", "seat_ids": [7]})

    respuesta = client.post(
        "/events/1/holds", json={"user_id": "user-2", "seat_ids": [7, 8]}
    )
    assert respuesta.status_code == 409

    detalle = respuesta.json()["detail"]
    assert detalle["code"] == "SEATS_UNAVAILABLE"
    assert detalle["seat_ids"] == [7]


def test_el_lote_es_todo_o_nada(client):
    client.post("/events/1/holds", json={"user_id": "user-1", "seat_ids": [10]})
    client.post("/events/1/holds", json={"user_id": "user-2", "seat_ids": [10, 11]})

    assert _butaca(_mapa(client), 11)["status"] == "AVAILABLE"


def test_butaca_inexistente(client):
    respuesta = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [999]}
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"]["code"] == "SEATS_NOT_FOUND"
    assert respuesta.json()["detail"]["seat_ids"] == [999]


def test_usuario_inexistente(client):
    respuesta = client.post(
        "/events/1/holds", json={"user_id": "nadie", "seat_ids": [1]}
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"]["code"] == "USER_NOT_FOUND"


def test_cuerpo_invalido(client):
    respuesta = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": []}
    )
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"]["code"] == "INVALID_REQUEST"


def test_json_invalido_se_traduce_al_contrato(client):
    respuesta = client.post(
        "/events/1/holds",
        data="`��",
        headers={"Content-Type": "application/json"},
    )
    assert respuesta.status_code == 422
    assert respuesta.json() == {
        "detail": {
            "code": "INVALID_REQUEST",
            "message": "La petición no es válida.",
        }
    }


def test_confirmar_un_lote(client):
    holds = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [20, 21]}
    ).json()["holds"]

    respuesta = client.post(
        "/holds/confirm",
        json={"user_id": "user-1", "hold_ids": [h["id"] for h in holds]},
    )
    assert respuesta.status_code == 200
    assert all(h["status"] == "CONFIRMED" for h in respuesta.json()["holds"])

    mapa = _mapa(client)
    assert _butaca(mapa, 20)["status"] == "CONFIRMED"
    assert _butaca(mapa, 20)["expires_at"] is None


def test_confirmar_dos_veces_da_conflicto(client):
    holds = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [25]}
    ).json()["holds"]
    ids = [h["id"] for h in holds]

    client.post("/holds/confirm", json={"user_id": "user-1", "hold_ids": ids})
    respuesta = client.post(
        "/holds/confirm", json={"user_id": "user-1", "hold_ids": ids}
    )

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["code"] == "HOLDS_NOT_CONFIRMABLE"


def test_una_retencion_ajena_no_existe_para_este_usuario(client):
    holds = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [30]}
    ).json()["holds"]

    respuesta = client.post(
        "/holds/confirm",
        json={"user_id": "user-2", "hold_ids": [holds[0]["id"]]},
    )
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"]["code"] == "HOLDS_NOT_FOUND"


def test_liberar_una_butaca_del_lote(client):
    """Liberar saca una butaca de la selección sin perder las demás."""
    holds = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [35, 36]}
    ).json()["holds"]

    assert client.delete(f"/holds/{holds[0]['id']}").status_code == 204

    mapa = _mapa(client)
    assert _butaca(mapa, 35)["status"] == "AVAILABLE"
    assert _butaca(mapa, 36)["status"] == "HELD"


def test_liberar_una_retencion_inexistente(client):
    respuesta = client.delete("/holds/9999")
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"]["code"] == "HOLD_NOT_FOUND"


def test_liberar_id_invalido_no_cae_en_404_generico(client):
    respuesta = client.delete("/holds/null%2Cnull")
    assert respuesta.status_code == 422


def test_liberar_confirm_no_interpreta_confirm_como_hold_id(client):
    respuesta = client.delete("/holds/confirm")
    assert respuesta.status_code == 405
    assert respuesta.headers["allow"] == "POST"


def test_id_fuera_de_rango_no_produce_500(client):
    respuesta = client.post(
        "/events/915393049253/holds",
        json={
            "user_id": "user-1",
            "seat_ids": [8224, -301243, 281474976710656, -236165994336],
        },
    )
    assert respuesta.status_code == 422


def test_confirmar_hold_id_fuera_de_rango_da_not_found(client):
    respuesta = client.post(
        "/holds/confirm",
        json={"user_id": "user-1", "hold_ids": [9223372036854775808]},
    )
    assert respuesta.status_code == 422


def test_openapi_documenta_los_errores_del_contrato(client):
    openapi = client.get("/openapi.json").json()
    paths = openapi["paths"]
    components = openapi["components"]["schemas"]

    evento = paths["/events/{event_id}"]["get"]["parameters"][0]["schema"]
    assert evento["minimum"] == -2147483648
    assert evento["maximum"] == 2147483647

    hold = paths["/holds/{hold_id}"]["delete"]["parameters"][0]["schema"]
    assert hold["minimum"] == -2147483648
    assert hold["maximum"] == 2147483647

    seat_ids = components["CreateHoldsIn"]["properties"][
        "seat_ids"
    ]["items"]
    assert seat_ids["minimum"] == -2147483648
    assert seat_ids["maximum"] == 2147483647

    hold_ids = components["ConfirmHoldsIn"]["properties"][
        "hold_ids"
    ]["items"]
    assert hold_ids["minimum"] == -2147483648
    assert hold_ids["maximum"] == 2147483647

    assert _error_schema_name(
        paths["/events/{event_id}"]["get"]["responses"]["404"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}"]["get"]["responses"]["422"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}/seats"]["get"]["responses"]["404"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}/seats"]["get"]["responses"]["422"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}/holds"]["post"]["responses"]["404"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}/holds"]["post"]["responses"]["409"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}/holds"]["post"]["responses"]["422"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/holds/confirm"]["post"]["responses"]["404"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/holds/confirm"]["post"]["responses"]["409"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/holds/confirm"]["post"]["responses"]["422"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/holds/{hold_id}"]["delete"]["responses"]["404"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/holds/{hold_id}"]["delete"]["responses"]["409"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/holds/{hold_id}"]["delete"]["responses"]["422"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}/stream"]["get"]["responses"]["404"]
    ) == "ErrorOut"
    assert _error_schema_name(
        paths["/events/{event_id}/stream"]["get"]["responses"]["422"]
    ) == "ErrorOut"


def _error_schema_name(response: dict) -> str:
    return response["content"]["application/json"]["schema"]["$ref"].rsplit(
        "/", 1
    )[-1]


def test_el_canal_de_eventos_rechaza_un_evento_inexistente(client):
    """
    El resto del canal se verifica en tests/aceptacion/: una respuesta que
    no termina no se puede consumir con el cliente de pruebas.
    """
    respuesta = client.get("/events/999/stream")
    assert respuesta.status_code == 404
    assert respuesta.json()["detail"]["code"] == "EVENT_NOT_FOUND"
