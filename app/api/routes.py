"""
Adaptador de entrada HTTP.

Responsabilidad: rutas, validación de la petición y traducción de
errores de dominio a códigos HTTP. No contiene reglas de negocio ni
acceso a SQL. Ver docs/contrato/arquitectura.md.

Esta capa es también quien elige el adaptador de persistencia concreto:
construye un SqlAlchemyHoldRepository y lo inyecta. Application solo
conoce el puerto.
"""

import os
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from app.api.errors import error
from app.api.schemas import (
    ConfirmedHoldOut,
    ConfirmedHoldsOut,
    ConfirmHoldsIn,
    CreateHoldsIn,
    EventBriefOut,
    EventOut,
    ErrorOut,
    HoldOut,
    HoldsOut,
    PG_INTEGER_MAX,
    PG_INTEGER_MIN,
    RoomOut,
    SeatMapOut,
    SeatOut,
    UserOut,
)
from app.application import use_cases
from app.application.ports import HoldRepository
from app.core.rules import RetencionDuplicadaError, RetencionNoLiberableError
from app.infrastructure import sse
from app.infrastructure.broker import broker
from app.infrastructure.db import SessionLocal, get_session
from app.infrastructure.repository import SqlAlchemyHoldRepository

router = APIRouter()

# Permite ensanchar la ventana de la condición de carrera durante la
# demostración didáctica, sin tocar el código de negocio.
DEMORA_DIDACTICA_SEG = float(os.getenv("DEMORA_DIDACTICA_SEG", "0"))

# El plazo de una retención es configuración, no contrato: el Frontend
# lee expires_at y no necesita saber cuántos minutos son (regla 7.6).
TTL_MINUTOS = int(os.getenv("HOLD_TTL_MINUTOS", "15"))


def get_repo(session=Depends(get_session)) -> HoldRepository:
    return SqlAlchemyHoldRepository(session)


def get_publisher() -> sse.SseEventPublisher:
    """
    Elige el adaptador de salida de eventos. Application solo conoce el
    puerto; esta capa decide cuál se usa.
    """
    return sse.SseEventPublisher()


def _error_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    return {status_code: {"model": ErrorOut} for status_code in status_codes}


PgIntPath = Annotated[int, Path(ge=PG_INTEGER_MIN, le=PG_INTEGER_MAX)]


@router.get("/health", tags=["salud"])
def health():
    return {"status": "ok"}


@router.get("/users", response_model=list[UserOut], tags=["usuarios"])
def listar_usuarios(repo: HoldRepository = Depends(get_repo)):
    return [UserOut(id=u.id, name=u.name) for u in use_cases.listar_usuarios(repo)]


@router.get("/events", response_model=list[EventOut], tags=["eventos"])
def listar_eventos(repo: HoldRepository = Depends(get_repo)):
    return [EventOut(**vars(e)) for e in use_cases.listar_eventos(repo)]


@router.get(
    "/events/{event_id}",
    response_model=EventOut,
    responses=_error_responses(404, 422),
    tags=["eventos"],
)
def obtener_evento(event_id: PgIntPath, repo: HoldRepository = Depends(get_repo)):
    try:
        return EventOut(**vars(use_cases.obtener_evento(repo, event_id)))
    except use_cases.EventoNoEncontradoError:
        raise error(404, "EVENT_NOT_FOUND", "El evento no existe.")


@router.get(
    "/events/{event_id}/seats",
    response_model=SeatMapOut,
    responses=_error_responses(404, 422),
    tags=["eventos"],
)
def obtener_mapa(event_id: PgIntPath, repo: HoldRepository = Depends(get_repo)):
    try:
        evento, sala, vistas = use_cases.obtener_mapa(repo, event_id)
    except use_cases.EventoNoEncontradoError:
        raise error(404, "EVENT_NOT_FOUND", "El evento no existe.")

    return SeatMapOut(
        event=EventBriefOut(
            id=evento.id, name=evento.name, starts_at=evento.starts_at
        ),
        room=RoomOut(**vars(sala)),
        seats=[
            SeatOut(
                id=v.seat.id,
                label=v.seat.label,
                row=v.seat.row,
                number=v.seat.number,
                x=v.seat.x,
                y=v.seat.y,
                sector=v.seat.sector,
                status=v.status.value,
                hold_id=v.hold_id,
                held_by_user_id=v.held_by_user_id,
                expires_at=v.expires_at,
            )
            for v in vistas
        ],
    )


@router.post(
    "/events/{event_id}/holds",
    response_model=HoldsOut,
    status_code=201,
    responses=_error_responses(404, 409, 422),
    tags=["retenciones"],
)
def crear_retenciones(
    event_id: PgIntPath,
    body: CreateHoldsIn,
    repo: HoldRepository = Depends(get_repo),
    publisher=Depends(get_publisher),
):
    try:
        holds = use_cases.crear_retenciones(
            repo,
            event_id=event_id,
            user_id=body.user_id,
            seat_ids=body.seat_ids,
            publisher=publisher,
            ttl_minutos=TTL_MINUTOS,
            demora_didactica_seg=DEMORA_DIDACTICA_SEG,
        )
    except use_cases.EventoNoEncontradoError:
        raise error(404, "EVENT_NOT_FOUND", "El evento no existe.")
    except use_cases.UsuarioNoEncontradoError:
        raise error(404, "USER_NOT_FOUND", "El usuario no existe.")
    except use_cases.ButacasNoEncontradasError as exc:
        raise error(
            404,
            "SEATS_NOT_FOUND",
            "Una o más butacas no existen en esta sala.",
            seat_ids=exc.seat_ids,
        )
    except use_cases.ButacasOcupadasError as exc:
        raise error(
            409,
            "SEATS_UNAVAILABLE",
            "Una o más butacas ya no están disponibles.",
            seat_ids=exc.seat_ids,
        )
    except RetencionDuplicadaError:
        raise error(
            409,
            "SEATS_UNAVAILABLE",
            "Una o más butacas ya no están disponibles.",
            seat_ids=sorted(set(body.seat_ids)),
        )

    return HoldsOut(holds=[HoldOut(**_hold_dict(h)) for h in holds])


@router.post(
    "/holds/confirm",
    response_model=ConfirmedHoldsOut,
    responses=_error_responses(404, 409, 422),
    tags=["retenciones"],
)
def confirmar_retenciones(
    body: ConfirmHoldsIn,
    repo: HoldRepository = Depends(get_repo),
    publisher=Depends(get_publisher),
):
    try:
        holds = use_cases.confirmar_retenciones(
            repo,
            user_id=body.user_id,
            hold_ids=body.hold_ids,
            publisher=publisher,
        )
    except use_cases.UsuarioNoEncontradoError:
        raise error(404, "USER_NOT_FOUND", "El usuario no existe.")
    except use_cases.RetencionesNoEncontradasError as exc:
        raise error(
            404,
            "HOLDS_NOT_FOUND",
            "Una o más retenciones no existen.",
            hold_ids=exc.hold_ids,
        )
    except use_cases.RetencionesNoConfirmablesError as exc:
        raise error(
            409,
            "HOLDS_NOT_CONFIRMABLE",
            "Una o más retenciones no pueden confirmarse.",
            hold_ids=exc.hold_ids,
        )

    return ConfirmedHoldsOut(
        holds=[
            ConfirmedHoldOut(
                id=h.id, seat_id=h.seat_id, user_id=h.user_id, status="CONFIRMED"
            )
            for h in holds
        ]
    )


@router.delete("/holds/confirm", include_in_schema=False)
def rechazar_delete_confirm():
    raise HTTPException(
        status_code=405,
        detail="Method Not Allowed",
        headers={"Allow": "POST"},
    )


@router.delete(
    "/holds/{hold_id}",
    status_code=204,
    responses=_error_responses(404, 409, 422),
    tags=["retenciones"],
)
def liberar_retencion(
    hold_id: PgIntPath,
    repo: HoldRepository = Depends(get_repo),
    publisher=Depends(get_publisher),
):
    """
    Libera una retención. Es idempotente: liberar algo ya liberado o ya
    vencido también devuelve 204, porque el efecto deseado ya se cumple.
    """
    try:
        use_cases.liberar_retencion(repo, hold_id, publisher=publisher)
    except use_cases.RetencionNoEncontradaError:
        raise error(404, "HOLD_NOT_FOUND", "La retención no existe.")
    except RetencionNoLiberableError:
        raise error(
            409,
            "HOLD_NOT_RELEASABLE",
            "La retención está confirmada y no puede liberarse.",
        )


@router.get(
    "/events/{event_id}/stream",
    tags=["eventos"],
    response_class=StreamingResponse,
    responses={
        **_error_responses(404, 422),
        200: {
            "description": "Canal de eventos del servidor hacia el cliente.",
            "content": {"text/event-stream": {}},
        }
    },
)
def canal_de_eventos(event_id: PgIntPath, repo: HoldRepository = Depends(get_repo)):
    """
    Canal SSE. Notifica cambios de estado de las butacas de un evento.

    Es de notificación, no de operación: el servidor nunca recibe datos
    por acá. El primer evento es siempre un `snapshot` con el estado
    completo, para que el cliente no tenga que consultar el mapa aparte y
    perder lo que pase en el medio.

    El generador es sincrónico a propósito: Starlette lo ejecuta en un
    hilo aparte, que es donde la espera bloqueante de la cola no molesta a
    nadie.
    """
    try:
        evento, sala, vistas = use_cases.obtener_mapa(repo, event_id)
    except use_cases.EventoNoEncontradoError:
        # Antes de abrir el stream todavía se puede responder con un
        # código HTTP. Una vez abierto, ya no. Ver la regla 7 de la
        # Sección 4.9 del contrato.
        raise error(404, "EVENT_NOT_FOUND", "El evento no existe.")

    inicial = sse.mensaje_snapshot(evento, sala, vistas)
    suscripcion = broker.suscribir(event_id)

    return StreamingResponse(
        sse.generar_stream(inicial, suscripcion),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _hold_dict(hold) -> dict:
    return {
        "id": hold.id,
        "event_id": hold.event_id,
        "seat_id": hold.seat_id,
        "user_id": hold.user_id,
        "status": "HELD",
        "expires_at": hold.expires_at,
    }
