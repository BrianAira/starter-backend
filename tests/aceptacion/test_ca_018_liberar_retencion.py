"""CA-018 — DELETE /holds/{hold_id} libera una retención vigente."""


def test_ca_018(client):
    hold = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [1]}
    ).json()["holds"][0]

    respuesta = client.delete(f"/holds/{hold['id']}")

    assert respuesta.status_code == 204
    assert respuesta.content == b""

    mapa = client.get("/events/1/seats").json()
    butaca = next(s for s in mapa["seats"] if s["id"] == 1)
    assert butaca["status"] == "AVAILABLE"
    assert butaca["hold_id"] is None
