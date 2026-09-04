"""CA-022 — Retener publica un evento con las butacas afectadas."""

from app.application import use_cases


class PublicadorEspia:
    def __init__(self):
        self.eventos = []

    def publish(self, event):
        self.eventos.append(event)


def test_ca_022(repo):
    espia = PublicadorEspia()

    use_cases.crear_retenciones(
        repo, event_id=1, user_id="user-1", seat_ids=[10, 11], publisher=espia
    )

    assert len(espia.eventos) == 1

    evento = espia.eventos[0]
    assert [v.seat.id for v in evento.seats] == [10, 11]
    assert all(v.status.value == "HELD" for v in evento.seats)
