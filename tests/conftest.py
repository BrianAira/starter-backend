"""
Fixtures compartidas de la suite.

Decisión pragmática: la suite normal corre contra SQLite en archivo, no
contra PostgreSQL, para que no dependa de tener Docker levantado. Se
logra fijando DATABASE_URL antes de importar cualquier módulo de la app.

La garantía de concurrencia se valida además contra PostgreSQL en el
entorno de integración. SQLite soporta índices únicos parciales, así que
la garantía es comprobable acá, pero el comportamiento bajo carga real
no lo es.
"""

import os
import pathlib

_TEST_DB_PATH = pathlib.Path(__file__).parent / "test_data.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"

import pytest
from fastapi.testclient import TestClient

from app.infrastructure.db import Base, SessionLocal, engine
from app.infrastructure.repository import SqlAlchemyHoldRepository, sembrar_datos_demo


@pytest.fixture(autouse=True)
def _reiniciar_base():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture()
def session():
    s = SessionLocal()
    try:
        sembrar_datos_demo(s)
        yield s
    finally:
        s.close()


@pytest.fixture()
def repo(session):
    return SqlAlchemyHoldRepository(session)


@pytest.fixture()
def client():
    from main import app  # import diferido: ya con DATABASE_URL seteado

    with TestClient(app) as c:
        yield c
