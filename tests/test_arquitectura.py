"""Verificaciones ejecutables del contrato arquitectónico.

La definición normativa vive exclusivamente en
``docs/contrato/arquitectura.md``. Este módulo implementa parte de ese
contrato como pruebas automáticas, sin volver a redefinirlo.
"""

import ast
from pathlib import Path

APP_DIR = Path(__file__).parent.parent / "app"


def _imports_de(archivo: Path) -> list[str]:
    """Devuelve los módulos importados por un archivo sin ejecutarlo."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ImportFrom) and nodo.module:
            modulos.append(nodo.module)
        elif isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
    return modulos


def _coincide(modulo: str, prefijo: str) -> bool:
    return modulo == prefijo or modulo.startswith(prefijo + ".")


def test_arq_002_core_independiente():
    """Verifica ARQ-002."""
    prohibidos = (
        "fastapi",
        "sqlalchemy",
        "psycopg",
        "app.infrastructure",
        "app.api",
        "app.application",
    )
    violaciones: dict[str, list[str]] = {}

    for archivo in (APP_DIR / "core").glob("*.py"):
        encontrados = [
            modulo
            for modulo in _imports_de(archivo)
            if any(_coincide(modulo, prohibido) for prohibido in prohibidos)
        ]
        if encontrados:
            violaciones[archivo.name] = encontrados

    assert violaciones == {}, f"Violación de ARQ-002: {violaciones}"


def test_arq_003_application_no_importa_infrastructure():
    """Verifica ARQ-003 en todos los módulos de Application."""
    violaciones: dict[str, list[str]] = {}

    for archivo in (APP_DIR / "application").glob("*.py"):
        encontrados = [
            modulo
            for modulo in _imports_de(archivo)
            if _coincide(modulo, "app.infrastructure")
        ]
        if encontrados:
            violaciones[archivo.name] = encontrados

    assert violaciones == {}, f"Violación de ARQ-003: {violaciones}"


def test_arq_006_core_no_conoce_puertos():
    """Verifica ARQ-006 y la ubicación establecida por ARQ-007."""
    violaciones: dict[str, list[str]] = {}

    for archivo in (APP_DIR / "core").glob("*.py"):
        encontrados = [
            modulo
            for modulo in _imports_de(archivo)
            if _coincide(modulo, "app.application.ports")
        ]
        if encontrados:
            violaciones[archivo.name] = encontrados

    assert violaciones == {}, f"Violación de ARQ-006/ARQ-007: {violaciones}"
