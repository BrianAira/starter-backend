"""CA-019 — Liberar es idempotente."""


def test_ca_019(client):
    hold = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [2]}
    ).json()["holds"][0]

    client.delete(f"/holds/{hold['id']}")
    respuesta = client.delete(f"/holds/{hold['id']}")

    assert respuesta.status_code == 204
