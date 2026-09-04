"""
Casos de uso de la aplicación.

Coordina QUÉ pasos ejecutar y en qué orden. No conoce detalles HTTP
(eso es app/api) y no ejecuta SQL (eso es app/infrastructure).

Depende de los puertos de app.application.ports, nunca de una
implementación concreta.

Ver docs/contrato/arquitectura.md y docs/adr/ADR-002.md.
"""

from datetime import datetime, timedelta, timezone

from app.application.ports import EventPublisher, HoldRepository, NullPublisher
from app.core import rules
from app.core.entities import (
    Event,
    Hold,
    HoldStatus,
    Room,
    SeatsChanged,
    SeatView,
    User,
)

TTL_POR_DEFECTO_MINUTOS = 15


class EventoNoEncontradoError(Exception):
    pass


class UsuarioNoEncontradoError(Exception):
    pass


class ButacasNoEncontradasError(Exception):
    def __init__(self, seat_ids: list[int]) -> None:
        super().__init__(seat_ids)
        self.seat_ids = seat_ids


class RetencionNoEncontradaError(Exception):
    pass


class RetencionesNoEncontradasError(Exception):
    def __init__(self, hold_ids: list[int]) -> None:
        super().__init__(hold_ids)
        self.hold_ids = hold_ids


class RetencionesNoConfirmablesError(Exception):
    def __init__(self, hold_ids: list[int]) -> None:
        super().__init__(hold_ids)
        self.hold_ids = hold_ids


class ButacasOcupadasError(Exception):
    def __init__(self, seat_ids: list[int]) -> None:
        super().__init__(seat_ids)
        self.seat_ids = seat_ids


def _ahora(ahora: datetime | None) -> datetime:
    """
    Instante de referencia, en UTC y sin zona.

    El proyecto trabaja internamente con UTC ingenuo: la base guarda
    marcas sin zona y comparar una con zona contra una sin zona es un
    error de tipo. La zona se agrega recién al serializar, porque el
    contrato exige el sufijo Z. Ver la Sección 2 del contrato.
    """
    if ahora is not None:
        return ahora.replace(tzinfo=None) if ahora.tzinfo else ahora
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------
# Lecturas
# --------------------------------------------------------------------


def listar_usuarios(repo: HoldRepository) -> list[User]:
    return repo.listar_usuarios()


def listar_eventos(repo: HoldRepository) -> list[Event]:
    return repo.listar_eventos()


def obtener_evento(repo: HoldRepository, event_id: int) -> Event:
    evento = repo.obtener_evento(event_id)
    if evento is None:
        raise EventoNoEncontradoError(event_id)
    return evento


def obtener_mapa(
    repo: HoldRepository, event_id: int, ahora: datetime | None = None
) -> tuple[Event, Room, list[SeatView]]:
    """
    Devuelve el evento, su sala y todas las butacas con el estado público
    ya calculado. No escribe nada: el vencimiento acá se deriva.
    """
    momento = _ahora(ahora)
    evento = obtener_evento(repo, event_id)

    sala = repo.obtener_sala(evento.room_id)
    if sala is None:  # pragma: no cover - inconsistencia de datos
        raise EventoNoEncontradoError(event_id)

    butacas = repo.listar_butacas_de_evento(event_id)
    holds = repo.holds_por_butaca(event_id)

    vistas = [
        rules.proyectar_butaca(butaca, holds.get(butaca.id, []), momento)
        for butaca in butacas
    ]
    return evento, sala, vistas


# --------------------------------------------------------------------
# Escrituras
# --------------------------------------------------------------------


def crear_retenciones(
    repo: HoldRepository,
    event_id: int,
    user_id: str,
    seat_ids: list[int],
    publisher: EventPublisher | None = None,
    ttl_minutos: int = TTL_POR_DEFECTO_MINUTOS,
    ahora: datetime | None = None,
    demora_didactica_seg: float = 0.0,
) -> list[Hold]:
    """
    Retiene un lote de butacas para un usuario. Todo o nada.

    Pasos:
    1. Validar evento, usuario y existencia de las butacas.
    2. Marcar como vencidas las retenciones cuyo plazo pasó, dentro de la
       misma transacción y antes de insertar.
    3. Evaluar RET-001 por butaca, reutilizando la retención propia si ya
       existe (idempotencia).
    4. Insertar las que falten.
    5. Publicar el cambio, ya fuera de la transacción.

    Las butacas se procesan en orden ascendente de identificador: dos
    lotes que se cruzan en distinto orden podrían bloquearse mutuamente.
    """
    momento = _ahora(ahora)
    publisher = publisher or NullPublisher()
    pedidas = sorted(set(seat_ids))

    evento = obtener_evento(repo, event_id)

    if repo.obtener_usuario(user_id) is None:
        raise UsuarioNoEncontradoError(user_id)

    conocidas = {s.id for s in repo.listar_butacas_de_evento(event_id)}
    faltantes = [s for s in pedidas if s not in conocidas]
    if faltantes:
        raise ButacasNoEncontradasError(faltantes)

    expires_at = momento + timedelta(minutes=ttl_minutos)
    resultado: list[Hold] = []

    with repo.transaccion():
        repo.marcar_vencidas(event_id, pedidas, momento)
        holds = repo.holds_por_butaca(event_id, pedidas)

        ocupadas: list[int] = []
        a_crear: list[int] = []

        for seat_id in pedidas:
            try:
                propia = rules.validar_creacion_retencion(
                    holds.get(seat_id, []), user_id, momento
                )
            except rules.RetencionDuplicadaError:
                ocupadas.append(seat_id)
                continue

            if propia is not None:
                resultado.append(propia)
            else:
                a_crear.append(seat_id)

        if ocupadas:
            raise ButacasOcupadasError(ocupadas)

        for seat_id in a_crear:
            resultado.append(
                repo.crear_retencion(
                    event_id=event_id,
                    seat_id=seat_id,
                    user_id=user_id,
                    expires_at=expires_at,
                    demora_didactica_seg=demora_didactica_seg,
                )
            )

    publicar_cambio(repo, publisher, event_id, pedidas, momento)
    return sorted(resultado, key=lambda h: h.seat_id)


def confirmar_retenciones(
    repo: HoldRepository,
    user_id: str,
    hold_ids: list[int],
    publisher: EventPublisher | None = None,
    ahora: datetime | None = None,
) -> list[Hold]:
    """
    Confirma un lote de retenciones del usuario. Todo o nada.

    Una retención que no existe y una retención de otro usuario producen
    el mismo resultado a propósito: una retención ajena no existe para
    este usuario.
    """
    momento = _ahora(ahora)
    publisher = publisher or NullPublisher()
    pedidos = sorted(set(hold_ids))

    if repo.obtener_usuario(user_id) is None:
        raise UsuarioNoEncontradoError(user_id)

    encontrados: list[Hold] = []
    ausentes: list[int] = []
    for hold_id in pedidos:
        hold = repo.obtener_hold(hold_id)
        if hold is None or hold.user_id != user_id:
            ausentes.append(hold_id)
        else:
            encontrados.append(hold)

    if ausentes:
        raise RetencionesNoEncontradasError(ausentes)

    no_confirmables: list[int] = []
    for hold in encontrados:
        try:
            rules.validar_confirmacion(hold, momento)
        except rules.RetencionNoConfirmableError:
            no_confirmables.append(hold.id)

    if no_confirmables:
        raise RetencionesNoConfirmablesError(no_confirmables)

    with repo.transaccion():
        confirmados = [repo.confirmar_hold(h.id) for h in encontrados]

    publicar_cambio(
        repo,
        publisher,
        encontrados[0].event_id,
        [h.seat_id for h in encontrados],
        momento,
    )
    return confirmados


def liberar_retencion(
    repo: HoldRepository,
    hold_id: int,
    publisher: EventPublisher | None = None,
    ahora: datetime | None = None,
) -> None:
    """
    Libera una retención individual.

    Es idempotente: liberar algo ya liberado o ya vencido devuelve el
    mismo resultado, porque el efecto deseado —que la butaca no esté
    tomada por este usuario— ya se cumple. Solo una retención confirmada
    se rechaza.
    """
    momento = _ahora(ahora)
    publisher = publisher or NullPublisher()

    hold = repo.obtener_hold(hold_id)
    if hold is None:
        raise RetencionNoEncontradaError(hold_id)

    rules.validar_liberacion(hold)

    if hold.status is not HoldStatus.ACTIVE:
        return  # ya estaba liberada o vencida: nada que escribir

    with repo.transaccion():
        repo.liberar_hold(hold_id)

    publicar_cambio(repo, publisher, hold.event_id, [hold.seat_id], momento)


# --------------------------------------------------------------------
# Publicación
# --------------------------------------------------------------------


def publicar_cambio(
    repo: HoldRepository,
    publisher: EventPublisher,
    event_id: int,
    seat_ids: list[int],
    momento: datetime,
) -> None:
    """
    Publica el estado público resultante de las butacas afectadas.

    Se llama DESPUÉS de cerrar la transacción, nunca adentro: si la
    transacción revierte, no debe haberse publicado nada. Ver la regla
    7.7 del contrato.

    Se publica la butaca completa, con la misma proyección que usa la
    lectura del mapa: una sola función calcula el estado (regla 7.8).
    """
    butacas = {s.id: s for s in repo.listar_butacas_de_evento(event_id)}
    holds = repo.holds_por_butaca(event_id, seat_ids)

    vistas = tuple(
        rules.proyectar_butaca(butacas[seat_id], holds.get(seat_id, []), momento)
        for seat_id in sorted(set(seat_ids))
        if seat_id in butacas
    )
    if vistas:
        publisher.publish(SeatsChanged(event_id=event_id, seats=vistas))
