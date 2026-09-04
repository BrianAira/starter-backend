"""
Traducción de excepciones del dominio a respuestas HTTP.

El catálogo de códigos es cerrado y lo fija la Sección 5 del contrato.
Un código que no esté ahí no debe aparecer en una respuesta.
"""

from fastapi import HTTPException


def error(status_code: int, code: str, message: str, **extra) -> HTTPException:
    detail = {"code": code, "message": message}
    detail.update(extra)
    return HTTPException(status_code=status_code, detail=detail)
