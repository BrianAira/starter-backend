"""
Demostración de la condición de carrera (Semana 1).

Se ejecuta aparte: `pytest -m race_demo`. Con la garantía del esquema
puesta, la carrera termina en un conflicto en lugar de en dos
retenciones sobre la misma butaca. Sin ella, este test mostraba el
defecto.

No es una prueba de la suite: es una demostración. Que pase no prueba que
el sistema aguante carga real, solo que dos peticiones que se cruzan
producen un ganador y un perdedor.
"""

import threading

import pytest

from app.application import use_cases
from app.core.rules import RetencionDuplicadaError
from app.infrastructure.db import SessionLocal
from app.infrastructure.repository import SqlAlchemyHoldRepository


@pytest.mark.race_demo
def test_dos_peticiones_simultaneas_producen_un_ganador(session):
    resultados: list[str] = []
    barrera = threading.Barrier(2)

    def intentar(user_id: str):
        barrera.wait()
        propia = SessionLocal()
        try:
            repo = SqlAlchemyHoldRepository(propia)
            use_cases.crear_retenciones(
                repo, event_id=1, user_id=user_id, seat_ids=[1]
            )
            resultados.append("ok")
        except (RetencionDuplicadaError, use_cases.ButacasOcupadasError):
            resultados.append("conflicto")
        except Exception as exc:  # pragma: no cover
            resultados.append(f"otro: {type(exc).__name__}")
        finally:
            propia.close()

    # Usuarios distintos a propósito: con el mismo usuario no habría
    # carrera sino idempotencia, y las dos peticiones ganarían.
    hilos = [
        threading.Thread(target=intentar, args=(user,))
        for user in ("user-1", "user-2")
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    assert resultados.count("ok") == 1, resultados
