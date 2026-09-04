"""
Configuración de acceso a base de datos.

Detalle técnico: usa la variable de entorno DATABASE_URL.
En docker-compose apunta a PostgreSQL. En tests, se sobreescribe
por una base SQLite liviana (ver tests/conftest.py) — esto es una
decisión pragmática para que la suite normal no dependa de tener
Postgres corriendo; la garantía de concurrencia real (Semana 3) sí
se valida contra Postgres.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:app@db:5432/app",
)


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str = DATABASE_URL):
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(database_url, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
