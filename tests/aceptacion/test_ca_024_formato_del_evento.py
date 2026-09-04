"""CA-024 — El evento se serializa con el formato del canal."""

import json

from app.core.entities import SeatsChanged
from app.core.rules import proyectar_butaca
from app.infrastructure import sse


def test_ca_024(repo):
    from datetime import datetime

    butaca = repo.listar_butacas_de_evento(1)[0]
    vista = proyectar_butaca(butaca, [], datetime(2026, 8, 7, 12, 0, 0))
    evento = SeatsChanged(event_id=1, seats=(vista,))

    bloque = sse.formatear(sse.mensaje_de_cambio(evento), id_evento=7)
    lineas = bloque.strip().splitlines()

    assert lineas[0] == "id: 7"
    assert lineas[1] == "event: seats.updated"
    assert lineas[2].startswith("data: ")
    assert bloque.endswith("\n\n")

    datos = json.loads(lineas[2][len("data: ") :])
    assert "seats" in datos
    assert datos["seats"][0]["id"] == butaca.id
