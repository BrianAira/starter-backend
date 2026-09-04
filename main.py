"""
Punto de entrada de la aplicación.

Ensambla la app de FastAPI, monta las rutas y no crea tablas
automáticamente: el esquema se gestiona con Alembic. Ver README.md.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.infrastructure.db import SessionLocal
from app.infrastructure.repository import sembrar_datos_demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    session = SessionLocal()
    try:
        sembrar_datos_demo(session)
    finally:
        session.close()
    yield


app = FastAPI(
    title="Starter Backend IA — Complejo de salas para eventos",
    version="2.0.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(_: Request, __: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "INVALID_REQUEST",
                "message": "La petición no es válida.",
            }
        },
    )


app.include_router(router)
