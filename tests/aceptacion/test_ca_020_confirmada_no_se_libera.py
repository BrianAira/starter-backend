"""CA-020 — Una retención confirmada no se libera."""


def test_ca_020(client):
    hold = client.post(
        "/events/1/holds", json={"user_id": "user-1", "seat_ids": [3]}
    ).json()["holds"][0]
    client.post(
        "/holds/confirm", json={"user_id": "user-1", "hold_ids": [hold["id"]]}
    )

    respuesta = client.delete(f"/holds/{hold['id']}")

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"]["code"] == "HOLD_NOT_RELEASABLE"
