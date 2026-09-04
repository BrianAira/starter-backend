#!/usr/bin/env python3
"""
Tablero de la Semana 4.

Reúne evidencia heterogénea en una sola vista: ejecuta pruebas, inspecciona
archivos, compara el OpenAPI con el contrato y verifica documentos derivados.

No reemplaza a la suite ni demuestra que el sistema esté bien. Demuestra que
estas comprobaciones concretas pasan. Ver la sección "Límites" de
docs/contrato/criterios_de_aceptacion.md.

Uso:
    python herramientas/evaluar_semana4.py
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

CONTEXTO = [
    "AGENTS.md",
    "docs/contrato/alcance.md",
    "docs/contrato/reglas.md",
    "docs/contrato/arquitectura.md",
    "docs/contrato/contrato_api_frontend.md",
    "docs/contrato/base_de_datos.md",
    "docs/contrato/criterios_de_aceptacion.md",
    "docs/contrato/trazabilidad.md",
]

# Rutas comprometidas en el contrato. Las dos últimas están declaradas y
# todavía no construidas: deben existir en el OpenAPI igualmente.
RUTAS_DEL_CONTRATO = [
    ("GET", "/health"),
    ("GET", "/users"),
    ("GET", "/events"),
    ("GET", "/events/{event_id}"),
    ("GET", "/events/{event_id}/seats"),
    ("POST", "/events/{event_id}/holds"),
    ("POST", "/holds/confirm"),
    ("DELETE", "/holds/{hold_id}"),
    ("GET", "/events/{event_id}/stream"),
]

PROHIBIDOS_ADENTRO = (
    "sqlalchemy",
    "psycopg",
    "alembic",
    "fastapi",
    "starlette",
    "app.infrastructure",
)

resultados: list[tuple[str, bool, str]] = []


def registrar(clave: str, ok: bool, detalle: str = "") -> None:
    resultados.append((clave, ok, detalle))


def _correr(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    entorno = os.environ.copy()
    entorno.setdefault("PYTHONPATH", str(RAIZ))
    if env:
        entorno.update(env)
    return subprocess.run(
        args, cwd=RAIZ, capture_output=True, text=True, env=entorno
    )


def ctx_contexto() -> None:
    faltan = [c for c in CONTEXTO if not (RAIZ / c).exists()]
    registrar("CTX", not faltan, "faltan: " + ", ".join(faltan) if faltan else "")


def ca_004_suite() -> None:
    proc = _correr(sys.executable, "-m", "pytest", "-q")
    registrar("CA-004", proc.returncode == 0, proc.stdout.strip().splitlines()[-1] if proc.stdout else "")


def ca_009_arquitectura() -> None:
    proc = _correr(sys.executable, "-m", "pytest", "-q", "tests/test_arquitectura.py")
    registrar("CA-009", proc.returncode == 0)


def ca_010_026_estanqueidad() -> None:
    """
    Ni Core ni Application importan infraestructura ni transporte.

    Es la misma inspección de siempre, ampliada: el canal de eventos no
    debe filtrarse hacia adentro (ARQ-010).
    """
    violaciones: list[str] = []
    for carpeta in ("app/core", "app/application"):
        for archivo in (RAIZ / carpeta).rglob("*.py"):
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            for nodo in ast.walk(arbol):
                nombres: list[str] = []
                if isinstance(nodo, ast.Import):
                    nombres = [a.name for a in nodo.names]
                elif isinstance(nodo, ast.ImportFrom) and nodo.module:
                    nombres = [nodo.module]
                for nombre in nombres:
                    if any(nombre.split(".")[0] == p.split(".")[0] and nombre.startswith(p) for p in PROHIBIDOS_ADENTRO):
                        violaciones.append(f"{archivo.relative_to(RAIZ)}: {nombre}")
    registrar("CA-010/026", not violaciones, "; ".join(violaciones))


def ca_011_rutas() -> None:
    # Solo se necesita el esquema OpenAPI, no una base. Se fija una URL de
    # SQLite antes de importar la app para no exigir PostgreSQL levantado.
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    from main import app

    esquema = app.openapi()
    faltantes = [
        f"{metodo} {ruta}"
        for metodo, ruta in RUTAS_DEL_CONTRATO
        if metodo.lower() not in esquema["paths"].get(ruta, {})
    ]
    registrar("CA-011", not faltantes, "faltan: " + ", ".join(faltantes) if faltantes else "")


def ca_006b_migracion() -> None:
    from sqlalchemy import create_engine, inspect

    from app.infrastructure.db import Base
    import app.infrastructure.models  # noqa: F401

    with tempfile.TemporaryDirectory() as carpeta:
        url = f"sqlite:///{Path(carpeta) / 'mig.db'}"
        proc = _correr(
            sys.executable, "-m", "alembic", "upgrade", "head",
            env={"DATABASE_URL": url},
        )
        if proc.returncode != 0:
            registrar("CA-006b", False, proc.stderr.strip().splitlines()[-1] if proc.stderr else "")
            return

        inspector = inspect(create_engine(url))
        reales = set(inspector.get_table_names()) - {"alembic_version"}
        esperadas = set(Base.metadata.tables)
        indices = {i["name"] for i in inspector.get_indexes("holds")}
        ok = reales == esperadas and "uq_holds_event_seat_active" in indices
        registrar("CA-006b", ok, "" if ok else f"tablas={sorted(reales)} indices={sorted(indices)}")


def ca_007_sin_create_all() -> None:
    texto = (RAIZ / "main.py").read_text(encoding="utf-8")
    registrar("CA-007", "create_all" not in texto)


def ca_013_diagrama() -> None:
    proc = _correr(
        sys.executable, "herramientas/generar_diagrama_estados.py", "--verificar"
    )
    registrar("CA-013", proc.returncode == 0)


def ca_017_sincronia_criterios() -> None:
    """
    Sincronía cruzada entre criterios y verificaciones derivadas.

    Mientras no exista tests/aceptacion/ el resultado es informativo: la
    generación de verificaciones desde criterios es tarea de la semana.
    """
    carpeta = RAIZ / "tests" / "aceptacion"
    documento = (RAIZ / "docs/contrato/criterios_de_aceptacion.md").read_text(
        encoding="utf-8"
    )
    declarados = set(re.findall(r"`(CA-\d+[a-z]?)`", documento))

    if not carpeta.exists():
        registrar("CA-017", False, "todavía no existe tests/aceptacion/")
        return

    referidos: set[str] = set()
    huerfanos: list[str] = []
    for archivo in carpeta.rglob("test_*.py"):
        encontrados = set(re.findall(r"(CA-\d+[a-z]?)", archivo.read_text(encoding="utf-8")))
        if not encontrados:
            huerfanos.append(archivo.name)
        referidos |= encontrados

    desconocidos = sorted(referidos - declarados)
    ok = not huerfanos and not desconocidos
    detalle = ""
    if huerfanos:
        detalle += "sin criterio: " + ", ".join(huerfanos) + " "
    if desconocidos:
        detalle += "criterios inexistentes: " + ", ".join(desconocidos)
    registrar("CA-017", ok, detalle.strip())


def main() -> int:
    ctx_contexto()
    ca_004_suite()
    ca_009_arquitectura()
    ca_010_026_estanqueidad()
    ca_011_rutas()
    ca_006b_migracion()
    ca_007_sin_create_all()
    ca_013_diagrama()
    ca_017_sincronia_criterios()

    ancho = max(len(clave) for clave, _, _ in resultados)
    print("\nTablero — Semana 4\n" + "-" * (ancho + 30))
    for clave, ok, detalle in resultados:
        marca = "OK  " if ok else "FALLA"
        print(f"{clave.ljust(ancho)}  {marca}  {detalle}")

    fallidos = [c for c, ok, _ in resultados if not ok]
    print("-" * (ancho + 30))
    if fallidos:
        print(f"{len(fallidos)} de {len(resultados)} sin cumplir: {', '.join(fallidos)}")
    else:
        print(f"{len(resultados)} comprobaciones cumplidas.")
    print(
        "\nUn tablero en verde significa que estas comprobaciones pasan.\n"
        "No demuestra que el sistema esté bien."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
