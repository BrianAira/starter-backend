#!/usr/bin/env python3
"""
Genera el diagrama de estados de una retención leyendo el código fuente.

Este script produce un documento DERIVADO: no define nada nuevo, describe lo
que el código vigente hace. Por eso no se edita a mano.

Uso:
    python herramientas/generar_diagrama_estados.py              # escribe el archivo
    python herramientas/generar_diagrama_estados.py --verificar  # solo compara

El modo --verificar sale con código 1 si el archivo commiteado difiere de lo
que se deriva del código: es el mecanismo que impide que el diagrama envejezca
en silencio.

LÍMITES DE ESTE ANÁLISIS
------------------------
El script lee la estructura del código con `ast`, sin ejecutarlo. Puede afirmar
que NO ENCONTRÓ una asignación de cierto estado en los archivos analizados. No
puede afirmar que ese estado sea inalcanzable: un estado podría escribirse por
SQL directo, por una migración, por reflexión o desde código no analizado.

La diferencia entre "no se detectó" y "no existe" es todo el contenido de esta
herramienta.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
APP = RAIZ / "app"
ENTIDADES = APP / "core" / "entities.py"
SALIDA = RAIZ / "docs" / "diagramas" / "estados_retencion.md"

ENUM_OBJETIVO = "HoldStatus"
# Funciones cuyo nombre indica creación de la entidad: producen el estado inicial.
PREFIJOS_DE_CREACION = ("crear", "create", "nuevo", "new")


def estados_declarados(archivo: Path = ENTIDADES) -> list[str]:
    """Devuelve los miembros del enum de estados, en orden de declaración."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.ClassDef) and nodo.name == ENUM_OBJETIVO:
            return [
                a.targets[0].id
                for a in nodo.body
                if isinstance(a, ast.Assign)
                and isinstance(a.targets[0], ast.Name)
            ]
    return []


def _estado_referido(expresion: ast.AST, estados: list[str]) -> str | None:
    """Extrae 'ACTIVE' de HoldStatus.ACTIVE, HoldStatus.ACTIVE.value o "active"."""
    texto = ast.unparse(expresion)
    for estado in estados:
        if f"{ENUM_OBJETIVO}.{estado}" in texto:
            return estado
        if texto.strip("\"'").upper() == estado:
            return estado
    return None


def productores(estados: list[str]) -> dict[str, list[tuple[str, str]]]:
    """
    Para cada estado, qué funciones lo asignan.

    Detecta dos formas: asignación a un atributo `.status` y paso del estado
    como argumento `status=` al construir un modelo.
    """
    encontrados: dict[str, list[tuple[str, str]]] = {e: [] for e in estados}

    for archivo in sorted(APP.rglob("*.py")):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        ruta = archivo.relative_to(RAIZ).as_posix()

        for funcion in ast.walk(arbol):
            if not isinstance(funcion, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if funcion.name.startswith("_"):
                continue  # helpers de traducción: leen, no producen

            for nodo in ast.walk(funcion):
                candidatos: list[ast.AST] = []

                if isinstance(nodo, ast.Assign):
                    destino = nodo.targets[0]
                    if isinstance(destino, ast.Attribute) and destino.attr == "status":
                        candidatos.append(nodo.value)

                if isinstance(nodo, ast.Call):
                    candidatos.extend(
                        kw.value for kw in nodo.keywords if kw.arg == "status"
                    )

                for candidato in candidatos:
                    estado = _estado_referido(candidato, estados)
                    if estado and (ruta, funcion.name) not in encontrados[estado]:
                        encontrados[estado].append((ruta, funcion.name))

    return encontrados


def _es_creacion(nombre_funcion: str) -> bool:
    return nombre_funcion.lower().startswith(PREFIJOS_DE_CREACION)


def construir_documento() -> str:
    estados = estados_declarados()
    mapa = productores(estados)

    iniciales = [
        e for e in estados if any(_es_creacion(f) for _, f in mapa[e])
    ]
    estado_inicial = iniciales[0] if iniciales else (estados[0] if estados else "?")

    lineas = ["stateDiagram-v2"]
    supuestos: list[str] = []

    for estado in estados:
        for ruta, funcion in mapa[estado]:
            if _es_creacion(funcion) and estado in iniciales:
                lineas.append(f"    [*] --> {estado}: {funcion}")
            else:
                lineas.append(f"    {estado_inicial} --> {estado}: {funcion}")
                supuestos.append(
                    f"`{estado_inicial} --> {estado}` ({funcion} en `{ruta}`): "
                    f"el análisis detecta la asignación del estado destino pero "
                    f"no puede determinar el estado de origen. Se asume "
                    f"`{estado_inicial}`."
                )

    sin_productor = [e for e in estados if not mapa[e]]

    doc = [
        "# Estados de una retención",
        "",
        "<!-- DOCUMENTO DERIVADO — NO EDITAR A MANO -->",
        "<!-- Se regenera con: python herramientas/generar_diagrama_estados.py -->",
        "",
        "Este archivo representa el código vigente. No define reglas nuevas: las",
        "reglas asociadas viven en `docs/contrato/reglas.md` y se referencian por",
        "identificador.",
        "",
        "```mermaid",
        *lineas,
        "```",
        "",
        "## Productores detectados",
        "",
        "| Estado | Producido por |",
        "|---|---|",
    ]

    for estado in estados:
        if mapa[estado]:
            detalle = "; ".join(f"`{f}` en `{r}`" for r, f in mapa[estado])
        else:
            detalle = "— sin productor detectado —"
        doc.append(f"| `{estado}` | {detalle} |")

    if sin_productor:
        doc += [
            "",
            "## Estados sin productor detectado",
            "",
            "No se detectaron asignaciones de los siguientes estados en los archivos",
            "analizados de `app/`:",
            "",
        ]
        doc += [f"- `{e}`" for e in sin_productor]
        doc += [
            "",
            "Esto significa que el análisis estático no encontró código que los",
            "produzca. **No significa que sean inalcanzables**: podrían escribirse",
            "por SQL directo, por una migración o desde código fuera de `app/`.",
        ]

    if supuestos:
        doc += ["", "## Supuestos del análisis", ""]
        doc += [f"- {s}" for s in dict.fromkeys(supuestos)]

    doc += [
        "",
        "## Límite de la herramienta",
        "",
        "El generador lee la estructura del código sin ejecutarlo. Puede afirmar",
        "qué encontró; no puede afirmar que no exista lo que no encontró.",
        "",
    ]

    return "\n".join(doc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verificar",
        action="store_true",
        help="No escribe: compara y sale con código 1 si hay diferencias.",
    )
    args = parser.parse_args()

    generado = construir_documento()

    if not args.verificar:
        SALIDA.parent.mkdir(parents=True, exist_ok=True)
        SALIDA.write_text(generado, encoding="utf-8")
        print(f"Escrito: {SALIDA.relative_to(RAIZ)}")
        return 0

    if not SALIDA.exists():
        print(f"FALTA el documento derivado: {SALIDA.relative_to(RAIZ)}")
        return 1

    actual = SALIDA.read_text(encoding="utf-8")
    if actual.strip() == generado.strip():
        print("El diagrama commiteado coincide con el código.")
        return 0

    import difflib

    print("DESINCRONIZADO: el diagrama commiteado no coincide con el código.\n")
    for linea in difflib.unified_diff(
        actual.splitlines(),
        generado.splitlines(),
        fromfile="commiteado",
        tofile="derivado del código",
        lineterm="",
    ):
        print(linea)
    return 1


if __name__ == "__main__":
    sys.exit(main())
