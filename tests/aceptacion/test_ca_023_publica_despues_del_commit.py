"""CA-023 — El evento se publica después del commit."""

import pytest

from app.application import use_cases


class PublicadorEspia:
    def __init__(self):
        self.eventos = []

    def publish(self, event):
        self.eventos.append(event)


def test_ca_023(repo):
    """Si la operación falla y revierte, no debe haberse publicado nada."""
    use_cases.crear_retenciones(
        repo, event_id=1, user_id="user-2", seat_ids=[15]
    )

    espia = PublicadorEspia()
    with pytest.raises(use_cases.ButacasOcupadasError):
        use_cases.crear_retenciones(
            repo, event_id=1, user_id="user-1", seat_ids=[15], publisher=espia
        )

    assert espia.eventos == []
